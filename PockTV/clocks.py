# -*- coding: utf-8 -*-
"""Disenos del reloj del inicio: hora + fecha + icono de wifi, todo en el mismo estilo (Ajustes > Apariencia > Reloj y Fecha)."""
import math

WHITE = (255, 255, 255)
CODES = ("default", "A", "B", "C", "D", "E")
DSCALE = 1.0                      # factor del tamano de la fecha (Ajustes > Hora y fecha > Tamano de fecha)
MAXW = 300                       # ancho maximo del bloque (con el formato de fecha mas largo no se sale)


class Dry(object):
    """Mide sin dibujar: usa text_w del dibujante real y no hace nada mas."""
    def __init__(self, g):
        self.g = g

    def text_w(self, *a, **k):
        return self.g.text_w(*a, **k)

    def __getattr__(self, name):
        return lambda *a, **k: True


def _tw(g, t, size, bold, face, gap=0):
    return sum(g.text_w(c, size, bold, face) + gap for c in t) - gap if gap else g.text_w(t, size, bold, face)


def _fit(g, t, size, bold, face, gap, maxw):
    """Tamano de letra mas grande (hasta `size`) con el que la fecha cabe en maxw."""
    size = int(round(size * DSCALE))
    while size > 9 and _tw(g, t, size, bold, face, gap) > maxw:
        size -= 1
    return size


def _txt(g, t, x, y, size, col, align, bold, face, gap=0):
    """Texto con espacio extra entre letras (gap) alineado a la derecha, izquierda o centro."""
    if not gap:
        g.text(t, x, y, size, col, align, bold, face)
        return
    w = _tw(g, t, size, bold, face, gap)
    cx = x - w if align == "r" else (x - w // 2 if align == "c" else x)
    for c in t:
        g.text(c, cx, y, size, col, "l", bold, face)
        cx += g.text_w(c, size, bold, face) + gap


def _arc(g, cx, cy, r, col, width):
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(225, 316, 15)]
    for i in range(len(pts) - 1):
        g.line(pts[i], pts[i + 1], col, width)


DIG = {"A": (26, 63), "B": (28, 60), "C": (29, 61), "D": (27, 62), "E": (29, 61)}      # alto de los numeros de la hora (arriba, abajo)


def _geom(S, code, width, dotr):
    """Radio del arco mayor y medio ancho del wifi para que mida lo mismo que los numeros de la hora."""
    top, bot = DIG[code]
    R = S(bot - top) - S(dotr) - S(width) // 2
    return R, int(R * 0.707) + S(width) // 2 + 1


def _wifi_arcs(g, S, Y, code, cx, lvl, dim, width, cols, dotcol, dotr, glow=None):
    """Wifi dibujado a mano; empieza abajo donde terminan los numeros de la hora y sube hasta donde terminan arriba.
    lvl: 0 solo punto, 1 un arco, 2 todos, -1 sin senal."""
    R, _hw = _geom(S, code, width, dotr)
    cy = Y(DIG[code][1]) - S(dotr)
    lit = (lvl >= 1, lvl >= 2, lvl >= 2)
    for i, f in enumerate((0.36, 0.68, 1.0)):
        r = max(2, int(R * f))
        if glow and lit[i]:
            _arc(g, cx, cy, r, glow, S(width) + 3)
        _arc(g, cx, cy, r, cols[i] if lit[i] else dim, max(1, S(width)))
    g.circle(cx, cy, max(2, S(dotr)), dotcol if lvl >= 0 else dim)


def draw(g, code, R, oy, k, tm, suf, ds, lvl, dim, maxw=MAXW):
    """Dibuja el reloj con la MISMA rejilla que el predeterminado: la hora y el wifi en la misma linea,
    el wifi a la misma distancia de la hora y la fecha bajo ellos. R = borde derecho, oy = desplazamiento
    vertical, k = escala. Devuelve (x del wifi, borde izquierdo del bloque)."""
    S = lambda v: int(round(v * k))
    Y = lambda v: int(round(oy + v * k))
    mw = S(maxw)
    if code == "A":                                              # AURORA
        TF, SF, DF = "Inter-Thin.otf", "Inter-Light.otf", "Lora-Italic-Variable.ttf"
        dsz = _fit(g, ds, S(15), False, DF, 0, mw)
        sw = g.text_w(suf, S(16), False, SF) if suf else 0
        r = R - sw - S(8) if suf else R
        tl = r - g.text_w(tm, S(48), False, TF)
        g.text(tm, r, Y(15), S(48), WHITE, "r", False, TF)
        if suf:
            g.text(suf, R, Y(38), S(16), (200, 210, 255), "r", False, SF)
        wx = tl - S(10) - _geom(S, "A", 4, 4)[1]
        L = min(wx - _geom(S, "A", 4, 4)[1], R - _tw(g, ds, dsz, False, DF))
        g.gradient(L, Y(66), R - L, max(2, S(2)), (150, 90, 255), (60, 210, 255), True)
        _wifi_arcs(g, S, Y, "A", wx, lvl, dim, 4, ((150, 90, 255), (110, 140, 255), (70, 190, 255)), (60, 210, 255), 4)
        g.text(ds, R, Y(70), dsz, (190, 175, 255), "r", False, DF)
        return wx, L
    if code == "B":                                              # RETRO TERMINAL
        TF, DF = "DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf"
        G, G2 = (70, 255, 120), (40, 190, 90)
        line = "> " + ds.upper() + "_"
        dsz = _fit(g, line, S(14), False, DF, 0, mw)
        sf = suf.replace(".", "").upper()
        sw = g.text_w(sf, S(16), True, TF) if sf else 0
        r = R - sw - S(8) if sf else R
        tl = r - g.text_w(tm, S(42), True, TF)
        g.text(tm, r, Y(21), S(42), G, "r", True, TF)
        if sf:
            g.text(sf, R, Y(39), S(16), G2, "r", True, TF)
        px = max(2, S(5))
        wx = tl - S(34)
        L = min(wx - S(25), R - _tw(g, line, dsz, False, DF))
        for i in range(4):
            on = lvl >= (0, 1, 2, 2)[i] and lvl >= 0
            for j in range(i + 1):
                g.rect(wx - S(24) + i * (px * 2 + S(3)), Y(DIG["B"][1]) - (j + 1) * S(8) + S(1), px * 2, S(7), G if on else dim)
        g.text(line, R, Y(72), dsz, (50, 210, 100), "r", False, DF)
        return wx, L
    if code == "C":                                              # POP
        TF, DF = "Poppins-BoldItalic.ttf", "Poppins-MediumItalic.ttf"
        ds2 = ds.upper()
        dsz = _fit(g, ds2, S(13), False, DF, S(3), mw)
        gap = S(3)
        if _tw(g, ds2, dsz, False, DF, gap) > mw:
            gap = S(1)
        sw = g.text_w(suf, S(16), True, TF) if suf else 0
        r = R - sw - S(8) if suf else R
        tl = r - g.text_w(tm, S(44), True, TF)
        g.text(tm, r + S(3), Y(17), S(44), (255, 60, 140), "r", True, TF)
        g.text(tm, r, Y(14), S(44), (255, 230, 60), "r", True, TF)
        if suf:
            g.text(suf, R, Y(38), S(16), WHITE, "r", True, TF)
        wx = tl - S(10) - _geom(S, "C", 4, 4)[1]
        _wifi_arcs(g, S, Y, "C", wx, lvl, dim, 4, ((255, 230, 60), (255, 150, 60), (255, 60, 140)), (255, 230, 60), 4)
        _txt(g, ds2, R, Y(71), dsz, WHITE, "r", False, DF, gap)
        return wx, min(wx - _geom(S, "C", 4, 4)[1], R - _tw(g, ds2, dsz, False, DF, gap))
    if code == "D":                                              # ELEGANTE DORADO
        TF, SF = "Lora-Variable.ttf", "Lora-Italic-Variable.ttf"
        gold, dgold = (236, 200, 120), (150, 120, 70)
        dsz = _fit(g, ds, S(14), False, SF, 0, mw)
        sw = g.text_w(suf, S(17), False, SF) if suf else 0
        r = R - sw - S(8) if suf else R
        tl = r - g.text_w(tm, S(46), False, TF)
        g.text(tm, r, Y(14), S(46), gold, "r", False, TF)
        if suf:
            g.text(suf, R, Y(37), S(17), (200, 170, 110), "r", False, SF)
        wx = tl - S(10) - _geom(S, "D", 3, 4)[1]
        L = min(wx - _geom(S, "D", 3, 4)[1], R - _tw(g, ds, dsz, False, SF))
        mid = (L + R) // 2
        g.rect(L, Y(68), mid - S(9) - L, max(1, S(1)), dgold)
        g.rect(mid + S(9), Y(68), R - mid - S(9), max(1, S(1)), dgold)
        g.polygon([(mid - S(4), Y(68)), (mid, Y(65)), (mid + S(4), Y(68)), (mid, Y(71))], gold)
        _wifi_arcs(g, S, Y, "D", wx, lvl, dim, 3, (gold, gold, gold), gold, 4)
        g.text(ds, mid, Y(72), dsz, (215, 185, 120), "c", False, SF)
        return wx, L
    # E: NEON
    TF, SF, DF = "Poppins-Medium.ttf", "Poppins-Medium.ttf", "Inter-Light.otf"
    ds2 = ds.upper()
    dsz = _fit(g, ds2, S(14), False, DF, S(3), mw)
    gap = S(3)
    if _tw(g, ds2, dsz, False, DF, gap) > mw:
        gap = S(1)
    sw = g.text_w(suf, S(16), False, SF) if suf else 0
    r = R - sw - S(8) if suf else R
    tl = r - g.text_w(tm, S(42), False, TF)
    for d, c in ((3, (0, 42, 56)), (2, (0, 70, 92))):            # brillo: copias tenues alrededor
        for dx, dy in ((-d, 0), (d, 0), (0, -d), (0, d)):
            g.text(tm, r + dx, Y(16) + dy, S(42), c, "r", False, TF)
    g.text(tm, r, Y(16), S(42), (215, 250, 255), "r", False, TF)
    if suf:
        g.text(suf, R + 1, Y(38) + 1, S(16), (90, 25, 70), "r", False, SF)
        g.text(suf, R, Y(38), S(16), (255, 170, 235), "r", False, SF)
    wx = tl - S(10) - _geom(S, "E", 4, 4)[1]
    C = (0, 210, 255)
    _wifi_arcs(g, S, Y, "E", wx, lvl, dim, 4, (C, C, C), C, 4, (0, 60, 80))
    _txt(g, ds2, R, Y(72), dsz, (255, 160, 230), "r", False, DF, gap)
    return wx, min(wx - _geom(S, "E", 4, 4)[1], R - _tw(g, ds2, dsz, False, DF, gap))
