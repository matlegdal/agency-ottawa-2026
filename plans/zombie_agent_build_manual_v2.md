# Zombie Recipients Agent — Build Manual v2

> **Changes from v1**: integrated reviewer feedback validated against BIRD-INTERACT (ICLR 2026 Oral), CHESS (ICML 2025), MAGIC (AAAI 2025). Five material changes, listed in §0.1 below.

A practical hour-by-hour guide to shipping a hackathon-winning agentic solution for Challenge 1 (Zombie Recipients) using the Claude Agent SDK. Optimized for the 4-criterion rubric (Impact, Agent Autonomy, Innovation, Presentation × 5 pts each) and the "Working Demo" expectation that judges watch the thing run.

---

## 0. What you are building, in one paragraph

A web page with three panels: a chat input on the left, an agent activity log in the middle, a briefing panel on the right. A judge types a question like *"Find federal recipients that received over $1M and disappeared within a year"*. They watch the activity log fill with labelled SQL steps as the orchestrator agent investigates. They watch a verifier subagent paranoidly cross-check the findings, and — when the verifier challenges a candidate — the orchestrator runs follow-up queries to defend or revise. They see 3–5 named entities with dollar figures and citations populate the briefing panel, with at least one card showing the cycle of *pending → challenged → revised → verified*. Total runtime ~75–120 seconds. The whole product is the agent loop plus the panels.

### 0.1 What changed from v1

1. **Added a bounded iterative-exploration loop** between the orchestrator and the verifier (the BIRD-INTERACT pattern). After the verifier returns a verdict, the orchestrator gets up to 3 follow-up queries to defend or revise per candidate. This is the single biggest capability gain.
2. **Reduced hooks from 4 to 3**. UserPromptSubmit context injection is now baked into the system prompt; the date and challenge focus are static for the demo and don't need a hook.
3. **Added an SQL-error self-correction step inside the PostToolUse hook**. If `execute_sql` returns an error, the hook injects an additional system message guiding the orchestrator to retry with the error in context — distinct from the verifier, which validates findings, not query syntax.
4. **Added a warm-path cache** for Step A (top federal recipients ≥ $1M). Run the night before; fall back to the cached JSON if the live Render DB takes >10s.
5. **Trimmed system-prompt / skill redundancy**. Methodology lives in skills; only enforcement rules live in the system prompt. ~120 tokens saved.

---

## 1. Stack

- **Python 3.11+** — the Claude Agent SDK is Python or TS; pick Python because the data ecosystem is friendlier.
- **`claude-agent-sdk`** (pip) — the Anthropic Agent SDK, formerly Claude Code SDK. Provides `query()`, `ClaudeSDKClient`, `ClaudeAgentOptions`, `AgentDefinition`, `HookMatcher`, `@tool`, `create_sdk_mcp_server`.
- **Postgres MCP Pro** (`crystaldba/postgres-mcp`) — Docker container, restricted mode (read-only). Five tools: `execute_sql`, `explain_query`, `list_schemas`, `list_objects`, `get_object_details`.
- **FastAPI + Uvicorn** — for the websocket and one HTML page.
- **Static HTML page with vanilla JS + websocket client.** No React, no build step, no router.
- **Anthropic API key** (`ANTHROPIC_API_KEY`) for both the orchestrator and the verifier subagent.

---

## 2. Repository layout

```
zombie-agent/
├── .env                          # ANTHROPIC_API_KEY, READONLY_DATABASE_URL
├── pyproject.toml                # pinned versions
├── server.py                     # FastAPI: serves index.html, /ws, /ask
├── agent.py                      # ClaudeSDKClient wiring + the run loop
├── hooks.py                      # 3 hook callbacks
├── ui_bridge.py                  # in-process MCP exposing publish_finding
├── verifier.py                   # AgentDefinition for the verifier subagent
├── system_prompt.py              # SYSTEM_PROMPT constant
├── warm_path.py                  # NEW: pre-cached Step A fallback
├── cache/
│   └── step_a_top_recipients.json  # NEW: pre-computed warm path
├── ui/
│   └── index.html                # 3-panel single page, websocket client
└── .claude/
    └── skills/
        ├── accountability-investigator/SKILL.md
        ├── data-quirks/SKILL.md
        └── zombie-detection/SKILL.md
```

Nine Python files, one HTML, three skills, one JSON cache. Under 1100 lines of code.

### 2.1 Architectural separation of concerns (clarification from reviewer feedback)

There are **two streams** going to the UI, and they use different mechanisms:

- **UI activity events** (step_start, step_complete, subagent_stop) — emitted directly from **hooks** to the websocket. Hooks fire deterministically on tool lifecycle; they don't go through any MCP.
- **Structured findings** (verified/refuted zombies with name, BN, $, evidence) — emitted from the **`publish_finding` custom tool** in the in-process MCP. The agent *chooses* to publish a finding by calling the tool; the tool's schema enforces the structure; the call is visible in the activity log.

This is an intentional split. Hooks → side-effecting telemetry. Custom tool → structured semantic outputs. Don't conflate them.

---

## 3. Hour-by-hour plan

### Day 1 — event start, 8 hours

- **H1 (setup):** `pip install claude-agent-sdk fastapi uvicorn`. Drop the four `.env.public` files into `CRA/`, `FED/`, `AB/`, `general/`. Run `npm run verify` in each. Copy `READONLY_DATABASE_URL` into your project's `.env`. Pull `crystaldba/postgres-mcp`.
- **H2 (smoke test):** 20-line `agent.py` using `query()` and Postgres MCP. Confirm it lists schemas. If this works, the spine is right.
- **H3 (system prompt + 1 skill):** Write `system_prompt.py` (§10) and `accountability-investigator/SKILL.md` (§6.1). Switch to `ClaudeSDKClient`. Set `setting_sources=["project"]`, `cwd` to project root.
- **H4 (zombie skill + first end-to-end):** Write `zombie-detection/SKILL.md` (§6.3). Ask the real question. Capture the candidate list to disk for later cache priming.
- **H5–6 (UI + websocket):** `server.py` + `ui/index.html` (§11). Wire `agent.py` to push events. Confirm browser sees them.
- **H7 (custom tool + skill 3):** `ui_bridge.py` with `publish_finding` (§7). `data-quirks/SKILL.md` (§6.2). End-to-end run; cards appear in briefing.
- **H8 (verifier subagent):** `verifier.py` (§8). Add to `agents={}`. Update system prompt to delegate. End-to-end run; verifier appears as separate agent context.

End of Day 1: working agent loop, working UI, no hooks yet, no exploration loop yet.

### Day 2 — 8 hours

- **H9 (3 hooks):** `hooks.py` (§9). Wire into `ClaudeAgentOptions.hooks`. Run a query; activity panel lights up step by step.
- **H10 (iterative-exploration loop):** Modify the system prompt's step 7 to give the orchestrator a "rebuttal turn" after the verifier returns. Allow up to 3 additional `execute_sql` calls per challenged candidate before final publication. (Implementation in §10.) Test that a contested candidate triggers follow-up queries.
- **H11–12 (find your three best zombies):** Run against the production DB. Pick the THREE most viscerally compelling — high $, clean disappearance, government-dependent, in different sectors. Verify by hand against `charitydata.ca` and provincial corporate registries. *This is the most important block of the build.*
- **H12.5 (warm path cache):** Run `python warm_path.py --refresh` to save `cache/step_a_top_recipients.json`. The agent's fallback path now has data even if Render is slow.
- **H13 (UI polish):** Activity panel readable to a non-technical viewer. Briefing cards: entity name big, BN small, $ as headline, verifier verdict as colored pill (pending=amber, challenged=blue, verified=green, refuted=gray). One animation showing pending → challenged → verified for the contested case. ~150 lines of CSS.
- **H14 (rehearsal):** End-to-end 5 times. Time it. Pin question phrasing. Add a "Try this question" suggestion bar with 2–3 pre-vetted prompts.
- **H15 (slides):** 4 slides, mapped 1:1 to "What Judges Need to See". (1) Problem. (2) Insight (the named finding with $). (3) How You Built It (architecture diagram). (4) Live Demo. Add a discreet footnote on slide 3 citing CHESS, MAGIC, BIRD-INTERACT.
- **H16 (rehearse the pitch):** Out loud, stopwatch. Aim 4:00.

---

## 4. Setup checklist

```bash
pip install "claude-agent-sdk>=0.1" fastapi "uvicorn[standard]" python-dotenv asyncpg
docker pull crystaldba/postgres-mcp
python -c "from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions; print('ok')"
docker run --rm crystaldba/postgres-mcp --help
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

On event day, add `READONLY_DATABASE_URL=postgresql://...@<host>.render.com:5432/...?sslmode=require` from `FED/.env.public`.

---

## 5. The orchestrator (`agent.py`)

```python
import asyncio
import os
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, HookMatcher
)
from system_prompt import SYSTEM_PROMPT
from ui_bridge import ui_bridge_mcp, set_ws_sender as set_bridge_ws
from verifier import verifier_agent
from hooks import (
    safe_sql_hook, post_sql_hook, subagent_stop_hook,
    set_ws_sender as set_hooks_ws,
)

PROJECT_ROOT = Path(__file__).parent

postgres_mcp = {
    "type": "stdio",
    "command": "docker",
    "args": [
        "run", "-i", "--rm",
        "-e", "DATABASE_URI",
        "crystaldba/postgres-mcp",
        "--access-mode=restricted",
        "--transport=stdio",
    ],
    "env": {"DATABASE_URI": os.environ["READONLY_DATABASE_URL"]},
}

OPTIONS = ClaudeAgentOptions(
    cwd=str(PROJECT_ROOT),
    setting_sources=["project"],
    model="claude-sonnet-4-6",
    system_prompt=SYSTEM_PROMPT,
    allowed_tools=[
        "Skill", "Agent",
        "mcp__postgres__execute_sql",
        "mcp__postgres__explain_query",
        "mcp__postgres__list_schemas",
        "mcp__postgres__list_objects",
        "mcp__postgres__get_object_details",
        "mcp__ui_bridge__publish_finding",
    ],
    mcp_servers={
        "postgres": postgres_mcp,
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
        "PostToolUse": [
            HookMatcher(
                matcher="mcp__postgres__execute_sql",
                hooks=[post_sql_hook],
            )
        ],
        "SubagentStop": [HookMatcher(hooks=[subagent_stop_hook])],
    },
    permission_mode="default",
    max_turns=60,           # was 40 — increased for the iterative-exploration loop
    max_budget_usd=8.0,     # was 5.0 — same reason
)


async def run_question(question: str, ws_send):
    set_hooks_ws(ws_send)
    set_bridge_ws(ws_send)

    async with ClaudeSDKClient(options=OPTIONS) as client:
        await ws_send({"type": "run_start", "question": question})
        await client.query(question)
        async for msg in client.receive_response():
            pass
        await ws_send({"type": "run_complete"})
```

---

## 6. The skills

### 6.1 `accountability-investigator/SKILL.md`

```markdown
---
name: accountability-investigator
description: Master playbook for investigating any Canadian government accountability question against the CRA + FED + AB Postgres database. Use this skill at the start of every question; load challenge-specific recipes (zombie-detection, loop-detection, etc.) on top.
---

# Investigation methodology

Every question follows the same shape: decompose, query broadly, narrow, resolve to canonical entity, publish candidates, verify, **iterate on challenges**, finalize.

## 1. Decompose
Restate the user's question as a list of 3–7 SQL questions in plain English. Do not write SQL yet.

## 2. Load data-quirks before any SQL
The `data-quirks` skill lists defects that will silently fool you. Always read it before writing your first query.

## 3. Run queries sequentially
Each query is visible to the user. Begin every `execute_sql` call with a short comment-style English label: `-- Step 3: count CRA filings in 2024 for the candidates above`. The hooks surface this label in the activity panel.

Always include LIMIT on exploratory queries unless aggregating.

## 4. Resolve to canonical entity
Once you have a candidate list, join through `general.vw_entity_funding` so you reason about one canonical org per entity, not a name string that might appear 10 different ways.

## 5. Publish candidates with verifier_status="pending"
For your top 3–5 candidates, call `publish_finding` with `verifier_status="pending"`. Briefing panel shows pending cards.

## 6. Delegate to the verifier
Use the `Agent` tool with name="verifier". Pass the candidate list (canonical names, BNs, primary claim). Wait for the per-candidate verdicts.

## 7. Handle challenges (iterative-exploration loop)
For each candidate the verifier marks **REFUTED or AMBIGUOUS**, you have a budget of up to 3 follow-up `execute_sql` queries to either:
- **Defend** the original claim by addressing the verifier's specific evidence (e.g., the verifier found a 2024 T3010 — but on inspection, that filing reports zero programs and zero employees, supporting the zombie claim).
- **Revise** the claim with the new evidence (e.g., the verifier found a 2025 AB grant — the entity isn't a zombie after all).
- **Concede** if the evidence is overwhelming.

Use `publish_finding` with `verifier_status="challenged"` while you investigate, then `verifier_status="verified"` or `"refuted"` with the final verdict and the additional evidence.

The cycle pending → challenged → verified/refuted is the demonstration of investigative reasoning the rubric rewards.

## 8. Final user response
Three to five sentences summarizing what was found and pointing the user to the briefing panel. Do not restate the dossier in chat.

# Hard constraints (also enforced by hooks)
- The database is read-only; the PreToolUse hook blocks DROP/UPDATE/DELETE/INSERT/ALTER/TRUNCATE/CREATE.
- `LIMIT` is auto-injected on exploratory queries that lack it.
```

### 6.2 `data-quirks/SKILL.md`

(Unchanged from v1 — see the v1 manual for full text. The methodology rules previously duplicated in the system prompt now live exclusively here.)

### 6.3 `zombie-detection/SKILL.md`

(Unchanged from v1, except step "G" is renamed to "Handle challenges" and refers back to the master skill's iterative-exploration loop. See v1 for full text.)

---

## 7. The custom in-process tool (`ui_bridge.py`)

(Unchanged from v1, except the `verifier_status` field now also accepts `"challenged"`.)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

_ws_send = None

def set_ws_sender(send_fn):
    global _ws_send
    _ws_send = send_fn

async def _push(payload):
    if _ws_send is not None:
        await _ws_send(payload)


@tool(
    "publish_finding",
    "Push a zombie finding to the briefing panel. Call once per candidate with status 'pending', then 'verified' / 'refuted' / 'challenged' as the investigation progresses.",
    {
        "entity_name": str,
        "bn": str,
        "total_funding_cad": float,
        "last_known_year": int,
        "govt_dependency_pct": float,
        "evidence_summary": str,
        "verifier_status": str,   # "pending" | "challenged" | "verified" | "refuted"
        "verifier_notes": str,
        "sql_trail": list,
    },
)
async def publish_finding(args):
    await _push({"type": "finding", **args})
    return {
        "content": [{
            "type": "text",
            "text": f"Published finding: {args['entity_name']} (status={args['verifier_status']})",
        }]
    }


ui_bridge_mcp = create_sdk_mcp_server(
    name="ui_bridge",
    version="0.1.0",
    tools=[publish_finding],
)
```

---

## 8. The verifier subagent (`verifier.py`)

The verifier prompt now anticipates the iterative-exploration loop — it returns one of VERIFIED / REFUTED / **AMBIGUOUS** so the orchestrator knows when to keep digging vs. accept.

```python
from claude_agent_sdk import AgentDefinition

verifier_agent = AgentDefinition(
    description=(
        "Skeptically verifies candidate zombie findings by attempting to disprove them. "
        "Returns one of VERIFIED, REFUTED, or AMBIGUOUS for each candidate with citations. "
        "AMBIGUOUS triggers the orchestrator's iterative-exploration loop."
    ),
    prompt=(
        "You are a paranoid auditor. The orchestrator has handed you 3-5 candidate "
        "'zombie' entities. Your job is to DISPROVE each claim by finding any evidence "
        "the entity is still active.\n\n"
        "For each candidate, run focused SQL queries via mcp__postgres__execute_sql to look for:\n"
        "  1. Any cra.cra_identification row for fiscal_year = 2024 (use LEFT(bn,9)).\n"
        "  2. Any fed.grants_contributions row with agreement_start_date >= '2024-01-01' "
        "for the same BN root or, if no BN, the resolved entity_id via "
        "general.entity_source_links.\n"
        "  3. Any ab.ab_grants payment in display_fiscal_year IN ('2024 - 2025', "
        "'2025 - 2026') for the resolved entity_id.\n"
        "  4. Any ab.ab_non_profit row with status indicating active for that legal name "
        "(use general.norm_name() to compare).\n\n"
        "Apply the data-quirks skill before querying. Do not aggregate "
        "fed.grants_contributions.agreement_value directly.\n\n"
        "For each candidate, return a one-paragraph verdict:\n"
        "  VERIFIED — no evidence of life. State which queries returned zero.\n"
        "  REFUTED — strong evidence of continued operation. Cite the row(s).\n"
        "  AMBIGUOUS — partial or contradictory evidence (e.g., a 2024 T3010 exists but "
        "    reports zero programs; a 2025 AB grant exists but is a $200 reversal). "
        "    Explain what made it ambiguous so the orchestrator knows what to probe.\n\n"
        "Be terse. The orchestrator will decide what to do with AMBIGUOUS verdicts."
    ),
    tools=["mcp__postgres__execute_sql"],
    model="sonnet",
    skills=["data-quirks"],
)
```

---

## 9. The hooks (`hooks.py`)

Three hooks. UserPromptSubmit context injection has been moved into the system prompt. SQL-error self-correction is now folded into `post_sql_hook`.

```python
import re
from claude_agent_sdk import HookContext

_ws_send = None

def set_ws_sender(send_fn):
    global _ws_send
    _ws_send = send_fn

async def _emit(payload):
    if _ws_send is not None:
        await _ws_send(payload)


_DESTRUCTIVE = re.compile(
    r"\b(DROP|TRUNCATE|UPDATE|DELETE|INSERT|ALTER|GRANT|REVOKE|CREATE|VACUUM)\b",
    re.IGNORECASE,
)

def _needs_limit(sql: str) -> bool:
    s = sql.lower()
    return ("limit" not in s) and not any(
        w in s for w in ("count(", "sum(", "avg(", "max(", "min(", "group by")
    )


async def safe_sql_hook(input_data, tool_use_id, context: HookContext):
    """PreToolUse: deny destructive SQL, inject LIMIT, emit step_start."""
    sql = input_data["tool_input"].get("sql", "")

    if _DESTRUCTIVE.search(sql):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Read-only database. Destructive SQL is blocked at the hook layer."
                ),
            }
        }

    updated_input = dict(input_data["tool_input"])
    if _needs_limit(sql):
        updated_input["sql"] = sql.rstrip(";").rstrip() + "\nLIMIT 1000"

    label = sql.lstrip().splitlines()[0] if sql else "(empty SQL)"
    await _emit({
        "type": "step_start",
        "id": tool_use_id,
        "label": label,
        "sql": updated_input["sql"],
    })

    if updated_input != input_data["tool_input"]:
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": updated_input,
        }}
    return {}


async def post_sql_hook(input_data, tool_use_id, context: HookContext):
    """PostToolUse: stream result preview AND inject self-correction context on errors."""
    response = input_data.get("tool_response") or {}
    text = ""
    if isinstance(response, dict):
        for block in response.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                break

    is_error = (
        "ERROR:" in text
        or "syntax error" in text.lower()
        or "does not exist" in text.lower()
        or "permission denied" in text.lower()
    )

    rows_estimate = 0 if is_error else text.count("\n")
    await _emit({
        "type": "step_complete",
        "id": tool_use_id,
        "duration_ms": input_data.get("duration_ms"),
        "rows_estimate": rows_estimate,
        "preview": text[:600],
        "error": is_error,
    })

    # SQL-error self-correction: inject context guiding the orchestrator to retry.
    if is_error:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "The previous SQL returned an error. Read the error message, identify "
                    "the cause (typo, missing column, schema prefix, type mismatch), and "
                    "issue a corrected query. Do NOT retry the exact same SQL. If the "
                    "column or table does not exist, use list_objects or get_object_details "
                    "to verify the schema before retrying."
                ),
            }
        }

    return {}


async def subagent_stop_hook(input_data, tool_use_id, context: HookContext):
    """SubagentStop: announce verifier completion to the UI."""
    agent_name = input_data.get("agent_type") or "subagent"
    await _emit({"type": "subagent_stop", "agent": agent_name})
    return {}
```

---

## 10. The system prompt (`system_prompt.py`)

Trimmed of methodology that lives in skills. Date and challenge focus baked in. Rebuttal-turn instruction added.

```python
SYSTEM_PROMPT = """You are an investigative analyst for Canadian government accountability.
Today is 2026-04-29. The active challenge is Zombie Recipients (Challenge #1).
The database is the hackathon's curated CRA + FED + AB Postgres, accessed via the
postgres MCP server in restricted (read-only) mode.

# How to investigate

Always begin by invoking the `accountability-investigator` skill — it owns the
methodology. Always invoke `data-quirks` before your first SQL query — it owns the
list of defects that will silently fool you. For zombie-style questions, also
invoke `zombie-detection`.

# How to delegate

After your initial discovery, call publish_finding for each top candidate with
verifier_status="pending", then use the Agent tool with name="verifier" to delegate
verification. The verifier returns one of VERIFIED, REFUTED, or AMBIGUOUS per
candidate.

# How to handle challenges (iterative-exploration loop)

For any candidate the verifier marks AMBIGUOUS or REFUTED, you have a budget of up
to 3 follow-up SQL queries per candidate to either:
- Defend by examining the verifier's evidence more closely (e.g., a 2024 T3010 may
  exist but report zero programs and zero employees, supporting the zombie claim).
- Revise with the new evidence and lower the candidate's confidence or drop it.
- Concede when the evidence is decisive.

Update each finding via publish_finding as you go: pending → challenged → verified
or refuted. The challenged → verified transition is the demonstration of
investigative reasoning, not a failure mode.

# Hard rules — enforced by hooks but you should also know them

- Never invent a number. Every numeric claim must trace to a SQL query in this session.
- Never run DROP, UPDATE, DELETE, INSERT, ALTER, TRUNCATE, CREATE, GRANT, REVOKE.
  The PreToolUse hook will deny these; do not waste a turn trying.
- LIMIT is auto-injected on exploratory queries; do not be surprised by it.
- If a number looks too large or too small, suspect a data quirk before fraud.

# Output contract

Every finding pushed via publish_finding must include a non-empty sql_trail
listing the query labels that produced it. Final user-facing message: 3-5 sentences
summarizing the dossier and pointing to the briefing panel. Do not restate the
dossier in chat.
"""
```

The methodology details (vw_agreement_current, t3010_impossibilities, LEFT(bn,9), display_fiscal_year, etc.) now live exclusively in the `data-quirks` skill, which is loaded on demand. The orchestrator must invoke that skill before its first SQL query — this is enforced by the methodology in `accountability-investigator`, which the system prompt instructs the agent to load first.

---

## 11. The UI

(Unchanged from v1, except the `.finding` CSS now includes a `.challenged` state — light blue background, indicating the verifier raised concerns and the orchestrator is following up.)

```css
.finding.challenged { background: #e7f0fa; border-color: #5a8bc7; }
```

The card animates pending (amber) → challenged (blue) → verified (green) or refuted (gray). Make sure at least one of your three demo zombies takes the challenged path — that's the moneyshot.

---

## 12. The warm path cache (`warm_path.py`) — NEW

Run this the night before the event to pre-compute Step A. The agent's `accountability-investigator` skill is updated to fall back to the cache if the live DB query for top recipients takes >10 seconds.

```python
"""Pre-compute Step A so the demo survives a sluggish Render DB on event day.
Run: python warm_path.py --refresh
"""
import asyncio
import json
import os
import sys
from pathlib import Path
import asyncpg

CACHE_PATH = Path(__file__).parent / "cache" / "step_a_top_recipients.json"

STEP_A_SQL = """
SELECT
  COALESCE(NULLIF(recipient_business_number, ''), recipient_legal_name) AS key,
  recipient_legal_name,
  recipient_business_number,
  SUM(agreement_value) AS total_committed_cad,
  MIN(agreement_start_date) AS first_grant,
  MAX(agreement_end_date) AS last_grant
FROM fed.vw_agreement_current
WHERE agreement_end_date BETWEEN '2018-01-01' AND '2022-12-31'
GROUP BY 1, 2, 3
HAVING SUM(agreement_value) >= 500000
ORDER BY total_committed_cad DESC
LIMIT 200;
"""

async def refresh():
    conn = await asyncpg.connect(os.environ["READONLY_DATABASE_URL"])
    rows = await conn.fetch(STEP_A_SQL)
    payload = {
        "computed_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "sql": STEP_A_SQL.strip(),
        "rows": [dict(r) for r in rows],
    }
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, default=str, indent=2))
    print(f"Wrote {len(payload['rows'])} rows to {CACHE_PATH}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(refresh())
```

The agent reads this only as a fallback. Wire it as a small custom MCP tool `read_warm_path()` if you want — or keep it simpler and have the skill instruct the orchestrator to read the file via a Bash/Read tool if `execute_sql` is slow. Simplest path: don't expose to the agent, just have `agent.py` race the live query against the cached load and surface whichever wins to the next step. ~20 lines.

---

## 13. Demo rehearsal checklist (updated)

- [ ] `npm run verify` succeeds in CRA, FED, AB, general.
- [ ] `docker run -i --rm -e DATABASE_URI="$READONLY_DATABASE_URL" crystaldba/postgres-mcp --access-mode=restricted --transport=stdio` doesn't error.
- [ ] One end-to-end run from cold start completes in 75–120 seconds.
- [ ] Activity panel shows ≥ 5 labelled steps with row counts and durations.
- [ ] Briefing panel shows ≥ 3 cards transitioning pending → verified.
- [ ] **At least one card transitions pending → challenged → verified, demonstrating the iterative-exploration loop.**
- [ ] Each verified card has a real entity name a judge could Google.
- [ ] Five repeat runs of the same question produce stable top-3 names.
- [ ] Destructive-SQL block tested: ask "drop the cra schema" — refused.
- [ ] **SQL-error retry tested**: temporarily mistype a column name; agent recovers within one turn via the post_sql_hook.
- [ ] **Warm path tested**: kill the network briefly during Step A; the agent falls back to `cache/step_a_top_recipients.json` and the demo continues.
- [ ] Backup screen recording exists.
- [ ] Pitch under 4:00 with 60s buffer.

---

## 14. The pitch (4 slides + script outline)

### Slide 1 — Problem
Show one number from the data. *Example*: "$X billion in federal grants flowed to entities that have no T3010 filings, no Alberta corporate registry presence, and no further grants since." Plain English. No methodology yet.

### Slide 2 — Insight
Name your top finding. *"<Entity> received $4.2M from <departments> 2019–2021. No filings since 2022. Government revenue dependency 87% in their last filing year."* This is the lean-forward moment.

### Slide 3 — How You Built It (this is where SOTA citations earn points)
The architecture diagram. One footnote: *"Adversarial verifier subagent (CHESS, ICML 2025), persistent failure-catalogue skill (MAGIC, AAAI 2025), iterative-exploration loop (BIRD-INTERACT, ICLR 2026 Oral)."* You don't need to read the footnote out loud — judges will see it. The point is to show your design isn't just clever; it's aligned with the published frontier.

### Slide 4 — Live Demo
Run it. Pin the question. Don't narrate every step — let the activity panel speak. *Do* call out, when it happens: "the verifier just challenged this candidate; watch the orchestrator follow up." That's the BIRD-INTERACT moment in plain English.

### Pitch script (~3:30)

> *Investigation phase (50s):* "Public funding rises every year, but the question of whether the public got anything for its money is rarely asked at the entity level. Our agent answers it. [demo starts] You're seeing it decompose the question into SQL, run six queries against the live federal and provincial databases, and resolve every candidate to a canonical entity using the hackathon's golden-record table. Notice the activity log — every claim it makes traces back to a query you can see and re-run."
>
> *Verification phase (40s):* "We've found five candidates. Now watch — a separate verifier agent is going to try to disprove each one. [verifier runs] Three came back verified, one refuted, one ambiguous. [orchestrator's rebuttal turn fires] On the ambiguous one, the orchestrator is following up — it's checking whether the verifier's evidence is real or a corner case. It just found that the 2024 T3010 the verifier flagged reports zero programs and zero employees. Verdict revised to verified."
>
> *Why this design (40s):* "We're not running a chat over a database. We're running a structured investigation. The agent's job is bounded, every output is auditable, every claim has a SQL trail. The architecture is informed by recent SQL-agent research — adversarial verifiers, persistent defects catalogues, multi-turn investigative loops. We didn't invent these patterns; we composed them on a Canadian government dataset where they pay off."
>
> *Briefing summary (40s):* "The briefing panel on the right is what a Deputy Minister would actually see. Three named entities, $X million each, last known filing year, dependency percentage, verifier verdict, evidence summary. Five minutes of agent time turns into a one-page briefing a Minister can act on."
>
> *Close (20s):* "Same architecture works on funding loops, sole-source amendment creep, vendor concentration. We picked zombies because the finding is visceral. The agent generalizes."

---

## 15. Risks and mitigations (updated)

**Render DB latency.** Mitigation: warm path cache (§12). Rehearse the fallback path.

**The agent goes off the rails on a complex question.** `max_turns=60` and `max_budget_usd=8.0` are circuit breakers. The hooks limit blast radius. If a run goes >180s, abort manually.

**Verifier returns AMBIGUOUS or REFUTED on all candidates.** Now a feature, not a bug. The iterative-exploration loop will defend or revise. Lean into it in the pitch.

**Iterative-exploration loop runs away.** Bound the rebuttal budget at 3 follow-up queries per candidate. Enforce in the system prompt; if needed, add a hook counter.

**A "zombie" turns out to be a structural special case.** Designation A foundations can legitimately have low operating revenue. Filter out designation A from candidates in the zombie-detection skill, and mention this preemptively in the pitch.

**Skills don't load.** Most common cause: `setting_sources=["project"]` missing, wrong `cwd`, or `Skill` not in `allowed_tools`. Test with `ls .claude/skills/*/SKILL.md`.

**SQL error cascades.** The new `post_sql_hook` injects retry guidance. Test by deliberately mistyping a column name in a test run.

---

## 16. If you have time — extensions in priority order

1. **Add `loop-detection` skill** for Challenge 3.
2. **Add `amendment-creep` skill** for Challenge 4.
3. **OpenSanctions cross-check** as a third verifier pass on the verified zombies (Challenge 10 flavor).
4. **Multiple verifier subagents in parallel** — one per candidate, fan-out via `Agent` tool calls.

Do not attempt these on Day 1.

---

## Closing

The discipline that wins this is: **everything you build serves the rubric, nothing you build is for show, every component cites a published pattern.** The reviewer's research and the SOTA citations matter — they convert "clever hackathon project" into "research-aligned production-shape." That's the difference between Top 6 and Top 1.
