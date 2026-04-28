"""Lightweight pub-sub for pushing agent events to the active websocket.

Hooks, the in-process `publish_finding` MCP tool, and the agent message
loop all need to send JSON to whatever client is watching the current run.
They can't import from `router` without creating a cycle, and they can't
take the websocket as an argument because the SDK creates them at module
load time.

The contract: `set_sender(fn)` is called once per run from
`agent.run_question`, then anything that wants to push an event calls
`emit({...})`. When no run is active, `emit` is a silent no-op.

We also keep a per-run dictionary of `tool_use_id -> perf_counter_start`
so that the hook (which fires on PreToolUse) and the agent loop (which
fires when the ToolResultBlock arrives) can cooperate on duration
calculation. The hook records the start; the loop reads it on completion.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional


Sender = Callable[[dict[str, Any]], Awaitable[None]]

_sender: Optional[Sender] = None
_step_starts: dict[str, float] = {}


def set_sender(fn: Optional[Sender]) -> None:
    """Bind a sender for the current run. Pass None to clear."""
    global _sender
    _sender = fn
    if fn is None:
        _step_starts.clear()


async def emit(payload: dict[str, Any]) -> None:
    """Push an event to the bound sender, if any. Silent no-op otherwise."""
    if _sender is None:
        return
    try:
        await _sender(payload)
    except Exception:
        # A dropped websocket should never crash the agent loop.
        pass


def mark_step_start(tool_use_id: str) -> None:
    _step_starts[tool_use_id] = time.perf_counter()


def take_step_duration_ms(tool_use_id: str) -> Optional[int]:
    """Pop the start timestamp for a tool_use_id, returning duration in ms."""
    start = _step_starts.pop(tool_use_id, None)
    if start is None:
        return None
    return int((time.perf_counter() - start) * 1000)


def was_step_started(tool_use_id: str) -> bool:
    """True if `mark_step_start` was called for this tool_use_id and it
    hasn't been popped yet."""
    return tool_use_id in _step_starts
