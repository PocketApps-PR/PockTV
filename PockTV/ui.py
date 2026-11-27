"""Pantallas: inicio con mosaicos (TV en vivo / Peliculas / Series / Favoritos), listas con
busqueda por nombre (teclado en pantalla) y favoritos. Pensado para 640x480 (Miyoo Flip).
No depende de pygame: dibuja con un objeto gfx.
"""
import bisect
import math
import os
import re
import struct
import time
import zlib

import icons
import tracks
from core import split_by_cat, filter_entries, langs_present, norm
import clocks
from i18n import T, lang_name, date_text, get_lang, set_lang, NATIVE, UI_LANGS

BG_TOP = (12, 20, 38)
BG_BOT = (40, 24, 28)
WHITE = (255, 255, 255)
SOFT = (232, 236, 246)
GRAY = (140, 152, 172)
LINE = (30, 42, 64)
KEY_BG = (34, 46, 72)
WARN = (255, 170, 120)
GOLD = (255, 205, 60)
SET_C1, SET_C2 = (110, 70, 210), (40, 140, 230)

TILE = {
    "TV": {"c1": (0, 214, 152), "c2": (60, 80, 235), "horizontal": False},
    "PELIS": {"c1": (170, 60, 190), "c2": (30, 160, 230), "horizontal": True},
    "SERIES": {"c1": (245, 10, 80), "c2": (255, 160, 30), "horizontal": True},
    "FAV": {"c1": (250, 190, 40), "c2": (235, 70, 110), "horizontal": True},
    "ALL": {"c1": (30, 160, 230), "c2": (140, 60, 200), "horizontal": True},    # busqueda maestra
}
HOME_ORDER = ("TV", "PELIS", "SERIES", "FAV")
TILE_RECT = {
    "TV": (24, 108, 292, 226),
    "PELIS": (332, 108, 284, 108),
    "SERIES": (332, 226, 284, 108),
    "FAV": (24, 346, 292, 62),
}
# Iconos de abajo a la derecha (centrados bajo Series): actualizar, cambiar de lista, ajustes
ICON_ORDER = ("UPD", "LISTS", "SET")
ICON_X = {"UPD": 379, "LISTS": 474, "SET": 569}
ICON_Y = 377          # misma linea central que la barra de Favoritos (346..408)
TILE_RADIUS = 4
SEARCH_Y = 49          # el centro del circulo de la lupa queda en y=45
TILE_ICON = 52          # tamano del icono de TV / Peliculas / Series (igual en los tres)
TILE_FONT = 22          # tamano de letra del titulo (igual en los tres)
TILE_BLOCK = TILE_ICON + 4 + TILE_FONT + 3 + 13   # alto del bloque icono + titulo + contador
BOT_ICON = 40
ICON_KEY = {"UPD": "icon_update", "LISTS": "icon_lists", "SET": "icon_settings"}
# Movimiento entre elementos del inicio: (actual, direccion) -> nuevo
HOME_MOVES = {
    ("SEARCH", "down"): "TV",
    ("SEARCH", "left"): "TV",
    ("SEARCH", "right"): "PELIS",
    ("TV", "up"): "SEARCH",
    ("PELIS", "up"): "SEARCH",
    ("TV", "right"): "PELIS",
    ("TV", "down"): "FAV",
    ("PELIS", "left"): "TV",
    ("PELIS", "down"): "SERIES",
    ("SERIES", "left"): "TV",
    ("SERIES", "up"): "PELIS",
    ("SERIES", "down"): "LISTS",
    ("FAV", "up"): "TV",
    ("FAV", "right"): "UPD",
    ("UPD", "left"): "FAV",
    ("UPD", "right"): "LISTS",
    ("UPD", "up"): "SERIES",
    ("LISTS", "left"): "UPD",
    ("LISTS", "right"): "SET",
    ("LISTS", "up"): "SERIES",
    ("SET", "left"): "LISTS",
    ("SET", "up"): "SERIES",
}

ROW_H = 38
LIST_Y = 76
VISIBLE = 9
SPLIT = ("TV", "PELIS", "SERIES", "FAV")  # listas de dos columnas: categorias | canales (Favoritos: categorias favoritas | contenido)
BL1, BL2 = (0, 190, 240), (30, 110, 235)       # marcador de categorias (azul)
OR1, OR2 = (255, 170, 30), (255, 110, 20)   # selector naranja de la columna de canales
GX, GW = 12, 214                           # columna de categorias
HX, HW = 234, 370                          # columna de canales (ocupa todo el ancho que queda)
MAX_QUERY = 30
GR1, GR2 = (84, 90, 108), (54, 59, 76)        # marcador gris oscuro (columna de episodios)
SER_GEO = {"g": (12, 204), "s": (224, 220), "c": (452, 152)}     # Series: categorias | series | episodios
STD_GEO = {"g": (GX, GW), "c": (HX, HW)}                           # TV y Peliculas: categorias | contenido
_EP_RE = re.compile(r"[\s\-\u2013:._\[\(]*\bs(\d{1,3}) ?e(\d{1,4})\b[\]\)]?", re.I)


def series_parts(name):
    """'Show S01E02 - Titulo' -> ('Show', 1, 2, 'Titulo'); sin temporada/episodio -> (nombre, None, None, '')."""
    m = _EP_RE.search(name)
    if not m:
        return name.strip(), None, None, ""
    title = name[:m.start()].strip(" -\u2013:._[]()")
    rest = name[m.end():].strip(" -\u2013:._[]()")
    return (title or name.strip()), int(m.group(1)), int(m.group(2)), rest

# Teclado en pantalla
# Teclas: una letra/numero/simbolo, o "shift", "del", "sym" (?123), "left", "right", "space", "go" (buscar, lupa)
KB_LETTERS = [list("1234567890"), list("qwertyuiop"), list("asdfghjklñ"),
              ["shift", "z", "x", "c", "v", "b", "n", "m", "/", "del"],
              ["sym", "left", "right", "space", "go"]]
KB_SYMBOLS = [list("1234567890"), list("@#$%&*-+()"), list("!?\"':;,._~"),
              list("=<>[]{}|") + ["/", "del"],
              ["sym", "left", "right", "space", "go"]]
KB_ROWS = KB_LETTERS
ROW4_COL = [0, 1, 2, 3, 7]              # columna donde empieza cada tecla de la ultima fila
ROW4_SPAN = [1, 1, 1, 4, 3]             # y cuantas columnas ocupa (barra: bajo c-v-b-n; buscar: bajo m / borrar)
ROW4_UP = [0, 1, 2, 5, 8]               # a que tecla de arriba sube cada una


KEY_W, KEY_H, KEY_GAP = 54, 46, 6
KB_Y = 138


def star_points(cx, cy, r):
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = math.radians(-90 + i * 36)
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


def letter_of(e):
    for ch in e.nname:
        if ch.isalnum():
            return ch.upper() if ch.isalpha() else "#"
    return "#"


def sort_key(e):
    s = e.nname.lstrip()
    k = "".join(ch for ch in s if ch.isalnum())
    return (0 if not k[:1].isalpha() else 1, k, s)


class UI(object):
    def __init__(self, gfx, entries, list_name="lista.m3u", notice="", favs=None, settings=None, sources=None):
        self.g = gfx
        self._fit_cache = {}
        self.settings = settings if settings is not None else {}
        self.sources = sources or []          # [{"id","name"}]
        self.list_name = list_name
        self.notice = notice
        self.favs = set(favs) if favs else set()
        self.state = "home"          # home / list / kbd / settings / setcat / pick / lists
        self.sel = "TV"
        self.cat = "TV"
        self.query = {}              # busqueda activa por categoria
        self.idx = 0
        self.top = 0
        self.view = []
        self.col = 0                 # 0 = categorias, 1 = canales (en Series: 1 = series, 2 = episodios)
        self.gquery = {}             # busqueda de categorias
        self.gidx = 0
        self.gtop = 0
        self.gname = None            # categoria elegida (azul)
        self.sname = None            # Series: serie elegida (naranja)
        self.sidx = self.stop = 0    # Series: cursor y desplazamiento de la columna de series
        self.sq = ""                  # Series: busqueda dentro de la columna de series
        self._mq_t0 = 0.0
        self._ic_last = None
        self.moving = False
        self._ic_t0 = 0.0
        self.kb_target = "chan"
        # teclado
        self.kb_text = ""
        self.kb_row = 1
        self.kb_col = 0
        self.kb_shift = 0
        self.kb_sym = False
        self.kb_pos = len(self.kb_text)
        # menus (ajustes / listas)
        self.online = False
        self.aud_sel = []
        self.wifi_level = None      # 0..3 (rayitas encendidas), -1 sin wifi, None desconocido
        self.m_idx = 0
        self.confirm_del = None     # id de la lista que se pregunta borrar
        self.conf_sel = 1           # 0 = Si, 1 = No
        self.set_path = []          # ruta dentro de Ajustes, p.ej. ["audio", "movies", "lang"]
        self.set_idx = [0]          # fila elegida en cada nivel
        self.sel_t = 0.0            # cuando cambio la fila elegida (para el letrero que se desplaza)
        self.anim = False
        self._mq_t = {}                  # letreros en marcha: clave -> momento de inicio
        self._mq_seen = set()
        self._mq_items = []              # textos largos de la pantalla actual (se dibujan encima de la parte fija)
        self._mq_defer = None
        self._mq_scr = None
        self._pv_pending = None
        self._scr_sig = {}
        self.mq_on = False
        self._sx = 0
        self.fx_t0 = {}              # momento en que se eligio cada tarjeta
        self.lt = {}                 # nivel de seleccion de cada tarjeta (0..1) para los efectos
        self._fx_last = None
        self._fx_broken = False
        self._perim = {}
        self._pv = {}                # vistas previas animadas ya cargadas
        self.pv_on = False
        self.confirm_quit = False
        self.zt = {}                 # zoom de los iconos de Home: clave -> [desde, hasta, t0]
        self.m_idx2 = 0
        self.set_cat = ""
        self.pick_key = ""
        self.p_idx = 0
        self.set_entries(entries, list_name)

    def set_entries(self, entries, list_name=None):
        self.entries = entries
        self.by_cat = split_by_cat(entries)
        self.gquery = {}
        if list_name is not None:
            self.list_name = list_name
        self._cache = {}
        if self.state in ("list", "kbd"):
            self.state = "home"

    # ---------- datos ----------
    def lang_ok(self, e):
        if e.cat != "TV":                 # el filtro de idioma es solo para TV en vivo
            return True
        cl = self.settings.get("content_lang", "all")
        if cl == "all" or e.lang == cl:
            return True
        return e.lang == "" and self.settings.get("show_unknown", True)

    def _home_dirty(self):
        """Obliga a rehacer el fondo guardado del inicio (hora y fecha van dentro de el)."""
        try:
            getattr(self.g, "_valid", set()).discard("home")
        except Exception:
            pass
        self._fx_last = None

    def invalidate(self):
        self._cache = {}
        if self.state == "list":
            self.refresh()

    # ----- favoritos: canales sueltos, categorias enteras y series (mismo conjunto guardado) -----
    def _gfav_key(self, cat, group):
        return "G|%s|%s" % (cat, group)

    def _sfav_key(self, cat, group, show):
        return "S|%s|%s|%s" % (cat, group, show)

    def _via_group(self, e):
        """El canal esta en favoritos porque su categoria (o su serie) lo esta."""
        fv = self.favs
        if self._gfav_key(e.cat, self._gkey(e)) in fv:
            return True
        return e.cat == "SERIES" and self._sfav_key(e.cat, self._gkey(e), series_parts(e.name)[0]) in fv

    def _is_fav(self, e):
        return e.fkey in self.favs or self._via_group(e)

    def _toggle_fav_key(self, key):
        if key in self.favs:
            self.favs.discard(key)
        else:
            self.favs.add(key)
        self._cache.pop("FAV", None)
        self._cache.pop("G_FAV", None)
        self._cache.pop("FL", None)
        if self.state == "list" and self.cat == "FAV":
            self.refresh()
        return ("save_favs", None)

    def base_items(self, cat):
        items = self._cache.get(cat)
        if items is None:
            if cat == "ALL":
                src = self.by_cat["TV"] + self.by_cat["PELIS"] + self.by_cat["SERIES"]
            else:
                src = self.entries if cat == "FAV" else self.by_cat[cat]
            items = [e for e in src if (cat != "FAV" or self._is_fav(e)) and self.lang_ok(e)]
            items.sort(key=sort_key)
            self._cache[cat] = items
        return items

    def _gkey(self, e):
        return (e.group or "").strip() or T("no_group")

    def groups_of(self, cat):
        """[(nombre, cantidad)] en el orden de la lista, ya filtradas por la busqueda de categorias."""
        ck = "G_" + cat
        g = self._cache.get(ck)
        if g is None and cat == "FAV":
            g = [(k, n) for k, n in self._fav_list()]
            self._cache[ck] = g
        elif g is None:
            order, cnt = [], {}
            for e in self.by_cat[cat]:
                if not self.lang_ok(e):
                    continue
                k = self._gkey(e)
                if k not in cnt:
                    cnt[k] = 0
                    order.append(k)
                cnt[k] += 1
            def gk(k):
                t = "".join(ch for ch in norm(k) if ch.isalnum())
                return (0 if not t[:1].isalpha() else 1, t, k)
            order.sort(key=gk)
            g = [(k, cnt[k]) for k in order]
            self._cache[ck] = g
        words = norm(self.gquery.get(cat, "")).split()
        if words:
            g = [x for x in g if all(w in norm(self._gdisp(x[0])) for w in words)]
        return g

    # ----- Favoritos: lista de categorias / series favoritas (cada una se abre y muestra su contenido) -----
    @staticmethod
    def _kparts(key):
        """'G|cat|grupo' / 'S|cat|grupo|serie' / 'C|cat<TAB>nombre' -> (tipo, categoria, nombre que se ve)."""
        if key.startswith("C|"):
            cat, _, name = key[2:].partition("\t")
            return "C", cat, name
        if key.startswith("S|"):
            p = key.split("|", 3)
            return "S", p[1], p[3] if len(p) > 3 else ""
        p = key.split("|", 2)
        return "G", p[1] if len(p) > 1 else "", p[2] if len(p) > 2 else key

    def _gdisp(self, key):
        """Nombre que se ve de una fila de la columna izquierda."""
        if self.cat != "FAV":
            return key
        return self._kparts(key)[2]

    def _gkind(self, key):
        return T("kind_" + self._kparts(key)[1])

    def _fav_list(self):
        """[(clave, cantidad)]: categorias ('G|cat|grupo'), series ('S|cat|grupo|serie') y canales sueltos ('C|fkey')."""
        res = self._cache.get("FL")
        if res is not None:                                  # se calcula una sola vez (el Home la consulta en cada cuadro)
            return res
        cnt = {}
        favs = self.favs
        gkeys = set(k for k in favs if k.startswith("G|"))
        skeys = set(k for k in favs if k.startswith("S|"))
        if favs:
            for e in self.entries:
                fk = e.fkey
                gk = "G|%s|%s" % (e.cat, self._gkey(e)) if gkeys else None
                hit_c = fk in favs
                hit_g = gk in gkeys if gk else False
                hit_s = None
                if skeys and e.cat == "SERIES":
                    sk = "S|%s|%s|%s" % (e.cat, self._gkey(e), series_parts(e.name)[0])
                    hit_s = sk if sk in skeys else None
                if not (hit_c or hit_g or hit_s) or not self.lang_ok(e):
                    continue
                if hit_c:
                    cnt["C|" + fk] = 1
                if hit_g:
                    cnt[gk] = cnt.get(gk, 0) + 1
                if hit_s:
                    cnt[hit_s] = cnt.get(hit_s, 0) + 1
        keys = sorted(cnt, key=lambda k: (norm(self._kparts(k)[2]), k))
        res = [(k, cnt[k]) for k in keys]
        self._cache["FL"] = res
        return res

    def _fav_items(self, key):
        out = []
        for e in self.entries:
            if not self.lang_ok(e):
                continue
            kd, kc, kn = self._kparts(key)
            if kd == "C":
                ok = False
            elif kd == "G":
                ok = e.cat == kc and self._gkey(e) == kn
            else:
                p = key.split("|", 3)
                ok = e.cat == kc and self._gkey(e) == p[2] and series_parts(e.name)[0] == kn
            if ok:
                out.append(e)
        if key.startswith("S|"):
            out.sort(key=lambda e: (series_parts(e.name)[1] or 0, series_parts(e.name)[2] or 0, e.nname))
        else:
            out.sort(key=sort_key)
        return out

    def _ser(self):
        return self.cat == "SERIES"

    def _geo(self):
        return SER_GEO if self._ser() else STD_GEO

    def _last_col(self):
        return 2 if self._ser() else 1

    def _row_label(self, e):
        if self._ser() or (self.cat == "FAV" and str(self.gname).startswith("S|")):
            return self._ep_label(e)
        return e.name

    def _ep_label(self, e):
        t, sn, ep, rest = series_parts(e.name)
        if sn is None:
            return e.name
        return "T%d \u00b7 E%02d" % (sn, ep) + ("   " + rest if rest else "")

    def _group_items(self):
        if self.cat == "FAV":
            return self._fav_items(self.gname)
        return [e for e in self.base_items(self.cat) if self._gkey(e) == self.gname]

    def shows_of(self):
        """Series de la categoria elegida: [(titulo, episodios)] en orden alfabetico, filtradas por su busqueda."""
        ck = "S_" + str(self.gname)
        sh = self._cache.get(ck)
        if sh is None:
            cnt, order = {}, []
            for e in self._group_items():
                t = series_parts(e.name)[0]
                if t not in cnt:
                    cnt[t] = 0
                    order.append(t)
                cnt[t] += 1
            order.sort(key=lambda k: (norm(k), k))
            sh = [(k, cnt[k]) for k in order]
            self._cache[ck] = sh
        words = norm(self.sq).split()
        if words:
            sh = [x for x in sh if all(w in norm(x[0]) for w in words)]
        return sh

    def _split_refresh(self, keep_current=False):
        cur = self.view[self.idx] if (keep_current and self.view and self.idx < len(self.view)) else None
        gl = self.groups_of(self.cat)
        pool = [x[0] for x in gl if not (self.cat == "FAV" and x[0].startswith("C|"))]
        if pool and self.gname not in pool:
            self.gname = pool[0]
        if not pool:
            self.gname = None
        self.gidx = max(0, min(self.gidx, len(gl) - 1))
        self._gscroll()
        if self.gname is None:
            self.view = []
        elif self.cat == "FAV":
            self.view = filter_entries(self._group_items(), self.query.get(self.cat, ""))
        elif self._ser():
            sh = self.shows_of()
            if sh and (self.sname is None or self.sname not in [x[0] for x in sh]):
                self.sname = sh[0][0]
            if not sh:
                self.sname = None
            self.sidx = max(0, min(self.sidx, len(sh) - 1))
            self._sscroll()
            items = [e for e in self._group_items() if series_parts(e.name)[0] == self.sname] if self.sname else []
            items.sort(key=lambda e: (series_parts(e.name)[1] or 0, series_parts(e.name)[2] or 0, e.nname))
            self.view = filter_entries(items, self.query.get(self.cat, ""))
        else:
            items = self._group_items()
            self.view = filter_entries(items, self.query.get(self.cat, ""))
        if cur is not None and cur in self.view:
            self.idx = self.view.index(cur)
        else:
            self.idx = min(self.idx, max(0, len(self.view) - 1))
        self._scroll()

    def _sscroll(self):
        if self.sidx < self.stop:
            self.stop = self.sidx
        if self.sidx >= self.stop + VISIBLE:
            self.stop = self.sidx - VISIBLE + 1
        self.stop = max(0, self.stop)

    def _gscroll(self):
        if self.gidx < self.gtop:
            self.gtop = self.gidx
        if self.gidx >= self.gtop + VISIBLE:
            self.gtop = self.gidx - VISIBLE + 1
        self.gtop = max(0, self.gtop)

    def refresh(self, keep_current=False):
        if self.cat in SPLIT:
            return self._split_refresh(keep_current)
        cur = self.view[self.idx] if (keep_current and self.view and self.idx < len(self.view)) else None
        if self.cat == "ALL" and not self.query.get("ALL"):
            self.view = []
        else:
            self.view = filter_entries(self.base_items(self.cat), self.query.get(self.cat, ""))
        if cur is not None and cur in self.view:
            self.idx = self.view.index(cur)
        else:
            self.idx = min(self.idx, max(0, len(self.view) - 1))
        self._scroll()

    def count(self, cat):
        if cat == "FAV":
            return len(self._fav_list())
        return len(self.base_items(cat))

    # ---------- entrada ----------
    def handle(self, action):
        """action: up/down/left/right/ok/back/pgup/pgdn/fav/search.
        Devuelve ('play', entry), ('save_favs', None), ('quit', None), ('settings_changed', None),
        ('switch_list', id), ('update_lists', None) o None."""
        if action == "home":                 # boton Menu de la consola: siempre al inicio
            self.state = "home"
            self.notice = ""
            return None
        if self.state == "home":
            return self._handle_home(action)
        if self.state in ("list", "kbd") and False:
            pass
        if self.state == "kbd":
            return self._handle_kbd(action)
        if self.state == "support":
            import updater
            busy = updater.ST["status"] in ("downloading", "installing")
            if action == "back" and not busy:
                self.state = "settings"
                self.sel_t = time.time()
            elif action == "ok":
                s_ = updater.ST["status"]
                if s_ in ("idle", "error", "ok"):
                    updater.check()
                elif s_ == "new":
                    updater.install()
                elif s_ == "done":
                    self.state = "settings"
            return None
        if self.state in ("settings", "lists"):
            return self._handle_menu(action)
        return self._handle_list(action)

    def _handle_home(self, action):
        if self.confirm_quit:                                  # pregunta: quieres salir?  Si / No
            if action in ("left", "right", "up", "down"):
                self.conf_sel = 1 - self.conf_sel
            elif action == "back":                             # volver a pulsar B = salir
                return ("quit", None)
            elif action == "ok":
                if self.conf_sel == 0:
                    return ("quit", None)
                self.confirm_quit = False
            return None
        if action == "back":
            self.confirm_quit = True
            self.conf_sel = 1                                  # por defecto "No"
            return None
        if action in ("up", "down", "left", "right"):
            if not any(k[0] == self.sel for k in HOME_MOVES):    # seleccion perdida (p. ej. tras la pausa): se recupera
                self.sel = "TV"
                self._ic_last = None
            nxt = HOME_MOVES.get((self.sel, action))
            if nxt:
                self.sel = nxt
        elif action in ("ok", "search"):
            if action == "search":                    # Y en Home: Busqueda Maestra
                self.sel = "SEARCH"
            if self.sel == "SEARCH":
                self.cat = "ALL"
                self.query["ALL"] = ""
                self.kb_text = ""
                self.kb_row = 1
                self.kb_col = 0
                self.kb_shift = 0
                self.kb_sym = False
                self.kb_pos = len(self.kb_text)
                self.view = []
                self.idx = self.top = 0
                self.state = "kbd"
                return None
            if self.sel == "UPD":
                return ("update_lists", None)
            if self.sel == "LISTS":
                self.state = "lists"
                self.m_idx = 0
                for i, sc in enumerate(self.sources):
                    if sc["id"] == self.settings.get("source", "main"):
                        self.m_idx = i
                return None
            if self.sel == "SET":
                self.state = "settings"
                self.m_idx = 0
                self.set_path = []
                self.set_idx = [0]
                self.sel_t = time.time()
                return None
            self.cat = self.sel
            self.state = "list"
            self.idx = 0
            self.top = 0
            self.col = 0
            self.gidx = self.gtop = 0
            self.gname = None
            self.sname = None
            self.sidx = self.stop = 0
            self.sq = ""
            self.gquery[self.cat] = ""
            self.query[self.cat] = ""
            self.refresh()
        return None

    # ----- menus de ajustes -----
    # Arbol: Idioma de Interfaz | Reloj > Formato | Video > Modo | Audio > (TV, Peliculas, Series) | Subtitulos > (Peliculas, Series)
    SINGLE = {("lang",): "ui_lang", ("sound",): "snd_style", ("clock", "fmt"): "fmt", ("clock", "date"): "datefmt", ("video", "mode"): "mode",
              ("audio", "tv", "chan"): "chan", ("audio", "tv", "unk"): "unk",
              ("look", "cards"): "cards", ("look", "icons"): "look_icons",
              ("look", "clockdate"): "look_cd", ("look", "fonts", "style"): "look_fonts"}
    FX_CODES = ("default", "A", "B", "C", "D", "E")
    MULTI = {("audio", "movies", "lang"): ("aud_movies", 4), ("audio", "series", "lang"): ("aud_series", 4),
             ("subs", "movies", "lang"): ("sub_movies", 3), ("subs", "series", "lang"): ("sub_series", 3)}
    PRIO_DEFAULT = {"aud_movies": ["lat", "cas", "spa", "eng"], "aud_series": ["lat", "cas", "spa", "eng"],
                    "sub_movies": [], "sub_series": []}

    def _prio(self, key):
        lst = self.settings.get(key)
        if lst is None:
            lst = self.PRIO_DEFAULT[key]
        return [c for c in lst if c not in ("all", "none")]

    def _prio_text(self, key):
        lst = self._prio(key)
        if not lst and key.startswith("sub_"):
            return T("sub_off")
        return " > ".join(tracks.name_of(c, get_lang()) for c in lst) if lst else T("all")

    def _label(self, path):
        """Nombre mostrado de un nodo del arbol (para titulos)."""
        p = tuple(path)
        if not p:
            return T("settings")
        k = p[-1]
        if len(p) == 1:
            return T("cat_" + k)
        if p[0] in ("audio", "subs") and len(p) == 2:
            return T({"tv": "tile_TV", "movies": "tile_PELIS", "series": "tile_SERIES"}[k])
        names = {("clock", "fmt"): "row_clock", ("clock", "date"): "row_date", ("video", "mode"): "row_video",
                 ("look", "cards"): "look_cards", ("look", "icons"): "look_icons",
                 ("look", "clockdate"): "look_clock", ("look", "logo"): "look_logo", ("look", "fonts"): "look_fonts", ("look", "fonts", "style"): "sf_row",
                 ("look", "logo", "per"): "logo_per", ("look", "logo", "per", "font"): "lg_font",
                 ("look", "logo", "per", "icon"): "lg_icon",
                 ("audio", "tv", "chan"): "row_channels", ("audio", "tv", "unk"): "row_unknown"}
        if p in names:
            return T(names[p])
        return T("row_lang_movies" if p[1] == "movies" else "row_lang_series")

    def _title(self):
        parts = [self._label(self.set_path[:i + 1]) for i in range(len(self.set_path))]
        return " › ".join(parts) if parts else T("settings")

    DATE_CODES = ("default", "A", "B", "C", "D", "E")

    def _date_code(self):
        c = self.settings.get("date_fmt", "default")
        return c if c in self.DATE_CODES else "default"

    def _today(self, code):
        t = time.localtime()
        return date_text(t.tm_wday, t.tm_mday, t.tm_mon, t.tm_year, code)

    def _menu_rows(self, path):
        """Filas de un menu, en el orden que el usuario eligio (menu_order)."""
        rows = self._menu_rows_raw(path)
        order = (self.settings.get("menu_order") or {}).get("/".join(path))
        if order:
            pos = {k: i for i, k in enumerate(order)}
            rows = sorted(rows, key=lambda r: pos.get(r[0], 999))
        return rows

    def _menu_rows_raw(self, path):
        st = self.settings
        p = tuple(path)
        if p == ():
            return [(k, T("cat_" + k), "") for k in ("lang", "clock", "video", "audio", "subs", "look", "sound", "support")]
        if p == ("look",):
            return [(k, T(n), "") for k, n in (("cards", "look_cards"), ("icons", "look_icons"),
                                               ("clockdate", "look_clock"), ("logo", "look_logo"),
                                               ("fonts", "look_fonts"))]
        if p == ("look", "logo"):
            return [("style", T("look_logo"), T("lg_" + self._logo_style())),
                    ("size", T("lg_size"), str(self._logo_size())),
                    ("txt", T("logo_per"), self._logo_text())]
        if p == ("look", "fonts"):
            return [("style", T("sf_row"), T("sf_" + self._sec_style())),
                    ("size", T("sf_size"), str(self._sec_size()))]
        if p == ("clock",):
            return [("fmt", T("row_clock"), T("clock12") if st.get("clock") == "12" else T("clock24")),
                    ("date", T("row_date"), self._today(self._date_code())),
                    ("dsize", T("row_dsize"), str(self._date_size()))]
        if p == ("video",):
            return [("mode", T("row_video"), T("video_" + st.get("video", "normal")))]
        if p in (("audio",), ("subs",)):
            return [("tv", T("tile_TV"), "")] * (p == ("audio",)) + [("movies", T("tile_PELIS"), ""),
                                                                      ("series", T("tile_SERIES"), "")]
        if p == ("audio", "tv"):
            cl = st.get("content_lang", "all")
            return [("chan", T("row_channels"), T("all") if cl == "all" else lang_name(cl)),
                    ("unk", T("row_unknown"), T("yes") if st.get("show_unknown", True) else T("no"))]
        kind = ("aud_" if p[0] == "audio" else "sub_") + p[1]
        return [("lang", T("row_lang_movies" if p[1] == "movies" else "row_lang_series"), self._prio_text(kind))]

    def _kind(self, path):
        p = tuple(path)
        if p in self.SINGLE:
            return "single"
        if p in self.MULTI:
            return "multi"
        return "menu"

    def _options(self, key):
        """[(valor, texto, descripcion)] de una opcion de eleccion unica."""
        st = self.settings
        if key == "ui_lang":
            return [(c, NATIVE.get(c, c), "") for c in UI_LANGS]
        if key == "chan":
            tv = self.by_cat["TV"]
            counts = langs_present(tv)
            out = [("all", T("all"), "%d" % len(tv))]
            codes = sorted([c for c in counts if c], key=lambda c: -counts[c])
            cur = st.get("content_lang", "all")
            if cur != "all" and cur not in codes:
                codes.append(cur)
            for c in codes:
                out.append((c, lang_name(c), "%d" % counts.get(c, 0)))
            return out
        if key == "unk":
            return [(True, T("yes"), ""), (False, T("no"), "")]
        if key == "cards":
            return [(c, T("fx_" + c), "") for c in self.FX_CODES]
        if key == "datefmt":
            return [(c, self._today(c), "") for c in self.DATE_CODES]
        if key == "look_icons":
            return [(c, T("fx_default") if c == "default" else T("ic_" + c), "") for c in self.ICON_FX]
        if key == "look_cd":
            return [(c, T("fx_default") if c == "default" else T("ck_" + c), "") for c in clocks.CODES]
        if key == "look_logo":
            return [("def", self.LOGO_DEFAULT, ""), ("per", T("logo_per"), self._logo_text())]
        if key == "lg_icon":
            return [(c, T("logo_" + c), "") for c in ("1", "2", "3")]
        if key in ("look_fonts", "sf_row"):
            return [(c, T("sf_" + c), "") for c in self.SEC_CODES]
        if key == "snd_style":
            return [(c, T("snd_" + c), "") for c in ("off", "suave", "cristal", "madera", "marimba")]
        if key == "lg_font":
            return [(c, T("lg_f_" + c), "") for c in "ABCDE"]
        if key == "fmt":
            return [("12", T("clock12"), "1:45 " + T("pm")), ("24", T("clock24"), "13:45")]
        return [(m, T("video_" + m), T("video_%s_d" % m)) for m in ("normal", "estirar", "auto", "zoom")]

    def _current(self, key):
        st = self.settings
        return {"ui_lang": get_lang(), "chan": st.get("content_lang", "all"),
                "unk": st.get("show_unknown", True), "fmt": st.get("clock", "12"),
                "mode": st.get("video", "normal"), "cards": st.get("tile_fx", "default"),
                "look_icons": self._icon_mode(), "datefmt": self._date_code(), "look_cd": self._clock_style(), "look_fonts": self._sec_style(), "sf_row": self._sec_style(),
                "snd_style": st.get("snd", "suave")}[key]

    def _apply(self, key, val):
        st = self.settings
        if key == "ui_lang":
            st["lang"] = val
            set_lang(val)
        elif key == "chan":
            st["content_lang"] = val
            self.invalidate()
        elif key == "unk":
            st["show_unknown"] = val
            self.invalidate()
        elif key == "fmt":
            st["clock"] = val
            self._home_dirty()
        elif key == "mode":
            st["video"] = val
        elif key == "cards":
            st["tile_fx"] = val
            self._fx_last = None
        elif key == "datefmt":
            st["date_fmt"] = val
            self._home_dirty()
        elif key == "look_cd":
            st["clock_style"] = val
            self._home_dirty()
        elif key == "look_logo":
            if val == "def":
                st["logo_text"] = ""
                self._home_dirty()
        elif key == "lg_font":
            st["logo_font"] = val
            self._home_dirty()
        elif key == "lg_icon":
            st["logo_icon"] = val
            self._home_dirty()
        elif key == "snd_style":
            st["snd"] = val
        elif key == "look_fonts":
            st["sec_font"] = val
            self._split_last = None
        elif key == "look_icons":
            st["icon_fx"] = val
            self._ic_t0 = time.time()

    def _multi_options(self):
        if self.set_path and self.set_path[0] == "subs":          # subtitulos: la lista vacia = sin subtitulos
            return [("all", T("sub_off"))] + [(c, tracks.name_of(c, get_lang())) for c in tracks.LANG_ORDER]
        return [("all", T("all"))] + [(c, tracks.name_of(c, get_lang())) for c in tracks.LANG_ORDER]

    def _toggle_prio(self, key, mx, code):
        lst = self._prio(key)
        if code == "all":
            lst = []
        elif code in lst:
            lst.remove(code)
        elif len(lst) < mx:
            lst.append(code)
        else:
            self.notice = T("multi_max", mx)
            return False
        self.settings[key] = lst
        self.notice = ""
        return True

    def _node_len(self):
        k = self._kind(self.set_path)
        if k == "menu":
            return len(self._menu_rows(self.set_path))
        if k == "single":
            return len(self._options(self.SINGLE[tuple(self.set_path)]))
        return len(self._multi_options())

    def _handle_menu(self, action):
        if self.state == "lists":
            n = max(1, len(self.sources))
            if self.confirm_del:                              # pregunta: quieres borrar?  Si / No
                if action in ("left", "right", "up", "down"):
                    self.conf_sel = 1 - self.conf_sel
                elif action == "back":
                    self.confirm_del = None
                elif action == "ok":
                    sid, self.confirm_del = self.confirm_del, None
                    if self.conf_sel == 0:
                        return ("delete_list", sid)
                return None
            if action == "fav" and self.sources:
                sid = self.sources[self.m_idx]["id"]
                if sid.startswith("f:"):
                    self.confirm_del = sid
                    self.conf_sel = 1                         # por defecto "No"
                    self.notice = ""
                else:
                    self.notice = T("del_main")
                return None
            if action in ("up", "down"):
                self.m_idx = (self.m_idx + (1 if action == "down" else -1)) % n
            elif action == "back":
                self.state = "home"
            elif action == "ok" and self.sources:
                return ("switch_list", self.sources[self.m_idx]["id"])
            return None
        # Ajustes (arbol)
        n = self._node_len()
        kind = self._kind(self.set_path)
        i = self.set_idx[-1]
        if kind != "menu":
            self.moving = False
        if kind == "menu" and action == "fav" and n > 0:       # X: coger / soltar la fila para cambiarla de lugar
            self.moving = not self.moving
            if not self.moving:
                return ("settings_changed", None)
            return None
        if self.moving:
            if action in ("up", "down"):
                j = i + (1 if action == "down" else -1)
                if 0 <= j < n:
                    keys = [r[0] for r in self._menu_rows(self.set_path)]
                    keys[i], keys[j] = keys[j], keys[i]
                    self.settings.setdefault("menu_order", {})["/".join(self.set_path)] = keys
                    self.set_idx[-1] = j
            elif action == "back":
                self.moving = False
                return ("settings_changed", None)
            return None
        if action in ("up", "down"):
            self.set_idx[-1] = (i + (1 if action == "down" else -1)) % n
            self.sel_t = time.time()
            self.notice = ""
        elif action in ("left", "right") and kind == "menu" and tuple(self.set_path) == self.LOGO_PER and i in (0, 1):
            if i == 0:
                self.settings["logo_style"] = "c" if self._logo_style() == "w" else "w"
            else:
                d = 2 if action == "right" else -2
                self.settings["logo_size"] = max(self.LOGO_MIN, min(self.LOGO_MAX, self._logo_size() + d))
            self._home_dirty()
            self.sel_t = time.time()
            return ("settings_changed", None)
        elif action in ("left", "right") and kind == "menu" and tuple(self.set_path) == ("look", "fonts") and i == 1:
            d = 1 if action == "right" else -1
            self.settings["sec_size"] = max(self.SEC_MIN, min(self.SEC_MAX, self._sec_size() + d))
            self._split_last = None
            self.sel_t = time.time()
            return ("settings_changed", None)
        elif action in ("left", "right") and kind == "menu" and tuple(self.set_path) == ("clock",) and i == 2:
            d = 1 if action == "right" else -1
            self.settings["date_size"] = max(self.DATE_MIN, min(self.DATE_MAX, self._date_size() + d))
            self._home_dirty()
            self.sel_t = time.time()
            return ("settings_changed", None)
        elif action in ("pgup", "pgdn", "l1", "r1"):
            self.set_idx[-1] = max(0, min(n - 1, i + (6 if action in ("pgdn", "r1") else -6)))
            self.sel_t = time.time()
        elif action == "back":
            self.notice = ""
            if self.set_path:
                self.set_path.pop()
                self.set_idx.pop()
                self.sel_t = time.time()
            else:
                self.state = "home"
        elif action == "ok":
            if kind == "menu" and tuple(self.set_path) == self.LOGO_PER:
                if i == 0:                                    # Logo: Blanco <-> Contorno
                    self.settings["logo_style"] = "c" if self._logo_style() == "w" else "w"
                    self._home_dirty()
                    return ("settings_changed", None)
                if i == 2:                                    # Personalizar: teclado (maximo 9 letras)
                    self.kb_target = "logo"
                    self.kb_text = self._logo_text()
                    self.kb_row = 1
                    self.kb_col = 0
                    self.kb_shift = 0
                    self.kb_sym = False
                    self.kb_pos = len(self.kb_text)
                    self.cat = "ALL"
                    self.state = "kbd"
                return None
            if kind == "menu" and ((tuple(self.set_path) == ("clock",) and i == 2) or (tuple(self.set_path) == ("look", "fonts") and i == 1)):
                return None
            if kind == "menu":
                key = self._menu_rows(self.set_path)[i][0]
                if not self.set_path and key == "support":      # pantalla de apoyo (codigo QR)
                    self.state = "support"
                    return None
                self.set_path.append(key)
                self.set_idx.append(0)
                if self._kind(self.set_path) == "single":      # arranca sobre la opcion activa
                    sk = self.SINGLE[tuple(self.set_path)]
                    cur = self._current(sk)
                    for j, o in enumerate(self._options(sk)):
                        if o[0] == cur:
                            self.set_idx[-1] = j
                self.sel_t = time.time()
            elif kind == "single":
                sk = self.SINGLE[tuple(self.set_path)]
                self._apply(sk, self._options(sk)[i][0])
                self.set_path = [] if sk == "ui_lang" else self.set_path[:-1]
                self.set_idx = self.set_idx[:len(self.set_path) + 1]
                self.sel_t = time.time()
                return ("settings_changed", None)
            else:
                key, mx = self.MULTI[tuple(self.set_path)]
                if self._toggle_prio(key, mx, self._multi_options()[i][0]):
                    return ("settings_changed", None)
        return None

    def _handle_split(self, action):
        n = len(self.view)
        gl = self.groups_of(self.cat)
        gn = len(gl)
        ser = self._ser()
        sh = self.shows_of() if ser else []
        sn = len(sh)
        last = self._last_col()
        if action == "back":
            if self.col == last and self.query.get(self.cat):
                self.query[self.cat] = ""
                self.idx = self.top = 0
                self.refresh()
            elif ser and self.col == 1 and self.sq:
                self.sq = ""
                self.sidx = self.stop = 0
                self.sname = None
                self.refresh()
            elif self.col == 0 and self.gquery.get(self.cat):
                self.gquery[self.cat] = ""
                self.gidx = self.gtop = 0
                self.refresh()
            else:
                self.state = "home"
            return None
        if action == "search":
            self.kb_target = "group" if self.col == 0 else ("show" if (ser and self.col == 1) else "chan")
            self.kb_text = {"group": self.gquery.get(self.cat, ""), "show": self.sq,
                            "chan": self.query.get(self.cat, "")}[self.kb_target]
            self.kb_row = 1
            self.kb_col = 0
            self.kb_shift = 0
            self.kb_sym = False
            self.kb_pos = len(self.kb_text)
            self.state = "kbd"
            return None
        if action == "left":
            self.col = max(0, self.col - 1) if ser else 0
        elif action == "right":
            if self.col == 0 and ((ser and sn) or (not ser and n)):
                self.col = 1
            elif ser and self.col == 1 and n:
                self.col = 2
        elif action in ("l1", "r1"):
            d = 1 if action == "r1" else -1
            if self.col == 0 and gn:
                self.gidx = self._name_jump([x[0] for x in gl], self.gidx, d)
                self._gscroll()
            elif ser and self.col == 1 and sn:
                self.sidx = self._name_jump([x[0] for x in sh], self.sidx, d)
                self._sscroll()
            elif self.col == last and n:
                if ser:
                    self.idx = max(0, min(n - 1, self.idx + d * VISIBLE))
                else:
                    self.idx = self._letter_jump(d)
        elif action == "fav":
            if self.cat == "FAV":
                if self.col == 0 and gn:                      # quitar el canal / categoria / serie de favoritos
                    key = gl[self.gidx][0]
                    self.notice = ""
                    return self._toggle_fav_key(key[2:] if key.startswith("C|") else key)
                if self.col == 1 and n:
                    self.notice = T("fav_in_group")
                return None
            if self.col == 0 and gn:                          # categoria entera a favoritos (o quitarla)
                return self._toggle_fav_key(self._gfav_key(self.cat, gl[self.gidx][0]))
            if ser and self.col == 1 and sn:                  # serie completa a favoritos
                return self._toggle_fav_key(self._sfav_key(self.cat, self.gname, sh[self.sidx][0]))
            if self.col == last and n:
                return self._toggle_fav_key(self.view[self.idx].fkey)
        elif action in ("up", "down", "pgup", "pgdn"):
            step = {"up": -1, "down": 1, "pgup": -VISIBLE, "pgdn": VISIBLE}[action]
            if self.col == 0 and gn:
                if abs(step) == 1:
                    self.gidx = (self.gidx + step) % gn
                else:
                    self.gidx = max(0, min(gn - 1, self.gidx + step))
                self._gscroll()
            elif ser and self.col == 1 and sn:
                if abs(step) == 1:
                    self.sidx = (self.sidx + step) % sn
                else:
                    self.sidx = max(0, min(sn - 1, self.sidx + step))
                self._sscroll()
            elif self.col == last and n:
                if abs(step) == 1:
                    self.idx = (self.idx + step) % n
                else:
                    self.idx = max(0, min(n - 1, self.idx + step))
        elif action == "ok":
            if self.col == 0 and self.cat == "FAV" and gn and gl[self.gidx][0].startswith("C|"):
                fk = gl[self.gidx][0][2:]                    # canal suelto: se reproduce ahi mismo
                e = next((x for x in self.entries if x.fkey == fk), None)
                if e is not None:
                    return ("play", e)
            elif self.col == 0:
                if gn:                       # elegir categoria: se marca en azul y el cursor pasa a la columna siguiente
                    self.gname = gl[self.gidx][0]
                    self.query[self.cat] = ""
                    self.idx = self.top = 0
                    self.sname = None
                    self.sidx = self.stop = 0
                    self.sq = ""
                    self.refresh()
                    if (ser and self.shows_of()) or (not ser and self.view):
                        self.col = 1
            elif ser and self.col == 1:
                if sn:                       # elegir serie: sus episodios aparecen a la derecha
                    self.sname = sh[self.sidx][0]
                    self.query[self.cat] = ""
                    self.idx = self.top = 0
                    self.refresh()
                    if self.view:
                        self.col = 2
            elif n:
                return ("play", self.view[self.idx])
        self._scroll()
        return None

    @staticmethod
    def _name_letter(s):
        for ch in norm(s):
            if ch.isalnum():
                return ch.upper() if ch.isalpha() else "#"
        return "#"

    def _name_jump(self, names, i, d):
        cur = self._name_letter(names[i])
        if d > 0:
            for j in range(i + 1, len(names)):
                if self._name_letter(names[j]) != cur:
                    return j
            return i
        j = i
        while j > 0 and self._name_letter(names[j - 1]) == cur:
            j -= 1
        if j == 0:
            return 0
        prev = self._name_letter(names[j - 1])
        while j > 0 and self._name_letter(names[j - 1]) == prev:
            j -= 1
        return j

    def _handle_list(self, action):
        if self.cat in SPLIT:
            return self._handle_split(action)
        n = len(self.view)
        if action == "back" and self.cat == "ALL":
            self.query["ALL"] = ""
            self.state = "home"
        elif action in ("l1", "r1") and n:
            self.idx = self._letter_jump(1 if action == "r1" else -1)
        elif action == "back":
            if self.query.get(self.cat):
                self.query[self.cat] = ""     # primero se quita la busqueda
                self.idx = 0
                self.top = 0
                self.refresh()
            else:
                self.state = "home"
        elif action == "search":
            self.kb_text = self.query.get(self.cat, "")
            self.kb_row = 1
            self.kb_col = 0
            self.kb_shift = 0
            self.kb_sym = False
            self.kb_pos = len(self.kb_text)
            self.state = "kbd"
        elif action == "fav" and n:
            e = self.view[self.idx]
            if e.fkey not in self.favs and self._via_group(e):       # viene de una categoria / serie favorita
                self.notice = T("fav_via_group")
                return None
            self.notice = ""
            self._toggle_fav_key(e.fkey)
            if self.cat == "FAV":
                self.refresh()
            return ("save_favs", None)
        elif action == "up" and n:
            self.idx = (self.idx - 1) % n
        elif action == "down" and n:
            self.idx = (self.idx + 1) % n
        elif action in ("pgup", "left") and n:
            self.idx = max(0, self.idx - VISIBLE)
        elif action in ("pgdn", "right") and n:
            self.idx = min(n - 1, self.idx + VISIBLE)
        elif action == "ok" and n:
            return ("play", self.view[self.idx])
        self._scroll()
        return None

    def _letter_jump(self, d):
        """L1/R1: salta al primer elemento de la letra siguiente / anterior (A, B, C...)."""
        v = self.view
        cur = letter_of(v[self.idx])
        if d > 0:
            for i in range(self.idx + 1, len(v)):
                if letter_of(v[i]) != cur:
                    return i
            return self.idx
        i = self.idx
        while i > 0 and letter_of(v[i - 1]) == cur:
            i -= 1
        if i == 0:
            return 0
        prev = letter_of(v[i - 1])
        while i > 0 and letter_of(v[i - 1]) == prev:
            i -= 1
        return i

    def _kb_rows(self):
        return KB_SYMBOLS if self.kb_sym else KB_LETTERS

    def _kb_len(self, row):
        return len(KB_ROWS[row])

    def _kb_type(self, text):
        mx = self.LOGO_CHARS if self.kb_target == "logo" else MAX_QUERY
        for ch in text:
            if len(self.kb_text) < mx:
                self.kb_text = self.kb_text[:self.kb_pos] + ch + self.kb_text[self.kb_pos:]
                self.kb_pos += 1

    def _kb_delete(self):
        if self.kb_pos > 0:
            self.kb_text = self.kb_text[:self.kb_pos - 1] + self.kb_text[self.kb_pos:]
            self.kb_pos -= 1

    def _handle_kbd(self, action):
        rows = self._kb_rows()
        last = len(rows) - 1
        if action == "l1":                                   # L1: mayusculas fijas (otra vez: minusculas)
            self.kb_shift = 0 if self.kb_shift == 2 else 2
        elif action == "pgup":                               # L2: simbolos <-> teclado normal
            self.kb_sym = not self.kb_sym
            self.kb_shift = 0
        elif action == "r1":                                 # R1: flecha derecha
            self.kb_pos = min(len(self.kb_text), self.kb_pos + 1)
        elif action == "pgdn":                               # R2: flecha izquierda
            self.kb_pos = max(0, self.kb_pos - 1)
        elif action == "fav":                                # X: barra espaciadora
            return self._kb_action("space")
        elif action in ("left", "right"):
            n = len(rows[self.kb_row])
            self.kb_col = (self.kb_col + (1 if action == "right" else -1)) % n
        elif action in ("up", "down"):
            old = self.kb_row
            self.kb_row = (self.kb_row + (1 if action == "down" else -1)) % (last + 1)
            if self.kb_row == last:                       # baja a la fila de abajo
                c = self.kb_col
                self.kb_col = max(i for i in range(len(ROW4_COL)) if ROW4_COL[i] <= c)
            elif old == last:                             # sube desde la fila de abajo
                self.kb_col = ROW4_UP[self.kb_col]
            else:
                self.kb_col = min(self.kb_col, len(rows[self.kb_row]) - 1)
        elif action == "ok":
            key = rows[self.kb_row][self.kb_col]
            if key == "shift":
                self.kb_shift = (self.kb_shift + 1) % 3      # 1 toque: una mayuscula; 2 toques: fijas; 3: apagar
            elif key == "sym":
                self.kb_sym = not self.kb_sym
                self.kb_shift = 0
            elif key == "del":
                self._kb_delete()
            elif key == "left":
                self.kb_pos = max(0, self.kb_pos - 1)
            elif key == "right":
                self.kb_pos = min(len(self.kb_text), self.kb_pos + 1)
            elif key == "go":
                return self._kb_action("go")
            elif key == "space":
                return self._kb_action("space")
            else:
                if self.kb_shift and key.isalpha():
                    key = key.upper()
                    if self.kb_shift == 1:
                        self.kb_shift = 0
                self._kb_type(key)
        elif action == "back":
            if self.kb_text:
                self._kb_delete()
            elif self.kb_target == "logo":
                return self._kb_leave_logo(False)
            else:
                self.state = "home" if self.cat == "ALL" else "list"
        elif action in ("search", "start"):
            return self._kb_action("go")
        return None

    def _kb_leave_logo(self, save):
        if save:
            self.settings["logo_text"] = self.kb_text.strip()[:self.LOGO_CHARS] or self.LOGO_DEFAULT
            self._home_dirty()
        self.kb_target = "chan"
        self.kb_sym = False
        self.state = "settings"
        self.sel_t = time.time()
        return ("settings_changed", None) if save else None

    def _kb_action(self, what):
        if what == "go" and self.kb_target == "logo":
            return self._kb_leave_logo(True)
        if what == "space":
            if self.kb_pos > 0 and self.kb_text[self.kb_pos - 1] != " ":
                self._kb_type(" ")
        elif what == "go":
            if self.cat == "ALL" and not self.kb_text.strip():
                self.state = "home"
                return None
            if self.cat in SPLIT and self.kb_target == "group":
                self.gquery[self.cat] = self.kb_text.strip()
                self.gidx = self.gtop = 0
            elif self.cat in SPLIT and self.kb_target == "show":
                self.sq = self.kb_text.strip()
                self.sidx = self.stop = 0
                self.sname = None
            else:
                self.query[self.cat] = self.kb_text.strip()
            self.kb_sym = False
            self.idx = 0
            self.top = 0
            self.state = "list"
            self.refresh()
        return None

    def _scroll(self):
        if self.idx < self.top:
            self.top = self.idx
        if self.idx >= self.top + VISIBLE:
            self.top = self.idx - VISIBLE + 1
        if self.top < 0:
            self.top = 0

    # ---------- dibujo ----------
    def draw(self, fast=False):
        self._mq_seen = set()
        self.mq_on = False
        if self.state not in ("settings", "lists"):
            self._pv_pending = None
        if self.state == "home":
            self.draw_home(fast)
            if self.confirm_quit:
                self._draw_quit()
        elif self.state == "kbd":
            self._screen("kbd", self._sig_kbd, self.draw_kbd)
        elif self.state == "support":
            self._screen("support", lambda: (get_lang(), __import__("updater").ST["status"], int(__import__("updater").ST["prog"] * 100)), self.draw_support)
        elif self.state in ("settings", "lists"):
            self._screen("menu", self._sig_menu, self.draw_menu)
        elif self.cat in SPLIT:
            self.draw_list()
        else:
            self._screen("list", self._sig_list, self.draw_list)
        for k in [k for k in self._mq_t if k not in self._mq_seen]:
            del self._mq_t[k]                              # el letrero vuelve a empezar al reaparecer
        self.g.present()

    # ----- letrero (banner): todo texto que no cabe se desplaza suave, recortado a su espacio -----
    MQ_SPEED = 48.0                                        # pixeles por segundo
    MQ_PAUSE = 1.2

    def _sig_menu(self):
        s = (self.state, tuple(self.set_path), tuple(self.set_idx), self.m_idx, self.moving, self.confirm_del,
             self.conf_sel, self.notice, get_lang(), repr(self.settings), len(self.sources), __import__("updater").ST["status"], self._blink())
        return s

    def _sig_list(self):
        c = self.cat
        return (c, self.idx, self.top, id(self.view), len(self.view), len(self.favs), self.query.get(c, ""),
                self.notice, get_lang())

    def _sig_kbd(self):
        return (self.kb_text, self.kb_pos, self.kb_row, self.kb_col, self.kb_shift, self.kb_sym, self.kb_target,
                self.cat, get_lang())

    def _screen(self, name, sigfn, fn):
        """Dibuja la pantalla; si hay textos con letrero, la parte fija se guarda y solo se redibuja el letrero."""
        g = self.g
        if not hasattr(g, "begin_cache") or getattr(self, "_scr_broken", False):
            self._mq_defer = None
            fn()
            self._mq_flush()
            return
        try:
            sig = sigfn()
            if (self._mq_items or self._pv_pending is not None) and g.cache_ok(name) \
                    and self._scr_sig.get(name) == sig and self._mq_scr == name:
                g.blit_cache(name)
                self._mq_flush()
                return
            if not g.begin_cache(name):
                raise RuntimeError("sin cache")
            self._mq_items = []
            self._mq_defer = self._mq_items
            self._mq_scr = name
            try:
                fn()
            finally:
                self._mq_defer = None
            g.end_cache()
            g.blit_cache(name)
            self._scr_sig[name] = sig
            self._mq_flush()
        except Exception:
            self._scr_broken = True
            self._mq_defer = None
            if hasattr(g, "abort_cache"):
                g.abort_cache()
            fn()
            self._mq_flush()

    def mt(self, s, x, y, size, col, align="l", bold=False, maxw=0, fbold=None):
        """Texto en un ancho maximo: si cabe, normal; si no, letrero que se desplaza (o puntos suspensivos si no hay recorte)."""
        g = self.g
        if not s:
            return
        fb = bold if fbold is None else fbold
        if not maxw or g.text_w(s, size, fb) <= maxw:
            g.text(s, x, y, size, col, align, bold)
            return
        if not hasattr(g, "clip"):
            g.text(self.fit(s, size, maxw, fb), x, y, size, col, align, bold)
            return
        item = (s, x, y, size, col, align, bold, maxw, fb)
        if self._mq_defer is not None:
            self._mq_defer.append(item)
        else:
            self._mq_text(item)

    def _mq_off(self, el, over):
        """Desplazamiento suave: pausa, avanza, pausa, regresa."""
        d = over / self.MQ_SPEED
        per = 2 * (self.MQ_PAUSE + d)
        t = el % per
        if t < self.MQ_PAUSE:
            return 0.0
        if t < self.MQ_PAUSE + d:
            return self.MQ_SPEED * (t - self.MQ_PAUSE)
        if t < 2 * self.MQ_PAUSE + d:
            return float(over)
        return over - self.MQ_SPEED * (t - 2 * self.MQ_PAUSE - d)

    def _mq_text(self, item):
        s, x, y, size, col, align, bold, maxw, fb = item
        g = self.g
        now = getattr(self, "clock", time.time)()
        bx = x if align == "l" else (x - maxw if align == "r" else x - maxw // 2)
        key = (s, bx, y, size)
        t0 = self._mq_t.get(key)
        if t0 is None:
            t0 = self._mq_t[key] = now
        self._mq_seen.add(key)
        over = g.text_w(s, size, fb) - maxw
        off = self._mq_off(now - t0, over)
        g.clip(bx, y - 3, maxw, size + 14)
        g.text(s, bx - int(off), y, size, col, "l", bold)
        g.unclip()
        self.anim = True
        self.mq_on = True

    def _mq_flush(self):
        if self.confirm_del or self.confirm_quit:
            return                                          # un cuadro encima: no se dibuja el letrero
        if self._pv_pending is not None and self.state in ("settings", "lists"):
            self._draw_preview(self._pv_pending[1], self._pv_pending[0])      # recuadro de previa, cuadro a cuadro
        for it in self._mq_items:
            self._mq_text(it)

    def _draw_quit(self):
        g = self.g
        g.rect(90, 150, g.w - 180, 170, (10, 12, 28), 12)
        g.outline(90, 150, g.w - 180, 170, WHITE, 3, 12)
        g.text(T("quit_ask"), g.w // 2, 182, 28, WHITE, "c", True)
        for k, lab in enumerate((T("yes"), T("no"))):
            bx = 150 + k * 190
            if self.conf_sel == k:
                g.gradient(bx, 250, 150, 48, SET_C1, SET_C2, True, 6)
            else:
                g.rect(bx, 250, 150, 48, (40, 44, 70), 6)
            g.text(lab, bx + 75, 250 + 11, 22, WHITE, "c", self.conf_sel == k)

    def _background(self):
        self.g.gradient(0, 0, self.g.w, self.g.h, BG_TOP, BG_BOT)

    def fit(self, s, size, maxw, bold=False, face=None):
        """Recorta con "…" para que quepa en maxw. Busqueda binaria y memoria: los nombres larguisimos
        (listas mal formadas) ya no frenan la pantalla."""
        key = (s, size, maxw, bold, face)
        c = self._fit_cache.get(key)
        if c is not None:
            return c
        g = self.g
        cut = int(maxw / 3) + 1                     # ningun caracter mide menos de ~3 px
        if len(s) <= cut and g.text_w(s, size, bold, face) <= maxw:
            r = s
        else:
            t = s[:cut]
            lo, hi = 1, len(t)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if g.text_w(t[:mid].rstrip() + "…", size, bold, face) <= maxw:
                    lo = mid
                else:
                    hi = mid - 1
            r = t[:lo].rstrip() + "…"
        if len(self._fit_cache) > 3000:
            self._fit_cache.clear()
        self._fit_cache[key] = r
        return r

    def draw_star(self, cx, cy, r, c, filled=True):
        pts = star_points(cx, cy, r)
        self.g.polygon(pts, c)

    ZOOM = 1.45
    ZOOM_T = 0.22

    def zoom_of(self, key):
        """Escala actual del icono `key` (crece al elegirlo, vuelve a 1 al soltarlo; con animacion suave)."""
        now = time.time()
        want = self.ZOOM if self.sel == key else 1.0
        z = self.zt.get(key)
        if z is None:
            self.zt[key] = [want, want, now - 10]
            return want
        e = min(1.0, (now - z[2]) / self.ZOOM_T)
        cur = z[0] + (z[1] - z[0]) * (1 - (1 - e) ** 3)       # arranca rapido y frena suave al final
        if z[1] != want:
            z[0], z[1], z[2] = cur, want, now
        return cur

    def zoom_busy(self):
        now = time.time()
        return (self.icon_live() or any(now - z[2] < self.ZOOM_T + 0.05 for z in self.zt.values())
                or any(now - z[2] < self.FX_T + 0.05 for z in self.lt.values()))

    def draw_home(self, fast=False):
        self._draw_home_inner(fast)
        self._mq_flush()                                    # textos largos del inicio: letrero

    def _draw_home_inner(self, fast=False):
        g = self.g
        mode = self.settings.get("tile_fx", "default")
        if mode not in self.FX_CODES:
            mode = "default"
        if mode != "default" and not self._fx_broken and hasattr(g, "blit_part") and self._draw_home_fx(mode):
            return
        if fast and hasattr(g, "cache_ok") and g.cache_ok("home"):
            g.blit_cache("home")                # fondo ya dibujado: solo se mueven los iconos
            self._home_icons()
            return
        cached = hasattr(g, "begin_cache") and g.begin_cache("home")
        self._background()
        self._home_body(True)
        if cached:
            g.end_cache()
            g.blit_cache("home")
        self._home_icons()

    ICON_FX = ("default", "A", "B", "C", "D", "E")

    def _clock_style(self):
        m = self.settings.get("clock_style", "default")
        return m if m in clocks.CODES else "default"

    def _icon_mode(self):
        m = self.settings.get("icon_fx", "default")
        return m if m in self.ICON_FX else "default"

    def icon_live(self):
        """Hay un efecto de icono en marcha (para redibujar el inicio cuadro a cuadro)."""
        if self.state != "home" or self._icon_mode() == "default" or self.sel not in ("SEARCH",) + ICON_ORDER:
            return False
        if self._icon_mode() == "A":                         # el giro dura un instante
            return time.time() - self._ic_t0 < 1.5
        return True

    def _icon_xf(self, k):
        """(escala, dx, dy, angulo, ancho, alto) del icono elegido segun el efecto."""
        z = self.zoom_of(k)
        mode = self._icon_mode()
        if mode == "default" or self.sel != k:
            return z, 0, 0, 0.0, 1.0, 1.0
        t = time.time() - self._ic_t0
        dx = dy = 0.0
        ang = 0.0
        sxx = syy = 1.0
        if mode == "A":                                       # giro
            if k in ("SET", "UPD"):
                e = min(1.0, t / 0.9)
                ang = -360.0 * (1 - (1 - e) ** 3)
            else:
                ang = 14.0 * math.sin(t * 9.0) * max(0.0, 1 - t / 1.2)
        elif mode == "B":                                     # latido
            if t > 0.25:
                z += 0.10 * math.sin((t - 0.25) * 8.0)
        elif mode == "C":                                     # flotar
            dy = -5.0 * math.sin(max(0.0, t - 0.2) * 4.2) * min(1.0, t / 0.4)
        elif mode == "D":                                     # campana
            if t > 0.25:
                tt = (t - 0.25) % 2.0
                th = 26.0 * math.exp(-1.4 * tt) * math.sin(tt * 11.0)
                dd = 20.0 * z / 1.45
                ang = th
                dx = dd * math.sin(math.radians(th))
                dy = dd * math.cos(math.radians(th)) - dd
        elif mode == "E":                                     # gelatina
            if t > 0.25:
                tt = (t - 0.25) % 1.8
                kk = math.exp(-3.2 * tt) * math.sin(tt * 18.0)
                sxx, syy = 1 + 0.22 * kk, 1 - 0.22 * kk
        return z, dx, dy, ang, sxx, syy

    def _draw_icon(self, name, size, x, y, k):
        z, dx, dy, ang, sxx, syy = self._icon_xf(k)
        if ang or sxx != 1.0 or syy != 1.0:
            try:
                return self.g.image(name, size, x + dx, y + dy, None, z, ang, sxx, syy)
            except TypeError:
                pass
        return self.g.image(name, size, x + dx, y + dy, None, z)

    def _home_icons(self):
        """Lupa e iconos de abajo (con zoom al elegirlos): lo unico que se redibuja durante la animacion."""
        g = self.g
        sx = self._sx
        if self.sel != self._ic_last:                          # al cambiar de icono, el efecto empieza de cero
            self._ic_last = self.sel
            self._ic_t0 = time.time()
        if not self._draw_icon("buscar", 40, sx, SEARCH_Y, "SEARCH"):
            g.circle(sx - 4, SEARCH_Y - 4, 11, WHITE)
        if self.sel == "SEARCH":
            g.text(T("icon_search"), sx, SEARCH_Y + 36, 12, WHITE, "c", True)
        for k in ICON_ORDER:
            x = ICON_X[k]
            name = {"UPD": "actualizar_lista", "LISTS": "cambiar_lista", "SET": "ajustes"}[k]
            if not self._draw_icon(name, BOT_ICON, x, ICON_Y, k):
                hole = _mix(BG_TOP, BG_BOT, ICON_Y / 480.0)
                if k == "UPD":
                    icons.refresh_box(g, x, ICON_Y, 38)
                elif k == "LISTS":
                    icons.swap_lists(g, x, ICON_Y, 42, hole)
                else:
                    icons.gear(g, x, ICON_Y, 38, hole)
            if self.sel == k:
                g.text(T(ICON_KEY[k]), x, ICON_Y + 38, 12, WHITE, "c", True)

    def _home_body(self, tiles=True):
        self._mq_items = []
        self._mq_defer = self._mq_items
        try:
            self._home_body2(tiles)
        finally:
            self._mq_defer = None

    def _home_body2(self, tiles=True):
        """Logo, hora, wifi, (tarjetas) y pie de pagina del inicio."""
        g = self.g
        # Logo
        self._sync_dscale()
        lg_end = self._draw_logo(24, 44, self._logo_cfg())
        # Hora (12 / 24 h), fecha y senal de internet
        t = time.localtime()
        dtxt = date_text(t.tm_wday, t.tm_mday, t.tm_mon, t.tm_year, self._date_code())
        style = self._clock_style()
        if self.settings.get("clock") == "12":
            tm = "%d:%02d" % (t.tm_hour % 12 or 12, t.tm_min)
            suf = T("pm") if t.tm_hour >= 12 else T("am")
        else:
            tm = "%02d:%02d" % (t.tm_hour, t.tm_min)
            suf = ""
        lvl = self.wifi_level           # 0 = solo el punto, 1 = una rayita, 2 = dos rayitas, -1 = sin wifi
        if lvl is None:
            lvl = 2 if self.online else -1       # sin lector de senal: usa el estado de internet
        dim = (96, 106, 128) if lvl < 0 else (70, 78, 100)
        if style != "default":
            wx, _left = clocks.draw(g, style, 616, 0, 1.0, tm, suf, dtxt, lvl, dim)
        else:
            if suf:
                sw = g.text_w(suf, 18, True)
                g.text(suf, 616, 38, 18, WHITE, "r", True)
                tx_r = 616 - sw - 8
            else:
                tx_r = 616
            g.text(tm, tx_r, 20, 44, WHITE, "r", True)
            g.text(dtxt, 616, 72, self._date_size(), (214, 218, 232), "r")
            wx = tx_r - g.text_w(tm, 44, True) - 32          # wifi pegado a la izquierda de la hora
        # Busqueda maestra: centrada entre el logo "IPTV" y el wifi
        sx = (lg_end + (wx - 14)) // 2
        self._sx = sx
        if style == "default":
            ok = g.image("wifi_0", 38, wx, 44, WHITE if lvl >= 0 else dim, 1.14)       # mide lo mismo que los numeros
            for k in (1, 2):
                ok = g.image("wifi_%d" % k, 38, wx, 44, WHITE if lvl >= k else dim, 1.14) and ok
            if not ok:
                g.circle(wx, 50, 3, WHITE if lvl >= 0 else dim)
        # Mosaicos
        if tiles:
            for cat in HOME_ORDER:
                self._tile(cat)
        # Pie
        if self.notice:
            self.mt(self.notice, 24, 436, 14, WARN, "l", False, 400)
        else:
            self.mt(T("footer_list", self.list_name, len(self.entries)), 24, 436, 14, GRAY, "l", False, 400)
        cl = self.settings.get("content_lang", "all")
        if cl != "all":
            self.mt(T("filter_on", lang_name(cl)), 24, 416, 13, GOLD, "l", False, 292)
        self.mt(T("footer_keys"), 616, 436, 14, GRAY, "r", False, 200)

    # ----- efectos de las tarjetas (Ajustes > Apariencia > Tarjetas) -----
    FX_T = 0.25

    def _fx_sig(self, mode):
        return (mode, self.list_name, len(self.entries), tuple(self.count(c) for c in HOME_ORDER), self.notice,
                self.settings.get("content_lang"), self.settings.get("clock"), self.settings.get("date_fmt"), self._clock_style(), get_lang(), self.wifi_level,
                self.online, time.localtime().tm_min, self._logo_text())

    def _draw_home_fx(self, mode):
        """Fondo y tarjetas se dibujan una vez en texturas; cada cuadro solo las coloca (zoom, brillo...)."""
        g = self.g
        try:
            sig = self._fx_sig(mode)
            if not (g.cache_ok("bg") and g.cache_ok("tiles") and sig == self._fx_last):
                if not g.begin_cache("bg"):
                    return False
                self._background()
                self._home_body(False)
                g.end_cache()
                if not g.begin_cache("tiles", True):
                    return False
                for cat in HOME_ORDER:
                    self._tile(cat, False)
                g.end_cache()
                self._fx_last = sig
            self._compose_fx(mode)
            self._home_icons()
            return True
        except Exception:
            self._fx_broken = True               # si algo falla, se vuelve al dibujo normal
            if hasattr(g, "abort_cache"):
                g.abort_cache()
            return False

    def level_of(self, cat):
        """Nivel de seleccion de una tarjeta (0 = suelta, 1 = elegida), con transicion suave."""
        now = time.time()
        want = 1.0 if self.sel == cat else 0.0
        z = self.lt.get(cat)
        if z is None:
            self.lt[cat] = [want, want, now - 10]
            self.fx_t0[cat] = now
            return want
        e = min(1.0, (now - z[2]) / self.FX_T)
        cur = z[0] + (z[1] - z[0]) * (1 - (1 - e) ** 3)
        if z[1] != want:
            z[0], z[1], z[2] = cur, want, now
            if want == 1.0:
                self.fx_t0[cat] = now                      # el efecto B / D arranca de cero en la tarjeta elegida
        return cur

    def fx_live(self):
        """Efectos que se mueven solos mientras estas quieto en una tarjeta (brillo, luz del borde)."""
        return (self.state == "home" and not self._fx_broken and self.sel in TILE_RECT
                and self.settings.get("tile_fx") in ("B", "D", "E"))

    def fx_interval(self):
        """Segundos entre cuadros de los efectos que se mueven solos (B y D)."""
        return 0.03                                      # ~30 cuadros por segundo (B y D)

    def _lit(self, yc, k):
        return _mix(_mix(BG_TOP, BG_BOT, yc / 480.0), WHITE, k)

    def _perimeter(self, x, y, w, h, r):
        key = (x, y, w, h, r)
        p = self._perim.get(key)
        if p is None:
            def arc(cx, cy, a0):
                return [(cx + r * math.cos(math.radians(a0 + k * 9)), cy + r * math.sin(math.radians(a0 + k * 9)))
                        for k in range(11)]
            path = [(x + r + i * (w - 2 * r) / 10.0, y) for i in range(11)]
            path += arc(x + w - r, y + r, -90)
            path += [(x + w, y + r + i * (h - 2 * r) / 10.0) for i in range(11)]
            path += arc(x + w - r, y + h - r, 0)
            path += [(x + w - r - i * (w - 2 * r) / 10.0, y + h) for i in range(11)]
            path += arc(x + r, y + h - r, 90)
            path += [(x, y + h - r - i * (h - 2 * r) / 10.0) for i in range(11)]
            path += arc(x + r, y + r, 180)
            d = [0.0]
            for a, b in zip(path, path[1:]):
                d.append(d[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            p = (path, d)
            self._perim[key] = p
        return p

    def _orbit_table(self, x, y, w, h, r):
        """Puntos del borde ya repartidos cada ~2 px: asi cada cuadro solo busca posiciones, sin calcular."""
        key = ("tab", x, y, w, h, r)
        tab = self._perim.get(key)
        if tab is None:
            path, d = self._perimeter(x, y, w, h, r)
            total = d[-1]
            n = int(total / 2.0)
            tab = []
            j = 1
            for i in range(n):
                s = i * total / n
                while j < len(d) - 1 and d[j] < s:
                    j += 1
                f = (s - d[j - 1]) / max(1e-6, d[j] - d[j - 1])
                a, b = path[j - 1], path[j]
                tab.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            self._perim[key] = tab
        return tab

    def _orbit(self, x, y, w, h, r, now, e):
        """Luz que recorre el borde. Velocidad y largo de la cola iguales en todas las tarjetas
        (los de Peliculas / Series: una vuelta en 2 s, cola de un 25 % de su borde)."""
        tab = self._orbit_table(x, y, w, h, r)
        n = len(tab)
        total = self._perimeter(x, y, w, h, r)[1][-1]
        px, py, pw, ph = TILE_RECT["PELIS"]
        ref = self._perimeter(px - 4, py - 4, pw + 8, ph + 8, TILE_RADIUS + 4)[1][-1]
        speed = ref / 2.0                                 # pixeles por segundo
        gap = ref * 0.255 / 30.0                          # pixeles entre puntos de la cola
        head = ((now - self.fx_t0.get(self.sel, now)) * speed) % total
        dot = self.g.dot
        for k in range(30):
            q = tab[int(((head - k * gap) % total) / total * n) % n]
            dot(q[0], q[1], e * (1 - k / 30.0) ** 1.5)

    def _compose_fx(self, mode):
        g = self.g
        now = time.time()
        g.blit_cache("bg")
        L = dict((c, self.level_of(c)) for c in HOME_ORDER)
        lifted = []
        for c in HOME_ORDER:
            x, y, w, h = TILE_RECT[c]
            e = L[c]
            if mode in ("A", "E") and e > 0.01:
                lifted.append(c)
                continue
            g.blit_part("tiles", x, y, w, h, x, y, w, h)
            if mode == "C" and e < 0.99:
                g.dim(x, y, w, h, int(255 * 0.5 * (1 - e)))
        for c in sorted(lifted, key=lambda k: L[k]):
            x, y, w, h = TILE_RECT[c]
            e = L[c]
            if mode == "A":                                  # zoom con sombra
                s = 1 + 0.07 * e
                nw, nh = int(w * s), int(h * s)
                nx, ny = x - (nw - w) // 2, y - (nh - h) // 2
                g.shadow(nx + nw / 2.0, ny + nh / 2.0 + 8 * e + 2, w, h, s, 0.69 * e)
                g.blit_part("tiles", x, y, w, h, nx, ny, nw, nh)
            else:                                            # E: respirar con halo
                ph = (1 - math.cos(2 * math.pi * ((now - self.fx_t0.get(c, now)) % 1.6) / 1.6)) / 2.0
                s = 1 + 0.04 * e * ph
                nw, nh = int(w * s), int(h * s)
                nx, ny = x - (nw - w) // 2, y - (nh - h) // 2
                yc = y + h // 2
                for r in range(4, 0, -1):                    # halo: 4 anillos que se apagan hacia afuera
                    g.outline(nx - r * 2, ny - r * 2, nw + r * 4, nh + r * 4, self._lit(yc, e * (0.12 + 0.30 * ph) * (1 - (r - 1) / 4.0) ** 1.5),
                              2, TILE_RADIUS + r * 2)
                g.blit_part("tiles", x, y, w, h, nx, ny, nw, nh)
                g.outline(nx - 2, ny - 2, nw + 4, nh + 4, self._lit(yc, e), 2, TILE_RADIUS + 2)
        for c in HOME_ORDER:
            e = L[c]
            if e <= 0.01:
                continue
            x, y, w, h = TILE_RECT[c]
            if mode in ("B", "C"):
                g.outline(x - 4, y - 4, w + 8, h + 8, self._lit(y + h // 2, e), 3, TILE_RADIUS + 4)
                if mode == "B":                              # brillo que barre
                    g.shine(x, y, w, h, (((now - self.fx_t0.get(c, now)) % 1.5) / 1.5) * (w + 0.7 * h + 120) - 60, e)
            elif mode == "D":                                # luz que recorre el borde
                g.outline(x - 4, y - 4, w + 8, h + 8, self._lit(y + h // 2, 0.27 * e), 2, TILE_RADIUS + 4)
                self._orbit(x - 4, y - 4, w + 8, h + 8, TILE_RADIUS + 4, now, e)

    # ----- vistas previas animadas (archivos img/fx_*.bin: cuadros RGB comprimidos) -----
    def _pv_load(self, code, prefix="fx"):
        if (prefix, code) in self._pv:
            return self._pv[(prefix, code)]
        res = None
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "%s_%s.bin" % (prefix, code))
            with open(path, "rb") as f:
                raw = f.read()
            w, h, n, fps = struct.unpack("<HHHH", raw[:8])
            xor = bool(fps & 0x8000)                         # cuadros guardados como diferencia con el primero
            fps &= 0x7FFF
            pos, frames = 8, []
            for _ in range(n):
                ln = struct.unpack("<I", raw[pos:pos + 4])[0]
                frames.append(raw[pos + 4:pos + 4 + ln])
                pos += 4 + ln
            base = int.from_bytes(zlib.decompress(frames[0]), "little") if xor else None
            res = (w, h, fps, frames, base)
        except Exception:
            res = None
        self._pv[(prefix, code)] = res
        return res

    def _draw_preview(self, code, prefix="fx"):
        """Recuadro con marco blanco (como las tarjetas) a la derecha, centrado, por encima de todo."""
        g = self.g
        W, H = 280, 210
        x, y = 480 - W // 2 - 14, (62 + 480 - H) // 2 + getattr(self, "_pv_dy", 0)
        if prefix == "sf":
            self._draw_sec_preview(code, x, y, W, H)
            return
        if prefix == "ck":
            self._draw_clock_preview(code, x, y, W, H)
            return
        if prefix == "lg":
            self._draw_logo_preview(code, x, y, W, H)
            return
        pv = self._pv_load(code, prefix)
        if pv and hasattr(g, "rgb_frame"):
            w, h, fps, frames, base = pv
            idx = int((time.time() - self.sel_t) * fps) % len(frames)
            data = zlib.decompress(frames[idx])
            if base is not None and idx > 0:
                data = (int.from_bytes(data, "little") ^ base).to_bytes(len(data), "little")
            g.rgb_frame(data, w, h, x + 4, y + 4)
            self.anim = True
            self.pv_on = True
        else:
            g.rect(x + 3, y + 3, W - 6, H - 6, (10, 12, 28), 6)
        g.outline(x, y, W, H, WHITE, 3, 8)

    # ----- pausa de peliculas (Start): imagen detenida + barra + Relacion de aspecto / Audio / Subtitulos -----
    @staticmethod
    def _pause_t(sec):
        sec = max(0, int(sec))
        return ("%d:%02d:%02d" % (sec // 3600, (sec // 60) % 60, sec % 60)) if sec >= 3600 else ("%02d:%02d" % (sec // 60, sec % 60))

    PAUSE_ICONS = (("pause_aspect", "PA_ASPECT"), ("pause_audio", "PA_AUDIO"), ("pause_subs", "PA_SUBS"))
    LIVE_ICONS = (("pause_aspect", "PA_ASPECT"), ("star", "PA_FAV"))
    SERIES_ICONS = (("pause_eps", "PA_EPS"), ("pause_aspect", "PA_ASPECT"), ("pause_audio", "PA_AUDIO"),
                    ("pause_subs", "PA_SUBS"), ("pause_next", "PA_NEXT"))

    def _draw_star(self, cx, cy, k, on):
        """Estrella de favorito (blanca; amarilla si el canal ya es favorito), con el mismo zoom y efecto."""
        g = self.g
        z, dx, dy, ang, sxx, syy = self._icon_xf(k)
        cx, cy = cx + dx, cy + dy
        R, r = 15.0 * z, 6.2 * z
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rad = R if i % 2 == 0 else r
            pts.append((cx + rad * math.cos(a) * sxx, cy + 1 + rad * math.sin(a) * syy))
        col = (255, 205, 40) if on else WHITE
        g.polygon([pts[1], pts[3], pts[5], pts[7], pts[9]], col)       # pentagono central
        for i in range(0, 10, 2):                                      # cinco puntas
            g.polygon([pts[i], pts[(i + 1) % 10], pts[(i - 1) % 10]], col)

    def pause_live(self):
        """True mientras hay un icono elegido con animacion (hay que redibujar cuadro a cuadro)."""
        return True

    def end_pause(self):
        """Al cerrar la pausa se devuelve al Home el icono que estaba elegido."""
        sv = getattr(self, "_pz_saved", None)
        if sv is not None:
            self.sel, self._ic_last, self._ic_t0 = sv
            del self._pz_saved

    EXP_OK, EXP_WARN, EXP_BAD = (120, 220, 150), (255, 200, 70), (255, 110, 110)

    def _exp_info(self, sc):
        """(texto, color) del vencimiento de una lista. sc["exp"] = {"st": load|na|none|ok, "ts": segundos}."""
        ex = sc.get("exp") or {"st": "load"}
        st = ex.get("st")
        if st == "ok" and ex.get("ts"):
            days = int((ex["ts"] - time.time()) // 86400)
            d = time.strftime("%d/%m/%Y", time.localtime(ex["ts"]))
            if days < 0:
                return T("exp_dead", d), self.EXP_BAD
            col = self.EXP_BAD if days <= 7 else self.EXP_WARN if days <= 30 else self.EXP_OK
            return T("exp_left", d, days), col
        if st == "none":
            return T("exp_none"), GRAY
        if st == "na":
            return T("exp_na"), GRAY
        return T("exp_load"), GRAY

    def _battery(self):
        """Porcentaje de bateria de la consola (None si no se puede leer). Se relee cada 20 s."""
        ov = getattr(self, "_bat_override", None)
        if ov is not None:
            return ov
        now = time.time()
        c = getattr(self, "_bat_c", None)
        if c and now - c[0] < 20:
            return c[1]
        v = None
        try:
            base = "/sys/class/power_supply"
            names = sorted(os.listdir(base), key=lambda n: (0 if "bat" in n.lower() else 1, n))
            for n in names:
                fp = os.path.join(base, n, "capacity")
                if os.path.exists(fp):
                    v = max(0, min(100, int(open(fp).read().strip())))
                    break
        except Exception:
            v = None
        self._bat_c = (now, v)
        return v

    def _draw_batt(self, cx, y, pct):
        """Bateria con su porcentaje, centrada en cx, con borde negro (roja por debajo de 20 %)."""
        g = self.g
        txt = "%d%%" % pct
        fs = 19
        tw = g.text_w(txt, fs, True)
        bw, bh = 38, 19
        xr = cx + (bw + 4 + 9 + tw) // 2
        xb = xr - tw - 9 - bw
        by = y - bh // 2
        k = 2
        g.rect(xb - k, by - k, bw + 2 * k, bh + 2 * k, (0, 0, 0), 5)          # borde negro del icono
        g.rect(xb + bw, y - 5 - k, 4 + k, 10 + 2 * k, (0, 0, 0), 2)
        g.rect(xb, by, bw, bh, WHITE, 3)
        g.rect(xb + 2, by + 2, bw - 4, bh - 4, (30, 30, 40), 2)
        fw = int((bw - 8) * pct / 100.0)
        g.rect(xb + 4, by + 4, max(2, fw), bh - 8, (120, 230, 140) if pct > 20 else (255, 90, 90), 1)
        g.rect(xb + bw, y - 4, 3, 8, WHITE, 1)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):   # borde negro del texto
            g.text(txt, xr + dx, y - 11 + dy, fs, (0, 0, 0), "r", True)
        g.text(txt, xr, y - 11, fs, WHITE, "r", True)

    def _title_marquee(self, t, size, maxw, x, y):
        """Titulo que no cabe: se desplaza como un letrero (pausa al inicio y al final)."""
        g = self.g
        tw = g.text_w(t, size, True)
        mq = getattr(self, "_pz_mq", None)
        if mq is None or mq[0] != t:
            mq = self._pz_mq = (t, time.time())
        span = tw - maxw + 8
        SPD, P0, P1 = 45.0, 1.4, 1.2
        per = P0 + span / SPD + P1
        ph = (time.time() - mq[1]) % per
        off = 0 if ph < P0 else min(span, (ph - P0) * SPD)
        g.clip(x - 2, y - 6, maxw + 4, size + 16)
        g.text(t, x + 1 - int(off), y + 1, size, (0, 0, 0), "l", True)
        g.text(t, x - int(off), y, size, WHITE, "l", True)
        g.unclip()

    def draw_pause(self, title, pos, total, focus, frame=None, fid=0, playing=False, seek=False, live=False, fav=False, series=False, restart=False):
        """focus: -1 = Reiniciar, 0 = barra de avance, 1.. = opciones de abajo (series: episodios, pantalla, audio, subs, siguiente).
        Los iconos elegidos usan el mismo efecto que los iconos de la interfaz (Ajustes > Iconos de Interfaz)."""
        title = re.split(r'\s+[\w-]+="|"\s', title or "")[0].strip(' "') or title
        g = self.g
        if not hasattr(self, "_pz_saved"):                         # guarda el icono elegido del Home para devolverlo
            self._pz_saved = (self.sel, self._ic_last, self._ic_t0)
        icons = self.LIVE_ICONS if live else (self.SERIES_ICONS if series else self.PAUSE_ICONS)
        self.sel = "PA_RESTART" if focus == -1 else (icons[focus - 1][1] if focus > 0 else None)
        if self.sel != self._ic_last:                              # al cambiar de icono el efecto empieza de cero
            self._ic_last = self.sel
            self._ic_t0 = time.time()
        tmax = g.w - 48 - (140 if restart else 0)
        key = ("pause", fid, title, restart)
        cached = hasattr(g, "begin_cache") and not g.cache_ok(key) and g.begin_cache(key)
        if cached or not hasattr(g, "begin_cache"):
            g.clear((0, 0, 0))
            if frame is not None:
                g.rgb_frame(frame, g.w, g.h, 0, 0)
            for i in range(14):                                    # degradados oscuros arriba y abajo
                g.dim(0, i * 4, g.w, 4, 170 - i * 12)
            for i in range(25):
                g.dim(0, 332 + i * 6, g.w, 6, 10 + i * 8)
            if g.text_w(title, 24, True) <= tmax:
                g.text(title, 25, 21, 24, (0, 0, 0), "l", True)
                g.text(title, 24, 20, 24, WHITE, "l", True)
            if cached:
                g.end_cache()
        if hasattr(g, "blit_cache"):
            g.blit_cache(key)
        if g.text_w(title, 24, True) > tmax:                       # titulo largo: se mueve como letrero
            self._title_marquee(title, 24, tmax, 24, 20)
        if restart:                                                # Reiniciar: arriba a la derecha, en la linea del titulo
            rw = g.text_w(T("pause_restart"), 15, True)
            rx = 616 - rw
            self._draw_icon("pause_restart", 26, rx - 20, 32, "PA_RESTART")
            g.text(T("pause_restart"), rx + 1, 24, 15, (0, 0, 0), "l", True)
            g.text(T("pause_restart"), rx, 23, 15, WHITE, "l", True)
        cy = 398                                                   # barra de avance
        if live and focus == 0:                                    # en vivo el boton de play/pausa es lo seleccionable
            g.circle(42, cy, 25, (120, 140, 255))
        g.circle(42, cy, 20, (196, 178, 240))
        if playing:                                                # reproduciendo: flecha de play
            g.polygon([(36, cy - 10), (36, cy + 10), (53, cy)], WHITE)
        else:                                                      # en pausa: simbolo de pausa
            g.rect(35, cy - 10, 6, 20, WHITE, 2)
            g.rect(45, cy - 10, 6, 20, WHITE, 2)
        if not seek:                                               # al adelantar/atrasar no hay letrero
            word = T("play_txt") if playing else T("pause_txt")   # letrero en el centro de la imagen
            for dx, dy in ((-2, 2), (2, 2), (0, 3), (2, -2), (-2, -2)):
                g.text(word, g.w // 2 + dx, 196 + dy, 44, (0, 0, 0), "c", True)
            g.text(word, g.w // 2, 196, 44, WHITE, "c", True)
            pct = self._battery()                                  # bateria centrada sobre la palabra
            if pct is not None:
                self._draw_batt(g.w // 2, 170, pct)
        if not live:
            g.text(self._pause_t(pos), 72, cy - 10, 16, WHITE, "l", True)
        bx0, bx1 = (84, 504) if live else (166, 520)
        frac = 1.0 if live else (0.0 if not total else max(0.0, min(1.0, pos / float(total))))
        g.rect(bx0, cy - 2, bx1 - bx0, 4, (150, 152, 166), 2)
        kx = bx0 + int((bx1 - bx0) * frac)
        if kx > bx0:
            g.rect(bx0, cy - 2, kx - bx0, 4, WHITE, 2)
        if focus == 0 and not live:                                # la barra en vivo no se puede tocar
            g.circle(kx, cy, 12, (120, 140, 255))
        g.circle(kx, cy, 8, WHITE)
        if live:
            g.circle(532, cy, 5, (255, 70, 70))                           # punto rojo + EN VIVO
            g.text(T("live_txt"), 616, cy - 10, 16, WHITE, "r", True)
            labels = [T("pause_aspect"), T("pause_fav")]
            icons = self.LIVE_ICONS
        else:
            g.text(self._pause_t(total) if total else "--:--", 616, cy - 10, 16, WHITE, "r", True)
            if series:
                labels = [T("pause_eps"), T("pause_aspect"), T("pause_audio"), T("pause_subs_s"), T("pause_next")]
                icons = self.SERIES_ICONS
            else:
                labels = [T("pause_aspect"), T("pause_audio"), T("pause_subs")]     # pantalla / audio / subtitulos
                icons = self.PAUSE_ICONS
        off = 36 if series else 42
        widths = [off + g.text_w(l, 15, True) for l in labels]
        gap = 44 if not series else max(12, min(44, (604 - sum(widths)) // (len(labels) - 1)))
        x = (g.w - (sum(widths) + gap * (len(labels) - 1))) // 2          # las opciones centradas en la pantalla
        oy = 446
        for i, (nm, k) in enumerate(icons):
            w = widths[i]
            if nm == "star":
                self._draw_star(x + 17, oy, k, fav)
            else:
                self._draw_icon(nm, 30, x + 17, oy, k)                     # zoom + efecto de la interfaz
            g.text(labels[i], x + off, oy - 9, 15, WHITE, "l", True)
            x += w + gap

    # ----- logo del inicio (Ajustes > Apariencia > Logo) -----
    LOGO_PER = ("look", "logo")
    LOGO_CHARS = 9
    LOGO_DY = 9
    LOGO_DEFAULT = "PockTV"
    LOGO_TXT_W = {14: 47, 16: 56, 18: 61, 20: 70, 22: 75, 24: 85, 26: 89, 28: 99, 30: 103, 32: 113, 34: 117, 36: 127, 38: 131, 40: 141, 42: 146, 44: 155}
    LOGO_ICON_W = {'blanco': 41, 'contorno': 41}
    LOGO_MIN, LOGO_MAX = 14, 44
    LOGO_MAXW = 176                                          # ancho maximo del texto (en el inicio y en la previa)
    LOGO_FONTS = {"A": (None, True), "B": ("Poppins-BoldItalic.ttf", True), "C": ("Lora-Variable.ttf", False),
                  "D": ("DejaVuSansMono-Bold.ttf", True), "E": ("Poppins-Medium.ttf", False)}

    def _logo_kind(self):
        k = self.settings.get("logo", "1")
        return k if k in ("1", "2", "3", "per") else "1"

    SEC_CODES = ("def", "A", "B", "C", "D", "E")
    SEC_MIN, SEC_MAX, SEC_DEF = 16, 24, 20
    # tipografia (normal, resaltada), negrita en todo, borde negro
    SEC_STYLES = {"def": (("ComicSansMS.ttf", "ComicSansMS-Bold.ttf"), False, False),
                  "A": (None, False, False),
                  "B": (("Poppins-Medium.ttf", "Poppins-BoldItalic.ttf"), False, False),
                  "C": (("Lora-Variable.ttf", "Lora-Variable.ttf"), False, False),
                  "D": (("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"), False, False),
                  "E": (("Inter-Light.otf", "Inter-Bold.otf"), False, False)}

    def _sec_style(self):
        k = getattr(self, "_sec_ov", None) or self.settings.get("sec_font", "def")
        return k if k in self.SEC_STYLES else "def"

    def _sec_size(self):
        try:
            return max(self.SEC_MIN, min(self.SEC_MAX, int(self.settings.get("sec_size", self.SEC_DEF))))
        except Exception:
            return self.SEC_DEF

    def _sf(self, k, sel):
        """(tamano, negrita, tipografia, borde) de las letras de las secciones; k: g/s = categorias y series, c = canales."""
        face, ball, out = self.SEC_STYLES[self._sec_style()]
        base = self._sec_size()
        size = base if k in ("g", "s") else base - 1
        if face:
            return size, bool(sel), face[1 if sel else 0], out
        return size, bool(sel or ball), None, out

    def _stext(self, t, x, y, k, col, sel, size=None):
        """Texto de una fila (y = arriba de la fila), centrado en vertical y con el estilo elegido."""
        g = self.g
        sz, bold, face, out = self._sf(k, sel)
        sz = size or sz
        y += (ROW_H - 2 - g.text_h(t, sz, bold, face)) // 2 - 1
        if out:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                g.text(t, x + dx, y + dy, sz, (0, 0, 0), "l", bold, face)
        g.text(t, x, y, sz, col, "l", bold, face)

    def _logo_icon(self):
        k = self.settings.get("logo_icon", "1")
        return k if k in ("1", "2", "3") else "1"

    def _logo_text(self):
        return (self.settings.get("logo_text") or self.LOGO_DEFAULT)[:self.LOGO_CHARS]

    def _logo_font(self):
        f = self.settings.get("logo_font", "A")
        return f if f in self.LOGO_FONTS else "A"

    DATE_MIN, DATE_MAX, DATE_DEF = 12, 22, 16

    def _date_size(self):
        try:
            return max(self.DATE_MIN, min(self.DATE_MAX, int(self.settings.get("date_size", self.DATE_DEF))))
        except Exception:
            return self.DATE_DEF

    def _sync_dscale(self):
        clocks.DSCALE = self._date_size() / float(self.DATE_DEF)

    def _logo_size(self):
        try:
            return max(self.LOGO_MIN, min(self.LOGO_MAX, int(self.settings.get("logo_size", 32)) // 2 * 2))
        except Exception:
            return 32

    def _logo_style(self):
        return "c" if self.settings.get("logo_style") == "c" else "w"

    def _logo_is_default(self, txt):
        return txt.strip().lower() == self.LOGO_DEFAULT.lower()

    def _logo_cfg(self, txt=None):
        """(icono, texto, usa_imagen, tamano, ancho_texto): el texto se achica solo si no cabe en el espacio."""
        g = self.g
        txt = txt or self._logo_text()
        size = self._logo_size()
        img = self._logo_is_default(txt)
        face, bold = "ComicSansMS-Bold.ttf", True
        tw = lambda sz: self.LOGO_TXT_W.get(sz, 0) if img else g.text_w(txt, sz, bold, face)
        while size > 14 and tw(size) > self.LOGO_MAXW:
            size -= 2
        return ("logo_" + ("contorno" if self._logo_style() == "c" else "blanco"), txt, img, size, tw(size))

    def _logo_width(self, cfg):
        return self.LOGO_ICON_W["contorno" if cfg[0].endswith("contorno") else "blanco"] + 12 + cfg[4]

    def _draw_logo(self, ox, cy, cfg):
        """Mascota (alineada con el reloj) + nombre. Devuelve el borde derecho del texto."""
        g = self.g
        icon, txt, img, size, tw = cfg
        iw = self.LOGO_ICON_W["contorno" if icon.endswith("contorno") else "blanco"]
        g.image(icon, 52, ox + iw // 2 + 1, cy + 1, WHITE)
        tx = ox + iw + 12
        if img:
            g.image("logo_txt", size, tx + tw // 2, cy + 3, WHITE)
        else:
            th = g.text_h(txt, size, True, "ComicSansMS-Bold.ttf")
            g.text(txt, tx, cy - th // 2 + 1 + self.LOGO_DY - 6, size, WHITE, "l", True, "ComicSansMS-Bold.ttf")
        return tx + tw

    def _draw_logo_preview(self, code, x, y, W, H):
        g = self.g
        g.rect(x + 3, y + 3, W - 6, H - 6, (12, 15, 34), 6)
        cfg = self._logo_cfg()
        self._draw_logo(x + (W - self._logo_width(cfg)) // 2, y + H // 2 - 1, cfg)
        g.outline(x, y, W, H, WHITE, 3, 8)

    def _draw_sec_preview(self, code, x, y, W, H):
        """Recuadro con filas de ejemplo (categoria elegida + otras) en el estilo y tamano de letra de las secciones."""
        g = self.g
        g.rect(x + 3, y + 3, W - 6, H - 6, (12, 15, 34), 6)
        self._sec_ov = None if code == "cur" else code
        try:
            names = ("Noticias", "Deportes", "Películas", "Música", "Infantil")
            ry = y + 12
            for n, nm in enumerate(names):
                sel = (n == 1)
                if sel:
                    g.gradient(x + 10, ry, W - 20, ROW_H - 2, SET_C1, SET_C2, True, 4)
                self._stext(nm, x + 22, ry, "g", WHITE if sel else SOFT, sel)
                ry += ROW_H
        finally:
            self._sec_ov = None
        g.outline(x, y, W, H, WHITE, 3, 8)

    def _draw_clock_preview(self, code, x, y, W, H):
        """Recuadro del reloj: el estilo elegido, con la hora y la fecha reales, centrado."""
        g = self.g
        self._sync_dscale()
        t = time.localtime()
        if self.settings.get("clock") == "12":
            tm = "%d:%02d" % (t.tm_hour % 12 or 12, t.tm_min)
            suf = T("pm") if t.tm_hour >= 12 else T("am")
        else:
            tm, suf = "%02d:%02d" % (t.tm_hour, t.tm_min), ""
        dtxt = date_text(t.tm_wday, t.tm_mday, t.tm_mon, t.tm_year, self._date_code())
        g.rect(x + 3, y + 3, W - 6, H - 6, (12, 15, 34), 6)
        cy = y + H // 2
        dim = (70, 78, 100)
        if code == "default":
            # mismas medidas que en el inicio; el bloque (wifi + hora + fecha) queda centrado en el recuadro
            sw = g.text_w(suf, 18, True) + 8 if suf else 0
            tw = g.text_w(tm, 44, True)
            dsz = self._date_size()
            while dsz > 9 and g.text_w(dtxt, dsz) > W - 30:
                dsz -= 1
            dw = g.text_w(dtxt, dsz)
            total = max(tw + sw + 54, dw)                    # 54 = wifi (22) + separacion (32)
            R = x + W // 2 + total // 2
            oy = cy - 57                                     # el bloque va de y=28 a y=86 en el inicio
            if suf:
                g.text(suf, R, oy + 38, 18, WHITE, "r", True)
            g.text(tm, R - sw, oy + 20, 44, WHITE, "r", True)
            g.text(dtxt, R, oy + 72, dsz, (214, 218, 232), "r")
            wx = R - sw - tw - 32
            ok = g.image("wifi_0", 38, wx, oy + 44, WHITE, 1.14)
            for k in (1, 2):
                ok = g.image("wifi_%d" % k, 38, wx, oy + 44, WHITE, 1.14) and ok
        else:
            d = clocks.Dry(g)
            _wx, left = clocks.draw(d, code, 0, 0, 1.0, tm, suf, dtxt, 2, dim)
            kk = min(1.0, (W - 30) / float(-left))       # con la fecha mas larga se reduce para no salirse
            _wx, left = clocks.draw(d, code, 0, 0, kk, tm, suf, dtxt, 2, dim)
            R = x + W // 2 + (-left) // 2                # el bloque completo queda centrado
            clocks.draw(g, code, R, int(cy - 57 * kk), kk, tm, suf, dtxt, 2, dim)
        g.outline(x, y, W, H, WHITE, 3, 8)

    def _tile(self, cat, outline=True):
        g = self.g
        x, y, w, h = TILE_RECT[cat]
        st = TILE[cat]
        g.gradient(x, y, w, h, st["c1"], st["c2"], st["horizontal"], TILE_RADIUS)
        count = self.count(cat)
        label = T("tile_" + cat).upper()
        cx = x + w // 2
        unit = "%d %s" % (count, T("unit_" + cat))
        if cat == "FAV":
            if not self.g.image("star", 44, x + 44, y + h // 2, WHITE):
                self.draw_star(x + 44, y + h // 2, 22, WHITE)
            g.text(label, x + 84, y + 8, 22, WHITE, "l", True, "title")
            g.text(unit, x + 84, y + 38, 14, SOFT, "l")
        else:
            # TV, Peliculas y Series: mismo tamano de icono y de letra
            name = {"TV": "tv_en_vivo", "PELIS": "peliculas", "SERIES": "series"}[cat]
            top = y + (h - TILE_BLOCK) // 2          # bloque icono + titulo + contador, centrado
            if not g.image(name, TILE_ICON, cx, top + TILE_ICON // 2):
                self._fallback_icon(cat, cx, top + TILE_ICON // 2)
            g.text(label, cx, top + TILE_ICON + 4, TILE_FONT, WHITE, "c", True, "title")
            g.text(unit, cx, top + TILE_ICON + 4 + TILE_FONT + 3, 13, SOFT, "c")
        if self.sel == cat and outline:
            g.outline(x - 4, y - 4, w + 8, h + 8, WHITE, 4, TILE_RADIUS + 4)

    def _fallback_icon(self, cat, cx, cy):
        g = self.g
        if cat == "TV":
            icons.tv(g, cx, cy, 52, (44, 104, 200))
        elif cat == "PELIS":
            icons.movie(g, cx, cy, 44)
        else:
            icons.clapper(g, cx, cy, 44, _mix(TILE[cat]["c1"], TILE[cat]["c2"], 0.5))

    def _magnifier(self, x, y, c):
        self.g.circle(x, y, 7, c, 2)
        self.g.line((x + 5, y + 5), (x + 12, y + 12), c, 3)

    def marquee(self, text, size, maxw, bold=False):
        """Texto largo en la fila elegida: se desplaza como un letrero hasta verse completo."""
        g = self.g
        if g.text_w(text, size, bold) <= maxw:
            return text
        self.anim = True
        el = time.time() - self.sel_t
        gap = text + "     "
        step = int((el - 1.0) / 0.16) if el > 1.0 else 0
        pos = step % len(gap)
        rot = gap[pos:] + gap[:pos]
        out = ""
        for ch in rot:
            if g.text_w(out + ch, size, bold) > maxw:
                break
            out += ch
        return out

    @staticmethod
    def _blink():
        return int(time.time() * 1.6) % 2 == 0

    def draw_support(self):
        """Acerca de: logo, version, autor, apoyo (QR de Ko-fi) y boton de actualizaciones."""
        import qr_kofi, updater
        g = self.g
        st = updater.ST
        self._background()
        g.gradient(0, 0, g.w, 62, SET_C1, SET_C2, True)
        g.text(T("cat_support"), 24, 16, 28, WHITE, "l", True)
        self._draw_logo(24, 108, self._logo_cfg())          # el mismo logo (mascota + nombre) que muestra la app
        g.text(T("about_ver") % updater.VERSION, 24, 138, 18, GRAY, "l", False)
        g.text(T("about_by"), 24, 164, 18, GRAY, "l", False)
        g.rect(24, 200, 290, 1, LINE)
        g.text("\u2665 " + T("sup_t1"), 24, 216, 22, GOLD, "l", True)
        def wrap(txt, size, maxw, y, col, lh):
            line = ""
            for w in txt.split():
                t = (line + " " + w).strip()
                if line and g.text_w(t, size, False) > maxw:
                    g.text(line, 24, y, size, col, "l", False)
                    y += lh
                    line = w
                else:
                    line = t
            if line:
                g.text(line, 24, y, size, col, "l", False)
                y += lh
            return y
        y_ = wrap(T("about_t2"), 18, 290, 254, WHITE, 25)
        wrap(T("sup_t3"), 16, 290, y_ + 8, GRAY, 22)
        # tarjeta blanca con el codigo (4 modulos de margen: lo pide el estandar QR)
        n = len(qr_kofi.ROWS)
        mod = 6
        quiet = 4 * mod
        side = n * mod + 2 * quiet
        x0, y0 = 342, 92
        g.rect(x0, y0, side, side, (255, 255, 255), 8)
        for r, row in enumerate(qr_kofi.ROWS):
            c = 0
            while c < n:                                   # tramos horizontales: menos dibujos
                if row[c] == "1":
                    e = c
                    while e < n and row[e] == "1":
                        e += 1
                    g.rect(x0 + quiet + c * mod, y0 + quiet + r * mod, (e - c) * mod, mod, (0, 0, 0))
                    c = e
                else:
                    c += 1
        g.text(qr_kofi.SHOW, x0 + side // 2, y0 + side + 12, 18, WHITE, "c", True)
        # boton de actualizaciones
        s_ = st["status"]
        lab = {"checking": T("au_checking"), "ok": T("au_ok"), "new": T("au_new") % st["ver"],
               "downloading": T("au_down") % int(st["prog"] * 100), "installing": T("au_inst"),
               "done": T("au_done_btn")}.get(s_, T("au_check"))
        note = {"error": T("au_err_" + ("net" if st["msg"] == "sin_conexion" else "fail")),
                "new": T("au_ask"), "done": T("au_done")}.get(s_, "")
        if note:
            g.text(note, 24, 350, 15, (255, 120, 110) if s_ == "error" else WHITE, "l", False)
        g.gradient(24, 376, 290, 44, (255, 225, 110), (235, 150, 20), True, 6)
        if s_ == "downloading":
            g.rect(24 + 4, 376 + 36, int(282 * st["prog"]), 4, (40, 25, 0))
        g.text(lab, 24 + 145, 376 + 10, 20, (40, 25, 0), "c", True)
        self.mt(T("about_hint"), 24, 440, 14, GRAY, "l", False, 592)

    def draw_menu(self):
        """Ajustes (arbol) y Cambiar de lista."""
        g = self.g
        self._background()
        g.gradient(0, 0, g.w, 62, SET_C1, SET_C2, True)
        self.anim = False
        self.pv_on = False
        pv_code = None
        pv_dy = 0
        mode = "menu"
        if self.state == "lists":
            title = T("lists_title")
            rows = [(sc["name"], T("active") if sc["id"] == self.settings.get("source", "main") else "",
                     self._exp_info(sc)[0]) for sc in self.sources]
            mode = "lists"
            sel = self.m_idx
            hint = T("lists_hint")
            marks = None
        else:
            title = self._title()
            kind = self._kind(self.set_path)
            sel = self.set_idx[-1]
            hint = T("set_hint_menu") if kind == "menu" else T("set_hint")
            if kind == "menu" and self.moving:
                hint = T("move_hint")
            marks = None
            if kind == "menu":
                rows = [(lab, val, "") for _, lab, val in self._menu_rows(self.set_path)]
                mode = "menu"
                if tuple(self.set_path) == self.LOGO_PER:
                    pv_code = ("lg", "cur")
                    hint = T("lg_hint")
                elif tuple(self.set_path) == ("look", "fonts"):
                    pv_code = ("sf", "cur")
                    hint = T("lg_hint")
                elif tuple(self.set_path) == ("clock",):
                    pv_code = ("ck", self._clock_style())          # previa de la fecha, debajo de las filas
                    pv_dy = 70
            elif kind == "single":
                sk = self.SINGLE[tuple(self.set_path)]
                cur = self._current(sk)
                opts = self._options(sk)
                side = sk in ("chan", "fmt")
                rows = [(o[1], o[2] if side else "", "" if side else o[2]) for o in opts]
                marks = [("dot" if o[0] == cur else None) for o in opts]
                mode = "single"
                if sk == "look_logo" and opts:
                    pv_code = ("lg", opts[min(sel, len(opts) - 1)][0])
                elif sk == "lg_icon" and opts:
                    pv_code = ("lg", "i" + opts[min(sel, len(opts) - 1)][0])
                elif sk == "lg_font" and opts:
                    pv_code = ("lg", "f" + opts[min(sel, len(opts) - 1)][0])
                elif sk in ("cards", "look_icons") and opts:
                    pv_code = (("fx" if sk == "cards" else "ic"), opts[min(sel, len(opts) - 1)][0])
                elif sk == "look_cd" and opts:
                    pv_code = ("ck", opts[min(sel, len(opts) - 1)][0])
                elif sk in ("look_fonts", "sf_row") and opts:
                    pv_code = ("sf", opts[min(sel, len(opts) - 1)][0])
            else:
                key, mx = self.MULTI[tuple(self.set_path)]
                lst = self._prio(key)
                opts = self._multi_options()
                rows = [(o[1], "", "") for o in opts]
                marks = []
                for o in opts:
                    if o[0] == "all":
                        marks.append("dot" if not lst else None)
                    else:
                        marks.append(str(lst.index(o[0]) + 1) if o[0] in lst else None)
                hint = T("multi_hint")
                mode = "multi"
        self.mt(title, 24, 14, 28, WHITE, "l", True, 600)
        if not rows:
            g.text(T("no_entries"), g.w // 2, 200, 20, SOFT, "c")
        big = (mode == "lists")                     # lista de listas: letra mas grande, filas mas altas
        nvis, pitch, rh = (6, 56, 52) if big else (7, 50, 46)
        top = max(0, min(sel - (nvis - 3), len(rows) - nvis)) if len(rows) > nvis else 0
        for i in range(top, min(len(rows), top + nvis)):
            lab, val, desc = rows[i]
            y = 80 + (i - top) * pitch
            about = (mode == "menu" and not self.set_path and lab == T("cat_support"))
            if i == sel and about:
                g.gradient(16, y, g.w - 32, rh, (255, 225, 110), (235, 150, 20), True, 4)
                col, gcol = (40, 25, 0), (70, 45, 0)
            elif i == sel:
                g.gradient(16, y, g.w - 32, rh, SET_C1, SET_C2, True, 4)
                col, gcol = WHITE, SOFT
            else:
                g.rect(16, y + rh - 1, g.w - 32, 1, LINE)
                col, gcol = SOFT, GRAY
            tx = 32
            if about and __import__("updater").ST["status"] == "new":
                self.anim = True                               # el puntito parpadea
                if self._blink():
                    g.circle(g.w - 84, y + rh // 2, 10, (255, 50, 50))
            if marks is not None:
                tx = 62
                mk = marks[i]
                if mk == "dot":
                    g.circle(40, y + 23, 8, WHITE)
                elif mk:
                    g.circle(40, y + 23, 12, WHITE)
                    g.text(mk, 40, y + 23 - 10, 18, (0, 0, 0), "c", True)
            avail = (g.w - 36 - tx) - (g.text_w(val, 18) + 24 if val else 0)
            if val:
                avail = min(avail, 330)          # las filas con valor muestran un letrero que se desplaza
            if pv_code is not None:
                avail = min(avail, 318 - tx)     # el recuadro de previa tapa la derecha: el texto se desplaza antes de llegar
            if desc and mode in ("single", "lists"):
                if mode == "lists":
                    gcol = self._exp_info(self.sources[i])[1]
                    if i == sel and gcol == GRAY:
                        gcol = SOFT
                ls, ds, dy = (24, 16, 31) if big else (20, 13, 28)
                if i == sel:
                    self.mt(lab, tx, y + (3 if big else 5), ls, col, "l", True, 400)
                    self.mt(desc, tx, y + dy, ds, gcol, "l", False, 560 - tx)
                else:
                    g.text(self.fit(lab, ls, 400), tx, y + (3 if big else 5), ls, col, "l", False)
                    g.text(self.fit(desc, ds, 560 - tx), tx, y + dy, ds, gcol, "l")
            else:
                if i == sel:
                    self.mt(lab, tx, y + 11, 20, col, "l", True, avail)
                else:
                    g.text(self.fit(lab, 20, avail), tx, y + 11, 20, col, "l", False)
            bar = None
            if val and mode == "menu":
                if pv_code == ("lg", "cur") and i == 1:
                    bar = (self._logo_size(), self.LOGO_MIN, self.LOGO_MAX, 2)
                elif tuple(self.set_path) == ("clock",) and i == 2:
                    bar = (self._date_size(), self.DATE_MIN, self.DATE_MAX, 1)
                elif tuple(self.set_path) == ("look", "fonts") and i == 1:
                    bar = (self._sec_size(), self.SEC_MIN, self.SEC_MAX, 1)
            if bar:
                cur, lo, hi, stp = bar                          # barra con marcas, numeros y perilla
                bw, bx = 140, g.w - 36 - 140
                frac = (cur - lo) / float(hi - lo)
                by = y + 21
                g.rect(bx, by, bw, 6, (60, 66, 96) if i == sel else (46, 50, 76), 3)
                g.rect(bx, by, max(6, int(bw * frac)), 6, WHITE if i == sel else GRAY, 3)
                nst = (hi - lo) // stp
                for k in range(nst + 1):                        # una marca por cada escala
                    tx_ = bx + int(round(bw * k / float(nst)))
                    g.rect(tx_, by + 8, 1, 3 if k % 5 else 5, gcol)
                kx = bx + int(bw * frac)
                g.circle(kx, by + 3, 8 if i == sel else 6, WHITE)
                for num, nx in ((lo, bx), (hi, bx + bw)):
                    if abs(nx - kx) > 22:
                        g.text(str(num), nx, y + 3, 13, gcol, "c")
                g.text(str(cur), kx, y + 1, 16, WHITE if i == sel else SOFT, "c", True)
            elif val:
                if i == sel:
                    self.mt(val, g.w - 36, y + 13, 18, gcol, "r", False, 330)
                else:
                    g.text(self.fit(val, 18, 330), g.w - 36, y + 13, 18, gcol, "r")
            elif self.state == "settings" and mode == "menu":
                if not (self.moving and i == sel):
                    g.text(">", g.w - 36, y + 11, 20, gcol, "r")
            if self.moving and i == sel and self.state == "settings" and mode == "menu":
                g.outline(12, y - 4, g.w - 24, 54, WHITE, 3, 10)
                ax, ay = g.w - 46, y + 23
                g.polygon([(ax - 9, ay - 3), (ax + 9, ay - 3), (ax, ay - 14)], WHITE)
                g.polygon([(ax - 9, ay + 3), (ax + 9, ay + 3), (ax, ay + 14)], WHITE)
        self._pv_dy = pv_dy
        self._pv_pending = pv_code                      # la previa se dibuja aparte, cuadro a cuadro (sin rehacer la pantalla)
        if self.state == "lists" and self.confirm_del:
            g.rect(90, 150, g.w - 180, 170, (10, 12, 28), 12)
            g.outline(90, 150, g.w - 180, 170, WHITE, 3, 12)
            g.text(T("del_ask"), g.w // 2, 168, 28, WHITE, "c", True)
            nm = next((sc["name"] for sc in self.sources if sc["id"] == self.confirm_del), "")
            self.mt(nm, g.w // 2, 210, 16, GRAY, "c", False, g.w - 220)
            for k, lab in enumerate((T("yes"), T("no"))):
                bx = 150 + k * 190
                if self.conf_sel == k:
                    g.gradient(bx, 250, 150, 48, SET_C1, SET_C2, True, 6)
                else:
                    g.rect(bx, 250, 150, 48, (40, 44, 70), 6)
                g.text(lab, bx + 75, 250 + 11, 22, WHITE, "c", self.conf_sel == k)
        if self.state == "lists" and len(self.sources) <= 1 and not self.confirm_del:
            self.mt(T("lists_more"), 24, 410, 14, GOLD, "l", False, 592)
        if self.notice and self.state == "settings":
            self.mt(self.notice, 24, 440, 14, WARN, "l", False, 592)
        else:
            if self.notice:
                self.mt(self.notice, 24, 416, 14, WARN, "l", False, 592)
            self.mt(hint, 24, 440, 14, GRAY, "l", False, 592)

    def _split_sig(self):
        c = self.cat
        return (c, self.col, self.gidx, self.gtop, self.gname, self.sname, self.sidx, self.stop, self.sq, self.idx, self.top, id(self.view),
                len(self.view), self.gquery.get(c, ""), self.query.get(c, ""), len(self.favs), self.notice,
                get_lang(), self._mq_target() is not None, self._sec_style(), self._sec_size())

    def _draw_split(self):
        g = self.g
        if hasattr(g, "begin_cache") and not getattr(self, "_split_broken", False):
            try:
                sig = self._split_sig()
                if not (g.cache_ok("split") and sig == getattr(self, "_split_last", None)):
                    if not g.begin_cache("split"):
                        raise RuntimeError("sin cache")
                    self._split_static()
                    g.end_cache()
                    self._split_last = sig
                g.blit_cache("split")
                self._split_live()
                return
            except Exception:
                self._split_broken = True
                if hasattr(g, "abort_cache"):
                    g.abort_cache()
        self._split_static()
        self._split_live()

    def _row_fav(self, k, name):
        if self.cat == "FAV":
            return False
        if k == "g":
            return self._gfav_key(self.cat, name) in self.favs
        return self._sfav_key(self.cat, self.gname, name) in self.favs

    def _gtext(self, name, cnt, y, col, cc, sel, name_on=True, k="g"):
        g = self.g
        x, w = self._geo()[k]
        single = self.cat == "FAV" and k == "g" and name.startswith("C|")
        cw = 16 if single else g.text_w(str(cnt), 13)
        if single:                                               # canal suelto: estrella en vez de cantidad
            self.draw_star(x + w - 16, y + 17, 7, GOLD if not sel else WHITE)
        else:
            g.text(str(cnt), x + w - 8, y + 10, 13, cc, "r")
        off = 0
        if self._row_fav(k, name):                               # categoria / serie en favoritos
            self.draw_star(x + 14, y + 17, 6, GOLD if not sel else WHITE)
            off = 14
        if self.cat == "FAV" and k == "g":                       # Favoritos: nombre y, debajo, de que lista viene
            disp = self._gdisp(name)
            if name_on:
                sz, bd, fc, _o = self._sf(k, sel)
                sz = min(sz, 16)
                g.text(self.fit(disp, sz, w - 28 - cw, bd, fc), x + 10, y + 4, sz, col, "l", bd, fc)
            kd = self._gkind(name)
            if kd:
                g.text(kd, x + 10, y + 22, 11, cc, "l")
            return
        if name_on:
            sz, bd, fc, _o = self._sf(k, sel)
            self._stext(self.fit(name, sz, w - 28 - cw - off, bd, fc), x + 10 + off, y, k, col, sel)

    def _ctext(self, e, y, col, sel, name_on=True):
        g = self.g
        x, w = self._geo()["c"]
        x0 = x + 14
        if self._is_fav(e):
            self.draw_star(x + 14, y + 17, 7, GOLD if not sel else WHITE)
            x0 = x + 28
        if name_on:
            nm = self._row_label(e)
            sz, bd, fc, _o = self._sf("c", sel)
            self._stext(self.fit(nm, sz, x + w - 8 - x0, bd, fc), x0, y, "c", col, sel)

    def _mq_target(self):
        """Fila del cursor si su nombre no cabe: (tipo, indice, y, texto, x, ancho, tam)."""
        g = self.g
        geo = self._geo()
        if self.col == 0 or (self._ser() and self.col == 1):
            if self.col == 0:
                lst, i, top, k = self.groups_of(self.cat), self.gidx, self.gtop, "g"
            else:
                lst, i, top, k = self.shows_of(), self.sidx, self.stop, "s"
            if not (0 <= i < len(lst)) or not (top <= i < top + VISIBLE):
                return None
            name, cnt = lst[i]
            single = self.cat == "FAV" and k == "g" and name.startswith("C|")
            name = self._gdisp(name) if k == "g" else name
            cw = 16 if single else g.text_w(str(cnt), 13)
            x, w = geo[k]
            off = 14 if self._row_fav(k, name) else 0
            avail = w - 28 - cw - off
            sz, bd, fc, _o = self._sf(k, True)
            if self.cat == "FAV" and k == "g":
                sz = min(sz, 16)
            if g.text_w(name, sz, bd, fc) <= avail:
                return None
            return (k, i, LIST_Y + (i - top) * ROW_H, name, x + 10 + off, avail, sz)
        i = self.idx
        if not (0 <= i < len(self.view)) or not (self.top <= i < self.top + VISIBLE):
            return None
        e = self.view[i]
        x, w = geo["c"]
        x0 = x + 28 if self._is_fav(e) else x + 14
        avail = x + w - 8 - x0
        nm = self._row_label(e)
        sz, bd, fc, _o = self._sf("c", True)
        if g.text_w(nm, sz, bd, fc) <= avail:
            return None
        return ("c", i, LIST_Y + (i - self.top) * ROW_H, nm, x0, avail, sz)

    def _mq_offset(self, now, over):
        """Desplazamiento suave (pixeles): pausa, avanza, pausa, regresa."""
        t = now - self._mq_t0
        d = over / 45.0                                    # 45 px por segundo
        per = 2 * (1.2 + d)
        t %= per
        if t < 1.2:
            return 0.0
        if t < 1.2 + d:
            return 45.0 * (t - 1.2)
        if t < 2.4 + d:
            return float(over)
        return over - 45.0 * (t - 2.4 - d)

    def _split_live(self):
        self._split_live2()
        self._mq_flush()                                    # textos largos de la pantalla: letrero

    def _split_live2(self):
        """Lo unico que cambia cada cuadro: el brillo que cruza el marcador activo."""
        g = self.g
        if not hasattr(g, "glow"):
            return
        now = getattr(self, "clock", time.time)()
        mt = self._mq_target()
        mkey = (self.cat, self.col, self.gidx, self.sidx, self.idx, mt[3] if mt else None)
        if mkey != getattr(self, "_mq_key", None):
            self._mq_key = mkey
            self._mq_t0 = now
        geo = self._geo()
        row = None
        if self.col == 0:
            gl = self.groups_of(self.cat)
            if 0 <= self.gidx < len(gl) and self.gtop <= self.gidx < self.gtop + VISIBLE:
                row = ("g", geo["g"], LIST_Y + (self.gidx - self.gtop) * ROW_H, gl[self.gidx])
        elif self._ser() and self.col == 1:
            sh = self.shows_of()
            if 0 <= self.sidx < len(sh) and self.stop <= self.sidx < self.stop + VISIBLE:
                row = ("s", geo["s"], LIST_Y + (self.sidx - self.stop) * ROW_H, sh[self.sidx])
        elif 0 <= self.idx < len(self.view) and self.top <= self.idx < self.top + VISIBLE:
            row = ("c", geo["c"], LIST_Y + (self.idx - self.top) * ROW_H, self.view[self.idx])
        if row is None:
            self._mq_draw(mt, now)
            return
        k, (x, w), y, it = row
        h = ROW_H - 2
        pos = (now * 0.8) % 1.5 - 0.25                             # franja de brillo que cruza la fila
        cx = x + int(pos * w)
        for bw, al in ((60, 22), (38, 34), (18, 52)):
            x0, x1 = max(x, cx - bw // 2), min(x + w, cx + bw // 2)
            if x1 > x0:
                g.glow(x0, y, x1 - x0, h, al)
        same = mt is not None and mt[2] == y
        if k == "c":
            self._ctext(it, y, WHITE, True, not same)
        else:
            self._gtext(it[0], it[1], y, WHITE, WHITE, True, not same, k)
        self._mq_draw(mt, now)

    def _mq_draw(self, mt, now):
        """Nombre largo de la fila del cursor: se desplaza como banner, suave, recortado a su espacio."""
        if mt is None or not hasattr(self.g, "clip"):
            return
        g = self.g
        kind, i, y, text, x, avail, size = mt
        sz, bd, fc, out = self._sf(kind, True)
        over = g.text_w(text, size, bd, fc) - avail
        off = self._mq_offset(now, over)
        ty = y + 4 if (self.cat == "FAV" and kind == "g") else y + (ROW_H - 2 - g.text_h(text, size, bd, fc)) // 2 - 1
        g.clip(x, y, avail, ROW_H - 2)
        if out:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                g.text(text, x - int(off) + dx, ty + dy, size, (0, 0, 0), "l", bd, fc)
        g.text(text, x - int(off), ty, size, WHITE, "l", bd, fc)
        g.unclip()

    def _split_static(self):
        self._mq_items = []
        self._mq_defer = self._mq_items
        try:
            self._split_static2()
        finally:
            self._mq_defer = None

    def _split_static2(self):
        g = self.g
        st = TILE[self.cat]
        n = len(self.view)
        ser = self._ser()
        geo = self._geo()
        gx, gw = geo["g"]
        cx_, cw_ = geo["c"]
        mt = self._mq_target()
        self._background()
        g.gradient(0, 0, g.w, 62, st["c1"], st["c2"], True)
        title = T("tile_" + self.cat)
        g.text(title, 24, 14, 30, WHITE, "l", True)
        gl = self.groups_of(self.cat)
        sh = self.shows_of() if ser else []
        if self.col == 0:
            cnt_txt = "%d / %d" % (self.gidx + 1, len(gl)) if gl else "0"
        elif ser and self.col == 1:
            cnt_txt = "%d / %d" % (self.sidx + 1, len(sh)) if sh else "0"
        else:
            cnt_txt = "%d / %d" % (self.idx + 1, n) if n else "0"
        g.text(cnt_txt, 616, 20, 20, WHITE, "r")
        if self.col == 0:
            q = self.gquery.get(self.cat, "")
        elif ser and self.col == 1:
            q = self.sq
        else:
            q = self.query.get(self.cat, "")
        if q:
            tx = 24 + g.text_w(title, 30, True) + 22
            self._magnifier(tx + 8, 28, WHITE)
            self.mt('"%s"' % q, tx + 30, 20, 18, WHITE, "l", False, 400 - (tx + 30))
        if not gl and self.cat == "FAV" and not self.gquery.get(self.cat):
            g.text(T("no_favs"), g.w // 2, 180, 22, SOFT, "c")
            g.text(T("no_favs_1"), g.w // 2, 224, 14, GRAY, "c")
            g.text(T("no_favs_2"), g.w // 2, 246, 14, GRAY, "c")
        elif not gl:
            g.text(T("no_results", self.gquery.get(self.cat, "")) if self.gquery.get(self.cat) else T("no_entries"),
                   gx + gw // 2, 190, 14, SOFT, "c")
        for row in range(VISIBLE):
            i = self.gtop + row
            if i >= len(gl):
                break
            name, cnt = gl[i]
            y = LIST_Y + row * ROW_H
            cur = (i == self.gidx and self.col == 0)
            chosen = (name == self.gname)
            sel = cur or chosen
            if cur or chosen:                                  # categorias: siempre azul (con borde blanco si tiene el cursor)
                g.gradient(gx, y, gw, ROW_H - 2, BL1, BL2, True)
                if cur:
                    g.outline(gx, y, gw, ROW_H - 2, WHITE, 2, 0)
                col, cc = WHITE, SOFT
            else:
                g.rect(gx, y + ROW_H - 2, gw, 1, LINE)
                col, cc = SOFT, GRAY
            self._gtext(name, cnt, y, col, cc, sel, not (mt and mt[0] == "g" and mt[1] == i))
        if ser:
            sx, sw = geo["s"]
            if not sh and gl:
                g.text(T("no_results", self.sq) if self.sq else T("no_entries"), sx + sw // 2, 190, 14, SOFT, "c")
            for row in range(VISIBLE):
                i = self.stop + row
                if i >= len(sh):
                    break
                name, cnt = sh[i]
                y = LIST_Y + row * ROW_H
                cur = (i == self.sidx and self.col == 1)
                chosen = (name == self.sname)
                if cur or chosen:                              # series: siempre naranja
                    g.gradient(sx, y, sw, ROW_H - 2, OR1, OR2, True)
                    if cur:
                        g.outline(sx, y, sw, ROW_H - 2, WHITE, 2, 0)
                    col, cc = WHITE, SOFT
                else:
                    g.rect(sx, y + ROW_H - 2, sw, 1, LINE)
                    col, cc = SOFT, GRAY
                self._gtext(name, cnt, y, col, cc, cur or chosen, not (mt and mt[0] == "s" and mt[1] == i), "s")
        elif n == 0 and gl:
            g.text(T("no_results", self.query.get(self.cat, "")) if self.query.get(self.cat) else T("no_entries"),
                   cx_ + cw_ // 2, 190, 14, SOFT, "c")
        cc1, cc2 = (GR1, GR2) if ser else (OR1, OR2)
        for row in range(VISIBLE):
            i = self.top + row
            if i >= n:
                break
            e = self.view[i]
            y = LIST_Y + row * ROW_H
            cur = (i == self.idx and self.col == self._last_col())
            sel = cur
            if cur:                                            # canales: naranja; episodios: gris oscuro
                g.gradient(cx_, y, cw_, ROW_H - 2, cc1, cc2, True)
                g.outline(cx_, y, cw_, ROW_H - 2, WHITE, 2, 0)   # marco blanco como categorias y series
                col = WHITE
            else:
                g.rect(cx_, y + ROW_H - 2, cw_, 1, LINE)
                col = SOFT
            self._ctext(e, y, col, sel, not (mt and mt[0] == "c" and mt[1] == i))
        if n > VISIBLE:
            track_h = VISIBLE * ROW_H
            thumb_h = max(18, int(track_h * VISIBLE / float(n)))
            thumb_y = LIST_Y + int((track_h - thumb_h) * self.top / float(max(1, n - VISIBLE)))
            g.rect(612, LIST_Y, 3, track_h, LINE)
            g.rect(612, thumb_y, 3, thumb_h, SOFT)
        if self.notice:
            self.mt(self.notice, 24, 416, 14, WARN, "l", False, 592)
        self.mt(T("split_hint"), 24, 440, 14, GRAY, "l", False, 592)

    def draw_list(self):
        if self.cat in SPLIT:
            return self._draw_split()
        g = self.g
        st = TILE[self.cat]
        items = self.view
        n = len(items)
        q = self.query.get(self.cat, "")
        self._background()
        # Cabecera
        g.gradient(0, 0, g.w, 62, st["c1"], st["c2"], True)
        title = T("tile_" + self.cat)
        g.text(title, 24, 14, 30, WHITE, "l", True)
        counter = "%d / %d" % (self.idx + 1, n) if n else "0"
        g.text(counter, 616, 20, 20, WHITE, "r")
        if n:
            lt = letter_of(items[self.idx])
            lw = g.text_w(counter, 20) + 16
            g.rect(616 - lw - 34, 18, 28, 28, (255, 255, 255), 6)
            g.text(lt, 616 - lw - 20, 20, 20, (30, 30, 60), "c", True)
        if q:
            tx = 24 + g.text_w(title, 30, True) + 22
            self._magnifier(tx + 8, 28, WHITE)
            self.mt('"%s"' % q, tx + 30, 20, 18, WHITE, "l", False, 616 - 80 - (tx + 30))
        # Filas
        if n == 0:
            if q:
                g.text(T("no_results", q), g.w // 2, 190, 20, SOFT, "c")
                g.text(T("no_results_hint"), g.w // 2, 230, 14, GRAY, "c")
            elif self.cat == "FAV":
                g.text(T("no_favs"), g.w // 2, 180, 22, SOFT, "c")
                g.text(T("no_favs_1"), g.w // 2, 224, 14, GRAY, "c")
                g.text(T("no_favs_2"), g.w // 2, 246, 14, GRAY, "c")
            else:
                g.text(T("no_entries"), g.w // 2, 200, 20, SOFT, "c")
                g.text(T("no_entries_hint"), g.w // 2, 236, 14, GRAY, "c")
        for row in range(VISIBLE):
            i = self.top + row
            if i >= n:
                break
            e = items[i]
            y = LIST_Y + row * ROW_H
            selected = (i == self.idx)
            if selected:
                gst = TILE[e.cat] if self.cat in ("FAV", "ALL") else st
                g.gradient(12, y, 612, ROW_H - 2, gst["c1"], gst["c2"], True)
                col, gcol = WHITE, SOFT
            else:
                g.rect(12, y + ROW_H - 2, 612, 1, LINE)
                col, gcol = SOFT, GRAY
            if self._is_fav(e):
                self.draw_star(30, y + 17, 8, GOLD)
            # Texto de la derecha: en Favoritos la categoria, en el resto el grupo
            side = T("kind_" + e.cat) if self.cat in ("FAV", "ALL") else e.group
            gw = 0
            if side:
                sw_ = min(150, g.text_w(side, 13))
                gw = sw_
                if selected:
                    self.mt(side, 612, y + 11, 13, gcol, "r", False, 150)
                else:
                    g.text(self.fit(side, 13, 150), 612, y + 11, 13, gcol, "r")
            maxw = 570 - gw - (16 if gw else 0)
            if selected:
                self.mt(e.name, 48, y + 7, 18, col, "l", True, maxw)
            else:
                g.text(self.fit(e.name, 18, maxw), 48, y + 7, 18, col, "l", False)
        # Barra de desplazamiento
        if n > VISIBLE:
            track_h = VISIBLE * ROW_H
            thumb_h = max(18, int(track_h * VISIBLE / float(n)))
            thumb_y = LIST_Y + int((track_h - thumb_h) * self.top / float(max(1, n - VISIBLE)))
            g.rect(630, LIST_Y, 4, track_h, LINE)
            g.rect(630, thumb_y, 4, thumb_h, SOFT)
        if self.notice:
            self.mt(self.notice, 24, 416, 14, WARN, "l", False, 592)
        # Pie
        hint = T("list_hint", T("list_clear") if (q and self.cat != "ALL") else T("list_back"))
        self.mt(hint, 24, 440, 14, GRAY, "l", False, 592)

    def draw_kbd(self):
        g = self.g
        st = TILE[self.cat]
        self._background()
        g.gradient(0, 0, g.w, 62, st["c1"], st["c2"], True)
        if self.kb_target == "logo":
            self.mt(T("lg_kb"), 24, 14, 30, WHITE, "l", True, 592)
            g.text("%d/%d" % (len(self.kb_text), self.LOGO_CHARS), 600, 126, 14, GRAY, "r")
        elif self.cat in SPLIT and self.kb_target == "group":
            self.mt(T("search_groups"), 24, 14, 30, WHITE, "l", True, 592)
        elif self.cat in SPLIT and self.kb_target == "show":
            self.mt(T("search_shows"), 24, 14, 30, WHITE, "l", True, 592)
        else:
            self.mt(T("search_in", T("tile_" + self.cat)), 24, 14, 30, WHITE, "l", True, 592)
        # Caja de texto
        g.rect(24, 76, 592, 46, KEY_BG, 8)
        shown = self.kb_text[:self.kb_pos] + "|" + self.kb_text[self.kb_pos:]
        if g.text_w(shown, 24) > 540:                       # el texto largo se corre para que se vea donde escribes
            cut = 0
            while cut < self.kb_pos and g.text_w("…" + shown[cut:], 24) > 540:
                cut += 1
            shown = "…" + shown[cut:]
            while len(shown) > 2 and g.text_w(shown, 24) > 540:
                shown = shown[:-1]
        if self.kb_text:
            g.text(shown, 40, 84, 24, WHITE, "l")
        else:
            g.text("|", 40, 84, 24, WHITE, "l")
            g.text(T("type_name"), 56, 88, 18, GRAY, "l")
        # Teclas
        x_base = (g.w - 594) // 2
        rows = self._kb_rows()
        for r, row in enumerate(rows):
            y = KB_Y + r * (KEY_H + KEY_GAP)
            for c, key in enumerate(row):
                sel = (self.kb_row == r and self.kb_col == c)
                col0, span = (ROW4_COL[c], ROW4_SPAN[c]) if r == len(rows) - 1 else (c, 1)
                x = x_base + col0 * (KEY_W + KEY_GAP)
                w = span * KEY_W + (span - 1) * KEY_GAP
                label = key.upper() if (self.kb_shift and key.isalpha()) else key
                if key == "sym":
                    label = "abc" if self.kb_sym else "?123"
                self._key(x, y, w, label, sel, st, 20, key)
        self.mt(T("kb_hint"), 24, 440, 14, GRAY, "l", False, 592)

    def _key(self, x, y, w, label, selected, st, size=20, kind=None):
        g = self.g
        active = (kind == "shift" and self.kb_shift > 0) or (kind == "sym" and self.kb_sym)
        if selected:
            g.gradient(x, y, w, KEY_H, st["c1"], st["c2"], True, 6)
            g.outline(x - 2, y - 2, w + 4, KEY_H + 4, WHITE, 3, 8)
            col = WHITE
            hole = st["c2"]
        else:
            g.rect(x, y, w, KEY_H, (70, 84, 128) if active else KEY_BG, 6)
            col = WHITE if active else SOFT
            hole = (70, 84, 128) if active else KEY_BG
        cx, cy = x + w // 2, y + KEY_H // 2
        if kind == "shift":
            pts = [(cx, cy - 10), (cx + 10, cy), (cx + 4, cy), (cx + 4, cy + 8), (cx - 4, cy + 8), (cx - 4, cy), (cx - 10, cy)]
            g.polygon(pts, col)
            if self.kb_shift == 2:                      # mayusculas fijas: barrita debajo
                g.rect(cx - 6, cy + 11, 12, 3, col, 1)
        elif kind == "space":
            for p, q in (((cx - 12, cy - 3), (cx - 12, cy + 5)), ((cx - 12, cy + 5), (cx + 12, cy + 5)),
                         ((cx + 12, cy + 5), (cx + 12, cy - 3))):
                g.line(p, q, col, 3)
        elif kind == "go" and self.kb_target == "logo":      # en el logo: palomita (aceptar)
            g.line((cx - 9, cy), (cx - 3, cy + 7), col, 4)
            g.line((cx - 3, cy + 7), (cx + 10, cy - 8), col, 4)
        elif kind == "go":
            if not g.image("buscar", 26, cx, cy, col):
                g.circle(cx - 3, cy - 3, 7, col)
                g.line((cx + 2, cy + 2), (cx + 9, cy + 9), col, 3)
        elif kind == "left":
            g.polygon([(cx - 8, cy), (cx + 6, cy - 10), (cx + 6, cy + 10)], col)
        elif kind == "right":
            g.polygon([(cx + 8, cy), (cx - 6, cy - 10), (cx - 6, cy + 10)], col)
        elif kind == "del":
            g.polygon([(cx - 13, cy), (cx - 5, cy - 9), (cx + 12, cy - 9), (cx + 12, cy + 9), (cx - 5, cy + 9)], col)
            g.line((cx - 1, cy - 4), (cx + 7, cy + 4), hole, 2)
            g.line((cx - 1, cy + 4), (cx + 7, cy - 4), hole, 2)
        elif kind == "sym":
            g.text(label, cx, y + (KEY_H - 16) // 2 - 2, 16, col, "c", True)
        else:
            g.text(label, cx, y + (KEY_H - size) // 2 - 3, size, col, "c")

    def draw_splash(self, title):
        g = self.g
        self._background()
        g.text(T("opening"), g.w // 2, 196, 30, WHITE, "c", True)
        g.text(self.fit(title, 18, 580), g.w // 2, 246, 18, SOFT, "c")
        g.text(T("play_hint"), g.w // 2, 400, 14, GRAY, "c")
        g.present()


def _mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def lang_name_native(code):
    return {"es": "Español", "en": "English"}.get(code, code)
