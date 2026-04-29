# Zombie-Recipients Agent — v3 Correctness & Polish Plan

**Status:** Ready to implement. Stand-alone hand-off document.
**Audience:** A fresh Claude Code session with no prior context on this repo.
**Goal:** Take the existing zombie-recipients agent from "sometimes correct, always inconsistent" to "deterministic across runs, methodologically defensible, demo-ready" before the AI for Accountability Hackathon (Agency 2026, Ottawa, April 29 2026).

---

## 0. How to use this document

1. Read sections 1–4 first. They give you the context you need to act safely.
2. Section 5 (Defects) and section 6 (Enhancements) are numbered (D1, D2, …, E1, E2, …). Each item is self-contained — file path, line number, symptom, root cause, fix, verification.
3. Section 7 is the recommended patch order. Follow it; it is sequenced so each step is independently verifiable and so you don't paint yourself into a corner.
4. Section 8 is the post-patch verification plan. Do not declare done until those checks pass.
5. Section 9 lists anti-patterns. Do not do those things even if they look tempting.

You do **not** need to re-derive any analysis below. The 4 agent traces have already been read end-to-end and the relevant repo files have been audited. Trust the findings; your job is execution.

---

## 1. Repo & challenge context

The repo at `/Users/reza.yaghoubi/ottawa_hackathon/ottawa-hackaton-2026` is a hackathon working tree for the **AI for Accountability Hackathon (Agency 2026)**. It unifies four Canadian government open-data sources into one Postgres database, schema-isolated:

| Schema | Module | What it owns |
|--------|--------|--------------|
| `cra` | `CRA/` | T3010 charity filings 2020–2024 (~8.76M rows). Includes pre-computed pre-cycle / risk / overhead / `govt_funding_by_charity` tables. |
| `fed` | `FED/` | Federal Grants & Contributions (~1.275M rows). Two canonical views: `fed.vw_agreement_current` and `fed.vw_agreement_originals`. |
| `ab` | `AB/` | Alberta grants/contracts/sole-source/non-profit registry (~2.61M rows). |
| `general` | `general/` | Cross-dataset entity-resolution → `entity_golden_records` (~10.5M rows). |

`challenges.md` lists 10 hackathon themes. The team chose **Challenge #1 — Zombie Recipients**:

> Did public funding go to entities that ceased operations within 12 months — or to entities so dependent on public money (>70–80% of revenue) that they could not survive without it?

The host evaluation lives at `evaluations/01-zombie-recipients.md`. Headline scores: Data 4/5, Implementation 4/5, Fit 5/5, total 13/15 — Pursue. The host explicitly recommends a per-entity dossier UI with three panels (funding-events timeline, dependence-ratio sparkline, status-after-funding banner) and a "two-minute story" headline per VERIFIED card.

The CRA / FED / AB / general modules each have their own `CLAUDE.md` with module-specific gotchas. The most load-bearing pieces of context for this challenge:

- **`fed.agreement_value` is cumulative across amendments**, not delta. Naive `SUM` triple-counts ($921B vs the correct ~$816B). Always go through `fed.vw_agreement_current` (current commitment per agreement) or `fed.vw_agreement_originals` (initial commitment).
- **`fed.ref_number` is not unique** (41,046 collisions). Group by `(ref_number, recipient)`, not `ref_number` alone. The two FED views above already do this disambiguation by construction.
- **CRA designation A = public foundation, B = private foundation, C = charitable organization.** A and B exist to *distribute* grants, not deliver programs. The CHL "70-80% revenue dependency" flag does not interpret cleanly for them. Only designation C is in scope for zombie analysis.
- **2024 CRA data is partial** (charities have 6 months after fiscal-year-end to file). Don't infer "stopped filing" within 6 months of FY end 2024.
- **AB has almost no BNs.** Cross-dataset matching for AB recipients goes through `general.entity_golden_records`, not BN joins.
- **The `bn` column is messy.** Group by 9-digit BN root: `LEFT(NULLIF(bn,''),9)`.

For deeper context read `CLAUDE.md` (root), `CRA/CLAUDE.md`, `FED/CLAUDE.md`, and `KNOWN-DATA-ISSUES.md`. They are concise and authoritative.

---

## 2. The agent — architecture map

The agent lives at `zombie-agent/`. It is a Python project (uv-managed), running a FastAPI server with a websocket that drives a single-page UI. Architecture:

```
User → ws → run_question (agent.py)
              ├─ ClaudeSDKClient (Sonnet 4.6)
              │   ├─ skills auto-loaded from .claude/skills/*/SKILL.md
              │   ├─ MCP "postgres" (crystaldba/postgres-mcp, read-only)
              │   ├─ MCP "ui_bridge" (in-process, publish_finding tool)
              │   └─ subagent "verifier" (Sonnet, restricted to execute_sql)
              └─ streaming → ws → UI (briefing panel + activity panel)
```

**Files you will touch.** All paths relative to repo root.

| Path | Role |
|------|------|
| `zombie-agent/src/system_prompt.py` | Orchestrator system prompt (the "build manual v4.1" prompt). |
| `zombie-agent/src/verifier.py` | Verifier subagent definition + prompt. |
| `zombie-agent/src/agent.py` | `run_question`, `ClaudeAgentOptions`, tool allow-list, hooks wiring. |
| `zombie-agent/src/hooks.py` | `safe_sql_hook` (denies destructive SQL, auto-injects LIMIT), `inject_context_hook` (run-time reminders), `subagent_stop_hook`. |
| `zombie-agent/src/mcp_servers/ui_bridge.py` | In-process MCP server with `publish_finding`. |
| `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md` | Recipe for finding zombies. Contains the "Step A" deterministic candidate-enumeration query. |
| `zombie-agent/src/workspace/.claude/skills/accountability-investigator/SKILL.md` | Master playbook. Loaded first on every question. |
| `zombie-agent/src/workspace/.claude/skills/data-quirks/SKILL.md` | Catalogue of dataset defects. Loaded before any SQL. |
| `zombie-agent/ui/index.html` | Single-page UI. Briefing panel + activity panel. |

**Files you will NOT touch unless explicitly told to.** `zombie-agent/src/router.py`, `zombie-agent/src/main.py`, `zombie-agent/src/streaming.py`, `zombie-agent/src/config.py`, `zombie-agent/src/mcp_servers/postgres.py`, anything under `CRA/`, `FED/`, `AB/`, `general/`. Those are external scope.

**Verifier model: it cannot load skills.** `AgentDefinition` in `claude-agent-sdk 0.1.48` has no `skills` field, and the verifier's `tools` list does not include `Skill`. The data-quirks rules it needs are therefore embedded directly in its prompt. If you change `data-quirks/SKILL.md`, you MUST mirror the change into `verifier.py`. There is no automatic propagation.

**Permission mode is `bypassPermissions`.** The orchestrator can call any tool in its allow-list without prompting. Risky tools (destructive SQL) are blocked by `safe_sql_hook`, not the permission system.

**Tool searching is deferred.** When the agent needs `Task`/`Agent`/`Skill`, it will burn 1–3 turns on `ToolSearch` calls before finding them. This is annoying but not a bug — leave it alone unless §6 explicitly addresses it.

---

## 3. Ground truth — host evaluation summary

`evaluations/01-zombie-recipients.md` (read it in full once). The relevant operational rules:

- **Datasets needed:** `fed.grants_contributions` + `fed.vw_agreement_current`; `cra.cra_identification`, `cra.cra_financial_details`; `ab.ab_non_profit`; `general.entity_golden_records`.
- **Known traps explicitly listed by the host:**
  - F-3: `fed.agreement_value` is cumulative — use `fed.vw_agreement_current` / `fed.vw_agreement_originals`. Never SUM the raw base table.
  - F-1: `fed.ref_number` is not unique. The two FED views neutralize this by including a recipient disambiguator in the `DISTINCT ON`.
  - AB has almost no BNs — route through `general.entity_golden_records`.
  - 2024 CRA data is partial.
  - 2024 T3010 form revision: some fields NULL for 2024 (removed), others NULL for 2020–2023 (added 2024).
- **Recommended demo shape (verbatim):** "A live recipient dossier. The user types or selects a funded entity (or asks the agent in natural language). The agent retrieves the funding history from `fed`/`ab`, the CRA registration trajectory, the AB non-profit status, computes the dependence ratio from `cra.cra_financial_details`, and renders a single page with: top-line verdict (Active / Zombie / At-risk), funding-events timeline, dependence-ratio sparkline, and a status-change banner."
- **Two-minute story test:** "This $4.2M went to entity Y, which dissolved 9 months later and where federal grants made up 86% of revenue."

Score-wise the demo currently meets the Data and Implementation criteria but the Fit / Resilience criteria are at risk because of the run-to-run drift documented in section 4.

---

## 4. What four agent runs showed

Four traces were captured (PDFs at `/Users/reza.yaghoubi/ottawa_hackathon/Zombie Recipients — *.pdf`), all on the same prompt asking for 3 federally-funded operationally-dormant recipients. Plain-text dumps live in `/tmp/zombie_traces/*.txt`. Summary of what each surfaced:

| Run | Time | Cost | Turns | Top candidates published (BN, $, verdict) |
|-----|------|------|-------|---------------------------------------------|
| 12pm | 11:43 PM | $2.78 | 46 | YMCA-KW 107572687 $25.58M **VERIFIED**; JobStart 106881139 $9.65M **VERIFIED**; Canada World Youth 118973999 $3.07M VERIFIED; Interagency Coalition AIDS 864967922 $1.99M VERIFIED; Learning Partnership 140756107 $2.64M |
| 1130pm | — | $1.94 | 43 | Canada World Youth $3.07M; Banff TV Foundation 854953700 $4.26M; Expert Collective 781347307 $2.76M; Learning Partnership $2.64M; Canadian Energy Research Inst. 121461313 $1.24M |
| 1230 | 12:00 AM | $2.16 | 43 | Treaty Three Police 870094018 **$222.01M** VERIFIED; Anishinabek Police 140591710 **$161.42M** VERIFIED; (third large entity) 872308499 $171.79M; Canada World Youth **$39.87M**; Learning Partnership $2.64M |
| 11pm | 11:11 PM | $2.25 | 47 | YMCA-KW $45.40M **REFUTED**; JobStart $9.65M **REFUTED**; Canada World Youth **$39.90M** VERIFIED; Interagency Coalition AIDS $1.99M VERIFIED; Learning Partnership $2.64M VERIFIED |

**Three smoking guns visible in the table:**

1. **Same BN, different verdicts.** YMCA-KW (107572687) and JobStart (106881139) are VERIFIED in 12pm and REFUTED in 11pm. Both have `field_1570 = TRUE` self-dissolution AND a CIC settlement agreement extending to 2025-03-31. The verifier prompt has CHECK 8 (field_1570=TRUE → VERIFIED) and CHECK 2b (live agreement → REFUTED) without a precedence rule. Stochastic.

2. **Same BN, different totals.** Canada World Youth (118973999) shows $3.07M in two runs and $39.9M in two others. 13× variance on identical input. Caused by the orchestrator falling back to the `data-quirks` inline CTE (which has a different ORDER BY than `fed.vw_agreement_current`) when it incorrectly believes the view doesn't exist (see D2).

3. **Indigenous police boards padded into the candidate set.** The 1230 run surfaced Treaty Three Police Service Board ($222M), Anishinabek Police ($161M), and a third $171M non-charity. These are not zombies — they are operationally active First Nations police services whose federal funding rolled to non-FED programs. They surface because the "no_post_grant_activity" rule for non-charity recipients fires when there's no AB grant in 2024+, but Ontario police services are never expected to receive AB grants.

**The govt-dependency UI numbers are also visibly wrong** — "8118%" for 81.18%, "9661%" for 96.61%, "1347%" for 13.47%. UI multiplies a value already in percent units by 100 again.

---

## 5. Defects — fix these first

Each defect has: file & line, symptom, root cause, fix, verification.

### D1 — Verifier prompt has no precedence rule between CHECK 2b (live agreement) and CHECK 8 (field_1570 self-dissolution)

**File:** `zombie-agent/src/verifier.py`

**Symptom.** YMCA-KW (BN 107572687) and JobStart (BN 106881139) are VERIFIED in some runs and REFUTED in others. Both pass CHECK 8 (the charity itself filed a T3010 saying it had wound up) and fail CHECK 2b (an unamended CIC settlement-services agreement under their BN runs to 2025-03-31). The verifier picks whichever check it reads "first" in the chain — and the LLM is non-deterministic about that.

**Root cause.** Lines 50-56 of `verifier.py` instruct REFUTED for CHECK 2b. Lines 111-122 instruct VERIFIED for CHECK 8. The output-format section (167-186) lists both as decision points without saying one wins. The orchestrator's `system_prompt.py` is also silent on the conflict.

**Authoritative answer.** The `zombie-detection` skill (`.../SKILL.md`, "Live-agreement test — disqualifies a candidate") is unambiguous: *"Active multi-year delivery contracts that started pre-2024 but run past 2024-01-01 fail the zombie test. They may be Challenge 2 (Ghost Capacity) candidates if delivery capacity is missing — but that is a different investigation. Refute them as zombies, do not blur the categories."* So **live agreement disqualifies even if field_1570=TRUE.** The agreement is alive even if the legal entity is dead — that is itself the accountability story, but it is Challenge 2, not Challenge 1.

**Fix.** Add an explicit precedence block at the top of `VERIFIER_PROMPT`. Reorder the existing checks so the deterministic refutations run before the field_1570 positive evidence. Concretely:

```
PRECEDENCE — apply in this order, return the first matching verdict per candidate:
  1. CHECK 5 (BN-anchored vw_agreement_current total < $1M)         → REFUTED
  2. CHECK 0 (designation A or B)                                   → REFUTED
  3. CHECK 1 (T3010 filing window still open)                       → REFUTED
  4. CHECK 7 (entity rebranded — identification_name_history shows
              a name change in the most recent year)                → REFUTED
  5. CHECK 2b (FED agreement_end_date >= 2024-01-01 AND
              end_date >= start_date on any row tied to the BN)     → REFUTED
  6. CHECK 3 (any AB payment > 0 in FY2024-25 / FY2025-26 for the
              resolved entity_id)                                   → REFUTED
  7. CHECK 8 (field_1570 = TRUE — first-party dissolution)          → VERIFIED
  8. CHECK 6 (govt_share_of_rev < 70 on most-recent clean filing,
              row exists in govt_funding_by_charity)                → AMBIGUOUS
  9. otherwise (death signal fired AND nothing above triggered)     → VERIFIED
```

**Verification.** Re-run the same prompt 3× consecutively. YMCA-KW and JobStart should be REFUTED every time, with reason citing `agreement_end_date 2025-03-31`. Canada World Youth should be VERIFIED every time. The verdict-status JSON block at the end of the verifier reply should be identical across runs (modulo `reason` wording).

---

### D2 — `accountability-investigator` skill falsely says the FED views don't exist

**File:** `zombie-agent/src/workspace/.claude/skills/accountability-investigator/SKILL.md` lines 27-28

**Symptom.** In the 1230 run the orchestrator concluded `fed.vw_agreement_current` doesn't exist and fell back to the `data-quirks` inline CTE. That CTE has a subtly different ORDER BY than the view (see D3), producing different latest-amendment rows for the same agreements. Result: Canada World Youth's BN-anchored total swung from $3.07M (view) to $39.87M (CTE) in the 1230 run.

**Root cause.** Line 27-28 reads: *"The database does NOT ship with `vw_agreement_current` / `vw_agreement_originals` views; do not reference them."* This contradicts:

- `FED/CLAUDE.md` (canonical source for FED data quirks) which says the views are the canonical mitigation.
- `data-quirks/SKILL.md:42-55` which says the views ship and to use them.
- `FED/scripts/01-migrate.js:270-307` which actually creates them at module-bootstrap time. The verifier in the same 1230 trace queries `fed.vw_agreement_current` successfully later in the run (so it really does exist).

**Fix.** Delete those two lines. Replace with:
```
- `fed.vw_agreement_current` and `fed.vw_agreement_originals` ship with the
  schema (per `FED/CLAUDE.md` and `FED/scripts/01-migrate.js`). Use them
  directly. They neutralize both F-3 (cumulative-amendment double-count) and
  F-1 (ref_number collisions) by construction.
```

Also remove from line 26 the parenthetical "(originals-only approximation)" since `vw_agreement_originals` is now the named go-to and is exact.

**Verification.** Run the same prompt 3× consecutively. The orchestrator narration must never say "the view doesn't exist." All Step A and CHECK 5 SQL must use `fed.vw_agreement_current`, not the inline CTE. Canada World Youth's `total_funding_cad` must be the same number across runs — should be $3.07M.

---

### D3 — Inline CTE in `data-quirks` has a different ORDER BY than `fed.vw_agreement_current`

**File:** `zombie-agent/src/workspace/.claude/skills/data-quirks/SKILL.md` lines 60-78

**Symptom.** Even when the orchestrator does fall back to the inline CTE (which it should not after D2 is fixed, but defensive correctness matters), the totals it computes don't match the view. This created the secondary path to the $-amount drift.

**Root cause.** `fed.vw_agreement_current` is defined at `FED/scripts/01-migrate.js:270-307` and orders by:

```sql
ORDER BY
  ref_number,
  COALESCE(recipient_business_number, recipient_legal_name, _id::text),
  NULLIF(regexp_replace(amendment_number, '\D', '', 'g'), '')::int DESC NULLS LAST,
  amendment_date DESC NULLS LAST,
  _id DESC
```

The data-quirks inline CTE orders by:

```sql
ORDER BY
  ref_number,
  COALESCE(recipient_business_number, recipient_legal_name, _id::text),
  amendment_date  DESC NULLS LAST,
  CASE WHEN amendment_number ~ '^[0-9]+$' THEN amendment_number::int ELSE -1 END DESC,
  _id DESC
```

The two differ on the priority of `amendment_number` vs `amendment_date`. When a publisher anomaly disagrees on which amendment is "latest," the two paths pick different rows, and `SUM(agreement_value)` differs.

**Fix.** Replace the inline CTE in `data-quirks/SKILL.md:60-78` with the exact ordering from the view:

```sql
WITH agreement_current AS (
  SELECT DISTINCT ON (
    ref_number,
    COALESCE(recipient_business_number, recipient_legal_name, _id::text)
  ) *
  FROM fed.grants_contributions
  WHERE ref_number IS NOT NULL
  ORDER BY
    ref_number,
    COALESCE(recipient_business_number, recipient_legal_name, _id::text),
    NULLIF(regexp_replace(amendment_number, '\D', '', 'g'), '')::int DESC NULLS LAST,
    amendment_date DESC NULLS LAST,
    _id DESC
)
SELECT ... FROM agreement_current ...;
```

Add a one-line comment above the CTE: `-- This ordering must match fed.vw_agreement_current at FED/scripts/01-migrate.js:270-307.`

**Verification.** `SELECT SUM(agreement_value) FROM fed.vw_agreement_current` and `SELECT SUM(agreement_value) FROM <inline CTE>` should return the same total to the cent. Canada World Youth-anchored total should match across both paths.

---

### D4 — Step A does not enforce the live-agreement disqualifier

**File:** `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md` lines 119-253 (the Step A query)

**Symptom.** Step A surfaces YMCA-KW, JobStart, and similar entities even though they have agreements running to 2025-03-31. The verifier then has to refute them via CHECK 2b. When CHECK 2b collides with CHECK 8 the LLM picks stochastically (this is what D1 fixes from the verifier side; D4 fixes it from the gate side so the conflict doesn't reach the verifier in the first place). Beyond the conflict, Step A advertised as deterministic but isn't, because borderline entities reach the verifier at all.

**Root cause.** Step A has two `NOT EXISTS` clauses on `agreement_start_date >= 2024-01-01` and `amendment_date >= 2024-01-01`. It does **not** have one on `agreement_end_date >= 2024-01-01`. So a 2018-signed 5-year contract that runs to 2023-03-31 is correctly excluded as "no further activity," but a 2020-signed 5-year contract that runs to 2025-03-31 — never amended — passes Step A despite the live-agreement disqualifier the same skill defines on lines 66-80.

**Fix.** Add this clause to the Step A WHERE block, immediately after the existing two `NOT EXISTS` (just before the `ORDER BY`):

```sql
-- No FED agreement extends into 2024+ (catches zero-amendment 5-year contracts
-- and matches the live-agreement disqualifier defined on lines 66-80 of this
-- skill). The end_date >= start_date guard drops the 947 KDI F-9 corrupt-date
-- rows where end < start.
AND NOT EXISTS (
  SELECT 1 FROM fed.grants_contributions
  WHERE LEFT(NULLIF(recipient_business_number,''),9) = e.bn_root
    AND agreement_end_date >= '2024-01-01'
    AND agreement_end_date >= agreement_start_date
)
```

Also update the prose under the query to add a 7th invariant:
```
7. Live-agreement disqualifier: NOT EXISTS any agreement_end_date >= 2024-01-01.
   This is the gate-side enforcement of the rule defined under "Live-agreement
   test" above. Catches zero-amendment multi-year contracts.
```

**Side effect — and how to handle it.** With D4 in place, fewer charities pass Step A. In particular, only `Canada World Youth` and `Learning Partnership` are likely to qualify at the strictest setting plus `Interagency Coalition on AIDS / Development`. That is **fine and methodologically correct**. Do NOT relax other gates to pad the candidate count back to 5. The host evaluation prefers depth over breadth (`evaluations/01-zombie-recipients.md:41`: *"Per-recipient query is the natural unit"*). If Step A returns fewer than 5 candidates, the orchestrator should publish all of them and clearly note the gate counts in the briefing — see E5.

**Verification.** YMCA-KW and JobStart should never appear as candidates after D4. Canada World Youth should appear with `total_M = 3.07` regardless of run. Re-run 4× consecutively; verified candidate set must be a stable subset of `{Canada World Youth, Interagency Coalition on AIDS, Learning Partnership}`.

---

### D5 — UI renders govt-dependency 100× larger than reality

**File:** `zombie-agent/ui/index.html` line 566

**Symptom.** The briefing card shows "8118%" for Canada World Youth (true value 81.18%), "9661%" for JobStart (96.61%), "1347%" for Learning Partnership (13.47%). Visible across every run. Single most demo-killing visible defect.

**Root cause.** The line reads:
```js
(m.govt_dependency_pct ? ` · govt-dependency ${(m.govt_dependency_pct*100).toFixed(0)}%` : '');
```
But `cra.govt_funding_by_charity.govt_share_of_rev` is already in percent units (0–100) per `CRA/scripts/advanced/08-government-funding-analysis.js:195-198`: `ROUND((federal+provincial+municipal+section_d) / revenue * 100, 2)`. The orchestrator passes the value through `publish_finding` unchanged. The UI then multiplies by 100 again.

**Fix.** Drop the `*100` and bump precision to one decimal place:
```js
(m.govt_dependency_pct ? ` · govt-dependency ${m.govt_dependency_pct.toFixed(1)}%` : '');
```

**Verification.** Open the briefing UI. Verified Canada World Youth card should read "govt-dependency 81.2%" (was 8118%). Learning Partnership should read "govt-dependency 13.5%" (was 1347%).

**Sanity guard.** While editing, search the UI file for any other `*100` near a percent literal. There should not be one for funding totals — those use `$X.XXM` and are passed in CAD already.

---

### D6 — `inject_context_hook` only excludes designation A; should exclude both A and B

**File:** `zombie-agent/src/hooks.py` lines 173-176

**Symptom.** A subtle correctness bug — the run-time reminder string injected on every prompt says "Exclude `cra.cra_identification.designation = 'A'` from zombie candidates." But the zombie-detection skill (correctly) excludes both A (public foundation) and B (private foundation). When the orchestrator scans this reminder it may permit B-designation candidates through if it doesn't immediately load the skill.

**Root cause.** Drift between the hook and the skill. Easy to miss because both are correct in isolation.

**Fix.** Change line 175-176 to:
```python
"  - Exclude cra.cra_identification.designation IN ('A','B') from "
"zombie candidates (A=public foundation, B=private foundation)."
```

**Verification.** Search the agent narration in any new run for "designation = 'A'" string. Should now read "IN ('A','B')". No designation-B foundation should ever appear in a published candidate list.

---

### D7 — Non-charity Indigenous police boards / municipal entities false-positive

**File:** `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md` Step A query

**Symptom.** In the 1230 run, three Indigenous police boards / governing authorities surfaced: Treaty Three Police Service Board ($222.01M), Anishinabek Police Governing Authority ($161.42M), and a third $171.79M entity. They have huge cumulative federal commitments 2018-2022, no T3010 filings (they are not charities — the "no T3010" signal does not apply), and no AB grants in 2024+ (they are in Ontario; Alberta would never fund them). They satisfy the gate but they are NOT zombies — they are operationally active under federal-provincial-First Nations agreements that aren't surfaced by the FED dataset's later years.

**Root cause.** Step A's "no_post_grant_activity" branch (death signal d) fires for any non-CRA-registered recipient with no AB grants 2024+. For Ontario or BC entities this is meaningless; AB grants are not a liveness signal for them.

**Fix.** Add to Step A's WHERE clause an exclusion for recipient legal-name patterns and recipient-type codes that are operationally publicly-funded but out of scope for "zombie":

```sql
-- Exclude operationally publicly-funded non-charity entities from the
-- "no_post_grant_activity" branch. These are governments, police services,
-- school boards, hospitals, universities — they may go quiet in the FED
-- dataset because their funding rolled to a non-FED federal-provincial
-- program, not because they ceased operations.
AND e.recipient_name !~* (
  '\m(POLICE|POLICING|TRIBAL POLICE|FIRST NATION|BAND COUNCIL|'
  '|GOVERNMENT OF|MINISTRY OF|CITY OF|MUNICIPALITY OF|TOWN OF|'
  '|VILLAGE OF|REGIONAL DISTRICT|COLLEGE OF|UNIVERSITY OF|'
  '|HOSPITAL|HEALTH AUTHORITY|SCHOOL DIVISION|SCHOOL DISTRICT|'
  '|SCHOOL BOARD)\M'
)
AND e.recipient_type NOT IN ('GBC','GP','GF','GM','IS')
```

Recipient-type codes documented in `FED/docs/DATA_DICTIONARY.md` (verify by reading that file before committing — `IS` may be coded differently in the live data; if so, just keep the legal-name regex and drop the `recipient_type` filter).

**Verification.** Re-run with the prompt verbatim. No Indigenous police board, municipal entity, or hospital should appear in any candidate list. Use `grep -iE "(POLICE|MUNICIPAL|HOSPITAL|UNIVERSITY|MINISTRY)"` against the published findings — must return zero.

---

### D8 — Orchestrator can override the verifier's REFUTED via "challenged → verified" loop

**File:** `zombie-agent/src/system_prompt.py` lines 65-77; `zombie-agent/src/agent.py` (parse step)

**Symptom.** In the 12pm run the verifier returned a clear REFUTED on YMCA-KW (live agreement) but the orchestrator narrated *"The YMCA is a curious case—it self-reported dissolution in 2021 but still has an active agreement … pushing through as VERIFIED."* The system prompt allows "challenged → verified" promotions on AMBIGUOUS verdicts, but the orchestrator misapplied this to a REFUTED verdict.

**Root cause.** Two issues:
1. The system prompt says "iterative-exploration loop … for any candidate the verifier marks AMBIGUOUS." But this is only enforced in prose — there is no machine-parsed gate.
2. The verifier returns a JSON block like `{"verdicts": [{"bn":"...","status":"REFUTED","reason":"..."}]}`. `agent.py` does not parse this JSON; the orchestrator just re-narrates the verifier's English output and decides for itself.

**Fix.** Two parts:

(a) Tighten `system_prompt.py:65-77` (the "How to handle challenges" section) to:

```
For any candidate the verifier marks AMBIGUOUS, you have a budget of up to 3
follow-up SQL queries per candidate to either defend, revise, or concede. The
final verdict you publish must be VERIFIED, REFUTED, or AMBIGUOUS.

A REFUTED verdict from the verifier is FINAL. You may not override REFUTED
to VERIFIED via the iterative-exploration loop. If the verifier's REFUTED
reason is "live federal agreement runs past 2024-01-01," consider whether the
entity is a Challenge 2 (Ghost Capacity) lead worth surfacing on a separate
panel — but do NOT re-classify it as a zombie.
```

(b) Add a small JSON parser in `agent.py`. After the verifier subagent finishes, extract the `verdicts` JSON block from the verifier's last `TextBlock`, parse it, and emit a `verifier_verdicts` event over the websocket. The orchestrator can still narrate, but the briefing UI now has a structured ground truth of what the verifier said. If you want to be strict, also enforce: the orchestrator's final `publish_finding(verifier_status=...)` call must match the verifier's verdict for that BN, or the call gets rejected by `ui_bridge.py`. This is optional but gives you machine-checked safety.

**Verification.** Run the full prompt. The verifier returns REFUTED for any entity with a live agreement. The orchestrator never narrates "Challenged → Verified" for that entity. The briefing card shows REFUTED.

---

### D9 — `cra.govt_funding_by_charity` queries miss the impossibilities filter

**File:** `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md` Step E query (lines ~352-376); `zombie-agent/src/verifier.py` CHECK 6 (lines 76-96)

**Symptom.** Borderline. A charity-year row in `cra.govt_funding_by_charity` with a stray $5B-typo can poison the dependency ratio because `08-government-funding-analysis.js` does not pre-filter `cra.t3010_impossibilities` upstream. Step E in the skill correctly applies the filter at query time. CHECK 6 in the verifier correctly applies it. Confirm and keep.

**Root cause.** None — both currently apply the filter. This item is a regression-prevention guardrail rather than a fix. Worth calling out so future edits don't drop the filter.

**Action.** Add a short comment to both query sites:
```sql
-- DO NOT remove the t3010_impossibilities filter.
-- cra.govt_funding_by_charity is built without it (per CRA/scripts/advanced/
-- 08-government-funding-analysis.js); a $5B typo can flip the flag without it.
```

---

### D10 — Verifier embedded data-quirks rules drift from `data-quirks/SKILL.md`

**File:** `zombie-agent/src/verifier.py` lines 138-162

**Symptom.** The verifier cannot load skills (no `Skill` tool in its allow-list). The data-quirks rules it needs are embedded directly in the prompt. This was a deliberate workaround per the docstring at lines 9-13. But it means a future edit to `data-quirks/SKILL.md` will silently desync from the verifier's embedded copy. We are about to make D2 and D3 changes that affect this exact section.

**Action.** When you implement D2 and D3, mirror those changes into `verifier.py:138-162`. Specifically, the embedded note about `vw_agreement_current` / `vw_agreement_originals` (lines 142-145) is already correct — just confirm it stays correct. The line about "DISTINCT ON (ref_number)-only CTE" (lines 146-150) is correct. Do not re-introduce a contradiction.

**Verification.** Search both files for the string `vw_agreement_current`. The treatment must be consistent: "ships, use it" in both places.

---

## 6. Enhancements — do these after D1–D10

These do not fix correctness bugs. They make the demo dramatically better. All optional, but every one materially raises the score on Fit, Resilience, and Differentiation per the host rubric (`evaluations/01-zombie-recipients.md`).

### E1 — Per-entity dossier panel with three sub-views

**Driver.** Host evaluation `evaluations/01-zombie-recipients.md:35,41,65`: *"Visual demo path: per-entity dossier with three panels — funding events, dependence ratio time-series, status-after-funding banner."* Currently the UI only has a one-line briefing card per entity.

**Implementation sketch.**
- Add a `dossier` panel to `zombie-agent/ui/index.html`. It should render when the user clicks a VERIFIED briefing card.
- Three sub-panels:
  1. **Funding events timeline.** SQL: `SELECT agreement_start_date, agreement_end_date, agreement_value, owner_org_title, prog_name_en FROM fed.vw_agreement_current WHERE LEFT(NULLIF(recipient_business_number,''),9) = $1 ORDER BY agreement_start_date`. Render as a horizontal Gantt-ish strip with one bar per agreement.
  2. **Dependence-ratio sparkline.** SQL: `SELECT fiscal_year, govt_share_of_rev FROM cra.govt_funding_by_charity WHERE LEFT(bn,9) = $1 AND NOT EXISTS (SELECT 1 FROM cra.t3010_impossibilities ti WHERE ti.bn = govt_funding_by_charity.bn AND EXTRACT(YEAR FROM ti.fpe)::int = govt_funding_by_charity.fiscal_year) ORDER BY fiscal_year`. Render as a small line chart, with the 70% threshold drawn as a red dashed line.
  3. **Status-after-funding banner.** Big text. "Self-dissolved 2023-03-31 (T3010 line A2)" or "Stopped filing T3010 after FY2021" or "AB registry: Cancelled".
- The three queries should be exposed as a single `dossier` MCP tool that takes a BN and returns a JSON bundle. The agent calls it once when publishing a VERIFIED finding; the UI just renders.

**Out of scope.** Don't build interactive charts. SVG sparkline + text banner is enough for a 2-minute demo.

### E2 — "Two-minute story" headline per VERIFIED card

**Driver.** Host evaluation §"Fit" (`evaluations/01-zombie-recipients.md:40`): *"This $4.2M went to entity Y, which dissolved 9 months later and where federal grants made up 86% of revenue."*

**Implementation.** When the orchestrator calls `publish_finding(verifier_status="verified", ...)`, also include a `headline` field — a single sentence in that exact shape. Add the field to `ui_bridge.py:25-35` and render it in `ui/index.html` above the existing card body. Generate it from the orchestrator side; do not delegate to a separate model call.

Example for Canada World Youth: *"$3.07M in federal commitments 2018–2022 to a charity that self-dissolved in March 2023, on which government funding was 81% of revenue at the time."*

### E3 — "Universe panel" — show gate counts

**Driver.** Anchors the audience in methodology. Right now they see 5 candidates and have to take it on faith.

**Implementation.** Above the briefing cards, render: *"5 candidates surfaced from N BN-anchored federal recipients with cumulative commitment ≥ $1M (2018-2022); after live-agreement, foundation, and rebrand filters."* The number `N` comes from a sub-query that runs once at the start of Step A (`SELECT COUNT(*) FROM exposure`). Pass it through `publish_finding` as a top-level metadata field, not as part of any one card.

### E4 — Pre-materialise the candidate table

**Driver.** Run-to-run determinism. Even with D2–D4, the agent re-derives Step A every run and that's where prompt-engineering drift creeps in.

**Implementation.**
- Add a one-shot script `zombie-agent/scripts/build_candidate_table.py` that runs Step A SQL exactly as defined in `zombie-detection/SKILL.md` and inserts the results into a Postgres temp table or a JSONL file at `zombie-agent/.candidates_v1.jsonl`.
- Run it once at agent boot (or via `npm run build:candidates` analog).
- Update the skill's Step A to: "Step A is precomputed. Read the candidate list from `zombie-agent/.candidates_v1.jsonl` (or `SELECT FROM zombie_candidates_v1` if you went the temp-table route). Do not re-derive. The build script and SQL live at `scripts/build_candidate_table.py`."

This is the single biggest determinism win available, but it requires permissions to write to the DB (or to write a JSONL file). The team's DB credentials are read-only by default; the JSONL route is safer.

### E5 — Surface the "fewer than 5 verified candidates" case explicitly

**Driver.** D4 will make the candidate set smaller and more correct. Don't let the agent compensate by relaxing other gates.

**Implementation.** Update `system_prompt.py` to say:

```
If Step A (after all gates) returns FEWER than 5 candidates, that is the
correct answer — surface them all, then add a single non-card status line
in the briefing: "Step A surfaced N candidates passing all hard gates. The
methodology favours depth over breadth — see `zombie_agent_v3_correctness_
and_polish.md` §6 E5 for rationale." Do NOT relax gates to reach 5.

If Step A returns ZERO candidates, that is also a meaningful answer. Surface
the gate counts and explain which gate cleared the field. Do not reach for
non-charity recipients to pad.
```

### E6 — Reduce orchestrator sampling temperature

**Driver.** Even with D1–D5, two LLM calls on the same input may pick different phrasings. Lower temperature reduces this.

**Implementation.** The `claude-agent-sdk` exposes a temperature knob via `ClaudeAgentOptions`. Set the orchestrator to `temperature=0.0` (or as low as the SDK supports). The verifier's precedence rule from D1 is now deterministic regardless. Verify by reading `claude_agent_sdk/types.py` for the exact field name (it may be `temperature`, may be nested under `model_settings`).

### E7 — Pin the `Task`/`Agent` tool to avoid wasted ToolSearch turns

**Driver.** Every run burns 2-3 turns searching for the verifier-spawn tool. Saves ~30 seconds and reduces the chance the agent gives up and inlines the verification logic.

**Implementation.** This is environment-level, not code. Check whether `claude-agent-sdk` lets you pre-pin tool schemas at session start (look in `agent.py` `build_options`). If yes, pin `Task` and `Agent`. If no, leave alone.

### E8 — Integrate `cra.identification_name_history` into Step A

**Driver.** CHECK 7 (rebrand check) currently lives only in the verifier. Pulling it into Step A removes Ryerson→TMU-style rebrands at gate time, makes the verifier cheaper, and removes one source of AMBIGUOUS verdicts.

**Implementation.** Add a CTE to Step A:

```sql
rebranded AS (
  -- Charities that appear under multiple legal_name values across years —
  -- they renamed, they didn't cease.
  SELECT DISTINCT LEFT(bn,9) AS bn_root
  FROM cra.identification_name_history
  GROUP BY LEFT(bn,9)
  HAVING COUNT(DISTINCT legal_name) > 1
)
```

Add `LEFT JOIN rebranded r ON r.bn_root = e.bn_root` to the main SELECT. Add `AND r.bn_root IS NULL` to the WHERE.

### E9 — Add a "ghost capacity lead" sidebar for REFUTED entities with the specific zombie-but-live-agreement pattern

**Driver.** YMCA-KW and JobStart are *not* zombies, but they ARE legitimate accountability stories: a charity self-dissolves and a multi-year federal contract under that BN runs another 4 years unamended. That is Challenge 2 (Ghost Capacity) — and the host evaluation explicitly notes the demo could touch Ghost Capacity if the methodology surfaces it (`evaluations/01-zombie-recipients.md:78`).

**Implementation.** When the verifier REFUTES with `reason = "live federal agreement runs past 2024-01-01"` AND the entity also has `field_1570 = TRUE`, surface a separate small "Ghost Capacity lead" card on the briefing panel. Two-line: *"BN X self-dissolved on date Y but contract Z ran to 2025-03-31 unamended. Funding may be reaching a successor without formal novation."* Don't claim this is a zombie. Frame as a Ghost Capacity lead.

### E10 — Add a smoke test that runs the full prompt end-to-end

**File:** `zombie-agent/scripts/smoke_test.py` (already exists per `ls` output)

**Implementation.** Extend the existing smoke test to:
1. Boot the agent.
2. Submit the standard prompt 3× consecutively.
3. Collect the published findings from each run.
4. Assert: each run's set of VERIFIED BNs is identical. Each VERIFIED card's `total_funding_cad` is within 1% across runs. No "GHOST", "POLICE", "MUNICIPAL", "HOSPITAL", "UNIVERSITY", or "MINISTRY" in any entity name.
5. Print a diff table and exit non-zero if any of those fail.

This becomes the regression test for everything in D1–D10. Run before every demo.

---

## 7. Recommended patch order

Sequenced so each step is independently verifiable, and so you don't paint yourself into a corner.

| Step | Item | Time | Why this order |
|------|------|------|----------------|
| 1 | D5 — UI 100× fix | 1 min | Trivial. Eliminates the most visible defect immediately. Independent of every other change. |
| 2 | D2 — Skill contradiction about views | 2 min | One-line edit. Eliminates the $-amount drift on Canada World Youth. Independent. |
| 3 | D3 — Inline CTE ordering | 5 min | Defensive. Even after D2, if the agent ever falls back to the CTE, totals match. |
| 4 | D6 — Hook designation B | 1 min | One-line. Independent. |
| 5 | D9 — Impossibilities filter comment | 2 min | Documentation only. Future-proofs against regression. |
| 6 | D1 — Verifier precedence | 15 min | Bigger prose edit. Test by re-running prompt; verdict stability is the test. |
| 7 | D4 — Step A live-agreement filter | 10 min | Cuts the candidate set. Some entities (YMCA-KW, JobStart) drop out. This is intentional. |
| 8 | D7 — Non-charity exclusion regex | 15 min | Filters Indigenous police boards et al. After this, the candidate list should be stable across runs. |
| 9 | D10 — Mirror D2/D3 into verifier prompt | 5 min | Keep the verifier's embedded copy in sync. |
| 10 | D8 — Orchestrator REFUTED is final | 10 min | Prevents the "challenged → verified" override that 12pm run did. |
| 11 | E5 — "Fewer than 5 is fine" prose | 5 min | Tells the agent not to compensate for the smaller candidate set. |
| 12 | Run smoke test (E10 if not yet built, otherwise existing) | 5 min | First validation that D1–D10 are correct. |
| 13 | E2 — Two-minute story headline | 30 min | First demo polish item. Materially raises the Fit score. |
| 14 | E3 — Universe panel | 15 min | Anchors the audience. Cheap. |
| 15 | E1 — Per-entity dossier panel | 1–2 hr | Biggest demo lift. Save for last. |
| 16 | E6 — Temperature knob | 5 min | Minor determinism win. Do whenever. |
| 17 | E10 — Smoke test (extended) | 30 min | Regression safety net. Do whenever D1–D10 are stable. |
| Optional | E4, E7, E8, E9 | varies | All optional. E4 is the highest-impact. |

**Hard rule on this ordering.** Steps 1–11 are correctness; do them all before any of the enhancements. The smoke test (step 12) is your gate to enhancements.

---

## 8. Verification plan

Run all of these after the patch order above is complete. Failure on any item = revisit.

### 8.1 Determinism

Run the standard prompt 4 consecutive times. Each run must produce the same set of VERIFIED BNs. Each VERIFIED card's `total_funding_cad` must agree to within 1% across runs.

The standard prompt is:

> Find 3 federal grant recipients that look operationally dormant on the public record. Criteria: cumulative federal commitment ≥ $1M between 2018 and 2022 (use the agreement_current CTE pattern, not a naive SUM of fed.grants_contributions); no CRA T3010 filing in any year after their last grant when matched on the 9-digit BN root; no further federal grants since 2024-01-01; no Alberta grant payments in FY 2024-2025 or 2025-2026. For each surviving candidate, quantify total federal exposure (CAD), last-known year of activity, and government-share of operating revenue from the most recent CRA filing (filtered through cra.t3010_impossibilities so a stray five-billion-dollar typo does not pollute the ratio). Resolve every candidate through general.vw_entity_funding so the briefing names canonical entities, not aliases. Publish your top 3-5 candidates with verifier_status="pending" first, then delegate to the verifier subagent. Expect the verifier to REFUTE candidates that turn out to be designation A private foundations or whose T3010 filing window is still open — those refutations are the methodology working, not failing. For any candidate the verifier marks AMBIGUOUS, use the iterative-exploration loop (up to 3 follow-up SQL queries) to defend or revise before publishing the final verdict. Frame all output as audit leads worth a closer look — never as accusations.

### 8.2 Correctness — entity-level

Expected stable VERIFIED set (subject to live database state at demo time):

| Entity | BN | total_M | govt-dependency (most recent clean year) | Death signal |
|--------|----|---------|-------------------------------------------|---------------|
| Canada World Youth / Jeunesse Canada Monde | 118973999 | 3.07 | 81.2% (FY2022) | t3010_self_dissolution (fpe 2023-03-31) |
| Interagency Coalition on AIDS and Development | 864967922 | 1.99 | 86.4% (FY2021) | stopped_filing (last_fy 2021) |
| Learning Partnership Canada / Partenariat Canadien en Éducation | 140756107 | 2.64 | 13.5% (FY2022) — flag does not fire | t3010_self_dissolution + AB Cancelled |

If your live numbers differ by more than ~5%, investigate before declaring it a regression — partial 2024 data may have shifted slightly between runs. But the BN set must match.

Expected REFUTED-or-not-surfaced set:

| Entity | BN | Why |
|--------|----|-----|
| YMCA Kitchener-Waterloo / Three Rivers | 107572687 | CIC settlement agreement runs to 2025-03-31 |
| JobStart / WoodGreen Community Services | 106881139 | Three CIC agreements run to 2025-03-31 |
| Treaty Three Police Service Board | 870094018 | Police board — non-charity, non-zombie |
| Anishinabek Police Governing Authority | 140591710 | Police board — non-charity, non-zombie |

### 8.3 UI sanity

- govt-dependency reads as a single- or low-double-digit followed by a decimal (e.g. "81.2%"). Never four digits.
- No card text contains the words "fraud", "stole", "misappropriated", "criminal" — all `audit lead` language per system prompt rule.
- All VERIFIED cards include the headline sentence (E2) if you implemented it.

### 8.4 Skill internal consistency

```bash
# Both files must agree on view existence:
grep -n "vw_agreement_current" zombie-agent/src/workspace/.claude/skills/*/SKILL.md
grep -n "vw_agreement_current" zombie-agent/src/verifier.py
```
Should not contain the phrase "does NOT ship" or "does not exist" anywhere except in a comment that explicitly references this resolved issue.

### 8.5 No regression on the destructive-SQL hook

Run a smoke check that obviously-destructive SQL is still blocked:
```bash
# This should be blocked by safe_sql_hook:
echo "DROP TABLE foo" | python -c "import asyncio, src.hooks; asyncio.run(src.hooks.safe_sql_hook({'tool_input':{'sql':'DROP TABLE foo'}}, 'tid', None))"
```
Expected: a hook output with `permissionDecision: deny`.

### 8.6 Smoke-test command (after E10)

```bash
cd zombie-agent && uv run python scripts/smoke_test.py --runs 3 --strict
```
Must exit 0. Any non-zero is a regression.

---

## 9. Anti-patterns — do NOT do these

These all looked tempting at some point during the audit. Do not be tempted.

1. **Do NOT change `cra.govt_funding_by_charity` to be 0–1 instead of 0–100 to "fix" the UI bug.** The CRA build script writes percent units. Multiple downstream consumers depend on that. Fix the UI (D5).
2. **Do NOT relax Step A gates to keep the candidate count at 5.** The methodology is supposed to surface fewer-but-cleaner cases. The host evaluation prefers depth.
3. **Do NOT remove the 2018–2022 commitment window from Step A.** That window exists so the agent can observe ≥1.5 years of post-grant behaviour. Removing it lets 2023-funded entities into the candidate set where "no_post_grant_activity" is meaningless.
4. **Do NOT compute `total_funding_cad` from `general.vw_entity_funding` or by aggregating across `general.entity_source_links`.** Both inflate the figure by including predecessor entities and pre-BN name variants. The Acadia Centre lesson: $0.88M true → $6.65M aggregate. The Northwest Inter-Nation lesson: $11.7M true → $101.79M aggregate. **BN-anchored `fed.vw_agreement_current` is the only correct source.** This is documented in `zombie-detection/SKILL.md:96-104` already; preserve it.
5. **Do NOT bypass `safe_sql_hook` even temporarily** to "test something quickly." The hook is a hard rule and the database is read-only by policy. If a query is being false-positive blocked (the 1230 trace shows the agent thinking this happened), the right fix is to refine the regex in `hooks.py`, not bypass it.
6. **Do NOT add new MCP servers** in scope of this work. The two existing ones (postgres + ui_bridge) are sufficient. New servers add init time and surface-area for new failure modes.
7. **Do NOT switch the orchestrator to a different model.** Sonnet 4.6 is what was tested. Switching to Haiku or to an OpenAI model invalidates every behavioral observation in this document.
8. **Do NOT modify `CLAUDE.md`, `KNOWN-DATA-ISSUES.md`, or any of the per-module `CLAUDE.md` files.** Those are authoritative and shared with the rest of the hackathon team.
9. **Do NOT modify any `CRA/`, `FED/`, `AB/`, `general/` source.** Out of scope.
10. **Do NOT add "fraud" / "criminal" vocabulary anywhere.** The agent's framing rule (system prompt, top of file) is non-negotiable and the host evaluates on it.
11. **Do NOT auto-publish the dossier panel for REFUTED entities.** Only VERIFIED gets the dossier. REFUTED gets a small note explaining the refutation reason. Showing a full dossier for a refuted entity confuses the audit lead with the audit conclusion.
12. **Do NOT extend `max_turns` past 60.** The current value (`agent.py:123`) is already generous. If a run is hitting the cap, the right answer is to reduce wasted turns (E7), not raise the cap.

---

## 10. Background reading order (for the next session)

If the next session picks this up cold, read in this order:

1. `CLAUDE.md` (root) — repo orientation.
2. `evaluations/01-zombie-recipients.md` — the host's rubric.
3. `zombie-agent/README.md` — current agent shape.
4. `zombie-agent/src/system_prompt.py` — what the orchestrator believes.
5. `zombie-agent/src/verifier.py` — what the verifier believes.
6. `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md` — the methodology.
7. `zombie-agent/src/workspace/.claude/skills/data-quirks/SKILL.md` — the dataset defects.
8. `zombie-agent/src/workspace/.claude/skills/accountability-investigator/SKILL.md` — the master playbook.
9. `FED/CLAUDE.md` — the FED dataset's quirks (the F-1 / F-3 / F-9 issues are critical).
10. `CRA/CLAUDE.md` — the CRA dataset's quirks (especially designation A/B/C).
11. `KNOWN-DATA-ISSUES.md` — the full catalogue.
12. This document.

After that, read the four PDF traces (already converted to text at `/tmp/zombie_traces/*_nl.txt`) — at minimum skim Run11pm and 12pm side by side to see the verdict drift on YMCA-KW first-hand. That's the most concrete grounding you can get in the actual failure mode.

---

## 11. Done criteria

This work is "done" when all of the following are true:

- [ ] All D1–D10 patches landed.
- [ ] Section 8.1 (Determinism) passes 4-of-4 runs.
- [ ] Section 8.2 (Correctness) — the expected VERIFIED set is the actual VERIFIED set on every run.
- [ ] Section 8.3 (UI sanity) — no four-digit dependency percentages, no accusation language.
- [ ] Section 8.4 (Skill consistency) — `grep` checks pass.
- [ ] Section 8.5 (Hook regression) — destructive SQL still blocked.
- [ ] At minimum E2 (two-minute story headline) and E3 (universe panel) shipped.
- [ ] At least one full demo run-through done end-to-end against a live audience or a teammate playing audience.

If you are unsure whether you are done, you are not done. The default is "keep verifying" — the cost of one more 4-run determinism check is minutes; the cost of a flaky demo on stage is the entire submission.

---

*End of document.*
