# -*- coding: utf-8 -*-
"""Reproductor interno (prueba): ffmpeg decodifica y la app dibuja.
ffmpeg manda el video (RGB24 640x480) por stdout y el audio (s16le estereo) por una tubería extra;
el audio se reproduce con SDL y es el reloj maestro. La pausa congela el reloj sin cerrar nada."""
import ctypes
import os
import re
import subprocess
import threading
import time
import traceback
from collections import deque

import sdl2

import tracks
import vgeom

AR = 44100
ABPS = AR * 4            # bytes de audio por segundo (s16, estereo)


class VPlayer(object):
    def __init__(self, ffmpeg, url, pos, W, H, mode, ast, ua, env, log, hdr=None, logfile=None, sst=None, live=False, ssc=None, short=False):
        self.W, self.H, self.log = W, H, log
        self.fs = W * H * 3
        self.pos0 = float(pos)
        self.info = {}
        self.frames = deque()
        self.lock = threading.Lock()
        self.eof = False
        self.dead = False
        self.vfps = 0.0
        self.nframes = 0          # cuadros decodificados (indice del siguiente)
        self.shown = 0
        self.dropped = 0
        self.last = None          # ultimo cuadro mostrado (bytes)
        self.last_pts = 0.0
        self.t_start = time.time()
        self.t_first = None
        self.paused = False
        self.fed = 0              # bytes de audio entregados a SDL
        self.adev = 0
        self.audio_ok = False
        self.wall0 = None
        self.pause_clock = None
        self.stop_flag = False
        self.audio_done = False
        self.W, self.H = W, H
        self.crop = None          # (x0, y0, x1, y1) sin las barras negras de la propia imagen (modo "auto")
        self.mode = mode
        self.auto = (mode == "auto")
        self._bars = None         # barras minimas vistas (izq, arriba, der, abajo) en pixeles
        self.dar = None           # relacion de aspecto de la imagen original (se lee de ffmpeg)
        self._dar_read = False
        self.net_fail = False     # ffmpeg no pudo llegar al servidor (sin internet / DNS)
        self.marks = {}           # tiempos del arranque (para el log)
        # ffmpeg manda siempre el cuadro completo estirado a W x H; el modo de pantalla se aplica al dibujar
        # (geom), asi cambiar de modo no reinicia el video ni pierde el punto donde estaba.
        vf = "scale=%d:%d:flags=fast_bilinear,setsar=1" % (W, H)
        ar, aw = os.pipe()
        self.afd = ar
        self.cues = []
        self.sfd = None
        self.sub_proc = None
        self.sub_off = 0.0
        sw = None
        sep = sst is not None and ssc == "mov_text"       # mov_text (mp4): proceso aparte, solo lee la pista de texto
        if sst is not None and not sep:
            self.sfd, sw = os.pipe()
        cmd = [ffmpeg, "-nostdin", "-nostats", "-loglevel", "info",
               "-probesize", "1000000" if short else "3000000", "-analyzeduration", "1000000" if short else "3000000"]
        if ua:
            cmd += ["-user_agent", ua]
        if live and url.startswith("http"):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "4"]
        if pos > 1 and not live:
            cmd += ["-ss", "%.3f" % pos]
        cmd += list(hdr or [])
        cmd += ["-i", url, "-map", "0:v:0", "-vf", vf, "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
        cmd += ["-map", ("0:%d" % ast) if ast is not None else "0:a:0?",
                "-vn", "-ac", "2", "-ar", str(AR), "-f", "s16le", "pipe:%d" % aw]
        if sst is not None and not sep:       # subtitulos de texto -> SRT por otra tuberia (la app los dibuja)
            cmd += ["-map", "0:%d" % sst, "-vn", "-an", "-c:s", "srt", "-flush_packets", "1", "-f", "srt", "pipe:%d" % sw]
        self.cmd = cmd
        env = dict(env)
        self._open_audio()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env,
                                     pass_fds=(aw,) if sw is None else (aw, sw))
        os.close(aw)
        if sw is not None:
            os.close(sw)
        self.logf = logfile
        self.threads = []
        fns = [self._err_reader, self._video_reader, self._audio_reader, self._sub_reader]
        self._sub_ctx = (ffmpeg, ua, url, hdr, env)
        if sep:
            self._start_sub_proc(sst, fns)
        for fn in fns:
            th = threading.Thread(target=fn, daemon=True)
            th.start()
            self.threads.append(th)

    def _start_sub_proc(self, sst, fns=None):
        """Lee la pista de texto mov_text en un proceso aparte (sin tocar el video)."""
        ffmpeg, ua, url, hdr, env = self._sub_ctx
        try:
            scmd = [ffmpeg, "-nostdin", "-nostats", "-loglevel", "error", "-probesize", "3000000"]
            if ua:
                scmd += ["-user_agent", ua]
            if url.startswith("http"):
                scmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "4"]
            scmd += list(hdr or [])
            scmd += ["-i", url, "-map", "0:%d" % sst, "-vn", "-an", "-c:s", "srt",
                     "-flush_packets", "1", "-f", "srt", "pipe:1"]
            self.sub_off = self.pos0
            self.sub_proc = subprocess.Popen(scmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, env=dict(env))
            if fns is not None:
                fns.append(self._sub_proc_reader)
            else:
                th = threading.Thread(target=self._sub_proc_reader, daemon=True)
                th.start()
                self.threads.append(th)
        except Exception:
            self.log("video interno: no se pudo leer la pista de subtitulos\n" + traceback.format_exc())

    def start_subs(self, sst):
        """Activa subtitulos mov_text con el video ya sonando (sin reiniciar)."""
        if self.sub_proc is None:
            self.cues = []
            self._start_sub_proc(sst)

    # ---------- audio SDL ----------
    def _open_audio(self):
        try:
            if not sdl2.SDL_WasInit(sdl2.SDL_INIT_AUDIO):
                sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO)
            want = sdl2.SDL_AudioSpec(AR, sdl2.AUDIO_S16LSB, 2, 2048)
            have = sdl2.SDL_AudioSpec(0, 0, 0, 0)
            self.adev = sdl2.SDL_OpenAudioDevice(None, 0, want, ctypes.byref(have), 0)
            if self.adev:
                self.audio_ok = True
                self.log("video interno: audio SDL abierto (%d Hz)" % have.freq)
            else:
                self.log("video interno: sin audio SDL: %s" % sdl2.SDL_GetError())
        except Exception:
            self.log("video interno: audio fallo\n" + traceback.format_exc())

    def _audio_reader(self):
        started = False
        try:
            while not self.stop_flag:
                d = os.read(self.afd, 8192)
                if not d:
                    break
                if not self.audio_ok:
                    continue
                while not self.stop_flag and sdl2.SDL_GetQueuedAudioSize(self.adev) > ABPS * 3:
                    time.sleep(0.05)
                sdl2.SDL_QueueAudio(self.adev, d, len(d))
                self.fed += len(d)
                if not started and self.fed >= ABPS // 2:
                    started = True
                    if not self.paused:
                        sdl2.SDL_PauseAudioDevice(self.adev, 0)
        except Exception:
            self.log("video interno: lector de audio\n" + traceback.format_exc())
        self.audio_done = True

    # ---------- subtitulos ----------
    _T = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")

    def _sub_reader(self):
        if self.sfd is None:
            return
        buf = b""
        try:
            while not self.stop_flag:
                d = os.read(self.sfd, 4096)
                if not d:
                    break
                buf += d.replace(b"\r", b"")
                while b"\n\n" in buf:
                    blk, buf = buf.split(b"\n\n", 1)
                    self._add_cue(blk.decode("utf-8", "replace"))
            if buf.strip():
                self._add_cue(buf.decode("utf-8", "replace"))
        except Exception:
            self.log("video interno: lector de subtitulos\n" + traceback.format_exc())

    def _sub_proc_reader(self):
        buf = b""
        try:
            out = self.sub_proc.stdout
            while not self.stop_flag:
                d = out.read1(4096)
                if not d:
                    break
                buf += d.replace(b"\r", b"")
                while b"\n\n" in buf:
                    blk, buf = buf.split(b"\n\n", 1)
                    self._add_cue(blk.decode("utf-8", "replace"))
            if buf.strip():
                self._add_cue(buf.decode("utf-8", "replace"))
            self.log("video interno: subtitulos de texto cargados: %d" % len(self.cues))
        except Exception:
            self.log("video interno: lector de subtitulos (proceso)\n" + traceback.format_exc())

    def _add_cue(self, blk):
        lines = [x for x in blk.strip().split("\n")]
        for i, ln in enumerate(lines):
            m = self._T.search(ln)
            if m:
                g = [int(x) for x in m.groups()]
                t0 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0 - self.sub_off
                t1 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0 - self.sub_off
                txt = []
                for x in lines[i + 1:]:
                    x = re.sub(r"<[^>]*>|\{[^}]*\}", "", x).strip()
                    if x:
                        txt.append(x)
                if txt:
                    self.cues.append((t0, t1, txt))
                return

    def sub_lines(self):
        """Lineas de subtitulo que tocan mostrar ahora."""
        if not self.cues:
            return []
        now = self.clock()
        out = []
        for t0, t1, txt in (self.cues if self.sub_proc else self.cues[-40:]):
            if t0 <= now <= t1:
                out += txt
        return out[-3:]

    # ---------- video y mensajes ----------
    def _video_reader(self):
        try:
            out = self.proc.stdout
            while not self.stop_flag:
                while len(self.frames) >= 20 and not self.stop_flag:
                    time.sleep(0.01)
                d = out.read(self.fs)
                if not d or len(d) < self.fs:
                    break
                with self.lock:
                    self.frames.append((self.nframes, d))
                    self.nframes += 1
                if self.t_first is None:
                    self.t_first = time.time()
                    self.marks["frame"] = self.t_first - self.t_start
        except Exception:
            self.log("video interno: lector de video\n" + traceback.format_exc())
        self.eof = True

    def _err_reader(self):
        buf = b""
        try:
            while True:
                chunk = self.proc.stderr.read1(4096)
                if not chunk:
                    break
                parts = re.split(rb"[\r\n]", buf + chunk)
                buf = parts.pop()
                for p in parts:
                    if not p.strip():
                        continue
                    try:
                        tracks.parse_line(self.info, p.decode("utf-8", "replace"))
                    except Exception:
                        pass
                    t = p.decode("utf-8", "replace")
                    if "t0" not in self.marks:
                        self.marks["t0"] = time.time() - self.t_start          # primer mensaje de ffmpeg
                    if t.startswith("Input #0") and "in" not in self.marks:
                        self.marks["in"] = time.time() - self.t_start          # entrada abierta
                    if not self.net_fail and re.search(
                            r"Failed to resolve hostname|Network is unreachable|No route to host|Connection timed out|Connection refused", t):
                        self.net_fail = True
                    if not self._dar_read:
                        dr = vgeom.parse_dar(t.strip())
                        if dr:
                            self.dar = dr
                            self._dar_read = True
                            self.marks["dar"] = time.time() - self.t_start
                            self.log("video interno: imagen original aspecto %.3f" % dr)
                    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
                    if d and "dur" not in self.info:
                        self.info["dur"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
                    m = re.search(r"Video:.*?([\d.]+) fps", t) or re.search(r"Video:.*?([\d.]+) tbr", t)
                    if m and not self.vfps:
                        try:
                            self.vfps = float(m.group(1))
                        except ValueError:
                            pass
                    if "http" not in t.lower() and re.search(r"rror|ail|nvalid|Stream #|Duration|Unsupported|denied", t):
                        self.log("ffmpeg: " + t.strip()[:200])
        except Exception:
            pass

    # ---------- reloj ----------
    def clock(self):
        """Segundos transcurridos desde el inicio del tramo (reloj de audio, o de pared sin audio)."""
        if self.pause_clock is not None:
            return self.pause_clock
        if self._aclock():
            q = sdl2.SDL_GetQueuedAudioSize(self.adev)
            return max(0.0, (self.fed - q) / float(ABPS))
        if self.wall0 is None:
            return 0.0
        return time.time() - self.wall0

    def _aclock(self):
        return self.audio_ok and self.fed >= ABPS // 2

    def position(self):
        return self.pos0 + self.clock()

    def pause(self):
        if self.paused:
            return
        self.pause_clock = self.clock()
        self.paused = True
        if self.audio_ok:
            sdl2.SDL_PauseAudioDevice(self.adev, 1)

    def resume(self):
        if not self.paused:
            return
        self.paused = False
        if self.audio_ok:
            if self.fed >= ABPS // 2:
                sdl2.SDL_PauseAudioDevice(self.adev, 0)
        if not self._aclock() and self.wall0 is not None:
            self.wall0 = time.time() - self.pause_clock
        self.pause_clock = None

    def ready(self):
        return self.last is not None or len(self.frames) > 0

    def next_frame(self):
        """Devuelve el cuadro que toca mostrar ahora (bytes), o None si no hay uno nuevo."""
        if self.paused:
            return None
        fps = self.vfps or 24.0
        if not self._aclock():
            if self.audio_ok and not self.audio_done:
                return None                      # esperando el primer medio segundo de audio
            if self.wall0 is None and self.frames:
                self.wall0 = time.time()
        now = self.clock()
        got = None
        with self.lock:
            while self.frames and self.frames[0][0] / fps <= now:
                n, d = self.frames.popleft()
                if got is not None:
                    self.dropped += 1
                got = d
                self.last_pts = n / fps
        if got is not None:
            self.shown += 1
            self.last = got
            if "shown" not in self.marks:
                self.marks["shown"] = time.time() - self.t_start
            if self.auto and (self.shown < 60 and self.shown % 6 == 1 or self.shown % 45 == 1):
                try:
                    self._detect(got)
                except Exception:
                    self.auto = False
        return got

    _TBL = bytes([0] * 29 + [1] * 227)          # <= 28 = negro

    @staticmethod
    def _pct(v, p=0.2):
        v = sorted(v)
        return v[int(len(v) * p)] if v else 0

    def _detect(self, d):
        """Busca las barras negras que ya trae la imagen (lados o arriba/abajo) y fija el recorte."""
        W, H, tb = self.W, self.H, self._TBL
        L, R, T_, B = [], [], [], []
        for y in range(4, H - 4, max(1, H // 24)):
            t = d[y * W * 3:(y + 1) * W * 3].translate(tb)
            a = len(t.lstrip(b"\x00"))
            if a == 0:                           # fila toda negra: no dice nada
                continue
            L.append((len(t) - a) // 3)
            R.append((len(t) - len(t.rstrip(b"\x00"))) // 3)
        for x in range(4, W - 4, max(1, W // 32)):
            t = d[x * 3 + 1::W * 3].translate(tb)
            a = len(t.lstrip(b"\x00"))
            if a == 0:
                continue
            T_.append(len(t) - a)
            B.append(len(t) - len(t.rstrip(b"\x00")))
        if len(L) < 10 or len(T_) < 10:          # escena casi toda negra
            return
        cur = (self._pct(L), self._pct(T_), self._pct(R), self._pct(B))
        if self._bars is None:
            self._bars = cur
        else:
            self._bars = tuple(min(a, b) for a, b in zip(self._bars, cur))   # solo se achican
        l, t, r, b = self._bars
        l = min(l, W * 35 // 100) // 2 * 2
        r = min(r, W * 35 // 100) // 2 * 2
        t = min(t, H * 35 // 100) // 2 * 2
        b = min(b, H * 35 // 100) // 2 * 2
        if l < 8: l = 0
        if r < 8: r = 0
        if t < 8: t = 0
        if b < 8: b = 0
        new = (l, t, W - r, H - b) if (l or t or r or b) else None
        if new != self.crop:
            self.crop = new
            self.log("video interno: Estirar recorte %s" % (new,))

    def set_mode(self, mode):
        """Cambia el modo de pantalla al instante, sin reiniciar el video."""
        if mode == self.mode:
            return
        self.mode = mode
        self.auto = (mode == "auto")
        if not self.auto:
            self.crop = None
        elif self.last is not None:
            try:
                self._detect(self.last)
            except Exception:
                self.auto = False

    def geom(self):
        """(origen, destino) para dibujar el cuadro actual segun el modo (ver vgeom)."""
        return vgeom.geometry(self.mode, self.dar, self.W, self.H, self.crop)

    def start_report(self):
        m = self.marks
        return "arranque: ffmpeg %.2fs, entrada abierta %.2fs, analisis %.2fs, primer cuadro %.2fs, mostrado %.2fs" % (
            m.get("t0", -1), m.get("in", -1), m.get("dar", -1), m.get("frame", -1), m.get("shown", -1))

    def finished(self):
        return self.eof and not self.frames

    def failed(self):
        return self.dead or (self.proc.poll() not in (None, 0) and self.nframes == 0)

    def stats(self):
        el = max(0.001, time.time() - (self.t_first or self.t_start))
        return "cuadros %d mostrados %d perdidos %d (%.1f/s) fps_fuente %.1f" % (
            self.nframes, self.shown, self.dropped, self.shown / el, self.vfps)

    def close(self):
        self.stop_flag = True
        try:
            import proxy
            proxy.drop_all_active()          # corta ya la conexion del puente hacia el proveedor
        except Exception:
            pass
        try:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait()
        except Exception:
            pass
        try:
            if self.sub_proc is not None:
                if self.sub_proc.poll() is None:
                    self.sub_proc.kill()
                self.sub_proc.wait()
        except Exception:
            pass
        # los lectores terminan solos al cerrarse ffmpeg; se esperan ANTES de cerrar las tuberias
        # (cerrar un descriptor que otro hilo esta leyendo puede robar el de un mando u otro archivo)
        for th in getattr(self, "threads", []):
            th.join(2.0)
        for fd in (self.afd, self.sfd):
            try:
                if fd is not None:
                    os.close(fd)
            except Exception:
                pass
        if self.adev:
            try:
                sdl2.SDL_CloseAudioDevice(self.adev)
            except Exception:
                pass
