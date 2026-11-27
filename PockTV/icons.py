"""Iconos dibujados con formas (sin imagenes): estilo IPTV Smarters. Cada funcion recibe
el gfx, el centro (cx, cy) y el tamano s (ancho aproximado en pixeles)."""
import math

WHITE = (255, 255, 255)


def _rot(p, c, ang):
    a = math.radians(ang)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * math.cos(a) - dy * math.sin(a), c[1] + dx * math.sin(a) + dy * math.cos(a))


def _bez(p0, p1, p2, n=12):
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts


def _poly_line(g, pts, c, w):
    for a, b in zip(pts[:-1], pts[1:]):
        g.line(a, b, c, w)


def _head(g, tip, frm, size, c):
    """Punta de flecha en `tip`, mirando en la direccion frm -> tip."""
    ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
    back = (tip[0] - size * math.cos(ang), tip[1] - size * math.sin(ang))
    nx, ny = -math.sin(ang), math.cos(ang)
    g.polygon([tip, (back[0] + nx * size * 0.75, back[1] + ny * size * 0.75),
               (back[0] - nx * size * 0.75, back[1] - ny * size * 0.75)], c)


def tv(g, cx, cy, s, screen, body=WHITE):
    """TV con antena, pantalla con boton de play y 3 puntos (como IPTV Smarters)."""
    x0, w = cx - s / 2.0, s
    h = 0.70 * s
    y0 = cy - 0.30 * s
    lw = max(3, int(s * 0.05))
    # antena
    g.line((cx - 0.04 * s, y0 - 0.02 * s), (cx - 0.24 * s, y0 - 0.22 * s), body, lw)
    g.line((cx + 0.04 * s, y0 - 0.02 * s), (cx + 0.24 * s, y0 - 0.22 * s), body, lw)
    g.circle(cx - 0.24 * s, y0 - 0.22 * s, max(2, lw // 2 + 1), body)
    g.circle(cx + 0.24 * s, y0 - 0.22 * s, max(2, lw // 2 + 1), body)
    g.circle(cx, y0 + 0.01 * s, 0.11 * s, body)
    # cuerpo
    g.rect(x0, y0, w, h, body, int(0.14 * s))
    sx, sy, sw, sh = x0 + 0.07 * s, y0 + 0.08 * s, 0.70 * s, h - 0.16 * s
    g.rect(sx, sy, sw, sh, screen, int(0.08 * s))
    g.outline(sx + 0.02 * s, sy + 0.02 * s, sw - 0.04 * s, sh - 0.04 * s, body, max(2, int(0.025 * s)), int(0.06 * s))
    # play (contorno)
    px, py, t = sx + sw / 2.0, sy + sh / 2.0, 0.17 * s
    g.polygon([(px - 0.45 * t, py - t), (px - 0.45 * t, py + t), (px + 0.95 * t, py)], body)
    k = 0.55
    g.polygon([(px - 0.45 * t + 0.35 * t, py - t * k - 0.05 * t), (px - 0.45 * t + 0.35 * t, py + t * k + 0.05 * t),
               (px + 0.95 * t - 0.45 * t, py)], screen)
    # puntos de la derecha
    for i in (-1, 0, 1):
        g.circle(x0 + 0.885 * s, y0 + h / 2.0 + i * 0.11 * s, max(2, int(0.025 * s)), screen)


def movie(g, cx, cy, s, c=WHITE):
    """Circulo con triangulo de play."""
    g.circle(cx, cy, s / 2.0, c, max(3, int(s * 0.09)))
    g.polygon([(cx - 0.12 * s, cy - 0.2 * s), (cx - 0.12 * s, cy + 0.2 * s), (cx + 0.23 * s, cy)], c)


def clapper(g, cx, cy, s, stripe, c=WHITE):
    """Claqueta de cine."""
    x0, w = cx - s / 2.0, s
    lw = max(3, int(s * 0.07))
    by = cy - 0.02 * s
    g.outline(x0, by, w, 0.52 * s, c, lw, int(0.04 * s))
    # franja fija con rayas
    g.rect(x0, cy - 0.20 * s, w, 0.18 * s, c)
    n = 4
    for i in range(n):
        xa = x0 + (i * 2 + 0.6) * w / (2 * n)
        xb = xa + w / (2 * n) * 0.8
        g.polygon([(xa, cy - 0.02 * s), (xa + 0.1 * s, cy - 0.20 * s), (xb + 0.1 * s, cy - 0.20 * s), (xb, cy - 0.02 * s)], stripe)
    # brazo levantado
    hinge = (x0 + 0.01 * s, cy - 0.24 * s)
    arm = [(x0, cy - 0.24 * s), (x0 + w, cy - 0.24 * s), (x0 + w, cy - 0.40 * s), (x0, cy - 0.40 * s)]
    arm = [_rot(p, hinge, -16) for p in arm]
    g.polygon(arm, c)
    for i in range(n):
        xa = x0 + (i * 2 + 0.6) * w / (2 * n)
        xb = xa + w / (2 * n) * 0.8
        q = [(xa, cy - 0.24 * s), (xa + 0.1 * s, cy - 0.40 * s), (xb + 0.1 * s, cy - 0.40 * s), (xb, cy - 0.24 * s)]
        g.polygon([_rot(p, hinge, -16) for p in q], stripe)


def gear(g, cx, cy, s, hole, c=WHITE):
    """Engranaje (ajustes) de 8 dientes con agujero central."""
    r_body = 0.33 * s
    for i in range(8):
        a = i * 45
        pts = [(cx - 0.11 * s, cy - 0.30 * s), (cx + 0.11 * s, cy - 0.30 * s),
               (cx + 0.08 * s, cy - 0.5 * s), (cx - 0.08 * s, cy - 0.5 * s)]
        g.polygon([_rot(p, (cx, cy), a) for p in pts], c)
    g.circle(cx, cy, r_body, c)
    g.circle(cx, cy, 0.15 * s, hole)


def swap_lists(g, cx, cy, s, bg, c=WHITE):
    """Dos hojas con lista de verificacion y dos flechas curvas (cambiar de lista)."""
    lw = max(3, int(s * 0.075))
    dw, dh = 0.34 * s, 0.46 * s
    for sign in (-1, 1):
        dx = cx + sign * 0.27 * s
        x0, y0 = dx - dw / 2.0, cy - dh / 2.0 + 0.02 * s
        g.rect(x0, y0, dw, dh, c, int(0.04 * s))
        cut = 0.11 * s
        g.polygon([(x0 + dw - cut, y0), (x0 + dw, y0), (x0 + dw, y0 + cut)], bg)
        for i in range(3):
            ry = y0 + 0.14 * s + i * 0.115 * s
            g.line((x0 + 0.05 * s, ry), (x0 + 0.085 * s, ry + 0.035 * s), bg, 2)
            g.line((x0 + 0.085 * s, ry + 0.035 * s), (x0 + 0.14 * s, ry - 0.03 * s), bg, 2)
            g.rect(x0 + 0.18 * s, ry - 0.01 * s, 0.12 * s, max(2, int(0.025 * s)), bg)
    top = _bez((cx + 0.36 * s, cy - 0.20 * s), (cx + 0.05 * s, cy - 0.52 * s), (cx - 0.28 * s, cy - 0.34 * s))
    _poly_line(g, top, c, lw)
    _head(g, (cx - 0.40 * s, cy - 0.30 * s), top[-2], 0.2 * s, c)
    bot = _bez((cx - 0.36 * s, cy + 0.24 * s), (cx - 0.05 * s, cy + 0.56 * s), (cx + 0.28 * s, cy + 0.38 * s))
    _poly_line(g, bot, c, lw)
    _head(g, (cx + 0.40 * s, cy + 0.34 * s), bot[-2], 0.2 * s, c)


def refresh_box(g, cx, cy, s):
    """Rectangulo claro con dos flechas en bucle (actualizar)."""
    w, h = s, 0.78 * s
    g.rect(cx - w / 2.0 - 1, cy - h / 2.0 - 1, w + 2, h + 2, (255, 255, 255), int(0.16 * s))
    g.rect(cx - w / 2.0 + 3, cy - h / 2.0 + 3, w - 6, h - 6, (226, 226, 230), int(0.12 * s))
    k = (20, 20, 24)
    lw = max(3, int(s * 0.07))
    top = _bez((cx - 0.2 * s, cy + 0.0 * s), (cx - 0.24 * s, cy - 0.15 * s), (cx - 0.04 * s, cy - 0.15 * s), 8)
    top += [(cx + 0.14 * s, cy - 0.15 * s)]
    _poly_line(g, top, k, lw)
    _head(g, (cx + 0.31 * s, cy - 0.15 * s), (cx + 0.1 * s, cy - 0.15 * s), 0.17 * s, k)
    bot = _bez((cx + 0.2 * s, cy + 0.0 * s), (cx + 0.24 * s, cy + 0.15 * s), (cx + 0.04 * s, cy + 0.15 * s), 8)
    bot += [(cx - 0.14 * s, cy + 0.15 * s)]
    _poly_line(g, bot, k, lw)
    _head(g, (cx - 0.31 * s, cy + 0.15 * s), (cx - 0.1 * s, cy + 0.15 * s), 0.17 * s, k)
