# Zombie Agent — CORP + PA Augmentation Addendum

> Companion to `zombie_agent_build_manual_v2.md` and `zombie_agent_lobby_addendum.md`. Adds the federal corporate registry (`corp` schema) and the audited Public Accounts of Canada (`pa` schema) as probes 6 and 7. Read v2 first; this only documents the delta.

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

Append to the verifier prompt's probe list in v2 §8:

```
  6. Run the CORP probe (§3 of the corp-pa addendum). Match by 9-digit BN
     when available, fall back to normalized name. If current_status_code
     is 11 (Dissolved) or 3 (Active - Dissolution Pending Non-compliance),
     emit verdict VERIFIED with the dissolution_date or status_date as the
     primary evidence. If status is 1 (Active) and last_annual_return_year
     >= grant_end_year - 1, emit REFUTED unless other probes contradict.

  7. Run the PA probe (§3 of the corp-pa addendum). If the FED agreement
     value is >= $100K AND the PA query returns zero rows AND the agreement
     start_date is at least 12 months before today, emit verdict VERIFIED
     with "no cash ever paid" as primary evidence. If PA shows recent
     payments (last_year >= current_year - 1) emit REFUTED.
```

### Verdict mapping (with all 7 probes in play)

| Probe 6 (CORP) | Probe 7 (PA) | Other 5 probes | Verdict |
|---|---|---|---|
| status 11 (Dissolved) | empty (no payments) | (any) | **VERIFIED** — strongest possible, dual-confirmed dead |
| status 3 (Dissolution Pending) | empty | all silent | **VERIFIED** — registry striking off + no money flowed |
| status 11 or 3 | non-empty (cash flowed) | all silent | **VERIFIED** — dead now, but did receive money historically; emit both |
| status 1 (Active) | empty | all silent | **AMBIGUOUS** — alive in registry but no money disbursed; rebuttal turn should pull the agreement-amendment trail to see if the agreement was canceled |
| status 1 | non-empty recent | (any) | **REFUTED** — alive and being paid |
| status 9 (Amalgamated) | (any) | (any) | **REFUTED** — chase the successor entity (use `corp_status_history` to find the amalgamation target) |
| no match (BN absent + name miss) | empty | all silent | **AMBIGUOUS** — the entity may be a sole proprietorship, partnership, or non-federal corporation; cannot conclude from CORP absence alone |

### A concrete dual-signal example (the SDTC case)

```
Probe 6 → status_code = 11 (Dissolved), dissolution_date = 2025-03-31
Probe 7 → empty (zero recipient-detail rows in PA across all 6 fiscal years)
Other 5 → silent
Verdict → VERIFIED with the most damning narrative: "Foundation dissolved
          by parliamentary action; $1.6B of disclosed federal grants but
          no payments visible in audited Public Accounts."
```

This is the demo's strongest landing zone — call it out explicitly in the pitch.

---

## 5. How the orchestrator uses it

### Step B — sweetening the candidate list (v2 §7, hour H11–12)

When ranking the 3–5 candidates to hand to the verifier, run probes 6 and 7 in a single batch query and prefer candidates where **both** signals fire (status ∈ {2, 3, 11} AND PA empty). Tie-break: dissolution_date most recent. This automatically surfaces the WE-Charity- and SDTC-shaped cases without changing the dollar-threshold logic.

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

- **CORP status 1 (Active) is not exculpatory by itself.** 657K of 1.56M corps are Active — the registry doesn't purge inactive ones, but plenty of Active corps are also functionally dormant. Use Active to *refute* a verdict only when paired with a recent annual return (`last_annual_return_year >= grant_end_year - 1`).
- **CORP status 3 ("Dissolution Pending - Non-compliance") is the demo's secret weapon.** 35,598 corps in this state. Many overlap with FED grants. Each one is a live story — *"the federal government is still paying out on an agreement to a company it's actively striking off the registry for not filing."* The narrative writes itself.
- **The Inactive - Amalgamated case (status 9) is a trap.** Treating an amalgamated corp as a zombie will get challenged — it's not dead, it's been absorbed. Use `corp_status_history` to locate the amalgamation activity (code 4) and follow up to the successor.
- **PA empty result on a small agreement is meaningless.** The $100K threshold cuts off small-but-real payments. Always check `agreement_value` before reading PA absence as a signal.
- **PA name-match precision drops on government recipients.** "Government of Alberta" / "Province of Alberta" / "Alberta" all appear. Filter government recipients out of the demo target set; they are not zombies anyway.
- **`recipient_name_location` in PA sometimes contains the city embedded in the recipient line** — `"NAME - CITY, PROV"`. The `recipient_name_norm` column already strips this on the way in (peels off after `" - "`), but be aware when manually inspecting.
- **Bilingual recipient names use `|` separator** in some FED rows (e.g., `City of Toronto | Ville de Toronto`). PA does not use `|`. The verifier should split on `|` and try both halves before concluding "no match."

---

## 10. The combined demo punchline (slide 2 candidates)

The dual-signal CORP+PA table currently surfaces three demo-grade stories. Pick whichever lands best with the audience:

1. **Sustainable Development Technology Canada (SDTC)** — $1.6B FED-disclosed, **Dissolved 2025-03-31** by parliamentary action following the AG's 2024 governance findings, **$0 in audited Public Accounts** across 2020–2025. *The foundation Parliament killed last year still appeared in the federal grants register with $1.6B in commitments.* Triple-confirmed (CORP + PA + parliamentary record).

2. **WE Charity Foundation** — $543M FED-disclosed agreement (May 2020 – March 2021), **$0 in Public Accounts**, no Corporations Canada match (the foundation was provincially incorporated). *The foundation at the centre of the 2020 ethics investigation was assigned $543M of federal contribution agreements that never drew a dollar.* PA-confirmed; CORP silent because not federally incorporated.

3. **The 35,598 "Dissolution Pending" corps with FED grants stretching to 2032** — Aspire Food Group ($9.2M to 2033), Ukko Agro ($1.8M to 2031), Nexus Robotics, Ukko Agro. *The federal government has signed contribution agreements stretching seven years into the future with companies it is currently striking off the corporate registry for not filing annual returns.* Volume-shaped story: not one entity, but a category.

Story #1 is the safest live demo (high-profile, publicly known, the slide writes itself). Story #2 is the strongest *sole* example. Story #3 is the most damning *systemic* finding — best for the closing slide.

---

## 11. Optional: higher-recall paths (post-hackathon)

1. **Add `corp_corporations` as an 8th `general.entity_source_links` source.** Then golden records resolve federal corps to the same `bn_root` as CRA / FED / AB rows, lifting CORP recall from 80% to ~95% on incorporated FED recipients. ~2 hours of pipeline work.
2. **Trigram fuzzy match** on `pg_trgm` for both CORP and PA name lookups — same pattern as the lobby addendum. Use only as an alternative-name search on AMBIGUOUS verdicts.
3. **Backfill PA fiscal years 2003–2019.** PSPC publishes them at the same URL pattern; we currently load only 2020–2025 because that's the window of FED relevance. Older years would let us reason about long-tail historical patterns, but they don't help a one-day demo.
4. **Add Public Accounts contracts (Volume III, Section 3).** Same source publisher, separate set of CSVs (~610 MB for the unified contracts file). Extends the framework from grants to procurement and unlocks Challenges 4/5/9. Out of scope for this addendum.
