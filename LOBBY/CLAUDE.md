# Lobbying Registry — AI For Accountability (Zombie-Agent Augmentation)

Federal lobbying disclosures from the Office of the Commissioner of Lobbying (OCL), loaded into the local Docker Postgres only. **Not on the shared Render DB.** Built to augment the zombie-agent plan with a third signal: was the recipient *lobbying* government before its grants ended?

## Source

- **Publisher:** Office of the Commissioner of Lobbying of Canada (OCL)
- **Bulk download:** `https://lobbycanada.gc.ca/media/zwcjycef/registrations_enregistrements_ocl_cal.zip` and `https://lobbycanada.gc.ca/media/mqbbmaqk/communications_ocl_cal.zip` (linked from open.canada.ca dataset IDs `70ef2117-...` and `a34eb330-...`)
- **Update frequency:** weekly (last modified 2026-04-27)
- **License:** Open Government Licence – Canada
- **Note:** the host blocks `curl` — download via browser. Save zips to `LOBBY/data/raw/`.

## Database

- **Host:** local Docker Postgres only (`localhost:5434`, db `hackathon`, user `qohash`).
- **Schema:** `lobby` (search path set automatically by `lib/db.js`).
- **Tables loaded:**

| Table | Rows | Source CSV |
|---|---:|---|
| `lobby.lobby_registrations` | 170,037 | `Registration_PrimaryExport.csv` |
| `lobby.lobby_govt_funding` | 203,845 | `Registration_GovtFundingExport.csv` |
| `lobby.lobby_communications` | 363,616 | `Communication_PrimaryExport.csv` |
| `lobby.lobby_communication_dpoh` | 554,695 | `Communication_DpohExport.csv` |

- **Views:** `lobby.vw_client_activity` (per-client summary), `lobby.vw_communications_with_dpoh` (comms enriched with target institutions).

The other 14 CSVs in the source bundles (subject matter, beneficiaries, in-house lobbyists, etc.) are not loaded — extend `02-import.js` if needed.

## Pipeline

```bash
cd LOBBY
npm install
npm run setup      # unzip → migrate → import → verify (~15s on M-series)
# or run the steps individually:
npm run unzip      # extract data/raw/*.zip into data/csv/
npm run migrate    # create schema + tables
npm run import     # bulk COPY all four CSVs
npm run verify     # row counts + sample queries
npm run reset      # drop + setup
```

**Prereq:** drop the two OCL zips into `LOBBY/data/raw/` (`registrations_enregistrements_ocl_cal.zip` and `communications_ocl_cal.zip`). The `setup` script unzips, migrates, imports, and verifies in one shot. The import script transforms the literal `"null"` field convention to SQL NULL inline during streaming.

## Key fields for the zombie agent

### `lobby_registrations`
- `client_name_en` / `client_name_norm` — the *recipient*-side lobbying client. Match against `fed.grants_contributions.recipient_legal_name` via the same `norm_name` regex.
- `effective_date` / `end_date` — registration validity window. Multiple registrations per client over time.
- `govt_fund_ind` (Y/N) — registrant has self-declared receiving government funding for this client.
- `reg_type` — 1 = consultant lobbyist, 2 = in-house corporation, 3 = in-house organization.

### `lobby_govt_funding`
- `reg_id` joins back to `lobby_registrations`.
- `institution` — *self-disclosed* funding source (free text; includes `'Provincial'`, `'Government of Canada'`, plus specific dept abbreviations like `'ISED'`, `'CIHR'`).
- `amount` — self-disclosed dollar amount. **Do not sum naively.** This is *registrant-reported*, not government-published, and includes provincial + federal + foreign sources mixed.
- `text_description` — free-text purpose of the funding.

### `lobby_communications` + `lobby_communication_dpoh`
- A communication is one logged interaction with a *Designated Public Office Holder*. `comlog_id` is the join key.
- `dpoh.institution` is the *target department*. `dpoh.dpoh_title` is the senior-official role lobbied (Minister, DM, ADM, MP, etc.).

## How this augments the zombie-agent plan

The verifier subagent gets a fifth probe alongside the four in `plans/zombie_agent_build_manual_v2.md` §8:

> 5. Did this entity register lobbyists in the 24 months around the grant
>    end_date? Use `lobby.vw_client_activity` matched on `client_name_norm`.
>    A "zombie" that was lobbying multiple departments before disappearing
>    is a stronger story than one that was silent.

A **lobbying-while-zombying** finding strengthens the demo punchline from *"$X to {entity}, dissolved 9 months later"* to *"$X to {entity}, who lobbied {institution} {N} times in the year before its grants ended, then dissolved."*

Worked example (run from `LOBBY/`):

```sql
WITH fed_endings AS (
  SELECT
    recipient_legal_name,
    NULLIF(regexp_replace(regexp_replace(lower(coalesce(recipient_legal_name,'')),
      '^the\s+', '', 'i'), '[^a-z0-9 ]+', ' ', 'g'), '') AS norm_name,
    SUM(agreement_value) FILTER (WHERE NOT is_amendment) AS originals,
    MAX(agreement_end_date) AS last_grant
  FROM fed.grants_contributions
  GROUP BY 1, 2
  HAVING SUM(agreement_value) FILTER (WHERE NOT is_amendment) >= 500000
     AND MAX(agreement_end_date) BETWEEN '2018-01-01' AND '2022-12-31'
)
SELECT fe.recipient_legal_name, fe.originals::bigint, fe.last_grant,
       COUNT(DISTINCT lr.reg_id) AS lobby_regs,
       COUNT(DISTINCT lc.comlog_id) AS lobby_comms
FROM fed_endings fe
JOIN lobby.lobby_registrations lr ON lr.client_name_norm = fe.norm_name
LEFT JOIN lobby.lobby_communications lc ON lc.client_name_norm = fe.norm_name
WHERE NOT EXISTS (
  SELECT 1 FROM fed.grants_contributions later
   WHERE later.recipient_legal_name = fe.recipient_legal_name
     AND later.agreement_start_date >= '2023-01-01'
)
GROUP BY 1, 2, 3 ORDER BY 2 DESC LIMIT 20;
```

Currently produces ~15 viable candidates. Validate by hand (filter out major corporations like Toyota / Ford / Bombardier that are obviously not dead — they're just not showing as primary recipients in recent data).

## Things that will trip you up

- **Name match is regex-based, not entity-resolved.** ~16% of lobby clients match a FED recipient by `norm_name`. For higher recall, port `general.norm_name()` or join through `general.entity_golden_records` once we add `lobby_registrations` as a 7th source link.
- **`govt_fund_ind = 'Y'` is registrant-self-reported.** Many heavy government-funded entities have `govt_fund_ind = 'N'` because the registrant ticked the wrong box. Treat the flag as a hint, not ground truth.
- **`amount` in `lobby_govt_funding` is wildly heterogeneous.** Some rows are annual grants, some are cumulative, some are commitments, some are loans. Top institution is `'Provincial'` at $433B — this is registrant-reported text, not a real number. Use only as supporting evidence, never as a primary metric.
- **The CSV uses literal `"null"` strings**, not empty fields. The import script rewrites these to unquoted empties so `COPY ... NULL ''` reads them as SQL NULL.
- **78 / 107 row drops** during import (out of 533K total) are due to embedded newlines in quoted fields confusing the line-by-line splitter. Acceptable for the hackathon. Fix by switching to a streaming CSV parser if needed.
- **Schema is dropped+recreated by `01-migrate.js`.** The migration is non-idempotent on purpose — `npm run reset` is a clean slate.
- **`House of Commons` dominates the DPOH table** (164K of 555K rows = 30%). MPs count as DPOH. Filter to `institution NOT IN ('House of Commons', 'Senate of Canada')` for executive-branch-only analysis.
