---
name: zombie-detection
description: Recipe for finding federally-funded recipients that ceased operations shortly after receiving public money (Challenge 1 — Zombie Recipients). Use when investigating zombie/dissolution/disappearance questions.
---

# CHL clause map — what the literal challenge asks vs what we compute

The challenge text is literal. Every clause maps to a specific column or
filter in this skill so the dossier can be checked against the question
verbatim.

| CHL clause                                          | Where enforced                                                                                                                                                                                  |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| "companies AND nonprofits"                          | Step A `LEFT JOIN charity`; companies pass via the `no_post_grant_activity` branch                                                                                                              |
| "received large amounts of public funding"          | $1M cumulative `fed.vw_agreement_current` HARD GATE in the `exposure` CTE                                                                                                                       |
| "ceased operations shortly after"                   | Death-signal CASE expression — one of {t3010_self_dissolution, dissolved_and_stopped_filing, dissolved, stopped_filing, no_post_grant_activity}                                                  |
| "bankrupt"                                          | NOT directly observable in this dataset (no federal/provincial bankruptcy registry coverage). Disclose explicitly on the dossier — do not silently substitute. Most downstream bankruptcies show up as registry "dissolved" events, which IS captured. |
| "dissolved"                                         | `cra_financial_general.field_1570 = TRUE` (first-party, strongest) OR `ab.ab_non_profit.status` ILIKE dissolved/struck/inactive/revoked                                                          |
| "stopped filing"                                    | `cra_identification.last_fy <= 2022` for designation C charities                                                                                                                                 |
| "within 12 months of receiving funding"             | `months_grant_to_death_signal` SORTABLE column (NOT a hard gate; partial 2024 data + AB-only-dissolution cases produce NULLs). Closer to 12 = stronger CHL match                                |
| "Flag entities where public funding makes up more than 70-80% of total revenue" | `cra.govt_funding_by_charity.govt_share_of_rev >= 70` on the most-recent clean filing (Step E). REQUIRED to compute for every charity candidate                                                 |
| "could not survive without it"                      | Same as above — high govt-share-of-rev is the operationalization                                                                                                                                |
| "did the public get anything for its money?"        | Surface `cra.overhead_by_charity` (admin+fundraising / programs) on the dossier when available; for non-charity recipients, surface program/agreement description from `fed.vw_grants_decoded`  |

# Filters applied before any candidate enters consideration

EXCLUDE entities whose `cra.cra_identification.designation` is **A** (public
  foundation) or **B** (private foundation). Per `CRA/CLAUDE.md`, both
  foundation designations exist to distribute grants to other charities, not
  to deliver programs themselves. They are STRUCTURALLY allowed to have low
  or zero operating revenue and may carry a high `govt_share_of_rev` for
  legitimate accounting reasons (endowment draws, government-funded grant
  programs). The CHL "70-80% revenue dependency" flag does not interpret
  cleanly for them. Only **designation C** (charitable organization, ~80%
  of all charities) is investigated by default. NOTE: A is *public*, B is
  *private* — earlier drafts of this skill had the labels swapped.

EXCLUDE entities whose most recent observed `fiscal_year_end + 6 months`
  is AFTER the CRA scrape effective date. Their T3010 filing window is
  still open, so "missing recent filing" is not yet a real signal. See
  the `data-quirks` skill for the math.

# What counts as a zombie

An entity that received material federal or provincial public funding and
shows no operating signs of life afterwards. Operationalized:

1. **Cumulative federal funding ≥ $1,000,000 (current commitment from
   `fed.vw_agreement_current` — not the originals-only sum and not
   the entity-resolved roll-up).** This is a HARD GATE. If the
   `vw_agreement_current` total for the BN is below $1,000,000, drop the
   candidate even if you already published it as `pending` — re-publish
   as `refuted` with reason "below $1M material-funding threshold". The
   $1M cutoff operationalizes CHL's "large amounts"; CHL itself does not
   pin a number.
2. **T3010 self-reported dissolution**: `cra_financial_general.field_1570
   = TRUE` ("Has the charity wound-up, dissolved, or terminated
   operations?"). This is FIRST-PARTY CHL "dissolved" evidence — the
   charity itself reported cessation on its T3010. Strictly stronger
   than absence-of-filing inference.
3. **Stopped filing**: No CRA T3010 filing in any year after the last grant
   (operationalized as `cra_identification.last_fy <= 2022` for the
   2018–2022 funding window).
4. **No FED/AB activity post-grant**: No appearance in subsequent FED
   grants or AB grants in 2024+ — see the "live-agreement test" below
   for what "appearance" means.
5. **AB corporate registry dissolution**: `ab.ab_non_profit.status`
   indicates dissolved, struck, inactive, or revoked. ROOT `CLAUDE.md`
   lists this as a primary data source for this challenge. When
   present, it satisfies CHL's "dissolved" alternative on its own —
   independent of T3010 silence.
6. **CHL-mandated dependency flag**: `govt_share_of_rev >= 70` on the
   most-recent clean CRA filing (from `cra.govt_funding_by_charity` with
   the impossibility/plausibility filters). This is the literal CHL
   "70-80%" criterion — *required* to compute for every candidate, not
   optional. A candidate that ceased operations AND was
   govt-revenue-dependent is the strongest CHL form of zombie.

A finding is strong when (1) holds AND at least one of (2, 3, 4, 5)
holds AND (6) holds. Signal (2) is the strongest single death signal
(first-party reported); (5) is the second strongest (registry-of-record);
(3) is third (inferred from absence); (4) is the fallback for non-charity
recipients without registry coverage.

## Live-agreement test — disqualifies a candidate

A candidate is NOT a zombie if any FED agreement is still active:

  - `agreement_end_date >= '2024-01-01'` AND `agreement_end_date >=
    agreement_start_date` on ANY row tied to the BN (the second clause
    rejects the 947 F-9 corrupt-date rows where end < start — those are
    publisher defects, not real live agreements), OR
  - The latest amendment for any agreement carries `amendment_date >=
    '2024-01-01'` (the agreement was being modified after the cutoff).

Active multi-year delivery contracts that started pre-2024 but run past
2024-01-01 fail the zombie test. They may be Challenge 2 (Ghost Capacity)
candidates if delivery capacity is missing — but that is a different
investigation. Refute them as zombies, do not blur the categories.

## How to compute "total federal exposure (CAD)" — the dossier number

For every published candidate, the `total_funding_cad` field on the
finding card MUST equal:

  - `SUM(agreement_value) FROM fed.vw_agreement_current
     WHERE LEFT(NULLIF(recipient_business_number,''),9) = <bn_root>`.

`fed.vw_agreement_current` is the canonical mitigation for both F-3
(cumulative-amendment-double-counting) and F-1 (ref_number collisions
across distinct recipients) — the view's own `DISTINCT ON` includes a
recipient disambiguator, so a naïve `DISTINCT ON (ref_number)`-only CTE
must NOT be used in its place.

Do NOT compute exposure by:
  - Summing `agreement_value` over the raw base table (F-3
    cumulative-double-counting).
  - Using a `DISTINCT ON (ref_number)`-only CTE without a recipient
    disambiguator — this silently mis-attributes 41,046 colliding
    ref_numbers (KDI F-1).
  - Aggregating across `general.entity_source_links` to the entity (this
    catches predecessor entities and pre-BN name variants and inflates the
    figure — see the Acadia Centre / Northwest Inter-Nation lessons).

If the BN-anchored `agreement_current` total is below $1M, the candidate
fails Rule 1 above and must be refuted.

# Investigation steps

## Step A — DETERMINISTIC candidate enumeration (one query, every gate)

Run this query EXACTLY as written. It returns the FULL ranked list of
zombie candidates that pass every hard gate, sorted by total committed
exposure descending. Same database state → same candidate list every
run. This is the single point of candidate selection — do not author a
different shortlist.

```sql
-- Step A: deterministic zombie candidate enumeration
-- CHL: "Which companies and nonprofits received large amounts of public
-- funding and then ceased operations shortly after?" — universe is broader
-- than registered charities. Universe = every BN-anchored federal recipient
-- 2018-2022 with cumulative commitment >= $1M, with a CHL-recognized death
-- signal: T3010 self-reported dissolution (field_1570=TRUE) OR AB-registry
-- dissolution OR T3010 silence (designation C only) OR no post-grant
-- activity for non-charity recipients.
WITH exposure AS (
  -- Per-BN-root cumulative exposure on agreements SIGNED 2018-2022.
  -- fed.vw_agreement_current handles F-3 (cumulative double-count) AND F-1
  -- (ref_number collisions) by construction. $1M HARD GATE.
  SELECT LEFT(NULLIF(recipient_business_number,''), 9) AS bn_root,
         MIN(recipient_legal_name) AS recipient_name,
         MIN(recipient_type)       AS recipient_type,
         SUM(agreement_value)      AS total_committed_cad,
         MAX(agreement_end_date)   AS latest_end_date,
         COUNT(DISTINCT ref_number) AS n_agreements
  FROM fed.vw_agreement_current
  WHERE LEFT(NULLIF(recipient_business_number,''), 9) ~ '^[1-9][0-9]{8}$'
    AND agreement_start_date BETWEEN '2018-01-01' AND '2022-12-31'
  GROUP BY 1
  HAVING SUM(agreement_value) >= 1000000
),
charity AS (
  -- T3010 registration state per BN root. NULL via LEFT JOIN for
  -- non-CRA-registered recipients (companies, foreign entities, etc.).
  -- NOTE: cra.cra_identification has no `fpe` column (v3 baseline bug);
  -- the actual fiscal-period-end date lives on cra.cra_financial_general
  -- and is sourced via the separate `charity_fpe` CTE below.
  SELECT LEFT(bn,9) AS bn_root,
         MAX(fiscal_year) AS last_fy,
         MAX(designation) AS designation
  FROM cra.cra_identification
  GROUP BY 1
),
charity_fpe AS (
  -- last_fpe = the actual fiscal-period-end date of the most recent
  -- T3010 filing for this BN, used by the 12-month-proximity column
  -- below. Sourced from cra_financial_general (which carries fpe);
  -- cra_identification only has integer fiscal_year, not the day-precise
  -- fpe needed for the months_grant_to_death_signal calculation.
  SELECT LEFT(bn, 9) AS bn_root,
         MAX(fpe)    AS last_fpe
  FROM cra.cra_financial_general
  GROUP BY LEFT(bn, 9)
),
cra_self_dissolved AS (
  -- Charities that affirmatively answered "Yes" to T3010 line A2
  -- (field_1570 = TRUE): "Has the charity wound-up, dissolved, or
  -- terminated operations?" This is FIRST-PARTY CHL "dissolved"
  -- evidence — the charity itself reported cessation. Strictly stronger
  -- than the absence-based T3010-silence signal.
  SELECT LEFT(fg.bn, 9) AS bn_root,
         MAX(fg.fpe)    AS dissolution_fpe
  FROM cra.cra_financial_general fg
  WHERE fg.field_1570 = TRUE
  GROUP BY LEFT(fg.bn, 9)
),
ab_dissolved AS (
  -- Alberta non-profits whose registry status indicates dissolved /
  -- struck / inactive / revoked. ROOT-CLAUDE Challenge 1 row names
  -- this as a primary data source ("ab.ab_non_profit (status=dissolved
  -- /struck)"). This is the CHL "dissolved" death signal alongside
  -- "stopped filing".
  SELECT DISTINCT egr.bn_root,
         MIN(np.legal_name) AS ab_legal_name,
         MIN(np.status)     AS ab_status
  FROM ab.ab_non_profit np
  JOIN general.entity_source_links esl
    ON esl.source_schema = 'ab'
   AND esl.source_table  = 'ab_non_profit'
   -- ab_non_profit.id is UUID locally; cast the JSONB pk-key string to
   -- uuid (NOT int) to match. ab_grants.id below is INTEGER, hence the
   -- different cast in that JOIN.
   AND (esl.source_pk->>'id')::uuid = np.id
  JOIN general.entity_golden_records egr ON egr.id = esl.entity_id
  WHERE np.status ILIKE '%dissolved%'
     OR np.status ILIKE '%struck%'
     OR np.status ILIKE '%inactive%'
     OR np.status ILIKE '%revoked%'
  GROUP BY egr.bn_root
)
-- CORP and PA columns below (cc.*, pt.*) are attached as evidence for
-- the verifier and the dossier panel; they DO NOT participate in
-- candidate selection or ordering. The candidate set and its sort order
-- are governed solely by the existing gates and `total_committed_cad
-- DESC` (see system_prompt.py determinism contract — same DB state must
-- produce the same candidate list and ordering every run).
SELECT
  e.bn_root,
  e.recipient_name,
  e.recipient_type,
  ROUND(e.total_committed_cad::numeric/1e6, 2) AS total_M,
  e.latest_end_date,
  e.n_agreements,
  c.last_fy      AS last_t3010_year,
  cf.last_fpe    AS last_t3010_fpe,
  c.designation,
  d.ab_status    AS ab_dissolution_status,
  s.dissolution_fpe AS t3010_self_dissolution_fpe,
  -- Which CHL death signal fired (CHL: "bankrupt, dissolved, or stopped filing").
  -- Priority: self-reported dissolution > AB-registry dissolution > T3010
  -- silence > non-charity post-grant absence. (Bankruptcy not directly
  -- observable in this dataset; folded into "dissolved" via downstream
  -- registry events. The dossier should disclose this coverage gap rather
  -- than silently substitute.)
  CASE
    WHEN s.bn_root IS NOT NULL                                               THEN 't3010_self_dissolution'
    WHEN d.bn_root IS NOT NULL AND c.designation = 'C' AND c.last_fy <= 2022 THEN 'dissolved_and_stopped_filing'
    WHEN d.bn_root IS NOT NULL                                               THEN 'dissolved'
    WHEN c.designation = 'C' AND c.last_fy <= 2022                           THEN 'stopped_filing'
    WHEN c.bn_root IS NULL                                                   THEN 'no_post_grant_activity'
    ELSE NULL
  END AS death_signal,
  -- 12-MONTH PROXIMITY (CHL: "within 12 months of receiving funding").
  -- Months between latest_end_date (last FED agreement payment window
  -- closed) and the death-event date. The death-event date depends on
  -- which signal fired:
  --   * t3010_self_dissolution → s.dissolution_fpe (decisive first-party)
  --   * stopped_filing / dissolved_and_stopped_filing → c.last_fpe + 12mo
  --     (we observed the last filing on c.last_fpe; the "death event" is
  --     the next expected filing they didn't make)
  --   * dissolved (AB-only) / no_post_grant_activity → NULL (no event date)
  -- This is a SORTABLE column, NOT a hard gate. CHL's "12 months" is the
  -- literal CHL test for "shortly after"; smaller values are stronger
  -- CHL matches. Surface it on the dossier card so the reader can judge
  -- proximity directly. NULL means we can't compute it for this signal.
  CASE
    WHEN s.dissolution_fpe IS NOT NULL AND e.latest_end_date IS NOT NULL THEN
      (EXTRACT(YEAR  FROM age(s.dissolution_fpe, e.latest_end_date))::int * 12
     + EXTRACT(MONTH FROM age(s.dissolution_fpe, e.latest_end_date))::int)
    WHEN cf.last_fpe IS NOT NULL AND c.last_fy <= 2022 AND e.latest_end_date IS NOT NULL THEN
      (EXTRACT(YEAR  FROM age(cf.last_fpe + INTERVAL '12 months', e.latest_end_date))::int * 12
     + EXTRACT(MONTH FROM age(cf.last_fpe + INTERVAL '12 months', e.latest_end_date))::int)
    ELSE NULL
  END AS months_grant_to_death_signal,
  -- CORP+PA pre-enrich (addendum §5.2). Evidence only — see banner above
  -- the SELECT for the determinism contract. NULL when no match.
  cc.corporation_id           AS corp_corporation_id,
  cc.current_status_code      AS corp_status_code,
  cc.current_status_label     AS corp_status_label,
  cc.current_status_date::date AS corp_status_date,
  cc.dissolution_date::date   AS corp_dissolution_date,
  cc.last_annual_return_year  AS corp_last_filing_year,
  pt.last_year                AS pa_last_year,
  pt.total_paid::bigint       AS pa_total_paid_cad
FROM exposure e
LEFT JOIN charity            c  ON c.bn_root  = e.bn_root
LEFT JOIN charity_fpe        cf ON cf.bn_root = e.bn_root
LEFT JOIN ab_dissolved       d  ON d.bn_root  = e.bn_root
LEFT JOIN cra_self_dissolved s  ON s.bn_root  = e.bn_root
-- CORP: federal corporate registry (status, dissolution_date, last
-- annual return). Local-only schema. business_number is the 9-digit BN
-- root, matching e.bn_root directly. NULL row for non-federally-
-- incorporated recipients (provincial corps, foreign entities, etc.) is
-- normal and must NOT trigger any gate.
--
-- BN reuse: ~16K of ~1.4M BN'd corps share a BN with at least one other
-- corp (Kinectrics-shape). A naive JOIN multiplies rows. We pick the
-- single most-recent CORP record per BN deterministically via
-- DISTINCT ON so Step A's row count and ordering remain stable. The
-- verifier still runs CHECK 11's temporal gate to reject pre-grant
-- dissolutions that survive this pre-enrich step.
LEFT JOIN LATERAL (
  SELECT corporation_id, current_status_code, current_status_label,
         current_status_date, dissolution_date, last_annual_return_year
  FROM corp.corp_corporations
  WHERE business_number = e.bn_root
  ORDER BY current_status_date DESC NULLS LAST,
           corporation_id DESC
  LIMIT 1
) cc ON TRUE
-- PA: audited Public Accounts recipient totals. Name-based match against
-- pa.vw_recipient_totals.recipient_name_norm — same regex PA used on
-- load (see PA/scripts/02-import.js). NULL for recipients below the PA
-- $100K threshold or whose name doesn't normalize identically; that is
-- evidence for CHECK 12, not a Step A gate.
LEFT JOIN pa.vw_recipient_totals pt
       ON pt.recipient_name_norm = lower(
            regexp_replace(regexp_replace(coalesce(e.recipient_name, ''),
              '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'))
WHERE
  -- Foundations excluded: A=public, B=private; both have low operating
  -- revenue by design and CHL's 70-80% rule does not interpret cleanly.
  (c.designation IS NULL OR c.designation NOT IN ('A','B'))
  -- At least one CHL-recognized death signal must fire
  AND (
       -- (a) T3010 self-reported dissolution (field_1570 = TRUE)
       --     This is first-party CHL "dissolved" evidence.
       (s.bn_root IS NOT NULL)
       -- (b) AB non-profit registry says dissolved/struck/inactive/revoked
       OR (d.bn_root IS NOT NULL)
       -- (c) Stopped filing T3010 (charities, designation C)
       OR (c.designation = 'C' AND c.last_fy <= 2022)
       -- (d) Companies / unregistered nonprofits with no post-grant activity
       OR (
         c.bn_root IS NULL
         -- Exclude operationally publicly-funded non-charity entities from
         -- this branch. These are governments, police services, school
         -- boards, hospitals, universities — they may go quiet in the FED
         -- dataset because their funding rolled to a non-FED federal-
         -- provincial program (e.g. Treaty Three Police Service Board has
         -- ongoing federal-First-Nations policing agreements that aren't in
         -- this dataset's later years), not because they ceased operations.
         -- AB grants are ALSO not a meaningful liveness signal for them
         -- (an Ontario police service is never expected to receive AB
         -- grants), which is why the absence of AB activity below would
         -- otherwise wrongly fire the zombie signal.
         AND e.recipient_name !~* (
           '\m(POLICE|POLICING|TRIBAL POLICE|FIRST NATION|BAND COUNCIL|'
           'GOVERNMENT OF|MINISTRY OF|MINISTÈRE|CITY OF|CITÉ DE|'
           'MUNICIPALITY OF|MUNICIPALITÉ|TOWN OF|VILLE DE|VILLAGE OF|'
           'REGIONAL DISTRICT|REGIONAL MUNICIPALITY|COUNTY OF|'
           'COLLEGE OF|UNIVERSITY OF|UNIVERSITÉ|HOSPITAL|HÔPITAL|'
           'HEALTH AUTHORITY|HEALTH CENTRE|REGIE DE LA SANTÉ|'
           'SCHOOL DIVISION|SCHOOL DISTRICT|SCHOOL BOARD|'
           'COMMISSION SCOLAIRE|SCHOOL AUTHORITY|PUBLIC LIBRARY)\M'
         )
         AND NOT EXISTS (
           SELECT 1 FROM ab.ab_grants ag
           JOIN general.entity_source_links esl
             ON esl.source_schema = 'ab'
            AND esl.source_table  = 'ab_grants'
            AND (esl.source_pk->>'id')::int = ag.id
           JOIN general.entity_golden_records egr ON egr.id = esl.entity_id
           WHERE egr.bn_root = e.bn_root
             AND ag.display_fiscal_year IN ('2024 - 2025','2025 - 2026')
             AND ag.amount > 0
         )
       )
     )
  -- No NEW federal agreement signed in 2024+
  AND NOT EXISTS (
    SELECT 1 FROM fed.grants_contributions
    WHERE LEFT(NULLIF(recipient_business_number,''),9) = e.bn_root
      AND agreement_start_date >= '2024-01-01')
  -- No federal AMENDMENT activity in 2024+ (agreement is dormant)
  AND NOT EXISTS (
    SELECT 1 FROM fed.grants_contributions
    WHERE LEFT(NULLIF(recipient_business_number,''),9) = e.bn_root
      AND amendment_date >= '2024-01-01')
  -- No FED agreement extends INTO 2024+ — gate-side enforcement of the
  -- live-agreement disqualifier defined under "Live-agreement test"
  -- above. Catches zero-amendment multi-year contracts (e.g. CIC
  -- settlement-services agreements running to 2025-03-31). The
  -- end_date >= start_date guard drops the 947 KDI F-9 corrupt-date rows
  -- where end < start.
  AND NOT EXISTS (
    SELECT 1 FROM fed.grants_contributions
    WHERE LEFT(NULLIF(recipient_business_number,''),9) = e.bn_root
      AND agreement_end_date >= '2024-01-01'
      AND agreement_end_date >= agreement_start_date)
ORDER BY e.total_committed_cad DESC;
```

This query enforces:
1. **$1M hard gate** via `HAVING SUM(...) >= 1000000`. The threshold is an
   operationalization of CHL's "large amounts" — not in CHL itself.
2. **2018–2022 commitment window** via `agreement_start_date BETWEEN`. This
   is a runtime convenience (the agent expects to observe at least 1.5
   years of post-grant behavior); CHL itself doesn't pin a window. The
   per-candidate "within 12 months of receiving funding" (CHL) is
   approximated by combining this window with `last_fy <= 2022`.
3. **CHL-faithful universe**: `LEFT JOIN` to charity table — companies
   AND nonprofits both pass (CHL: "*companies and nonprofits*"). KDI F-7
   note: 16.3% of `recipient_type='N'` rows have missing BN; those are
   excluded by the `^[1-9][0-9]{8}$` BN format guard. Resolving them via
   name+entity matching is out of scope for this single deterministic
   query.
4. **Foundations excluded**: `designation NOT IN ('A','B')`. A is public
   foundation, B is private foundation. Both have structurally low
   operating revenue.
5. **CHL death signals (one of three required)**:
   - `stopped_filing`: charity (designation C) with `last_fy <= 2022`
   - `dissolved`: BN appears in `ab.ab_non_profit` with a dissolution-
     equivalent status
   - `no_post_grant_activity`: non-CRA recipient with no AB grants
     2024-25/2025-26 (the negative-amount filter neutralizes A-6 reversals)
6. **No new federal commitments in 2024+** (`agreement_start_date`).
7. **No federal amendment activity in 2024+** (`amendment_date`). An
   agreement still being amended after the cutoff means the relationship
   is alive — REFUTED.
8. **Live-agreement disqualifier**: NOT EXISTS any agreement with
   `agreement_end_date >= '2024-01-01'` AND `end_date >= start_date`.
   This is the gate-side enforcement of the rule defined under the
   "Live-agreement test" header above. Catches zero-amendment multi-year
   contracts (e.g. a 2020-signed 5-year contract that runs to 2025-03-31
   and was never amended). The agreement is ALIVE even if no new
   agreements have started — refute as zombie. Such candidates may be
   Challenge 2 (Ghost Capacity) leads if delivery capacity is missing,
   but that is a different investigation.

Running this query produces the deterministic candidate list. The
ordering is determined by `total_committed_cad DESC`, so when we surface
the top N, we always show the biggest verified zombies.

## Step A1 — universe + gate counts (publish ONCE)

Run this query exactly once, immediately after Step A. It reports the
pre-gate universe size and how many candidates each successive gate
dropped, so the audience can audit the WHOLE methodology, not just the
survivors. Pass the five counts to `mcp__ui_bridge__publish_universe`.

```sql
-- Step A1: universe + gate counts
WITH exposure AS (
  SELECT LEFT(NULLIF(recipient_business_number,''), 9) AS bn_root,
         SUM(agreement_value) AS total_committed_cad
  FROM fed.vw_agreement_current
  WHERE LEFT(NULLIF(recipient_business_number,''), 9) ~ '^[1-9][0-9]{8}$'
    AND agreement_start_date BETWEEN '2018-01-01' AND '2022-12-31'
  GROUP BY 1
  HAVING SUM(agreement_value) >= 1000000
),
charity AS (
  SELECT LEFT(bn,9) AS bn_root,
         MAX(fiscal_year) AS last_fy,
         MAX(designation) AS designation
  FROM cra.cra_identification GROUP BY 1
),
not_foundation AS (
  SELECT e.* FROM exposure e
  LEFT JOIN charity c ON c.bn_root = e.bn_root
  WHERE c.designation IS NULL OR c.designation NOT IN ('A','B')
),
not_live_agreement AS (
  SELECT * FROM not_foundation nf
  WHERE NOT EXISTS (
    SELECT 1 FROM fed.grants_contributions
    WHERE LEFT(NULLIF(recipient_business_number,''),9) = nf.bn_root
      AND ((agreement_start_date >= '2024-01-01')
        OR (amendment_date >= '2024-01-01')
        OR (agreement_end_date >= '2024-01-01'
            AND agreement_end_date >= agreement_start_date)))
)
SELECT
  (SELECT COUNT(*) FROM exposure)            AS n_universe_pre_gate,
  (SELECT COUNT(*) FROM not_foundation)      AS n_after_foundation_filter,
  (SELECT COUNT(*) FROM not_live_agreement)  AS n_after_live_agreement_filter,
  (SELECT COUNT(*) FROM not_live_agreement)  AS n_after_non_charity_filter,
  -- n_final_candidates is the row count of Step A's main query — pass
  -- that value directly from Step A's result row count, not re-derived
  -- here. The non-charity-filter column is mirrored from
  -- not_live_agreement above because the regex filter applies inside one
  -- branch of the death-signal disjunction (see Step A); modeling it as
  -- a clean intersection here would over-report drops.
  (SELECT COUNT(*) FROM not_live_agreement)  AS n_pre_death_signal;
```

Then call:

```
mcp__ui_bridge__publish_universe(
  n_universe_pre_gate=<col 1>,
  n_after_foundation_filter=<col 2>,
  n_after_live_agreement_filter=<col 3>,
  n_after_non_charity_filter=<col 4>,
  n_final_candidates=<row count of Step A>,
  narrative="Universe: <U> recipients with cumulative federal commitment "
            "≥ $1M between 2018-2022. Gates dropped: foundations (-X), "
            "live federal agreements running past 2024-01-01 (-Y); "
            "<N> remained after a death signal was required.",
  sql_trail=["Step A1: universe + gate counts", "Step A: deterministic ..."]
)
```

The narrative is a TEMPLATED format string — fill in the integers from
the row above. Do NOT estimate or round. The audience sees these numbers
and can audit them against the database directly.

## Step B — verify EVERY candidate, then sort verified by $ desc

The orchestrator delegates each candidate from Step A to the verifier
subagent for an independent paranoid cross-check. Then surface the
verified ones in $-descending order.

If Step A returns more than 5 candidates, you may cap verification at
the top 10 by total_committed_cad to bound runtime — but if it returns
≤ 5, verify all of them.

## Step C — Alberta liveness (per candidate)

For each candidate from Step A, also check Alberta payments. The deterministic
gate above is FED-only; the AB liveness signal is a secondary refinement.

```sql
-- Step C: any AB payments in FY 2024-25 / 2025-26?
-- Alberta fiscal year runs April 1 → March 31; display_fiscal_year is the
-- canonical "YYYY - YYYY" label (e.g. "2024 - 2025" = 2024-04-01 → 2025-03-31).
-- KDI A-6 / A-13: 50K negative reversal rows + 5.5K exact duplicates +
-- 951 perfect-reversal pairs in the AB CSV years. Filter `amount > 0` so
-- a refund-pair doesn't masquerade as a "live" payment.
SELECT COUNT(*) FILTER (WHERE ag.amount > 0) AS n_positive_payments,
       COALESCE(SUM(ag.amount) FILTER (WHERE ag.amount > 0), 0) AS gross_paid,
       COALESCE(SUM(ag.amount), 0)                              AS net_paid
FROM ab.ab_grants ag
JOIN general.entity_source_links esl
  ON esl.source_schema = 'ab'
 AND esl.source_table  = 'ab_grants'
 AND (esl.source_pk->>'id')::int = ag.id
JOIN general.entity_golden_records egr ON egr.id = esl.entity_id
WHERE egr.bn_root = $1
  AND ag.display_fiscal_year IN ('2024 - 2025', '2025 - 2026');
```

The candidate is REFUTED as a zombie when `n_positive_payments > 0` AND
`net_paid` is materially non-zero (e.g. > $1,000 to allow for small
admin reversals). If `gross_paid > 0` but `net_paid` is near zero, the
"payments" netted out to a wash — that is itself a structurally weird
signal and should be flagged in `evidence_summary`, not silently treated
as either zombie or alive.

## Step D — resolve to canonical entity

Look each surviving candidate up in `general.vw_entity_funding` so you
have one canonical name, every alias, and the cross-dataset roll-up
(useful for the briefing card body). NOTE: `total_funding_cad` on the
finding card must still come from the BN-anchored `agreement_current`
total computed in Step A — do NOT replace it with the entity-resolved
roll-up.

## Step E — funding dependency (REQUIRED, not optional)

CHL line 15: *"Flag entities where public funding makes up more than 70-80%
of total revenue, meaning they likely could not survive without it."* This
is a **CHL-mandated reportable signal**, not a nice-to-have. Compute it
for every candidate and surface it on the finding card.

Use the pre-computed `cra.govt_funding_by_charity` table directly. It
ships per-`(bn, fiscal_year)` `total_govt`, `revenue`, and
`govt_share_of_rev` (0–100), already grouped from `cra_financial_details`.
**Important caveat:** the build script does NOT filter
`cra.t3010_impossibilities` upstream — apply the filter yourself when
querying so a $5B-typo year doesn't poison the ratio.

```sql
-- Step E: govt-share-of-revenue from the pre-computed table, with
-- impossibility-row exclusion applied at query time (the build script
-- doesn't pre-filter these).
-- DO NOT remove the t3010_impossibilities filter or the
-- PLAUS_MAGNITUDE_OUTLIER filter. cra.govt_funding_by_charity is built
-- without them (CRA/scripts/advanced/08-government-funding-analysis.js);
-- a $5B unit-error year can flip the dependency flag without these
-- guards.
SELECT gfc.bn,
       gfc.fiscal_year,
       gfc.total_govt,
       gfc.revenue,
       gfc.govt_share_of_rev      -- percent, 0-100
FROM cra.govt_funding_by_charity gfc
WHERE LEFT(gfc.bn, 9) = $1
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_impossibilities ti
    WHERE ti.bn = gfc.bn
      AND EXTRACT(YEAR FROM ti.fpe)::int = gfc.fiscal_year
  )
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_plausibility_flags pf
    WHERE pf.bn = gfc.bn
      AND EXTRACT(YEAR FROM pf.fpe)::int = gfc.fiscal_year
      AND pf.rule_code = 'PLAUS_MAGNITUDE_OUTLIER'
  )
ORDER BY gfc.fiscal_year DESC
LIMIT 2;
```

Treat the candidate as **dependency-flagged** when
`govt_share_of_rev >= 70` on the most recent clean filing. Surface this
as a boolean `dependency_flag` plus the literal percentage on the
briefing card. Foundations (designation A and B) were already excluded
upstream, so the result reflects designation C charitable organizations
whose accounting is straightforward.

If the candidate has NO row in `cra.govt_funding_by_charity` (charities
with zero recorded govt revenue across 2020-2024 are simply absent from
the table by design — see `08-government-funding-analysis.js`), report
`dependency_flag=false` and `govt_share_of_rev=NULL`. That is itself
informative: a candidate flagged as a zombie that never reported any
govt revenue on its T3010 is a different kind of lead worth surfacing.

## Step F — publish (pending) for EVERY surviving candidate

For each candidate that passed Step A's deterministic gate AND Step C's
AB liveness check, call `mcp__ui_bridge__publish_finding` with:
- `entity_name`, `bn` (9-digit root),
- `total_funding_cad` = BN-anchored `fed.vw_agreement_current` total from
  Step A (column `total_M * 1_000_000`). **Do NOT use entity-resolved
  roll-ups for this number.** Acadia/Northwest Inter-Nation lessons.
- `last_known_year` = `last_t3010_year` from Step A (or, if the death
  signal is AB dissolution rather than T3010 silence, the year derived
  from the dissolution event),
- `govt_dependency_pct` from Step E — REQUIRED to compute for every
  candidate. Pass the percentage on the most recent clean filing. If the
  candidate has no row in `cra.govt_funding_by_charity` (no recorded
  govt revenue), pass `0.0` and call this out explicitly in
  `evidence_summary` text: "no govt revenue recorded on T3010 — CHL 70-80%
  flag does not apply".
- `evidence_summary` — audit-lead language. **Required content**:
    1. which death signal fired — `t3010_self_dissolution`
       (field_1570=TRUE; first-party), `dissolved` (AB registry status),
       `dissolved_and_stopped_filing` (both), `stopped_filing` (T3010
       silence), or `no_post_grant_activity` (non-charity recipient);
    2. whether the CHL 70-80% revenue-dependency flag is satisfied
       (`govt_dependency_pct >= 70`) and on which fiscal year, OR
       "no govt revenue recorded on T3010 — flag does not apply" if
       the candidate has no row in `cra.govt_funding_by_charity`;
    3. one-sentence summary of the federal-funding profile (year range,
       department count).
- `verifier_status="pending"`,
- `sql_trail` (the labels of the queries that produced it),
- `last_dept` (optional) — the `owner_org_title` of the most recent
  agreement for this BN from `fed.vw_agreement_current`. If you already
  have this from Step A data in memory, pass it; otherwise omit.

Publish ALL surviving candidates as `pending`, not just the top 3.
Verification + final ranking happens in Step G.

## Step G — verify, sort, finalize

Spawn the verifier subagent ONCE with the FULL candidate list from Step
F (cap at top 10 by `total_committed_cad` if Step A returned more than
10 — but for the canonical zombie demo we expect ≤ 5 so all should fit).

The verifier returns VERIFIED / REFUTED / AMBIGUOUS per candidate plus
a JSON block summarizing all verdicts. Update each finding via
`publish_finding`:
- VERIFIED   → `verifier_status="verified"`
- REFUTED    → `verifier_status="refuted"`
- AMBIGUOUS  → `verifier_status="challenged"`, then run up to 3 follow-up
               SQL queries to defend or revise, then publish a final
               `"verified"` or `"refuted"`.

Final briefing order is **sorted by `total_funding_cad` DESCENDING
among VERIFIED candidates only**. The deterministic gate produces a
stable input set; the verifier produces a stable verdict per candidate
(modulo small LLM sampling); the final sort gives the same top-N
biggest verified zombies on every run.

Refuted and challenged-then-refuted candidates remain visible on the
briefing panel as a record of the methodology — they show the verifier
caught structural special-cases (designation A, live agreement, sub-$1M
exposure, etc.).

## Step H — dossier publish for each VERIFIED candidate

For every candidate that ended VERIFIED (not REFUTED, not AMBIGUOUS),
run THREE small SQL queries and call
`mcp__ui_bridge__publish_dossier` ONCE per BN. Every value passed into
the dossier MUST come from a SQL query in this session — never paraphrase
or round.

### H1 — Funding events timeline

```sql
-- Step H1: per-agreement timeline for the dossier (BN <bn_root>)
SELECT EXTRACT(YEAR FROM agreement_start_date)::int AS year,
       owner_org_title AS dept,
       prog_name_en    AS program,
       agreement_value AS amount_cad,
       agreement_start_date AS start_date,
       agreement_end_date   AS end_date,
       ref_number
FROM fed.vw_agreement_current
WHERE LEFT(NULLIF(recipient_business_number,''),9) = $1
  AND agreement_value > 0
ORDER BY agreement_start_date;
```

Pass the rows as `funding_events`. Up to ~30 rows is fine; if more, take
the largest 30 by `amount_cad`.

### H2 — Dependence-ratio history

```sql
-- Step H2: govt-share-of-rev history for the sparkline (BN <bn_root>)
SELECT gfc.fiscal_year,
       gfc.govt_share_of_rev AS govt_share_pct,  -- 0-100
       gfc.total_govt        AS total_govt_cad,
       gfc.revenue           AS revenue_cad
FROM cra.govt_funding_by_charity gfc
WHERE LEFT(gfc.bn,9) = $1
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_impossibilities ti
    WHERE ti.bn = gfc.bn
      AND EXTRACT(YEAR FROM ti.fpe)::int = gfc.fiscal_year)
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_plausibility_flags pf
    WHERE pf.bn = gfc.bn
      AND EXTRACT(YEAR FROM pf.fpe)::int = gfc.fiscal_year
      AND pf.rule_code = 'PLAUS_MAGNITUDE_OUTLIER')
ORDER BY gfc.fiscal_year;
```

Pass the rows as `dependence_history`. Empty list is fine for non-charity
recipients or charities with zero recorded govt revenue — the UI
shows "no recorded govt revenue" in that case.

### H3 — Overhead snapshot ("did the public get anything?")

```sql
-- Step H3: most-recent clean overhead snapshot (BN <bn_root>)
SELECT obc.fiscal_year,
       obc.strict_overhead_pct,    -- (admin + fundraising) / revenue, %
       obc.programs                AS programs_cad,
       (obc.administration + obc.fundraising) AS admin_fundraising_cad
FROM cra.overhead_by_charity obc
WHERE LEFT(obc.bn,9) = $1
  AND obc.outlier_flag = false
  AND NOT EXISTS (
    SELECT 1 FROM cra.t3010_impossibilities ti
    WHERE ti.bn = obc.bn
      AND EXTRACT(YEAR FROM ti.fpe)::int = obc.fiscal_year)
ORDER BY obc.fiscal_year DESC
LIMIT 1;
```

Pass as `overhead_snapshot` (one dict, or `{}` if no row — non-charity
recipients have no T3010 financial data).

### H4 — Death-event banner text

A single deterministic string built from values you ALREADY have from
Step A:
- if `t3010_self_dissolution_fpe` is not null:
  `f"Self-dissolved on {fpe_iso_date} (T3010 line A2: charity wound up, dissolved, or terminated operations)"`
- else if `ab_dissolution_status` is not null AND `last_t3010_year <= 2022`:
  `f"Alberta non-profit registry status: {status}; stopped filing T3010 after FY{last_t3010_year}"`
- else if `ab_dissolution_status` is not null:
  `f"Alberta non-profit registry status: {status}"`
- else if `last_t3010_year <= 2022`:
  `f"Stopped filing T3010 after FY{last_t3010_year} (last received federal funding through {latest_end_iso_date})"`
- else (`no_post_grant_activity` branch):
  `f"No federal grants since 2024-01-01 and no Alberta grant activity in FY 2024-25 or 2025-26 (BN {bn_root}, last federal payment window closed {latest_end_iso_date})"`

Pass as `death_event_text`.

### H4a — Federal corporate registry timeline (CORP)

Run this query ONLY when Step A's pre-enrich returned a non-null
`corp_status_code` (and therefore `corp_corporation_id`) for this BN.
The dossier panel renders the result as a vertical event list; if Step A
returned no CORP match, skip the query and pass `corp_timeline=[]` to
`publish_dossier`. CORP is a local-only schema and is silent for many
real recipients (provincially-incorporated charities, foreign entities,
sole proprietorships) — empty `corp_timeline` is normal, not a finding.

```sql
-- Step H4a: corp registry timeline (status + name history)
-- $1 = corp_corporation_id from Step A's pre-enriched row.
SELECT 'status'::text       AS kind,
       status_label          AS label,
       effective_date::date  AS event_date,
       is_current
  FROM corp.corp_status_history
 WHERE corporation_id = $1
UNION ALL
SELECT 'name', name, effective_date::date, is_current
  FROM corp.corp_name_history
 WHERE corporation_id = $1
 ORDER BY event_date DESC, kind;
```

Pass the rows as `corp_timeline`. Each row is
`{kind, label, event_date, is_current}`. The dossier UI highlights any
status row whose label is "Dissolved" in red and renders the rest as
gray dots on a timeline.

### H4b — Audited Public Accounts cash trajectory (PA)

Run this query ONLY when Step A's pre-enrich returned a non-null
`pa_last_year` for this BN. PA is a local-only schema and matches by
normalized name; an empty result is informative on its own (CHECK 12 in
the verifier may have already converted the absence into a VERIFIED
verdict). When Step A returned nothing, skip the query and pass
`pa_payments=[]`.

```sql
-- Step H4b: per-fiscal-year PA payments (recipient-detail rows only)
-- $1 = recipient_name_norm: lower(regexp_replace(regexp_replace(
--      e.recipient_name, '^the\s+', '', 'i'),
--      '[^a-z0-9 ]+', ' ', 'g')).
SELECT fiscal_year_end,
       department_name,
       aggregate_payments::bigint AS paid_cad
  FROM pa.transfer_payments
 WHERE recipient_name_norm        = $1
   AND recipient_name_location IS NOT NULL
 ORDER BY fiscal_year_end;
```

Pass the rows as `pa_payments`. Each row is
`{fiscal_year_end, department_name, paid_cad}`. The dossier UI renders a
6-bar sparkline (FY 2020 → 2025), bar height proportional to `paid_cad`,
empty/missing FYs styled gray. The visual contrast between an Active FED
agreement value and an all-gray PA row is the dossier's punchline for
PA-empty cases.

### H5 — Templated headline (DETERMINISTIC, NOT LLM-AUTHORED)

Build the headline as a Python format string from the values above.
**Do NOT rephrase, summarize, or LLM-author this string.** The headline
is structurally deterministic so the same database state produces the
same headline every run.

For charity candidates with a govt-dependency value:
```
f"${total_M:.2f}M in federal commitments {first_year}–{last_year} to a "
f"recipient that {death_clause}; on its most recent clean filing, "
f"government funding was {govt_dependency_pct:.1f}% of total revenue."
```

For charity candidates WITHOUT a govt-dependency value (no row in
`govt_funding_by_charity`):
```
f"${total_M:.2f}M in federal commitments {first_year}–{last_year} to a "
f"recipient that {death_clause}; the entity reported no government "
f"revenue on its T3010, so CHL's 70-80% revenue-dependency flag does "
f"not apply."
```

For non-charity candidates (`no_post_grant_activity`):
```
f"${total_M:.2f}M in federal commitments {first_year}–{last_year} to a "
f"non-charity recipient with no federal grants since 2024-01-01 and no "
f"AB grant activity in FY 2024-25 or 2025-26."
```

`death_clause` derives mechanically from the death signal:
- `t3010_self_dissolution`             → `"self-dissolved on {fpe}"`
- `dissolved_and_stopped_filing`       → `"dissolved (Alberta registry: {status}) and stopped filing T3010 after FY{last_fy}"`
- `dissolved`                          → `"was marked {status} in the Alberta non-profit registry"`
- `stopped_filing`                     → `"stopped filing T3010 after FY{last_fy}"`

### H6 — Call publish_dossier

```
mcp__ui_bridge__publish_dossier(
  bn=<9-digit BN root>,
  headline=<H5 string>,
  funding_events=<H1 rows>,
  dependence_history=<H2 rows>,
  overhead_snapshot=<H3 dict or {}>,
  death_event_text=<H4 string>,
  corp_timeline=<H4a rows or []>,         # OPTIONAL — pass [] when Step A
                                          # returned no CORP match.
  pa_payments=<H4b rows or []>,           # OPTIONAL — pass [] when Step A
                                          # returned no PA match.
  sql_trail=["Step H1: ...", "Step H2: ...", "Step H3: ...",
             "Step H4a: ..."  if H4a ran else omitted,
             "Step H4b: ..."  if H4b ran else omitted]
)
```

The UI attaches the dossier to the existing finding card (matched by
`bn`). Refuted and ambiguous candidates do NOT get a dossier; only
the verified ones become auditable from the briefing panel. The CORP
and PA sub-views are additive: when both are absent the dossier looks
exactly like the v3 baseline; when present they appear below the
overhead snapshot as a registry timeline + audited-cash sparkline.

# Pitfalls

- Do not naïvely `SUM(agreement_value)` over `fed.grants_contributions` —
  use `fed.vw_agreement_current` (handles F-3 cumulative-amendment
  double-counting AND F-1 ref_number-collision disambiguation by
  construction).
- Do NOT use a `DISTINCT ON (ref_number)`-only CTE in place of the view —
  it silently mis-attributes the 41,046 colliding ref_numbers (KDI F-1).
  The view's `DISTINCT ON` includes a recipient disambiguator.
- **Do not compute `total_funding_cad` by aggregating across entity
  source links.** The entity-resolution path catches predecessor entities
  and pre-BN name variants; summing those will inflate the figure
  dramatically (lesson from Northwest Inter-Nation = $101.79M aggregate
  vs. ~$11.7M true current commitment, and Acadia Centre where pre-BN
  variants padded $0.88M up to $6.65M).
- **Do not let a sub-$1M candidate through.** $0.947M is not "$1M-ish".
  If `vw_agreement_current` total is below the gate, refute.
- **Do not treat a multi-year agreement that ends after 2024-01-01 as
  compatible with a zombie pattern.** That agreement is ALIVE — even if
  no new agreements have started, the entity is still a delivery
  counterparty to the federal government. Refute and consider whether
  it's actually a Challenge 2 (Ghost Capacity) lead instead.
- Do not assume `recipient_business_number` is a clean 9-digit string;
  trim and use `LEFT(NULLIF(...,''),9)`.
- Do not re-derive `govt_share` from raw `field_4540 / field_4700` — query
  `cra.govt_funding_by_charity` instead. It is grouped per `(bn,
  fiscal_year)` already. NOTE: it does NOT pre-filter
  `cra.t3010_impossibilities`; you must add a `NOT EXISTS` filter
  yourself to avoid impossibility-row pollution (Step E shows the
  pattern).
- An entity that received funding in 2022 and last filed T3010 with
  `fpe = 2023-12-31` is NOT a zombie — that's normal.
- Both Designation A (public) and B (private) foundations are excluded
  by default (top of skill). Do not confuse the labels.
- Filing window must be closed before "no recent filing" counts (see
  `data-quirks`).
- Filter A-6 reversals (`amount > 0`) and F-9 corrupt-date pairs
  (`agreement_end_date >= agreement_start_date`) before treating any row
  as a "live" signal.
