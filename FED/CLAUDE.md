# Federal Grants and Contributions - AI For Accountability

## Project Context

This is the Federal Grants & Contributions dataset pipeline for the **AI For Accountability Hackathon**. It contains 1.275M records of federal government grants, contributions, and other transfer payments, loaded into the `fed` schema of a shared PostgreSQL database.

The companion project is `../CRA/` which contains CRA T3010 charity data in the `cra` schema.

## Database

- **Schema**: `fed` (search path set automatically by `lib/db.js`)
- **Main table**: `fed.grants_contributions` (1.275M rows, 40 columns including `is_amendment`)
- **Lookup tables**: `fed.agreement_type_lookup`, `fed.recipient_type_lookup`, `fed.country_lookup`, `fed.province_lookup`, `fed.currency_lookup`
- **Views**: `fed.vw_grants_decoded`, `fed.vw_grants_by_department`, `fed.vw_grants_by_province`
- **Connection**: `.env.public` (read-only) loaded first, `.env` (admin) overrides if present

## Key Fields

- `_id`: Primary key (from Open Data API)
- `recipient_legal_name`, `recipient_business_number`, `recipient_type` (F/N/G/A/P/S/I/O)
- `owner_org`, `owner_org_title`: Funding department
- `agreement_type`: G=Grant, C=Contribution, O=Other
- `agreement_value`: Dollar amount (can be negative for amendments)
- `is_amendment`: Boolean flag (true = amendment to original grant)
- `agreement_start_date`, `agreement_end_date`
- `prog_name_en`, `prog_purpose_en`: Program info
- `recipient_province`, `recipient_city`, `federal_riding_number`

## Recipient Types

| Code | Type |
|------|------|
| F | For-profit organizations |
| N | Not-for-profit organizations and charities |
| G | Government |
| A | Indigenous recipients |
| P | Individual or sole proprietorships |
| S | Academia |
| I | International (non-government) |
| O | Other |

Note: ~148K entities have NULL recipient_type (pre-2018 data).

## Pipeline Scripts

```bash
npm run migrate       # Create schema, tables, indexes, views
npm run seed          # Populate lookup tables from data-schema.json
npm run fetch         # Download 1.275M records from Open Data API
npm run import        # Load into PostgreSQL
npm run fix-quality   # Normalize agreement types, provinces, add is_amendment
npm run verify        # Verify completeness and quality
npm run dashboard     # Run summary queries, output to data/reports/dashboard.json
```

## Advanced Analysis Scripts

```bash
npm run analyze:equity         # Per-capita provincial funding analysis
npm run analyze:forprofit      # For-profit recipient deep dive
npm run analyze:amendments     # Amendment creep detection
npm run analyze:concentration  # Vendor/recipient concentration (HHI)
npm run analyze:zombies        # Zombie recipients & ghost capacity
npm run analyze:export         # Entity export for external research
npm run analyze:risk           # Comprehensive 7-dimension risk register
npm run analyze:individuals    # Individual grant recipients analysis
npm run analyze:all            # Run all 8 advanced scripts
```

## Reports (data/reports/)

All analysis outputs are in `data/reports/` as JSON (structured), CSV (sortable), and TXT (readable):
- `risk-register.*` - 109K entities scored 0-35 across 7 risk dimensions
- `provincial-equity.*` - Per-capita analysis with population data
- `for-profit-deep-dive.*` - For-profit entity analysis
- `amendment-creep.*` - Amendment patterns
- `recipient-concentration.*` - HHI and dominance analysis
- `zombie-and-ghost.*` - Inactive/identity risk entities
- `entity-export-*.csv` - Entity lists for external research
- `individual-recipients.*` - Individual grant analysis
- `dashboard.json` - Summary statistics

## Skills

Available Claude skills for interactive analysis:
- `/provincial-briefing [province code]` - Provincial funding briefing
- `/recipient-profile [name]` - Deep profile of a grant recipient
- `/risk-assessment [name]` - Risk factor analysis for an entity
- `/program-analysis [program name]` - Analyze a federal program
- `/department-audit [department name]` - Audit a department's grants

## Important Notes

- **"Funding cessation"** means no new grants received - NOT that the entity ceased operations
- **Government recipients** (type G) should be analyzed separately from private entities
- **"Batch report"** entries are aggregate reporting, not individual grants
- **NULL recipient_type** is common in pre-2018 data - not necessarily suspicious
- **Negative agreement_value** rows are amendments/corrections, not errors

## Sample Queries

See `docs/SAMPLE_QUERIES.sql` for 35+ ready-to-run analytical queries.

## Hackathon Challenges

This dataset directly supports challenges: #1 Zombie Recipients, #2 Ghost Capacity, #4 Amendment Creep, #5 Vendor Concentration, #7 Policy Misalignment, #8 Duplicative Funding, #9 Contract Intelligence, #10 Adverse Media.
