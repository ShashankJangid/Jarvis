@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo       JARVIS DUAL-DISPLAY AUTONOMOUS WORKSPACE LAUNCHER
echo ================================================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Read SECOND_DISPLAY_X and SECOND_DISPLAY_Y from .env if present
set SECOND_DISPLAY_X=1920
set SECOND_DISPLAY_Y=0
set HUD_WIDTH=960
set HUD_HEIGHT=1040

if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="SECOND_DISPLAY_X" set SECOND_DISPLAY_X=%%b
        if "%%a"=="SECOND_DISPLAY_Y" set SECOND_DISPLAY_Y=%%b
        if "%%a"=="HUD_WINDOW_WIDTH" set HUD_WIDTH=%%b
        if "%%a"=="HUD_WINDOW_HEIGHT" set HUD_HEIGHT=%%b
    )
)

echo [*] Target Second Display Position: X=%SECOND_DISPLAY_X%, Y=%SECOND_DISPLAY_Y%
echo [*] HUD Dimensions: %HUD_WIDTH% x %HUD_HEIGHT%
echo.

:: 1. Start the Jarvis FastAPI Server in a separate window
echo [*] Starting Jarvis Orchestrator Server on http://localhost:8000 ...
start "Jarvis Orchestrator Server" python server.py

:: Wait 3 seconds for uvicorn to initialize
echo [*] Waiting for server initialization...
timeout /t 3 /nobreak >nul

:: 2. Detect Browser (Google Chrome or Microsoft Edge)
set BROWSER_CMD=""

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set BROWSER_CMD="%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set BROWSER_CMD="%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set BROWSER_CMD="%LocalAppData%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set BROWSER_CMD="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
) else (
    set BROWSER_CMD=start msedge
)

:: 3. Launch HUD in App Mode pinned to Monitor 2 (Left Half)
echo [*] Snapping Sci-Fi HUD to Monitor 2 (Left Half: X=%SECOND_DISPLAY_X%, Y=%SECOND_DISPLAY_Y%)...
start "" %BROWSER_CMD% --app=http://localhost:8000/ --window-position=%SECOND_DISPLAY_X%,%SECOND_DISPLAY_Y% --window-size=%HUD_WIDTH%,%HUD_HEIGHT% --user-data-dir="%TEMP%\jarvis_hud_chrome_profile"

echo.
echo ================================================================
echo  [SUCCESS] JARVIS Dual-Display Agent is active!
echo  - Monitor 1 (Laptop) : Completely Uninterrupted
echo  - Monitor 2 (Left)   : Sci-Fi Command Center HUD
echo  - Monitor 2 (Right)  : Playwright Headed Automations
echo ================================================================
echo.
pause
