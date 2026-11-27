"""Actualizaciones de PockTV desde GitHub (Releases).

Flujo: leer version.json -> si hay version mayor, el usuario acepta -> descargar PockTV.zip ->
verificar (sha256, estructura, compilar los .py) -> copia de seguridad -> copiar archivos -> si algo falla, volver atras.
Nunca toca: listas/, ajustes.json, lista.m3u, ui.conf, *.log ni los favoritos del usuario.
"""
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import zipfile

VERSION = "1.0.2"
REPO = "PocketApps-PR/PockTV"
BASE = "https://github.com/%s/releases/latest/download/" % REPO
UA = "PockTV-updater"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
KEEP_DIRS = ("listas",)
KEEP_FILES = ("ui.conf", "ajustes.json", "lista.m3u", "lista.url")

# estado visible para la pantalla: idle / checking / ok / new / downloading / installing / done / error
ST = {"status": "idle", "ver": "", "notes": "", "prog": 0.0, "msg": "", "sha": ""}
_lock = threading.Lock()


def _log(msg):
    try:
        with open(os.path.join(APP_DIR, "iptv_ui.log"), "a") as f:
            f.write("%s actualizacion: %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def vtuple(v):
    out = []
    for p in str(v).strip().lstrip("vV").split("."):
        d = "".join(c for c in p if c.isdigit())
        out.append(int(d) if d else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def _get(url, dest=None, prog=None, timeout=25):
    """Descarga url. Devuelve bytes (si dest es None) o True al guardar en dest. urllib primero, wget de respaldo."""
    err = None
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            clen = int(r.headers.get("Content-Length") or 0)
            if dest is None:
                return r.read(200000)
            tot = 0
            with open(dest, "wb") as f:
                while True:
                    c = r.read(65536)
                    if not c:
                        break
                    f.write(c)
                    tot += len(c)
                    if prog and clen > 0:
                        prog(min(1.0, tot / float(clen)))
            if tot > 0:
                return True
    except Exception as e:
        err = repr(e)
        _log("urllib fallo: %s" % err)
    tmp = dest or os.path.join(APP_DIR, ".upd_tmp")
    try:
        rc = subprocess.call(["wget", "--no-check-certificate", "-U", UA, "-T", "30", "-q", "-O", tmp, url])
        if rc == 0 and os.path.getsize(tmp) > 0:
            if dest is None:
                with open(tmp, "rb") as f:
                    data = f.read(200000)
                os.remove(tmp)
                return data
            return True
    except Exception as e:
        _log("wget fallo: %r" % (e,))
    try:
        os.remove(tmp)
    except OSError:
        pass
    raise RuntimeError(err or "sin conexion")


def _set(**kw):
    with _lock:
        ST.update(kw)


def check(silent=False):
    """Busca version nueva en segundo plano. silent: al abrir la app, un fallo no muestra nada."""
    if ST["status"] in ("checking", "downloading", "installing"):
        return
    _set(status="checking", msg="")

    def work():
        try:
            data = json.loads(_get(BASE + "version.json").decode("utf-8"))
            ver = str(data.get("version", "")).strip()
            if not ver:
                raise ValueError("version.json sin version")
            _log("version publicada %s, instalada %s" % (ver, VERSION))
            if vtuple(ver) > vtuple(VERSION):
                _set(status="new", ver=ver, notes=str(data.get("notes", "")), sha=str(data.get("sha256", "")).lower())
            else:
                _set(status="ok", ver=ver)
        except Exception as e:
            _log("no se pudo comprobar: %r" % (e,))
            _set(status="idle" if silent else "error", msg="sin_conexion")
    threading.Thread(target=work, daemon=True).start()


def install():
    """Descarga e instala la version anunciada (solo si el usuario acepto)."""
    if ST["status"] != "new":
        return
    _set(status="downloading", prog=0.0, msg="")

    def work():
        stage = os.path.join(APP_DIR, ".upd_stage")
        backup = os.path.join(APP_DIR, ".upd_backup")
        copied = []
        try:
            shutil.rmtree(stage, ignore_errors=True)
            os.makedirs(stage)
            zpath = os.path.join(stage, "PockTV.zip")
            _get(BASE + "PockTV.zip", zpath, lambda p: _set(prog=p), timeout=40)
            _set(status="installing", prog=1.0)
            sha = ST["sha"]
            if sha:
                h = hashlib.sha256()
                with open(zpath, "rb") as f:
                    for c in iter(lambda: f.read(1 << 20), b""):
                        h.update(c)
                if h.hexdigest() != sha:
                    raise ValueError("sha256 no coincide")
            ex = os.path.join(stage, "x")
            with zipfile.ZipFile(zpath) as z:
                if z.testzip() is not None:
                    raise ValueError("zip danado")
                names = z.namelist()
                for n in names:
                    if n.startswith("/") or ".." in n.split("/"):
                        raise ValueError("ruta insegura: %s" % n)
                if "PockTV/main.py" not in names or "PockTV/launch.sh" not in names:
                    raise ValueError("el zip no es de PockTV")
                z.extractall(ex)
            root = os.path.join(ex, "PockTV")
            files = []
            for dp, dn, fn in os.walk(root):
                rel = os.path.relpath(dp, root)
                if rel.split(os.sep)[0] in KEEP_DIRS:
                    continue
                for n in fn:
                    r = os.path.normpath(os.path.join(rel, n))
                    if r in KEEP_FILES or r.endswith(".log"):
                        continue
                    files.append(r)
            for r in files:                                     # los .py deben compilar antes de tocar nada
                if r.endswith(".py"):
                    compile(open(os.path.join(root, r), "rb").read(), r, "exec")
            shutil.rmtree(backup, ignore_errors=True)
            os.makedirs(backup)
            for r in files:
                dst = os.path.join(APP_DIR, r)
                if os.path.exists(dst):
                    b = os.path.join(backup, r)
                    os.makedirs(os.path.dirname(b), exist_ok=True)
                    shutil.copy2(dst, b)
            try:
                for r in files:
                    dst = os.path.join(APP_DIR, r)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(root, r), dst + ".new")
                    os.replace(dst + ".new", dst)
                    copied.append(r)
                try:
                    os.chmod(os.path.join(APP_DIR, "launch.sh"), 0o755)
                except OSError:
                    pass
            except Exception:
                for r in copied:                                # volver atras
                    b = os.path.join(backup, r)
                    try:
                        if os.path.exists(b):
                            shutil.copy2(b, os.path.join(APP_DIR, r))
                        else:
                            os.remove(os.path.join(APP_DIR, r))
                    except OSError:
                        pass
                raise
            _log("instalada %s (%d archivos)" % (ST["ver"], len(files)))
            _set(status="done")
        except Exception as e:
            _log("fallo la instalacion: %r" % (e,))
            _set(status="error", msg="fallo")
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    threading.Thread(target=work, daemon=True).start()
