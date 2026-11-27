"""PockTV (IPTV con interfaz) para SpruceOS (Miyoo Flip). Usa PySDL2, el que Spruce trae para PyUI.
Todo lo que pasa queda en iptv_ui.log (botones, errores) para poder ajustarlo.
"""
import ctypes
import os
import re
import signal
import subprocess
import threading
import sys
import time
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from i18n import T, set_lang, get_lang  # noqa: E402
from core import (load_file, read_conf, load_favs, save_favs,  # noqa: E402
                  DEFAULT_KW_SERIES, DEFAULT_KW_PELIS)

LOG_PATH = os.path.join(APP_DIR, "iptv_ui.log")


def log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def download_list(url, dest, prog=None):
    """Descarga lista.url (urllib primero, wget de respaldo). Devuelve aviso o ''."""
    tmp = dest + ".new"
    err = ""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "IPTVSmartersPro", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=40) as r, open(tmp, "wb") as f:
            log("descarga: HTTP %s, tipo %s" % (r.status, r.headers.get("Content-Type")))
            total = 0
            try:
                clen = int(r.headers.get("Content-Length") or 0)
            except Exception:
                clen = 0
            if clen <= 0:                       # sin tamaño: se usa el de la descarga anterior
                try:
                    clen = os.path.getsize(dest)
                except OSError:
                    clen = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if prog is not None:
                    try:
                        prog(min(0.97, total / float(clen)) if clen > 0 else None)
                    except Exception:
                        pass
        log("descarga: %d bytes" % total)
        if total > 0:
            os.replace(tmp, dest)
            return ""
        err = "respuesta vacia"
    except Exception as e:
        err = repr(e)
        log("descarga urllib fallo: %s" % err)
    try:
        rc = subprocess.call(["wget", "--no-check-certificate", "-U", "IPTVSmartersPro", "-T", "30", "-q", "-O", tmp, url])
        log("wget rc=%s" % rc)
        if rc == 0 and os.path.getsize(tmp) > 0:
            os.replace(tmp, dest)
            return ""
    except Exception as e:
        log("wget fallo: %r" % (e,))
    try:
        os.remove(tmp)
    except OSError:
        pass
    if os.path.exists(dest):
        return T("dl_fail")
    if "Name or service" in err or "resolution" in err or "unreachable" in err:
        return T("no_internet")
    return T("dl_fail_log")


def ffplay_reason():
    """Ultima linea util de ffplay.log para mostrarla en pantalla."""
    try:
        with open(os.path.join(APP_DIR, "ffplay.log"), "rb") as f:
            lines = f.read().decode("utf-8", "replace").splitlines()
    except Exception:
        return T("see_log")
    skip = ("Canal:", "URL:", "ffplay:", "ffplay termino")
    cand = [l.strip() for l in lines if l.strip() and not l.startswith(skip)]
    for l in reversed(cand):
        if any(k in l.lower() for k in ("error", "invalid", "not found", "failed", "unable", "aviso", "refused", "denied")):
            return l[:90]
    return cand[-1][:90] if cand else T("see_log")


def auth_failed():
    """True si ffplay.log termina con 401/403 (el servidor rechazo la peticion)."""
    try:
        with open(os.path.join(APP_DIR, "ffplay.log"), "rb") as f:
            tail = f.read()[-1500:].decode("utf-8", "replace").lower()
    except Exception:
        return False
    return any(k in tail for k in ("401 unauthorized", "403 forbidden", "authorization failed", "returned 401", "returned 403"))


VLC_UA = "VLC/3.0.20 LibVLC/3.0.20"
UA_TRY = set()     # URLs que ya fallaron con 401/403 y se reintentan como VLC


def main():
    try:
        open(LOG_PATH, "w").close()
    except Exception:
        pass
    try:
        import faulthandler
        CRASH_F = open(os.path.join(APP_DIR, "crash.log"), "w")
        faulthandler.enable(CRASH_F)
    except Exception:
        faulthandler = None
        CRASH_F = None

    _wd_t = [0.0]

    def wd():
        """Vigilante: si la app se queda 15 s sin pasar por aqui, escribe en crash.log donde esta atascada."""
        if faulthandler is None or time.time() - _wd_t[0] < 1.0:
            return
        _wd_t[0] = time.time()
        try:
            faulthandler.dump_traceback_later(15, repeat=False, file=CRASH_F)
        except Exception:
            pass
    log("inicio, python %s" % sys.version.split()[0])
    log("PYSDL2_DLL_PATH=%s" % os.environ.get("PYSDL2_DLL_PATH"))

    conf = read_conf(os.path.join(APP_DIR, "ui.conf"))
    import json
    import sdl2
    from gfx_sdl import Sdl2Gfx
    from ui import UI, SPLIT as SPLIT_CATS, series_parts
    import tracks

    # ---- ajustes guardados (idioma, reloj, video...) ----
    settings_path = os.path.join(APP_DIR, "ajustes.json")
    settings = {"lang": "es", "content_lang": "all", "show_unknown": True, "clock": "12", "snd": "suave",
                "video": "normal", "source": "main"}
    loaded = {}
    try:
        with open(settings_path, "r") as f:
            loaded = json.load(f)
            settings.update(loaded)
    except Exception:
        pass
    if not settings.get("clock12_v1"):          # reloj de 12 horas como predeterminado (una sola vez; luego se respeta la eleccion)
        settings["clock"] = "12"
        settings["clock12_v1"] = True
    # Prioridades de idioma (audio hasta 4, subtitulos hasta 3), por separado para peliculas y series.
    # Si el archivo es de una version anterior, se aprovechan los valores viejos.
    old_audio = [c for c in loaded.get("audio_prio", ["lat", "cas", "spa", "eng"]) if c != "all"][:4]
    old_subs = [c for c in (loaded.get("sub1", "none"), loaded.get("sub2", "none")) if c not in ("none", "all")]
    settings.setdefault("aud_movies", list(old_audio))
    settings.setdefault("aud_series", list(old_audio))
    settings.setdefault("sub_movies", list(old_subs))
    settings.setdefault("sub_series", list(old_subs))
    for k in ("audio_prio", "sub1", "sub2"):
        settings.pop(k, None)
    set_lang(settings.get("lang", "es"))

    def save_settings():
        try:
            tmp = settings_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(settings, f)
            os.replace(tmp, settings_path)
        except Exception:
            log("no pude guardar ajustes: " + traceback.format_exc())

    W = int(conf.get("WIDTH", "640"))
    H = int(conf.get("HEIGHT", "480"))
    gfx = Sdl2Gfx(os.path.join(APP_DIR, "fonts"), W, H, log)
    gfx.open()

    def splash(msg, frac=None):
        """Pantalla de espera; con frac (0..1) dibuja la barra de progreso y el porcentaje."""
        try:
            gfx.clear((12, 14, 28))
            if frac is None:
                gfx.text(msg, W // 2, H // 2 - 20, 26, (255, 255, 255), "c", True)
                gfx.text(T("wait"), W // 2, H // 2 + 20, 16, (150, 155, 175), "c")
            else:
                frac = max(0.0, min(1.0, frac))
                gfx.text(msg, W // 2, H // 2 - 40, 26, (255, 255, 255), "c", True)
                bw, bh = 360, 14
                x, y = (W - bw) // 2, H // 2 + 4
                gfx.rect(x - 2, y - 2, bw + 4, bh + 4, (70, 75, 100), 8)
                gfx.rect(x, y, bw, bh, (24, 27, 48), 7)
                fw = max(bh, int(bw * frac))
                gfx.rect(x, y, fw, bh, (90, 170, 255), 7)
                gfx.rect(x + 4, y + 2, max(2, fw - 8), 4, (150, 205, 255), 2)
                gfx.text("%d%%" % int(frac * 100), W // 2, y + bh + 10, 20, (255, 255, 255), "c", True)
                gfx.text(T("wait"), W // 2, y + bh + 44, 16, (150, 155, 175), "c")
            gfx.present()
        except Exception:
            log(traceback.format_exc())

    def make_prog(msg, lo, hi):
        """Devuelve prog(frac) que dibuja la barra entre lo y hi (limitado a ~12 cuadros/s)."""
        st = [0.0, -1.0]
        def prog(fr):
            now = time.time()
            if fr is None:
                fr = 0.0
            v = lo + (hi - lo) * max(0.0, min(1.0, fr))
            if now - st[0] < 0.08 and v < hi - 0.001:
                return
            st[0] = now
            splash(msg, v)
        return prog

    # ---- listas: la principal (lista.url / lista.m3u) y las de la carpeta listas/ ----
    lista = os.path.join(APP_DIR, "lista.m3u")
    listas_dir = os.path.join(APP_DIR, "listas")
    cache_dir = os.path.join(listas_dir, ".cache")
    kw_s = conf.get("KW_SERIES", DEFAULT_KW_SERIES)
    kw_p = conf.get("KW_PELIS", DEFAULT_KW_PELIS)

    def read_url_from(path):
        """Direccion http(s) guardada en un .url/.txt (una linea), o '' si no lo es."""
        try:
            with open(path, "rb") as f:
                txt = f.read(8192).decode("utf-8", "replace").lstrip("﻿")
        except Exception:
            return ""
        if txt.lstrip().startswith("#EXTM3U"):
            return ""
        for ln in txt.splitlines():
            ln = ln.strip().strip("\"'").strip()
            if ln:
                return ln if ln.lower().startswith(("http://", "https://")) else ""
        return ""

    def discover_sources():
        srcs = []
        main_url = read_url_from(os.path.join(APP_DIR, "lista.url")) if os.path.exists(
            os.path.join(APP_DIR, "lista.url")) else ""
        if os.path.isdir(listas_dir):
            for fn in sorted(os.listdir(listas_dir)):
                full = os.path.join(listas_dir, fn)
                if fn.startswith(".") or not os.path.isfile(full):
                    continue
                if fn.lower().startswith(("00_", "leeme", "readme")):     # el archivo de instrucciones no es una lista
                    continue
                stem, ext = os.path.splitext(fn)
                ext = ext.lower()
                if ext in (".m3u", ".m3u8"):
                    srcs.append({"id": "f:" + fn, "name": stem, "url": "", "path": full})
                elif ext in (".url", ".txt"):
                    u = read_url_from(full)
                    if u:
                        srcs.append({"id": "f:" + fn, "name": stem, "url": u,
                                     "path": os.path.join(cache_dir, stem + ".m3u")})
                    else:
                        try:
                            with open(full, "rb") as f:
                                if f.read(16).lstrip(b"\xef\xbb\xbf").startswith(b"#EXTM3U"):
                                    srcs.append({"id": "f:" + fn, "name": stem, "url": "", "path": full})
                        except Exception:
                            pass
        return srcs

    def load_source(src, download):
        """Devuelve (entradas, aviso)."""
        notice = ""
        if src["url"] and download:
            os.makedirs(os.path.dirname(src["path"]), exist_ok=True)
            splash(T("downloading"), 0.0)
            log("descargando %s -> %s" % (src["url"].split("?")[0], src["path"]))
            notice = download_list(src["url"], src["path"], make_prog(T("downloading"), 0.0, 0.6))
            did_dl = True
        else:
            did_dl = False
        entries = []
        if os.path.exists(src["path"]):
            lo_ = 0.6 if (did_dl and not notice) else 0.0
            splash(T("reading"), lo_)
            entries = load_file(src["path"], kw_s, kw_p, make_prog(T("reading"), lo_, 1.0))
            splash(T("reading"), 1.0)                 # se ve el 100 % un instante
            time.sleep(0.35)
        elif not notice:
            notice = T("no_list")
        return entries, notice

    # ---- vencimiento de cada lista (servidores tipo Xtream: player_api.php) ----
    exp_file = os.path.join(APP_DIR, "expiry.json")
    exp_flag = [False]
    exp_busy = [False]
    EXP_TTL = 6 * 3600

    def exp_cache():
        try:
            with open(exp_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def exp_creds(src):
        """(servidor, usuario, clave) de una lista, o None. Nunca se escriben en el log."""
        from urllib.parse import urlsplit, parse_qs
        try:
            if src.get("url"):
                sp = urlsplit(src["url"])
                q = parse_qs(sp.query)
                if q.get("username") and q.get("password"):
                    return "%s://%s" % (sp.scheme, sp.netloc), q["username"][0], q["password"][0]
            with open(src["path"], "rb") as f:
                txt = f.read(300000).decode("utf-8", "replace")
            m = re.search(r"(https?://[^/\s\"']+)/(?:live/|movie/|series/)?([^/\s\"']+)/([^/\s\"']+)/\d+", txt)
            if m:
                return m.group(1), m.group(2), m.group(3)
        except Exception:
            pass
        return None

    def exp_fetch(src):
        """{"st": ok|none|na, "ts": segundos}"""
        cr = exp_creds(src)
        if not cr:
            return {"st": "na"}
        import urllib.request
        from urllib.parse import quote
        url = "%s/player_api.php?username=%s&password=%s" % (cr[0], quote(cr[1]), quote(cr[2]))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "IPTVSmartersPro", "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read(200000).decode("utf-8", "replace"))
            ui_ = data.get("user_info") or {}
            ed = ui_.get("exp_date")
            if ed in (None, "", "null", 0, "0"):
                return {"st": "none"} if ui_ else {"st": "na"}
            return {"st": "ok", "ts": int(float(ed))}
        except Exception as ex:
            log("vencimiento: no se pudo consultar (%s)" % type(ex).__name__)
            return {"st": "na"}

    def exp_start():
        """Pone lo guardado al instante y consulta en segundo plano lo que esta viejo."""
        cache = exp_cache()
        todo = []
        for sc in list(sources):
            c = cache.get(sc["id"])
            if c and c.get("st") in ("ok", "none"):
                sc["exp"] = {"st": c["st"], "ts": c.get("ts")}
            else:
                sc["exp"] = {"st": "load"}
            if not c or time.time() - c.get("at", 0) > EXP_TTL or c.get("st") == "na":
                todo.append(sc)
        if not todo or exp_busy[0]:
            exp_flag[0] = True
            return

        def work():
            exp_busy[0] = True
            try:
                for sc in todo:
                    r = exp_fetch(sc)
                    cache = exp_cache()
                    if r["st"] != "na" or sc["id"] not in cache:
                        cache[sc["id"]] = dict(r, at=time.time())
                    try:
                        with open(exp_file, "w") as f:
                            json.dump(cache, f)
                    except Exception:
                        pass
                    old = cache.get(sc["id"], r)
                    sc["exp"] = {"st": old["st"] if r["st"] == "na" and old.get("st") in ("ok", "none") else r["st"],
                                 "ts": old.get("ts") if r["st"] == "na" else r.get("ts")}
                    exp_flag[0] = True
            finally:
                exp_busy[0] = False
        threading.Thread(target=work, daemon=True).start()

    sources = discover_sources()
    active = None
    for sc in sources:
        if sc["id"] == settings.get("source", "main"):
            active = sc
    if active is None and sources:
        active = sources[0]
    exp_start()
    log("listas: %s | activa: %s" % ([sc["id"] for sc in sources], active["id"] if active else None))
    if active is not None:
        entries, notice = load_source(active, download=(active["id"] == "main" or not os.path.exists(active["path"])))
    else:
        entries, notice = [], T("no_list")
    log("entradas: %d" % len(entries))

    favs_path = os.path.join(APP_DIR, "favoritos.json")
    from sound import Sound
    snd = Sound(os.path.join(APP_DIR, "sounds"), log)

    def ui_sig():
        return (ui.state, ui.sel, ui.idx, ui.gidx, ui.sidx, ui.col, tuple(ui.set_path), tuple(ui.set_idx),
                ui.m_idx, ui.confirm_quit, ui.kb_row, ui.kb_col)

    def snd_after(action, before):
        """Sonido de la interfaz: mover (si el cursor se movio), elegir y volver; en Ajustes > Sonido suena la muestra."""
        st = settings.get("snd", "suave")
        try:
            if action in ("up", "down", "left", "right"):
                if ui_sig() == before:
                    return
                if ui.state == "settings" and tuple(ui.set_path) == ("sound",):
                    opts = ui._options("snd_style")
                    hi = ui.set_idx[-1] if ui.set_idx else 0
                    if 0 <= hi < len(opts):
                        snd.play(opts[hi][0], "ok")
                else:
                    snd.play(st, "move")
            elif action == "ok":
                snd.play(st, "ok")
            elif action == "back":
                snd.play(st, "back")
        except Exception:
            log("sonido: " + traceback.format_exc())

    ui = UI(gfx, entries, active["name"] if active else "-", notice, load_favs(favs_path), settings, sources)
    try:
        import updater
        updater.check(silent=True)                       # un solo vistazo al abrir; si hay version nueva, aparece el puntito
    except Exception:
        pass
    log("favoritos: %d" % len(ui.favs))

    # ---- senal de internet (icono de wifi del inicio): gris sin conexion, blanco con conexion ----
    net = {"ok": False, "wifi": None}

    def read_wifi_level():
        """Rayitas de wifi (0-3) como el icono de la consola; -1 si no hay enlace; None si no se puede leer."""
        try:
            with open("/proc/net/wireless") as f:
                rows = [l for l in f.read().splitlines()[2:] if ":" in l]
            if rows:
                parts = rows[0].split(":", 1)[1].split()
                q = float(parts[1].rstrip("."))
                dbm = float(parts[2].rstrip("."))
                if dbm > 0:
                    dbm -= 256
                if q <= 0 and dbm <= -100:
                    return -1
                lvl = 2 if dbm >= -65 else 1 if dbm >= -75 else 0
                net["raw"] = (q, dbm)
                return lvl
        except Exception:
            pass
        try:
            out = subprocess.run(["iw", "dev", "wlan0", "link"], capture_output=True, timeout=3).stdout.decode()
            if "Not connected" in out:
                return -1
            mt = re.search(r"signal:\s*(-?\d+)", out)
            if mt:
                dbm = int(mt.group(1))
                return 2 if dbm >= -65 else 1 if dbm >= -75 else 0
        except Exception:
            pass
        try:
            with open("/sys/class/net/wlan0/operstate") as f:
                return 2 if f.read().strip() == "up" else -1
        except Exception:
            return None

    def net_loop():
        import socket
        while True:
            ok = False
            for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
                try:
                    socket.create_connection((host, port), timeout=3).close()
                    ok = True
                    break
                except Exception:
                    pass
            if ok != net["ok"]:
                log("internet: %s" % ("conectado" if ok else "sin conexion"))
            net["ok"] = ok
            lv = read_wifi_level()
            if lv != net["wifi"]:
                log("wifi: nivel %s %s" % (lv, net.get("raw", "")))
            net["wifi"] = lv
            time.sleep(10 if ok else 4)

    threading.Thread(target=net_loop, daemon=True).start()

    # Botones del joystick (indices). Mira iptv_ui.log si no coinciden.
    BTN_OK = int(conf.get("BTN_OK", "0"))
    BTN_BACK = int(conf.get("BTN_BACK", "1"))
    BTN_PGUP = int(conf.get("BTN_PGUP", "4"))
    BTN_PGDN = int(conf.get("BTN_PGDN", "5"))
    BTN_FAV = int(conf.get("BTN_FAV", "2"))
    BTN_SEARCH = int(conf.get("BTN_SEARCH", "3"))
    BTN_HOME_JOY = int(conf.get("BTN_HOME_JOY", "8"))
    joy_map = {BTN_OK: "ok", BTN_BACK: "back", BTN_PGUP: "l1", BTN_PGDN: "r1", BTN_HOME_JOY: "home",
               BTN_FAV: "fav", BTN_SEARCH: "search"}
    # Mando (GameController): A/B/X/Y por nombre; SWAP_AB="1" los intercambia
    swap = conf.get("SWAP_AB", "1") == "1"
    ok_a, back_a = ("back", "ok") if swap else ("ok", "back")
    fav_x, search_y = ("search", "fav") if swap else ("fav", "search")
    ctrl_map = {
        sdl2.SDL_CONTROLLER_BUTTON_A: ok_a, sdl2.SDL_CONTROLLER_BUTTON_B: back_a,
        sdl2.SDL_CONTROLLER_BUTTON_X: fav_x, sdl2.SDL_CONTROLLER_BUTTON_Y: search_y,
        sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: "l1", sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: "r1",
        int(conf.get("BTN_HOME", str(sdl2.SDL_CONTROLLER_BUTTON_GUIDE))): "home",
        sdl2.SDL_CONTROLLER_BUTTON_START: "start",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: "up", sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: "down",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: "left", sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: "right",
    }
    K = sdl2
    key_map = {
        K.SDLK_UP: "up", K.SDLK_DOWN: "down", K.SDLK_LEFT: "left", K.SDLK_RIGHT: "right",
        K.SDLK_RETURN: "ok", K.SDLK_SPACE: "ok", K.SDLK_a: "ok",
        K.SDLK_ESCAPE: "back", K.SDLK_BACKSPACE: "back", K.SDLK_b: "back",
        K.SDLK_PAGEUP: "pgup", K.SDLK_PAGEDOWN: "pgdn",
        K.SDLK_x: "fav", K.SDLK_y: "search",
    }

    opened = []
    state = {"controllers": 0}

    def open_inputs():
        del opened[:]
        state["controllers"] = 0
        n = sdl2.SDL_NumJoysticks()
        log("joysticks detectados: %d" % n)
        for i in range(n):
            try:
                if sdl2.SDL_IsGameController(i):
                    c = sdl2.SDL_GameControllerOpen(i)
                    if c:
                        opened.append(c)
                        state["controllers"] += 1
                        log("controlador %d: %s" % (i, sdl2.SDL_GameControllerName(c)))
                        continue
                j = sdl2.SDL_JoystickOpen(i)
                if j:
                    opened.append(j)
                    log("joystick %d: %s, botones=%d" % (i, sdl2.SDL_JoystickName(j),
                                                         sdl2.SDL_JoystickNumButtons(j)))
            except Exception:
                log(traceback.format_exc())

    open_inputs()

    held = None
    toast = False
    bridge = {}
    last_minute = -1
    last_anim = 0.0
    running = True
    axis = {0: 0, 1: 0}
    ev = sdl2.SDL_Event()

    # ---------------- Reproduccion: cambio de canal y menu de video ----------------
    VIDEO_MODES = ("normal", "estirar", "auto", "zoom")
    EMU_DIR = conf.get("EMU_DIR", "/mnt/SDCARD/Emu/MEDIA")
    try:
        open(os.path.join(APP_DIR, "ffplay.log"), "w").close()
    except Exception:
        pass

    def find_ffplay():
        cands = [conf.get("FFPLAY_BIN", ""), EMU_DIR + "/bin64/ffplay",
                 "/mnt/SDCARD/spruce/bin64/ffplay", EMU_DIR + "/bin/ffplay"]
        for c in cands:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    def playable(url):
        if url.lower().startswith("https://") and conf.get("HTTPS_BRIDGE", "1") == "1":
            try:
                if "b" not in bridge:
                    from proxy import Bridge
                    bridge["b"] = Bridge(log)
                    log("puente https activo en puerto %d" % bridge["b"].port)
                return bridge["b"].url_for(url)
            except Exception:
                log("puente https no disponible: " + traceback.format_exc())
        return url

    STATUS_RE = re.compile(rb"^\s*(\d+(?:\.\d+)?|nan)\s+(?:A-V|M-V|V-A|M-A|A:|V:|:)")
    DUR_RE = re.compile(rb"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

    def _reader(proc, info, logf):
        buf = b""
        try:
            while True:
                chunk = proc.stderr.read1(4096)
                if not chunk:
                    break
                parts = re.split(rb"[\r\n]", buf + chunk)
                buf = parts.pop()
                for p in parts:
                    if not p.strip():
                        continue
                    mt = STATUS_RE.match(p)
                    if mt:
                        if mt.group(1) != b"nan":
                            info["pos"] = float(mt.group(1))
                        info["last"] = p.strip()
                        continue
                    try:
                        tracks.parse_line(info, p.decode("utf-8", "replace"))
                    except Exception:
                        pass
                    d = DUR_RE.search(p)
                    if d and "dur" not in info:
                        info["dur"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
                    logf.write(p + b"\n")
                    logf.flush()
        except Exception:
            pass
        try:
            if info.get("last"):                      # ultimo estado de ffplay (cuadros perdidos, colas de audio/video)
                logf.write(b"   [estado final] " + info["last"][:160] + b"\n")
            logf.close()
        except Exception:
            pass

    def spawn(e, start_pos, live, mode, ast=None, sst=None):
        """Devuelve (proceso, info) o (None, {})."""
        ff = find_ffplay()
        logf = open(os.path.join(APP_DIR, "ffplay.log"), "ab")
        if not ff:
            logf.write(b"ERROR: no encontre ffplay\n")
            logf.close()
            return None, {}
        cmd = [ff, "-x", str(W), "-y", str(H), "-fs", "-loglevel", "32"]
        if mode in ("estirar", "auto"):
            cmd += ["-vf", "scale=%d:%d,setsar=1" % (W, H)]
        elif mode == "zoom":
            cmd += ["-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1" % (W, H, W, H)]
        if not live:
            cmd.append("-autoexit")
            if start_pos > 1:
                cmd += ["-ss", "%d" % start_pos]
        if ast is not None:
            cmd += ["-ast", str(ast)]
        if sst == "off":
            cmd.append("-sn")
        elif sst is not None:
            cmd += ["-sst", str(sst)]
        extra = conf.get("FFPLAY_EXTRA", "")
        if e.url in UA_TRY and "user_agent" not in extra:
            cmd += ["-user_agent", VLC_UA]
        cmd += extra.split()
        cmd += ["-i", playable(e.url)]
        env = dict(os.environ)
        env["PATH"] = EMU_DIR + "/bin64:" + env.get("PATH", "")
        env["LD_LIBRARY_PATH"] = EMU_DIR + "/lib64:/usr/miyoo/lib:/usr/lib:" + env.get("LD_LIBRARY_PATH", "")
        logf.write(("\n== Canal: %s | modo %s | desde %ds\n" % (e.name, mode, start_pos)).encode("utf-8", "replace"))
        logf.write(("   URL: %s\n" % e.url).encode("utf-8", "replace"))
        logf.flush()
        log("ffplay: " + " ".join(cmd[:12]))
        info = {}
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.PIPE, env=env,
                                    cwd=EMU_DIR if os.path.isdir(EMU_DIR) else None)
        except Exception:
            log(traceback.format_exc())
            return None, {}
        threading.Thread(target=_reader, args=(proc, info, logf), daemon=True).start()
        return proc, info

    def cur_pos(info, start_pos, t0):
        p = info.get("pos")
        if p is None:
            return start_pos + (time.time() - t0)
        return p if p >= start_pos - 2 else start_pos + p

    def fmt_t(s):
        s = max(0, int(s))
        return "%d:%02d:%02d" % (s // 3600, (s // 60) % 60, s % 60)

    SEEK_STEP = {"left": -10, "right": 10, "pgup": -60, "pgdn": 60, "l1": -60, "r1": 60, "l2": -300, "r2": 300}
    home_req = [False]       # el boton Menu pide volver al inicio desde cualquier pantalla

    def scrub(e, pos, delta, total):
        """Pantalla de adelantar/atrasar con barra. Devuelve la posicion elegida (seg)."""
        def clamp(x):
            x = max(0.0, x)
            if total:
                x = min(x, max(0.0, total - 5))
            return x
        target = clamp(pos + delta)
        last = time.time()
        dirty = True
        step_txt = "%+d s" % delta
        streak = [None, 0, 0.0]
        while True:
            if dirty:
                gfx.clear((12, 14, 28))
                name = e.name if len(e.name) <= 44 else e.name[:43] + "..."
                gfx.text(name, W // 2, 40, 20, (205, 210, 230), "c")
                gfx.text(fmt_t(target), W // 2, 120, 64, (255, 255, 255), "c", True)
                gfx.text(step_txt + " " + T("scrub_from", fmt_t(pos)), W // 2, 200, 16, (150, 155, 175), "c")
                bx, by, bw = 40, 270, W - 80
                gfx.rect(bx, by, bw, 12, (50, 54, 80), 6)
                if total:
                    fw = int(bw * min(1.0, target / total))
                    if fw > 0:
                        gfx.rect(bx, by, max(fw, 12), 12, (60, 150, 235), 6)
                    gfx.circle(bx + fw, by + 6, 11, (255, 255, 255))
                    gfx.text(T("scrub_total", fmt_t(total)), W - 40, 296, 16, (150, 155, 175), "r")
                else:
                    gfx.text(T("scrub_unknown"), W - 40, 296, 16, (150, 155, 175), "r")
                gfx.text(T("scrub_keys1"), W // 2, 380, 16, (150, 155, 175), "c")
                gfx.text(T("scrub_keys2"), W // 2, 406, 16, (150, 155, 175), "c")
                gfx.present()
                dirty = False
            a = poll_play_action()
            if a is None:
                if time.time() - last > 1.8:
                    return target
                sdl2.SDL_Delay(30)
                continue
            last = time.time()
            d = SEEK_STEP.get(a)
            if d is not None:
                now = time.time()
                streak[1] = streak[1] + 1 if (streak[0] == a and now - streak[2] < 0.4) else 1
                streak[0], streak[2] = a, now
                d *= 1 if streak[1] < 6 else 3 if streak[1] < 16 else 6
                target = clamp(target + d)
                step_txt = "%+d s" % d
                dirty = True
            elif a in ("ok", "menu", "pause"):
                return target
            elif a == "home":
                home_req[0] = True
                return pos
            elif a == "back":
                return pos

    def stop(proc):
        try:
            if proc.poll() is None:
                proc.terminate()
                for _ in range(40):
                    if proc.poll() is not None:
                        return
                    time.sleep(0.05)
                proc.kill()
                proc.wait()
        except Exception:
            pass

    REPEAT = ("up", "down", "left", "right", "pgup", "pgdn", "l1", "r1", "l2", "r2")
    phold = [None]      # [accion, fuente, proximo_instante, repeticiones]
    trig = {"l": False, "r": False}

    def reset_hold():
        phold[0] = None
        trig["l"] = trig["r"] = False

    def still_down(src):
        """Comprueba en el mando que el boton sigue pulsado (por si se perdio el evento de soltar)."""
        try:
            if src[0] == "b" and state["controllers"]:
                for c in opened:
                    if sdl2.SDL_GameControllerGetButton(c, src[1]):
                        return True
                return False
            if src[0] == "a" and state["controllers"]:
                for c in opened:
                    if sdl2.SDL_GameControllerGetAxis(c, src[1]) > 16000:
                        return True
                return False
        except Exception:
            pass
        return True

    def arm(a, src):
        if a in REPEAT:
            phold[0] = [a, src, time.time() + 0.4, 0]
        return a

    def release(src):
        if phold[0] and phold[0][1] == src:
            phold[0] = None

    def poll_play_action():
        """Un boton -> accion. Mantener pulsada una direccion/L1/R1/L2/R2 la repite (turbo)."""
        wd()
        while sdl2.SDL_PollEvent(ctypes.byref(ev)):
            t = ev.type
            if t == sdl2.SDL_KEYDOWN:
                if ev.key.repeat:
                    continue
                a = key_map.get(ev.key.keysym.sym)
                if a:
                    return arm(a, ("k", ev.key.keysym.sym))
            elif t == sdl2.SDL_KEYUP:
                release(("k", ev.key.keysym.sym))
            elif t == sdl2.SDL_CONTROLLERBUTTONDOWN:
                b = ev.cbutton.button
                log("mando boton %d (reproduciendo)" % b)
                if b == sdl2.SDL_CONTROLLER_BUTTON_START:
                    return "pause"
                if b == sdl2.SDL_CONTROLLER_BUTTON_BACK:
                    return "menu"
                a = ctrl_map.get(b)
                if a:
                    return arm(a, ("b", b))
            elif t == sdl2.SDL_CONTROLLERBUTTONUP:
                release(("b", ev.cbutton.button))
            elif t == sdl2.SDL_CONTROLLERAXISMOTION:
                ax, v = ev.caxis.axis, ev.caxis.value
                if ax in (sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT):
                    k = "l" if ax == sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT else "r"
                    down = v > 16000
                    if down and not trig[k]:
                        trig[k] = True
                        log("gatillo %s (eje %d) pulsado" % (k.upper() + "2", ax))
                        return arm(k + "2", ("a", ax))
                    if not down and v < 8000 and trig[k]:
                        trig[k] = False
                        release(("a", ax))
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYHATMOTION:
                v = ev.jhat.value
                a = ("left" if v & sdl2.SDL_HAT_LEFT else "right" if v & sdl2.SDL_HAT_RIGHT
                     else "up" if v & sdl2.SDL_HAT_UP else "down" if v & sdl2.SDL_HAT_DOWN else None)
                if a:
                    return arm(a, ("h",))
                release(("h",))
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYBUTTONDOWN:
                a = joy_map.get(ev.jbutton.button)
                log("joy boton %d (reproduciendo)" % ev.jbutton.button)
                if a:
                    return arm(a, ("j", ev.jbutton.button))
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYBUTTONUP:
                release(("j", ev.jbutton.button))
            elif t == sdl2.SDL_QUIT:
                return "back"
        h = phold[0]
        if h and time.time() >= h[2]:
            if not still_down(h[1]):
                phold[0] = None
                return None
            h[3] += 1
            h[2] = time.time() + (0.11 if h[3] < 12 else 0.07)
            return h[0]
        return None

    def choose(title, sub, items, cur, hint=None):
        """Lista vertical con seleccion. items=[(texto, detalle)]. Devuelve indice o None (B)."""
        sel = cur if 0 <= cur < len(items) else 0
        while True:
            gfx.clear((12, 14, 28))
            gfx.text(title, 32, 22, 32, (255, 255, 255), "l", True)
            if sub:
                gfx.text(sub, 32, 62, 15, (255, 205, 60), "l")
            top = max(0, min(sel - 2, len(items) - 5)) if len(items) > 5 else 0
            for i in range(top, min(len(items), top + 5)):
                y = 96 + (i - top) * 62
                if i == sel:
                    gfx.gradient(24, y, W - 48, 56, (120, 60, 200), (40, 140, 230), True)
                else:
                    gfx.rect(24, y, W - 48, 56, (28, 31, 52), 8)
                mark = "● " if i == cur else ""
                lab, det = items[i]
                if len(lab) > 40:
                    lab = lab[:39] + "..."
                gfx.text(mark + lab, 44, y + 7, 22, (255, 255, 255), "l", True)
                if det:
                    gfx.text(det if len(det) < 70 else det[:69] + "...", 44, y + 34, 14,
                             (205, 210, 230) if i == sel else (150, 155, 175), "l")
            gfx.text(hint or T("video_menu_hint"), 32, H - 40, 15, (150, 155, 175), "l")
            gfx.present()
            a = None
            while a is None:
                a = poll_play_action()
                if a is None:
                    sdl2.SDL_Delay(30)
            if a in ("up", "down"):
                sel = (sel + (1 if a == "down" else -1)) % len(items)
            elif a in ("ok", "menu", "pause"):
                return sel
            elif a == "home":
                home_req[0] = True
                return None
            elif a == "back":
                return None

    def play_menu(mode, info, sel, live):
        """Menu durante la reproduccion: Video / Audio / Subtitulos. Devuelve el modo de video.
        Las pistas elegidas se guardan en `sel` solo para este video."""
        streams = info.get("streams", [])
        ui_lang = get_lang()
        while True:
            aus, sus = tracks.audios(streams), tracks.subs(streams)
            items = [(T("menu_video"), T("video_" + mode)),
                     (T("menu_audio"), T("tracks_n", len(aus)) if aus else T("tracks_none")),
                     (T("menu_subs"), T("tracks_n", len(sus)) if sus else T("tracks_none"))]
            c = choose(T("menu_title"), T("video_session"), items, 0,
                       T("video_menu_hint"))
            if c is None or home_req[0]:
                return mode
            if c == 0:
                m = choose(T("video_title"), T("video_session"),
                           [(T("video_" + k), T("video_%s_d" % k)) for k in VIDEO_MODES],
                           VIDEO_MODES.index(mode) if mode in VIDEO_MODES else 0)
                if m is not None:
                    mode = VIDEO_MODES[m]
                    log("modo de video (esta reproduccion): %s" % mode)
                    return mode
            elif c == 1:
                if not aus:
                    continue
                cur_idx = sel["ast"] if sel["ast"] is not None else next(
                    (x["idx"] for x in aus if x["default"]), aus[0]["idx"])
                lst = [tracks.label(x, ui_lang) for x in aus]
                n = choose(T("menu_audio"), T("video_session"), lst,
                           [x["idx"] for x in aus].index(cur_idx) if cur_idx in [x["idx"] for x in aus] else 0)
                if n is not None:
                    sel["ast"] = aus[n]["idx"]
                    sel["auto_done"] = True
                    log("audio elegido: %s" % aus[n])
                    return mode
            else:
                if not sus:
                    continue
                items2 = [(T("subs_off"), "")] + [
                    (tracks.label(x, ui_lang)[0],
                     tracks.label(x, ui_lang)[1] + ("  " + T("subs_bitmap") if tracks.is_bitmap(x) else "  " + T("subs_text")))
                    for x in sus]
                curs = sel["sst"]
                cur_i = 0 if curs in (None, "off") else 1 + tracks.sub_ordinal(streams, curs)
                n = choose(T("menu_subs"), T("video_session"), items2, cur_i)
                if n is not None:
                    sel["sst"] = "off" if n == 0 else sus[n - 1]["idx"]
                    sel["auto_done"] = True
                    log("subtitulo elegido: %s" % sel["sst"])
                    return mode


    def urlsplit_host(u):
        from urllib.parse import urlsplit
        return urlsplit(u).hostname

    def net_args(url, follow=False, tag="", lazy=False):
        """Este ffmpeg no resuelve nombres de dominio: se resuelve aqui y se pasa la IP (+ encabezado Host).
        follow: antes se siguen las redirecciones (canales en vivo) para resolver el servidor final."""
        hdr = []
        t_red = t_dns = 0.0
        if follow and url.startswith("http") and not url.startswith("http://127.0.0.1"):
            t_ = time.time()
            try:
                import urllib.request, urllib.error, urllib.parse

                class NoRed(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *a, **k):
                        return None
                op = urllib.request.build_opener(NoRed)
                cu, hops = url, []
                for _ in range(6):
                    th_ = time.time()
                    rq = urllib.request.Request(cu, headers={"User-Agent": VLC_UA if url in UA_TRY else "Lavf/58"})
                    try:
                        op.open(rq, timeout=8).close()
                        hops.append("%.2fs final" % (time.time() - th_))
                        break
                    except urllib.error.HTTPError as he:
                        loc = he.headers.get("Location")
                        hops.append("%.2fs HTTP %d" % (time.time() - th_, he.code))
                        if he.code in (301, 302, 303, 307, 308) and loc:
                            cu = urllib.parse.urljoin(cu, loc)
                            if lazy:               # un solo salto: el destino se abre una sola vez (ffmpeg), sin confirmar antes
                                break
                        else:
                            break
                    if time.time() - t_ > 12:
                        break
                log("redireccion saltos: %s%s" % (" > ".join(hops), tag))
                if cu != url:
                    log("redireccion: cambio de servidor (%s)" % ("mismo host" if urlsplit_host(cu) == urlsplit_host(url) else "otro host"))
                    url = cu
            except Exception as ex:
                log("redireccion: %s tras %.2fs" % (type(ex).__name__, time.time() - t_))
            t_red = time.time() - t_
        t_ = time.time()
        try:
            import socket
            from urllib.parse import urlsplit
            sp = urlsplit(url)
            if sp.scheme == "http" and sp.hostname and not re.match(r"^[\d.]+$", sp.hostname):
                ip = socket.gethostbyname(sp.hostname)
                hostport = sp.hostname + (":%d" % sp.port if sp.port else "")
                url = url.replace(sp.hostname, ip, 1)
                hdr = ["-headers", "Host: %s\r\n" % hostport]
        except Exception as ex:
            log("no pude resolver el host (%s)" % ex)
        t_dns = time.time() - t_
        if url.startswith("http"):
            log("enlace preparado: redireccion %.2fs, dns %.2fs" % (t_red, t_dns))
        return url, hdr

    def find_ffmpeg():
        import shutil
        fp = find_ffplay()
        cands = [conf.get("FFMPEG_BIN", ""), (os.path.dirname(fp) + "/ffmpeg") if fp else "",
                 EMU_DIR + "/bin64/ffmpeg", "/mnt/SDCARD/spruce/bin64/ffmpeg", EMU_DIR + "/bin/ffmpeg",
                 shutil.which("ffmpeg") or ""]
        for c in cands:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    def grab_frame(e, pos):
        """Un cuadro RGB 640x480 de la pelicula en `pos` (para el fondo de la pausa). None si falla."""
        ff = find_ffmpeg()
        if not ff:
            log("pausa: no hay ffmpeg (solo ffplay); fondo negro")
            return None
        out = {}
        def run():
            try:
                url, hdr = net_args(playable(e.url))
                cmd = [ff, "-loglevel", "error", "-ss", "%d" % max(0, pos)] + hdr + ["-i", url,
                       "-frames:v", "1", "-vf",
                       "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % (W, H, W, H),
                       "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
                if e.url in UA_TRY:
                    cmd[1:1] = ["-user_agent", VLC_UA]
                env = dict(os.environ)
                env["LD_LIBRARY_PATH"] = EMU_DIR + "/lib64:/usr/miyoo/lib:/usr/lib:" + env.get("LD_LIBRARY_PATH", "")
                p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env)
                out["p"] = p
                out["d"], err = p.communicate()
                if err:
                    log("pausa ffmpeg: " + err.decode("utf-8", "replace").strip()[-300:])
            except Exception:
                log(traceback.format_exc())
        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(15)
        if th.is_alive():
            try:
                out["p"].kill()
            except Exception:
                pass
            th.join(1)
        d = out.get("d")
        if d and len(d) >= W * H * 3:
            return d[:W * H * 3]
        log("pausa: no pude obtener la imagen (fondo negro); ffmpeg=%s" % ff)
        return None

    def pause_screen(e, pos, info, mode, sel, frame, out=None):
        try:
            return _pause_screen(e, pos, info, mode, sel, frame, out if out is not None else {})
        finally:
            ui.end_pause()

    def series_eps(e):
        """Episodios de la misma serie que `e`, en orden de temporada y episodio."""
        base = series_parts(e.name)[0]
        lst = [x for x in ui.view if series_parts(x.name)[0] == base]
        if e not in lst:
            lst.append(e)
        lst.sort(key=lambda x: (series_parts(x.name)[1] or 0, series_parts(x.name)[2] or 0, x.nname))
        return lst

    def confirm_exit(pl, cur):
        """Pregunta "¿Quieres salir?" (Si / No, empieza en No). X otra vez = salir. True = salir."""
        pl.pause()
        sel_ = 1
        try:
            while True:
                if pl.last is not None:
                    gfx.rgb_frame(pl.last, W, H, 0, 0)
                else:
                    gfx.clear((0, 0, 0))
                gfx.dim(0, 0, W, H, 150)
                px, py, pw, ph = 140, 150, 360, 180
                gfx.rect(px, py, pw, ph, (28, 31, 52), 14)
                gfx.rect(px, py, pw, 4, (120, 100, 220), 2)
                gfx.text(T("exit_q"), W // 2, py + 30, 28, (255, 255, 255), "c", True)
                for i, k in enumerate(("exit_yes", "exit_no")):
                    bx = px + 30 + i * 160
                    gfx.rect(bx, py + 100, 140, 50, (120, 100, 220) if i == sel_ else (70, 74, 110), 10)
                    gfx.text(T(k), bx + 70, py + 112, 24, (255, 255, 255), "c", True)
                gfx.present()
                a = None
                while a is None:
                    a = poll_play_action()
                    if a is None:
                        sdl2.SDL_Delay(30)
                if a in ("left", "right"):
                    sel_ = 0 if a == "left" else 1
                elif a == "ok":
                    if sel_ == 0:
                        return True
                    break
                elif a == "back":
                    return True
                elif a == "home":
                    home_req[0] = True
                    return True
        finally:
            pass
        pl.resume()
        reset_hold()
        return False

    def _pause_screen(e, pos, info, mode, sel, frame, out):
        """Pantalla de pausa de peliculas y series. Devuelve (posicion para reanudar, modo de video).
        `out` recibe "restart" (Reiniciar) o "ep" (otro episodio elegido)."""
        series = (e.cat == "SERIES")
        opts = ["eps", "aspect", "audio", "subs", "next"] if series else ["aspect", "audio", "subs"]
        total = info.get("dur")
        streams = info.get("streams", [])
        ui_lang = get_lang()
        focus, last_opt = 0, 1
        fid = int(time.time())
        playing = False
        end_t = 0.0

        def draw():
            ui.draw_pause(e.name, pos, total, focus, frame, fid, playing, False, False, False, series, True)
            gfx.present()

        def resume():
            nonlocal playing, end_t
            playing = True
            end_t = time.time() + 0.7

        def pick_option():
            nonlocal mode, fid
            aus, sus = tracks.audios(streams), tracks.subs(streams)
            kind = opts[focus - 1]
            if kind == "eps":
                lst = series_eps(e)
                ci = lst.index(e) if e in lst else 0
                n = choose(T("pause_eps"), series_parts(e.name)[0], [(ui._ep_label(x), "") for x in lst], ci)
                if n is not None and n != ci:
                    out["ep"] = lst[n]
                    return True
            elif kind == "next":
                lst = series_eps(e)
                ci = lst.index(e) if e in lst else 0
                if ci + 1 < len(lst):
                    out["ep"] = lst[ci + 1]
                    return True
            elif kind == "aspect":
                m = choose(T("video_title"), T("video_session"),
                           [(T("video_" + k), T("video_%s_d" % k)) for k in VIDEO_MODES],
                           VIDEO_MODES.index(mode) if mode in VIDEO_MODES else 0)
                if m is not None:
                    mode = VIDEO_MODES[m]
                    if gfx.mode_hook:
                        gfx.mode_hook(mode)
                    fid += 1                      # redibuja el cuadro de fondo con el modo nuevo
                    return True
            elif kind == "audio" and aus:
                ids = [x["idx"] for x in aus]
                cur_idx = sel["ast"] if sel["ast"] is not None else next(
                    (x["idx"] for x in aus if x["default"]), ids[0])
                n = choose(T("menu_audio"), T("video_session"), [tracks.label(x, ui_lang) for x in aus],
                           ids.index(cur_idx) if cur_idx in ids else 0)
                if n is not None:
                    sel["ast"] = aus[n]["idx"]
                    sel["auto_done"] = True
                    return True
            elif kind == "subs" and sus:
                items2 = [(T("subs_off"), "")] + [
                    (tracks.label(x, ui_lang)[0],
                     tracks.label(x, ui_lang)[1] + ("  " + T("subs_bitmap") if tracks.is_bitmap(x) else "  " + T("subs_text")))
                    for x in sus]
                curs = sel["sst"]
                cur_i = 0 if curs in (None, "off") else 1 + tracks.sub_ordinal(streams, curs)
                n = choose(T("menu_subs"), T("video_session"), items2, cur_i)
                if n is not None:
                    sel["sst"] = "off" if n == 0 else sus[n - 1]["idx"]
                    sel["auto_done"] = True
                    return True
            return False

        while True:
            draw()
            if playing:
                if time.time() >= end_t:
                    return max(0.0, pos), mode
                sdl2.SDL_Delay(30)
                continue
            a = poll_play_action()
            if a is None:
                sdl2.SDL_Delay(30)
                continue
            if a == "home":
                home_req[0] = True
                return max(0.0, pos), mode
            if a in ("pause", "back", "menu"):
                resume()
            elif a == "up":
                if focus > 0:
                    last_opt, focus = focus, 0
                elif focus == 0:
                    focus = -1
            elif a == "down":
                if focus == -1:
                    focus = 0
                elif focus == 0:
                    focus = last_opt
            elif a in ("left", "right") and focus == -1:
                pass
            elif a in ("left", "right"):
                d = -1 if a == "left" else 1
                if focus == 0:
                    pos = pos + 10 * d
                    if total:
                        pos = min(pos, max(0, total - 5))
                    pos = max(0.0, pos)
                else:
                    focus = min(len(opts), max(1, focus + d))
                    last_opt = focus
            elif a in SEEK_STEP and focus == 0:
                pos = max(0.0, pos + SEEK_STEP[a])
                if total:
                    pos = min(pos, max(0, total - 5))
            elif a == "ok":
                if focus == 0:
                    resume()
                elif focus == -1:
                    out["restart"] = True
                    pos = 0.0
                    resume()
                else:
                    gfx_ok = pick_option()
                    if home_req[0]:
                        return max(0.0, pos), mode
                    if gfx_ok:
                        resume()

    def draw_subs(pl):
        lines = pl.sub_lines()
        if not lines:
            return
        size = 22
        wmax = max(gfx.text_w(x, size, True) for x in lines)
        if wmax > W - 40:
            size = max(14, int(size * (W - 40) / float(wmax)))
        y = H - 28 - size - (len(lines) - 1) * (size + 4)
        for ln in lines:
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                gfx.text(ln, W // 2 + dx, y + dy, size, (0, 0, 0), "c", True)
            gfx.text(ln, W // 2, y, size, (255, 255, 255), "c", True)
            y += size + 4

    def pause_screen_live(e, mode, frame):
        """Pausa de TV en vivo: boton de play/pausa, Pantalla y Favorito. Devuelve el modo de video."""
        focus, last_opt = 0, 1
        fid = int(time.time() * 1000)
        playing = False
        end_t = 0.0
        try:
            while True:
                ui.draw_pause(e.name, 0, 0, focus, frame, fid, playing, False, True, ui._is_fav(e))
                gfx.present()
                if playing:
                    if time.time() >= end_t:
                        return mode
                    sdl2.SDL_Delay(30)
                    continue
                a = poll_play_action()
                if a is None:
                    sdl2.SDL_Delay(30)
                    continue
                if a == "home":
                    home_req[0] = True
                    return mode
                if a in ("pause", "back", "menu"):
                    playing, end_t = True, time.time() + 0.7
                elif a == "up":
                    if focus:
                        last_opt, focus = focus, 0
                elif a == "down":
                    if focus == 0:
                        focus = last_opt
                elif a in ("left", "right") and focus:
                    focus = min(2, max(1, focus + (-1 if a == "left" else 1)))
                    last_opt = focus
                elif a == "ok":
                    if focus == 0:
                        playing, end_t = True, time.time() + 0.7
                    elif focus == 1:
                        m = choose(T("video_title"), T("video_session"),
                                   [(T("video_" + k), T("video_%s_d" % k)) for k in VIDEO_MODES],
                                   VIDEO_MODES.index(mode) if mode in VIDEO_MODES else 0)
                        if home_req[0]:
                            return mode
                        if m is not None:
                            mode = VIDEO_MODES[m]
                            if gfx.mode_hook:
                                gfx.mode_hook(mode)
                            fid += 1
                            playing, end_t = True, time.time() + 0.7
                    elif focus == 2:
                        ui._toggle_fav_key(e.fkey)
                        ok_ = save_favs(favs_path, ui.favs)
                        log("favorito (pausa en vivo): %s" % ("ok" if ok_ else "ERROR al escribir"))
        finally:
            ui.end_pause()

    def apply_mode(pl_, m_):
        """Aplica el modo de pantalla al reproductor sin reiniciarlo."""
        try:
            pl_.set_mode(m_)
            gfx.vcrop, gfx.vdst = pl_.geom()
            log("modo de pantalla: %s | aspecto %s | origen %s | destino %s" % (
                m_, ("%.3f" % pl_.dar) if pl_.dar else "?", gfx.vcrop, gfx.vdst))
        except Exception:
            log("modo de pantalla: error\n" + traceback.format_exc())

    def url_kind(u):
        """Tipo de enlace para el log (sin la direccion): hls, ts, mp4, etc."""
        p = u.split("?", 1)[0].lower()
        for k in ("m3u8", "ts", "mp4", "mkv", "avi"):
            if p.endswith("." + k):
                return k
        return "otro"

    redir_cache = {}

    def prepare_link(cur, live, lazy=False):
        """Resuelve (redireccion + DNS) en un hilo. Mientras tanto muestra "cargando" y atiende Arriba/Abajo
        (cambia de canal sin esperar), B y Home. Devuelve (url, hdr), "switch" o None (salir)."""
        import threading
        raw = playable(cur.url)
        hit = redir_cache.get(raw)
        if hit and time.time() - hit[0] < 90:
            log("enlace preparado: en memoria")
            return hit[1], hit[2]
        box = {}
        def work():
            try:
                box["r"] = net_args(raw, live, " (al elegir)", lazy)
            except Exception as ex:
                box["e"] = ex
        th = threading.Thread(target=work, daemon=True)
        th.start()
        t_ = time.time()
        while th.is_alive():
            wd()
            gfx.clear((0, 0, 0))
            if live:
                gfx.text(ui.fit(cur.name, 24, W - 48, True), 24, 20, 24, (255, 255, 255), "l", True)
            gfx.text(T("pv_loading"), W // 2, H - 32, 18, (255, 255, 255), "c", True)
            gfx.present()
            a = poll_play_action()
            if a == "back" or a == "home":
                if a == "home":
                    home_req[0] = True
                return None
            if a in ("up", "down") and live:
                n_ = len(ui.view)
                if n_ > 1:
                    ui.idx = (ui.idx + (1 if a == "down" else -1)) % n_
                    ui._scroll()
                    cur2 = ui.view[ui.idx]
                    log("cambio de canal -> %s (antes de conectar)" % cur2.name)
                    return ("switch", cur2, 1 if a == "down" else -1)
            sdl2.SDL_Delay(15)
        if "e" in box:
            raise box["e"]
        url, hdr = box["r"]
        redir_cache[raw] = (time.time(), url, hdr)
        return url, hdr

    def prefetch_neighbors(cur, slow):
        """Con el canal ya sonando, resuelve en segundo plano la redireccion del siguiente y del anterior."""
        import threading
        try:
            i = ui.view.index(cur)
            n = len(ui.view)
            cand = [ui.view[(i + 1) % n], ui.view[(i - 1) % n]] if n > 2 else []
        except ValueError:
            return
        raws = [playable(c.url) for c in cand]
        raws = [r_ for r_ in raws if not r_.startswith("http://127.0.0.1")]   # via puente: no hay redireccion que adelantar
        if not raws:
            return
        def work():
            time.sleep(2.0)
            for raw in raws:
                hit = redir_cache.get(raw)
                if hit and time.time() - hit[0] < 90:
                    continue
                try:
                    url, hdr = net_args(raw, True, " (adelantado)", raw not in slow)
                    redir_cache[raw] = (time.time(), url, hdr)
                except Exception:
                    pass
        threading.Thread(target=work, daemon=True).start()

    def reopen_wait():
        """Pausa de 2 s antes de reabrir un video (B/Home la cancelan)."""
        for _ in range(100):
            wd()
            a_ = poll_play_action()
            if a_ in ("back", "home"):
                if a_ == "home":
                    home_req[0] = True
                raise StopIteration
            sdl2.SDL_Delay(20)

    def internal_movie(cur):
        """Reproductor interno de peliculas (prueba). Devuelve "" al terminar bien o None si no pudo
        arrancar (entonces se usa ffplay como siempre). La pantalla queda abierta (gfx)."""
        from vplayer import VPlayer
        ff = find_ffmpeg()
        mode = settings.get("video", "normal")
        sel = {"ast": None, "sst": None, "auto_done": False}
        pos = 0.0
        meta = {}
        prev = None
        retries = 0
        started_ok = False
        live = (cur.cat == "TV")
        switch_dir, fails, last_good, notice, nosig = 0, 0, None, "", False
        open_retries = 0
        slow_urls = set()        # canales donde el modo rapido fallo: solo esos usan el modo completo
        pf_done = [False]
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = EMU_DIR + "/lib64:/usr/miyoo/lib:/usr/lib:" + env.get("LD_LIBRARY_PATH", "")
        ua = VLC_UA if cur.url in UA_TRY else None
        pl = None
        result = ""
        try:
            while True:
                got = prepare_link(cur, live, live and playable(cur.url) not in slow_urls)         # redireccion en segundo plano: se puede seguir cambiando de canal
                if isinstance(got, tuple) and got[0] == "switch":
                    if not switch_dir:
                        last_good = cur
                    switch_dir, fails = got[2], 0
                    cur = got[1]
                    prev, started_ok, retries, pos = None, False, 0, 0.0
                    continue
                if got is None:
                    raise StopIteration
                url, hdr = got
                sst_use = None
                if sel["sst"] not in (None, "off"):
                    sm = next((x for x in tracks.subs(meta.get("streams")) if x["idx"] == sel["sst"]), None)
                    if sm is not None and not tracks.is_bitmap(sm):
                        sst_use = sel["sst"]
                    else:
                        log("video interno: subtitulo grafico o desconocido, no se puede mostrar")
                ssc_use = next((x["codec"] for x in tracks.subs(meta.get("streams")) if x["idx"] == sst_use), None) if sst_use is not None else None
                if sst_use is not None:
                    log("video interno: subtitulo pista %s codec %s" % (sst_use, ssc_use))
                short_ = live and playable(cur.url) not in slow_urls
                pl = VPlayer(ff, url, pos, W, H, mode, sel["ast"], ua, env, log, hdr, None, sst_use, live, ssc_use, short_)
                pl.dar = meta.get("dar")             # mismo video que antes: se conserva el aspecto hasta leerlo otra vez
                gfx.vcrop, gfx.vdst = pl.geom()
                gfx.mode_hook = lambda m_: apply_mode(pl, m_)
                log("video interno: inicio en %.1fs modo %s audio %s tipo %s%s" % (pos, mode, sel["ast"], url_kind(url), " analisis corto" if short_ else ""))
                start_logged = False
                pf_done[0] = False
                t0 = time.time()
                last_stat = time.time()
                again = False
                while not again:
                    wd()
                    fr = pl.next_frame()
                    if fr is not None:
                        prev = fr
                        gfx.vcrop, gfx.vdst = pl.geom()
                        gfx.rgb_frame(fr, W, H, 0, 0)
                        if not start_logged:
                            start_logged = True
                            log("video interno: %s" % pl.start_report())
                        draw_subs(pl)
                        gfx.present()
                    elif not pl.ready():
                        gfx.clear((0, 0, 0))
                        if prev:
                            gfx.rgb_frame(prev, W, H, 0, 0)
                            gfx.rect(0, H - 40, W, 40, (0, 0, 0))
                        if live:
                            gfx.text(ui.fit(cur.name, 24, W - 48, True), 24, 20, 24, (255, 255, 255), "l", True)
                        gfx.text(T("pv_loading"), W // 2, H - 32, 18, (255, 255, 255), "c", True)
                        gfx.present()
                    if pl.ready():
                        open_retries = 0
                        if live and not pf_done[0]:
                            pf_done[0] = True
                            prefetch_neighbors(cur, slow_urls)
                        started_ok = True
                        if live and switch_dir:
                            switch_dir, fails = 0, 0
                    if not started_ok and (time.time() - t0 > (15 if (live and switch_dir) else (25 if live else 45)) or pl.failed()):
                        log("video interno: no arranco (%s)" % pl.stats())
                        redir_cache.pop(playable(cur.url), None)
                        if short_:                            # solo en vivo: peliculas y series ya usan el modo completo
                            slow_urls.add(playable(cur.url))          # el modo rapido no basto: reintenta con analisis y redireccion completos
                            log("video interno: reintento con analisis y redireccion completos")
                            again = True
                            break
                        if pl.net_fail:                    # sin internet: no saltar de canal ni abrir ffplay
                            notice = T("no_net")
                            result = ""
                            raise StopIteration
                        if live and switch_dir:
                            nosig = True
                            again = True
                            break
                        if not live and open_retries < 2:
                            open_retries += 1             # el proveedor puede tardar en liberar la conexion anterior
                            log("video interno: no se pudo abrir, reintento %d en 2 s" % open_retries)
                            reopen_wait()
                            again = True
                            break
                        return None
                    if time.time() - last_stat > 5:
                        last_stat = time.time()
                        log("video interno: %s pos %.0f" % (pl.stats(), pl.position()))
                    if pl.dar:
                        meta["dar"] = pl.dar
                    if pl.info.get("dur"):
                        meta["dur"] = pl.info["dur"]
                    if pl.info.get("streams"):
                        meta["streams"] = pl.info["streams"]
                    cur_p = pl.position()
                    if live and (pl.finished() or (started_ok and pl.failed())):
                        if retries < 3:
                            retries += 1
                            log("video interno: corte del canal, reconecto (%d)" % retries)
                            pos = 0.0
                            again = True
                            break
                        raise StopIteration
                    if not live and pl.failed() and pl.nframes == 0 and open_retries < 3 and not pl.net_fail:
                        open_retries += 1             # al reabrir, el proveedor puede tardar en liberar la conexion anterior
                        log("video interno: no se pudo abrir, reintento %d en 2 s" % open_retries)
                        redir_cache.pop(playable(cur.url), None)
                        reopen_wait()
                        again = True
                        break
                    if pl.finished() or (started_ok and pl.failed()):
                        dur = pl.info.get("dur")
                        if dur and cur_p < dur - 20 and retries < 3:
                            retries += 1
                            pos = cur_p
                            log("video interno: corte en %.0fs, reintento %d" % (pos, retries))
                            again = True
                            break
                        result = ""
                        raise StopIteration
                    st_ = pl.info.get("streams")
                    if st_ and not sel["auto_done"] and not live:
                        sel["auto_done"] = True
                        kd_ = "series" if cur.cat == "SERIES" else "movies"
                        a_pick = tracks.pick_audio(st_, settings.get("aud_" + kd_))
                        aus_ = tracks.audios(st_)
                        dflt = next((x["idx"] for x in aus_ if x["default"]), aus_[0]["idx"] if aus_ else None)
                        s_pick = tracks.pick_sub(st_, settings.get("sub_" + kd_))
                        need = False
                        if a_pick is not None and a_pick != dflt:
                            sel["ast"] = a_pick
                            need = True
                        if s_pick is not None:
                            sel["sst"] = s_pick
                            if s_pick != "off":
                                need = True
                        sub_only = False
                        if need and (a_pick is None or a_pick == dflt) and s_pick not in (None, "off"):
                            sm_ = next((x for x in tracks.subs(st_) if x["idx"] == s_pick), None)
                            if sm_ is not None and sm_["codec"] == "mov_text":
                                sub_only = True
                        if need and sub_only:                 # solo subtitulos mov_text: proceso aparte, sin reiniciar el video
                            log("video interno: subtitulo pista %s codec mov_text (sin reiniciar)" % s_pick)
                            pl.start_subs(s_pick)
                        elif need:
                            pos = cur_p
                            log("video interno: pistas audio %s subtitulo %s (reiniciar)" % (a_pick, s_pick))
                            again = True
                            break
                    a = poll_play_action()
                    if a is None:
                        sdl2.SDL_Delay(4)
                        continue
                    if a == "back":
                        if confirm_exit(pl, cur):
                            raise StopIteration
                        continue
                    if a == "home":
                        home_req[0] = True
                        raise StopIteration
                    if pl.last is None and not (a in ("up", "down") and live):
                        continue                       # imagen aun en negro: Start/A/Select/saltos no hacen nada
                    if a in ("up", "down") and live:
                        n_ = len(ui.view)
                        if n_ > 1:
                            if not switch_dir:
                                last_good = cur
                            switch_dir = 1 if a == "down" else -1
                            fails = 0
                            ui.idx = (ui.idx + switch_dir) % n_
                            ui._scroll()
                            cur = ui.view[ui.idx]
                            log("cambio de canal -> %s" % cur.name)
                            prev, started_ok, retries, pos = None, False, 0, 0.0
                            again = True
                    elif a == "pause" and live:
                        pl.pause()
                        m0 = mode
                        mode = pause_screen_live(cur, mode, pl.last)
                        if home_req[0]:
                            raise StopIteration
                        apply_mode(pl, mode)               # el modo de pantalla cambia al instante, sin reconectar
                        if pl.failed() or pl.finished():
                            pos = 0.0
                            again = True                  # se cayo la conexion: reconecta en vivo
                        else:
                            pl.resume()
                    elif a == "pause":
                        pl.pause()
                        p0 = pl.position()
                        m0, a0, s0 = mode, sel["ast"], sel["sst"]
                        pout = {}
                        newp, mode = pause_screen(cur, p0, dict(meta), mode, sel, pl.last, pout)
                        if home_req[0]:
                            raise StopIteration
                        apply_mode(pl, mode)               # el modo de pantalla cambia al instante, sin reiniciar
                        if pout.get("ep") is not None:                 # otro episodio (lista o Siguiente)
                            cur = pout["ep"]
                            try:
                                ui.idx = ui.view.index(cur)
                                ui._scroll()
                            except ValueError:
                                pass
                            log("serie: cambio de episodio -> %s" % cur.name)
                            prev, started_ok, retries, pos = None, False, 0, 0.0
                            meta = {}
                            sel = {"ast": None, "sst": None, "auto_done": False}
                            again = True
                        elif pout.get("restart") or abs(newp - p0) > 0.5 or sel["ast"] != a0 or sel["sst"] != s0:
                            pos = newp
                            again = True
                        else:
                            pl.resume()
                    elif a in SEEK_STEP and not live:
                        # la imagen se queda congelada con la barra encima; al dejar de pulsar (1.2 s) salta
                        pl.pause()
                        p0 = pl.position()
                        tgt = p0 + SEEK_STEP[a]
                        total = meta.get("dur")
                        last_in = time.time()
                        fid = int(time.time() * 1000)
                        cancel = False
                        while True:
                            tgt = max(0.0, min(tgt, (total - 5) if total else tgt))
                            ui.draw_pause(cur.name, tgt, total, 0, pl.last, fid, True, True, False, False,
                                          cur.cat == "SERIES", True)
                            gfx.present()
                            a2 = poll_play_action()
                            if a2 is None:
                                if time.time() - last_in > 1.2:
                                    break
                                sdl2.SDL_Delay(30)
                                continue
                            if a2 in SEEK_STEP:
                                tgt += SEEK_STEP[a2]
                                last_in = time.time()
                            elif a2 in ("ok", "pause"):
                                break
                            elif a2 == "back":
                                cancel = True
                                break
                            elif a2 == "home":
                                home_req[0] = True
                                raise StopIteration
                        ui.end_pause()
                        if cancel or abs(tgt - p0) < 0.5:
                            pl.resume()
                        else:
                            pos = tgt
                            again = True
                    elif a in ("ok", "menu"):
                        pl.pause()
                        a0, s0 = sel["ast"], sel["sst"]
                        mode = play_menu(mode, dict(meta), sel, live)
                        if home_req[0]:
                            raise StopIteration
                        apply_mode(pl, mode)               # el modo de pantalla cambia al instante, sin reiniciar
                        if sel["ast"] != a0 or sel["sst"] != s0:
                            pos = 0.0 if live else pl.position()
                            again = True
                        else:
                            pl.resume()
                log("video interno: %s" % pl.stats())
                pl.close()
                pl = None
                if nosig:                                  # el canal al que salte no transmite: probar el siguiente
                    nosig = False
                    n_ = len(ui.view)
                    log("sin transmision: %s" % cur.name)
                    fails += 1
                    prev, started_ok, retries, pos = None, False, 0, 0.0
                    if fails < n_:
                        ui.idx = (ui.idx + switch_dir) % n_
                        ui._scroll()
                        cur = ui.view[ui.idx]
                    else:
                        switch_dir = 0
                        if last_good is not None:
                            cur = last_good
                            try:
                                ui.idx = ui.view.index(last_good)
                                ui._scroll()
                            except ValueError:
                                pass
                            notice = T("no_other")
                        else:
                            raise StopIteration
        except StopIteration:
            pass
        except Exception:
            log("video interno: error\n" + traceback.format_exc())
            if not started_ok:
                result = None
        if pl is not None:
            log("video interno: fin. %s" % pl.stats())
            pl.close()
        ui.end_pause()                       # devuelve al Home el icono que estaba elegido
        return result if result is None else (result or notice)

    GUARD = float(conf.get("PLAY_GUARD", "0.8"))
    seen_status = [False]

    def play_loop(entry):
        """Reproduce `entry`. Arriba/Abajo cambia de canal, A/Start/Select abre el menu
        de video, B vuelve. Devuelve un aviso (texto) si fallo, o ''."""
        cur = entry
        start_pos = 0.0
        notice = ""
        mode = settings.get("video", "normal")   # por defecto (Ajustes); el menu de video lo cambia solo aqui
        switch_dir = 0      # +1/-1 mientras se busca el proximo canal con senal
        fails = 0
        last_good = None
        sel = {"ast": None, "sst": None, "auto_done": False}
        home_req[0] = False
        reset_hold()
        if (((cur.cat == "PELIS" and conf.get("PLAYER_INTERNO", "1") == "1")
             or (cur.cat == "TV" and conf.get("PLAYER_INTERNO_TV", "1") == "1")
             or (cur.cat == "SERIES" and conf.get("PLAYER_INTERNO_SERIES", "1") == "1")) and find_ffmpeg()
                ):                                  # listas https tambien usan el reproductor interno (via el puente local)
            try:
                r = internal_movie(cur)
            finally:
                gfx.vcrop = gfx.vdst = None
                gfx.mode_hook = None
            if r is not None:
                # al salir se reinicia la pantalla y los mandos igual que despues de ffplay
                ui.end_pause()
                gfx.close()
                time.sleep(0.4)                  # deja que la pantalla se libere antes de volver a abrirla
                gfx.open()
                open_inputs()
                reset_hold()
                log("reproductor interno: pantalla reabierta")
                return r
            log("reproductor interno no disponible: uso ffplay")
        gfx.close()
        sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
        open_inputs()
        while True:
            live = (cur.cat == "TV")
            t0 = time.time()
            proc, info = spawn(cur, start_pos, live, mode, sel["ast"], sel["sst"])
            nxt = None
            want = ""
            seek_delta = 0
            if proc is not None:
                while proc.poll() is None:
                    if "pos" in info:
                        seen_status[0] = True
                        if switch_dir:
                            switch_dir = 0      # este canal si transmite: listo
                    elif (switch_dir and live and seen_status[0] and time.time() - t0 > 15):
                        log("sin senal (15 s sin imagen): %s" % cur.name)
                        want = "skip"
                        break
                    if (not live and "pos" in info and not sel["auto_done"] and info.get("streams")
                            and time.time() - t0 > 1.0):
                        sel["auto_done"] = True
                        st_ = info["streams"]
                        aus_ = tracks.audios(st_)
                        kind_ = "series" if cur.cat == "SERIES" else "movies"
                        a_pick = tracks.pick_audio(st_, settings.get("aud_" + kind_))
                        s_pick = tracks.pick_sub(st_, settings.get("sub_" + kind_))
                        dflt = next((x["idx"] for x in aus_ if x["default"]), aus_[0]["idx"] if aus_ else None)
                        need = False
                        if a_pick is not None and a_pick != dflt:
                            sel["ast"] = a_pick
                            need = True
                        if s_pick is not None:
                            sel["sst"] = s_pick
                            if s_pick != "off":
                                need = True
                        log("pistas: audio %s, subtitulo %s (reiniciar=%s)" % (a_pick, s_pick, need))
                        if need:
                            want = "retune"
                            break
                    a = poll_play_action()
                    if a is None:
                        sdl2.SDL_Delay(40)
                        continue
                    if time.time() - t0 < GUARD:
                        continue
                    if a in ("up", "down"):
                        n = len(ui.view)
                        if n > 1:
                            if not switch_dir:
                                last_good = cur
                            switch_dir = 1 if a == "down" else -1
                            fails = 0
                            ui.idx = (ui.idx + switch_dir) % n
                            ui._scroll()
                            nxt = ui.view[ui.idx]
                            log("cambio de canal -> %s" % nxt.name)
                            break
                    elif a in SEEK_STEP and not live:
                        want = "seek"
                        seek_delta = SEEK_STEP[a]
                        break
                    elif a in ("back", "home"):
                        if a == "home":
                            home_req[0] = True
                        want = "back"
                        break
                    elif a in ("ok", "menu", "pause"):
                        want = "pause" if (a == "pause" and not live and cur.cat == "PELIS") else "menu"
                        break
                dur = time.time() - t0
                died = proc.poll() is not None
                pos_now = cur_pos(info, start_pos, t0)
                frame = None
                if want == "pause" and not died:
                    try:
                        os.kill(proc.pid, signal.SIGSTOP)     # imagen congelada en pantalla
                    except Exception:
                        pass
                    frame = grab_frame(cur, pos_now)
                stop(proc)
            else:
                dur, died, pos_now, info = 0.0, True, start_pos, {}
            if nxt is not None:
                cur, start_pos = nxt, 0.0
                sel = {"ast": None, "sst": None, "auto_done": False}
                continue
            if want == "retune":
                start_pos = pos_now
                continue
            if want == "pause":
                gfx.open()
                open_inputs()
                start_pos, mode = pause_screen(cur, pos_now, info, mode, sel, frame)
                ui.end_pause()
                log("pausa -> reanudar en %.0fs" % start_pos)
                gfx.close()
                sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
                open_inputs()
                if home_req[0]:
                    break
                continue
            if want in ("menu", "seek"):
                if not live:
                    start_pos = pos_now
                gfx.open()
                open_inputs()
                if want == "seek":
                    start_pos = scrub(cur, pos_now, seek_delta, info.get("dur"))
                    log("salto a %.0fs" % start_pos)
                else:
                    mode = play_menu(mode, info, sel, live)
                gfx.close()
                sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
                open_inputs()
                if home_req[0]:
                    break
                continue
            n = len(ui.view)
            if switch_dir and want in ("", "skip") and (want == "skip" or (died and dur < 8)) and start_pos == 0:
                # El canal al que salte no transmite: buscar el siguiente que si
                log("sin transmision: %s" % cur.name)
                fails += 1
                if fails < n:
                    ui.idx = (ui.idx + switch_dir) % n
                    ui._scroll()
                    cur = ui.view[ui.idx]
                    continue
                # Ninguno transmite: volver al canal donde estaba
                switch_dir = 0
                if last_good is not None:
                    cur = last_good
                    try:
                        ui.idx = ui.view.index(last_good)
                        ui._scroll()
                    except ValueError:
                        pass
                    notice = T("no_other")
                    continue
            if want != "back" and died and dur < 8 and auth_failed() and cur.url not in UA_TRY:
                UA_TRY.add(cur.url)
                log("401/403: reintento como VLC: %s" % cur.name)
                time.sleep(1.5)
                continue
            if want != "back" and died and dur < 8 and start_pos == 0:
                if auth_failed():
                    notice = T("auth_fail")
                else:
                    notice = T("play_fail", ffplay_reason())
                log("ffplay duro %.1fs: %s" % (dur, notice))
            break
        reset_hold()
        gfx.open()
        open_inputs()
        return notice

    ui.draw()

    def start_hold(action):
        if ui.state == "kbd" and action in ("pgup", "l1"):   # L1/L2 del teclado son interruptores: sin repeticion
            return None
        return (action, time.time() + 0.35) if action in ("up", "down", "left", "right", "pgup", "pgdn", "l1", "r1") else None

    while running:
        wd()
        action = None
        while action is None and sdl2.SDL_PollEvent(ctypes.byref(ev)):
            t = ev.type
            if t == sdl2.SDL_QUIT:
                running = False
            elif t == sdl2.SDL_KEYDOWN:
                if ev.key.repeat:
                    continue
                sym = ev.key.keysym.sym
                action = key_map.get(sym)
                log("tecla %s -> %s" % (sym, action))
                held = start_hold(action)
            elif t == sdl2.SDL_KEYUP:
                held = None
            elif t == sdl2.SDL_CONTROLLERBUTTONDOWN:
                b = ev.cbutton.button
                action = ctrl_map.get(b)
                log("mando boton %d -> %s" % (b, action))
                held = start_hold(action)
            elif t == sdl2.SDL_CONTROLLERBUTTONUP:
                held = None
            elif t == sdl2.SDL_CONTROLLERAXISMOTION:
                ax, v = ev.caxis.axis, ev.caxis.value
                if ax in (sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT):
                    k = "l" if ax == sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT else "r"
                    if v > 16000 and not trig[k]:
                        trig[k] = True
                        action = "pgup" if k == "l" else "pgdn"      # L2/R2: pagina
                        log("gatillo %s2 (eje %d)" % (k.upper(), ax))
                        held = start_hold(action)
                    elif v < 8000 and trig[k]:
                        trig[k] = False
                        held = None
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYHATMOTION:
                v = ev.jhat.value
                action = ("left" if v & sdl2.SDL_HAT_LEFT else "right" if v & sdl2.SDL_HAT_RIGHT
                          else "up" if v & sdl2.SDL_HAT_UP else "down" if v & sdl2.SDL_HAT_DOWN else None)
                log("hat %d -> %s" % (v, action))
                held = start_hold(action)
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYBUTTONDOWN:
                b = ev.jbutton.button
                action = joy_map.get(b)
                log("joy boton %d -> %s" % (b, action))
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYBUTTONUP:
                held = None
            elif state["controllers"] == 0 and t == sdl2.SDL_JOYAXISMOTION:
                a, v = ev.jaxis.axis, ev.jaxis.value
                if a in axis:
                    new = -1 if v < -16000 else 1 if v > 16000 else 0
                    if new != axis[a]:
                        axis[a] = new
                        if new:
                            action = (("left" if new < 0 else "right") if a == 0
                                      else ("up" if new < 0 else "down"))
                            log("eje %d -> %s" % (a, action))
                            held = start_hold(action)
                        else:
                            held = None
            elif t in (sdl2.SDL_JOYDEVICEADDED, sdl2.SDL_JOYDEVICEREMOVED):
                log("cambio de dispositivo")

        if action is None and held and time.time() >= held[1]:
            action = held[0]
            held = (held[0], time.time() + 0.08)

        if action:
            log("accion %s (estado %s)" % (action, ui.state))
            if toast:
                ui.notice = ""
            toast = False
            sig0 = ui_sig()
            res = ui.handle(action)
            snd_after(action, sig0)
            if res:
                kind, entry = res
                if kind == "quit":
                    log("salir pedido por la UI")
                    running = False
                elif kind == "save_favs":
                    ok = save_favs(favs_path, ui.favs)
                    log("favoritos guardados (%d): %s" % (len(ui.favs), "ok" if ok else "ERROR al escribir"))
                    if not ok:
                        ui.notice = T("no_save_favs")
                elif kind == "settings_changed":
                    save_settings()
                    sources[:] = discover_sources()
                    exp_start()      # los nombres cambian con el idioma
                    ui.sources = sources
                    log("ajustes: %s" % settings)
                elif kind == "switch_list":
                    src = next((sc for sc in sources if sc["id"] == entry), None)
                    if src is not None:
                        ents, nt = load_source(src, download=(not os.path.exists(src["path"])))
                        ui.query = {}
                        ui.state = "home"
                        ui.set_entries(ents, src["name"])
                        settings["source"] = src["id"]
                        save_settings()
                        ui.notice = nt or (T("list_loaded", src["name"], len(ents)) if ents
                                           else T("list_empty", src["name"]))
                        toast = True
                        log("lista activa: %s (%d)" % (src["id"], len(ents)))
                elif kind == "delete_list":
                    src = next((sc for sc in sources if sc["id"] == entry), None)
                    if src is not None and entry.startswith("f:"):
                        try:
                            os.remove(os.path.join(listas_dir, entry[2:]))
                            if src["url"] and os.path.exists(src["path"]):
                                os.remove(src["path"])
                            was_active = (settings.get("source", "main") == entry)
                            sources[:] = discover_sources()
                            exp_start()
                            ui.sources = sources
                            ui.m_idx = max(0, min(ui.m_idx, len(sources) - 1))
                            if was_active:
                                nxt = sources[0] if sources else None
                                ents = []
                                if nxt is not None:
                                    ents, _ = load_source(nxt, download=(not os.path.exists(nxt["path"])))
                                ui.query = {}
                                ui.set_entries(ents, nxt["name"] if nxt else "-")
                                settings["source"] = nxt["id"] if nxt else "main"
                                save_settings()
                                ui.state = "lists"
                            ui.notice = T("del_done", src["name"])
                            log("lista borrada: %s" % entry)
                        except Exception:
                            log("no pude borrar la lista: " + traceback.format_exc())
                            ui.notice = T("del_fail")
                    toast = True
                elif kind == "update_lists":
                    splash(T("updating"), 0.0)
                    sources[:] = discover_sources()
                    exp_start()
                    ok_n = tot_n = 0
                    n_url = max(1, sum(1 for sc in sources if sc["url"]))
                    for src in sources:
                        if src["url"]:
                            lo_ = 0.7 * tot_n / n_url
                            tot_n += 1
                            os.makedirs(os.path.dirname(src["path"]), exist_ok=True)
                            if not download_list(src["url"], src["path"],
                                                 make_prog(T("updating"), lo_, 0.7 * tot_n / n_url)):
                                ok_n += 1
                    cur_src = next((sc for sc in sources if sc["id"] == settings.get("source", "main")),
                                   sources[0] if sources else None)
                    ents = []
                    if cur_src is not None and os.path.exists(cur_src["path"]):
                        splash(T("reading"), 0.7)
                        ents = load_file(cur_src["path"], kw_s, kw_p, make_prog(T("reading"), 0.7, 1.0))
                    ui.sources = sources
                    ui.set_entries(ents, cur_src["name"] if cur_src else "-")
                    if tot_n == 0:
                        ui.notice = T("upd_none")
                    elif ok_n == tot_n:
                        ui.notice = T("upd_ok", len(ents))
                    else:
                        ui.notice = T("upd_partial", ok_n, tot_n)
                    toast = True
                    log("actualizar: %d/%d listas, %d entradas" % (ok_n, tot_n, len(ents)))
                elif kind == "play":
                    log("reproducir: %s | %s" % (entry.name, entry.url))
                    ui.draw_splash(entry.name)
                    ui.notice = ""
                    snd.close()                                  # el video usa su propio audio
                    note = play_loop(entry)
                    if home_req[0]:
                        home_req[0] = False
                        ui.state = "home"
                    if note:
                        ui.notice = note
                        toast = True
                    held = None
                    reset_hold()
                    axis[0] = axis[1] = 0
            if running:
                try:
                    ui.draw()
                except Exception:
                    log("ERROR al dibujar: " + traceback.format_exc())
        elif ui.state == "list" and ui.cat in SPLIT_CATS and time.time() - last_anim > 0.05:
            last_anim = time.time()
            ui.draw()                                    # brillo del marcador animado
        elif ui.state == "settings" and ui.anim and time.time() - last_anim > (
                0.03 if ui.mq_on else (0.05 if ui.pv_on else 0.15)):
            last_anim = time.time()
            ui.draw()                                    # letrero que se desplaza
        elif ui.state == "support" and time.time() - last_anim > 0.25:
            last_anim = time.time()
            ui.draw()                                    # progreso de la actualizacion
        elif ui.state == "lists" and exp_flag[0]:
            exp_flag[0] = False
            ui.draw()                                    # llego un vencimiento
        elif ui.state in ("list", "kbd", "lists") and ui.mq_on and not (ui.state == "list" and ui.cat in SPLIT_CATS) \
                and time.time() - last_anim > 0.03:
            last_anim = time.time()
            ui.draw()                                    # letrero que se desplaza (listas, teclado)
        elif ui.state == "home":
            m = time.localtime().tm_min
            if ui.zoom_busy() or ((ui.fx_live() or ui.mq_on) and m == last_minute):
                if time.time() - last_anim > (0.025 if ui.zoom_busy() else ui.fx_interval()):
                    last_anim = time.time()
                    ui.draw(fast=True)                   # zoom de iconos y efectos de las tarjetas
            elif m != last_minute or ui.online != net["ok"] or ui.wifi_level != net["wifi"]:
                last_minute = m
                ui.online = net["ok"]
                ui.wifi_level = net["wifi"]
                ui.draw()
        sdl2.SDL_Delay(10 if ((ui.state == "list" and ui.cat in SPLIT_CATS) or ui.mq_on) else 25)

    gfx.close()
    log("fin")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise
