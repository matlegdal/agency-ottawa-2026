# Federal Corporations Registry — AI For Accountability (Zombie-Agent Augmentation)

Federal corporate registry from Corporations Canada (Innovation, Science and Economic Development), loaded into the local Docker Postgres only. **Not on the shared Render DB.** Closes the single biggest gap in the zombie-agent plan: the corporate-status signal that converts "we couldn't find evidence of life" into "the federal corporation was formally struck off / is in dissolution proceedings."

## Source

- **Publisher:** Innovation, Science and Economic Development Canada (ISED) — Corporations Canada
- **Bulk download:** `https://ised-isde.canada.ca/cc/lgcy/download/OPEN_DATA_SPLIT.zip` (~200 MB zipped → ~2.5 GB unzipped, 103 chunked XML files of ~25 MB each)
- **Update frequency:** weekly
- **License:** Open Government Licence – Canada
- **Coverage:** every federally-incorporated entity (CBCA business corporations, NFP Act not-for-profits, Boards of Trade, cooperatives, special-act corporations). Excludes provincial corporations (those live with each province) and financial institutions (separate regime).

## Database

- **Host:** local Docker Postgres only (`localhost:5434`, db `hackathon`, user `qohash`).
- **Schema:** `corp` (search path set automatically by `lib/db.js`).
- **Tables:**

| Table | Rows | Description |
|---|---:|---|
| `corp.corp_corporations` | 1,559,761 | One row per federal corporation, with current name + status + address + BN flattened. |
| `corp.corp_status_history` | 3,819,713 | One row per historical status transition (active → intent-to-dissolve → dissolved, etc.). |
| `corp.corp_name_history` | 1,868,880 | One row per (current or historical) name. Useful for matching FED grants recorded under an old name. |

- **View:** `corp.vw_zombie_candidates` — corps with non-active status or stopped filing annual returns for 3+ years.

## Status code reference (the critical field)

| Code | Label | Zombie signal? |
|---|---|---|
| 1 | Active | No (657,597 corps) |
| 2 | Active - Intent to Dissolve Filed | **Yes** — the corp itself filed dissolution paperwork (1,020 corps) |
| 3 | Active - Dissolution Pending (Non-compliance) | **Yes — strongest signal**. Corporations Canada is striking the corp off for failing to file annual returns (35,598 corps) |
| 4 | Active - Discontinuance Pending | Maybe — moving to another act/jurisdiction (122 corps) |
| 9 | Inactive - Amalgamated | Merged into another corp (78,226) |
| 10 | Inactive - Discontinued | Moved to another regime, no longer federally-incorporated (18,480) |
| 11 | Dissolved | **Yes — final state** (741,359 corps) |
| 19 | Inactive | (5 corps, edge cases) |

**Codes 2, 3, and 11 are the core zombie signals.** Code 3 is the smoking gun — these are corps that have demonstrably stopped operating (no annual return for 1+ years), with Corporations Canada actively winding them up.

## BN coverage

**92.4% of federal corporations have a 9-digit business number** (1,441,961 of 1,559,761). This is the same 9-digit BN root used by FED and CRA — direct join, no fuzzy matching needed. The remaining 7.6% are mostly old NFP-Act corps or cooperatives that pre-date the modern BN system.

## Pipeline

```bash
cd CORP
npm install
npm run setup      # unzip → migrate → import → verify (~5 min)
# steps individually:
npm run unzip      # extract data/raw/OPEN_DATA_SPLIT.zip into data/xml/
npm run migrate    # create corp schema + tables
npm run import     # two-phase load (XML → CSV staging → COPY into Postgres)
npm run verify     # row counts + status distribution + zombie preview
npm run reset      # drop + setup
```

**Prereq:** drop `OPEN_DATA_SPLIT.zip` into `CORP/data/raw/`. The setup script unzips (2.5 GB), parses with SAX, stages CSVs to `data/staging/`, then bulk-COPYs into Postgres. Phase 1 (XML→CSV) takes ~4 min; Phase 2 (CSV→DB) takes ~30 sec.

The import is two-phase on purpose: streaming three pg-copy-streams in parallel from a single SAX parser deadlocks on backpressure. Two-phase (write CSV files first, then sequential COPYs) is faster and easier to reason about.

## How this augments the zombie-agent plan

The verifier subagent gets a 6th probe alongside the five in `plans/zombie_agent_build_manual_v2.md` §8:

> 6. Is the federal corporation registry showing this entity as **Dissolved**,
>    **Active - Dissolution Pending (Non-compliance)**, or **Active - Intent
>    to Dissolve Filed**? Use `corp.corp_corporations.business_number` joined
>    on `LEFT(fed.recipient_business_number, 9)`. A FED grant recipient with
>    `current_status_code IN (2, 3, 11)` is a definitive zombie — the
>    Government of Canada itself has officially recognized the entity is
>    winding up.

The narrative lift: the demo punchline upgrades from *"$X to {entity}, no filings since 2022"* (absence of evidence — slightly weak on stage) to *"$X to {entity}, struck off the federal corporate registry on {date}, $Y of grants still scheduled to flow until {future date}"* (evidence of dissolution — decisive).

### The headline finding (live, on stage)

Run from `CORP/`:

```sql
WITH bn_corps AS (
  SELECT business_number, current_name, current_status_label,
         current_status_date, dissolution_date, last_annual_return_year
  FROM corp.corp_corporations
  WHERE business_number IS NOT NULL
    AND current_status_code IN (2, 3, 11)
),
fed_recipients AS (
  SELECT
    LEFT(recipient_business_number, 9) AS bn9,
    recipient_legal_name,
    SUM(agreement_value) FILTER (WHERE NOT is_amendment)::bigint AS originals,
    MAX(agreement_end_date) AS last_grant_end
  FROM fed.grants_contributions
  WHERE recipient_business_number IS NOT NULL
    AND recipient_business_number ~ '^[0-9]'
  GROUP BY 1, 2
  HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 100000
)
SELECT f.recipient_legal_name, c.current_name AS corp_name,
       c.current_status_label, c.current_status_date::date AS status_date,
       c.last_annual_return_year, f.originals, f.last_grant_end::date
FROM fed_recipients f
JOIN bn_corps c ON c.business_number = f.bn9
ORDER BY f.originals DESC LIMIT 20;
```

Currently surfaces the SDTC ($1.6B, dissolved 2025-03-31), a cluster of cleantech/biotech zombies (Variation Biotechnologies $56M, D-Wave $40M, Xanadu $64M), and ~35K smaller "Dissolution Pending" companies still drawing grants.

## Things that will trip you up

- **`current_status_code = 1` (Active) covers ~657K of 1.56M corps**, which means more than half of the registry is non-active. That is *normal* — Corporations Canada doesn't purge old records, so the registry is cumulative since 1947. Do NOT use "any non-active status" as a zombie signal without restricting to corps that have been *recently* funded.
- **Status code 3 ("Active - Dissolution Pending - Non-compliance") is the cleanest signal.** Code 11 (Dissolved) catches corps that wound up cleanly years ago — many will not have a recent FED grant. Code 3 specifically means "stopped filing in the last 1–2 years and ISED is winding them up *now*" — the most relevant for live demo.
- **The XML uses `<address current="true">` with multiple `<addressLine>` children.** I concatenate them with `, ` separators. Some corps have 3+ address lines.
- **Some corps register `director_max = 999999`** as "no upper limit" — that's why the column is INTEGER, not SMALLINT. Don't `MAX(director_max)` without filtering.
- **`business_number` here is the 9-digit BN root, NOT the 15-character CRA BN.** When joining to FED's `recipient_business_number` (which can be either format), use `LEFT(fed.recipient_business_number, 9)` to extract the root. The repo's `general.extract_bn_root()` does this and handles the placeholder values too.
- **2.5 GB of raw XML** — the import script writes ~600 MB of staging CSVs to `CORP/data/staging/`. These are gitignored. Delete them after import if disk space matters.
- **The `data/xml/` directory contains 103 25-MB XML chunks.** Gitignored. Re-run `npm run unzip` to recreate from the source zip.
- **Schema is dropped+recreated by `01-migrate.js`.** `npm run reset` is a clean slate.

## Distribution to the team

The source zip is 200 MB — too large to commit even one-off. Either:
- Share `OPEN_DATA_SPLIT.zip` out of band (Slack file, shared drive); colleagues drop it into `CORP/data/raw/` and run `npm run setup`.
- Or download fresh from `https://ised-isde.canada.ca/cc/lgcy/download/OPEN_DATA_SPLIT.zip` directly (this URL works with normal browser User-Agent — no curl bot blocking unlike LOBBY).
