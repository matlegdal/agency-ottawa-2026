# Public Accounts Transfer Payments — AI For Accountability (Zombie-Agent Augmentation)

The audited, post-fiscal-year-end record of every transfer payment ≥ $100K from the Government of Canada — published in Volume III of the Public Accounts. Loaded into the local Docker Postgres only. **Not on the shared Render DB.** Closes the "did the money actually flow?" loop on top of the FED proactive disclosure.

## Source

- **Publisher:** Public Services and Procurement Canada (PSPC) — Receiver General
- **Bulk download URL pattern:** `https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/pt-tp/pt-tp-{YEAR}.csv` (2022+) or `pt-tp-{YEAR}-eng.csv` (2020–2021)
- **License:** Open Government Licence – Canada
- **Update frequency:** annual, released after Fall Economic Statement
- **Coverage:** every recipient who received ≥ CAD 100,000 in any fiscal year since 2003 (we load 2020–2025).

This is the **audited** counterpart to FED's `grants_contributions` (which is the unaudited TBS proactive-disclosure feed). The two complement each other:

| Schema | Source | Timing | Shape | Use it for |
|---|---|---|---|---|
| `fed.grants_contributions` | TBS Proactive Disclosure | quarterly, real-time | one row per agreement amendment | what the government *committed to pay* |
| `pa.transfer_payments` | Receiver General Public Accounts | annual, post-audit | one row per (department × program × recipient × FY) | what the government *actually paid* |

The gap between the two — *committed but not paid* — is itself a zombie signal: an agreement was signed but the money never moved (cancellation, lapse, recipient default).

## Database

- **Host:** local Docker Postgres only (`localhost:5434`, db `hackathon`, user `qohash`).
- **Schema:** `pa` (search path set automatically by `lib/db.js`).
- **Tables:**

| Table | Rows | Coverage |
|---|---:|---|
| `pa.transfer_payments` | 144,570 | Fiscal years 2020 → 2025, all departments |

- **View:** `pa.vw_recipient_totals` — per-recipient-name aggregate across years.

## Pipeline

```bash
cd PA
npm install
npm run setup      # migrate → import → verify (~10s)
# steps individually:
npm run migrate
npm run import     # loads pt-tp-{2020..2025}.csv via COPY
npm run verify
npm run reset      # drop + setup
```

**Prereq:** the six CSV files (2020 → 2025) must exist in `PA/data/raw/`. Download them from `https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/pt-tp/pt-tp-{YEAR}.csv` (2022+) or `pt-tp-{YEAR}-eng.csv` (2020/2021). The CSVs are committed-friendly at ~58 MB total (~13 MB max per file).

## ⚠ The row-type gotcha (read this before querying)

**`pa.transfer_payments` mixes two row shapes** and the meaning of two columns flips depending on which:

| Row type | `recipient_name_location` | `expenditure_current_yr` | `aggregate_payments` | What it means |
|---|---|---|---|---|
| **Program total** | NULL or empty | filled (large) | 0 | Roll-up of all recipients of one program in one fiscal year |
| **Recipient detail** | filled (the recipient name) | NULL | filled | Money paid to one specific recipient |

Out of 144,570 rows: **4,423 are program totals**, **140,147 are recipient details**. So:

- **For per-recipient queries**, `WHERE recipient_name_location IS NOT NULL` and use `aggregate_payments` as the dollar amount.
- **For program-level rollups**, `WHERE recipient_name_location IS NULL` and use `expenditure_current_yr`.
- **`vw_recipient_totals`** already filters to recipient-detail rows.

This is a publisher convention from the Public Accounts source CSVs, not something I introduced. The header names are misleading on purpose (the same column name carries a different meaning depending on where the cursor is in the report).

## How this augments the zombie-agent plan

The verifier subagent gets a **7th probe** (alongside the 6 from CRA/AB/LOBBY/CORP/FED-views):

> 7. Did the recipient actually *receive* money via Public Accounts in any
>    fiscal year between the FED grant's `agreement_start_date` and now?
>    Match `pa.transfer_payments.recipient_name_norm` against the FED
>    recipient name. If the FED disclosure shows a multi-million-dollar
>    agreement but no PA recipient-detail row matches across all six
>    fiscal years, the agreement was signed and never drew down — the
>    cleanest possible zombie.

### The headline finding

```sql
WITH fed_recipients AS (
  SELECT
    NULLIF(regexp_replace(regexp_replace(lower(coalesce(recipient_legal_name,'')),
      '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm,
    recipient_legal_name,
    SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals,
    MIN(agreement_start_date)::date AS first_grant,
    MAX(agreement_end_date)::date AS last_grant
  FROM fed.grants_contributions
  WHERE agreement_start_date BETWEEN '2020-01-01' AND '2024-12-31'
    AND recipient_legal_name IS NOT NULL
    AND recipient_legal_name NOT ILIKE '%batch report%'
    AND recipient_legal_name NOT ILIKE 'Government of%'
  GROUP BY 1, 2
  HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 5000000
),
pa_recipients AS (
  SELECT DISTINCT recipient_name_norm
  FROM pa.transfer_payments
  WHERE recipient_name_location IS NOT NULL AND recipient_name_location <> ''
)
SELECT f.recipient_legal_name, f.originals, f.first_grant, f.last_grant
FROM fed_recipients f
LEFT JOIN pa_recipients p ON p.recipient_name_norm = f.norm
WHERE p.recipient_name_norm IS NULL
ORDER BY f.originals DESC LIMIT 15;
```

Currently surfaces:

- **WE Charity Foundation** — $543M FED disclosure (May 2020 – March 2021), $0 in Public Accounts. The agreement was signed during the WE Charity scandal and rolled back before any cash moved. **The cleanest zombie in the dataset.**
- **SDTC** — $748M FED, $0 PA recipient-detail rows. Same SDTC the CORP module flagged as Dissolved 2025-03-31.
- **Mitacs Inc.** — $748M FED, no PA match (likely a name-norm mismatch worth a verifier probe — Mitacs is real and active, this would be a false positive to dig into).
- Battery-plant megagrants (NextStar $14B, PowerCo $13B) — these are not zombies but legitimate slow-disbursing megagrants where most of the agreement value is in future fiscal years. Worth flagging as a separate "watch list" category in the demo.

## Things that will trip you up

- **The row-type column-flip described above.** Easy to misread in any aggregate query. Always filter explicitly.
- **NULL recipient names dominate top-by-amount queries.** Aggregate program totals are bigger than any individual recipient. Filter to `recipient_name_location IS NOT NULL` for headline finds.
- **Bilingual recipient names use `|` as a separator** in some FED rows (e.g., `City of Toronto | Ville de Toronto`) but `|` does NOT appear in PA recipient names. The same entity will normalize differently between FED and PA. The verifier subagent should compare BOTH sides of a `|` against the PA name when the FED row contains one.
- **Provincial governments are inconsistently named** across FED and PA. FED writes `Government of Alberta`; PA might write `Province of Alberta` or `Alberta` alone. Expect false-positive zombies on government recipients — filter them out of the demo target set.
- **2020 and 2021 CSVs use English-only column headers.** 2022+ added French sibling columns. The import script handles both via the same `HEADER_MAP`.
- **The CSV uses BOM-prefixed UTF-8 on the first line.** The header parser strips it.
- **`expenditure_current_yr` for program-total rows is the cash payment for THAT fiscal year only**, not cumulative. Summing across all years gives a true 6-year total.
- **No BN field.** Cross-dataset matching to FED is name-based via `recipient_name_norm`. For higher recall, eventually route through `general.entity_golden_records`.

## Distribution to the team

The six CSVs total ~58 MB and can be committed directly (no file exceeds 13 MB). The pipeline is fully reproducible: `npm run setup` from a clean clone takes ~10 seconds.
