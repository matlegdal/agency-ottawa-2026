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

Schemas use the explicit JSON-Schema form (`{type, properties, required}`)
rather than the SDK's simple `{name: type}` shorthand because the CORP+PA
addendum adds optional evidence fields. The shorthand marks every key as
required, which would break older call sites that don't supply the new
fields. With the explicit form we can list only the historically-required
keys in `required` and let CORP/PA / lobby fields default to absent.

All three turn into websocket messages the briefing panel picks up.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from src.streaming import emit


# --------------------------------------------------------------------------
# publish_finding
# --------------------------------------------------------------------------

_PUBLISH_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # Core identity / framing
        "entity_name": {"type": "string"},
        "bn": {"type": "string"},
        "total_funding_cad": {"type": "number"},
        "last_known_year": {"type": "integer"},
        "govt_dependency_pct": {"type": "number"},
        "evidence_summary": {"type": "string"},
        "verifier_status": {"type": "string"},
        "verifier_notes": {"type": "string"},
        "sql_trail": {"type": "array", "items": {"type": "string"}},
        # CORP+PA evidence (optional — addendum §5.4). Cards render these
        # as supplementary chips/sparklines beside the verifier verdict.
        # Absence is normal: not every recipient is federally incorporated
        # (CORP), and recipients with FED commitments below the PA $100K
        # threshold are legitimately not in pa.transfer_payments.
        "corp_status_code": {"type": "integer"},
        "corp_status_label": {"type": "string"},
        "corp_status_date": {"type": "string"},
        "corp_dissolution_date": {"type": "string"},
        "pa_last_year": {"type": "integer"},
        "pa_total_paid_cad": {"type": "integer"},
        # Optional: owner_org_title of the most recent FED agreement.
        # Rendered as the dept column in the dashboard table view.
        "last_dept": {"type": "string"},
    },
    "required": [
        "entity_name",
        "bn",
        "total_funding_cad",
        "last_known_year",
        "govt_dependency_pct",
        "evidence_summary",
        "verifier_status",
        "verifier_notes",
        "sql_trail",
    ],
}


@tool(
    "publish_finding",
    (
        "Push a candidate or verdict to the briefing panel. Call once per "
        "candidate with verifier_status='pending', then again with 'verified', "
        "'refuted', or 'challenged' as the investigation progresses. Use the "
        "same `bn` value across calls for the same entity so the card updates "
        "in place rather than duplicating. Optional CORP/PA evidence fields "
        "(corp_status_code/label/date, corp_dissolution_date, pa_last_year, "
        "pa_total_paid_cad) attach registry + audited-payments evidence to "
        "the card; pass them when Step A's pre-enrich returned matching rows, "
        "omit them otherwise."
    ),
    _PUBLISH_FINDING_SCHEMA,
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


# --------------------------------------------------------------------------
# publish_universe
# --------------------------------------------------------------------------

_PUBLISH_UNIVERSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "n_universe_pre_gate": {"type": "integer"},
        "n_after_foundation_filter": {"type": "integer"},
        "n_after_live_agreement_filter": {"type": "integer"},
        "n_after_non_charity_filter": {"type": "integer"},
        "n_final_candidates": {"type": "integer"},
        "narrative": {"type": "string"},
        "sql_trail": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "n_universe_pre_gate",
        "n_after_foundation_filter",
        "n_after_live_agreement_filter",
        "n_after_non_charity_filter",
        "n_final_candidates",
        "narrative",
        "sql_trail",
    ],
}


@tool(
    "publish_universe",
    (
        "Call EXACTLY ONCE at the start of an investigation, after Step A "
        "runs. Reports the search-space size and gate-drop counts so the "
        "audience can audit the methodology end-to-end, not just the "
        "survivors. Every count must come from a SQL query in this session."
    ),
    _PUBLISH_UNIVERSE_SCHEMA,
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


# --------------------------------------------------------------------------
# publish_dossier
# --------------------------------------------------------------------------

_PUBLISH_DOSSIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bn": {"type": "string"},
        "headline": {"type": "string"},
        "funding_events": {"type": "array"},
        "dependence_history": {"type": "array"},
        "overhead_snapshot": {"type": "object"},
        "death_event_text": {"type": "string"},
        "sql_trail": {"type": "array", "items": {"type": "string"}},
        # CORP+PA dossier sub-views (optional — addendum §5.3 / H4a / H4b).
        # corp_timeline: rows from corp.corp_status_history UNION
        # corp.corp_name_history for the corporation_id matched in Step A.
        # pa_payments: rows from pa.transfer_payments filtered to
        # recipient-detail (recipient_name_location IS NOT NULL) for the
        # recipient_name_norm match. Both default to [] when no enriched
        # data was attached at Step A time.
        "corp_timeline": {"type": "array"},
        "pa_payments": {"type": "array"},
    },
    "required": [
        "bn",
        "headline",
        "funding_events",
        "dependence_history",
        "overhead_snapshot",
        "death_event_text",
        "sql_trail",
    ],
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
        "line A2)' or 'Stopped filing T3010 after FY2021'. Optional "
        "corp_timeline: list of {kind, label, event_date, is_current} "
        "from corp_status_history + corp_name_history. Optional "
        "pa_payments: list of {fiscal_year_end, department_name, "
        "paid_cad} from pa.transfer_payments recipient-detail rows."
    ),
    _PUBLISH_DOSSIER_SCHEMA,
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
    version="0.3.0",
    tools=[publish_finding, publish_universe, publish_dossier],
)
