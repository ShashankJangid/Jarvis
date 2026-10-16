"""
Jarvis Advanced LangGraph Autonomous Goal & Task Engine.
Implements a stateful cyclical directed graph:
  [START]
     │
  [plan_node] (Decompose high-level goal into structured sub-steps)
     │
  [agent_node] ◄───────────────┐ (Reasoner & Tool Calling)
     │                         │
     ├─► [tool_node]           │
     │      │                  │
     │   [verifier_node] ──────┘ (Critic, Reflection, & Self-Correction)
     │
     └─► [finalize_node] ──► [END]
Emits live telemetry directly to the Second-Screen HUD and supports graph inspection via Mermaid.
"""

import os
import time
import json
import traceback
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from google.genai import types

import config
from agent_core import (
    get_gemini_client,
    telemetry_buffer,
    TOOL_MAP,
    TOOL_FUNCTIONS,
    SYSTEM_INSTRUCTION,
)

# ---------------------------------------------------------
# GRAPH STATE SCHEMA
# ---------------------------------------------------------
class JarvisGraphState(TypedDict):
    task: str
    plan: List[str]
    current_step_index: int
    messages: List[Dict[str, Any]]
    tools_executed: List[Dict[str, Any]]
    latest_tool_calls: List[Dict[str, Any]]
    latest_tool_results: List[Dict[str, Any]]
    verification_feedback: str
    retry_count: int
    final_response: str
    is_complete: bool

# ---------------------------------------------------------
# NODE IMPLEMENTATIONS
# ---------------------------------------------------------
def plan_node(state: JarvisGraphState) -> Dict[str, Any]:
    """
    Supervisor / Planner Node:
    Decomposes the user's high-level task into concrete executable sub-steps.
    """
    task = state["task"]
    telemetry_buffer.add_event(
        event_type="planner",
        message=f"[LangGraph Planner] Analyzing goal and formulating multi-step plan: '{task}'",
        status="running"
    )

    client = get_gemini_client()
    if not client:
        return {
            "plan": [task],
            "current_step_index": 0,
            "final_response": "⚠️ Gemini API key is missing. Please configure GEMINI_API_KEY in .env.",
            "is_complete": True,
        }

    planning_prompt = f"""You are the Master Planner for JARVIS Autonomous Agent.
Given the user goal below, decompose it into a logical, numbered list of 1 to 5 sequential execution steps.
Available capabilities:
- Google Calendar & Tasks: Check today's schedule and to-dos
- Gmail: Search recent emails/replies, compose drafts or send emails
- WhatsApp Web (Monitor 2): Send messages or read recent chats
- Google Colab & Kaggle: Run notebooks on Monitor 2, download/manage Kaggle datasets
- Laptop File System & Web Upload: Search local files, upload files to websites on Monitor 2
- Google Drive: Search or upload files to Drive

If the task is simple and atomic (e.g. 'Show me today\'s tasks'), output exactly 1 step.
Return ONLY a valid JSON list of strings, for example:
["Search for sales_report.pdf on laptop", "Open https://xyz.com and upload the file", "Send WhatsApp message to Shashank confirming upload"]

User Goal: {task}
"""

    try:
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=planning_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        plan_steps = json.loads(resp.text)
        if not isinstance(plan_steps, list) or not plan_steps:
            plan_steps = [task]
    except Exception as e:
        plan_steps = [task]

    telemetry_buffer.add_event(
        event_type="planner",
        message=f"[LangGraph Planner] Generated {len(plan_steps)} sub-step plan: {', '.join(plan_steps)}",
        output=json.dumps(plan_steps),
        status="success"
    )

    return {
        "plan": plan_steps,
        "current_step_index": 0,
        "retry_count": 0,
        "verification_feedback": "",
        "latest_tool_calls": [],
        "latest_tool_results": [],
        "tools_executed": state.get("tools_executed", []),
        "is_complete": False,
    }


def agent_node(state: JarvisGraphState) -> Dict[str, Any]:
    """
    Reasoner / Agent Node:
    Assesses current plan progress, feedback from the verifier, and invokes tools.
    """
    task = state["task"]
    plan = state.get("plan", [task])
    step_idx = state.get("current_step_index", 0)
    current_step = plan[step_idx] if step_idx < len(plan) else "Finalize task"
    feedback = state.get("verification_feedback", "")
    tools_history = state.get("tools_executed", [])

    telemetry_buffer.add_event(
        event_type="reasoner",
        message=f"[LangGraph Reasoner] Processing Step {step_idx + 1}/{len(plan)}: '{current_step}'",
        status="running"
    )

    client = get_gemini_client()
    if not client:
        return {
            "latest_tool_calls": [],
            "final_response": "⚠️ Gemini API key is missing.",
            "is_complete": True,
        }

    # Build contextual prompt for the step
    context_lines = [
        f"Overall User Goal: {task}",
        f"Master Plan: {json.dumps(plan)}",
        f"Active Step ({step_idx + 1}/{len(plan)}): {current_step}",
    ]
    if tools_history:
        context_lines.append(f"Completed Tools So Far: {json.dumps([t['tool'] for t in tools_history])}")
    if feedback:
        context_lines.append(f"Feedback/Correction from Previous Step: {feedback}")

    agent_prompt = "\n".join(context_lines) + "\n\nExecute the required tool for this step, or formulate the response if complete."

    gen_config = types.GenerateContentConfig(
        tools=TOOL_FUNCTIONS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2,
    )

    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=agent_prompt,
            config=gen_config,
        )
    except Exception as e:
        err_msg = f"Gemini API error during reasoning: {str(e)}"
        telemetry_buffer.add_event(event_type="system", message=err_msg, status="error")
        return {
            "latest_tool_calls": [],
            "final_response": f"⚠️ Reasoning error: {str(e)}",
            "is_complete": True,
        }

    function_calls = response.function_calls
    if function_calls:
        tool_calls_data = []
        for call in function_calls:
            tool_calls_data.append({
                "name": call.name,
                "args": dict(call.args) if call.args else {}
            })
        return {
            "latest_tool_calls": tool_calls_data,
        }
    else:
        # No tool called, response text generated
        final_text = response.text or "Step completed."
        return {
            "latest_tool_calls": [],
            "final_response": final_text,
            "is_complete": (step_idx >= len(plan) - 1),
        }


def tool_node(state: JarvisGraphState) -> Dict[str, Any]:
    """
    Tool Execution Node:
    Executes the scheduled tools, records latency, and emits live HUD telemetry.
    """
    tool_calls = state.get("latest_tool_calls", [])
    executed_results = []
    tools_history = list(state.get("tools_executed", []))

    for call in tool_calls:
        name = call["name"]
        args = call["args"]

        telemetry_buffer.add_event(
            event_type="tool_start",
            message=f"[LangGraph ToolNode] Executing: {name}",
            tool_name=name,
            args=args,
            status="running"
        )

        start_t = time.time()
        func = TOOL_MAP.get(name)
        status_flag = "success"
        output_str = ""

        if func:
            try:
                raw_out = func(**args)
                output_str = str(raw_out)
            except Exception as e:
                status_flag = "error"
                output_str = f"Execution error in {name}: {str(e)}\n{traceback.format_exc()}"
        else:
            status_flag = "error"
            output_str = f"Tool '{name}' not found in registry."

        elapsed_ms = (time.time() - start_t) * 1000.0

        telemetry_buffer.add_event(
            event_type="tool_end",
            message=f"[LangGraph ToolNode] Completed {name} in {elapsed_ms:.1f}ms",
            tool_name=name,
            args=args,
            output=output_str[:300] + ("..." if len(output_str) > 300 else ""),
            duration_ms=elapsed_ms,
            status=status_flag
        )

        record = {
            "tool": name,
            "args": args,
            "output": output_str,
            "duration_ms": elapsed_ms,
            "status": status_flag
        }
        executed_results.append(record)
        tools_history.append(record)

    return {
        "latest_tool_results": executed_results,
        "tools_executed": tools_history,
        "latest_tool_calls": [],
    }


def verifier_node(state: JarvisGraphState) -> Dict[str, Any]:
    """
    Critic & Self-Correction Node:
    Evaluates tool outcomes, detects partial failures, handles retries,
    and advances plan sub-steps.
    """
    results = state.get("latest_tool_results", [])
    step_idx = state.get("current_step_index", 0)
    plan = state.get("plan", [])
    retry_count = state.get("retry_count", 0)

    has_error = any(r.get("status") == "error" for r in results)
    needs_qr = any("QR" in str(r.get("output", "")) for r in results)
    file_not_found = any("not found" in str(r.get("output", "")).lower() for r in results)

    if has_error or (file_not_found and retry_count < 2):
        retry_count += 1
        feedback = f"Step failed or produced incomplete results: {[r.get('output', '')[:100] for r in results]}. Self-correct parameters or check alternative paths."
        telemetry_buffer.add_event(
            event_type="verifier",
            message=f"[LangGraph Verifier] Detected issue in Step {step_idx + 1}. Triggering self-correction loop (Attempt {retry_count}).",
            status="warning"
        )
        return {
            "retry_count": retry_count,
            "verification_feedback": feedback,
            "is_complete": False,
        }

    # Step successful: advance to next plan step
    next_idx = step_idx + 1
    telemetry_buffer.add_event(
        event_type="verifier",
        message=f"[LangGraph Verifier] Step {step_idx + 1}/{len(plan)} verified successfully! Advancing.",
        status="success"
    )

    is_complete = next_idx >= len(plan)
    return {
        "current_step_index": next_idx,
        "retry_count": 0,
        "verification_feedback": "",
        "is_complete": is_complete,
    }


def finalize_node(state: JarvisGraphState) -> Dict[str, Any]:
    """
    Finalizer Node:
    Synthesizes the complete outcomes into a cohesive, structured response for the user.
    """
    task = state["task"]
    plan = state.get("plan", [])
    history = state.get("tools_executed", [])
    existing_resp = state.get("final_response", "")

    telemetry_buffer.add_event(
        event_type="finalizer",
        message=f"[LangGraph Finalizer] Synthesizing final report across {len(history)} executed actions.",
        status="running"
    )

    client = get_gemini_client()
    if not client or (existing_resp and not history):
        final_out = existing_resp or "Goal successfully executed."
    else:
        synth_prompt = f"""You are JARVIS. Synthesize a clean, professional, structured Markdown report of the goal execution.
Goal: {task}
Plan Executed: {json.dumps(plan)}
Actions and Tool Outputs:
{json.dumps([{'tool': h['tool'], 'output': h['output'][:400]} for h in history], indent=2)}

Include:
- Clear headline and status
- Summary of what was accomplished across Monitor 1 and Monitor 2
- Specific links, recipients, or files affected
Keep it crisp, polite, and executive.
"""
        try:
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=synth_prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            final_out = resp.text.strip()
        except Exception:
            final_out = existing_resp or "Goal completed successfully."

    telemetry_buffer.add_event(
        event_type="finalizer",
        message="[LangGraph Finalizer] Goal execution complete. Response ready.",
        status="success"
    )

    return {
        "final_response": final_out,
        "is_complete": True,
    }


# ---------------------------------------------------------
# CONDITIONAL EDGES
# ---------------------------------------------------------
def route_after_agent(state: JarvisGraphState) -> str:
    """Routes to tool execution if tools were requested, otherwise finalizes."""
    if state.get("latest_tool_calls"):
        return "tool_node"
    return "finalize_node"


def route_after_verifier(state: JarvisGraphState) -> str:
    """Routes back to agent for next step or retry, or to finalizer if done."""
    if state.get("is_complete") or state.get("current_step_index", 0) >= len(state.get("plan", [])):
        return "finalize_node"
    return "agent_node"


# ---------------------------------------------------------
# GRAPH COMPILATION
# ---------------------------------------------------------
def build_jarvis_graph():
    """Builds and compiles the stateful LangGraph application."""
    workflow = StateGraph(JarvisGraphState)

    # Register nodes
    workflow.add_node("plan_node", plan_node)
    workflow.add_node("agent_node", agent_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("verifier_node", verifier_node)
    workflow.add_node("finalize_node", finalize_node)

    # Add edges
    workflow.add_edge(START, "plan_node")
    workflow.add_edge("plan_node", "agent_node")

    workflow.add_conditional_edges(
        "agent_node",
        route_after_agent,
        {
            "tool_node": "tool_node",
            "finalize_node": "finalize_node",
        }
    )

    workflow.add_edge("tool_node", "verifier_node")

    workflow.add_conditional_edges(
        "verifier_node",
        route_after_verifier,
        {
            "agent_node": "agent_node",
            "finalize_node": "finalize_node",
        }
    )

    workflow.add_edge("finalize_node", END)

    # Compile with in-memory checkpointer
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app

# Singleton compiled graph instance
jarvis_graph_app = build_jarvis_graph()


def get_graph_mermaid_diagram() -> str:
    """Generates Mermaid diagram definition of the LangGraph architecture."""
    try:
        return jarvis_graph_app.get_graph().draw_mermaid()
    except Exception as e:
        # Fallback standard representation
        return """graph TD
    START([START]) --> plan_node[Supervisor / Planner Node]
    plan_node --> agent_node[Reasoner & Tool Calling Node]
    agent_node -->|Tool Calls| tool_node[Tool Execution Node]
    tool_node --> verifier_node[Critic & Self-Correction Node]
    verifier_node -->|Next Step or Retry| agent_node
    verifier_node -->|Plan Complete| finalize_node[Executive Finalizer Node]
    agent_node -->|Direct Response| finalize_node
    finalize_node --> END([END])
"""


def execute_jarvis_goal(goal_prompt: str, thread_id: str = "default_session") -> Dict[str, Any]:
    """
    Executes a high-level goal using the full LangGraph state engine.
    Returns structured results including plan, executed tools, and final response.
    """
    telemetry_buffer.add_event(
        event_type="system",
        message=f"[LangGraph Goal] Launching autonomous graph pipeline for: '{goal_prompt}'",
        status="running"
    )

    initial_state: JarvisGraphState = {
        "task": goal_prompt,
        "plan": [],
        "current_step_index": 0,
        "messages": [],
        "tools_executed": [],
        "latest_tool_calls": [],
        "latest_tool_results": [],
        "verification_feedback": "",
        "retry_count": 0,
        "final_response": "",
        "is_complete": False,
    }

    config_dict = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = jarvis_graph_app.invoke(initial_state, config=config_dict)
        return {
            "response": final_state.get("final_response", "Goal execution finished."),
            "plan": final_state.get("plan", []),
            "tools_executed": final_state.get("tools_executed", []),
            "status": "success",
            "engine": "langgraph"
        }
    except Exception as e:
        err_msg = f"LangGraph execution exception: {str(e)}\n{traceback.format_exc()}"
        telemetry_buffer.add_event(event_type="system", message=err_msg, status="error")
        return {
            "response": f"⚠️ LangGraph goal pipeline failed: {str(e)}",
            "plan": [],
            "tools_executed": [],
            "status": "error",
            "engine": "langgraph"
        }
