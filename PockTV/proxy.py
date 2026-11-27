"""Mini puente https -> http local. El ffplay de la Flip no trae https, asi que
ffplay pide http://127.0.0.1:PUERTO/p/<token>/x.m3u8 y este puente baja el
contenido por https (con el Python de Spruce) y reescribe las listas HLS para
que los segmentos tambien pasen por aqui.
"""
import base64
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

UA = "Mozilla/5.0 (Linux; Miyoo) IPTV"
_ACTIVE = set()                      # respuestas abiertas hacia el proveedor (para cerrarlas al detener el video)
_ACTIVE_LOCK = threading.Lock()


def drop_all_active():
    """Cierra YA las conexiones abiertas hacia el proveedor: al reiniciar el video no queda una conexion vieja
    ocupando el cupo (algunos proveedores solo dejan una a la vez)."""
    with _ACTIVE_LOCK:
        rs = list(_ACTIVE)
        _ACTIVE.clear()
    for r in rs:
        try:
            sk = getattr(getattr(r.fp, "raw", None), "_sock", None)
            if sk is not None:
                import socket
                sk.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            r.close()
        except Exception:
            pass

URI_RE = re.compile(r'URI="([^"]+)"')


def _enc(u):
    return base64.urlsafe_b64encode(u.encode()).decode().rstrip("=")


def _dec(t):
    return base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)).decode()


def _ext(u):
    path = urllib.parse.urlparse(u).path.lower()
    for e in (".m3u8", ".ts", ".aac", ".mp4", ".m4s", ".mp3", ".key", ".vtt"):
        if path.endswith(e):
            return e
    return ".bin"


class Bridge(object):
    def __init__(self, log=None, verify=False):
        import ssl
        self.log = log or (lambda m: None)
        self.ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                outer._serve(self)

        class S(ThreadingMixIn, HTTPServer):
            daemon_threads = True

        self.srv = S(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def url_for(self, u):
        return "http://127.0.0.1:%d/p/%s/x%s" % (self.port, _enc(u), _ext(u))

    def _rewrite(self, text, base):
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                out.append(line)
            elif s.startswith("#"):
                out.append(URI_RE.sub(
                    lambda m: 'URI="%s"' % self.url_for(urllib.parse.urljoin(base, m.group(1))), line))
            else:
                out.append(self.url_for(urllib.parse.urljoin(base, s)))
        return "\n".join(out) + "\n"

    def _serve(self, h):
        try:
            token = h.path.split("/")[2]
            url = _dec(token)
        except Exception:
            h.send_error(400)
            return
        hdrs = {"User-Agent": UA, "Accept": "*/*"}
        rng = h.headers.get("Range")
        if rng:                                   # ffmpeg pide tramos (saltos en peliculas/series)
            hdrs["Range"] = rng
        try:
            req = urllib.request.Request(url, headers=hdrs)
            r = urllib.request.urlopen(req, timeout=20, context=self.ctx)
        except urllib.error.HTTPError as e:
            self.log("puente: HTTP %d %s" % (e.code, url[:60]))
            try:
                h.send_error(e.code)
            except Exception:
                pass
            return
        except Exception as e:
            self.log("puente: fallo %s -> %r" % (url[:120], e))
            try:
                h.send_error(502, str(e)[:100])
            except Exception:
                pass
            return
        with _ACTIVE_LOCK:
            _ACTIVE.add(r)
        try:
            try:
                first = r.read1(65536)             # no espera a llenar 64 KB: el video empieza antes
            except AttributeError:
                first = r.read(65536)
            code = r.getcode() or 200
            if rng:
                self.log("puente: tramo %s -> HTTP %d" % (rng[:30], code))
            ct = (r.headers.get("Content-Type") or "").lower()
            if not first.startswith(b"#EXTM3U") and ("text/" in ct or "html" in ct or "json" in ct):
                # no es video (pagina de error del proveedor): se avisa y se corta para que el reproductor falle rapido
                self.log("puente: respuesta rara del proveedor HTTP %d tipo %s tam %s" % (code, ct[:30], r.headers.get("Content-Length")))
                h.send_error(503)
                return
            if first.startswith(b"#EXTM3U") and code == 200:
                rest = r.read(5 * 1024 * 1024)
                body = self._rewrite((first + rest).decode("utf-8", "replace"), r.geturl()).encode()
                h.send_response(200)
                h.send_header("Content-Type", "application/vnd.apple.mpegurl")
                h.send_header("Content-Length", str(len(body)))
                h.end_headers()
                h.wfile.write(body)
                return
            h.send_response(code if code in (200, 206) else 200)
            for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                v = r.headers.get(name)
                if v:
                    h.send_header(name, v)
            h.end_headers()
            h.wfile.write(first)
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                h.wfile.write(chunk)
        except Exception:
            pass  # el reproductor cerro la conexion
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(r)
            try:
                r.close()
            except Exception:
                pass

    def close(self):
        try:
            self.srv.shutdown()
        except Exception:
            pass
