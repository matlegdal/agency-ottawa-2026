# Zombie Agent — Lobby Augmentation Addendum

> Companion to `zombie_agent_build_manual_v2.md`. Adds federal lobbying disclosures (`lobby` schema) as a fifth signal. Read v2 first; this only documents the delta.

---

## 1. What this adds

The v2 verifier checks four signals to confirm a candidate zombie is *dead*. Lobby adds a fifth signal in the opposite direction — was the entity *politically active* before going dark? The story shifts from

> "$2.4M to {entity}, no T3010 since 2022"

to

> "$2.4M to {entity}, who lobbied ISED and Health Canada 47 times between 2019 and 2022, then stopped filing T3010s and never registered another grant."

Lobbying-while-zombying is a stronger demo punchline, and it is independent evidence — a charity that registered consultant lobbyists is a charity that *could* be reached, so silence afterward is not just bureaucratic drift.

---

## 2. Data shape, in one screen

- **Schema**: `lobby` (local Docker only — *not* on Render). Loaded by `LOBBY/npm run setup`.
- **Tables used**: `lobby_registrations`, `lobby_communications`, `lobby_communication_dpoh`, `lobby_govt_funding`.
- **Pre-computed view**: `lobby.vw_client_activity` — one row per `client_name_norm` with reg counts, first/last reg dates, govt-funding flag.
- **Join key**: `client_name_norm` (already normalized at load time, indexed).
- **Match the CRA / FED side via the same regex**:
  ```sql
  NULLIF(regexp_replace(regexp_replace(lower(coalesce(name,'')),
    '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '')
  ```

### Coverage reality check

| Source side | Match rate to lobby clients (norm_name) |
|---|---|
| FED `recipient_legal_name` | ~16% |
| CRA `legal_name` (any year) | ~0.5% (458 of ~87K) |

CRA charities almost never register *as the client* — most lobbying for charities is done by consultant lobbyist firms whose `client_name_en` is the charity. Match rate is low but precision is high: any charity that *does* match is one that paid lobbyists or filed an in-house registration directly. Treat the probe as **high-precision, low-recall**: a hit is a strong signal; a miss is not evidence of innocence.

---

## 3. The new probe

Lives alongside the four existing probes in §8 of v2. The verifier subagent calls it on every candidate; the orchestrator can also call it during iterative exploration when defending an AMBIGUOUS verdict.

```sql
-- Inputs: legal_name (text), grant_end_date (date) — or NULL for all-time
WITH cand AS (
  SELECT NULLIF(regexp_replace(regexp_replace(lower($1),
         '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name
)
SELECT
  va.registrations_count,
  va.first_registration_date,
  va.last_registration_date,
  va.ever_received_govt_funding,
  -- Departments lobbied (executive branch only)
  ARRAY(
    SELECT DISTINCT d.institution
    FROM lobby.lobby_communications c
    JOIN lobby.lobby_communication_dpoh d ON d.comlog_id = c.comlog_id
    WHERE c.client_name_norm = (SELECT norm_name FROM cand)
      AND d.institution NOT IN ('House of Commons','Senate of Canada')
    ORDER BY 1 LIMIT 10
  ) AS departments_lobbied,
  -- Comm count in the 24 months around the grant end (NULL window = all-time)
  (SELECT COUNT(*)
     FROM lobby.lobby_communications c
    WHERE c.client_name_norm = (SELECT norm_name FROM cand)
      AND ($2::date IS NULL
           OR c.comm_date BETWEEN ($2::date - INTERVAL '12 months')
                              AND ($2::date + INTERVAL '12 months'))
  ) AS comms_around_grant_end
FROM lobby.vw_client_activity va, cand
WHERE va.client_name_norm = (SELECT norm_name FROM cand);
```

Returns 0 or 1 row. Empty result = no lobby footprint under that exact name (do not retry, do not infer absence — see §2 coverage note). Non-empty = real signal.

---

## 4. How the verifier uses it

Append to the verifier prompt's probe list in v2 §8:

```
  5. Did this entity register lobbyists or log communications with public
     office holders in the 24 months around its last grant end_date? Run the
     lobby probe (§3 of the addendum). A non-zero result strengthens the
     "this entity was operating, then disappeared" reading. A zero result is
     not exculpatory — only ~0.5% of CRA charities and ~16% of FED recipients
     match by name; absence here means nothing on its own.
```

Verdict mapping:

| Other 4 probes | Lobby probe | Verdict |
|---|---|---|
| All silent (no signs of life) | Non-zero (was lobbying) | **VERIFIED**, with stronger narrative — emit lobby fields in the briefing card |
| All silent | Zero | **VERIFIED**, standard narrative — do not mention lobby |
| Any showing life | (any) | **REFUTED** — lobby is not used to overturn life evidence |
| Mixed | Non-zero | **AMBIGUOUS** lean-VERIFIED — orchestrator should follow up on lobby comms to date-anchor the activity |

The lobby probe never flips a verdict to REFUTED on its own. Lobbying activity is consistent with both alive *and* recently-dead entities.

---

## 5. How the orchestrator uses it

Two opportunities, both in the existing Step B (candidate ranking) and Step C (iterative-exploration loop):

**Step B — sweetening the candidate list.** When ranking the 3–5 candidates to hand to the verifier, run the lobby probe in a single batch query and prefer candidates with `comms_around_grant_end > 0`. Tie-break by total dollar amount as before. This makes the "best three zombies" workflow (v2 §7, hour H11–12) lean toward demo-friendly cases automatically, without changing the dollar-threshold logic.

**Step C — defending an AMBIGUOUS verdict.** If the verifier returns AMBIGUOUS because (e.g.) a 2024 T3010 exists but reports zero programs, the orchestrator's follow-up should pull `lobby_communications` rows by date for that entity to show whether activity *also* tapered. A lobby-comm timeline that flatlines around the same date as the T3010 zero-program filing is a "transitioning into zombie" pattern — emit it as a finding even if the strict zombie definition doesn't fit.

Cap follow-up lobby queries to 2 per candidate to stay inside the v2 iteration budget.

---

## 6. Briefing card surface

When the verifier emits a VERIFIED finding with non-empty lobby data, `publish_finding` (the in-process MCP from v2 §6) should include three new fields:

```json
{
  "lobby_registrations": 49,
  "lobby_last_registration": "2022-06-14",
  "lobby_top_departments": ["ISED", "Health Canada", "PCO"]
}
```

Render as a small chip row beneath the "Verifier verdict" pill. Do not render the chip row when the lobby fields are absent — empty lobby data is not a finding.

---

## 7. Connecting to the database

The agent talks to a single Postgres connection. Two options:

1. **Local-only demo (recommended for hackathon)**: point `READONLY_DATABASE_URL` at the local Docker DB (`postgresql://qohash:qohash@localhost:5434/hackathon`). All four schemas (`cra`, `fed`, `ab`, `general`) plus `lobby` are present locally. No code changes to v2.
2. **Render demo with lobby fallback**: keep v2's Render URL for the four primary schemas; add a second connection for `lobby` queries. Costs an extra MCP server. Skip unless the local demo is unstable.

The v2 SQL-validation hook (`pre_sql_hook`) does not need changes — `lobby.*` table references parse identically to `cra.*`/`fed.*`.

---

## 8. Setup checklist (copy into the day-of runbook)

```bash
# 1. Drop the two OCL zips into LOBBY/data/raw/  (host blocks curl)
ls LOBBY/data/raw/*.zip                         # expect 2 files

# 2. One-shot import (~15s on M-series)
cd LOBBY && npm install && npm run setup

# 3. Sanity-check the four loaded tables and the view
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon \
  -c "SELECT COUNT(*) FROM lobby.vw_client_activity;"

# 4. Smoke-test the probe with a known charity
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon -v ON_ERROR_STOP=1 <<'SQL'
WITH cand AS (SELECT NULLIF(regexp_replace(regexp_replace(
  lower('Pure North S''Energy Foundation'),
  '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name)
SELECT * FROM lobby.vw_client_activity, cand WHERE client_name_norm = cand.norm_name;
SQL
```

If step 4 returns 0 rows for a charity you expect to match, recompute the norm regex against `lobby_registrations.client_name_en` directly — name drift across years is the most common cause.

---

## 9. Things to watch for during the demo

- **`govt_fund_ind = 'Y'` is registrant-self-reported.** Don't surface it as ground truth. Use only to colour the narrative ("registrant attested govt funding").
- **`lobby_govt_funding.amount` is unusable as a number.** Mixed annual / cumulative / commitments / loans, plus the literal "Provincial" institution sums to $433B. Never feature it as a dollar figure.
- **`House of Commons` dominates the DPOH table** (30% of rows). The probe filter excludes it plus `Senate of Canada`; do not remove that filter or every charity will look like it was lobbying "Parliament".
- **Norm-match precision drops on common names.** E.g. "Canadian Cancer Society" matches multiple unrelated registrations. The verifier should cross-reference dates: a 1998 lobby registration is irrelevant to a 2022 grant cessation.

---

## 10. Match rates by data tier

The norm_name probe is high-precision, low-recall — but recall scales sharply with the dollar tier the agent actually cares about:

| Universe | Recipients | Match to lobby (norm_name) |
|---|---:|---:|
| All FED recipients | 477K | 1.6% |
| FED ≥ $100K originals | 136K | 3.6% |
| FED ≥ $1M originals | 30K | 8.3% |
| FED ≥ $10M originals | 4.7K | **16.8%** |
| FED non-profit ≥ $1M | 4.4K | **11.0%** |
| FED for-profit ≥ $1M | 3.8K | 8.7% |
| **Zombie agent pool** (FED ≥ $500K, last grant pre-2022) | **19.6K** | **3.8% → 737 candidates** |
| All CRA charities | 87K | 0.5% |

The selection bias works for us: orgs that lobby tend to be the ones receiving large recurring federal money — exactly the demo-relevant pool. 737 candidates with a lobby footprint is more than enough for an agent that picks 3–5.

---

## 11. Higher-recall path: add lobby to `general.entity_source_links` (no LLM)

A second integration path lifts both FED *and* CRA recall by routing lobby through entity resolution. Crucially, **the LLM stage is not required** for this — `08-llm-golden-records.js` only authors `canonical_name`/`aliases` and merges existing golden records; it places zero source links. All 5.2M source links in the system today come from deterministic methods (`bn_anchor`, `exact_name`, `normalized`, `trade_name`, `pipe_split`, `new_entity`, `bn_new`).

### What deterministic-only resolution buys

| Path | Lobby clients resolved to existing golden records |
|---|---:|
| Lobby's own `client_name_norm` ↔ `entity_golden_records.norm_name` | **0 / 19,139 (0%)** |
| `general.norm_name(client_name_en)` ↔ `entity_golden_records.norm_name` | **3,182 / 18,208 (17.5%)** |

Lobby's homegrown normalizer (lowercase, simple regex) is incompatible with `general.norm_name()` (uppercase, strips trade-name tails / bilingual splits / `THE` / etc.). Re-normalizing with the canonical function does most of the work.

### Sketch: `general/scripts/12-resolve-lobby-entities.js`

~150 lines, mirrors the AB pattern in `04-resolve-entities.js`. No Splink, no LLM, idempotent.

```
Step 1. ALTER TABLE lobby.lobby_registrations  ADD COLUMN gnorm_name TEXT;
        ALTER TABLE lobby.lobby_communications ADD COLUMN gnorm_name TEXT;
        UPDATE both: gnorm_name = general.norm_name(client_name_en);

Step 2. INSERT INTO general.entity_resolution_log
        one row per distinct (gnorm_name, client_org_corp_num)
        source_schema='lobby', source_table='lobby_registrations'
        ON CONFLICT DO NOTHING.

Step 3. Three-pass deterministic match:
        (a) exact_name:  rl.gnorm_name = e.canonical_name (UPPER)
                         → match_method='exact_name'
        (b) normalized:  rl.gnorm_name = e.norm_name
                         → match_method='normalized'
        (c) leftover:    create new entities, match_method='new_entity',
                         entity_type='lobby_only'

Step 4. (Optional) trigram fallback (similarity > 0.85), mirrors
        10-donee-trigram-fallback.js. Adds ~3-5% more matches at
        small precision cost. ~30 min run.

Step 5. Refresh entity_golden_records for affected entity_ids
        via 09-build-golden-records.js (no LLM call).
```

### Verifier becomes one indexed lookup

After resolution, the §3 SQL probe can be replaced by:

```sql
SELECT lr.*, va.*
FROM general.entity_source_links esl
JOIN lobby.lobby_registrations lr
  ON (esl.source_pk->>'reg_id')::bigint = lr.reg_id
JOIN lobby.vw_client_activity va ON va.client_name_norm = lr.client_name_norm
WHERE esl.entity_id = $1 AND esl.source_schema = 'lobby';
```

No regex per query, no name drift, and the same `entity_id` resolves CRA / FED / AB / lobby in one place.

### What you give up by skipping the LLM

- **Variant unification.** The LLM is what merges "Coca-Cola Ltd / Coca-Cola Refreshments Canada Co." into one golden record. Without re-running it post-lobby, those FED entities and their lobby counterparts attach to *different* golden records.
- **Trade-name edge cases.** `general.norm_name()` strips most trade-name tails, but the LLM catches cases the regex misses.

For the hackathon, ship the deterministic resolver and accept the variant ceiling. Post-hackathon, re-run `08-llm-golden-records.js` once to merge across the new lobby↔FED gaps.

### Other recall improvements worth considering

1. **Trigram fuzzy match** (`pg_trgm`, `similarity > 0.7`) — useful as a *verifier alternative-name probe* on AMBIGUOUS verdicts, not as the primary join.
2. **Lobby's `client_org_corp_num_int` → `corp` schema → CRA / FED name.** Federal corporations registry is loaded locally. For incorporated entities (the high-dollar ones), this is an ID-based join that beats name matching. ~30-min spike if the demo lands on a low-recall candidate set.
