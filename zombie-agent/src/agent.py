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
    ToolResultBlock,
    UserMessage,
)
from claude_agent_sdk.types import HookMatcher

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
        max_turns=40,
        env={"ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY},
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


async def _emit_step_complete(
    block: ToolResultBlock, sender: Callable[[dict[str, Any]], Awaitable[None]]
) -> None:
    """Emit a `step_complete` event for an `mcp__postgres__execute_sql`
    tool result. Only fires for tool calls that the PreToolUse hook saw
    a `step_start` for (i.e. SQL queries) — Skill / Task / publish_finding
    tool results bypass this path so they don't show up as 0-row SQL
    steps in the activity panel."""
    if not streaming.was_step_started(block.tool_use_id):
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
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text.strip():
                            await sender(
                                {"type": "assistant_text", "text": block.text}
                            )
                elif isinstance(msg, UserMessage):
                    content = (
                        msg.content if isinstance(msg.content, list) else []
                    )
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            await _emit_step_complete(block, sender)
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
