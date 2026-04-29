# Zombie Agent — CORP + PA Implementation Prompt (standalone)

> Hand this file to a new session. It is self-contained: read the referenced
> files, then make the exact changes listed in §5 and verify per §6.

## 1. Context

You are implementing two new evidence sources into an existing, working
investigative agent: the federal Corporations Canada registry (`corp` schema)
and the audited Public Accounts of Canada transfer payments (`pa` schema). The
agent investigates Challenge 1 — Zombie Recipients — for a hackathon demo on
2026-04-29. Audience is federal/provincial Ministers and Deputies.

**Read these files first, in this order, before touching code:**

1. `CLAUDE.md` (repo root) — schema layout, the FED/CRA/AB/general data
   quirks that already trip queries, what "BN root" means, conventions.
2. `challenges.md` — Challenge 1 text (the literal CHL the agent
   operationalizes).
3. `KNOWN-DATA-ISSUES.md` (repo root) — catalogued data-quality issues
   across all schemas; cross-reference any anomaly here before assuming
   it's a bug.
4. `plans/zombie_agent_v3_correctness_and_polish.md` — the correctness
   baseline. Almost all of this is **already implemented** (see §3 below).
   Read §5 D1, D4, D6, D7, D8 closely; you must not regress any of them.
5. `plans/zombie_agent_corp_pa_addendum.md` — the design proposal for CORP
   and PA. **Do not implement it verbatim.** §5 of this prompt lists the
   four corrections you must apply on top.
6. `plans/zombie_agent_lobby_addendum.md` — pre-existing addendum that
   adds a 5th probe (lobby registry). Already integrated. You do not
   need to change it; just be aware references to "probe 5" / "lobby"
   in code or comments are not stale.
7. `CORP/CLAUDE.md` and `PA/CLAUDE.md` — schemas, tables, gotchas.
   `CORP/sql/01-schema.sql` and `PA/sql/01-schema.sql` are the canonical
   DDL if you need exact column types.
8. `zombie-agent/src/verifier.py` (the `VERIFIER_PROMPT` constant — note
   it is a Python concatenated string literal, not a multiline triple
   string; preserve the concatenation style) and
   `zombie-agent/src/system_prompt.py` — current orchestrator + verifier
   prompts.
9. `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md`
   — Step A enumeration query, dossier query bundle.
10. `zombie-agent/src/workspace/.claude/skills/data-quirks/SKILL.md` and
    `zombie-agent/src/workspace/.claude/skills/accountability-investigator/SKILL.md`
    — referenced by the orchestrator at run time. Read them so your
    changes don't contradict an existing rule embedded in either skill.
11. `zombie-agent/src/run_manager.py` — defines the `ZOMBIE_QUESTION`
    canonical question used by `POST /api/run`. The verification runs in
    §6 invoke this same question.
12. `zombie-agent/src/mcp_servers/ui_bridge.py` — `publish_finding`,
    `publish_universe`, `publish_dossier` schemas you will extend.

Do NOT edit `plans/zombie_agent_corp_pa_addendum.md`, the CLAUDE.md files,
the v3 plan, or the lobby addendum. The addendum is a design document;
treat it as read-only specification with the four corrections in §5 below
applied.

## 2. Goal

Add CORP and PA as two new evidence sources to the verifier subagent and the
finding/dossier surfaces. Convert the demo's narrative posture from
"absence of evidence" (T3010 silence + no recent FED activity) to
"evidence of death" (federal corporate registry confirms dissolution + audited
Public Accounts confirms cash never moved).

Concrete acceptance: on a fresh run of the canonical question against the
local Docker database with both schemas loaded, the SDTC case (BN 881292817 →
Canada Foundation for Sustainable Development Technology) should either (a)
verify cleanly with CORP `Dissolved 2025-03-31` cited as primary evidence and
PA-empty cited as secondary, OR (b) refute as a zombie and emit as a Ghost
Capacity lead per v3 §E9 if a live agreement disqualifies it. Both are correct
outcomes; which one fires depends on Step A's live-agreement gate at run time.

## 3. v3 baseline — already in code; DO NOT regress

The following items from `plans/zombie_agent_v3_correctness_and_polish.md`
are already implemented. Re-run against the code before you change anything
to confirm. The acceptance test in §6 will catch regressions on these.

| v3 item | Current location | Invariant you must preserve |
|---|---|---|
| D1 — Verifier precedence chain | `verifier.py` PRECEDENCE block ("FIRST match wins") | The 9-step ordering. You will *insert* new checks; you must not reorder existing ones. |
| D4 — Step A live-agreement gate | `zombie-detection/SKILL.md` `NOT EXISTS (... agreement_end_date >= '2024-01-01' AND end_date >= start_date)` | Step A still rejects entities with any agreement extending into 2024+. CORP signal does not override this. |
| D6 — Designation A and B excluded | `hooks.py` inject_context_hook + `zombie-detection/SKILL.md` foundation filter | Foundations stay excluded; CORP probe does not bring them back. |
| D7 — Non-charity exclusion regex | `zombie-detection/SKILL.md` POLICE / FIRST NATION / UNIVERSITY / HOSPITAL regex on the `no_post_grant_activity` branch | Still applies; CORP match does not override the regex. |
| D8 — REFUTED is final | `system_prompt.py` "A REFUTED verdict from the verifier is FINAL" | The orchestrator must not promote REFUTED → VERIFIED via iterative-exploration even when CORP says Dissolved. Such cases become Ghost Capacity leads (v3 §E9). |
| E1/E2/E3 — Dossier, templated headlines, universe panel | `mcp_servers/ui_bridge.py` + `system_prompt.py` Step H5 | Existing tools and templates remain canonical. New CORP/PA fields are *additions*, not rewrites. |
| E5 — "Fewer than 5 candidates is fine" | `system_prompt.py` | Adding CORP+PA must not pad the candidate count. The deterministic Step A is still the single point of candidate selection. |

**Determinism contract (v3 §D1 + system_prompt.py).** Same DB state → same
candidate list and same ordering every run. Final briefing order is
**total_funding_cad DESC among VERIFIED candidates only**. Do not introduce
any sort, tie-break, or filter that depends on CORP or PA signals to
change the candidate ordering.

## 4. Operational prerequisites

Before code changes, verify the local DB has both schemas loaded:

```bash
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon -c \
  "SELECT 'corp' AS s, COUNT(*) FROM corp.corp_corporations
   UNION ALL SELECT 'pa', COUNT(*) FROM pa.transfer_payments;"
```

Expect `corp ~1559761`, `pa ~144570`. If `pa` is missing, run from the
repo root:

```bash
cd PA && npm install && npm run setup    # ~10s
```

If `corp` is missing, see `CORP/CLAUDE.md` for the OPEN_DATA_SPLIT.zip
prerequisite (~5min).

The agent's `READONLY_DATABASE_URL` (in `zombie-agent/.env`) must point at
the **local** DB, not Render. CORP and PA are local-only schemas. Verify
the URL host is `localhost` before continuing. If it's Render, do not
proceed — the demo target DB needs to be decided first.

## 5. Required changes

These are the changes to merge. Apply each one and run the §6 verification
after every two or three changes.

### 5.1 — Verifier precedence: insert four new CHECKs

File: `zombie-agent/src/verifier.py`. Modify the PRECEDENCE block
("apply checks in THIS ORDER per candidate; the FIRST match wins") to
insert the new checks at exactly these positions:

```
 1. CHECK 5  (vw_agreement_current total < $1M)                  → REFUTED
 2. CHECK 0  (designation A or B)                                → REFUTED
 3. CHECK 9  (CORP status 1 Active AND last_annual_return_year
              >= grant_end_year - 1)                             → REFUTED
 4. CHECK 9b (CORP status 9 Amalgamated)                         → REFUTED
 5. CHECK 1  (T3010 filing window still open)                    → REFUTED
 6. CHECK 7  (entity rebranded — identification_name_history)    → REFUTED
 7. CHECK 2b (FED agreement_end_date >= 2024-01-01 AND
              end_date >= start_date)                            → REFUTED
 8. CHECK 3  (any AB payment > 0 in FY2024-25 / FY2025-26)       → REFUTED
 9. CHECK 10 (PA shows aggregate_payments > 0 AND
              last_year >= current_year - 1)                     → REFUTED
10. CHECK 11 (CORP status 11 Dissolved OR status 3 Dissolution
              Pending - Non-compliance, AND temporal gate fires) → VERIFIED
11. CHECK 8  (field_1570 = TRUE)                                 → VERIFIED
12. CHECK 12 (PA empty across all loaded FYs AND
              agreement_value >= $100K AND
              agreement_start_date <= today - 12mo)              → VERIFIED
13. CHECK 6  (govt_share_of_rev < 70 on most recent clean filing) → AMBIGUOUS
14. otherwise (death signal fired AND nothing above triggered)   → VERIFIED
```

Then add the bodies of CHECK 9, 9b, 10, 11, 12 to the prompt's "MANDATORY
checks" section. Use the exact SQL skeletons in §5.2 below. The bodies
must include three explicit guards documented inline:

**CHECK 9 — CORP-Active short-circuit (REFUTED).**
```
SELECT current_status_code, last_annual_return_year, current_status_date::date
  FROM corp.corp_corporations
 WHERE business_number = $1::text   -- 9-digit BN root
 LIMIT 1;
-- Inputs: $1 = bn_root (9 digits), $2 = grant_end_year (int) supplied by
--         orchestrator from MAX(agreement_end_date) over vw_agreement_current.
-- Fire REFUTED only when current_status_code = 1 AND
--   last_annual_return_year >= ($2::int - 1).
-- "No row" is SILENT, not REFUTED — many real recipients are not federally
--   incorporated (provinces, sole props, foreign entities, WE Charity
--   Foundation). Continue down the precedence chain.
```

**CHECK 9b — Amalgamated (REFUTED).**
```
SELECT current_status_code, current_status_date::date AS amal_date
  FROM corp.corp_corporations
 WHERE business_number = $1::text
   AND current_status_code = 9   -- Inactive - Amalgamated
 LIMIT 1;
-- Fire REFUTED with reason "federal corporation amalgamated on {amal_date};
--   chase the successor (corp_status_history activity code 4)". Do NOT
--   verify zombie on an amalgamated entity. The successor is alive even
--   if a final field_1570=TRUE filing exists.
```

**CHECK 10 — PA recent payment (REFUTED).**
```
SELECT MAX(rt.last_year) AS last_year, rt.total_paid::bigint AS total_paid
  FROM pa.vw_recipient_totals rt
 WHERE rt.recipient_name_norm = $1   -- normalized FED legal_name
   AND rt.last_year >= EXTRACT(YEAR FROM CURRENT_DATE)::int - 1
 GROUP BY rt.total_paid
 LIMIT 1;
-- Inputs: $1 = lower(regexp_replace(regexp_replace(legal_name,
--   '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'))
-- Fire REFUTED only when a row is returned (recent recipient-detail
--   payment > 0). Cite the year and amount.
-- Bilingual FED names: if recipient_legal_name contains '|', split on
--   '|' and try both halves before concluding "no match".
```

**CHECK 11 — CORP-Dissolved/Pending (VERIFIED) WITH TEMPORAL GATE.** This
is the highest-risk check. Get this exact form right:

```
WITH corp_match AS (
  SELECT current_status_code, current_status_label,
         current_status_date::date AS status_date,
         dissolution_date::date     AS diss_date
    FROM corp.corp_corporations
   WHERE business_number = $1::text
     AND current_status_code IN (3, 11)
   LIMIT 1
),
fed_window AS (
  SELECT MIN(agreement_start_date)::date AS first_grant,
         MAX(agreement_end_date)::date   AS last_grant
    FROM fed.vw_agreement_current
   WHERE LEFT(NULLIF(recipient_business_number, ''), 9) = $1::text
)
SELECT cm.current_status_code, cm.current_status_label,
       cm.status_date, cm.diss_date,
       fw.first_grant, fw.last_grant
  FROM corp_match cm, fed_window fw
 WHERE
   -- Temporal gate: dissolution must be AFTER the first grant, OR within
   -- 24 months before the latest agreement_end_date. Rejects BN-reuse
   -- false positives where a corp dissolved decades before any FED
   -- activity (Kinectrics-shape: BN 864020920 has Dissolved row from
   -- 1989-08-31 sharing a BN with three living successor corps).
   COALESCE(cm.diss_date, cm.status_date) >= GREATEST(
     fw.first_grant,
     fw.last_grant - INTERVAL '24 months'
   )::date;
-- Fire VERIFIED only when this query returns a row. If corp_match
-- has a row but the temporal gate excludes it, emit AMBIGUOUS with reason
-- "registry dissolution predates FED grants — possible BN reuse or
-- successor entity; manual review needed".
```

**CHECK 12 — PA empty (VERIFIED).**
```
SELECT 1
  FROM pa.vw_recipient_totals rt
 WHERE rt.recipient_name_norm = $1
 LIMIT 1;
-- Fire VERIFIED only when:
--   (a) this query returns ZERO rows, AND
--   (b) the orchestrator's claimed agreement_value >= 100000, AND
--   (c) the agreement_start_date <= CURRENT_DATE - INTERVAL '12 months'.
-- If any condition fails, CHECK 12 is silent — fall through to CHECK 6.
-- Bilingual handling per CHECK 10.
```

In the verifier prompt body, after the existing "DATA QUIRKS YOU MUST
RESPECT" section, append:

```
- CORP and PA absence rules:
  * No CORP match → SILENT (do not refute; many recipients are not
    federally incorporated).
  * No PA match alone → not VERIFIED unless CHECK 12 pre-conditions
    (agreement_value >= $100K AND signed > 12mo ago) all hold.
  * CORP business_number is the 9-digit BN root, NOT the 15-char CRA BN.
    Always pass LEFT(bn,9) when joining.
- pa.transfer_payments row-type column-flip: filter
  `recipient_name_location IS NOT NULL` and use `aggregate_payments` for
  recipient-detail rows. `pa.vw_recipient_totals` already does this.
- Bilingual recipient names: split FED legal_name on '|' and try both
  halves against PA before concluding "no match".
```

### 5.2 — Skill: Step A pre-enrich (NO reorder)

File: `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md`.

In the Step A query, add two LEFT JOINs and two output columns. **Do not
add any WHERE clause that uses the new columns. Do not change ORDER BY.**
The candidate list and its ordering remain governed solely by the existing
gates and `total_committed_cad DESC`.

Add to the FROM/JOIN block:

```sql
LEFT JOIN corp.corp_corporations cc
       ON cc.business_number = e.bn_root
LEFT JOIN pa.vw_recipient_totals pt
       ON pt.recipient_name_norm = lower(
            regexp_replace(regexp_replace(e.recipient_name,
              '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'))
```

Add to the SELECT list (anywhere, after `months_grant_to_death_signal`):

```sql
  cc.current_status_code   AS corp_status_code,
  cc.current_status_label  AS corp_status_label,
  cc.dissolution_date::date AS corp_dissolution_date,
  cc.last_annual_return_year AS corp_last_filing_year,
  pt.last_year             AS pa_last_year,
  pt.total_paid::bigint    AS pa_total_paid_cad
```

Document a single sentence above the SELECT: *"CORP and PA columns are
attached as evidence for the verifier and the dossier panel; they do not
participate in candidate selection or ordering (see system_prompt.py
determinism contract)."*

**Do NOT implement** the addendum's §5 "Step B sweetening" composite
`dual_signal DESC` re-ranking. That block conflicts with the determinism
contract. The §5 "Step A pre-enrich" path described above is sufficient.

### 5.3 — Dossier sub-views 4 and 5

File: `zombie-agent/src/workspace/.claude/skills/zombie-detection/SKILL.md`.

Add two new dossier-bundle queries (H4a and H4b — keep H4 / H5 / H6
unchanged):

**H4a — CORP timeline.** Run only if Step A returned a non-null
`corp_status_code` for this BN.

```sql
-- Step H4a: corp registry timeline
SELECT 'status'::text AS kind, status_label AS label,
       effective_date::date AS event_date, is_current
  FROM corp.corp_status_history
 WHERE corporation_id = $1
UNION ALL
SELECT 'name', name, effective_date::date, is_current
  FROM corp.corp_name_history
 WHERE corporation_id = $1
 ORDER BY event_date DESC, kind;
```

`corporation_id` is found via `SELECT corporation_id FROM
corp.corp_corporations WHERE business_number = $1 LIMIT 1` — store from
Step A's enriched row to avoid an extra lookup.

**H4b — PA cash trajectory.** Run only if Step A returned a non-null
`pa_last_year` for this BN.

```sql
-- Step H4b: per-fiscal-year PA payments
SELECT fiscal_year_end, department_name, aggregate_payments::bigint AS paid_cad
  FROM pa.transfer_payments
 WHERE recipient_name_norm = $1
   AND recipient_name_location IS NOT NULL
 ORDER BY fiscal_year_end;
```

Pass results to `publish_dossier` as new fields `corp_timeline` (list of
dicts) and `pa_payments` (list of dicts). Both default to empty list when
no enriched data is available.

### 5.4 — Extend ui_bridge MCP tool schemas

File: `zombie-agent/src/mcp_servers/ui_bridge.py`.

Extend `publish_finding` to accept these optional fields (preserve all
existing fields, do not require any new ones):

```
corp_status_code       : int | None
corp_status_label      : str | None
corp_status_date       : str | None    # ISO date
corp_dissolution_date  : str | None    # ISO date
pa_last_year           : int | None
pa_total_paid_cad      : int | None
```

Extend `publish_dossier` to accept these optional fields:

```
corp_timeline   : list[dict] | None    # rows from H4a, default []
pa_payments     : list[dict] | None    # rows from H4b, default []
```

When CORP/PA fields are absent, the tool must accept the call as
unchanged-from-baseline (no error, no different routing). The UI handles
absence by hiding the corresponding chip / sparkline.

### 5.5 — System prompt: brief CORP/PA awareness

File: `zombie-agent/src/system_prompt.py`.

Add one short paragraph in the "How to delegate" section, after the
existing verifier description, exactly:

```
The verifier now also probes the federal corporate registry (corp schema)
and the audited Public Accounts (pa schema). These are local-only
schemas. CORP confirms or refutes federal incorporation status; PA
confirms or refutes that cash actually flowed. Both attach evidence to
the existing finding card — they do not change candidate selection or
ordering. A REFUTED verdict citing CHECK 2b (live federal agreement)
remains REFUTED even when CORP says Dissolved; surface that combination
as a Ghost Capacity lead per the existing §E9 path, not as a zombie.
```

Do **not** rewrite the framing rule, the explainability bar, or the
"Hard rules" block.

### 5.6 — Bump max_turns

File: `zombie-agent/src/agent.py`.

Change `max_turns=60` to `max_turns=80`. The two new mandatory CHECKs
per candidate add ~10 verifier turns across the typical 3–5 candidate
set; the live-agreement defense via Ghost Capacity adds another 5–10.
Comment the change inline:

```
# 80 absorbs the two new mandatory CORP/PA probes per candidate plus the
# Ghost Capacity sidebar emission. v3 anti-pattern #12 prohibits going
# above 60 to mask wasted turns; this raise is justified by new
# functionality, not waste.
```

### 5.7 — UI updates (optional, do last)

Files: `zombie-agent/ui/index.html` and `zombie-agent/dashboard/index.html`.

Add two render hooks below the verifier verdict pill on each finding card:
- A colored chip for `corp_status_label` (red for "Dissolved", orange for
  "Active - Dissolution Pending (Non-compliance)" / "Active - Intent to
  Dissolve Filed", gray for other inactive labels). Hide when the field
  is absent or `corp_status_code = 1` (Active).
- A 6-bar sparkline for PA payments by fiscal year, where bar height is
  proportional to `aggregate_payments` and empty bars are styled gray.
  Hide entirely when both `corp_status_code` is null and `pa_payments` is
  empty AND the finding's `agreement_value < 100000` (PA absence is not
  a signal below the threshold).

UI changes are demo polish; they must not break the layout when the new
fields are absent. Skip if time is short.

## 6. Verification — run after every two or three changes

### 6.1 — Smoke test passes

```bash
cd zombie-agent
uv run python scripts/smoke_test.py
```

Both probes (orchestrator + verifier) must pass against the local DB.

### 6.2 — Regression invariants from v3

Run the canonical investigation. Two equivalent invocation paths:

```bash
# Option A — start the FastAPI server, then trigger the canonical question
# in the background. The dashboard auto-triggers this on page load.
cd zombie-agent
uv run uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
# In another terminal:
curl -s -XPOST http://127.0.0.1:8080/api/run
# Then watch the live trace at http://127.0.0.1:8080/dashboard
# Or, after completion, the static report at http://127.0.0.1:8080/report

# Option B — drive directly via the websocket /ws endpoint with the
# ZOMBIE_QUESTION constant from src/run_manager.py:18 (kept verbatim;
# do not paraphrase — the question text is part of the determinism
# contract). See ui/index.html for the websocket message shape.
```

Verify against the `/report` HTML or the live websocket trace:

| Invariant | Source | Pass criterion |
|---|---|---|
| YMCA-KW (BN 107572687) is REFUTED | v3 §D4 | Verdict REFUTED with reason "live federal agreement runs past 2024-01-01" |
| JobStart Hamilton (BN 106881139) is REFUTED | v3 §D4 | Same as above |
| Canada World Youth (BN 118973999) total_M = 3.07 | v3 §D2/§D3 | Briefing card shows ~$3.07M, not $39.87M |
| REFUTED is final | v3 §D8 | No briefing card narrates "challenged → verified" on a CHECK 2b REFUTED |
| Foundations excluded | v3 §D6 | No designation A or B charity appears in the candidate list |
| Final ordering | system_prompt.py L83-84 | Cards sorted by `total_funding_cad` DESC; no card with smaller funding ahead of a larger one even if its CORP signal is stronger |

### 6.3 — New CORP/PA correctness

| Test | Pass criterion |
|---|---|
| SDTC (BN 881292817) | Verifier walk shows CHECK 11 fires (status 11 Dissolved 2025-03-31, temporal gate satisfied) OR CHECK 2b fires (live agreement → REFUTED + Ghost Capacity lead). Whichever fires, CORP fields appear on the card. PA-empty cited as secondary if CHECK 11 fires. |
| Pre-grant-dissolution false-positive guard (CHECK 11 temporal gate) | Use BN `864020920`. This BN has a real `corp.corp_corporations` Status 11 row for `CENTRE DE DIAMANTS ET DE BIJOUX D'HERITAGE S. & L. INC.` dissolved `1989-08-31`; the same BN was reassigned to Kinectrics Inc. (active, three living successor corps in CORP). FED has >$1M of post-2018 grants on `LEFT(recipient_business_number,9) = '864020920'`. The pre-corrected CHECK 11 returns the dissolved diamond shop and would VERIFY a $8M zombie. The corrected CHECK 11 (with the temporal gate) must return zero rows for this BN. Verify by running the CHECK 11 SQL from §5.1 directly with `$1 = '864020920'` and confirming an empty result. |
| Status 9 (Amalgamated) → REFUTED | Discovery query: `SELECT cc.business_number, cc.current_name FROM corp.corp_corporations cc WHERE cc.current_status_code = 9 AND cc.business_number IN (SELECT LEFT(recipient_business_number,9) FROM fed.grants_contributions WHERE recipient_business_number ~ '^[0-9]' GROUP BY 1 HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 1000000) LIMIT 5;`. Pick any returned BN. Verifier must REFUTE with reason citing amalgamation, even if `cra.cra_financial_general.field_1570 = TRUE` exists on a final filing. |
| No-CORP-match silent | A provincially-incorporated charity will not appear in `corp.corp_corporations`. WE Charity Foundation is one such case (no row in CORP; the federal corporate registry covers CBCA / NFP-Act / Boards-of-Trade / coops only — see `CORP/CLAUDE.md`). Find a candidate's 9-digit BN root and confirm `SELECT 1 FROM corp.corp_corporations WHERE business_number = '<bn>'` returns zero rows. Verifier must not REFUTE on CHECK 9 / 9b / 11 for this candidate; the chain falls through to the existing v3 checks. |
| PA-empty signal-conditional | Pick a BN with FED `agreement_value < $100K`. CHECK 12 must NOT fire (silent). |
| PA-empty fires when load-bearing | Pick a BN with FED `agreement_value >= $100K`, `agreement_start_date < current_date - 12mo`, and no `pa.vw_recipient_totals` row. CHECK 12 fires VERIFIED. |
| Bilingual name handling | Pick a FED row where `recipient_legal_name` contains `\|`. Verifier tries both halves against PA before deciding. |

### 6.4 — Determinism

Run the canonical question 4 times back-to-back. The set of VERIFIED BNs
must be identical across all 4 runs (modulo the documented stochastic
risk: a candidate near the live-agreement boundary may flip between
zombie and Ghost Capacity lead between runs only if FED data changes —
which it should not within a session). The ORDER of cards must be
identical in all 4 runs.

### 6.5 — UI does not break on absent fields

Disable the new probes temporarily (comment out the LEFT JOINs in Step A)
and run once. The UI must still render correctly with no CORP chips and
no PA sparklines. Re-enable before committing.

## 7. What NOT to do

- Do not re-rank the candidate list by `dual_signal` or any composite of
  CORP/PA signals. The addendum's §5 "Step B sweetening" block is
  rejected. Use only §5 "Step A pre-enrich".
- Do not add new gates to Step A based on CORP or PA. Step A's gate set
  is locked by v3 §D1/§D4. CORP and PA are evidence, not selectors.
- Do not promote any REFUTED verdict to VERIFIED via the
  iterative-exploration loop, even when CORP shows Dissolved. v3 §D8.
- Do not change the templated headline format strings (Step H5). Add
  the CORP/PA evidence lines as supplementary text on the dossier or in
  `evidence_summary`, not in the headline template.
- Do not drop the existing v3 invariants in §3 above. If a change you
  make would weaken any of them, stop and ask for clarification.
- Do not add a CORP/PA-specific death-signal to Step A's CASE expression.
  The death-signal taxonomy in `zombie-detection/SKILL.md` is the
  contract; CORP and PA are verifier-side evidence, not Step A signals.
- Do not commit changes without running the §6 verification.

## 8. Suggested commit sequence

One PR per logical change. Each must pass §6.1 + §6.2 before the next is
applied:

1. 5.4 (ui_bridge schema extensions, additive only) — landed first because
   subsequent commits depend on the new optional fields.
2. 5.2 (Step A pre-enrich columns) — additive, no behavior change yet.
3. 5.3 (dossier sub-view queries) — additive.
4. 5.1 (verifier precedence inserts) — this is the behavior change.
   Run §6.2 + §6.3 thoroughly here.
5. 5.5 + 5.6 (system prompt blurb + max_turns bump) — small.
6. 5.7 (UI) — last, optional.

## 9. Out of scope (do not implement)

- The addendum's §11 post-hackathon paths (entity-resolution integration,
  trigram fuzzy match, PA fiscal-year backfill, PA contracts).
- A separate `publish_ghost_lead` MCP tool. Existing v3 §E9 path —
  emitting Ghost Capacity leads through the existing finding card with
  `verifier_status="refuted"` and a Ghost Capacity hand-off line in
  `evidence_summary` — is sufficient for the demo. A dedicated sidebar
  tool can land later.
- Routing through `general.entity_golden_records` for PA name fallback.
  The bilingual `|` split in CHECK 10 / CHECK 12 is the agreed minimum.
  Higher-recall name resolution is post-hackathon.
- Anything in the addendum's §5 "Step B sweetening" block.
- Loading PA data on the Render database. CORP and PA are local-only.

If you find yourself wanting to do any of these to make the implementation
cleaner, stop and surface the concern instead of doing it.
