# JARVIS — Dual-Display Autonomous AI Workspace & Desktop Agent

An autonomous multi-display personal AI agent powered by **Google Gemini 3.8 Flash**, **FastAPI**, **Playwright**, and a **Sci-Fi Command Center HUD** running on your add-on second display (**Monitor 2**), keeping your primary laptop display (**Monitor 1**) completely uninterrupted.

---

## 🌟 Key Features

- **Dual-Display Architecture**:
  - **Monitor 1 (Laptop)**: 100% free for your work, coding, and day-to-day tasks.
  - **Monitor 2 (Left Half)**: Dark-mode Sci-Fi Command Center HUD dashboard (`jarvis_command_center.html`).
  - **Monitor 2 (Right Half)**: Persistent headed Playwright Chromium window pinned for WhatsApp Web, Google Colab, Kaggle, and web form automations.
- **⚡ LangGraph Autonomous Goal Engine (`jarvis_graph.py`)**:
  - **Supervisor / Planner Node**: Decomposes high-level objectives into structured sub-steps.
  - **Reasoner / Tool Node**: Gemini 3.8 Flash assesses step progress and invokes tools.
  - **Critic & Reflection Node**: Audits tool outputs, catches missing files/auth, and performs self-healing retries.
  - **Executive Finalizer Node**: Synthesizes end-to-end outcome reports.
  - **State Checkpointing**: In-memory `MemorySaver` preserves multi-turn session state.
- **LLM Brain**: Official Google GenAI SDK (`google-genai`) with Gemini 3.8 Flash multi-step tool-calling loop and granular telemetry buffer.
- **3 Simultaneous Interfaces**:
  1. **Second-Screen Web HUD**: Native browser speech recognition (`en-IN`), 1-click preset workflows, voice readback synthesis, and live execution telemetry terminal.
  2. **Room Voice Listener**: Background microphone wake-word listener (`"jarvis"`) with offline TTS.
  3. **Phone Telegram Bot**: Secure remote assistant worker supporting text commands and voice notes.
- **Autonomous Toolset**:
  - **Google Workspace**: Calendar events, Google Tasks, Gmail threads/replies/drafts, and Drive search/upload.
  - **WhatsApp Web**: Persistent session messaging and chat history extraction on Monitor 2.
  - **Google Colab & Kaggle**: Automated Colab notebook execution (`Ctrl+F9`) and Kaggle dataset/competition management.
  - **System File Search & Web Upload**: Recursive local laptop file search and automated website file upload.

---

## ⚡ Operating Jarvis in Goal Mode (`/goal`)

Jarvis can execute long-running, multi-step autonomous workflows using the `/goal` command:

```text
/goal Search sales invoice on laptop, upload it to xyz.com, and send a WhatsApp message to Shashank that invoice is uploaded.
```

When `/goal` is used, the **LangGraph Planner** automatically:
1. Decomposes the goal into sequential sub-steps.
2. Displays the execution plan visually in the HUD.
3. Coordinates Playwright automation on **Monitor 2 (Right Half)**.
4. Reflects on outcomes and self-heals errors.
5. Emits a final executive briefing to the user.

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` and set your `GEMINI_API_KEY`:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
SECOND_DISPLAY_X=1920
SECOND_DISPLAY_Y=0
```

### 3. Google Workspace OAuth (One-time)
Place your `credentials.json` (OAuth Client ID - Desktop App from Google Cloud Console) in the root directory and run:
```bash
python setup_google_oauth.py
```

### 4. Launch Jarvis Dual-Display Agent
- **macOS / Linux**:
  ```bash
  ./start_jarvis_linux_mac.sh
  ```
- **Windows**:
  ```cmd
  start_jarvis_windows.bat
  ```

---

## 📐 Project Structure

```
├── config.py                 # Configuration and display geometry
├── agent_core.py             # Gemini 3.8 Flash multi-step agent loop & telemetry buffer
├── server.py                 # FastAPI orchestrator server
├── telegram_bot.py           # Remote Telegram bot worker
├── voice_listener.py         # Room microphone wake-word listener
├── setup_google_oauth.py     # OAuth token generator for Google Workspace
├── frontend/
│   └── jarvis_command_center.html  # Single-file HUD Command Center
├── tools/
│   ├── workspace_tools.py    # Calendar, Tasks, Gmail, Drive
│   ├── whatsapp_web_tool.py  # Playwright WhatsApp automation
│   ├── colab_kaggle_tools.py # Colab & Kaggle tools
│   ├── system_file_tools.py  # File search & web uploader
│   └── browser_session.py    # Headed Chromium session manager
├── start_jarvis_linux_mac.sh # macOS/Linux launcher
└── start_jarvis_windows.bat  # Windows launcher
```

---

## 🔒 Security
- All sensitive API keys and tokens (`.env`, `credentials.json`, `token.json`, browser session profiles) are excluded via `.gitignore`.
- Telegram bot is restricted to your designated `ALLOWED_TELEGRAM_USER_ID`.
