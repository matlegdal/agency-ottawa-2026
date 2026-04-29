"""In-process SDK MCP server: `publish_finding`, `publish_universe`,
`publish_dossier`.

- `publish_finding` — call once per candidate with verifier_status='pending',
  then again with 'verified', 'refuted', or 'challenged' as the investigation
  progresses. Use the same `bn` across calls so the card updates in place.

- `publish_universe` — call EXACTLY ONCE at the start of an investigation,
  immediately after Step A returns. Reports the size of the search space
  and how many candidates each gate dropped, so the audience can see the
  WHOLE methodology, not just the survivors. This is explainability:
  "5 candidates from N possible recipients ≥ $1M; M dropped at the
  foundation gate; K dropped at the live-agreement gate".

- `publish_dossier` — call ONCE PER VERIFIED candidate after the verdict
  lands. Carries the per-entity evidence panels (funding-events timeline,
  dependence-ratio history, overhead snapshot, status banner, templated
  story headline). Every value MUST come from a SQL query in this session
  — no LLM authoring of numbers, percentages, dates, or names. The
  headline is a deterministic format string built from already-queried
  values.

All three turn into websocket messages the briefing panel picks up.
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


@tool(
    "publish_universe",
    (
        "Call EXACTLY ONCE at the start of an investigation, after Step A "
        "runs. Reports the search-space size and gate-drop counts so the "
        "audience can audit the methodology end-to-end, not just the "
        "survivors. Every count must come from a SQL query in this session."
    ),
    {
        "n_universe_pre_gate": int,
        "n_after_foundation_filter": int,
        "n_after_live_agreement_filter": int,
        "n_after_non_charity_filter": int,
        "n_final_candidates": int,
        "narrative": str,
        "sql_trail": list,
    },
)
async def publish_universe(args: dict[str, Any]) -> dict[str, Any]:
    await emit({"type": "universe", **args})
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Published universe: {args['n_final_candidates']} "
                    f"candidates from {args['n_universe_pre_gate']} pre-gate."
                ),
            }
        ]
    }


@tool(
    "publish_dossier",
    (
        "Call ONCE PER VERIFIED candidate after the verdict lands. "
        "Carries the per-entity evidence panels. Every numeric or date "
        "value MUST trace to a SQL query in THIS session — no LLM "
        "authoring of figures. The `headline` is a deterministic format "
        "string assembled from already-queried values, NOT an LLM "
        "rewrite. funding_events: list of {year, dept, program, "
        "amount_cad, start_date, end_date}. dependence_history: list of "
        "{fiscal_year, govt_share_pct, total_govt_cad, revenue_cad}. "
        "overhead_snapshot: {fiscal_year, strict_overhead_pct, "
        "programs_cad, admin_fundraising_cad} or {} if unavailable. "
        "death_event_text: e.g. 'Self-dissolved on 2023-03-31 (T3010 "
        "line A2)' or 'Stopped filing T3010 after FY2021'."
    ),
    {
        "bn": str,
        "headline": str,
        "funding_events": list,
        "dependence_history": list,
        "overhead_snapshot": dict,
        "death_event_text": str,
        "sql_trail": list,
    },
)
async def publish_dossier(args: dict[str, Any]) -> dict[str, Any]:
    await emit({"type": "dossier", **args})
    return {
        "content": [
            {
                "type": "text",
                "text": f"Published dossier for BN {args['bn']}.",
            }
        ]
    }


ui_bridge_mcp = create_sdk_mcp_server(
    name="ui_bridge",
    version="0.2.0",
    tools=[publish_finding, publish_universe, publish_dossier],
)
