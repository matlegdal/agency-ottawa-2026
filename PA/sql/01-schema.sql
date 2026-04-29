-- Public Accounts transfer payments schema for the AI for Accountability Hackathon.
-- Source: Public Services and Procurement Canada (PSPC) — Public Accounts Volume III
-- Bulk download: https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/pt-tp/pt-tp-{YEAR}.csv
--
-- This is the AUDITED, post-fiscal-year-end record of transfer payments
-- (grants, contributions, other transfer payments). It complements the
-- pre-audit TBS proactive disclosure we already have in the `fed` schema:
--
--   fed.grants_contributions  → unaudited, real-time, agreement-shaped (one
--                               row per amendment with cumulative snapshots)
--   pa.transfer_payments      → audited, post-year-end, recipient-shaped
--                               (one row per recipient × department × program ×
--                               fiscal year with the actual cash paid)
--
-- The two-way comparison lets us flag zombies who appeared in the proactive
-- disclosure (a grant agreement was signed) but did not draw down the money
-- (no row in Public Accounts, or smaller PA amount than the agreement value).

CREATE SCHEMA IF NOT EXISTS pa;

DROP TABLE IF EXISTS pa.transfer_payments CASCADE;

CREATE TABLE pa.transfer_payments (
  fiscal_year             TEXT NOT NULL,        -- e.g. "2023/2024"
  fiscal_year_end         INTEGER,              -- 2024 — the calendar year the FY ends in (computed)

  ministry_code           TEXT,                 -- 2-digit ministry code
  ministry_portfolio      TEXT,                 -- e.g. "Agriculture and Agri-Food"
  department_number       TEXT,                 -- 3-digit dept code
  department_name         TEXT,                 -- e.g. "Department of Agriculture and Agri-Food"

  recipient_class         TEXT,                 -- the program / grant class. Free text, can be very long.
  recipient_name_location TEXT,                 -- the recipient line — name + location concatenated. Free text.
  recipient_name_norm     TEXT,                 -- normalized name extracted from recipient_name_location

  city                    TEXT,
  province                TEXT,                 -- e.g. "Ontario", or NULL
  country                 TEXT,                 -- usually "Canada", sometimes US/UK/etc.

  expenditure_current_yr  NUMERIC(18,2),        -- "Xpnd-current-yr" — cash paid this fiscal year
  aggregate_payments      NUMERIC(18,2),        -- cumulative amount across years (often 0 or NULL)

  source_file             TEXT NOT NULL         -- which CSV this row came from
);

CREATE INDEX idx_pa_fy             ON pa.transfer_payments (fiscal_year_end);
CREATE INDEX idx_pa_dept           ON pa.transfer_payments (department_name);
CREATE INDEX idx_pa_recipient_norm ON pa.transfer_payments (recipient_name_norm);
CREATE INDEX idx_pa_amount         ON pa.transfer_payments (expenditure_current_yr) WHERE expenditure_current_yr > 0;


-- View: per-recipient aggregate across all years
CREATE OR REPLACE VIEW pa.vw_recipient_totals AS
SELECT
  recipient_name_norm,
  MIN(recipient_name_location) AS sample_name,
  COUNT(DISTINCT fiscal_year_end) AS years_appeared,
  MIN(fiscal_year_end) AS first_year,
  MAX(fiscal_year_end) AS last_year,
  SUM(expenditure_current_yr) AS total_paid
FROM pa.transfer_payments
WHERE recipient_name_norm IS NOT NULL
GROUP BY recipient_name_norm;
