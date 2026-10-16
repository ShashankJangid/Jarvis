"""
FastAPI Orchestrator Server for Jarvis Dual-Display Personal Agent.
Provides endpoints:
- POST /command: Process user commands through Gemini 3.8 Flash multi-step loop
- GET /logs: Poll real-time telemetry buffer events
- GET /health: Status of integrations, displays, and credentials
- POST /open-browser: Open headed Chromium on Monitor 2 for one-time auth
- GET /: Serves the Second-Screen HUD dashboard
Spawns background Telegram listener thread on startup.
"""

import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import config
from agent_core import execute_agent_command, telemetry_buffer
from jarvis_graph import execute_jarvis_goal, get_graph_mermaid_diagram
from telegram_bot import start_telegram_bot_thread
from tools.browser_session import get_or_create_page, close_browser

# ---------------------------------------------------------
# LIFESPAN & INITIALIZATION
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    print("=" * 65)
    print("      JARVIS DUAL-DISPLAY ORCHESTRATOR IS ONLINE")
    print(f"      Backend URL: {config.BACKEND_BASE_URL}")
    print(f"      Engine     : LangGraph Stateful Cyclical Graph + Gemini 3.8 Flash")
    print(f"      HUD Display: Monitor 2 Left (X={config.HUD_WINDOW_X}, Y={config.HUD_WINDOW_Y})")
    print(f"      Automation : Monitor 2 Right (X={config.BROWSER_WINDOW_X}, Y={config.BROWSER_WINDOW_Y})")
    print("=" * 65)

    # Launch Telegram bot background thread if configured
    telegram_thread = start_telegram_bot_thread()

    yield

    # Shutdown actions
    print("[*] Shutting down Jarvis server and releasing persistent browser...")
    close_browser()

app = FastAPI(
    title="Jarvis Dual-Display Agent",
    description="Autonomous Second-Display AI Workspace & Desktop Agent powered by LangGraph & Gemini 3.8 Flash",
    version="2.5.0",
    lifespan=lifespan
)

# Enable Full CORS for seamless HUD communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend directory for static assets
FRONTEND_DIR = (config.BASE_DIR / "frontend").resolve()
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# ---------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------
class CommandRequest(BaseModel):
    command: str
    source: Optional[str] = "web"
    use_langgraph: Optional[bool] = True

class CommandResponse(BaseModel):
    response: str
    status: str
    tools_executed: List[Dict[str, Any]]
    plan: Optional[List[str]] = None
    engine: Optional[str] = "langgraph"

class OpenBrowserRequest(BaseModel):
    url: Optional[str] = "https://web.whatsapp.com"


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.get("/", response_class=FileResponse)
@app.get("/hud", response_class=FileResponse)
async def serve_hud():
    """Serves the Second-Display Command Center Web HUD."""
    hud_file = FRONTEND_DIR / "jarvis_command_center.html"
    if hud_file.exists():
        return FileResponse(str(hud_file))
    return HTMLResponse("<h2>HUD not found. Please ensure frontend/jarvis_command_center.html exists.</h2>", status_code=404)


@app.post("/command", response_model=CommandResponse)
async def run_command(req: CommandRequest):
    """
    Receives a natural language command or goal from HUD, voice listener, or Telegram.
    Routes to the LangGraph autonomous engine by default or direct tool loop if specified.
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Command string cannot be empty.")

    loop = asyncio.get_running_loop()

    if req.use_langgraph:
        result = await loop.run_in_executor(None, execute_jarvis_goal, req.command)
    else:
        result = await loop.run_in_executor(None, execute_agent_command, req.command)

    return CommandResponse(
        response=result.get("response", ""),
        status=result.get("status", "success"),
        tools_executed=result.get("tools_executed", []),
        plan=result.get("plan"),
        engine=result.get("engine", "langgraph" if req.use_langgraph else "direct")
    )


@app.post("/goal", response_model=CommandResponse)
async def run_goal(req: CommandRequest):
    """
    Dedicated endpoint for complex, long-running multi-step goals.
    Always executes through the LangGraph planner, executor, and self-correcting verifier.
    """
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty.")

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, execute_jarvis_goal, req.command)

    return CommandResponse(
        response=result.get("response", ""),
        status=result.get("status", "success"),
        tools_executed=result.get("tools_executed", []),
        plan=result.get("plan", []),
        engine="langgraph"
    )


@app.get("/graph")
async def get_graph():
    """Returns the LangGraph architecture schema and live Mermaid flowchart."""
    mermaid_code = get_graph_mermaid_diagram()
    return {
        "engine": "LangGraph Stateful Cyclical Graph",
        "mermaid": mermaid_code,
        "nodes": [
            {"id": "plan_node", "name": "Supervisor / Planner", "description": "Decomposes goals into structured sub-steps"},
            {"id": "agent_node", "name": "Reasoner / Tool Dispatcher", "description": "Formulates tool calls via Gemini 3.8 Flash"},
            {"id": "tool_node", "name": "Tool Execution Engine", "description": "Runs tools, measures latency, logs HUD telemetry"},
            {"id": "verifier_node", "name": "Critic & Reflection", "description": "Validates outputs and handles self-healing loops"},
            {"id": "finalize_node", "name": "Executive Finalizer", "description": "Synthesizes final comprehensive briefing"},
        ]
    }


@app.get("/logs")
async def get_logs(since_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    """
    Returns real-time telemetry buffer entries since `since_id`.
    Polled every 1.5 seconds by the HUD's execution log terminal.
    """
    events = telemetry_buffer.get_events(since_id=since_id, limit=limit)
    return {"events": events, "count": len(events)}


@app.get("/health")
async def health_check():
    """Checks operational status of Gemini brain, Google OAuth, Kaggle, and display geometry."""
    google_token_present = config.GOOGLE_TOKEN_FILE.exists()
    kaggle_creds_present = bool(
        (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY")) or
        (Path.home() / ".kaggle" / "kaggle.json").exists()
    )

    return {
        "status": "healthy",
        "gemini": {
            "configured": bool(config.GEMINI_API_KEY),
            "model": config.GEMINI_MODEL,
        },
        "workspace_oauth": {
            "token_exists": google_token_present,
            "token_path": str(config.GOOGLE_TOKEN_FILE),
        },
        "kaggle": {
            "configured": kaggle_creds_present,
        },
        "telegram": {
            "enabled": bool(config.TELEGRAM_BOT_TOKEN),
            "allowed_user_id": config.ALLOWED_TELEGRAM_USER_ID,
        },
        "dual_display": {
            "second_display_x": config.SECOND_DISPLAY_X,
            "second_display_y": config.SECOND_DISPLAY_Y,
            "hud_geometry": f"{config.HUD_WINDOW_WIDTH}x{config.HUD_WINDOW_HEIGHT}+{config.HUD_WINDOW_X}+{config.HUD_WINDOW_Y}",
            "browser_geometry": f"{config.BROWSER_WINDOW_WIDTH}x{config.BROWSER_WINDOW_HEIGHT}+{config.BROWSER_WINDOW_X}+{config.BROWSER_WINDOW_Y}",
            "chrome_profile": str(config.CHROME_PROFILE_DIR),
        }
    }


@app.post("/open-browser")
async def open_browser(req: Optional[OpenBrowserRequest] = None):
    """
    Launches or brings up the headed Chromium window on Monitor 2 (Right Half)
    to allow the user to scan the WhatsApp QR code, log in to Google, or interact manually.
    """
    target_url = req.url if req and req.url else "https://web.whatsapp.com"
    try:
        loop = asyncio.get_running_loop()
        def _open():
            p = get_or_create_page(target_url)
            p.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            p.bring_to_front()
            return p.title()

        title = await loop.run_in_executor(None, _open)
        telemetry_buffer.add_event(
            event_type="browser",
            message=f"Opened browser window on Monitor 2: {target_url}",
            status="success"
        )
        return {
            "status": "opened",
            "url": target_url,
            "page_title": title,
            "display": f"Monitor 2 Right Half (X={config.BROWSER_WINDOW_X}, Y={config.BROWSER_WINDOW_Y})"
        }
    except Exception as e:
        telemetry_buffer.add_event(
            event_type="browser",
            message=f"Failed to open browser: {str(e)}",
            status="error"
        )
        raise HTTPException(status_code=500, detail=f"Error launching browser: {str(e)}")


def run_server():
    """Runs the FastAPI application via uvicorn."""
    uvicorn.run(
        "server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    run_server()
