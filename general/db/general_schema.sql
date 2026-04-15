-- Schema: general
-- Generated: 2026-04-13T15:06:13.756Z
-- Tables: 1

-- Table: general.ministries
CREATE TABLE "general"."ministries" (
  "id" integer NOT NULL DEFAULT nextval('general.ministries_id_seq'::regclass) PRIMARY KEY,
  "short_name" character varying(20) NOT NULL,
  "name" text NOT NULL,
  "description" text,
  "minister" text,
  "deputy_minister" text,
  "effective_from" date,
  "effective_to" date,
  "is_active" boolean DEFAULT true,
  "created_at" timestamp without time zone DEFAULT now(),
  "updated_at" timestamp without time zone DEFAULT now()
);
