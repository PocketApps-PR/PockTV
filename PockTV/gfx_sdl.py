"""Backend grafico SDL2 (PySDL2 + SDL_ttf), el que trae Spruce para PyUI."""
import ctypes
import os
import struct

import sdl2
import sdl2.sdlttf as ttf

from gfx_raster import RasterGfx


class Sdl2Gfx(RasterGfx):
    def __init__(self, font_dir, w=640, h=480, log=None):
        self.font_dir = font_dir
        self.w, self.h = w, h
        self.log = log or (lambda m: None)
        self.win = None
        self.ren = None
        self._fonts = {}
        self.vcrop = None                # parte del cuadro de video que se muestra
        self.vdst = None                 # donde se dibuja el cuadro de video (modo Normal)
        self.mode_hook = None            # el reproductor lo usa para cambiar de modo al instante
        self._tex = {}
        self._color = None

    # ---- ciclo de vida -------------------------------------------------
    def open(self):
        flags = sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER
        if sdl2.SDL_Init(flags) != 0:
            raise RuntimeError("SDL_Init: %s" % sdl2.SDL_GetError())
        if ttf.TTF_Init() != 0:
            raise RuntimeError("TTF_Init: %s" % sdl2.SDL_GetError())
        self.log("SDL video driver: %s" % sdl2.SDL_GetCurrentVideoDriver())
        self.win = sdl2.SDL_CreateWindow(b"PockTV", 0, 0, self.w, self.h,
                                         sdl2.SDL_WINDOW_SHOWN)
        if not self.win:
            raise RuntimeError("SDL_CreateWindow: %s" % sdl2.SDL_GetError())
        self.ren = sdl2.SDL_CreateRenderer(self.win, -1, sdl2.SDL_RENDERER_ACCELERATED)
        if not self.ren:
            self.log("renderer acelerado fallo (%s); uso software" % sdl2.SDL_GetError())
            self.ren = sdl2.SDL_CreateRenderer(self.win, -1, sdl2.SDL_RENDERER_SOFTWARE)
        if not self.ren:
            raise RuntimeError("SDL_CreateRenderer: %s" % sdl2.SDL_GetError())
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_NONE)
        sdl2.SDL_ShowCursor(0)
        self._color = None                    # el renderer nuevo no recuerda el color del anterior
        self._valid = set()
        ww, hh = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetRendererOutputSize(self.ren, ctypes.byref(ww), ctypes.byref(hh))
        self.log("ventana %dx%d, salida %dx%d" % (self.w, self.h, ww.value, hh.value))
        if ww.value and (ww.value, hh.value) != (self.w, self.h):
            sdl2.SDL_RenderSetLogicalSize(self.ren, self.w, self.h)

    def close(self):
        for t in self._tex.values():
            sdl2.SDL_DestroyTexture(t[0])
        self._tex = {}
        for f in self._fonts.values():
            ttf.TTF_CloseFont(f)
        self._fonts = {}
        if self.ren:
            sdl2.SDL_DestroyRenderer(self.ren)
        if self.win:
            sdl2.SDL_DestroyWindow(self.win)
        self.ren = self.win = None
        ttf.TTF_Quit()
        sdl2.SDL_Quit()

    # ---- primitivas ----------------------------------------------------
    def _set(self, c):
        if c != self._color:
            sdl2.SDL_SetRenderDrawColor(self.ren, c[0], c[1], c[2], 255)
            self._color = c

    def _fill(self, x, y, w, h, c):
        if w <= 0 or h <= 0:
            return
        self._set(c)
        sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))

    def _line(self, x1, y1, x2, y2, c):
        self._set(c)
        sdl2.SDL_RenderDrawLine(self.ren, x1, y1, x2, y2)

    def clear(self, c):
        self._set(c)
        sdl2.SDL_RenderClear(self.ren)

    def present(self):
        sdl2.SDL_RenderPresent(self.ren)

    # ---- imagenes (.rgba crudos hechos con tools/bake_icons) -------------
    def image(self, name, size, cx, cy, color=None, scale=1.0, angle=0.0, sx=1.0, sy=1.0):
        """Dibuja img/<name>_<size>.rgba centrado en (cx, cy). `color` tine el icono (blanco por defecto).
        Devuelve False si no existe el archivo (para usar el dibujo de respaldo)."""
        key = ("img", name, size)
        t = self._tex.get(key)
        if t is None:
            base = os.path.join(os.path.dirname(self.font_dir), "img", "%s_%d" % (name, size))
            hd = os.path.exists(base + "@2.rgba")           # version HD (el doble de pixeles): se dibuja a la mitad con filtro suave
            path = base + ("@2.rgba" if hd else ".rgba")
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                w, h = struct.unpack("<II", raw[:8])
                data = raw[8:8 + w * h * 4]
                if hd:
                    sdl2.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
                tex = sdl2.SDL_CreateTexture(self.ren, sdl2.SDL_PIXELFORMAT_ABGR8888,
                                             sdl2.SDL_TEXTUREACCESS_STATIC, w, h)
                if hd:
                    sdl2.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"0")
                if not tex:
                    self.log("imagen %s: no se pudo crear la textura (%s)" % (path, sdl2.SDL_GetError()))
                    return False
                sdl2.SDL_UpdateTexture(tex, None, data, w * 4)
                sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
                if hd:
                    w, h = w // 2, h // 2
            except Exception as e:
                self.log("imagen %s: %r" % (path, e))
                self._tex[key] = (None, 0, 0)
                return False
            t = (tex, w, h)
            self._tex[key] = t
        tex, w, h = t
        if tex is None:
            return False
        c = color or (255, 255, 255)
        sdl2.SDL_SetTextureColorMod(tex, c[0], c[1], c[2])
        dw, dh = (int(round(w * scale * sx)), int(round(h * scale * sy))) if (scale != 1.0 or sx != 1.0 or sy != 1.0) else (w, h)
        rect = sdl2.SDL_Rect(int(round(cx - dw / 2.0)), int(round(cy - dh / 2.0)), dw, dh)
        if angle:
            sdl2.SDL_RenderCopyEx(self.ren, tex, None, rect, float(angle), None, sdl2.SDL_FLIP_NONE)
        else:
            sdl2.SDL_RenderCopy(self.ren, tex, None, rect)
        return True

    _SPECIAL = ("cache", "shadow", "shine", "dot", "pv", "img", "asset")

    # ---- cache del fondo (textura de destino) -------------------------
    def begin_cache(self, key, clear=False):
        """Empieza a dibujar en una textura guardada; si no se puede, False y dibuja normal."""
        try:
            self._valid = getattr(self, "_valid", set())
            self._valid.discard(key)
            t = self._tex.get(("cache", key))
            if t is None:
                tex = sdl2.SDL_CreateTexture(self.ren, sdl2.SDL_PIXELFORMAT_ARGB8888,
                                             sdl2.SDL_TEXTUREACCESS_TARGET, self.w, self.h)
                if not tex:
                    return False
                sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
                t = (tex, self.w, self.h)
                self._tex[("cache", key)] = t
            if sdl2.SDL_SetRenderTarget(self.ren, t[0]) != 0:
                return False
            self._cache_key = key
            if clear:                                     # fondo transparente (para las tarjetas sueltas)
                sdl2.SDL_SetRenderDrawColor(self.ren, 0, 0, 0, 0)
                sdl2.SDL_RenderClear(self.ren)
                self._color = None
            return True
        except Exception as e:
            self.log("cache: %r" % (e,))
            return False

    def end_cache(self):
        sdl2.SDL_SetRenderTarget(self.ren, None)
        self._valid.add(self._cache_key)

    def abort_cache(self):
        try:
            sdl2.SDL_SetRenderTarget(self.ren, None)
        except Exception:
            pass

    def cache_ok(self, key):
        return key in getattr(self, "_valid", ()) and ("cache", key) in self._tex

    def blit_cache(self, key):
        sdl2.SDL_RenderCopy(self.ren, self._tex[("cache", key)][0], None, None)

    def blit_part(self, key, sx, sy, sw, sh, dx, dy, dw, dh):
        """Copia un trozo del cache a otro lugar / tamano (zoom, elevar)."""
        sdl2.SDL_RenderCopy(self.ren, self._tex[("cache", key)][0],
                            sdl2.SDL_Rect(int(sx), int(sy), int(sw), int(sh)),
                            sdl2.SDL_Rect(int(dx), int(dy), int(dw), int(dh)))

    def dim(self, x, y, w, h, alpha):
        """Oscurece un rectangulo (negro con transparencia)."""
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_SetRenderDrawColor(self.ren, 0, 0, 0, int(alpha))
        sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_NONE)
        self._color = None

    def clip(self, x, y, w, h):
        sdl2.SDL_RenderSetClipRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))

    def unclip(self):
        sdl2.SDL_RenderSetClipRect(self.ren, None)

    def glow(self, x, y, w, h, alpha):
        """Aclara un rectangulo (blanco con transparencia)."""
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_SetRenderDrawColor(self.ren, 255, 255, 255, int(alpha))
        sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_NONE)
        self._color = None

    def _asset(self, fname):
        """Textura ya calculada (img/<fname>.rgba): sin bucles en Python, no hay tirones. None si no existe."""
        key = ("asset", fname)
        if key in self._tex:
            t = self._tex[key]
            return t if t[0] else None
        try:
            with open(os.path.join(os.path.dirname(self.font_dir), "img", fname), "rb") as f:
                raw = f.read()
            w, h = struct.unpack("<II", raw[:8])
            tex = sdl2.SDL_CreateTexture(self.ren, sdl2.SDL_PIXELFORMAT_ABGR8888, sdl2.SDL_TEXTUREACCESS_STATIC, w, h)
            if not tex:
                raise RuntimeError("textura")
            sdl2.SDL_UpdateTexture(tex, None, raw[8:8 + w * h * 4], w * 4)
            sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
            self._tex[key] = (tex, w, h)
            return self._tex[key]
        except Exception:
            self._tex[key] = (None, 0, 0)
            return None

    def _alpha_tex(self, key, W, H, rgb, alpha_fn, sym):
        """Textura RGBA de un solo color con transparencia calculada por alpha_fn(dx, dy)."""
        t = self._tex.get(key)
        if t is not None:
            return t
        buf = bytearray(W * H * 4)
        r, gg, b = rgb
        if sym:                                           # simetrica: se calcula un cuarto y se refleja
            hw, hh = W // 2, H // 2
            for py in range(hh + 1):
                for px in range(hw + 1):
                    a = int(alpha_fn(px + 0.5 * (1 - W % 2), py + 0.5 * (1 - H % 2)) * 255)
                    if a <= 0:
                        continue
                    for X in {hw + px, hw - px - 1 + (W % 2)}:
                        for Y in {hh + py, hh - py - 1 + (H % 2)}:
                            if 0 <= X < W and 0 <= Y < H:
                                o = (Y * W + X) * 4
                                buf[o], buf[o + 1], buf[o + 2], buf[o + 3] = r, gg, b, a
        else:
            for py in range(H):
                for px in range(W):
                    a = int(alpha_fn(px, py) * 255)
                    if a > 0:
                        o = (py * W + px) * 4
                        buf[o], buf[o + 1], buf[o + 2], buf[o + 3] = r, gg, b, a
        tex = sdl2.SDL_CreateTexture(self.ren, sdl2.SDL_PIXELFORMAT_ABGR8888, sdl2.SDL_TEXTUREACCESS_STATIC, W, H)
        if not tex:
            return None
        sdl2.SDL_UpdateTexture(tex, None, bytes(buf), W * 4)
        sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
        t = (tex, W, H)
        self._tex[key] = t
        return t

    SHADOW_B = 10

    def shadow(self, cx, cy, w, h, scale, level, radius=4):
        """Sombra suave bajo una tarjeta de w x h centrada en (cx, cy)."""
        import math
        B = self.SHADOW_B
        W, H = w + 2 * B, h + 2 * B

        def fn(px, py):                                   # px, py: distancia al centro (cuarto de textura)
            qx = px - (w / 2.0 - radius)
            qy = py - (h / 2.0 - radius)
            d = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - radius
            if d <= 0:
                return 0.55
            if d >= B:
                return 0.0
            return 0.55 * (1 - d / float(B)) ** 2
        t = self._asset("fx_shadow_%dx%d.rgba" % (w, h)) or self._alpha_tex(("shadow", w, h), W, H, (0, 0, 0), fn, True)
        if t is None:
            return
        sdl2.SDL_SetTextureAlphaMod(t[0], max(0, min(255, int(255 * level))))
        dw, dh = int(W * scale), int(H * scale)
        sdl2.SDL_RenderCopy(self.ren, t[0], None, sdl2.SDL_Rect(int(cx - dw / 2), int(cy - dh / 2), dw, dh))

    def shine(self, x, y, w, h, pos, level):
        """Franja de brillo diagonal que cruza el rectangulo (x, y, w, h); pos = avance (-60 .. w + 0.7h + 60)."""
        import math
        BW = int(0.7 * h) + 70
        uc = 30 + 0.7 * h

        def fn(px, py):
            u = px + 0.7 * py
            return math.exp(-((u - uc) / 22.0) ** 2) * 0.37
        t = self._asset("fx_shine_%d.rgba" % h) or self._alpha_tex(("shine", h), BW, int(h), (255, 255, 255), fn, False)
        if t is None:
            return
        sdl2.SDL_SetTextureAlphaMod(t[0], max(0, min(255, int(255 * level))))
        sdl2.SDL_RenderSetClipRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))
        sdl2.SDL_RenderCopy(self.ren, t[0], None, sdl2.SDL_Rect(int(x + pos - uc), int(y), BW, int(h)))
        sdl2.SDL_RenderSetClipRect(self.ren, None)

    def dot(self, cx, cy, level):
        """Punto de luz blanco (9 x 9) con borde suave."""
        import math

        def fn(px, py):
            return max(0.0, 1 - math.hypot(px, py) / 4.5) ** 0.6
        t = self._asset("fx_dot.rgba") or self._alpha_tex(("dot",), 10, 10, (255, 255, 255), fn, True)
        if t is None:
            return
        sdl2.SDL_SetTextureAlphaMod(t[0], max(0, min(255, int(255 * level))))
        sdl2.SDL_RenderCopy(self.ren, t[0], None, sdl2.SDL_Rect(int(cx - 5), int(cy - 5), 10, 10))

    def rgb_frame(self, data, w, h, x, y):
        """Dibuja un cuadro RGB24 (bytes) en (x, y): las vistas previas animadas."""
        t = self._tex.get(("pv", w, h))
        full = (w == self.w and h == self.h)
        if t is None:
            if full:                                   # cuadro de video: escalado suave (modo Estirar)
                sdl2.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
            tex = sdl2.SDL_CreateTexture(self.ren, sdl2.SDL_PIXELFORMAT_RGB24, sdl2.SDL_TEXTUREACCESS_STREAMING, w, h)
            if full:
                sdl2.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"0")
            if not tex:
                return False
            t = (tex, w, h)
            self._tex[("pv", w, h)] = t
        sdl2.SDL_UpdateTexture(t[0], None, data, w * 3)
        vc = getattr(self, "vcrop", None) if full else None      # parte del cuadro que se muestra (Zoom, Estirar)
        vd = getattr(self, "vdst", None) if full else None       # donde se dibuja (Normal: con barras negras)
        src = sdl2.SDL_Rect(vc[0], vc[1], vc[2] - vc[0], vc[3] - vc[1]) if vc else None
        if vd:
            self._set((0, 0, 0))
            if vd[0] > 0:
                sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(0, 0, vd[0], h))
                sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(vd[2], 0, w - vd[2], h))
            if vd[1] > 0:
                sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(0, 0, w, vd[1]))
                sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(0, vd[3], w, h - vd[3]))
            dst = sdl2.SDL_Rect(vd[0], vd[1], vd[2] - vd[0], vd[3] - vd[1])
        else:
            dst = sdl2.SDL_Rect(int(x), int(y), w, h)
        if full:
            gk = (vc, vd)
            if gk != getattr(self, "_geom_log", None):          # una linea cuando cambia lo que realmente se dibuja
                self._geom_log = gk
                self.log("video: se dibuja origen %s destino %s" % (vc, vd))
        sdl2.SDL_RenderCopy(self.ren, t[0], src, dst)
        return True

    # ---- texto ---------------------------------------------------------
    def _font(self, size, bold, face=None):
        key = (size, bold, face)
        f = self._fonts.get(key)
        if f is None:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            if face == "title" and os.path.exists(os.path.join(self.font_dir, "Inter-Bold.otf")):
                name = "Inter-Bold.otf"
            elif face and face.endswith((".ttf", ".otf")) and os.path.exists(os.path.join(self.font_dir, face)):
                name = face                      # tipografia propia del reloj (estilos de Apariencia)
            path = os.path.join(self.font_dir, name).encode()
            f = ttf.TTF_OpenFont(path, size)
            if not f:
                raise RuntimeError("TTF_OpenFont %s: %s" % (path, sdl2.SDL_GetError()))
            self._fonts[key] = f
        return f

    def text_w(self, s, size, bold=False, face=None):
        w, h = ctypes.c_int(), ctypes.c_int()
        ttf.TTF_SizeUTF8(self._font(size, bold, face), s.encode("utf-8"), ctypes.byref(w), ctypes.byref(h))
        return w.value

    def text_h(self, s, size, bold=False, face=None):
        w, h = ctypes.c_int(), ctypes.c_int()
        ttf.TTF_SizeUTF8(self._font(size, bold, face), (s or " ").encode("utf-8"), ctypes.byref(w), ctypes.byref(h))
        return h.value

    def text(self, s, x, y, size, c, align="l", bold=False, face=None):
        if not s:
            return
        key = (s, size, bold, tuple(c), face)
        t = self._tex.get(key)
        if t is None:
            if len(self._tex) > 400:
                keep = {}
                for k, v in self._tex.items():
                    if k[0] in self._SPECIAL:
                        keep[k] = v
                    else:
                        sdl2.SDL_DestroyTexture(v[0])
                self._tex = keep
            col = sdl2.SDL_Color(c[0], c[1], c[2], 255)
            surf = ttf.TTF_RenderUTF8_Blended(self._font(size, bold, face), s.encode("utf-8"), col)
            if not surf:
                return
            tex = sdl2.SDL_CreateTextureFromSurface(self.ren, surf)
            tw, th = surf.contents.w, surf.contents.h
            sdl2.SDL_FreeSurface(surf)
            if not tex:
                return
            sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
            t = (tex, tw, th)
            self._tex[key] = t
        tex, tw, th = t
        if align == "c":
            x -= tw // 2
        elif align == "r":
            x -= tw
        sdl2.SDL_RenderCopy(self.ren, tex, None, sdl2.SDL_Rect(int(x), int(y), tw, th))
