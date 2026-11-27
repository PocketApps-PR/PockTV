#!/bin/sh
# Lanzador de IPTV con interfaz. Usa el Python de Spruce (PySDL2) y ejecuta main.py.
# Todo queda en launch.log (este script) e iptv_ui.log (la app).

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$APP_DIR/launch.log"
: > "$LOG"
echo "APP_DIR=$APP_DIR" >> "$LOG"

# 1) Carpeta de las librerias SDL2 (como hace PyUI)
DLL=""
for d in /mnt/SDCARD/App/PyUI/dll /mnt/SDCARD/spruce/flip/lib/sdl2dll/dll; do
    if [ -d "$d" ]; then DLL="$d"; break; fi
done
echo "DLL=$DLL" >> "$LOG"
export PYSDL2_DLL_PATH="$DLL"
export LD_LIBRARY_PATH="$DLL:/usr/miyoo/lib:/usr/lib:$LD_LIBRARY_PATH"

# 2) Interprete con PySDL2 (primero los de Spruce Flip)
CANDIDATES="
/mnt/SDCARD/spruce/flip/bin/python3
/mnt/SDCARD/spruce/flip/bin/python
/mnt/SDCARD/spruce/flip/bin/python3.10
/mnt/SDCARD/spruce/flip/bin/MainUI
$(command -v python3 2>/dev/null)
$(command -v python 2>/dev/null)
"
export PYTHONPATH="/mnt/SDCARD/spruce/flip/lib/python3.10/site-packages:$PYTHONPATH"

PY=""
for c in $CANDIDATES; do
    [ -x "$c" ] || continue
    if "$c" -c "import sdl2, sdl2.sdlttf" >> "$LOG" 2>&1; then
        PY="$c"
        break
    fi
    echo "sin sdl2: $c" >> "$LOG"
done

if [ -z "$PY" ]; then
    echo "ERROR: no encontre un Python con PySDL2. Pasame este archivo (launch.log)." >> "$LOG"
    exit 1
fi
echo "Python: $PY" >> "$LOG"

# 3) Igual que PyUI: ejecutar desde /usr/miyoo/bin si existe
cd /usr/miyoo/bin 2>/dev/null || cd "$APP_DIR" || exit 1
exec "$PY" "$APP_DIR/main.py" >> "$LOG" 2>&1
