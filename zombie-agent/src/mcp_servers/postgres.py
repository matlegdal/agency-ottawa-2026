"""External Postgres MCP server config.

Runs `crystaldba/postgres-mcp` as a stdio subprocess in restricted (read-only)
mode. The Claude Agent SDK launches the container, talks JSON-RPC over stdin
/stdout, and exposes the server's tools to the orchestrator and any subagent
under the `mcp__postgres__*` namespace.

The five tools the agent will see:

  - mcp__postgres__execute_sql
  - mcp__postgres__explain_query
  - mcp__postgres__list_schemas
  - mcp__postgres__list_objects
  - mcp__postgres__get_object_details

`--access-mode=restricted` lets the container's SQL parser refuse anything that
isn't read-only. We still belt-and-suspender that at the agent layer with
`safe_sql_hook`.
"""

from typing import Any


def build_postgres_mcp(database_url: str) -> dict[str, Any]:
    """Build the stdio MCP config for crystaldba/postgres-mcp.

    Args:
        database_url: A `postgresql://...` URL the MCP container can reach.
            Use `host.docker.internal` (not `localhost`) for a Postgres
            running on the host on macOS/Windows Docker Desktop.

    Returns:
        The dict expected under `ClaudeAgentOptions.mcp_servers["postgres"]`.
    """
    return {
        "type": "stdio",
        "command": "docker",
        "args": [
            "run",
            "--rm",
            "-i",
            "-e",
            "DATABASE_URI",
            "crystaldba/postgres-mcp",
            "--access-mode=restricted",
            "--transport=stdio",
        ],
        "env": {"DATABASE_URI": database_url},
    }
