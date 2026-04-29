# Zombie Recipients — The Winning Pitch
### AI For Accountability Hackathon · Ottawa · April 29, 2026
### Challenge #1 — *"Did the public get anything for its money, or did it fund a disappearing act?"*

> **One-line thesis:** We built a self-running, multi-agent investigator that fuses **five Canadian government open-data sources** behind a deterministic SQL gate, an **adversarial paranoid verifier**, and a **registry + audited-cash double-check** — then publishes Minister-grade *audit leads* (never accusations) where every dollar, every percentage, every date traces back to a labelled SQL query you can re-run live, on stage, from the database.

---

## 0. Executive Summary — Why We Win

The judges score on four dimensions, each 1–5, total 20. Below is the at-a-glance map of *what we built that hits each dimension at a 5*, with the deeper proof in the sections that follow.

| Rubric | What we deliver | Beyond-baseline differentiator |
|---|---|---|
| **Impact & Significance** (1–5) | A $1M-hard-gated, BN-anchored, F-3-safe sweep across **CRA T3010 (8.76M rows) + FED Grants & Contributions (1.275M rows) + AB grants/registry (2.61M rows) + general entity-resolution (10.5M rows) + CORP federal corporate registry + PA audited Public Accounts** producing *named entities* with *quantified federal exposure*, *CHL-mandated 70–80% dependency flags*, and a *templated death-event banner* that an auditor can act on tomorrow morning. | We don't just find candidates — we **disclose the entire methodology funnel** (how many recipients survived each gate) and we route **structurally-disqualified-but-still-anomalous** entities into a *Ghost Capacity sidebar* (Challenge 2) instead of letting them die. Nothing falls through the cracks. |
| **Agent Autonomy** (1–5) | Two cooperating Claude agents (Orchestrator: Opus 4.7 / Verifier: Opus) with **3 auto-loaded skills**, **4 lifecycle hooks**, **a deterministic 14-step precedence chain**, and an **iterative-exploration loop** (≤3 follow-up SQL queries per AMBIGUOUS verdict). The dashboard literally **auto-starts the investigation on page load** and runs end-to-end with zero human input. | The verifier is **adversarial by design** — its job is to *disprove* every claim. "REFUTED is final" — the orchestrator cannot bully the verifier. Same DB state → same candidate list, every run, deterministically. |
| **Innovation & Originality** (1–5) | (a) **Templated deterministic headlines** so a 6th run of the same DB produces byte-identical Minister briefings — no LLM hallucination of numbers, *ever*; (b) **Universe panel** (`publish_universe`) showing every gate's drop count — explainability *of the methodology itself*, not just the survivors; (c) **CORP + PA cross-corroboration** — federal corporate registry status + audited cash flow as independent kill-switches; (d) **BN-reuse temporal gate** that catches Kinectrics-shape false positives no naive query would; (e) **Audit-leads framing** — language scrubbed of "fraud / stole / criminal", legally safe for ministers. | We treat the data quirks themselves as a feature: the project ships a `data-quirks` skill cataloguing the **F-3 cumulative-amendment triple-count** ($921B vs the correct $816B), the **F-1 ref_number-collision-across-recipients** (41,046 colliding numbers), and the **T3010 6-month filing-window** rule — all neutralized by canonical views (`fed.vw_agreement_current`) and `NOT EXISTS` filters baked into every query the agent writes. |
| **Presentation & Clarity** (1–5) | A **3-panel live UI** (Investigation / Activity / Briefing) that streams every SQL query, every skill load, every subagent spawn, every finding card, every dossier sparkline over a single websocket — plus a **standalone live operator dashboard** (`/dashboard`), a **printable HTML audit report** (`/report`), and a **deterministic format-string headline** that any non-technical reader can act on: *"$11.7M in federal commitments 2018–2022 to a recipient that self-dissolved on 2023-03-31; on its most recent clean filing, government funding was 87.4% of total revenue."* | Every number on screen is **clickable, traceable, and SQL-derived**. The bankruptcy-coverage disclosure appears under every card so we never overclaim. The verifier's *challenged → verified* transition is rendered as a **purple pulse animation** to *show* the investigative reasoning, not just describe it. |

**Score we are targeting: 20 / 20.** Every paragraph below is the receipts.

---

## 1. The Problem We Chose (Demo Slide 1)

> *"Which companies and nonprofits received large amounts of public funding and then ceased operations shortly after? Identify entities that went bankrupt, dissolved, or stopped filing within 12 months of receiving funding. Flag entities where public funding makes up more than 70-80% of total revenue, meaning they likely could not survive without it. The question is simple: did the public get anything for its money, or did it fund a disappearing act?"*

We took the literal CHL text and **decomposed every clause to a column or filter** in our `zombie-detection` skill so the dossier can be checked against the question verbatim. This is recorded in the skill itself as the **CHL clause map** (see §3 below).

**Concrete operationalization:**
1. *"large amounts"* → cumulative ≥ **$1,000,000** in `fed.vw_agreement_current` (HARD GATE).
2. *"companies and nonprofits"* → `LEFT JOIN` to CRA so non-charity companies pass via the `no_post_grant_activity` branch.
3. *"ceased operations shortly after"* → 5 distinct death signals (CASE expression): `t3010_self_dissolution`, `dissolved_and_stopped_filing`, `dissolved`, `stopped_filing`, `no_post_grant_activity`.
4. *"bankrupt"* → **explicitly disclosed as not directly observable** in this dataset. We surface this gap in the dossier instead of silently substituting.
5. *"within 12 months of receiving funding"* → SORTABLE `months_grant_to_death_signal` column on every candidate.
6. *"70–80% of total revenue"* → `cra.govt_funding_by_charity.govt_share_of_rev >= 70` on the most-recent clean filing, with `t3010_impossibilities` and `PLAUS_MAGNITUDE_OUTLIER` filters applied (a $5B unit-error year would otherwise flip the flag).
7. *"Did the public get anything for its money?"* → `cra.overhead_by_charity.strict_overhead_pct` rendered on every dossier (admin + fundraising ÷ programs).

This is not a vibes interpretation of the question. **Every clause maps to a column.**

---

## 2. The Insight We Found (Demo Slide 2)

The agent runs end-to-end against the live hackathon Postgres. On every run it produces, deterministically:

- **A universe panel** with five row counts: `n_universe_pre_gate`, `n_after_foundation_filter`, `n_after_live_agreement_filter`, `n_after_non_charity_filter`, `n_final_candidates`. The judges see *exactly* how many recipients each methodology gate dropped — not just the survivors.
- **A ranked candidate list** sorted by `total_committed_cad DESC` among VERIFIED entries.
- **Per-candidate templated headlines** of the form:
  *"$X.XM in federal commitments YYYY–YYYY to a recipient that self-dissolved on YYYY-MM-DD (T3010 line A2: charity wound up, dissolved, or terminated operations); on its most recent clean filing, government funding was XX.X% of total revenue."*
- **A dossier panel per VERIFIED candidate** with: status banner, full federal funding-events timeline, govt-share-of-revenue sparkline (with the 70% CHL threshold drawn as a dashed red line), overhead snapshot, CORP federal-registry timeline (status + name history), PA audited-cash sparkline (FY 2020 → 2025).
- **A briefing summary** stating in plain language: how many leads were independently verified, what cumulative federal funding they represent, and how many candidates were correctly excluded by the methodology.

**Quantification, concrete:** the system has shipped real verified outputs in development — e.g. **Acadia Centre** (taught us why we MUST anchor exposure totals to BN, not entity-resolution roll-ups), **Northwest Inter-Nation** ($101.79M aggregate vs ~$11.7M true current commitment — a 9x inflation we caught and prevented), **Kinectrics-shape BN-reuse** (a corp dissolved decades before the BN was reassigned to a successor — caught by our temporal gate, not by naive queries). These lessons are baked into the skill — the agent **cannot make these mistakes again**.

---

## 3. How We Built It (Demo Slide 3)

### 3.1 System architecture (one diagram, no apologies)

```
┌──────────────┐  websocket   ┌────────────────────────────────────────┐
│   Browser    │◀────────────▶│   FastAPI (uvicorn 8080)               │
│  3-panel UI  │              │   src/main.py + src/router.py          │
│  /dashboard  │              │   /report, /api/run, /api/stop, /ws    │
└──────────────┘              └────────────────────┬───────────────────┘
                                                    │ ClaudeSDKClient
                                                    ▼
                              ┌────────────────────────────────────────┐
                              │   Orchestrator — Claude Opus 4.7       │
                              │   src/agent.py + src/system_prompt.py  │
                              │   thinking=adaptive, effort=high       │
                              │   max_turns=80, bypassPermissions      │
                              │                                        │
                              │   Tools allowed:                       │
                              │     • Skill (auto-loads SKILL.md)      │
                              │     • Task / Agent (spawn subagent)    │
                              │     • mcp__postgres__execute_sql       │
                              │     • mcp__postgres__list_objects      │
                              │     • mcp__postgres__get_object_details│
                              │     • mcp__postgres__list_schemas      │
                              │     • mcp__postgres__explain_query     │
                              │     • mcp__ui_bridge__publish_finding  │
                              │     • mcp__ui_bridge__publish_universe │
                              │     • mcp__ui_bridge__publish_dossier  │
                              │                                        │
                              │   Hooks installed:                     │
                              │     • PreToolUse  → safe_sql_hook      │
                              │     • UserPromptSubmit → inject_ctx    │
                              │     • SubagentStop → announce          │
                              └────┬───────────────────┬──────────────┘
                                   │                   │
        ┌──────────────────────────┘                   └────────────────────────┐
        ▼                                                                       ▼
┌────────────────────────┐                                ┌────────────────────────────────┐
│ External stdio MCP     │                                │ In-process SDK MCP (UI bridge) │
│ crystaldba/postgres-   │                                │ src/mcp_servers/ui_bridge.py   │
│ mcp --access-mode=     │                                │   • publish_finding            │
│ restricted             │                                │   • publish_universe (1×)      │
│ (SQL parser refuses    │                                │   • publish_dossier (per BN)   │
│ destructive SQL)       │                                │ → emits ws events to browser   │
└──────────┬─────────────┘                                └────────────────────────────────┘
           ▼
┌────────────────────────────────────────────┐
│ Postgres (read-only role)                  │
│   schemas: cra, fed, ab, general,          │
│            corp, pa                        │
└────────────────────────────────────────────┘
                                   │
                                   │ Task tool
                                   ▼
                              ┌────────────────────────────────────────┐
                              │   Verifier subagent — Claude Opus      │
                              │   src/verifier.py (AgentDefinition)    │
                              │   Tools: ONLY mcp__postgres__execute_sql│
                              │   Cannot publish; cannot list schemas. │
                              │   Inherits parent mcp_servers config.  │
                              │                                        │
                              │   PARANOID AUDITOR PERSONA — its job   │
                              │   is to DISPROVE, not confirm.         │
                              └────────────────────────────────────────┘
```

### 3.2 The 14-step deterministic precedence chain (verifier)

The verifier doesn't "think" through each candidate freely. It runs a **strict ordered chain** — first match wins, stop checking. This eliminates verdict drift where two checks would otherwise both fire.

| Order | Check | Trigger | Outcome |
|---|---|---|---|
| 1 | CHECK 5 | Sub-$1M BN-anchored `vw_agreement_current` total | **REFUTED** |
| 2 | CHECK 0 | CRA designation = A (public foundation) or B (private foundation) | **REFUTED** |
| 3 | CHECK 9 | CORP status 1 (Active) AND `last_annual_return_year >= grant_end_year - 1` | **REFUTED** |
| 4 | CHECK 9b | CORP status 9 (Inactive – Amalgamated; chase the successor) | **REFUTED** |
| 5 | CHECK 1 | T3010 filing window still open (`fpe + 6 months > scrape date`) | **REFUTED** |
| 6 | CHECK 7 | Entity rebranded (`identification_name_history` shows recent name change) | **REFUTED** |
| 7 | CHECK 2b | FED `agreement_end_date >= 2024-01-01` AND `end >= start` (live agreement) | **REFUTED** |
| 8 | CHECK 3 | Any AB `ab_grants.amount > 0` in FY 2024-25 / 2025-26 | **REFUTED** |
| 9 | CHECK 10 | PA `recipient_totals.last_year >= current_year - 1` AND `total_paid > 0` | **REFUTED** |
| 10 | CHECK 11 | CORP status 11 (Dissolved) or 3 (Dissolution Pending) AND temporal gate satisfied | **VERIFIED** |
| 11 | CHECK 8 | `cra_financial_general.field_1570 = TRUE` (T3010 self-reported dissolution) | **VERIFIED** |
| 12 | CHECK 12 | PA empty across all loaded FYs AND `agreement_value >= $100K` AND `start_date <= today - 12mo` | **VERIFIED** |
| 13 | CHECK 6 | `govt_funding_by_charity.govt_share_of_rev < 70` on most-recent clean filing | **AMBIGUOUS** |
| 14 | (default) | Death signal fired AND nothing above triggered | **VERIFIED** |

**Why this chain wins:** the agent literally cannot "argue past" a refutation. CHECK 11 (registry-confirmed dissolution + temporal gate) is the strongest VERIFIED signal; CHECK 8 (T3010 self-dissolution) is decisive first-party evidence; CHECK 12 (PA empty + materially-large agreement) confirms cash never moved.

### 3.3 Skills — domain knowledge as auto-loaded markdown

Three skills live in `src/workspace/.claude/skills/` and auto-load when their description matches the question:

1. **`accountability-investigator`** — master playbook. *"Decompose, query broadly, narrow, resolve to canonical entity, verify, publish."* Hard rules: never invent a number, never destructive SQL, never accusation language, suspect a data quirk before fraud.
2. **`data-quirks`** — catalogue of every defect that will silently fool a naive query: F-3 cumulative-amendment double-counting, F-1 ref_number collisions across recipients, T3010 6-month filing window, AB `display_fiscal_year` literal `'2024 - 2025'` format, A-6 reversal rows, A-13 duplicate/perfect-reversal pairs, F-9 corrupt date pairs, C-1 impossibility violations, PLAUS_MAGNITUDE_OUTLIER, C-7 backfilled legal names, foundation A vs B distinction, BN root vs 15-char BN.
3. **`zombie-detection`** — the recipe. The literal CHL clause map; the deterministic Step A enumeration query; Step A1 universe-and-gate-counts; Step B verify-and-sort; Step C Alberta liveness; Step D entity resolution; **Step E (REQUIRED, not optional) govt-dependency**; Step F per-candidate `pending` publish; Step G verifier delegation + iterative-exploration; **Step H dossier publish** with H1 funding-events / H2 dependence-history / H3 overhead / H4a CORP timeline / H4b PA payments / H5 deterministic templated headline / H6 publish_dossier call.

### 3.4 Hooks — the four lifecycle gates

| Hook | Purpose | What it does |
|---|---|---|
| `safe_sql_hook` (PreToolUse) | Belt-and-suspender on the read-only DB | Regex-denies `DROP/TRUNCATE/UPDATE/DELETE/INSERT/ALTER/GRANT/REVOKE/VACUUM` and `CREATE TABLE/SCHEMA/DATABASE/ROLE/USER/EXTENSION/VIEW/MATERIALIZED/FUNCTION/TRIGGER/INDEX`. Auto-injects `LIMIT 1000` on non-aggregate exploratory queries. Marks `step_start` for duration timing. Streams the SQL + label to the activity panel. |
| `inject_context_hook` (UserPromptSubmit) | Reminders the agent should never forget | Prepends today's date, the active challenge, and the six biggest data-quirk reminders to every user prompt. |
| `subagent_stop_hook` (SubagentStop) | UI breadcrumb when verifier returns | Emits `subagent_stop` so the verifier badge stops pulsing and the activity log shows ✓. |
| (post-tool) | (handled in agent loop, not a hook) | The SDK's `tool_response` is unreliable for MCP tools, so we emit `step_complete` from the agent message loop where the real `ToolResultBlock` lands — with row counts parsed via `ast.literal_eval` and a regex fallback. This is a *bug we found in the SDK and worked around*, recorded in `src/agent.py:11-13`. |

### 3.5 The streaming pub-sub (`src/streaming.py`)

Every event — assistant text, tool call, step start, step complete, subagent stop, finding, universe, dossier, thinking block, run result — flows through one `emit()` function that fans out to:
1. The primary websocket (browser asking the question).
2. Any number of `/ws/live` broadcast subscribers (the operator dashboard).
3. The `RunStore` event hook (which builds state for the printable `/report` HTML).

This means the printable audit report, the live UI, and the operator dashboard are **always coherent** — there's no possibility of the briefing showing one number and the report showing another, because there is one source of truth.

### 3.6 The deterministic Step A query (the heart of the methodology)

This single query is the backbone. We run it **once per investigation, exactly as written, no LLM-authored variants**, and the output ordering is governed solely by `ORDER BY total_committed_cad DESC`. Same DB state → same candidate list, every run.

```sql
WITH exposure AS (
  SELECT LEFT(NULLIF(recipient_business_number,''), 9) AS bn_root,
         MIN(recipient_legal_name)  AS recipient_name,
         SUM(agreement_value)       AS total_committed_cad
  FROM fed.vw_agreement_current                    -- F-1 + F-3 safe view
  WHERE LEFT(NULLIF(recipient_business_number,''), 9) ~ '^[1-9][0-9]{8}$'
    AND agreement_start_date BETWEEN '2018-01-01' AND '2022-12-31'
  GROUP BY 1
  HAVING SUM(agreement_value) >= 1000000           -- $1M HARD GATE
), charity AS (...), charity_fpe AS (...),
   cra_self_dissolved AS (...), ab_dissolved AS (...)
SELECT e.*, c.last_fy, c.designation, ...,
       CASE
         WHEN s.bn_root IS NOT NULL                    THEN 't3010_self_dissolution'
         WHEN d.bn_root IS NOT NULL AND c.last_fy<=2022 THEN 'dissolved_and_stopped_filing'
         WHEN d.bn_root IS NOT NULL                    THEN 'dissolved'
         WHEN c.designation='C' AND c.last_fy<=2022    THEN 'stopped_filing'
         WHEN c.bn_root IS NULL                        THEN 'no_post_grant_activity'
       END AS death_signal,
       (months between latest grant end and dissolution event) AS months_grant_to_death_signal,
       cc.* AS corp_pre_enrich,                        -- DISTINCT ON BN-reuse-safe
       pt.* AS pa_pre_enrich
FROM exposure e
LEFT JOIN charity c ON ...
LEFT JOIN charity_fpe cf ON ...
LEFT JOIN cra_self_dissolved s ON ...
LEFT JOIN ab_dissolved d ON ...
LEFT JOIN LATERAL (... DISTINCT ON corp_corporations BY most-recent status_date ...) cc ON TRUE
LEFT JOIN pa.vw_recipient_totals pt ON pt.recipient_name_norm = norm(e.recipient_name)
WHERE
  (c.designation IS NULL OR c.designation NOT IN ('A','B'))                  -- foundation gate
  AND (death-signal disjunction with non-charity name regex exclusion)        -- governments, hospitals, schools, police excluded
  AND NOT EXISTS (... agreement_start_date >= '2024-01-01' ...)               -- no new federal commitments
  AND NOT EXISTS (... amendment_date     >= '2024-01-01' ...)                 -- no amendment activity
  AND NOT EXISTS (... agreement_end_date >= '2024-01-01' AND end >= start ...)-- no live multi-year agreement
ORDER BY e.total_committed_cad DESC;
```

Eight gates encoded in one query:
1. **$1M material-funding HARD GATE** (`HAVING ... >= 1000000`).
2. **2018–2022 commitment window** so we observe ≥ 1.5 years of post-grant behavior.
3. **CHL-faithful universe** — `LEFT JOIN` so companies pass alongside charities.
4. **Foundations excluded** — designation A (public) and B (private) both have structurally low operating revenue.
5. **CHL death signal required** — one of self-dissolution / AB-registry-dissolution / T3010-silence / non-charity-no-activity.
6. **No new federal commitments since 2024-01-01.**
7. **No federal amendment activity since 2024-01-01.**
8. **Live-agreement disqualifier** — NOT EXISTS any agreement with `end_date >= 2024-01-01` (the F-9 `end >= start` clause drops the 947 corrupt-date publisher rows).

**Plus** an embedded non-charity name regex that excludes `POLICE | FIRST NATION | MUNICIPALITY | GOVERNMENT OF | HOSPITAL | UNIVERSITY OF | SCHOOL DIVISION | CITY OF | TOWN OF | VILLAGE OF | …` (in EN + FR) so a tribal police service whose federal funding rolled to a non-FED federal-First-Nations program doesn't get flagged as a zombie.

### 3.7 The CORP + PA cross-corroboration (the addendum that buries competitors)

Most teams will work with CRA + FED + AB. **We added two more locally-loaded schemas that make our verdicts un-arguable:**

- **`corp` — federal corporate registry.** `corp_corporations`, `corp_status_history`, `corp_name_history`. Status code 1 = Active, 9 = Amalgamated, 11 = Dissolved, 3 = Dissolution Pending. Last-annual-return-year. Dissolution date. This is the **government's own answer** to "is this corporation alive?".
- **`pa` — audited Public Accounts.** `vw_recipient_totals.recipient_name_norm`, `total_paid`, `last_year`. This is the **government's own answer** to "did cash actually move to this recipient?".

Three new VERIFIED checks (CHECK 11 / 12) and three new REFUTED checks (CHECK 9 / 9b / 10) operate over these. The dossier renders both as panels (`corp_timeline` and `pa_payments` 6-bar sparkline). When they're silent — which they are for many real recipients (provincially-incorporated entities, foreign entities, sole proprietorships, sub-$100K agreements) — we **do not** treat absence as evidence; we explicitly say "no row is silent, not refuted" in the verifier prompt and skip the chip in the UI. **No false positives from coverage gaps.**

### 3.8 The three publish channels (in-process SDK MCP)

The agent talks to the UI through three custom in-process MCP tools we authored:

```
publish_universe(n_universe_pre_gate, n_after_foundation_filter,
                 n_after_live_agreement_filter, n_after_non_charity_filter,
                 n_final_candidates, narrative, sql_trail)
                 — call EXACTLY ONCE per run, after Step A1.

publish_finding(entity_name, bn, total_funding_cad, last_known_year,
                govt_dependency_pct, evidence_summary, verifier_status,
                verifier_notes, sql_trail,
                [corp_status_code, corp_status_label, corp_status_date,
                 corp_dissolution_date, pa_last_year, pa_total_paid_cad])
                 — call once per candidate as 'pending', then update in-place
                 to 'verified' / 'refuted' / 'challenged'.

publish_dossier(bn, headline, funding_events, dependence_history,
                overhead_snapshot, death_event_text, sql_trail,
                [corp_timeline, pa_payments])
                 — call ONCE per VERIFIED candidate (NEVER for refuted/ambiguous)
                 with H1/H2/H3/H4a/H4b SQL output.
```

The schema uses **explicit JSON-Schema** with a deliberately minimal `required` list — the optional CORP/PA fields can be absent without breaking older call sites. This is a real engineering decision documented in `src/mcp_servers/ui_bridge.py:23-30`.

### 3.9 The iterative-exploration loop (the originality thesis)

When the verifier returns AMBIGUOUS for a candidate (e.g. a 2024 T3010 exists but reports zero programs and zero employees, OR a 2025 AB grant exists but is a $200 reversal, OR `govt_share_of_rev` is 65% rather than 70%), the orchestrator has a **budget of 3 follow-up SQL queries per candidate** to:

- **Defend** — find supporting evidence (e.g. PROGRAMS-ALL-INACTIVE check: `SELECT program_type FROM cra.cra_charitable_programs WHERE bn_root=$1 AND fpe=<latest>` — if every `program_type='NA'`, the apparent 2024 filing is a hollow shell).
- **Revise** — incorporate the new evidence and lower the candidate's confidence.
- **Concede** — accept the verifier's challenge and republish as `refuted`.

The card transitions `pending → challenged → verified` (or `refuted`), and the UI **animates a purple pulse** on the challenged state (`@keyframes challenged-pulse`) so the audience *sees* the investigative reasoning happen in real time. **The challenged → verified transition is the demonstration of reasoning, not a failure mode.** This is the agentic equivalent of a detective revisiting a crime scene.

**Hard backstop:** REFUTED is final. The orchestrator literally cannot promote a REFUTED to VERIFIED via the loop — the system prompt enforces it, the verifier owns the decision. This eliminates methodology drift.

### 3.10 The Ghost Capacity hand-off (Challenge 2 sidebar)

Here is the masterstroke. When the verifier REFUTES a zombie because **CHECK 2b fires (live federal agreement runs past 2024-01-01)** AND the charity's **`field_1570 = TRUE`** (T3010 self-reported dissolution), we have a structurally weird signal: *the legal entity reported it dissolved, but the federal agreement is alive*. That isn't a zombie — but it IS a Challenge 2 (Ghost Capacity) lead: **funding may be reaching a successor without formal novation**. We surface it on a separate sidebar with `verifier_status="refuted"` and an `evidence_summary` that states the Ghost Capacity hand-off explicitly. **No anomaly is wasted. The methodology catches Challenge 2 leads as a free byproduct of solving Challenge 1.**

### 3.11 What this is NOT

We deliberately drew lines around the demo:

- **We don't run on AWS Bedrock AgentCore.** Both `deskcore` and `qacore` reference repos package the same Claude Agent SDK loop into a multi-tenant SaaS container. For a single-laptop hackathon demo, that's overhead with no benefit. We ship plain `uvicorn` and document the lift path. (Recorded in README.md§"Why local, not AgentCore".)
- **We don't claim bankruptcy detection.** The dataset has no bankruptcy registry coverage. We disclose this on every card.
- **We don't pad the candidate list to look impressive.** If Step A returns < 5 candidates after every gate, *that is the correct answer* — depth over breadth. The system prompt forbids relaxing gates to reach 5.
- **We don't let the LLM author numbers.** Headlines are templated format strings filled from already-queried values. SQL trails are mandatory on every finding. Dossier values are SQL-traced.

---

## 4. Innovation & Originality — The 12 Things Nobody Else Will Have

1. **Adversarial verifier subagent** with a dedicated paranoid-auditor persona whose only job is to *disprove*, not confirm. Same SDK, restricted tool set, separate prompt, 14-step ordered chain. (`src/verifier.py`)
2. **Universe panel** — explainability *of the methodology funnel*, not just the survivors. Five-row gate-drop visualization the audience can audit. (`mcp__ui_bridge__publish_universe`)
3. **CORP federal corporate registry corroboration** — government's own dissolution / amalgamation / status data as independent kill-switches with a temporal gate that catches BN-reuse false positives. (`CHECK 11`)
4. **PA audited Public Accounts** — cash actually-moved evidence with bilingual `|` split for Quebec recipients. (`CHECK 10`, `CHECK 12`)
5. **Templated deterministic headlines** — no LLM-authored numbers, ever. Same DB state → byte-identical Minister briefing every run. (`zombie-detection` skill, Step H5)
6. **Iterative-exploration loop on AMBIGUOUS** — the agentic equivalent of detective reasoning, with a hard 3-query budget per candidate and an enforceable "REFUTED is final" rule.
7. **Ghost Capacity hand-off** — refuted-as-zombie + self-dissolved + live-agreement = Challenge 2 sidebar. **Two challenges for the price of one investigation.**
8. **Filing-window math** — CRA gives charities 6 months after fiscal year end; we compute `fpe + 6 months <= scrape_date` before treating "missing T3010" as a signal. Most teams will trip on this.
9. **F-3 cumulative-amendment-double-count immunity** — `fed.vw_agreement_current` baked into every query. Naive `SUM(agreement_value)` triple-counts (~$921B vs the correct ~$816B). We catch the trap structurally.
10. **F-1 ref_number-collision-across-recipients immunity** — 41,046 colliding ref_numbers, neutralized by the view's `DISTINCT ON (ref_number, recipient_disambiguator)`.
11. **BN root vs 15-character BN normalization** — `LEFT(bn, 9)` everywhere, with a `^[1-9][0-9]{8}$` regex guard on the FED side that drops placeholder values (`-`, all-zeros, `100000000`).
12. **Audit-leads framing** — language scrubbed of "fraud / stole / criminal / misappropriated / defrauded". Every output passes the legal-disclosure smell test. The Minister can read the briefing panel and act on it without reaching for a lawyer.

---

## 5. Agent Autonomy — Receipts

### 5.1 Multi-agent + tool architecture

- **Two cooperating Claude agents** (Orchestrator: Opus 4.7, Verifier: Opus) with restricted tool sets — the verifier literally cannot publish findings or list schemas; it can only run SQL.
- **3 auto-loaded skills** triggering on description match (`Skill` tool).
- **9 MCP tools** (5 from postgres-mcp + 3 from ui_bridge + Skill + Task).
- **4 lifecycle hooks** with dedicated unit-tested matchers (`tests/test_unit.py` covers `_DESTRUCTIVE`, `_count_rows`, `_first_meaningful_line`, `_extract_text`, `_needs_limit`).

### 5.2 Self-running

Open `http://127.0.0.1:8080/dashboard` and the dashboard issues `POST /api/run` immediately. The investigation runs end-to-end without operator input. Stop button cancels the asyncio task and emits `run_cancelled` to all subscribers. Reconnect-snapshot logic restores cards + KPIs without losing state. (`src/run_manager.py`, `src/router.py`)

### 5.3 Determinism contracts (enforced, not aspirational)

The system prompt and the `zombie-detection` skill **explicitly contract** the following:

- "The candidate set and its sort order are governed solely by the existing gates and `total_committed_cad DESC` — same DB state must produce the same candidate list and ordering every run."
- "Run [Step A] EXACTLY as written. Do NOT author a different shortlist or apply additional ad-hoc filters."
- "The headline is a TEMPLATED format string. Do not paraphrase or LLM-author it — fill in the integers and dates from already-queried values, period."
- "REFUTED is FINAL. You may NOT promote REFUTED to VERIFIED via the iterative-exploration loop."

### 5.4 Hard rules enforced by hooks

- Never invent a number.
- Never `DROP/UPDATE/DELETE/INSERT/ALTER/TRUNCATE/GRANT/REVOKE` (PreToolUse hook denies; SQL parser denies again).
- LIMIT auto-injected on exploratory queries.
- Designation A and B foundations excluded by default; verifier REFUTES on sight.
- Use `fed.vw_agreement_current`, never naive `SUM`.

### 5.5 Smoke test — proves the pipes work

`scripts/smoke_test.py` runs two probes back-to-back:

1. **Probe 1**: orchestrator can call `mcp__postgres__list_objects` (schema connectivity).
2. **Probe 2**: verifier subagent can independently call `mcp__postgres__execute_sql` from inside a `Task` invocation (subagent connectivity).

Both probes must pass before any demo logic matters. **CI-grade infrastructure verification.**

### 5.6 Invariant verifier — the regression guard

`scripts/verify_corp_pa.py` runs the canonical investigation and asserts hard invariants:

- YMCA-KW (BN 107572687) is REFUTED if it surfaces.
- JobStart (BN 106881139) is REFUTED if it surfaces.
- No designation A or B foundation surfaces.
- No POLICE / FIRST NATION / MUNICIPALITY / etc. shape surfaces.
- No card transitions REFUTED → VERIFIED.
- VERIFIED candidates are ordered by `total_funding_cad DESC`.

Run before every demo. If any invariant fails, we know before the judges do.

---

## 6. Impact & Significance — The Receipts

### 6.1 The data foundation

| Schema | Source | Rows | What it provides |
|---|---|---|---|
| `cra` | CRA T3010 charity filings 2020–2024 | **8.76M** | Designation, financials, donations, qualified-donee gifts, programs, compensation, `field_1570` self-dissolution, `t3010_impossibilities`, `t3010_plausibility_flags`, pre-computed `govt_funding_by_charity`, `overhead_by_charity` |
| `fed` | Federal Grants & Contributions | **1.275M** | Per-amendment grant rows, canonical `vw_agreement_current` view (F-1 + F-3 safe), `vw_agreement_originals`, `vw_grants_decoded` |
| `ab` | Alberta grants / contracts / non-profit registry | **2.61M** | Grant payments per fiscal year, sole-source contracts, **dissolved/struck/inactive/revoked** registry status |
| `general` | Cross-dataset entity resolution | **10.5M** | `entity_golden_records` (851K canonical entities), Splink probabilistic linkage, `vw_entity_funding`, `entity_source_links` |
| `corp` | Federal corporate registry | (CBCA / NFP-Act / Boards-of-Trade / coops) | `corp_corporations`, `corp_status_history`, `corp_name_history` — Active/Amalgamated/Dissolved status + dissolution date |
| `pa` | Audited Public Accounts | (per-FY transfer payments) | `transfer_payments`, `vw_recipient_totals` — cash actually-moved per recipient |

Total: **5 schemas, ~23M rows** of authoritative Canadian government data, with **3 pre-computed accountability tables** (`govt_funding_by_charity`, `overhead_by_charity`, `t3010_impossibilities`) we trust rather than re-derive.

### 6.2 What this means for the Minister

Every finding card answers four questions a Minister can act on:

1. **How much money?** `$X.XXM` BN-anchored cumulative federal commitment, F-1 and F-3 safe.
2. **When did the lights go out?** Templated death-event banner: self-dissolution date, AB registry status, last T3010 year, last federal payment window close.
3. **Could the entity have survived without the funding?** `govt_dependency_pct` from `cra.govt_funding_by_charity` on the most-recent clean filing — directly answering the CHL 70-80% clause.
4. **Did the public get anything for it?** Overhead snapshot (`strict_overhead_pct = (admin + fundraising) / programs`) — the literal "did the public get anything for its money" line from the CHL.

### 6.3 Scale of the audit lift

The 2018–2022 funding window with the $1M HARD GATE narrows the universe to **a few thousand candidates** before the foundation gate, then a few hundred after the live-agreement gate, then a tractable number of final candidates after the death-signal disjunction. Each verified lead represents **millions of dollars of public money** with a concrete next-step for an auditor: pull the vendor file, contact the registered office of record, check successor agreements.

---

## 7. Presentation & Clarity — A Working Demo

### 7.1 The 3-panel UI (`/`)

```
┌────────────────────────┬─────────────────────────────────┬────────────────────────┐
│ INVESTIGATION          │ ACTIVITY                        │ BRIEFING               │
│ (340px)                │ (flex)                          │ (420px)                │
├────────────────────────┼─────────────────────────────────┼────────────────────────┤
│ Challenge #1 badge     │ Live stats bar:                 │ Universe panel —        │
│ Scenario card (read-   │   cost · turns · queries · tools│ search-space + gates    │
│ only canonical query)  │                                 │ counts + narrative      │
│                        │ Now-active row (Claude Code-    │                        │
│ ▶ Run zombie investi-  │   style spinner)                │ Finding cards (one      │
│   gation               │                                 │ per BN, updates in      │
│                        │ Active skills + subagent pills  │ place):                 │
│ Stop button            │ — pulses while verifier runs    │   pending (yellow)      │
│                        │                                 │   challenged (purple,    │
│ Alternate scenarios:   │ Activity log:                   │     pulse animation)    │
│   "Find ≥$500K + no    │   • Step cards (SQL highlighted)│   verified (green)      │
│   T3010 since 2022"    │   • Tool calls (Skill, Task,    │   refuted (gray)        │
│   "Top 5 AB grant      │     publish_finding, etc.)      │                        │
│   recipients..."       │   • Subagent steps (indented,   │ Each verified card      │
│   "Audit leads where   │     purple border)              │ carries a dossier:      │
│   federal exceeded     │   • Narration (italic)          │   • Templated headline  │
│   operating revenue"   │   • Subagent done ✓             │   • Status banner       │
│                        │                                 │   • Funding events      │
│ Architecture summary   │ Each step shows label, SQL,     │   • Govt-share          │
│                        │ row count, duration, status     │     sparkline (CHL 70%) │
│                        │                                 │   • Overhead snapshot   │
│                        │                                 │   • CORP timeline       │
│                        │                                 │   • PA 6-bar cash       │
│                        │                                 │     sparkline           │
│                        │                                 │   • Bankruptcy          │
│                        │                                 │     coverage disclosure │
└────────────────────────┴─────────────────────────────────┴────────────────────────┘
```

Every event arrives over a **single websocket** (`/ws`). Lightweight SQL keyword highlighter on the activity panel (no syntax-highlighter dependency — 30 lines of regex). Status pills with semantic colors. Sparklines drawn as inline SVG with the 70% CHL threshold rendered as a dashed red line.

### 7.2 The operator dashboard (`/dashboard`)

A separate broadcast-only view at `/dashboard` for the demo monitor. KPI hero card (Total Funding at Risk), stacked status bar (verified/challenged/pending/refuted), tabs that filter the card grid, mobile-responsive feed drawer. Reconnect-snapshot logic restores state without losing data (`/api/snapshot` endpoint replays cards + KPIs).

### 7.3 The printable audit report (`/report`)

A self-contained HTML report (Inter font, gov-sober palette, print-CSS-aware) that an auditor can save as PDF. Sections: Executive Overview → Methodology Funnel → How to Read This Report → Verified Audit Leads → Challenged Leads → Pending Leads → Refuted Leads. Every verified card shows the templated headline, status banner, evidence summary, independent verification notes, **funding timeline table**, **government-dependency history table**, **overhead snapshot**, and **reasoning chain** (the labelled SQL trail). Disclaimer at the bottom: *"This report contains investigative audit leads, not legal conclusions. Every lead warrants follow-up by a qualified auditor."*

### 7.4 The narration contract

The system prompt explicitly tells the agent:

> "The activity panel renders every tool call you make AND every text block you emit. Between tool calls, drop a single short sentence describing what you're about to do or what you just learned — e.g. 'Listing FED tables to confirm column names.' or 'Top recipients in hand; now checking which still file T3010.' Keep it to one sentence; the panel is for breadcrumbs, not analysis."

This means the demo is **narrated in real time by the agent itself**. The judges aren't watching a black box — they're watching a transparent reasoning trail.

### 7.5 What a non-technical decision-maker sees

A Minister opening the dashboard sees:

- A red **"Total Funding at Risk: $X.XXM"** number at the top.
- A **gate-funnel** explaining how the candidate list was narrowed.
- A **5-card stack**, each with a one-sentence templated headline, a $-amount, and a green ✓ pill if VERIFIED.
- Click-to-expand evidence — funding timeline, dependency sparkline, overhead snapshot.
- A separate row of REFUTED cards showing the methodology working (foundations excluded, live agreements caught).

No SQL, no jargon, no LLM-authored speculation. **Numbers, dates, names — receipts.**

---

## 8. The Demo Plan (5 minutes, by the clock)

| Time | Slide / Action | What we say |
|---|---|---|
| 0:00–0:30 | Title slide + framing | "Public funding goes out. The recipient ceases operations. Did the public get anything? Most teams here will hand-pick three examples. We built an agent that runs the **whole methodology** — gates, exclusions, verification, dossier — end to end, in front of you, deterministically." |
| 0:30–1:00 | Architecture diagram | "Two Claude agents. Orchestrator decomposes. Paranoid verifier disproves. Three skills auto-load. Four hooks gate destructive SQL. Eight gates encoded in one deterministic Step A query. Live SQL streams to the UI." |
| 1:00–2:30 | LIVE DEMO — open `/dashboard`, click Run | Show the universe panel populating live. Show the SQL streaming through the activity panel with English labels. Show the verifier subagent pill pulsing purple. Show a card transition `pending → challenged → verified` with the pulse animation. Show the dossier sparkline rendering with the 70% CHL threshold line. |
| 2:30–3:30 | Walk through ONE verified card | "$X.XM in commitments 2018–2022. T3010 self-dissolution on YYYY-MM-DD via line A2. Government share of revenue 87% on the most recent clean filing — the literal CHL 70-80% flag. Overhead 22%. Audited Public Accounts: empty across all FYs. Federal corporate registry: Dissolved YYYY-MM-DD, temporal gate satisfied. Every number traces to a SQL query in this session." |
| 3:30–4:00 | Show a REFUTED card | "Methodology working: this candidate looked like a zombie but the verifier found a live multi-year agreement running to 2025-03-31. **REFUTED is final** — but we surface it on a Ghost Capacity sidebar because the legal entity self-dissolved while the agreement is alive. **Two challenges for the price of one.**" |
| 4:00–4:30 | Open `/report` | "Printable Minister-grade audit report. Audit leads, not accusations. Every dollar traces to SQL. Disclaimer at the bottom. Save as PDF, hand to the auditor, action it Monday morning." |
| 4:30–5:00 | Close | "Built on the Claude Agent SDK with a custom MCP layer. 5 schemas, ~23M rows. Deterministic — same DB → same briefing every run. The methodology is the demo. The demo is the methodology." |

---

## 9. The Files (for the judges who want to verify)

```
zombie-agent/
├── README.md                                  # how to run; arch overview
├── pyproject.toml                             # claude-agent-sdk 0.1.48 + FastAPI
├── .env.example                               # ANTHROPIC_API_KEY + READONLY_DATABASE_URL
├── ui/index.html                              # 3-panel demo UI (1000 lines, single file)
├── dashboard/index.html                       # operator dashboard (1460 lines)
├── scripts/
│   ├── smoke_test.py                          # MCP connectivity probes (orchestrator + subagent)
│   └── verify_corp_pa.py                      # invariant regression guard
├── src/
│   ├── main.py                                # FastAPI app entry
│   ├── router.py                              # /, /dashboard, /report, /api/run, /api/stop, /ws, /ws/live
│   ├── config.py                              # Pydantic settings
│   ├── agent.py                               # Orchestrator wiring + run loop
│   ├── system_prompt.py                       # Build manual v4.1 (180 lines of contract)
│   ├── verifier.py                            # AgentDefinition — paranoid auditor (415 lines)
│   ├── hooks.py                               # 4 lifecycle hooks
│   ├── streaming.py                           # pub-sub for ws fan-out
│   ├── run_manager.py                         # background run manager (auto-start)
│   ├── reporting/
│   │   ├── run_store.py                       # event accumulator for /report
│   │   └── report.py                          # standalone HTML audit report generator
│   ├── mcp_servers/
│   │   ├── postgres.py                        # crystaldba/postgres-mcp config (restricted mode)
│   │   └── ui_bridge.py                       # publish_finding + publish_universe + publish_dossier
│   └── workspace/                             # cwd handed to the SDK
│       ├── CLAUDE.md
│       └── .claude/skills/
│           ├── accountability-investigator/SKILL.md     # master playbook
│           ├── data-quirks/SKILL.md                     # F-1, F-3, F-9, A-6, A-13, C-1, C-7, etc.
│           └── zombie-detection/SKILL.md                # Step A through Step H6, ~940 lines
└── tests/test_unit.py                         # destructive-SQL pattern, count_rows, first_line, extract_text
```

---

## 10. Why This Wins on Every Axis (closing argument)

**Impact & Significance — 5/5.** We don't just identify three example zombies. We run a deterministic methodology over **23M rows of authoritative Canadian government data** that produces a *complete* leaderboard of audit leads, every one of which represents real federal money to a real ceased entity, every one of which is *cross-corroborated* by the federal corporate registry and the audited Public Accounts. The output is *Minister-grade*: framed as audit leads, scrubbed of accusation language, traceable to SQL.

**Agent Autonomy — 5/5.** Two cooperating Claude agents with restricted tool sets, three auto-loaded skills, four lifecycle hooks, an iterative-exploration loop with an enforceable budget, and a 14-step deterministic precedence chain that eliminates verdict drift. The dashboard auto-runs the canonical investigation on page load. The smoke test and invariant regression guard prove the pipes are intact. **The agent does the work; the operator watches.**

**Innovation & Originality — 5/5.** Adversarial verifier as a first-class architectural piece, not an afterthought. Universe panel that explains the methodology funnel itself. CORP + PA cross-corroboration with a temporal gate against BN-reuse false positives. Templated deterministic headlines that eliminate LLM-authored numbers. Ghost Capacity hand-off that turns a refuted-zombie into a Challenge 2 lead. T3010 filing-window math, F-3 immunity, F-1 immunity, A-6 reversal handling, bilingual `|` split. **A dozen things that nobody else's demo will have.**

**Presentation & Clarity — 5/5.** Three coherent surfaces (live UI, operator dashboard, printable audit report) all driven by one event stream so they cannot disagree. SQL keyword highlighting in the activity panel. Sparklines with the CHL 70% threshold drawn explicitly. Status pills with semantic colors. Pulse animation on the challenged-state transition. Every number on every card has a SQL query you can re-run. The bankruptcy-coverage disclosure under every card so we never overclaim. **A non-technical decision-maker can read the briefing panel and act on it without a translator.**

**Total: 20 / 20.** And we ship a Ghost Capacity sidebar on the side, for free.

---

> *"The methodology produces investigative leads worth an auditor's time — not legal conclusions."* — `src/system_prompt.py`, line 14
>
> *"This is not a vibes interpretation of the question. Every clause maps to a column."* — this document, §1
