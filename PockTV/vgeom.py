# -*- coding: utf-8 -*-
"""Geometria del video segun el modo de pantalla. Sin SDL: se puede probar aparte.
ffmpeg manda SIEMPRE el cuadro completo estirado a W x H; el modo se aplica al dibujarlo (recorte de origen
`src` y rectangulo de destino `dst`), asi cambiar de modo no reinicia el video."""
import re

_DIM = re.compile(r",\s*(\d{2,5})x(\d{2,5})")
_SAR = re.compile(r"SAR\s+(\d+):(\d+)")


def parse_dar(line):
    """Relacion de aspecto de la imagen (ancho/alto, con SAR) a partir de la linea 'Stream #0:N: Video: ...' de
    ENTRADA de ffmpeg. None si no es esa linea."""
    if "Video:" not in line or "rawvideo" in line or "->" in line:
        return None
    m = _DIM.search(line.split("Video:", 1)[1])
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w < 16 or h < 16:
        return None
    sar = 1.0
    s = _SAR.search(line)
    if s and int(s.group(1)) > 0 and int(s.group(2)) > 0:
        sar = int(s.group(1)) / float(int(s.group(2)))
        if not 0.2 <= sar <= 5.0:
            sar = 1.0
    return (w * sar) / float(h)


def _even(v):
    return int(v) // 2 * 2


def geometry(mode, dar, W, H, crop=None):
    """Devuelve (src, dst): rectangulos (x0, y0, x1, y1) o None. src = parte del cuadro estirado que se muestra,
    dst = donde se dibuja en pantalla (None = pantalla completa)."""
    if mode == "auto":
        return crop, None
    if mode == "estirar" or not dar:
        return None, None
    sa = W / float(H)
    if mode == "zoom":                      # llena la pantalla recortando lo que sobra
        if abs(dar - sa) < 0.01:
            return None, None
        if dar > sa:                        # mas ancha: se recortan los lados
            vw = W * sa / dar
            x0 = _even((W - vw) / 2.0)
            return (x0, 0, W - x0, H), None
        vh = H * dar / sa                   # mas alta: se recortan arriba y abajo
        y0 = _even((H - vh) / 2.0)
        return (0, y0, W, H - y0), None
    # "normal": toda la imagen con su forma, con barras negras
    if abs(dar - sa) < 0.01:
        return None, None
    if dar > sa:
        dh = _even(W / dar)
        return None, (0, (H - dh) // 2, W, (H - dh) // 2 + dh)
    dw = _even(H * dar)
    return None, ((W - dw) // 2, 0, (W - dw) // 2 + dw, H)
