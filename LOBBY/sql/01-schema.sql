-- Lobbying Registry schema for the AI for Accountability Hackathon.
-- Source: Office of the Commissioner of Lobbying of Canada (OCL)
-- https://lobbycanada.gc.ca/  (bulk CSV via open.canada.ca)
--
-- Two source bundles:
--   1. registrations_enregistrements_ocl_cal.zip  → 11 CSVs about registrations
--   2. communications_ocl_cal.zip                  → 4 CSVs about monthly comms
--
-- We load the four most useful tables for the zombie-agent augmentation:
--   - lobby_registrations         (one row per registration version)
--   - lobby_govt_funding          (self-disclosed govt funding per registration)
--   - lobby_communications        (one row per communication report)
--   - lobby_communication_dpoh    (the DPOH targeted in each communication)

CREATE SCHEMA IF NOT EXISTS lobby;

DROP TABLE IF EXISTS lobby.lobby_communication_dpoh CASCADE;
DROP TABLE IF EXISTS lobby.lobby_communications CASCADE;
DROP TABLE IF EXISTS lobby.lobby_govt_funding CASCADE;
DROP TABLE IF EXISTS lobby.lobby_registrations CASCADE;

CREATE TABLE lobby.lobby_registrations (
  reg_id                          BIGINT PRIMARY KEY,             -- REG_ID_ENR
  reg_type                        SMALLINT,                       -- 1=consultant, 2=in-house corp, 3=in-house org
  reg_num                         TEXT,                           -- REG_NUM_ENR  (e.g. 777140-5070-1)
  version_code                    TEXT,                           -- VERSION_CODE (V4, V5, …)

  firm_name_en                    TEXT,
  firm_name_fr                    TEXT,
  registrant_position             TEXT,
  firm_address                    TEXT,
  firm_tel                        TEXT,
  firm_fax                        TEXT,

  registrant_num                  TEXT,
  registrant_last_nm              TEXT,
  registrant_first_nm             TEXT,
  ro_position                     TEXT,
  registrant_address              TEXT,
  registrant_tel                  TEXT,
  registrant_fax                  TEXT,

  client_org_corp_profile_id      TEXT,
  client_org_corp_num             TEXT,
  client_name_en                  TEXT,                           -- THIS is the recipient/client side we care about
  client_name_fr                  TEXT,
  client_address                  TEXT,
  client_tel                      TEXT,
  client_fax                      TEXT,

  rep_last_nm                     TEXT,
  rep_first_nm                    TEXT,
  rep_position                    TEXT,

  effective_date                  DATE,                           -- registration becomes effective
  end_date                        DATE,                           -- registration termination

  parent_ind                      TEXT,                           -- Y/N
  coalition_ind                   TEXT,
  subsidiary_ind                  TEXT,
  direct_int_ind                  TEXT,
  govt_fund_ind                   TEXT,                           -- Y/N: did this client receive govt funding?
  fy_end_date                     DATE,
  contg_fee_ind                   TEXT,                           -- Y/N: contingency fee
  prev_reg_id                     BIGINT,
  posted_date                     DATE,

  -- Normalized helpers (populated by import step)
  client_name_norm                TEXT,
  client_org_corp_num_int         BIGINT
);

CREATE INDEX idx_lobby_reg_client_norm  ON lobby.lobby_registrations (client_name_norm);
CREATE INDEX idx_lobby_reg_client_num   ON lobby.lobby_registrations (client_org_corp_num_int);
CREATE INDEX idx_lobby_reg_effective    ON lobby.lobby_registrations (effective_date);
CREATE INDEX idx_lobby_reg_end          ON lobby.lobby_registrations (end_date);
CREATE INDEX idx_lobby_reg_govt_fund    ON lobby.lobby_registrations (govt_fund_ind) WHERE govt_fund_ind = 'Y';
CREATE INDEX idx_lobby_reg_type         ON lobby.lobby_registrations (reg_type);


CREATE TABLE lobby.lobby_govt_funding (
  -- Composite key — same registration can list multiple funding sources.
  reg_id                          BIGINT NOT NULL,                -- REG_ID_ENR
  institution                     TEXT,
  amount                          NUMERIC(18,2),                  -- AMOUNT_MONTANT
  funds_expected                  TEXT,                           -- FUNDS_EXP_FIN_ATTENDU (Y/N)
  text_description                TEXT,                           -- free-text purpose
  amend_sub_date                  DATE                            -- AMEND_SUB_DATE_SOUM_AMEND
);

CREATE INDEX idx_lobby_fund_reg     ON lobby.lobby_govt_funding (reg_id);
CREATE INDEX idx_lobby_fund_inst    ON lobby.lobby_govt_funding (institution);
CREATE INDEX idx_lobby_fund_amount  ON lobby.lobby_govt_funding (amount) WHERE amount IS NOT NULL;


CREATE TABLE lobby.lobby_communications (
  comlog_id                       BIGINT PRIMARY KEY,             -- COMLOG_ID
  client_org_corp_num             TEXT,
  client_name_en                  TEXT,
  client_name_fr                  TEXT,
  registrant_num                  TEXT,
  registrant_last_nm              TEXT,
  registrant_first_nm             TEXT,
  comm_date                       DATE,                           -- date of communication
  reg_type                        SMALLINT,
  submission_date                 DATE,
  posted_date                     DATE,
  prev_comlog_id                  BIGINT,

  client_name_norm                TEXT,
  client_org_corp_num_int         BIGINT
);

CREATE INDEX idx_lobby_com_client_norm ON lobby.lobby_communications (client_name_norm);
CREATE INDEX idx_lobby_com_client_num  ON lobby.lobby_communications (client_org_corp_num_int);
CREATE INDEX idx_lobby_com_date        ON lobby.lobby_communications (comm_date);


CREATE TABLE lobby.lobby_communication_dpoh (
  comlog_id                       BIGINT NOT NULL,
  dpoh_last_nm                    TEXT,
  dpoh_first_nm                   TEXT,
  dpoh_title                      TEXT,
  branch_unit                     TEXT,
  other_institution               TEXT,
  institution                     TEXT
);

CREATE INDEX idx_lobby_dpoh_comlog      ON lobby.lobby_communication_dpoh (comlog_id);
CREATE INDEX idx_lobby_dpoh_institution ON lobby.lobby_communication_dpoh (institution);


-- View: per-client lobbying activity summary (the join target for the verifier)
CREATE OR REPLACE VIEW lobby.vw_client_activity AS
SELECT
  r.client_name_norm,
  MAX(r.client_name_en)               AS client_name_en,
  MAX(r.client_org_corp_num)          AS client_org_corp_num,
  COUNT(DISTINCT r.reg_id)            AS registrations_count,
  MIN(r.effective_date)               AS first_registration_date,
  MAX(r.effective_date)               AS last_registration_date,
  MAX(r.end_date)                     AS last_end_date,
  BOOL_OR(r.govt_fund_ind = 'Y')      AS ever_received_govt_funding
FROM lobby.lobby_registrations r
WHERE r.client_name_norm IS NOT NULL
GROUP BY r.client_name_norm;


-- View: communications enriched with DPOH targets
CREATE OR REPLACE VIEW lobby.vw_communications_with_dpoh AS
SELECT
  c.comlog_id,
  c.client_name_en,
  c.client_name_norm,
  c.client_org_corp_num,
  c.comm_date,
  c.posted_date,
  c.registrant_last_nm,
  c.registrant_first_nm,
  d.institution                    AS dpoh_institution,
  d.dpoh_title,
  d.dpoh_last_nm,
  d.dpoh_first_nm
FROM lobby.lobby_communications c
LEFT JOIN lobby.lobby_communication_dpoh d ON d.comlog_id = c.comlog_id;
