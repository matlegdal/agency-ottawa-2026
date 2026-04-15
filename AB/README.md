# Alberta Open Data Pipeline

Part of the **AI For Accountability Hackathon** suite, alongside the [CRA T3010](../CRA/) and [Federal Grants](../FED/) pipelines.

## Datasets

| Dataset | Source | Records | Format |
|---------|--------|---------|--------|
| **Alberta Grants** | Alberta Open Data Portal | ~1M+ | JSON (MongoDB export) |
| **Contracts (Blue Book)** | Alberta Blue Book | ~67K | Excel |
| **Sole-Source Contracts** | Alberta Procurement | ~15K | Excel |
| **Non-Profit Registry** | Alberta Corporate Registry | ~69K | Excel |

All data lives in the `ab` schema of the shared PostgreSQL database, completely isolated from the `cra` and `fed` schemas.

## Quick Start

```bash
# Install dependencies
npm install

# Run the full pipeline (migrate, seed, import all, verify)
npm run setup

# Or run individual steps:
npm run migrate           # Create schema and tables
npm run seed              # Load lookup tables
npm run import:grants     # Import grants (~5-10 min for 1.1GB file)
npm run import:contracts  # Import Blue Book contracts
npm run import:sole-source # Import sole-source contracts
npm run import:non-profit  # Import non-profit registry
npm run verify            # Run verification checks
```

## Configuration

The pipeline uses the same database as CRA and FED:

- `.env` - Admin credentials (gitignored)
- `.env.public` - Read-only credentials (committed, for hackathon participants)

## Testing

```bash
npm run test:unit         # 37 unit tests (transformers, no DB needed)
npm run test:integration  # Schema + data quality checks (needs DB)
npm test                  # All tests
```

## Architecture

Follows the same patterns as the CRA and FED pipelines:
- Numbered scripts (`01-migrate.js` through `07-verify.js`)
- Shared `lib/` for database, logging, and data transformers
- Batch-based imports with progress tracking
- Idempotent operations (safe to re-run)
- Comprehensive verification with source-vs-DB row count checks

## Data Notes

- **Fiscal years** use "YYYY - YYYY" format with spaces (e.g., "2024 - 2025")
- **Negative grant amounts** are reversals/corrections
- The main grants JSON file is **1.1GB** and uses streaming parser
- Non-profit registry dates go back to **1979**
- Sole-source dates are in M/D/YYYY format (parsed automatically)
