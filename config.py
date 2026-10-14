"""
Configuration module for Jarvis Dual-Display Personal Agent.
Loads environment variables from .env and establishes display layout,
model parameters, paths, and third-party API configurations.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file from project root
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# ---------------------------------------------------------
# GEMINI BRAIN CONFIGURATION
# ---------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ---------------------------------------------------------
# DUAL-DISPLAY & WINDOW PINNING CONFIGURATION
# Defaults assume a 1920x1080 Monitor 1 with Monitor 2 extended to the right.
# HUD occupies the left half (1920..2879), Playwright automation occupies right half (2880..3839).
# ---------------------------------------------------------
SECOND_DISPLAY_X = int(os.getenv("SECOND_DISPLAY_X", "1920"))
SECOND_DISPLAY_Y = int(os.getenv("SECOND_DISPLAY_Y", "0"))

# HUD Window Position & Dimensions (Monitor 2 Left Half)
HUD_WINDOW_X = int(os.getenv("HUD_WINDOW_X", str(SECOND_DISPLAY_X)))
HUD_WINDOW_Y = int(os.getenv("HUD_WINDOW_Y", str(SECOND_DISPLAY_Y)))
HUD_WINDOW_WIDTH = int(os.getenv("HUD_WINDOW_WIDTH", "960"))
HUD_WINDOW_HEIGHT = int(os.getenv("HUD_WINDOW_HEIGHT", "1040"))

# Playwright Headed Automation Window (Monitor 2 Right Half)
BROWSER_WINDOW_X = int(os.getenv("BROWSER_WINDOW_X", str(SECOND_DISPLAY_X + 960)))
BROWSER_WINDOW_Y = int(os.getenv("BROWSER_WINDOW_Y", str(SECOND_DISPLAY_Y)))
BROWSER_WINDOW_WIDTH = int(os.getenv("BROWSER_WINDOW_WIDTH", "960"))
BROWSER_WINDOW_HEIGHT = int(os.getenv("BROWSER_WINDOW_HEIGHT", "1040"))

# Persistent Chromium User Data Directory
RAW_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "~/.jarvis_chrome_profile")
CHROME_PROFILE_DIR = Path(os.path.expanduser(RAW_PROFILE_DIR)).resolve()
CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Downloads folder for datasets & artifacts
DOWNLOADS_DIR = (BASE_DIR / "downloads").resolve()
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# GOOGLE WORKSPACE (OAUTH)
# ---------------------------------------------------------
GOOGLE_CREDENTIALS_FILE = Path(
    os.getenv("GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json"))
).resolve()
GOOGLE_TOKEN_FILE = Path(
    os.getenv("GOOGLE_TOKEN_FILE", str(BASE_DIR / "token.json"))
).resolve()

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------
# TELEGRAM REMOTE WORKER
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_raw_telegram_id = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
ALLOWED_TELEGRAM_USER_ID = int(_raw_telegram_id) if _raw_telegram_id.isdigit() else None

# ---------------------------------------------------------
# KAGGLE API CREDENTIALS
# ---------------------------------------------------------
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "").strip()
KAGGLE_KEY = os.getenv("KAGGLE_KEY", "").strip()

if KAGGLE_USERNAME and KAGGLE_KEY:
    os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
    os.environ["KAGGLE_KEY"] = KAGGLE_KEY

# ---------------------------------------------------------
# SERVER & VOICE DEFAULTS
# ---------------------------------------------------------
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", f"http://localhost:{SERVER_PORT}")
VOICE_LANGUAGE = os.getenv("VOICE_LANGUAGE", "en-IN")
WAKE_WORD = os.getenv("WAKE_WORD", "jarvis").strip().lower()
