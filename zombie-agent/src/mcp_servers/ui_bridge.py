"""In-process SDK MCP server: `publish_finding`.

The orchestrator calls this every time it has a candidate to surface (with
`verifier_status="pending"`) or a verdict to record (`"verified"` /
`"refuted"`). The tool turns the call into a websocket message that the
briefing panel picks up.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from src.streaming import emit


@tool(
    "publish_finding",
    (
        "Push a candidate or verdict to the briefing panel. Call once per "
        "candidate with verifier_status='pending', then again with 'verified', "
        "'refuted', or 'challenged' as the investigation progresses. Use the "
        "same `bn` value across calls for the same entity so the card updates "
        "in place rather than duplicating."
    ),
    {
        "entity_name": str,
        "bn": str,
        "total_funding_cad": float,
        "last_known_year": int,
        "govt_dependency_pct": float,
        "evidence_summary": str,
        "verifier_status": str,
        "verifier_notes": str,
        "sql_trail": list,
    },
)
async def publish_finding(args: dict[str, Any]) -> dict[str, Any]:
    await emit({"type": "finding", **args})
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Published finding: {args['entity_name']} "
                    f"(status={args['verifier_status']})"
                ),
            }
        ]
    }


ui_bridge_mcp = create_sdk_mcp_server(
    name="ui_bridge",
    version="0.1.0",
    tools=[publish_finding],
)
