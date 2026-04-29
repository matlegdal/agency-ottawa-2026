# Zombie Agent — CHARSTAT Augmentation Addendum

> Companion to `zombie_agent_build_manual_v2.md`, `zombie_agent_v3_correctness_and_polish.md`, `zombie_agent_lobby_addendum.md`, `zombie_agent_corp_pa_addendum.md`, and `zombie_agent_web_presence_addendum.md`. Adds the CRA "List of Charities" registry (`charstat` schema) as **probe 9**. Read v2 + v3 first; this only documents the delta.

> **v3 alignment note.** This probe slots into v3 §D1's precedence chain on **both** the REFUTED side (CHECK 14) and the VERIFIED side (CHECK 15). It is registry-confirmed evidence, not a tie-breaker — same character as CORP probe 6. v3 §D8 (REFUTED is final) still applies: a CRA-revoked charity with a live federal agreement is REFUTED-as-zombie + Ghost Capacity lead, not a flippable VERIFIED.

---

## 1. What this adds

The eight existing probes break down as five government-side registry/payment probes (CRA-T3010, FED, AB, lobby, CORP, PA) and one recipient-side probe (web-presence). The **only** registry probe targeting charities specifically is CRA-T3010 (probe 1) — and T3010 is filing-driven, not status-driven. A charity that was revoked in 2021 and stopped filing is **invisible** in `cra.cra_identification` from 2022 onward.

CHARSTAT is the registry side of the same data: one row per charity regardless of filing, with explicit status (`Registered` / `Revoked` / `Annulled` / `Suspended`) and an effective date. It is to charities what CORP is to federal corporations — except with **100% BN-joinability** (every row has a 15-char CRA BN; every 9-digit root resolves cleanly).

The story shifts from

> "$2.4M to {entity}, no T3010 since 2022"

(absence of evidence) to

> "$2.4M to {entity}. **CRA officially revoked the charity on 2021-04-15** for failure to file annual returns. FED contributions continued for 287 days afterward."

(evidence of revocation + a quantified gap between revocation date and last grant-end). The "days funded after status change" number is the demo punchline this probe unlocks.

### Why this is not redundant with anything earlier

| Source | What it sees | What it misses |
|---|---|---|
| `cra.cra_identification` (T3010, probe 1) | Charities that filed a return in 2020–2024 | Revoked / Annulled / Suspended charities that stopped filing; effective dates of status changes |
| `corp.corp_corporations` (CORP, probe 6) | Federally-incorporated entities | Charities (most are provincially incorporated or by letters patent — see WE Charity in corp-pa addendum §10 Story 2: "no CORP match — provincially incorporated") |
| `pa.transfer_payments` (PA, probe 7) | Federal cash that actually moved ≥$100K | Status of the entity itself; smaller payments |
| `charstat.charity_status` (this probe, probe 9) | **Registry-confirmed registration status of every charity ever registered**, with effective date and sanction text | Non-charities (corporations not registered as charities — those are CORP's job) |

CHARSTAT is the missing complement to CORP. CORP covers ~1.56M federal corporations; CHARSTAT covers every CRA-registered charity (~150K active + ~50K formerly registered). Together they make registry-confirmed dissolution evidence available across the full spectrum of FED grant recipients.

---

## 2. Data shape, in one screen

### CHARSTAT — CRA charity registration status

- **Schema**: `charstat` (local Docker only — *not* on Render). Loaded by `CHARSTAT/npm run setup` (~30 seconds, single-CSV import).
- **Source**: CRA "List of Charities" public download — https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch (search-page button, not a stable URL). The operator clicks through; re-imports are idempotent (PK on `bn`).
- **Update cadence**: weekly (live snapshot from CRA). The local table tracks `source_snapshot_date` to make multi-import diffs visible.
- **Table**: `charstat.charity_status` — one row per charity (PK `bn` = 15-char CRA BN like `123456789RR0001`).
- **Pre-computed view**: `charstat.vw_zombie_candidates` — every non-`Registered` charity (Revoked / Annulled / Suspended).
- **Join keys**:
  1. **`bn_root` ←→ `LEFT(fed.recipient_business_number, 9)`** — direct, **100% BN-joinable on the charstat side** (every row has a clean 15-char BN). Same convention as `corp.business_number` and `general.entity_golden_records`.
  2. **`charity_name_norm`** ←→ same regex used everywhere else, as a backup for FED rows where `recipient_business_number` is `NULL`/`-`/placeholder.

### Status field — the verdict driver

| `status` value | Meaning | Verdict force |
|---|---|---|
| `Registered` | Charity is in good standing | Probe is **silent on the death side**; can REFUTE other death signals if `status_effective_date` is recent |
| `Revoked` | CRA cancelled the registration. Sub-categories carried in `sanction` when present: failure-to-file (administrative), non-compliance (regulatory), voluntary | **Decisive zombie verdict** — no charitable receipts, no CRA recognition |
| `Annulled` | Registration deemed never to have occurred (rare; for clerical errors or fraudulent registrations) | **Decisive zombie verdict** — stronger than Revoked for narrative purposes ("the registration was never valid") |
| `Suspended` | Receipting privileges suspended pending compliance (typically 1 year). Status is recoverable | **Strong zombie signal**, but not final — pair with an additional death signal |

### Sanction column

Optional CRA sanction text. When present, often gives the *reason* for the status:

- "Failure to file annual return" — administrative zombie (the most common revocation reason; cleanest narrative)
- "Issuing improper receipts" — regulatory action
- "Engaging in non-charitable activity" — substantive cause
- "Failure to maintain books and records" — governance failure

The `sanction` field is the bridge from "status changed" to "status changed *because* of X" — it lets the briefing card carry causation, not just chronology.

### Effective-date semantics (read this before querying)

`status_effective_date` means **different things** depending on `status`:

| status | What `status_effective_date` is |
|---|---|
| `Registered` | Original registration date (often decades old) |
| `Revoked` | Date of revocation order |
| `Annulled` | Date the annulment was granted |
| `Suspended` | Date the suspension started |

**For zombie detection always pair `status_effective_date` with a `status` filter.** Comparing effective dates across statuses without filtering is a precision bug — comparing a 1985 Registered date to a 2023 Revoked date will produce nonsense.

### Coverage reality check

| Probe | Source side | Match rate to FED candidates |
|---|---|---|
| 9 (CHARSTAT) | FED `recipient_business_number` (BN, 15-char or 9-digit) | ~40% of distinct FED recipients match (charities are a subset of all FED recipients) |
| 9 (CHARSTAT) | FED `recipient_legal_name` via `charity_name_norm` | ~5–10% additional via name matching (catches BN-NULL FED rows) |

CHARSTAT is **medium-recall, very high-precision** for charity recipients specifically. Among FED rows where the recipient is genuinely a CRA-registered charity, BN coverage is essentially 100%. The recall ceiling is determined by how many FED recipients are charities at all — many are corporations (CORP's territory), Indigenous bands, hospitals, universities, or municipalities (none of which carry CRA charity registrations).

---

## 3. The new probe

### Probe 9 — CHARSTAT

```sql
-- Inputs: $1 = legal_name (text), $2 = business_number (text, may be NULL or 15-char CRA BN)
WITH cand AS (
  SELECT
    NULLIF(regexp_replace(regexp_replace(lower($1),
      '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name,
    LEFT(NULLIF($2, ''), 9) AS bn9
)
SELECT
  cs.bn,
  cs.bn_root,
  cs.charity_name,
  cs.status,
  cs.status_effective_date::date         AS status_date,
  cs.sanction,
  cs.designation_code,
  cs.province,
  cs.source_snapshot_date::date          AS snapshot_date,
  CASE
    WHEN cand.bn9 IS NOT NULL AND cs.bn_root = cand.bn9 THEN 'bn'
    ELSE 'name'
  END                                    AS match_method
FROM charstat.charity_status cs, cand
WHERE
  (cand.bn9 IS NOT NULL AND cs.bn_root = cand.bn9)
  OR (cand.bn9 IS NULL AND cs.charity_name_norm = cand.norm_name)
LIMIT 1;
```

### Status interpretation — a verdict driver, not a tie-breaker

| `status` | Joined with… | Verdict |
|---|---|---|
| `Registered` AND `status_effective_date >= grant_end_year - 1` | (no other check needed) | **REFUTES** zombie reading — charity was registered as of the grant period or later |
| `Registered` AND `status_effective_date < grant_end_year - 1` | (registration is old) | Probe is **silent** — the charity is still registered but the date tells us nothing about activity |
| `Revoked` | (any) | **VERIFIED zombie** — strongest possible signal alongside CORP-Dissolved |
| `Annulled` | (any) | **VERIFIED zombie** — narrative-stronger than Revoked ("registration deemed never to have occurred") |
| `Suspended` | + at least one other death signal | **VERIFIED zombie** when paired; AMBIGUOUS-leaning-VERIFIED alone |
| (no row) | | Probe is **silent** — entity is either not a charity (likely → CORP probe applies) or pre-1989 lapsed registration (rare) |

### Days-funded-after-revocation — the headline metric

The unique number this probe enables, computable directly in SQL:

```sql
SELECT
  f.recipient_legal_name,
  cs.status,
  cs.status_effective_date,
  f.last_grant_end,
  (f.last_grant_end - cs.status_effective_date) AS days_funded_after_status_change
FROM (
  SELECT LEFT(recipient_business_number, 9) AS bn9,
         recipient_legal_name,
         MAX(agreement_end_date) AS last_grant_end
    FROM fed.grants_contributions
   WHERE recipient_business_number ~ '^[0-9]'
   GROUP BY 1, 2
) f
JOIN charstat.charity_status cs ON cs.bn_root = f.bn9
WHERE cs.status IN ('Revoked', 'Annulled', 'Suspended')
  AND f.last_grant_end > cs.status_effective_date
ORDER BY days_funded_after_status_change DESC;
```

This single column is what the probe contributes to the briefing card that no other probe produces.

---

## 4. How the verifier uses it

CHARSTAT is **two new checks (CHECK 14 and CHECK 15)** in v3 §D1's precedence chain. CHECK 14 is the REFUTED-side (still-registered charity); CHECK 15 is the VERIFIED-side (revoked/annulled charity).

**Why both sides.** CORP and CHARSTAT are *complements*, not substitutes — most FED charity recipients have NO CORP match because they're provincially incorporated. So CHARSTAT carries the registry-death signal alone for that population. Symmetrically, a `Registered` row with a recent `status_effective_date` is a clean cheap REFUTATION for the same population, parallel to CHECK 9 for federal corporations.

### Updated precedence chain (v3 + corp-pa addendum + web-presence addendum + this addendum)

```
1.  CHECK 5  (vw_agreement_current total < $1M)                  → REFUTED
2.  CHECK 0  (designation A or B)                                → REFUTED
3.  CHECK 9  (CORP Active + recent annual return)                → REFUTED
4.  CHECK 14 (CHARSTAT status='Registered' AND
              status_effective_date >= grant_end_year - 1)       → REFUTED
5.  CHECK 1  (T3010 filing window still open)                    → REFUTED
6.  CHECK 7  (entity rebranded)                                  → REFUTED
7.  CHECK 2b (FED agreement_end_date >= 2024-01-01)              → REFUTED
8.  CHECK 3  (any AB payment > 0 in FY2024-25 / FY2025-26)       → REFUTED
9.  CHECK 10 (PA recent payment)                                 → REFUTED
10. CHECK 15 (CHARSTAT status IN
              ('Revoked', 'Annulled', 'Suspended'))              → VERIFIED
11. CHECK 11 (CORP Dissolved or Dissolution Pending)             → VERIFIED
12. CHECK 8  (field_1570 = TRUE)                                 → VERIFIED
13. CHECK 12 (PA empty + ≥$100K + ≥12mo old)                     → VERIFIED
14. CHECK 6  (govt_share_of_rev < 70)                            → AMBIGUOUS
15. CHECK 13 (web-presence probe — AMBIGUOUS tie-breaker)        → AMBIGUOUS-coloring
16. otherwise (death signal fired AND nothing above triggered)   → VERIFIED
```

**Why these positions:**

- **CHECK 14 (CHARSTAT-Registered) before CHECK 1.** A clean `Registered` status with a recent `status_effective_date` (the date here is the *registration* or *most-recent-amendment* date — for `Registered` rows it confirms ongoing status) is the cheapest possible refutation for charity recipients. Slotting before CHECK 1 lets the verifier short-circuit on registry liveness without doing a T3010 lookup.
- **CHECK 15 (CHARSTAT-Revoked/Annulled/Suspended) before CHECK 11.** CRA charity revocation is at least as authoritative as Corporations Canada dissolution for charity recipients, and CHARSTAT covers provincial-incorp charities that CORP misses. Order them adjacent so the verifier picks the strongest evidence label without cascading. If both fire, they agree.
- **`Suspended` requires pairing.** CHECK 15 fires on `Suspended` only when at least one of CHECK 8 (field_1570), CHECK 11 (CORP), or CHECK 12 (PA empty) also fires. Suspension is recoverable; a lone Suspended status is AMBIGUOUS, not VERIFIED.

### Append to the verifier prompt

```
 14. Run the CHARSTAT probe. If status='Registered' AND
     status_effective_date >= grant_end_year - 1, emit REFUTED with
     "CRA charity registry shows charity is Registered as of {date}".
     This check fires near the top of the precedence chain — cheaper
     than T3010 lookups and works for charities CORP misses
     (provincially incorporated).

 15. (Continuing the CHARSTAT probe.) If status IN ('Revoked',
     'Annulled') emit VERIFIED with the status_effective_date as the
     primary evidence. Cite the status verbatim and include the
     sanction text when present (e.g. "CRA Revoked on 2021-04-15 for
     failure to file annual return"). Surface
     `(last_grant_end - status_effective_date)` as
     "days_funded_after_revocation" in the verdict reason — this is
     the headline number for the briefing card.

     If status='Suspended', emit VERIFIED only when at least one of
     CHECK 8, CHECK 11, or CHECK 12 also fires. A lone Suspended
     status is AMBIGUOUS — surface it but do not finalize.

 NOTE: status='Registered' with an OLD status_effective_date (more
 than 2 years before grant_end_year) is silent — the charity is
 still registered but the date is the original registration, not
 evidence of recent activity. Do not treat old Registered dates as
 REFUTATION.
```

### A concrete dual-signal example (a hypothetical revoked charity)

```
Step A surfaces:        Hypothetical Revoked Charity Foundation (BN 234567890)
CHECK 5  (≥$1M)         pass — $1.2M in vw_agreement_current
CHECK 0  (designation)  pass — designation C charitable organization
CHECK 9  (CORP active)  silent — provincially incorporated, no CORP match
CHECK 14 (CHARSTAT reg) silent — status='Revoked', not 'Registered'
CHECK 1  (T3010 open)   silent — last filing 2020, window closed
CHECK 7  (rebrand)      silent
CHECK 2b (live agreem.) silent — agreements wrapped 2022
CHECK 3  (AB payment)   silent
CHECK 10 (PA recent)    silent
CHECK 15 (CHARSTAT die) FIRES — status='Revoked', date 2021-04-15,
                        sanction='Failure to file annual return'

Verdict: VERIFIED on CHECK 15.
days_funded_after_revocation: 287 days
                              (agreement ended 2022-01-27;
                               revoked 2021-04-15)
Briefing chip: ✗ CRA Revoked 2021-04-15 (failure to file)
Headline: "$1.2M to a charity CRA revoked 287 days before the federal
          agreement ended — failure to file annual returns."
```

If CHECK 2b had fired (live agreement past 2024), the verdict flips to REFUTED-as-zombie + Ghost Capacity lead via §5.5 of the corp-pa addendum (extended below).

---

## 5. How the orchestrator uses it

### REFUTED is final (v3 §D8)

Repeating the v3 rule because CHARSTAT, like CORP, makes it especially tempting to bend: a verifier REFUTED on CHECK 2b (live federal agreement) **cannot** be flipped to VERIFIED via the iterative-exploration loop, even when CHARSTAT says the charity was Revoked. The Revoked-charity + live-agreement combination is a **Ghost Capacity lead** (§5.5 below extends the corp-pa addendum's sidebar), not a zombie.

### Step A — pre-enrich at gate time (v3 §D4 / §E4 compatible)

If you implement v3 §D4 (Step A live-agreement gate) and §E4 (pre-materialised candidate table), CHARSTAT can be pulled forward to gate time alongside CORP and PA. Add to Step A:

```sql
LEFT JOIN charstat.charity_status cs
       ON cs.bn_root = e.bn_root
-- ...
SELECT
  e.*,
  cs.status                  AS charstat_status,
  cs.status_effective_date   AS charstat_status_date,
  cs.sanction                AS charstat_sanction
```

Tie-break the candidate ranking by adding CHARSTAT to the existing CORP+PA composite:

```sql
ORDER BY
  -- Death-side composite
  (corp_status_code IN (3, 11))::int DESC,
  (charstat_status IN ('Revoked', 'Annulled'))::int DESC,
  (pa_total_paid IS NULL)::int DESC,
  -- Tie-breaks
  originals DESC
```

Triple-confirmed cases (CORP-Dissolved + CHARSTAT-Revoked + PA-empty) sort to the top automatically — these are the demo-grade stories.

### Step B — sweetening the candidate list (v2 §7, hour H11–12)

When ranking the 3–5 candidates to hand to the verifier, batch CHARSTAT alongside CORP and PA:

```sql
WITH fed_candidates AS (...)  -- top FED zombies by amount, from v2 query
SELECT
  fc.recipient_legal_name,
  fc.originals,
  c.current_status_label                             AS corp_status,
  c.dissolution_date::date,
  cs.status                                          AS charstat_status,
  cs.status_effective_date::date                     AS charstat_date,
  cs.sanction                                        AS charstat_sanction,
  rt.last_year                                       AS last_pa_year,
  rt.total_paid                                      AS pa_total,
  -- Composite score: prefer triple-confirmed cases for demo
  (CASE WHEN c.current_status_code IN (3, 11) THEN 1 ELSE 0 END
   + CASE WHEN cs.status IN ('Revoked', 'Annulled') THEN 1 ELSE 0 END
   + CASE WHEN rt.recipient_name_norm IS NULL THEN 1 ELSE 0 END)        AS dual_signal,
  -- The headline number this probe contributes
  CASE
    WHEN cs.status IN ('Revoked', 'Annulled', 'Suspended')
         AND fc.last_grant_end > cs.status_effective_date
    THEN (fc.last_grant_end - cs.status_effective_date)
  END                                                 AS days_funded_after_revocation
FROM fed_candidates fc
LEFT JOIN corp.corp_corporations c
       ON c.business_number = LEFT(NULLIF(fc.recipient_business_number, ''), 9)
       OR c.current_name_norm = fc.norm_name
LEFT JOIN charstat.charity_status cs
       ON cs.bn_root = LEFT(NULLIF(fc.recipient_business_number, ''), 9)
LEFT JOIN pa.vw_recipient_totals rt ON rt.recipient_name_norm = fc.norm_name
ORDER BY dual_signal DESC, days_funded_after_revocation DESC NULLS LAST, fc.originals DESC
LIMIT 10;
```

`days_funded_after_revocation DESC` is the secondary sort — when two candidates are equally death-signaled, prefer the one with the longest gap between revocation and last grant. That gap is the demo's most quotable number.

### Step C — defending an AMBIGUOUS verdict (v2 §7 iterative-exploration loop)

Two new follow-up patterns within the existing 3-query budget:

1. **Suspended-status timeline pull.** If CHARSTAT shows `Suspended` and the verifier returned AMBIGUOUS, check whether there's a more recent CRA decision — sometimes a suspension gets lifted, sometimes it converts to revocation. The current-snapshot table only has the *current* status; a re-query against a fresh download would surface the change. For the hackathon demo, the table is a single snapshot — note this as a known limitation.

2. **Sanction-text extraction.** When `sanction` is non-empty, parse it for the reason. The reason category determines narrative weight:
   - "Failure to file" → administrative zombie (most common, cleanest story)
   - "Non-compliance" / "Improper receipts" → regulatory zombie (stronger framing)
   - "Engaging in non-charitable activity" → substantive zombie (strongest framing)

Cap CHARSTAT follow-up queries to **1 per candidate**, alongside the existing 2-per-CORP+PA budget and 2-per-lobby budget. Total iterative-exploration budget remains **3 per candidate** from v2 §10.

### 5.5 Ghost Capacity leads — extending corp-pa §5.5

The corp-pa addendum's §5.5 sidebar uses CORP-Dissolved, T3010-self-dissolution, and AB-Cancelled as death-evidence sources. Add CHARSTAT to the table:

| Death evidence | Sidebar header phrasing |
|---|---|
| CORP `current_status_code = 11` (Dissolved) | "Federal corporate registry: Dissolved {date}" |
| CORP `current_status_code = 3` (Dissolution Pending) | "Federal corporate registry: striking off — {date}" |
| **CHARSTAT `status = 'Revoked'`** | **"CRA charity registry: Revoked {date} — {sanction}"** |
| **CHARSTAT `status = 'Annulled'`** | **"CRA charity registry: Annulled {date} (registration deemed never valid)"** |
| `field_1570 = TRUE` (charity self-dissolution) | "T3010 self-attests dissolution {fpe}" |
| AB `ab_non_profit.status = 'Cancelled'` or 'Struck' | "AB registry: {status}" |

The `sanction` text in the CHARSTAT-Revoked phrasing is the differentiator — Ghost Capacity leads where the federal government is paying out on agreements to charities CRA itself revoked **for failure to file annual returns** are the most narratively powerful sidebar candidates.

---

## 6. Briefing card surface

When the verifier emits a VERIFIED finding with non-empty CHARSTAT data, `publish_finding` should include four new fields:

```json
{
  "charstat_status": "Revoked",
  "charstat_status_date": "2021-04-15",
  "charstat_sanction": "Failure to file annual return",
  "days_funded_after_revocation": 287
}
```

UI rendering, in the chip row beneath the verifier verdict (alongside CORP and PA chips):

- **Charity status chip.** Red for Revoked / Annulled, orange for Suspended, green for Registered with recent date, hidden when no match. Hover shows the sanction text. Click opens the CRA public profile URL: `https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyRprtngPrd?q.bn={bn}`.
- **Days-funded-after-revocation badge.** When non-zero, render as a prominent number on the card body: e.g. *"287 days of federal funding after revocation."* This is the unique metric this probe contributes — give it visual weight.

Do not render CHARSTAT chips when the recipient has no CRA charity registration at all (no row in `charstat.charity_status`). Empty CHARSTAT for a non-charity is not a finding — it's a "wrong probe for this entity type" silent state.

### v3 §E1 dossier-panel extension

Add **sub-view 7 — CRA charity registry timeline.** Render the charity's status with its effective date as a single-row panel, with the sanction text quoted beneath when present, and a link to the live CRA profile. If CHARSTAT in a future version captures status history (currently snapshot-only), this becomes a vertical event list parallel to CORP's sub-view 4.

```sql
SELECT bn, charity_name, status, status_effective_date::date, sanction,
       designation_code, province
  FROM charstat.charity_status
 WHERE bn_root = $1
 LIMIT 1;
```

The dossier panel only renders for VERIFIED cards (per v3 §9 anti-pattern #11). Unlike CORP's sub-view 4 (full timeline) or PA's sub-view 5 (sparkline), CHARSTAT's sub-view is a single status panel — small, bright, and the most legible chip on the dossier for charity recipients.

---

## 7. Connecting to the database

Same options as the lobby and corp-pa addenda §7. The `charstat` schema is local-only:

1. **Local-only demo (recommended)**: point `READONLY_DATABASE_URL` at the local Docker DB. All eight schemas (`cra`, `fed`, `ab`, `general`, `lobby`, `corp`, `pa`, `charstat`) live there.
2. **Render demo with local fallback**: keep v2's Render URL for the four primary schemas; second connection for `lobby`/`corp`/`pa`/`charstat`. Costs an extra MCP server; skip unless local is unstable.

The v2 SQL-validation hook does not need changes — `charstat.*` table references parse identically.

---

## 8. Setup checklist (copy into the day-of runbook)

```bash
# 1. Bring up local Docker Postgres if not already running
docker compose up -d                            # from repo root

# 2. Download the CRA List of Charities CSV
#    Browser only — no stable URL.
#    Steps:
#      a. Open https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch
#      b. Leave all fields blank
#      c. Set Status dropdown to "All"
#      d. Click Search, scroll to bottom, click "Download results"
#      e. Save the CSV (or extract from ZIP) into CHARSTAT/data/raw/
#         Any filename ending in .csv works.

# 3. CHARSTAT setup (~30 seconds, single-CSV import)
cd CHARSTAT && npm install && npm run setup

# 4. Sanity check
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon \
  -c "SELECT status, COUNT(*) FROM charstat.charity_status GROUP BY 1 ORDER BY 2 DESC;"
# Expect: ~150K Registered, ~50K Revoked, plus small Annulled/Suspended counts

# 5. Smoke-test the dual-signal landing zone (top revoked-with-FED-money cases)
PGPASSWORD=qohash psql -h localhost -p 5434 -U qohash -d hackathon -v ON_ERROR_STOP=1 <<'SQL'
WITH dead AS (
  SELECT bn_root, charity_name, status, status_effective_date, sanction
    FROM charstat.charity_status
   WHERE status IN ('Revoked', 'Annulled', 'Suspended')
),
fed AS (
  SELECT LEFT(recipient_business_number, 9) AS bn9,
         recipient_legal_name,
         SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals,
         MAX(agreement_end_date) AS last_grant_end
    FROM fed.grants_contributions
   WHERE recipient_business_number ~ '^[0-9]'
   GROUP BY 1, 2
   HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 100000
)
SELECT f.recipient_legal_name, d.status, d.status_effective_date::date,
       f.originals, f.last_grant_end::date,
       (f.last_grant_end - d.status_effective_date) AS days_after_revocation
  FROM fed f JOIN dead d ON d.bn_root = f.bn9
 WHERE f.last_grant_end > d.status_effective_date
 ORDER BY days_after_revocation DESC
 LIMIT 10;
SQL
```

If step 5 returns at least 3 rows with `days_after_revocation > 30`, the demo's CHARSTAT story has material to work with.

---

## 9. Things to watch for during the demo

- **REFUTED is final (v3 §D8 cross-reference).** Even when CHARSTAT says Revoked, a live FED agreement (`agreement_end_date >= 2024-01-01`) still REFUTES the zombie verdict. Surface via §5.5 Ghost Capacity sidebar instead. Do not narrate "challenged → verified" on a CHECK-2b REFUTED, regardless of how strong the CHARSTAT signal is.
- **`Registered` with an old date is silent, not exculpatory.** A charity registered in 1985 that filed last in 2019 will still show `status='Registered'` until CRA processes a revocation — the registry is *cumulative*, not real-time. CHECK 14 only fires when `status_effective_date >= grant_end_year - 1`. Do not let the verifier treat any-Registered as REFUTATION.
- **`Annulled` is not the same as `Revoked`.** Annulment means the registration was deemed never valid — typically clerical error or fraud at registration time. Narratively stronger than revocation ("the registration was never legitimate"), but it's also rarer (a few hundred cases nationally). When it does fire, it's the strongest possible briefing card phrasing.
- **`Suspended` is recoverable.** Lone Suspended status is AMBIGUOUS, not VERIFIED — see CHECK 15's pairing requirement. Suspensions typically resolve within 12 months either by reinstatement or revocation; the CHARSTAT snapshot is a point-in-time read.
- **The CSV download is gated by a search-page button.** No `wget` recipe — operator clicks through. Re-downloads are idempotent (PK on `bn`). Keep one fresh export in `data/raw/` on demo day; older exports may show stale `Suspended` statuses that have since converted to `Revoked`.
- **Status localization.** CRA exports occasionally come back in French (`Révoqué`, `Annulé`, `Suspendu`). The importer canonicalizes these to English values; if a new localized string appears, it passes through unchanged — check `vw_zombie_candidates` for unexpected status values after import.
- **`bn` is 15-char; `bn_root` is 9-digit.** Always join via `bn_root` for cross-schema work. The 15-char `bn` is preserved for direct CRA-website lookups (e.g. dossier-panel "View on CRA" link).
- **Bilingual recipient names use `|` separator** in some FED rows. CHARSTAT does not use `|`. The verifier should split on `|` and try both halves of the FED legal_name when name-matching to CHARSTAT (same convention as PA in the corp-pa addendum).
- **Sanction text may be NULL even on Revoked rows.** CRA does not always populate the sanction column; older revocations especially are commonly NULL. Treat NULL sanction as "reason not published," not "no reason existed." Briefing card phrasing should fall back to the bare "CRA Revoked {date}" when sanction is empty.

---

## 10. The combined demo punchline (slide 2 candidates, refreshed)

The §10 candidates from the corp-pa addendum and web-presence addendum gain a fifth attribute. CHARSTAT primarily strengthens charity-recipient stories (Story 2 in particular).

### Story 2 — WE Charity Foundation (refreshed)

The corp-pa addendum noted that WE Charity is "no CORP match — provincially incorporated." CHARSTAT fills that exact gap if WE Charity is in the CRA registry (it is — registered as `WE CHARITY FOUNDATION` and `WE CHARITY`).

- **Headline (with CHARSTAT layered in):** *"$543M in federal contribution agreements to a CRA-registered charity, with zero payments visible in audited Public Accounts and a CRA registry status of {Registered/Revoked} as of {date}."*
- **Verifier walk delta:** CHECK 14 fires only if WE Charity's CRA status is `Registered` with a recent effective date (refutes). If status is `Revoked` or has not been updated post-2020, CHECK 15 fires alongside CHECK 8 (field_1570) and CHECK 12 (PA empty) — triple-confirmed VERIFIED.
- **Why this matters:** the WE story lacked a CORP signal under the corp-pa addendum because the entity isn't federally incorporated. CHARSTAT is the registry probe that *does* cover provincial charities, and is the right complement.

### Story 4 — The "days funded after revocation" pattern (new)

- **Headline:** *"{N} CRA-registered charities had their charitable status revoked while still drawing federal contributions. The longest gap between revocation and last grant payment is {M} days — agreements running for nearly a year after the federal government had already declared the recipient ineligible to operate as a charity."*
- **Verifier walk:** these stories fire on CHECK 15 alone (CHARSTAT-Revoked) when the agreement has wrapped pre-2024, or as Ghost Capacity leads via §5.5 when the agreement extends past 2024.
- **How to use it:** parallel closing-slide to Story 3 (the "Dissolution Pending" pattern from corp-pa). Where Story 3 generalizes from federal corps to a category, Story 4 generalizes from federal charities to a category. Both are systemic-pattern slides — pick one for the closing depending on what the candidate dataset surfaces strongest on demo day.

### Recommended ordering for a 4-minute pitch (refreshed)

1. **Story 1 (SDTC)** — well-known, dossier-panel-rich, CORP-led headline.
2. **Story 2 (WE Charity)** — CHARSTAT-led headline; different shape (PA-empty + CRA-status) shows reasoning across charity-specific evidence.
3. **Story 3 OR Story 4** as the closing pattern slide — pick whichever surfaces more candidates on demo day.

The CHARSTAT chip on Story 2's briefing card is the visible improvement vs the corp-pa-addendum baseline: where v3 / corp-pa had to fall back to T3010 absence and field_1570 self-attestation, CHARSTAT now shows a green-or-red registry chip with an effective date. The dossier panel for any charity recipient gets immediately more legible.

---

## 11. Optional: higher-recall paths (post-hackathon)

1. **Add `charstat.charity_status` as a 9th `general.entity_source_links` source.** Then golden records resolve charity revocations to the same `bn_root` as CRA / FED / AB rows, lifting CHARSTAT recall to 100% on charity-resolved entities. ~1 hour of pipeline work. Compatible with the lobby addendum §11 and corp-pa addendum §11 deterministic-only paths.
2. **Trigram fuzzy match on `pg_trgm`** for CHARSTAT name lookups — same pattern as lobby and corp-pa addenda. Use only as alternative-name search on AMBIGUOUS verdicts.
3. **Multi-snapshot history.** Currently a single point-in-time snapshot; CRA updates the listing weekly. A weekly cron downloading and appending to a `charstat.charity_status_history` table would let the agent reason about *when* a status changed within the year — distinguishing "Revoked 2 weeks before the agreement signed" from "Revoked 2 years after the agreement signed." Out of scope for hackathon; high-value for v3 of the dataset.
4. **Sanction-text classification.** Categorize the freeform `sanction` column into ~5 enum values (failure-to-file, improper-receipts, non-charitable-activity, governance-failure, voluntary). Strengthens the §5 narrative-weight categorization and lets the briefing card carry an icon for sanction type. ~1 hour of LLM-classification work over ~5K non-NULL sanctions.
5. **Pre-compute CHARSTAT into v3 §E4's candidate table** alongside CORP and PA. When v3 §E4 lands, fold CHARSTAT `status`, `status_effective_date`, and `sanction` into the same rows. The verifier becomes pure-classification — no SQL needed at probe time. Same single-biggest determinism win mentioned in the corp-pa addendum §11.
