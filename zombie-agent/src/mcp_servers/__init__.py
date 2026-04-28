"""MCP server builders.

Two servers are defined here:

- `postgres` (external stdio) — `crystaldba/postgres-mcp` running in restricted
  (read-only) mode against the hackathon database.
- `ui_bridge` (in-process SDK MCP) — exposes a single `publish_finding` tool
  that pushes structured findings to the briefing panel.
"""

from .postgres import build_postgres_mcp
from .ui_bridge import ui_bridge_mcp

__all__ = ["build_postgres_mcp", "ui_bridge_mcp"]
