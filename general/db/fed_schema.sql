-- Schema: fed
-- Generated: 2026-04-13T15:06:03.469Z
-- Tables: 6

-- Table: fed.agreement_type_lookup
CREATE TABLE "fed"."agreement_type_lookup" (
  "code" character varying(2) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);

-- Table: fed.country_lookup
CREATE TABLE "fed"."country_lookup" (
  "code" character varying(4) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);

-- Table: fed.currency_lookup
CREATE TABLE "fed"."currency_lookup" (
  "code" character varying(4) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);

-- Table: fed.grants_contributions
CREATE TABLE "fed"."grants_contributions" (
  "_id" integer NOT NULL PRIMARY KEY,
  "ref_number" text,
  "amendment_number" text,
  "amendment_date" date,
  "agreement_type" text,
  "agreement_number" text,
  "recipient_type" text,
  "recipient_business_number" text,
  "recipient_legal_name" text,
  "recipient_operating_name" text,
  "research_organization_name" text,
  "recipient_country" text,
  "recipient_province" text,
  "recipient_city" text,
  "recipient_postal_code" text,
  "federal_riding_name_en" text,
  "federal_riding_name_fr" text,
  "federal_riding_number" text,
  "prog_name_en" text,
  "prog_name_fr" text,
  "prog_purpose_en" text,
  "prog_purpose_fr" text,
  "agreement_title_en" text,
  "agreement_title_fr" text,
  "agreement_value" numeric,
  "foreign_currency_type" text,
  "foreign_currency_value" numeric,
  "agreement_start_date" date,
  "agreement_end_date" date,
  "coverage" text,
  "description_en" text,
  "description_fr" text,
  "expected_results_en" text,
  "expected_results_fr" text,
  "additional_information_en" text,
  "additional_information_fr" text,
  "naics_identifier" text,
  "owner_org" text,
  "owner_org_title" text,
  "is_amendment" boolean DEFAULT false
);

-- Table: fed.province_lookup
CREATE TABLE "fed"."province_lookup" (
  "code" character varying(4) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);

-- Table: fed.recipient_type_lookup
CREATE TABLE "fed"."recipient_type_lookup" (
  "code" character varying(2) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);
