# CRA Charity Registration Status — AI For Accountability (Zombie-Agent Augmentation)

CRA "List of Charities" registry export, loaded into the local Docker Postgres only. **Not on the shared Render DB.** Closes a specific gap that `cra/` (T3010 filings) cannot: charities that exist in the CRA registry but aren't filing returns, and charities whose registered status has been formally **Revoked / Annulled / Suspended** with an effective date.

## Why this is not redundant with `cra/`

| | `cra/` schema (T3010) | `charstat/` schema (this module) |
|---|---|---|
| Source | T3010 information return filings 2020–2024 | List of Charities registry snapshot (live) |
| Row granularity | One row per (BN, fiscal_year) **only when filed** | One row per charity, regardless of filing |
| Status field | None — inferred from absence of recent filings | Explicit: Registered / Revoked / Annulled / Suspended |
| Effective date | None | `status_effective_date` (exact date CRA changed status) |
| Revoked entities | Disappear from the table after they stop filing | Still present, with status='Revoked' + date |
| Sanctions | Not exposed | `sanction` column when present |

The narrative lift mirrors `corp/`: T3010 absence is *absence of evidence*; List of Charities revocation is *evidence of dissolution* — "CRA officially revoked this charity on YYYY-MM-DD, and FED contributions continued for N more days afterward."

## Source

- **Publisher:** Canada Revenue Agency
- **Public search + download:** https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch
- **Update frequency:** weekly (live-snapshot)
- **License:** Open Government Licence – Canada
- **Coverage:** every charity that has ever been registered under the Income Tax Act, with current status

### How to download (operator)

The CRA search page does not expose a direct CSV URL — the export is generated server-side after a search. Steps:

1. Open https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch in a browser.
2. Leave all fields blank.
3. Set the **Status** dropdown to **All**.
4. Click **Search**.
5. Scroll to the bottom of the results, click **Download results**.
6. Save the CSV (or extract from ZIP) into `CHARSTAT/data/raw/`.

Any filename ending in `.csv` works — the importer ingests every CSV in that directory.

## Database

- **Host:** local Docker Postgres only (`localhost:5434`, db `hackathon`, user `qohash`).
- **Schema:** `charstat` (search path set automatically by `lib/db.js`).
- **Table:** `charstat.charity_status` — one row per charity (PK `bn` = 15-char CRA BN like `123456789RR0001`).
- **View:** `charstat.vw_zombie_candidates` — every non-Registered charity.

### Schema highlights

| Column | Notes |
|---|---|
| `bn` | 15-char CRA BN (PK). Cleaned of spaces/hyphens. |
| `bn_root` | First 9 chars — the cross-dataset join key. Same convention as `corp.business_number`. |
| `status` | Canonicalized to `Registered` / `Revoked` / `Annulled` / `Suspended`. |
| `status_effective_date` | Exact date of last status change. The killer feature. |
| `sanction` | Sanction text when present (rare; e.g. "Suspension of receipting privileges"). |
| `source_snapshot_date` | File mtime — distinguishes re-imports from live updates. |

## BN coverage

Every row in this dataset has a 15-char CRA BN, so the 9-digit root is always derivable. **100% BN-joinable** to `cra/`, `fed/`, and `general.entity_golden_records`. No fuzzy matching needed.

## Pipeline

```bash
cd CHARSTAT
npm install
# (drop the CRA List of Charities CSV into CHARSTAT/data/raw/ first)
npm run setup      # migrate → import → verify
# steps individually:
npm run migrate    # create charstat schema + table
npm run import     # parse raw CSV → staging → COPY into Postgres
npm run verify     # row counts + status histogram + zombie cross-join preview
npm run reset      # drop + setup
```

The importer is **column-name tolerant** — CRA has renamed `BN/Registration Number` → `Registration Number` → `BN` between exports, and accented French headers are normalized. See `scripts/02-import.js` for the alias map.

The import is two-phase (parse → staging CSV → COPY) for the same reason as `corp/`: streaming directly into Postgres is fragile, and a staging file makes re-runs and debugging trivial.

## How this augments the zombie-agent plan

The verifier subagent gets a 7th probe alongside the six in `plans/zombie_agent_corp_pa_addendum.md`:

> 7. Has CRA officially **Revoked**, **Annulled**, or **Suspended** the charity's
>    registration? Use `charstat.charity_status` joined on
>    `bn_root = LEFT(fed.recipient_business_number, 9)`. A FED grant whose
>    `agreement_end_date` is **after** `charstat.status_effective_date` for a
>    revoked charity is the cleanest possible zombie hit — CRA itself has
>    already declared the recipient ineligible to operate as a charity.

### The headline finding (live, on stage)

```sql
WITH dead AS (
  SELECT bn_root, charity_name, status, status_effective_date
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
SELECT f.recipient_legal_name, d.status, d.status_effective_date,
       f.originals, f.last_grant_end,
       (f.last_grant_end - d.status_effective_date) AS days_funded_after_status_change
  FROM fed f JOIN dead d ON d.bn_root = f.bn9
 WHERE f.last_grant_end > d.status_effective_date
 ORDER BY days_funded_after_status_change DESC
 LIMIT 20;
```

`days_funded_after_status_change` is the demo number — money that flowed to a charity *after* CRA officially revoked them.

## Things that will trip you up

- **The CRA download is gated by a search-page button**, not a stable URL. There is no `wget` recipe — the operator has to click through. Re-runs are easy because re-importing the same file is idempotent (PK on `bn`).
- **Status values come back localized** in some exports. The importer canonicalizes `Enregistré` → `Registered`, `Révoqué` → `Revoked`, etc. New strings will pass through unchanged — check `charstat.vw_zombie_candidates` after import for unexpected values.
- **`bn` here is the full 15-char CRA BN.** Use `bn_root` (9 digits) to join to FED/CORP/general. The 15-char form is preserved for one-off lookups, since CRA's public search keys on it.
- **`source_snapshot_date` is the file mtime**, not the publish date. If you re-download and `mtime` is unchanged, set the file's mtime explicitly with `touch`.
- **Effective date semantics:** for `Registered` charities the field is the original registration date; for `Revoked/Annulled/Suspended` it's the date of that change. Don't compare effective dates across statuses without filtering by status.
- **Schema is dropped+recreated by `01-migrate.js`.** `npm run reset` is a clean slate.

## Distribution to the team

CRA does not block the search-page download. Each operator can do their own export, or one person can share the CSV out of band (Slack file). Files are typically <50 MB compressed.
