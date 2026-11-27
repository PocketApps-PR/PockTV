#!/bin/sh
# Reproduce un canal con el mismo ffplay que usa Spruce para videos (Emu/MEDIA),
# con los mismos botones (gptokeyb) que Spruce configura para ffplay.
# Uso: play.sh <url> [titulo]

URL="$1"
TITLE="$2"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
EMU_DIR="${EMU_DIR:-/mnt/SDCARD/Emu/MEDIA}"
GPTK="${GPTK:-/mnt/SDCARD/spruce/bin64/gptokeyb}"
LOG="$APP_DIR/ffplay.log"
FFPLAY_EXTRA=""
[ -f "$APP_DIR/ui.conf" ] && . "$APP_DIR/ui.conf"

: > "$LOG"
echo "Canal: $TITLE" >> "$LOG"
echo "URL: $URL" >> "$LOG"

if [ -z "$URL" ]; then
    echo "ERROR: no se recibio URL" >> "$LOG"
    exit 1
fi

# Buscar ffplay (el de Emu/MEDIA es el que usa Spruce en la Flip)
FFPLAY=""
for c in "$EMU_DIR/bin64/ffplay" "/mnt/SDCARD/spruce/bin64/ffplay" "$EMU_DIR/bin/ffplay"; do
    if [ -x "$c" ]; then FFPLAY="$c"; break; fi
done
[ -n "$FFPLAY" ] || FFPLAY=$(command -v ffplay 2>/dev/null)
if [ -z "$FFPLAY" ]; then
    echo "ERROR: no encontre ffplay (busque en $EMU_DIR/bin64)" >> "$LOG"
    exit 1
fi
echo "ffplay: $FFPLAY" >> "$LOG"

[ -d "$EMU_DIR/bin64" ] && export PATH="$EMU_DIR/bin64:$PATH"
export LD_LIBRARY_PATH="$EMU_DIR/lib64:/usr/miyoo/lib:/usr/lib:$LD_LIBRARY_PATH"

# Aviso en el log si el ffplay no soporta https
case "$URL" in
    https://*)
        if ! "$FFPLAY" -protocols 2>&1 | grep -qi https; then
            echo "AVISO: este ffplay no lista https; si falla, el canal necesita http." >> "$LOG"
        fi
        ;;
esac

# Botones: igual que Spruce para ffplay
GPTK_PID=""
if [ -x "$GPTK" ] && [ -f "$EMU_DIR/bin64/ffplay.gptk" ]; then
    cd "$EMU_DIR" || true
    "$GPTK" -k "ffplay" -c "./bin64/ffplay.gptk" >/dev/null 2>&1 &
    GPTK_PID=$!
    sleep 1
fi

W="${DISPLAY_WIDTH:-640}"
H="${DISPLAY_HEIGHT:-480}"

# shellcheck disable=SC2086
"$FFPLAY" -x "$W" -y "$H" -fs -loglevel 24 $FFPLAY_EXTRA -i "$URL" >> "$LOG" 2>&1
echo "ffplay termino con codigo $?" >> "$LOG"

[ -n "$GPTK_PID" ] && kill "$GPTK_PID" 2>/dev/null
exit 0
