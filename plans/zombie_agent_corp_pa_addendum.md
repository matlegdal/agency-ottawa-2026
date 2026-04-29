# Zombie Agent — CORP + PA Augmentation Addendum

> Companion to `zombie_agent_build_manual_v2.md`, `zombie_agent_lobby_addendum.md`, and `zombie_agent_v3_correctness_and_polish.md`. Adds the federal corporate registry (`corp` schema) and the audited Public Accounts of Canada (`pa` schema) as probes 6 and 7. Read v2 first; this only documents the delta.

> **v3 alignment note (read first if you read v3 already).** v3 §D1 establishes a strict precedence chain among the existing checks and §D8 makes REFUTED final (no rebuttal-turn promotion). The CORP and PA probes in this addendum slot **into** that precedence chain — they do not override CHECK 2b (live federal agreement → REFUTED). A Dissolved corp with a live agreement is **REFUTED as a zombie** but becomes a strong **Ghost Capacity lead** (v3 §E9). §4 below is rewritten in v3's precedence-chain idiom; the original tabular verdict matrix is gone.

---

## 1. What this adds

The v2 verifier checks 4 probes (CRA filings, FED later grants, AB grants, AB non-profit status). The lobby addendum adds a 5th (was the entity politically active?). This addendum adds **two probes that together flip zombie detection from inference-by-absence to evidence-of-death**:

- **Probe 6 (CORP — federal corporate registry):** is the entity formally dissolved or being struck off?
- **Probe 7 (PA — Public Accounts):** did the federal government actually *pay* the agreement, or only sign it?

The story shifts from

> "$2.4M to {entity}, no T3010 since 2022"

(absence of evidence — slightly weak on stage) to

> "$2.4M to {entity}. Federal corporation **Dissolved** 2024-11-12 (Corporations Canada record). Public Accounts shows **$0 actually paid out** across all six audited fiscal years. The agreement was signed, the cash never moved, the corporation is dead."

(evidence of dissolution + evidence of non-payment — decisive). This is the difference between *"we couldn't find them"* and *"the Government of Canada itself confirms they're gone."*

---

## 2. Data shape, in one screen

### CORP — federal corporate registry

- **Schema**: `corp` (local Docker only — *not* on Render). Loaded by `CORP/npm run setup` (~5 min, two-phase XML→CSV→COPY).
- **Tables used**: `corp_corporations` (1.56M rows), `corp_status_history`, `corp_name_history`.
- **Pre-computed view**: `corp.vw_zombie_candidates` — corps with status ∈ {2, 3, 9, 10, 11, 19} or stale annual returns.
- **Join keys, in priority order**:
  1. **`business_number` ←→ `LEFT(fed.recipient_business_number, 9)`** — direct, 92.4% BN coverage on the corp side. The verifier should always try this first.
  2. **`current_name_norm`** ←→ same regex used for FED/CRA name normalization. Use for the 7.6% of corps without BNs and for FED rows where `recipient_business_number` is `NULL`/`-`/placeholder.

### PA — audited Public Accounts of Canada

- **Schema**: `pa` (local Docker only). Loaded by `PA/npm run setup` (~10 s).
- **Table used**: `pa.transfer_payments` (144,570 rows across FY 2020–2025).
- **Pre-computed view**: `pa.vw_recipient_totals` — per-recipient total across years (recipient-detail rows only).
- **Join key**: `recipient_name_norm` (same regex as everywhere else).

### The row-type column-flip in PA (read this before querying)

`pa.transfer_payments` mixes two row shapes and the meaning of two columns flips:

| Row type | `recipient_name_location` | `expenditure_current_yr` | `aggregate_payments` |
|---|---|---|---|
| **Program total** | NULL | filled (large) | 0 |
| **Recipient detail** | filled | NULL | filled |

For zombie detection always filter to `recipient_name_location IS NOT NULL` and use `aggregate_payments` as the dollar amount. `vw_recipient_totals` already does this.

### Coverage reality check

| Probe | Source side | Match rate to candidates |
|---|---|---|
| 6 (CORP) | FED `recipient_business_number` (BN) | ~80% of distinct FED recipients with a clean 9-digit BN match a corp |
| 6 (CORP) | FED `recipient_legal_name` | ~30% via `current_name_norm` (catches BN-NULL cases) |
| 7 (PA)   | FED `recipient_legal_name` | ~25–35% (annual; depends on payment threshold ≥ $100K) |

CORP is **high-recall, high-precision** for incorporated entities. PA is **medium-recall, high-precision** — anyone who actually got paid >$100K in a fiscal year is in there; absence is meaningful for amounts that should be visible.

---

## 3. The new probes

Both probes live alongside the four in v2 §8 and the fifth in the lobby addendum. The verifier subagent calls them on every candidate. The orchestrator can also call them during iterative-exploration when defending an AMBIGUOUS verdict.

### Probe 6 — CORP

```sql
-- Inputs: $1 = legal_name (text), $2 = business_number (text, may be NULL or 15-char CRA BN)
WITH cand AS (
  SELECT
    NULLIF(regexp_replace(regexp_replace(lower($1),
      '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name,
    LEFT(NULLIF($2, ''), 9) AS bn9
)
SELECT
  c.corporation_id,
  c.current_name,
  c.current_status_code,
  c.current_status_label,
  c.current_status_date::date           AS status_date,
  c.dissolution_date::date              AS dissolution_date,
  c.intent_to_dissolve_date::date       AS intent_to_dissolve_date,
  c.last_annual_return_year,
  c.incorporation_date::date            AS incorporation_date,
  CASE
    WHEN bn9 IS NOT NULL AND c.business_number = bn9 THEN 'bn'
    ELSE 'name'
  END                                   AS match_method
FROM corp.corp_corporations c, cand
WHERE
  (cand.bn9 IS NOT NULL AND c.business_number = cand.bn9)
  OR (cand.bn9 IS NULL AND c.current_name_norm = cand.norm_name)
LIMIT 1;
```

**Status-code interpretation (memorize this — it's the verdict driver):**

| `current_status_code` | Label | Verdict force |
|---:|---|---|
| 1 | Active | Probe is **silent** — no zombie signal from CORP |
| 2 | Active - Intent to Dissolve Filed | **Strong zombie signal** — entity itself filed dissolution paperwork |
| 3 | Active - Dissolution Pending (Non-compliance) | **Strongest zombie signal** — Corporations Canada is striking the corp off for not filing annual returns |
| 4 | Active - Discontinuance Pending | Weak — entity is moving regimes, not dying |
| 9 | Inactive - Amalgamated | **Refutes zombie reading** — merged into a successor; chase the successor |
| 10 | Inactive - Discontinued | Ambiguous — left federal regime; may be alive provincially |
| 11 | Dissolved | **Decisive zombie verdict** — final state, no going back |
| 19 | Inactive | (5 rows total — edge case) |

### Probe 7 — PA

```sql
-- Inputs: $1 = legal_name (text)
WITH cand AS (
  SELECT NULLIF(regexp_replace(regexp_replace(lower($1),
    '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name
)
SELECT
  rt.years_appeared,
  rt.first_year,
  rt.last_year,
  rt.total_paid::bigint                 AS total_paid_cad,
  -- Year-by-year breakdown for the briefing-card sparkline
  ARRAY(
    SELECT json_build_object(
      'fy', tp.fiscal_year_end,
      'paid', tp.aggregate_payments::bigint,
      'department', tp.department_name)
    FROM pa.transfer_payments tp
    WHERE tp.recipient_name_norm = (SELECT norm_name FROM cand)
      AND tp.recipient_name_location IS NOT NULL
    ORDER BY tp.fiscal_year_end
  )                                     AS payments_by_year
FROM pa.vw_recipient_totals rt, cand
WHERE rt.recipient_name_norm = (SELECT norm_name FROM cand);
```

**Payment-trajectory interpretation:**

| Pattern | What it means |
|---|---|
| Empty result | **Strongest zombie signal** — agreement signed but no cash ever flowed (WE Charity, SDTC) |
| `last_year < EXTRACT(YEAR FROM grant_end_date) - 1` | Cash flowed for a while, then stopped before the agreement ended |
| `last_year >= 2024` AND `total_paid` near agreement value | Probe **refutes** zombie reading — recipient is actively drawing |
| `total_paid << agreement value` AND `last_year` recent | Slow disbursement; emit as caveat, not zombie |

**Important false-positive sources:** the empty-result reading only holds when the agreement amount is large enough (`>= $100K/year`) that PA *should* see it. Below that threshold, the recipient may legitimately be paid but PA simply doesn't list them. The verifier should always check `agreement_value >= 100000` before treating empty-PA as a signal.

---

## 4. How the verifier uses it

The verifier's existing precedence chain (v3 §D1) is:

```
1. CHECK 5 (BN-anchored vw_agreement_current total < $1M)        → REFUTED
2. CHECK 0 (designation A or B)                                  → REFUTED
3. CHECK 1 (T3010 filing window still open)                      → REFUTED
4. CHECK 7 (entity rebranded — identification_name_history shows
            a name change in the most recent year)               → REFUTED
5. CHECK 2b (FED agreement_end_date >= 2024-01-01 AND
            end_date >= start_date on any row tied to the BN)    → REFUTED
6. CHECK 3 (any AB payment > 0 in FY2024-25 / FY2025-26 for the
            resolved entity_id)                                  → REFUTED
7. CHECK 8 (field_1570 = TRUE — first-party dissolution)         → VERIFIED
8. CHECK 6 (govt_share_of_rev < 70 on most-recent clean filing)  → AMBIGUOUS
9. otherwise (death signal fired AND nothing above triggered)    → VERIFIED
```

CORP and PA insert as **two new REFUTED-side checks (CHECK 9 / CHECK 10)** and **two new VERIFIED-side checks (CHECK 11 / CHECK 12)**. The REFUTED-side checks slot near the top so live entities are short-circuited cheaply; the VERIFIED-side checks slot below CHECK 8 so first-party dissolution still wins on its own.

### Updated precedence chain (v3 §D1 + this addendum)

```
1.  CHECK 5  (vw_agreement_current total < $1M)                  → REFUTED
2.  CHECK 0  (designation A or B)                                → REFUTED
3.  CHECK 9  (CORP status 1 Active AND last_annual_return_year
              >= grant_end_year − 1)                             → REFUTED
4.  CHECK 1  (T3010 filing window still open)                    → REFUTED
5.  CHECK 7  (entity rebranded)                                  → REFUTED
6.  CHECK 2b (FED agreement_end_date >= 2024-01-01)              → REFUTED
7.  CHECK 3  (any AB payment > 0 in FY2024-25 / FY2025-26)       → REFUTED
8.  CHECK 10 (PA shows recipient-detail row in last_year >=
              current_year − 1 AND aggregate_payments > 0)       → REFUTED
9.  CHECK 11 (CORP status 11 Dissolved OR status 3 Dissolution
              Pending — Non-compliance)                          → VERIFIED
10. CHECK 8  (field_1570 = TRUE)                                 → VERIFIED
11. CHECK 12 (PA empty across all loaded FYs AND agreement_value
              >= $100K AND agreement_start_date <= today − 12mo) → VERIFIED
12. CHECK 6  (govt_share_of_rev < 70)                            → AMBIGUOUS
13. otherwise (death signal fired AND nothing above triggered)   → VERIFIED
```

**Why these positions:**

- **CHECK 9 (CORP-Active-with-recent-filing) before CHECK 1.** A clean Active record with an annual return filed within the last year is the cheapest possible refutation — no T3010 lookup needed.
- **CHECK 10 (PA-recent-payment) right after CHECK 3.** PA recent payment is conclusive: the cash actually moved, the entity is alive enough to have a bank account that received federal money. Slotting after CHECK 3 lets AB-payment evidence win first when present (faster path).
- **CHECK 11 (CORP-Dissolved) before CHECK 8.** Registry-confirmed dissolution outranks self-reported dissolution. If both fire they agree; the precedence just picks the stronger evidence label for the briefing.
- **CHECK 12 (PA-empty) after CHECK 8.** The empty-PA signal is decisive only when other death signals are silent — by itself it can mean "agreement signed but cash didn't move yet" rather than "the entity is gone." Pairing it with at least one other signal (or letting CHECK 11 fire first) keeps precision high.

### Append to the verifier prompt

```
  9. Run the CORP probe. If current_status_code = 1 (Active) AND
     last_annual_return_year >= grant_end_year - 1, emit REFUTED with
     "federal corporate registry shows entity is Active and filed an
     annual return in {year}". This check fires near the top of the
     precedence chain — cheaper than T3010 lookups.

 10. Run the PA probe. If the recipient appears in pa.transfer_payments
     with last_year >= current_year - 1 AND aggregate_payments > 0,
     emit REFUTED with "Public Accounts shows ${amount} paid to this
     recipient in FY{year}".

 11. (Continuing the CORP probe.) If current_status_code IN (3, 11) —
     Dissolution Pending or Dissolved — emit VERIFIED with the
     dissolution_date or status_date as the primary evidence. Cite the
     status_label verbatim ("Active - Dissolution Pending
     (Non-compliance)" or "Dissolved").

 12. (Continuing the PA probe.) If the FED agreement_value >= $100,000
     AND agreement_start_date <= today − 12 months AND the PA query
     returned zero recipient-detail rows across all six loaded fiscal
     years, emit VERIFIED with "no cash visible in audited Public
     Accounts despite ${amount} of federal commitments".

 NOTE: status_code 9 (Amalgamated) is REFUTED — chase the successor
 via corp_status_history (activity code 4). Status 4 (Discontinuance
 Pending) and 10 (Inactive - Discontinued) are AMBIGUOUS unless
 paired with other death signals; the entity may be alive under a
 different regime.
```

### A concrete dual-signal example (SDTC)

```
Step A surfaces:        Sustainable Development Technology Canada (BN xxxxxxx)
CHECK 5  (≥$1M)         pass — $1.6B in vw_agreement_current
CHECK 0  (designation)  pass — not a charity, no designation
CHECK 9  (CORP active)  no — status_code = 11 Dissolved, status_date 2025-03-31
CHECK 1  (T3010 open)   N/A — not in CRA
CHECK 7  (rebrand)      no
CHECK 2b (live agreem.) varies — depends on whether any agreement in
                        vw_agreement_current has end_date >= 2024-01-01.
                        If yes, REFUTED here and emit Ghost Capacity lead.
                        If no (agreements all wrapped before 2024), continue.
CHECK 3  (AB payment)   no
CHECK 10 (PA recent)    no — empty PA across all FYs
CHECK 11 (CORP died)    FIRES — status 11 Dissolved → VERIFIED

Verdict: VERIFIED. Headline: "$X in federal commitments to the foundation
Parliament dissolved on 2025-03-31; no payments visible in audited Public
Accounts."
```

If CHECK 2b fires (live SDTC agreement still on the books in 2024+), the verdict flips to REFUTED-as-zombie + Ghost Capacity lead — the strongest possible Challenge 2 case (registry-confirmed dead entity, federal contract still drawing).

---

## 5. How the orchestrator uses it

### REFUTED is final (v3 §D8)

Repeating the v3 rule because CORP/PA make it especially tempting to bend: a verifier REFUTED on CHECK 2b (live federal agreement) **cannot** be flipped to VERIFIED via the iterative-exploration loop, even when CORP says the corporation is Dissolved. The Dissolved-corp + live-agreement combination is the textbook **Ghost Capacity lead**, not a zombie. Surface it via the §5.5 path below; do not re-narrate it as VERIFIED.

### Step A — pre-enrich at gate time (v3 §D4 / §E4 compatible)

If you implement v3 §D4 (Step A live-agreement gate) and §E4 (pre-materialised candidate table), the CORP and PA probes can also be pulled forward to gate time, not verifier time. Add to Step A as an extra column on each candidate row:

```sql
LEFT JOIN corp.corp_corporations c
       ON c.business_number = e.bn_root
LEFT JOIN pa.vw_recipient_totals rt
       ON rt.recipient_name_norm = e.norm_name
-- ...
SELECT
  e.*,
  c.current_status_code     AS corp_status,
  c.dissolution_date,
  rt.last_year              AS pa_last_year,
  rt.total_paid             AS pa_total
```

This gives the orchestrator richer signal *before* the verifier runs, without changing the verifier's precedence chain. Tie-break the candidate ranking by: `(corp_status IN (3,11), pa.total IS NULL, originals DESC)` to surface dual-signal cases first.

### Step B — sweetening the candidate list (v2 §7, hour H11–12)

When ranking the 3–5 candidates to hand to the verifier, run probes 6 and 7 in a single batch query and prefer candidates where **both** signals fire (CORP status ∈ {3, 11} AND PA empty). Tie-break: dissolution_date most recent. This automatically surfaces the SDTC-shaped cases without changing the dollar-threshold logic.

```sql
-- Batch probe used by orchestrator's Step B for top-N FED recipients
WITH fed_candidates AS (...)  -- top FED zombies by amount, from v2 query
SELECT
  fc.recipient_legal_name,
  fc.originals,
  c.current_status_label,
  c.dissolution_date::date,
  rt.last_year                          AS last_pa_year,
  rt.total_paid                         AS pa_total,
  -- Composite score: prefer dual-confirmed cases for demo
  (CASE WHEN c.current_status_code IN (3, 11) THEN 1 ELSE 0 END
   + CASE WHEN rt.recipient_name_norm IS NULL THEN 1 ELSE 0 END) AS dual_signal
FROM fed_candidates fc
LEFT JOIN corp.corp_corporations c
       ON c.business_number = LEFT(NULLIF(fc.recipient_business_number, ''), 9)
       OR c.current_name_norm = fc.norm_name
LEFT JOIN pa.vw_recipient_totals rt ON rt.recipient_name_norm = fc.norm_name
ORDER BY dual_signal DESC, fc.originals DESC LIMIT 10;
```

### Step C — defending an AMBIGUOUS verdict (v2 §7 iterative-exploration loop)

Two new follow-up patterns the orchestrator can use within its 3-query budget:

1. **CORP timeline pull.** If the verifier returns AMBIGUOUS because CORP shows status 1 (Active), pull `corp_status_history` to see if there *was* a 2/3/11 status that got reverted. Sometimes a dissolution intent is filed and then revoked; both events are in the history table.

   ```sql
   SELECT status_label, effective_date::date, is_current
   FROM corp.corp_status_history
   WHERE corporation_id = $1
   ORDER BY effective_date DESC LIMIT 5;
   ```

2. **PA gap pull.** If PA shows historical payments but no recent ones, surface the year-by-year trajectory to confirm the disbursement stopped. A flatline ending 2+ years before the agreement end date is a "soft zombie" — still a story.

   ```sql
   SELECT fiscal_year_end, department_name, aggregate_payments::bigint
   FROM pa.transfer_payments
   WHERE recipient_name_norm = $1 AND recipient_name_location IS NOT NULL
   ORDER BY fiscal_year_end;
   ```

Cap follow-up CORP+PA queries to **2 per candidate**, alongside the existing 2-per-candidate lobby budget. Total iterative-exploration budget is unchanged at 3 queries per candidate from v2 §10 — the addenda just pre-allocate them by category so the agent doesn't all-spend on one source.

### 5.5 Emitting Ghost Capacity leads (v3 §E9 upgrade)

v3 §E9 introduces a sidebar for "Dissolved entity + live federal agreement" — REFUTED as a zombie, but a strong Challenge 2 (Ghost Capacity) lead. CORP makes this sidebar dramatically stronger than the v3-baseline version, which relied on charity self-attestation (`field_1570 = TRUE`). With CORP, the death signal is **registry-confirmed by Corporations Canada**, not self-reported.

When the verifier returns REFUTED with reason "live federal agreement runs past 2024-01-01" AND any of the following fire, emit a Ghost Capacity sidebar card via a new `publish_ghost_lead` tool (or extend `publish_finding` with a `category="ghost_capacity_lead"` field):

| Death evidence | Sidebar header phrasing |
|---|---|
| CORP `current_status_code = 11` (Dissolved) | "Federal corporate registry: Dissolved {date}" |
| CORP `current_status_code = 3` (Dissolution Pending) | "Federal corporate registry: striking off — {date}" |
| `field_1570 = TRUE` (charity self-dissolution) | "T3010 self-attests dissolution {fpe}" |
| AB `ab_non_profit.status = 'Cancelled'` or 'Struck' | "AB registry: {status}" |

The Ghost Capacity card body should include:
- The agreement detail (department, ref_number, agreement_value, end_date)
- The death-signal source and date
- A one-liner: *"Federal funds may be reaching a successor entity, a contractor, or no one — without a formal novation. Audit lead for Challenge 2 (Ghost Capacity)."*

Cap at 3 Ghost Capacity leads per run to avoid overshadowing the zombie findings on the briefing panel.

---

## 6. Briefing card surface

When the verifier emits a VERIFIED finding with non-empty CORP or PA data, `publish_finding` (the in-process MCP from v2 §6) should include up to six new fields:

```json
{
  "corp_status": "Dissolved",
  "corp_status_date": "2025-03-31",
  "corp_dissolution_date": "2025-03-31",
  "pa_total_paid_cad": 0,
  "pa_last_payment_year": null,
  "pa_payments_by_year": []
}
```

UI rendering, beneath the "Verifier verdict" pill:

- **Corporate status:** colored chip — red for Dissolved, orange for Dissolution Pending / Intent to Dissolve, gray for other inactive states. Hide chip when status is Active or no match.
- **Public Accounts trajectory:** mini sparkline (6 bars, FY 2020–2025), height proportional to `aggregate_payments`. Empty bars styled gray. A row of all-empty bars beneath an Active agreement value is the visual punchline.

Do not render either chip when the corresponding probe came back silent — empty CORP/PA data is not a finding *unless* the agreement amount makes the absence load-bearing (≥ $100K for PA; ≥ any amount for CORP if the entity is incorporated).

### v3 §E1 dossier-panel extensions

v3 §E1 introduces a per-entity dossier with three sub-views (funding events / dependence-ratio / status banner). CORP and PA each add a fourth sub-view that fits the same pattern:

- **Sub-view 4 (CORP) — Corporate registry timeline.** Render `corp_status_history` for the entity as a vertical event list: incorporation date, every status transition, every name change (from `corp_name_history`). Highlight the dissolution event in red. Pulled by extending the `dossier` MCP tool query bundle:
   ```sql
   SELECT 'status' AS kind, status_label AS label, effective_date::date AS date, is_current
     FROM corp.corp_status_history WHERE corporation_id = $1
   UNION ALL
   SELECT 'name', name, effective_date::date, is_current
     FROM corp.corp_name_history WHERE corporation_id = $1
   ORDER BY date DESC;
   ```

- **Sub-view 5 (PA) — Audited cash trajectory.** A 6-bar sparkline (FY 2020–2025) with bar height = `aggregate_payments`, colored gray when empty. Hover shows the paying department. The visual contrast between an Active agreement value (large) and an all-gray PA row is the dossier's punchline. Pulled by:
   ```sql
   SELECT fiscal_year_end, department_name, aggregate_payments::bigint
     FROM pa.transfer_payments
    WHERE recipient_name_norm = $1 AND recipient_name_location IS NOT NULL
    ORDER BY fiscal_year_end;
   ```

The dossier panel only renders for VERIFIED cards (per v3 §9 anti-pattern #11). Both sub-views render even when their data is empty — for the dossier specifically, "no rows" is a finding, not a hidden state.

---

## 7. Connecting to the database

Same options as the lobby addendum §7. Both `corp` and `pa` schemas are local-only:

1. **Local-only demo (recommended)**: point `READONLY_DATABASE_URL` at the local Docker DB. All seven schemas (`cra`, `fed`, `ab`, `general`, `lobby`, `corp`, `pa`) live there.
2. **Render demo with local fallback**: keep v2's Render URL for the four primary schemas; second connection for `lobby`/`corp`/`pa`. Costs an extra MCP server; skip unless local is unstable.

The v2 SQL-validation hook does not need changes — `corp.*` and `pa.*` table references parse identically.

---

## 8. Setup checklist (copy into the day-of runbook)

```bash
# 1. Bring up local Docker Postgres if not already running
docker compose up -d                            # from repo root

# 2. Drop the CORP zip into CORP/data/raw/
ls CORP/data/raw/OPEN_DATA_SPLIT.zip            # ~200 MB, browser download from
                                                # https://ised-isde.canada.ca/cc/lgcy/download/OPEN_DATA_SPLIT.zip

# 3. CORP setup (~5 minutes, two-phase XML→CSV→COPY)
cd CORP && npm install && npm run setup

# 4. PA setup (~10 seconds, CSVs are committed in PA/data/raw/)
cd ../PA && npm install && npm run setup

# 5. Sanity check both schemas are loaded
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon \
  -c "SELECT 'corp' AS s, COUNT(*) FROM corp.corp_corporations
      UNION ALL SELECT 'pa', COUNT(*) FROM pa.transfer_payments;"
# Expect: corp ~1.56M, pa ~144K

# 6. Smoke-test the dual-signal landing zone (SDTC)
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon -v ON_ERROR_STOP=1 <<'SQL'
SELECT current_status_label, dissolution_date::date
  FROM corp.corp_corporations
 WHERE current_name ILIKE '%SUSTAINABLE DEVELOPMENT TECH%' OR current_name ILIKE '%appui technologique%'
 LIMIT 3;
SELECT COUNT(*)
  FROM pa.transfer_payments
 WHERE recipient_name_norm LIKE '%sustainable development tech%';
SQL
```

If step 6 returns Dissolved + 2025-03-31 for CORP and 0 rows for PA, the dual-signal demo is ready.

---

## 9. Things to watch for during the demo

- **REFUTED is final (v3 §D8 cross-reference).** Even when CORP says Dissolved, a live FED agreement (`agreement_end_date >= 2024-01-01`) still REFUTES the zombie verdict. Surface it via the §5.5 Ghost Capacity sidebar instead. The orchestrator must not narrate "challenged → verified" on a CHECK-2b REFUTED, regardless of how strong the CORP signal is.
- **CORP status 1 (Active) is not exculpatory by itself.** 657K of 1.56M corps are Active — the registry doesn't purge inactive ones, but plenty of Active corps are also functionally dormant. Use Active to *refute* a verdict only when paired with a recent annual return (`last_annual_return_year >= grant_end_year - 1`) — that is what CHECK 9 enforces.
- **CORP status 3 ("Dissolution Pending - Non-compliance") is the demo's secret weapon.** 35,598 corps in this state. Many overlap with FED grants. Each one is a live story — *"the federal government is still paying out on an agreement to a company it's actively striking off the registry for not filing."* The narrative writes itself.
- **The Inactive - Amalgamated case (status 9) is a trap.** Treating an amalgamated corp as a zombie will get challenged — it's not dead, it's been absorbed. Use `corp_status_history` to locate the amalgamation activity (code 4) and follow up to the successor.
- **PA empty result on a small agreement is meaningless.** The $100K threshold cuts off small-but-real payments. Always check `agreement_value` before reading PA absence as a signal.
- **PA name-match precision drops on government recipients.** "Government of Alberta" / "Province of Alberta" / "Alberta" all appear. Filter government recipients out of the demo target set; they are not zombies anyway.
- **`recipient_name_location` in PA sometimes contains the city embedded in the recipient line** — `"NAME - CITY, PROV"`. The `recipient_name_norm` column already strips this on the way in (peels off after `" - "`), but be aware when manually inspecting.
- **Bilingual recipient names use `|` separator** in some FED rows (e.g., `City of Toronto | Ville de Toronto`). PA does not use `|`. The verifier should split on `|` and try both halves before concluding "no match."

---

## 10. The combined demo punchline (slide 2 candidates)

> **v3 framing rule (read first).** The audience is a Deputy Minister or Minister. v3 §9 anti-pattern #10 prohibits "fraud" / "criminal" / "stole" / "misappropriated" vocabulary. Frame every punchline as an **audit lead** — *"a closer look is warranted"* — never as an accusation.

> **v3 verifier-precedence cross-check.** Each candidate below has been walked through the §4 precedence chain. Items that flip from the v2-baseline candidate set under v3's stricter gates are noted.

The dual-signal CORP+PA table currently surfaces three demo-grade stories.

### Story 1 — Sustainable Development Technology Canada (SDTC)

- **Headline:** *"$1.6B in federal commitments to a foundation Parliament dissolved last year, with no payments visible in audited Public Accounts."*
- **Verifier walk:** CHECK 5 pass ($1.6B), CHECK 0 N/A (not a charity), CHECK 9 silent (status is 11 Dissolved, not 1 Active), CHECK 1 N/A, CHECK 7 N/A, **CHECK 2b**: depends on whether any agreement runs past 2024-01-01 in `vw_agreement_current`. **If yes**: REFUTED-as-zombie + Ghost Capacity lead (still the strongest §5.5 story). **If no**: continues to CHECK 11 (CORP Dissolved) → VERIFIED.
- **Confidence:** triple-confirmed (CORP registry + empty PA + parliamentary record), modulo the CHECK 2b branch.
- **Why this is the safest demo:** audience already knows SDTC was dissolved; the agent's contribution is showing the dollar trail and the audit-lead framing.

### Story 2 — WE Charity Foundation

- **Headline:** *"$543M in federal contribution agreements signed during the 2020 ethics review, with zero payments visible in audited Public Accounts."*
- **Verifier walk:** CHECK 5 pass, CHECK 0 N/A, CHECK 9 silent (no CORP match — provincially incorporated, not in `corp.corp_corporations`), CHECK 1 N/A or pass (charity is in CRA), **CHECK 2b**: agreements wrapped March 2021 → does not fire, continues. CHECK 3 silent. CHECK 10 silent. CHECK 11 silent (no CORP match). CHECK 8: was the field_1570 set? CHECK 12 fires: agreement value ≥ $100K, signed > 12 months ago, PA returned zero rows → **VERIFIED on PA-empty alone**.
- **Confidence:** PA-confirmed only. CORP is silent (not federally incorporated — provincially registered foundation). Headline must be careful: agreements signed but not paid is the only verifiable claim.
- **Caveat:** if your CRA T3010 lookup shows the foundation is still in the open filing window, CHECK 1 fires → REFUTED. Verify before featuring.

### Story 3 — The "Dissolution Pending" pattern

- **Headline:** *"35,598 federally-incorporated companies are currently being struck off the registry for not filing annual returns. {N} of them still appear in the federal grants register with agreements stretching to 2032."*
- **Top examples after v3 gate-filtering** (Step A live-agreement filter from v3 §D4 may reduce the pool further; verify on demo day):
  - Aspire Food Group Ltd. — agreement to 2033, status 3 since 2026-03-05, last filing 2023
  - Ukko Agro Inc. — agreement to 2031, status 3 since 2026-01-16, last filing 2023
  - Nexus Robotics Inc. — agreement to 2023, status 3 since 2026-02-18, last filing 2023
- **Verifier walk:** these will mostly **REFUTE** under v3 §D4 (Step A live-agreement gate) because their `agreement_end_date >= 2024-01-01`. They become **Ghost Capacity leads** via §5.5, not zombies.
- **How to use it:** This is the closing slide, not the headline. Frame as *"the systemic pattern — federal contracts with companies the federal registry is striking off — is the audit lead the agent surfaces at scale."* It generalizes the demo from a 3-zombie list to a category.

### Recommended ordering for a 4-minute pitch

1. **Story 1 (SDTC)** as the visible find — well-known, audience leans in, the agent's dossier panel makes the trail visible.
2. **Story 2 (WE Charity)** as the second card — different shape (PA-empty without CORP signal) shows the agent reasons across multiple evidence types.
3. **Story 3 (the pattern)** as the closing — *"and 35,000 more like this, surfaced by the same pipeline."* This is the differentiation line.

Do not feature any candidate that requires explaining why CHECK 2b doesn't fire. The audience will not follow the precedence chain in real time.

---

## 11. Optional: higher-recall paths (post-hackathon)

1. **Add `corp_corporations` as an 8th `general.entity_source_links` source.** Then golden records resolve federal corps to the same `bn_root` as CRA / FED / AB rows, lifting CORP recall from 80% to ~95% on incorporated FED recipients. ~2 hours of pipeline work. Compatible with the lobby addendum §11 deterministic-only path — both can land in one pipeline pass.
2. **Trigram fuzzy match** on `pg_trgm` for both CORP and PA name lookups — same pattern as the lobby addendum. Use only as an alternative-name search on AMBIGUOUS verdicts.
3. **Backfill PA fiscal years 2003–2019.** PSPC publishes them at the same URL pattern; we currently load only 2020–2025 because that's the window of FED relevance. Older years would let us reason about long-tail historical patterns, but they don't help a one-day demo.
4. **Add Public Accounts contracts (Volume III, Section 3).** Same source publisher, separate set of CSVs (~610 MB for the unified contracts file). Extends the framework from grants to procurement and unlocks Challenges 4/5/9. Out of scope for this addendum.
5. **Pre-compute CORP+PA into v3 §E4's candidate table.** When v3 §E4 (pre-materialised candidate table) lands, fold CORP `current_status_code` and PA `last_year` / `total_paid` into the same rows. The verifier becomes pure-classification — no SQL needed at probe time. Single biggest determinism win available once v3 correctness lands.
