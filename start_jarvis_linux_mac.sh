#!/usr/bin/env bash

# ================================================================
#       JARVIS DUAL-DISPLAY AUTONOMOUS WORKSPACE LAUNCHER
#       Supports macOS and Linux
# ================================================================

# Move to the script directory
cd "$(dirname "$0")" || exit 1

# Default display positioning
SECOND_DISPLAY_X=1920
SECOND_DISPLAY_Y=0
HUD_WIDTH=960
HUD_HEIGHT=1040

# Read configurations from .env if present
if [ -f ".env" ]; then
    VAL_X=$(grep -E "^SECOND_DISPLAY_X=" .env | cut -d '=' -f2 | tr -d '[:space:]')
    VAL_Y=$(grep -E "^SECOND_DISPLAY_Y=" .env | cut -d '=' -f2 | tr -d '[:space:]')
    VAL_W=$(grep -E "^HUD_WINDOW_WIDTH=" .env | cut -d '=' -f2 | tr -d '[:space:]')
    VAL_H=$(grep -E "^HUD_WINDOW_HEIGHT=" .env | cut -d '=' -f2 | tr -d '[:space:]')
    
    [ -n "$VAL_X" ] && SECOND_DISPLAY_X=$VAL_X
    [ -n "$VAL_Y" ] && SECOND_DISPLAY_Y=$VAL_Y
    [ -n "$VAL_W" ] && HUD_WIDTH=$VAL_W
    [ -n "$VAL_H" ] && HUD_HEIGHT=$VAL_H
fi

echo "================================================================"
echo "      JARVIS DUAL-DISPLAY AUTONOMOUS WORKSPACE LAUNCHER"
echo "================================================================"
echo "[*] Second Display Coordinates: X=$SECOND_DISPLAY_X, Y=$SECOND_DISPLAY_Y"
echo "[*] HUD Window Dimensions: ${HUD_WIDTH}x${HUD_HEIGHT}"
echo ""

# 1. Start the FastAPI orchestrator server in the background
echo "[*] Launching Jarvis Orchestrator Server on http://localhost:8000 ..."
PYTHON_BIN="python3"
if [ -f ".venv/bin/python3" ]; then
    PYTHON_BIN=".venv/bin/python3"
    echo "[*] Using dedicated virtual environment at .venv"
fi
$PYTHON_BIN server.py &
SERVER_PID=$!

# Register cleanup on script termination
cleanup() {
    echo ""
    echo "[*] Terminating Jarvis Server (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait 2.5 seconds for FastAPI/uvicorn to be ready
sleep 2.5

# 2. Locate Chrome/Chromium binary across macOS and Linux
CHROME_BIN=""

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS binary locations
    if [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
        CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif [ -f "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ]; then
        CHROME_BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    elif [ -f "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" ]; then
        CHROME_BIN="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    fi
else
    # Linux binary locations
    for bin in google-chrome google-chrome-stable chromium-browser chromium brave-browser; do
        if command -v "$bin" &> /dev/null; then
            CHROME_BIN="$bin"
            break
        fi
    done
fi

# 3. Launch HUD in App Mode pinned to Monitor 2
if [ -n "$CHROME_BIN" ]; then
    echo "[*] Snapping Sci-Fi HUD to Monitor 2 (Left Half: X=$SECOND_DISPLAY_X, Y=$SECOND_DISPLAY_Y)..."
    "$CHROME_BIN" \
        --app=http://localhost:8000/ \
        --window-position="${SECOND_DISPLAY_X},${SECOND_DISPLAY_Y}" \
        --window-size="${HUD_WIDTH},${HUD_HEIGHT}" \
        --user-data-dir="/tmp/jarvis_hud_profile" \
        --no-first-run \
        --no-default-browser-check &
else
    echo "[!] Chrome or Chromium binary not detected in standard paths."
    echo "[*] Opening default browser to http://localhost:8000 ..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:8000/"
    else
        xdg-open "http://localhost:8000/"
    fi
fi

echo ""
echo "================================================================"
echo " [SUCCESS] JARVIS Dual-Display Agent is active!"
echo " - Monitor 1 (Laptop) : Completely Uninterrupted"
echo " - Monitor 2 (Left)   : Sci-Fi Command Center HUD"
echo " - Monitor 2 (Right)  : Playwright Headed Automations"
echo "================================================================"
echo "Press Ctrl+C to stop the Jarvis server."
echo ""

# Wait on background server process
wait $SERVER_PID
