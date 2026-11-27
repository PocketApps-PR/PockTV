"""Formas (rectangulo redondeado, circulo, poligono, linea gruesa) hechas con
tramos horizontales. Solo necesita dos primitivas del backend:
    _fill(x, y, w, h, color)   rectangulo relleno
    _line(x1, y1, x2, y2, color)  linea de 1 px
Asi el mismo dibujo sirve para SDL2 (consola) y para Pillow (pruebas en PC).
"""
import math


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _inset(r, h, row):
    """Cuanto se mete el borde izquierdo en la fila `row` de un rect redondeado."""
    if r <= 0:
        return 0
    d = None
    if row < r:
        d = r - row - 0.5
    elif row >= h - r:
        d = row - (h - r) + 0.5
    if d is None:
        return 0
    return int(math.ceil(r - math.sqrt(max(0.0, r * r - d * d))))


class RasterGfx(object):
    w = 640
    h = 480

    def _fill(self, x, y, w, h, c):
        raise NotImplementedError

    def _line(self, x1, y1, x2, y2, c):
        raise NotImplementedError

    def rect(self, x, y, w, h, c, radius=0):
        x, y, w, h = int(x), int(y), int(w), int(h)
        radius = min(int(radius), w // 2, h // 2)
        if radius <= 0:
            self._fill(x, y, w, h, c)
            return
        for row in range(h):
            i = _inset(radius, h, row)
            self._fill(x + i, y + row, w - 2 * i, 1, c)

    def outline(self, x, y, w, h, c, width=3, radius=0):
        x, y, w, h, width = int(x), int(y), int(w), int(h), int(width)
        radius = min(int(radius), w // 2, h // 2)
        if width * 2 >= min(w, h):
            self.rect(x, y, w, h, c, radius)
            return
        ir = max(0, radius - width)
        ih = h - 2 * width
        for row in range(h):
            o = _inset(radius, h, row)
            irow = row - width
            if 0 <= irow < ih:
                i = width + _inset(ir, ih, irow)
                i = max(i, o)
                self._fill(x + o, y + row, i - o, 1, c)
                self._fill(x + w - i, y + row, i - o, 1, c)
            else:
                self._fill(x + o, y + row, w - 2 * o, 1, c)

    def gradient(self, x, y, w, h, c1, c2, horizontal=False, radius=0):
        radius = min(int(radius), w // 2, h // 2)
        n = w if horizontal else h
        for i in range(n):
            col = lerp(c1, c2, i / float(max(1, n - 1)))
            if horizontal:
                ins = _inset(radius, w, i)
                self._fill(x + i, y + ins, 1, h - 2 * ins, col)
            else:
                ins = _inset(radius, h, i)
                self._fill(x + ins, y + i, w - 2 * ins, 1, col)

    def circle(self, cx, cy, r, c, width=0):
        cx, cy, r, width = int(cx), int(cy), int(r), int(width)
        ir = r - width
        for dy in range(-r, r + 1):
            ox = int(math.sqrt(max(0.0, r * r - (dy + 0.0) ** 2)))
            if width <= 0 or abs(dy) >= ir:
                self._fill(cx - ox, cy + dy, 2 * ox + 1, 1, c)
            else:
                ix = int(math.sqrt(max(0.0, ir * ir - dy * dy)))
                self._fill(cx - ox, cy + dy, ox - ix, 1, c)
                self._fill(cx + ix + 1, cy + dy, ox - ix, 1, c)

    def polygon(self, points, c):
        pts = [(float(px), float(py)) for px, py in points]
        ys = [p[1] for p in pts]
        n = len(pts)
        for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys)))):
            yy = y + 0.5
            xs = []
            for i in range(n):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
                if (y1 <= yy < y2) or (y2 <= yy < y1):
                    xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                a, b = int(round(xs[k])), int(round(xs[k + 1]))
                if b > a:
                    self._fill(a, y, b - a, 1, c)

    def line(self, p1, p2, c, width=1):
        (x1, y1), (x2, y2) = p1, p2
        if width <= 1:
            self._line(int(x1), int(y1), int(x2), int(y2), c)
            return
        dx, dy = x2 - x1, y2 - y1
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d * width / 2.0, dx / d * width / 2.0
        self.polygon([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
                      (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], c)
        self.circle(x1, y1, width // 2, c)
        self.circle(x2, y2, width // 2, c)
