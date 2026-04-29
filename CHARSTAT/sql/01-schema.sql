-- CRA Charity Registration Status schema for the AI for Accountability Hackathon.
-- Source: CRA "List of Charities" public download
--   https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch
--   (search with all fields blank → Status=All → Search → "Download results" → ZIP/CSV)
--
-- WHY THIS EXISTS (not redundant with `cra/`):
--
-- The `cra/` schema loads T3010 *filings* — one row per (BN, fiscal_year)
-- only when a return was actually filed. A charity that was REVOKED in 2021
-- and stopped filing is invisible from 2022 onward. The List of Charities
-- is the registry side of the same data: one row per charity regardless of
-- filing, with explicit status (Registered / Revoked / Annulled / Suspended)
-- and the effective date of that status. That is the difference between
-- "we couldn't find recent filings" (absence of evidence) and "CRA officially
-- revoked this charity on 2021-04-15 for failure to file" (evidence of
-- dissolution). The latter is the demo punchline for the zombie agent.

CREATE SCHEMA IF NOT EXISTS charstat;

DROP VIEW  IF EXISTS charstat.vw_zombie_candidates CASCADE;
DROP TABLE IF EXISTS charstat.charity_status CASCADE;


-- One row per charity (as published in the List of Charities export).
-- BN is the 15-character CRA Business Number (e.g. 123456789RR0001).
-- bn_root is the 9-digit prefix used everywhere else in this repo for joins.
CREATE TABLE charstat.charity_status (
  bn                    TEXT PRIMARY KEY,                 -- 15-char CRA BN (e.g. 123456789RR0001)
  bn_root               TEXT NOT NULL,                    -- 9-digit BN root, derived from LEFT(bn, 9)

  charity_name          TEXT,
  charity_name_norm     TEXT,                             -- lower-cased canonical name for fuzzy backup matching

  status                TEXT,                             -- Registered | Revoked | Annulled | Suspended
  status_effective_date DATE,                             -- "Effective Date of Status" column in CSV

  -- "Sanction" column when present in the export (rare). Examples:
  -- "Suspension of receipting privileges", "Penalty for issuing improper receipts"
  sanction              TEXT,

  designation_code      TEXT,                             -- charitable organization / public foundation / private foundation
  category_code         TEXT,                             -- T3010 category code (e.g. 0070, 0210)

  street                TEXT,
  city                  TEXT,
  province              TEXT,
  postal_code           TEXT,
  country               TEXT,

  -- Provenance — what export this row came from. The List of Charities is a
  -- live snapshot, so we keep multiple snapshots distinguishable.
  source_file           TEXT,
  source_snapshot_date  DATE
);

CREATE INDEX idx_charstat_bn_root        ON charstat.charity_status (bn_root);
CREATE INDEX idx_charstat_status         ON charstat.charity_status (status);
CREATE INDEX idx_charstat_effective_date ON charstat.charity_status (status_effective_date);
CREATE INDEX idx_charstat_name_norm      ON charstat.charity_status (charity_name_norm);


-- View: zombie-shaped charities (officially non-Registered with FED money).
-- Joined on the 9-digit BN root — same convention as `corp.vw_zombie_candidates`.
CREATE OR REPLACE VIEW charstat.vw_zombie_candidates AS
SELECT
  cs.bn,
  cs.bn_root,
  cs.charity_name,
  cs.status,
  cs.status_effective_date,
  cs.sanction,
  cs.designation_code,
  cs.province
FROM charstat.charity_status cs
WHERE cs.status IN ('Revoked', 'Annulled', 'Suspended');
