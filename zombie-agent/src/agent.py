"""Orchestrator wiring + run loop.

Builds the `ClaudeAgentOptions` from config and exposes a single async
entry point, `run_question`, that the FastAPI websocket route calls per
user question. The orchestrator decomposes, queries Postgres via the
external MCP, delegates verification to the `verifier` subagent, and
pushes structured findings via the in-process `ui_bridge` MCP server.

Note on `step_complete` events: the SDK does NOT reliably populate
`tool_response` in PostToolUse hooks for MCP tools (we observed empty
`tool_response` even when the tool returned thousands of bytes of data).
So step-complete is emitted from this module's message loop, where the
real `ToolResultBlock` does land, rather than from a hook.

The message loop also surfaces ALL tool calls (not just SQL) to the UI
so the activity panel can show Skill loads, subagent spawns, and finding
publications. AssistantMessage.parent_tool_use_id is propagated so the
UI can render subagent activity nested under the verifier badge.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import (
    HookMatcher,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
)

from src import streaming
from src.config import WORKSPACE_DIR, config
from src.hooks import (
    count_rows,
    inject_context_hook,
    safe_sql_hook,
    subagent_stop_hook,
)
from src.mcp_servers import build_postgres_mcp, ui_bridge_mcp
from src.system_prompt import SYSTEM_PROMPT
from src.verifier import verifier_agent


logger = logging.getLogger(__name__)


# Tools the orchestrator is permitted to call.
#
# - `Skill` lets it load .claude/skills/*/SKILL.md on demand.
# - `Task` is the canonical SDK name for the subagent-spawn tool. Older
#   SDK builds also expose it as `Agent`; we list both to be defensive.
# - `mcp__postgres__*` are the five tools from `crystaldba/postgres-mcp`.
# - `mcp__ui_bridge__publish_finding` is our in-process tool.
_ORCHESTRATOR_TOOLS = [
    "Skill",
    "Task",
    "Agent",
    "mcp__postgres__execute_sql",
    "mcp__postgres__explain_query",
    "mcp__postgres__list_schemas",
    "mcp__postgres__list_objects",
    "mcp__postgres__get_object_details",
    "mcp__ui_bridge__publish_finding",
]


# Tool-name → (icon, friendly label) lookup for the UI activity panel.
# Mirrors how Claude Code distinguishes its built-in tool calls visually.
_TOOL_DISPLAY: dict[str, tuple[str, str]] = {
    "Skill": ("📚", "Skill"),
    "Task": ("🤖", "Subagent"),
    "Agent": ("🤖", "Subagent"),
    "mcp__postgres__execute_sql": ("🗄️", "SQL"),
    "mcp__postgres__explain_query": ("🗄️", "Explain"),
    "mcp__postgres__list_schemas": ("🗄️", "List schemas"),
    "mcp__postgres__list_objects": ("🗄️", "List objects"),
    "mcp__postgres__get_object_details": ("🗄️", "Object details"),
    "mcp__ui_bridge__publish_finding": ("📌", "Finding"),
}


def build_options() -> ClaudeAgentOptions:
    """Build a fresh options object. Called once per run so each run gets a
    clean MCP server lifecycle."""
    return ClaudeAgentOptions(
        cwd=str(WORKSPACE_DIR),
        setting_sources=["project"],  # required to load .claude/skills/
        model="claude-sonnet-4-6",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=_ORCHESTRATOR_TOOLS,
        mcp_servers={
            "postgres": build_postgres_mcp(config.READONLY_DATABASE_URL),
            "ui_bridge": ui_bridge_mcp,
        },
        agents={"verifier": verifier_agent},
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="mcp__postgres__execute_sql",
                    hooks=[safe_sql_hook],
                )
            ],
            "UserPromptSubmit": [HookMatcher(hooks=[inject_context_hook])],
            "SubagentStop": [HookMatcher(hooks=[subagent_stop_hook])],
        },
        permission_mode="bypassPermissions",
        # The iterative-exploration loop can run 3 follow-up queries per
        # AMBIGUOUS candidate × ~5 candidates on top of the initial discovery
        # phase. 60 turns gives comfortable headroom.
        max_turns=60,
        # Scrub CLAUDECODE / CLAUDE_CODE_ENTRYPOINT so the bundled Claude
        # CLI subprocess doesn't refuse to start when this server is run
        # from inside a Claude Code dev session ("Claude Code cannot be
        # launched inside another Claude Code session"). Setting them to
        # empty strings clears them in the spawned subprocess env.
        env={
            "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
            "CLAUDECODE": "",
            "CLAUDE_CODE_ENTRYPOINT": "",
        },
    )


def _extract_tool_result_text(block: ToolResultBlock) -> str:
    """Pull the first text content out of a ToolResultBlock. The SDK
    delivers the block's `content` either as a list of content dicts (the
    common path for MCP servers that return content blocks) or as a
    plain string (the convenience path for simple tools)."""
    content = block.content
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                return c.get("text", "") or ""
        return ""
    if isinstance(content, str):
        return content
    return ""


def _summarize_tool_input(name: str, tool_input: Any) -> str:
    """Build a one-line summary of a tool call's input for the UI.

    The activity panel needs something compact and meaningful: for SQL we
    already get a labelled `step_start` from the safe_sql_hook, so this
    summarizer is the fallback for everything else (Skill, Task,
    list_objects, publish_finding, etc.)."""
    if not isinstance(tool_input, dict):
        return ""
    if name == "Skill":
        # `command` is the slash-command-style skill name (e.g. "data-quirks").
        return tool_input.get("command") or tool_input.get("skill") or ""
    if name in ("Task", "Agent"):
        return (
            tool_input.get("subagent_type")
            or tool_input.get("description")
            or "subagent"
        )
    if name == "mcp__postgres__list_objects":
        return f"schema={tool_input.get('schema_name', '?')}"
    if name == "mcp__postgres__get_object_details":
        return (
            f"{tool_input.get('schema_name', '?')}."
            f"{tool_input.get('object_name', '?')}"
        )
    if name == "mcp__ui_bridge__publish_finding":
        ent = tool_input.get("entity_name", "?")
        st = tool_input.get("verifier_status", "?")
        return f"{ent} ({st})"
    if name == "mcp__postgres__execute_sql":
        sql = tool_input.get("sql") or ""
        # Mirror the safe_sql_hook's "first meaningful line" treatment.
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:140]
        return ""
    # Generic fallback: short list of input keys.
    keys = list(tool_input.keys())
    return ", ".join(keys[:4])


async def _emit_tool_call(
    block: ToolUseBlock,
    parent_tool_use_id: str | None,
    sender: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Emit a generic `tool_call` event for every tool the assistant uses.

    The safe_sql_hook already emits `step_start` for `execute_sql`, so to
    avoid the activity panel rendering two cards for one SQL query we
    skip those here. Everything else (Skill, Task, list_objects,
    publish_finding, etc.) gets a `tool_call` event instead."""
    if block.name == "mcp__postgres__execute_sql":
        # Already covered by safe_sql_hook → step_start / step_complete.
        return
    icon, label = _TOOL_DISPLAY.get(
        block.name, ("⚙️", block.name.split("__")[-1] or block.name)
    )
    summary = _summarize_tool_input(block.name, block.input)
    await sender(
        {
            "type": "tool_call",
            "id": block.id,
            "tool_name": block.name,
            "icon": icon,
            "label": label,
            "summary": summary,
            "is_subagent": parent_tool_use_id is not None,
            "parent_tool_use_id": parent_tool_use_id,
        }
    )


async def _emit_step_complete(
    block: ToolResultBlock,
    parent_tool_use_id: str | None,
    sender: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Emit a `step_complete` event for an `mcp__postgres__execute_sql`
    tool result. Only fires for tool calls that the PreToolUse hook saw
    a `step_start` for (i.e. SQL queries) — Skill / Task / publish_finding
    tool results bypass this path so they don't show up as 0-row SQL
    steps in the activity panel.

    For non-SQL tool results we emit a lightweight `tool_result` event
    so the UI can flip the matching `tool_call` card into a "done" state.
    """
    if not streaming.was_step_started(block.tool_use_id):
        # Non-SQL tool results — emit a generic completion so the UI can
        # mark the matching `tool_call` card as done.
        text = _extract_tool_result_text(block)
        is_error = bool(getattr(block, "is_error", False))
        await sender(
            {
                "type": "tool_result",
                "id": block.tool_use_id,
                "is_error": is_error,
                "is_subagent": parent_tool_use_id is not None,
                "parent_tool_use_id": parent_tool_use_id,
                "preview": text[:400],
            }
        )
        return

    text = _extract_tool_result_text(block)
    is_error = bool(getattr(block, "is_error", False))
    rows = 0 if is_error else count_rows(text)
    duration_ms = streaming.take_step_duration_ms(block.tool_use_id)
    await sender(
        {
            "type": "step_complete",
            "id": block.tool_use_id,
            "rows": rows,
            "duration_ms": duration_ms,
            "is_error": is_error,
            "is_subagent": parent_tool_use_id is not None,
            "parent_tool_use_id": parent_tool_use_id,
            "preview": text[:600],
        }
    )


async def run_question(
    question: str,
    sender: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Run one investigation against a single websocket connection.

    Args:
        question: The user's natural-language question.
        sender: An async callable that pushes a JSON-serializable dict to
            the client. Hooks and the in-process publish_finding tool both
            use it via the `streaming` module.
    """
    streaming.set_sender(sender)
    options = build_options()

    try:
        await sender({"type": "run_start", "question": question})
        async with ClaudeSDKClient(options=options) as client:
            await client.query(question)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    parent_tool_use_id = getattr(
                        msg, "parent_tool_use_id", None
                    )
                    for block in msg.content:
                        if (
                            isinstance(block, TextBlock)
                            and block.text.strip()
                        ):
                            # Surface narration from the orchestrator
                            # AND from the verifier subagent. The UI uses
                            # `is_subagent` to render verifier text under
                            # the verifier badge.
                            await sender(
                                {
                                    "type": "assistant_text",
                                    "text": block.text,
                                    "is_subagent": parent_tool_use_id
                                    is not None,
                                    "parent_tool_use_id": parent_tool_use_id,
                                }
                            )
                        elif isinstance(block, ToolUseBlock):
                            await _emit_tool_call(
                                block, parent_tool_use_id, sender
                            )
                        elif isinstance(block, ThinkingBlock):
                            # Extended thinking is currently disabled for
                            # demo speed, but if it gets turned on later
                            # we already surface the trace.
                            await sender(
                                {
                                    "type": "thinking",
                                    "text": block.thinking[:1000],
                                    "is_subagent": parent_tool_use_id
                                    is not None,
                                }
                            )
                elif isinstance(msg, UserMessage):
                    parent_tool_use_id = getattr(
                        msg, "parent_tool_use_id", None
                    )
                    content = (
                        msg.content if isinstance(msg.content, list) else []
                    )
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            await _emit_step_complete(
                                block, parent_tool_use_id, sender
                            )
                elif isinstance(msg, TaskStartedMessage):
                    # Subagent task lifecycle: surface to UI so the
                    # verifier badge can flip to "active".
                    await sender(
                        {
                            "type": "task_started",
                            "task_id": msg.task_id,
                            "description": msg.description,
                            "tool_use_id": msg.tool_use_id,
                            "task_type": msg.task_type,
                        }
                    )
                elif isinstance(msg, TaskProgressMessage):
                    await sender(
                        {
                            "type": "task_progress",
                            "task_id": msg.task_id,
                            "description": msg.description,
                            "tool_use_id": msg.tool_use_id,
                            "last_tool_name": msg.last_tool_name,
                            "tool_uses": msg.usage.get("tool_uses"),
                            "duration_ms": msg.usage.get("duration_ms"),
                        }
                    )
                elif isinstance(msg, TaskNotificationMessage):
                    await sender(
                        {
                            "type": "task_notification",
                            "task_id": msg.task_id,
                            "tool_use_id": msg.tool_use_id,
                            "status": msg.status,
                            "summary": msg.summary,
                        }
                    )
                elif isinstance(msg, SystemMessage):
                    # Generic system messages (init, etc.) — keep the UI
                    # informed for debugging but don't render them by
                    # default.
                    logger.debug(
                        "SystemMessage subtype=%s data=%s",
                        getattr(msg, "subtype", None),
                        getattr(msg, "data", None),
                    )
                elif isinstance(msg, ResultMessage):
                    await sender(
                        {
                            "type": "result",
                            "duration_ms": getattr(msg, "duration_ms", None),
                            "total_cost_usd": getattr(
                                msg, "total_cost_usd", None
                            ),
                            "num_turns": getattr(msg, "num_turns", None),
                        }
                    )
        await sender({"type": "run_complete"})
    except Exception as e:
        logger.exception("Agent run failed")
        await sender({"type": "error", "error": str(e)})
    finally:
        streaming.set_sender(None)
