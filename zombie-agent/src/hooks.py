"""Agent hooks.

Three hooks (PostToolUse is gone — the SDK doesn't reliably populate
`tool_response` for MCP tools, so we now emit `step_complete` from the
agent message loop where the real `ToolResultBlock` arrives):

- `safe_sql_hook` (PreToolUse on mcp__postgres__execute_sql) — denies
  destructive SQL, auto-injects LIMIT, marks step start, streams
  `step_start`.
- `inject_context_hook` (UserPromptSubmit) — prepends run-time reminders.
- `subagent_stop_hook` (SubagentStop) — announces verifier completion.

All hooks are best-effort: any exception is swallowed so a hook never
aborts the agent loop.
"""

import ast
import logging
import re
from typing import Any

from src.streaming import emit, mark_step_start


logger = logging.getLogger(__name__)


_DESTRUCTIVE = re.compile(
    # Word-boundary patterns. Avoids matching `created_at`, `updated_at`,
    # etc. (underscore is a word char).
    r"\b(DROP|TRUNCATE|UPDATE|DELETE|INSERT|ALTER|GRANT|REVOKE|VACUUM)\b"
    # `CREATE` is allowed as an identifier (created_at column) but never
    # as a DDL verb against a destructive object kind:
    r"|\bCREATE\s+(TABLE|SCHEMA|DATABASE|ROLE|USER|EXTENSION|VIEW|"
    r"MATERIALIZED|FUNCTION|TRIGGER|INDEX)\b",
    re.IGNORECASE,
)

_AGGREGATE_HINTS = ("count(", "sum(", "avg(", "max(", "min(", "group by")


def _needs_limit(sql: str) -> bool:
    s = sql.lower()
    if "limit" in s:
        return False
    if any(h in s for h in _AGGREGATE_HINTS):
        return False
    return True


def _first_meaningful_line(sql: str) -> str:
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "(empty SQL)"


def _extract_text(response: Any) -> str:
    """Pull the first text block out of an MCP tool_response.

    Used by tests + by the agent message loop. The hook itself no longer
    relies on this — see module docstring.
    """
    if isinstance(response, dict):
        for block in response.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "") or ""
    return ""


def count_rows(text: str) -> int:
    """Best-effort row count for a postgres-mcp execute_sql response.

    crystaldba/postgres-mcp serializes a result set as a single-line
    Python-style list literal:

        "[{'col': 'val', ...}, {'col': 'val', ...}, ...]"

    Try `ast.literal_eval` first; fall back to a regex over `}, {`
    boundaries; and as a last resort count newlines so the value is never
    less informative than zero.
    """
    if not text:
        return 0

    s = text.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return len(parsed)
        except (ValueError, SyntaxError):
            pass
        # Regex fallback for very large literals where literal_eval is slow.
        boundary_count = len(re.findall(r"\}\s*,\s*\{", s))
        if boundary_count or "{" in s:
            return boundary_count + 1

    # Fall back to newline-based count for non-list responses.
    return max(0, text.count("\n") - 1)


# Keep the old underscore-prefixed alias so existing tests keep working.
_count_rows = count_rows


async def safe_sql_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    sql = input_data.get("tool_input", {}).get("sql", "") or ""

    if _DESTRUCTIVE.search(sql):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "This database is read-only. Destructive SQL is blocked "
                    "at the agent layer (and again at the MCP layer)."
                ),
            }
        }

    updated_input = dict(input_data.get("tool_input", {}))
    if _needs_limit(sql):
        updated_input["sql"] = sql.rstrip().rstrip(";") + "\nLIMIT 1000"

    if tool_use_id is not None:
        mark_step_start(tool_use_id)

    label = _first_meaningful_line(sql)
    await emit(
        {
            "type": "step_start",
            "id": tool_use_id,
            "label": label,
            "sql": updated_input.get("sql", sql),
        }
    )

    if updated_input != input_data.get("tool_input"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": updated_input,
            }
        }
    return {}


async def inject_context_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "Today is 2026-04-29. Active challenge: Zombie Recipients "
                "(Challenge #1).\n"
                "Critical reminders before any SQL:\n"
                "  - Don't SUM fed.grants_contributions; use "
                "WHERE is_amendment=false or the agreement_current CTE.\n"
                "  - Filter cra.t3010_impossibilities from CRA financial "
                "aggregations.\n"
                "  - Resolve names via general.entity_golden_records or "
                "vw_entity_funding.\n"
                "  - Group CRA per-org by LEFT(bn, 9), not the 15-character "
                "BN.\n"
                "  - AB: filter by display_fiscal_year, not bare fiscal_year.\n"
                "  - Exclude cra.cra_identification.designation = 'A' from "
                "zombie candidates.\n"
                "  - Charity T3010 has a 6-month filing window from "
                "fiscal_year_end."
            ),
        }
    }


async def subagent_stop_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    agent_name = (
        input_data.get("agent_type")
        or input_data.get("subagent_type")
        or "subagent"
    )
    await emit({"type": "subagent_stop", "agent": agent_name})
    return {}
