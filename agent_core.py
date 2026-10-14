"""
Jarvis Agent Core.
Houses the Gemini 3.8 Flash multi-step tool-calling loop,
real-time telemetry buffer, tool dispatcher, and Jarvis system persona.
"""

import os
import time
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

import config
from tools import (
    get_todays_tasks_and_schedule,
    get_yesterdays_email_replies,
    compose_or_send_email,
    search_or_upload_google_drive,
    send_whatsapp_message,
    read_recent_whatsapp_messages,
    run_colab_notebook_on_display2,
    manage_kaggle,
    search_local_files_on_laptop,
    upload_local_file_to_website,
)

# ---------------------------------------------------------
# TELEMETRY BUFFER (Thread-Safe Event Stream for HUD)
# ---------------------------------------------------------
class TelemetryBuffer:
    """Stores telemetry logs for real-time polling by the HUD terminal."""
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._events: List[Dict[str, Any]] = []
        self._counter = 0

    def add_event(
        self,
        event_type: str,
        message: str,
        tool_name: str = "",
        args: Optional[Dict[str, Any]] = None,
        output: Optional[Any] = None,
        duration_ms: Optional[float] = None,
        status: str = "info"
    ) -> Dict[str, Any]:
        self._counter += 1
        now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event = {
            "id": self._counter,
            "timestamp": now_str,
            "type": event_type,
            "message": message,
            "tool_name": tool_name,
            "args": args or {},
            "output": str(output) if output is not None else None,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "status": status,
        }
        self._events.append(event)
        if len(self._events) > self.max_size:
            self._events.pop(0)
        return event

    def get_events(self, since_id: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        filtered = [e for e in self._events if e["id"] > since_id]
        return filtered[-limit:]

telemetry_buffer = TelemetryBuffer()

# Initial startup event
telemetry_buffer.add_event(
    event_type="system",
    message="Jarvis Agent Core initialized with Gemini 3.8 Flash brain.",
    status="success"
)

# ---------------------------------------------------------
# TOOL REGISTRY & FUNCTION DECLARATIONS
# ---------------------------------------------------------
TOOL_FUNCTIONS = [
    get_todays_tasks_and_schedule,
    get_yesterdays_email_replies,
    compose_or_send_email,
    search_or_upload_google_drive,
    send_whatsapp_message,
    read_recent_whatsapp_messages,
    run_colab_notebook_on_display2,
    manage_kaggle,
    search_local_files_on_laptop,
    upload_local_file_to_website,
]

TOOL_MAP = {func.__name__: func for func in TOOL_FUNCTIONS}

# ---------------------------------------------------------
# SYSTEM INSTRUCTION & WORKFLOW SPECIFICATION
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = f"""You are JARVIS, an expert autonomous personal AI assistant and workspace orchestrator.
You run on the user's laptop and have full command over a dedicated Add-On Second Display (Monitor 2).
Monitor 2 is configured with a Sci-Fi Command Center HUD on the left half (X={config.HUD_WINDOW_X}, Y={config.HUD_WINDOW_Y})
and live Playwright automation windows pinned to the right half (X={config.BROWSER_WINDOW_X}, Y={config.BROWSER_WINDOW_Y}, Size={config.BROWSER_WINDOW_WIDTH}x{config.BROWSER_WINDOW_HEIGHT}).
The primary laptop screen (Monitor 1) remains completely uninterrupted.

You possess concrete, working tools that you MUST invoke autonomously:
1. `get_todays_tasks_and_schedule()`:
   - Fetches today's Google Calendar events and pending Google Tasks.
   - Use whenever user asks "Show me today's tasks", "What's on my schedule today?", "Any meetings?", or "What do I need to do?".
2. `get_yesterdays_email_replies(sender_or_query)`:
   - Reads Gmail threads from the last 24-48 hours with sender, subject, and preview snippet.
   - Use when user asks "Tell me about my yesterday's mail reply" or asks about recent correspondence.
3. `compose_or_send_email(recipient, subject, body, attachment_path, send_now)`:
   - Composes a Gmail draft (send_now=False) or sends an email immediately (send_now=True).
   - If user asks to compose a mail to a person by name without an email address, first check `get_yesterdays_email_replies` or search to find their email address if possible, or format the draft with the known address.
4. `search_or_upload_google_drive(query, upload_local_path)`:
   - Searches Google Drive files or uploads local files and returns webViewLinks.
5. `send_whatsapp_message(contact_name, message_text)`:
   - Automates WhatsApp Web on the right half of Monitor 2 in persistent headed mode.
   - Use when user says "Send a WhatsApp message to [Contact] that [message]".
6. `read_recent_whatsapp_messages(contact_name, count)`:
   - Reads incoming and outgoing messages from a WhatsApp chat.
7. `run_colab_notebook_on_display2(notebook_url, run_all_cells)`:
   - Opens a Google Colab notebook on Monitor 2 and triggers 'Run all cells' (Ctrl+F9).
8. `manage_kaggle(action, target, download_dir)`:
   - Wraps Kaggle API to list/download datasets or competitions, and check kernel execution.
9. `search_local_files_on_laptop(filename_query, search_root)`:
   - Recursively searches laptop directories (Documents, Downloads, Desktop, etc.) for matching files, returning absolute paths.
10. `upload_local_file_to_website(target_url, local_file_path, additional_instructions)`:
   - Opens target_url on Monitor 2 and uploads the local file into the file input.

WORKFLOW CHAINING RULES:
- When a user asks: "Search this file in my system and send to xyz.com" or "Upload file to xyz":
  Step 1: Call `search_local_files_on_laptop` with the filename query to find the exact local absolute path.
  Step 2: Inspect the found file path. If `xyz.com` is a website (or target URL), call `upload_local_file_to_website(target_url="https://xyz.com", local_file_path=...)`.
  Step 3: If `xyz.com` was an email address or recipient, use `compose_or_send_email` with `attachment_path`.
- When a user asks to email a person:
  If an attachment is mentioned, search for the file first to locate the local path, then call `compose_or_send_email`.

COMMUNICATION STYLE:
- Crisp, professional, and efficient.
- State which tools you ran and their real-world outcomes.
- Present summaries with clear Markdown formatting.
"""

# ---------------------------------------------------------
# GEMINI CLIENT INITIALIZATION
# ---------------------------------------------------------
def get_gemini_client() -> Optional[genai.Client]:
    """Initializes and returns the official Google GenAI SDK client."""
    api_key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------
# MULTI-STEP AGENT LOOP
# ---------------------------------------------------------
def execute_agent_command(user_prompt: str, max_turns: int = 8) -> Dict[str, Any]:
    """
    Executes a user command through Gemini 3.8 Flash in an autonomous multi-step tool-calling loop.
    Emits granular telemetry events to the HUD buffer for every turn and tool execution.

    Args:
        user_prompt: Natural language user command.
        max_turns: Maximum tool-execution iterations permitted.

    Returns:
        Dict containing final answer, list of tools executed, and status.
    """
    telemetry_buffer.add_event(
        event_type="user_prompt",
        message=f"Received command: '{user_prompt}'",
        status="running"
    )

    client = get_gemini_client()
    if not client:
        msg = (
            "⚠️ **Gemini API Key Missing!**\n"
            "Please add `GEMINI_API_KEY=your_key` to your `.env` file in the project root.\n"
            "You can generate a key for free at: https://aistudio.google.com/"
        )
        telemetry_buffer.add_event(
            event_type="system",
            message="Execution halted: GEMINI_API_KEY is not configured.",
            status="error"
        )
        return {"response": msg, "tools_executed": [], "status": "error"}

    # Prepare tool configuration with automatic function calling disabled
    # so we maintain strict telemetry visibility and control
    gen_config = types.GenerateContentConfig(
        tools=TOOL_FUNCTIONS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2,
    )

    # Conversation contents
    contents: List[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        )
    ]

    tools_executed_list: List[Dict[str, Any]] = []

    for turn in range(1, max_turns + 1):
        try:
            telemetry_buffer.add_event(
                event_type="llm_request",
                message=f"Sending request to {config.GEMINI_MODEL} (Turn {turn}/{max_turns})...",
                status="running"
            )

            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=contents,
                config=gen_config,
            )
        except Exception as e:
            err_msg = f"Gemini API invocation error: {str(e)}"
            telemetry_buffer.add_event(
                event_type="system",
                message=err_msg,
                status="error"
            )
            return {
                "response": f"⚠️ An error occurred while communicating with Gemini ({config.GEMINI_MODEL}):\n`{str(e)}`",
                "tools_executed": tools_executed_list,
                "status": "error"
            }

        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            return {
                "response": "⚠️ Model produced an empty response.",
                "tools_executed": tools_executed_list,
                "status": "error"
            }

        # Append model response content to history
        contents.append(candidate.content)

        # Check for function calls
        function_calls = response.function_calls

        if not function_calls:
            # Model finished reasoning and returned final text response
            final_text = response.text or "(Action completed without commentary)"
            telemetry_buffer.add_event(
                event_type="agent_response",
                message="Jarvis completed response.",
                output=final_text[:200] + ("..." if len(final_text) > 200 else ""),
                status="success"
            )
            return {
                "response": final_text,
                "tools_executed": tools_executed_list,
                "status": "success"
            }

        # Process each tool call requested by Gemini
        function_response_parts = []

        for call in function_calls:
            func_name = call.name
            func_args = dict(call.args) if call.args else {}

            telemetry_buffer.add_event(
                event_type="tool_start",
                message=f"Executing tool: {func_name}",
                tool_name=func_name,
                args=func_args,
                status="running"
            )

            start_t = time.time()
            tool_output_str = ""
            status_flag = "success"

            target_func = TOOL_MAP.get(func_name)
            if target_func:
                try:
                    raw_result = target_func(**func_args)
                    tool_output_str = str(raw_result)
                except Exception as t_err:
                    status_flag = "error"
                    tool_output_str = f"Tool execution failed with exception: {str(t_err)}\n{traceback.format_exc()}"
            else:
                status_flag = "error"
                tool_output_str = f"Error: Tool '{func_name}' is not recognized in the Jarvis registry."

            elapsed_ms = (time.time() - start_t) * 1000.0

            telemetry_buffer.add_event(
                event_type="tool_end",
                message=f"Finished {func_name} in {elapsed_ms:.1f}ms",
                tool_name=func_name,
                args=func_args,
                output=tool_output_str[:300] + ("..." if len(tool_output_str) > 300 else ""),
                duration_ms=elapsed_ms,
                status=status_flag
            )

            tools_executed_list.append({
                "tool": func_name,
                "args": func_args,
                "duration_ms": elapsed_ms,
                "status": status_flag
            })

            # Create standard function response part
            function_response_parts.append(
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": tool_output_str}
                )
            )

        # Append tool response parts as role 'tool'
        contents.append(
            types.Content(
                role="tool",
                parts=function_response_parts
            )
        )

    # Reached turn limit
    limit_msg = "ℹ️ Jarvis reached the maximum automated tool execution turn limit."
    telemetry_buffer.add_event(
        event_type="system",
        message=limit_msg,
        status="warning"
    )
    return {
        "response": limit_msg,
        "tools_executed": tools_executed_list,
        "status": "warning"
    }
