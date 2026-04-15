-- Schema: cra
-- Generated: 2026-04-15T14:44:26.598Z
-- Tables: 35

-- Table: cra.cra_activities_outside_countries
CREATE TABLE "cra"."cra_activities_outside_countries" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "country" character(2)
);

-- Table: cra.cra_activities_outside_details
CREATE TABLE "cra"."cra_activities_outside_details" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "field_200" numeric,
  "field_210" boolean,
  "field_220" boolean,
  "field_230" text,
  "field_240" boolean,
  "field_250" boolean,
  "field_260" boolean
);

-- Table: cra.cra_category_lookup
CREATE TABLE "cra"."cra_category_lookup" (
  "code" character varying(10) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text,
  "description_en" text,
  "description_fr" text
);

-- Table: cra.cra_charitable_programs
CREATE TABLE "cra"."cra_charitable_programs" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "program_type" character varying(2) NOT NULL PRIMARY KEY,
  "description" text
);

-- Table: cra.cra_compensation
CREATE TABLE "cra"."cra_compensation" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "field_300" integer,
  "field_305" integer,
  "field_310" integer,
  "field_315" integer,
  "field_320" integer,
  "field_325" integer,
  "field_330" integer,
  "field_335" integer,
  "field_340" integer,
  "field_345" integer,
  "field_370" integer,
  "field_380" numeric,
  "field_390" numeric
);

-- Table: cra.cra_country_lookup
CREATE TABLE "cra"."cra_country_lookup" (
  "code" character(2) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text
);

-- Table: cra.cra_designation_lookup
CREATE TABLE "cra"."cra_designation_lookup" (
  "code" character(1) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text,
  "description_en" text,
  "description_fr" text
);

-- Table: cra.cra_directors
CREATE TABLE "cra"."cra_directors" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "last_name" text,
  "first_name" text,
  "initials" text,
  "position" text,
  "at_arms_length" boolean,
  "start_date" date,
  "end_date" date
);

-- Table: cra.cra_disbursement_quota
CREATE TABLE "cra"."cra_disbursement_quota" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "field_805" numeric,
  "field_810" numeric,
  "field_815" numeric,
  "field_820" numeric,
  "field_825" numeric,
  "field_830" numeric,
  "field_835" numeric,
  "field_840" numeric,
  "field_845" numeric,
  "field_850" numeric,
  "field_855" numeric,
  "field_860" numeric,
  "field_865" numeric,
  "field_870" numeric,
  "field_875" numeric,
  "field_880" numeric,
  "field_885" numeric,
  "field_890" numeric
);

-- Table: cra.cra_exported_goods
CREATE TABLE "cra"."cra_exported_goods" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "item_name" text,
  "item_value" numeric,
  "destination" text,
  "country" character(2)
);

-- Table: cra.cra_financial_details
CREATE TABLE "cra"."cra_financial_details" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "section_used" character(1),
  "field_4020" character(1),
  "field_4050" boolean,
  "field_4100" numeric,
  "field_4101" numeric,
  "field_4102" numeric,
  "field_4110" numeric,
  "field_4120" numeric,
  "field_4130" numeric,
  "field_4140" numeric,
  "field_4150" numeric,
  "field_4155" numeric,
  "field_4157" numeric,
  "field_4158" numeric,
  "field_4160" numeric,
  "field_4165" numeric,
  "field_4166" numeric,
  "field_4170" numeric,
  "field_4180" numeric,
  "field_4190" numeric,
  "field_4200" numeric,
  "field_4250" numeric,
  "field_4300" numeric,
  "field_4310" numeric,
  "field_4320" numeric,
  "field_4330" numeric,
  "field_4350" numeric,
  "field_4400" boolean,
  "field_4490" boolean,
  "field_4500" numeric,
  "field_4505" numeric,
  "field_4510" numeric,
  "field_4530" numeric,
  "field_4540" numeric,
  "field_4550" numeric,
  "field_4560" numeric,
  "field_4565" boolean,
  "field_4570" numeric,
  "field_4571" numeric,
  "field_4575" numeric,
  "field_4576" numeric,
  "field_4577" numeric,
  "field_4580" numeric,
  "field_4590" numeric,
  "field_4600" numeric,
  "field_4610" numeric,
  "field_4620" numeric,
  "field_4630" numeric,
  "field_4640" numeric,
  "field_4650" numeric,
  "field_4655" numeric,
  "field_4700" numeric,
  "field_4800" numeric,
  "field_4810" numeric,
  "field_4820" numeric,
  "field_4830" numeric,
  "field_4840" numeric,
  "field_4850" numeric,
  "field_4860" numeric,
  "field_4870" numeric,
  "field_4880" numeric,
  "field_4890" numeric,
  "field_4891" numeric,
  "field_4900" numeric,
  "field_4910" numeric,
  "field_4920" numeric,
  "field_4930" numeric,
  "field_4950" numeric,
  "field_5000" numeric,
  "field_5010" numeric,
  "field_5020" numeric,
  "field_5030" numeric,
  "field_5040" numeric,
  "field_5045" numeric,
  "field_5050" numeric,
  "field_5100" numeric,
  "field_5500" numeric,
  "field_5510" numeric,
  "field_5610" numeric,
  "field_5750" numeric,
  "field_5900" numeric,
  "field_5910" numeric,
  "field_5030_indicator" text
);

-- Table: cra.cra_financial_general
CREATE TABLE "cra"."cra_financial_general" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "program_area_1" character varying(10),
  "program_area_2" character varying(10),
  "program_area_3" character varying(10),
  "program_percentage_1" integer,
  "program_percentage_2" integer,
  "program_percentage_3" integer,
  "internal_division_1510_01" integer,
  "internal_division_1510_02" integer,
  "internal_division_1510_03" integer,
  "internal_division_1510_04" integer,
  "internal_division_1510_05" integer,
  "field_1510_subordinate" boolean,
  "field_1510_parent_bn" character varying(15),
  "field_1510_parent_name" text,
  "field_1570" boolean,
  "field_1600" boolean,
  "field_1610" boolean,
  "field_1620" boolean,
  "field_1630" boolean,
  "field_1640" boolean,
  "field_1650" boolean,
  "field_1800" boolean,
  "field_2000" boolean,
  "field_2100" boolean,
  "field_2110" boolean,
  "field_2300" boolean,
  "field_2350" boolean,
  "field_2400" boolean,
  "field_2500" boolean,
  "field_2510" boolean,
  "field_2520" boolean,
  "field_2530" boolean,
  "field_2540" boolean,
  "field_2550" boolean,
  "field_2560" boolean,
  "field_2570" boolean,
  "field_2575" boolean,
  "field_2580" boolean,
  "field_2590" boolean,
  "field_2600" boolean,
  "field_2610" boolean,
  "field_2620" boolean,
  "field_2630" boolean,
  "field_2640" boolean,
  "field_2650" boolean,
  "field_2660" boolean,
  "field_2700" boolean,
  "field_2730" boolean,
  "field_2740" boolean,
  "field_2750" boolean,
  "field_2760" boolean,
  "field_2770" boolean,
  "field_2780" boolean,
  "field_2790" boolean,
  "field_2800" boolean,
  "field_3200" boolean,
  "field_3205" boolean,
  "field_3210" boolean,
  "field_3220" boolean,
  "field_3230" boolean,
  "field_3235" boolean,
  "field_3240" boolean,
  "field_3250" boolean,
  "field_3260" boolean,
  "field_3270" boolean,
  "field_3400" boolean,
  "field_3600" boolean,
  "field_3610" boolean,
  "field_3900" boolean,
  "field_4000" boolean,
  "field_4010" boolean,
  "field_5000" boolean,
  "field_5010" boolean,
  "field_5030" boolean,
  "field_5031" boolean,
  "field_5032" boolean,
  "field_5450" boolean,
  "field_5460" boolean,
  "field_5800" boolean,
  "field_5810" boolean,
  "field_5820" boolean,
  "field_5830" boolean,
  "field_5840" boolean,
  "field_5841" boolean,
  "field_5842" boolean,
  "field_5843" boolean,
  "field_5844" boolean,
  "field_5845" boolean,
  "field_5846" boolean,
  "field_5847" boolean,
  "field_5848" boolean,
  "field_5849" boolean,
  "field_5850" boolean,
  "field_5851" boolean,
  "field_5852" boolean,
  "field_5853" boolean,
  "field_5854" boolean,
  "field_5855" boolean,
  "field_5856" boolean,
  "field_5857" boolean,
  "field_5858" boolean,
  "field_5859" boolean,
  "field_5860" boolean,
  "field_5861" boolean,
  "field_5862" boolean,
  "field_5863" boolean,
  "field_5864" boolean
);

-- Table: cra.cra_foundation_info
CREATE TABLE "cra"."cra_foundation_info" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "field_100" numeric,
  "field_110" numeric,
  "field_111" numeric,
  "field_112" numeric,
  "field_120" numeric,
  "field_130" numeric
);

-- Table: cra.cra_gifts_in_kind
CREATE TABLE "cra"."cra_gifts_in_kind" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "field_500" integer,
  "field_505" integer,
  "field_510" integer,
  "field_515" integer,
  "field_520" integer,
  "field_525" integer,
  "field_530" integer,
  "field_535" integer,
  "field_540" integer,
  "field_545" integer,
  "field_550" boolean,
  "field_555" text,
  "field_560" text,
  "field_565" text,
  "field_580" numeric
);

-- Table: cra.cra_identification
CREATE TABLE "cra"."cra_identification" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fiscal_year" integer NOT NULL PRIMARY KEY,
  "category" character varying(10),
  "sub_category" character varying(10),
  "designation" character(1),
  "legal_name" text,
  "account_name" text,
  "address_line_1" text,
  "address_line_2" text,
  "city" text,
  "province" character varying(2),
  "postal_code" character varying(10),
  "country" character(2),
  "registration_date" date,
  "language" character varying(2),
  "contact_phone" text,
  "contact_email" text
);

-- Table: cra.cra_non_qualified_donees
CREATE TABLE "cra"."cra_non_qualified_donees" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "recipient_name" text,
  "purpose" text,
  "cash_amount" numeric,
  "non_cash_amount" numeric,
  "country" character(2)
);

-- Table: cra.cra_political_activity_desc
CREATE TABLE "cra"."cra_political_activity_desc" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "description" text
);

-- Table: cra.cra_political_activity_funding
CREATE TABLE "cra"."cra_political_activity_funding" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "activity" text,
  "amount" numeric,
  "country" character(2)
);

-- Table: cra.cra_political_activity_resources
CREATE TABLE "cra"."cra_political_activity_resources" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "staff" integer,
  "volunteers" integer,
  "financial" numeric,
  "property" numeric,
  "other_resource" text
);

-- Table: cra.cra_program_type_lookup
CREATE TABLE "cra"."cra_program_type_lookup" (
  "code" character varying(2) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text,
  "description_en" text,
  "description_fr" text
);

-- Table: cra.cra_province_state_lookup
CREATE TABLE "cra"."cra_province_state_lookup" (
  "code" character varying(2) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text,
  "country" character(2)
);

-- Table: cra.cra_qualified_donees
CREATE TABLE "cra"."cra_qualified_donees" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "donee_bn" character varying(15),
  "donee_name" text,
  "associated" boolean,
  "city" text,
  "province" character varying(2),
  "total_gifts" numeric,
  "gifts_in_kind" numeric,
  "number_of_donees" integer,
  "political_activity_gift" boolean,
  "political_activity_amount" numeric
);

-- Table: cra.cra_resources_sent_outside
CREATE TABLE "cra"."cra_resources_sent_outside" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fpe" date NOT NULL PRIMARY KEY,
  "form_id" integer,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "individual_org_name" text,
  "amount" numeric,
  "country" character(2)
);

-- Table: cra.cra_sub_category_lookup
CREATE TABLE "cra"."cra_sub_category_lookup" (
  "category_code" character varying(10) NOT NULL PRIMARY KEY,
  "sub_category_code" character varying(10) NOT NULL PRIMARY KEY,
  "name_en" text NOT NULL,
  "name_fr" text,
  "description_en" text,
  "description_fr" text
);

-- Table: cra.cra_web_urls
CREATE TABLE "cra"."cra_web_urls" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "fiscal_year" integer NOT NULL PRIMARY KEY,
  "sequence_number" integer NOT NULL PRIMARY KEY,
  "contact_url" text
);

-- Table: cra.identified_hubs
CREATE TABLE "cra"."identified_hubs" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "legal_name" text,
  "scc_id" integer,
  "in_degree" integer DEFAULT 0,
  "out_degree" integer DEFAULT 0,
  "total_degree" integer DEFAULT 0,
  "total_inflow" numeric DEFAULT 0,
  "total_outflow" numeric DEFAULT 0,
  "hub_type" character varying(50)
);

-- Table: cra.johnson_cycles
CREATE TABLE "cra"."johnson_cycles" (
  "id" integer NOT NULL DEFAULT nextval('cra.johnson_cycles_id_seq'::regclass) PRIMARY KEY,
  "hops" integer NOT NULL,
  "path_bns" ARRAY NOT NULL,
  "path_display" text NOT NULL,
  "bottleneck_amt" numeric,
  "total_flow" numeric,
  "min_year" integer,
  "max_year" integer
);

-- Table: cra.loop_edges
CREATE TABLE "cra"."loop_edges" (
  "src" character varying(15) NOT NULL PRIMARY KEY,
  "dst" character varying(15) NOT NULL PRIMARY KEY,
  "total_amt" numeric NOT NULL DEFAULT 0,
  "edge_count" integer NOT NULL DEFAULT 0,
  "min_year" integer,
  "max_year" integer,
  "years" ARRAY
);

-- Table: cra.loop_participants
CREATE TABLE "cra"."loop_participants" (
  "bn" character varying(15) NOT NULL,
  "loop_id" integer NOT NULL PRIMARY KEY,
  "position_in_loop" integer NOT NULL PRIMARY KEY,
  "sends_to" character varying(15),
  "receives_from" character varying(15)
);

-- Table: cra.loop_universe
CREATE TABLE "cra"."loop_universe" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "legal_name" text,
  "total_loops" integer DEFAULT 0,
  "loops_2hop" integer DEFAULT 0,
  "loops_3hop" integer DEFAULT 0,
  "loops_4hop" integer DEFAULT 0,
  "loops_5hop" integer DEFAULT 0,
  "loops_6hop" integer DEFAULT 0,
  "loops_7plus" integer DEFAULT 0,
  "max_bottleneck" numeric DEFAULT 0,
  "total_circular_amt" numeric DEFAULT 0,
  "scored_at" timestamp without time zone,
  "score" integer
);

-- Table: cra.loops
CREATE TABLE "cra"."loops" (
  "id" integer NOT NULL DEFAULT nextval('cra.loops_id_seq'::regclass) PRIMARY KEY,
  "hops" integer NOT NULL,
  "path_bns" ARRAY NOT NULL,
  "path_display" text NOT NULL,
  "bottleneck_amt" numeric,
  "total_flow" numeric,
  "min_year" integer,
  "max_year" integer
);

-- Table: cra.matrix_census
CREATE TABLE "cra"."matrix_census" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "legal_name" text,
  "walks_2" numeric DEFAULT 0,
  "walks_3" numeric DEFAULT 0,
  "walks_4" numeric DEFAULT 0,
  "walks_5" numeric DEFAULT 0,
  "walks_6" numeric DEFAULT 0,
  "walks_7" numeric DEFAULT 0,
  "walks_8" numeric DEFAULT 0,
  "max_walk_length" integer DEFAULT 0,
  "total_walk_count" numeric DEFAULT 0,
  "in_johnson_cycle" boolean DEFAULT false,
  "in_selfjoin_cycle" boolean DEFAULT false,
  "scc_id" integer,
  "scc_size" integer
);

-- Table: cra.partitioned_cycles
CREATE TABLE "cra"."partitioned_cycles" (
  "id" integer NOT NULL DEFAULT nextval('cra.partitioned_cycles_id_seq'::regclass) PRIMARY KEY,
  "hops" integer NOT NULL,
  "path_bns" ARRAY NOT NULL,
  "path_display" text NOT NULL,
  "bottleneck_amt" numeric,
  "total_flow" numeric,
  "min_year" integer,
  "max_year" integer,
  "tier" character varying(20) NOT NULL,
  "source_scc_id" integer,
  "source_scc_size" integer
);

-- Table: cra.scc_components
CREATE TABLE "cra"."scc_components" (
  "bn" character varying(15) NOT NULL PRIMARY KEY,
  "scc_id" integer NOT NULL,
  "scc_root" character varying(15) NOT NULL,
  "scc_size" integer NOT NULL,
  "legal_name" text
);

-- Table: cra.scc_summary
CREATE TABLE "cra"."scc_summary" (
  "scc_id" integer NOT NULL PRIMARY KEY,
  "scc_root" character varying(15) NOT NULL,
  "node_count" integer NOT NULL,
  "edge_count" integer NOT NULL DEFAULT 0,
  "total_internal_flow" numeric DEFAULT 0,
  "cycle_count_from_loops" integer DEFAULT 0,
  "cycle_count_from_johnson" integer DEFAULT 0,
  "top_charity_names" ARRAY
);
