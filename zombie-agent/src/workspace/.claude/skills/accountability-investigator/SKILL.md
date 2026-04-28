---
name: accountability-investigator
description: Master playbook for investigating any Canadian government accountability question against the CRA + FED + AB Postgres database. Use this skill at the start of every question; load challenge-specific recipes (zombie-detection, loop-detection, etc.) on top.
---

# Investigation methodology

Every question follows the same shape: decompose, query broadly, narrow,
resolve to canonical entity, verify, publish.

## 1. Decompose
Restate the user's question as a list of 3-7 SQL questions in plain English.
Do not write SQL yet. Examples:
- "Federal recipients ≥ $1M between 2018-2022 — who are they?"
- "Of those, which still file T3010 in 2024?"
- "Of the rest, which have any Alberta corporate registry presence?"

## 2. Load data-quirks before any SQL
The `data-quirks` skill lists the defects that will silently fool you. Always
read it before writing your first query. The big four for cross-dataset
questions:
- `fed.grants_contributions.agreement_value` is **cumulative** across
  amendments. Never naïvely `SUM` the base table. Either filter
  `WHERE is_amendment = false` (originals-only approximation), or use the
  inline `agreement_current` CTE pattern documented in `data-quirks`. The
  database does NOT ship with `vw_agreement_current` /
  `vw_agreement_originals` views; do not reference them.
- Filter `cra.t3010_impossibilities` from any CRA financial aggregation.
- Names drift. Always resolve through `general.entity_golden_records` or
  `general.vw_entity_funding`.
- BNs come in multiple formats. Group by `LEFT(bn, 9)` not the 15-character
  string.

## 3. Run queries sequentially
Each query is visible to the user. Begin every `mcp__postgres__execute_sql`
call with a short comment-style English label on the first line:
`-- Step 3: count CRA filings in 2024 for the candidates above`. The hooks
add this to the activity panel.

Always include a LIMIT on exploratory queries unless you are aggregating.

## 4. Resolve to canonical entity
Once you have a candidate list of names or BNs, join through
`general.vw_entity_funding` so you are reasoning about one canonical org per
entity, not a name string that might appear 10 different ways across CRA +
FED + AB.

## 5. Identify candidates and publish (status pending)
Pick your top 3-5 candidates by the question's primary metric. For each,
call `mcp__ui_bridge__publish_finding` with `verifier_status="pending"`. The
briefing panel will show pending cards.

## 6. Delegate to the verifier
Use the `Task` tool with `subagent_type="verifier"`. Pass the candidate list
with their canonical names, BNs, and the primary claim. Wait for the
verdicts.

## 7. Update findings with verdicts
For each candidate, call `publish_finding` again with
`verifier_status="verified"`, `"refuted"`, or `"challenged"` and the
verifier's evidence. For AMBIGUOUS verdicts, mark the card `"challenged"`,
run up to 3 follow-up SQL queries to defend or revise, then update one final
time.

## 8. Final user response
Three to five sentences summarizing what was found and pointing the user to
the briefing panel for details. Do not restate the dossier in chat — the
panel is the deliverable. Use audit-lead language, not accusation language.

# Hard rules
- Never invent a number. Every numeric claim has a SQL query in this session
  that produced it.
- Never `UPDATE`, `DELETE`, `INSERT`, `DROP`, `TRUNCATE`, `ALTER`. The
  database is read-only by policy and by SQL parser; attempting these will be
  denied by a hook.
- If a number looks too large or too small, suspect a data quirk before you
  suspect fraud.
- Output "audit leads" not accusations. No "fraud" / "stole" / "criminal"
  vocabulary in card text or user-facing messages.
