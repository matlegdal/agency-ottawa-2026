-- Schema: ab
-- Generated: 2026-04-13T15:04:40.004Z
-- Tables: 9

-- Table: ab.ab_contracts
CREATE TABLE "ab"."ab_contracts" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  "display_fiscal_year" text,
  "recipient" text,
  "amount" numeric,
  "ministry" text
);

-- Table: ab.ab_grants
CREATE TABLE "ab"."ab_grants" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_grants_id_seq'::regclass) PRIMARY KEY,
  "mongo_id" character varying(255),
  "ministry" text,
  "business_unit_name" text,
  "recipient" text,
  "program" text,
  "amount" numeric,
  "lottery" text,
  "payment_date" timestamp without time zone,
  "fiscal_year" text,
  "display_fiscal_year" text,
  "lottery_fund" text,
  "data_quality" boolean,
  "data_quality_issues" jsonb,
  "version" integer,
  "created_at" timestamp without time zone,
  "updated_at" timestamp without time zone
);

-- Table: ab.ab_grants_fiscal_years
CREATE TABLE "ab"."ab_grants_fiscal_years" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_grants_fiscal_years_id_seq'::regclass) PRIMARY KEY,
  "mongo_id" character varying(255),
  "display_fiscal_year" text,
  "count" integer,
  "total_amount" numeric,
  "last_updated" timestamp without time zone,
  "version" integer
);

-- Table: ab.ab_grants_ministries
CREATE TABLE "ab"."ab_grants_ministries" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_grants_ministries_id_seq'::regclass) PRIMARY KEY,
  "mongo_id" character varying(255),
  "ministry" text,
  "display_fiscal_year" text,
  "aggregation_type" text,
  "count" integer,
  "total_amount" numeric,
  "last_updated" timestamp without time zone,
  "version" integer
);

-- Table: ab.ab_grants_programs
CREATE TABLE "ab"."ab_grants_programs" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_grants_programs_id_seq'::regclass) PRIMARY KEY,
  "mongo_id" character varying(255),
  "program" text,
  "ministry" text,
  "display_fiscal_year" text,
  "aggregation_type" text,
  "count" integer,
  "total_amount" numeric,
  "last_updated" timestamp without time zone,
  "version" integer
);

-- Table: ab.ab_grants_recipients
CREATE TABLE "ab"."ab_grants_recipients" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_grants_recipients_id_seq'::regclass) PRIMARY KEY,
  "mongo_id" character varying(255),
  "recipient" text,
  "payments_count" integer,
  "payments_amount" numeric,
  "programs_count" integer,
  "ministries_count" integer,
  "last_updated" timestamp without time zone,
  "version" integer
);

-- Table: ab.ab_non_profit
CREATE TABLE "ab"."ab_non_profit" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  "type" text,
  "legal_name" text,
  "status" text,
  "registration_date" date,
  "city" text,
  "postal_code" text
);

-- Table: ab.ab_non_profit_status_lookup
CREATE TABLE "ab"."ab_non_profit_status_lookup" (
  "id" integer NOT NULL DEFAULT nextval('ab.ab_non_profit_status_lookup_id_seq'::regclass) PRIMARY KEY,
  "status" text NOT NULL,
  "description" text
);

-- Table: ab.ab_sole_source
CREATE TABLE "ab"."ab_sole_source" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  "ministry" text,
  "department_street" text,
  "department_street_2" text,
  "department_city" text,
  "department_province" text,
  "department_postal_code" text,
  "department_country" text,
  "vendor" text,
  "vendor_street" text,
  "vendor_street_2" text,
  "vendor_city" text,
  "vendor_province" text,
  "vendor_postal_code" text,
  "vendor_country" text,
  "start_date" date,
  "end_date" date,
  "amount" numeric,
  "contract_number" text,
  "contract_services" text,
  "permitted_situations" text,
  "display_fiscal_year" text,
  "special" text
);
