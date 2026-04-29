-- Federal Corporations Registry schema for the AI for Accountability Hackathon.
-- Source: Innovation, Science and Economic Development Canada (Corporations Canada)
-- https://ised-isde.canada.ca/cc/lgcy/download/OPEN_DATA_SPLIT.zip
--
-- The source is 103 chunked XML files (~25 MB each) with one <corporation>
-- element per company. We flatten the most useful per-corporation fields
-- into corp_corporations, and keep per-event history tables for status
-- changes and name changes (the timeline is what makes the zombie story
-- vivid: "incorporated 1989 → struck off 2023").

CREATE SCHEMA IF NOT EXISTS corp;

DROP TABLE IF EXISTS corp.corp_status_history CASCADE;
DROP TABLE IF EXISTS corp.corp_name_history CASCADE;
DROP TABLE IF EXISTS corp.corp_corporations CASCADE;


-- One row per federal corporation.
-- "Current" fields are denormalized snapshots of the row in the
-- corresponding history table whose current="true". History tables
-- preserve every transition.
CREATE TABLE corp.corp_corporations (
  corporation_id            INTEGER PRIMARY KEY,                  -- corporationId attribute

  -- Current name (from <names> where current="true")
  current_name              TEXT,
  current_name_norm         TEXT,                                 -- lowercase, deburr-ish, for join to FED/AB

  -- Current status (from <statuses> where current="true")
  current_status_code       SMALLINT,                             -- 1=Active, 2=Intent to Dissolve, 3=Dissolution Pending, 4=Discontinuance Pending, 9=Inactive-Amalgamated, 10=Inactive-Discontinued, 11=Dissolved, 19=Inactive
  current_status_label      TEXT,                                 -- denormalized human-readable label
  current_status_date       TIMESTAMP,                            -- effectiveDate of the current status

  -- Current act (from <acts> where current="true")
  current_act_code          SMALLINT,                             -- 6=CBCA, 14=NFP Act, etc.
  current_act_label         TEXT,

  -- Incorporation date (earliest activity with code 1, or earliest annualReturn)
  incorporation_date        DATE,

  -- Dissolution date (most recent activity with code 101=Dissolution, if any)
  dissolution_date          DATE,

  -- Intent-to-dissolve filed (activity code 14, most recent)
  intent_to_dissolve_date   DATE,

  -- Most recent annual return filed
  last_annual_return_year   INTEGER,                              -- yearOfFiling
  last_annual_return_date   DATE,                                 -- annualMeetingDate

  -- Current head office address
  current_address_line      TEXT,
  current_city              TEXT,
  current_province          TEXT,                                 -- 2-letter code
  current_country           TEXT,                                 -- 2-letter code (often CA)
  current_postal_code       TEXT,

  -- Federal Business Number (9-digit). Some corps have multiple BNs over time;
  -- we keep the first one returned. Use general.extract_bn_root() to compare
  -- with FED/CRA — but here this is already 9-digit-clean.
  business_number           TEXT,

  -- Director count limits (corporation-level rule, not actual directors).
  -- INTEGER (not SMALLINT) because some corps register 999999 as "no limit".
  director_min              INTEGER,
  director_max              INTEGER
);

CREATE INDEX idx_corp_name_norm    ON corp.corp_corporations (current_name_norm);
CREATE INDEX idx_corp_status_code  ON corp.corp_corporations (current_status_code);
CREATE INDEX idx_corp_bn           ON corp.corp_corporations (business_number);
CREATE INDEX idx_corp_diss_date    ON corp.corp_corporations (dissolution_date);
CREATE INDEX idx_corp_intent_date  ON corp.corp_corporations (intent_to_dissolve_date);


-- One row per status change. Same corporation can transition many times.
CREATE TABLE corp.corp_status_history (
  corporation_id            INTEGER NOT NULL,
  status_code               SMALLINT,
  status_label              TEXT,
  effective_date            TIMESTAMP,
  is_current                BOOLEAN
);

CREATE INDEX idx_corp_sh_corp_id   ON corp.corp_status_history (corporation_id);
CREATE INDEX idx_corp_sh_status    ON corp.corp_status_history (status_code);


-- One row per (current or historical) name. Useful for matching FED grants
-- recorded under an old name to the now-current corporate identity.
CREATE TABLE corp.corp_name_history (
  corporation_id            INTEGER NOT NULL,
  name                      TEXT,
  name_norm                 TEXT,
  effective_date            TIMESTAMP,
  expiry_date               TIMESTAMP,
  is_current                BOOLEAN
);

CREATE INDEX idx_corp_nh_corp_id     ON corp.corp_name_history (corporation_id);
CREATE INDEX idx_corp_nh_name_norm   ON corp.corp_name_history (name_norm);


-- View: zombie-shaped corporations (likely-dead but with recent govt money)
CREATE OR REPLACE VIEW corp.vw_zombie_candidates AS
SELECT
  c.corporation_id,
  c.current_name,
  c.current_name_norm,
  c.business_number,
  c.current_status_code,
  c.current_status_label,
  c.current_status_date,
  c.dissolution_date,
  c.intent_to_dissolve_date,
  c.last_annual_return_year,
  c.incorporation_date,
  c.current_province
FROM corp.corp_corporations c
WHERE c.current_status_code IN (
    2,   -- Active - Intent to Dissolve Filed
    3,   -- Active - Dissolution Pending (Non-compliance)
    11,  -- Dissolved
    19,  -- Inactive
    10,  -- Inactive - Discontinued
    9    -- Inactive - Amalgamated
)
   OR (c.last_annual_return_year IS NOT NULL AND c.last_annual_return_year < EXTRACT(YEAR FROM CURRENT_DATE) - 2);
