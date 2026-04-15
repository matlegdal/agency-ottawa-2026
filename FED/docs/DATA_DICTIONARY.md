# Federal Grants and Contributions - Data Dictionary

## Source

- **Dataset**: Proactive Publication - Grants and Contributions
- **Portal**: [Government of Canada Open Data](https://open.canada.ca)
- **Resource ID**: `1d15a62f-5656-49ad-8c88-f40ce689d831`
- **Schema**: `fed`
- **Table**: `fed.grants_contributions`

## Main Table: `fed.grants_contributions`

| Column | Type | Description |
|--------|------|-------------|
| `_id` | INTEGER (PK) | Internal row ID from Open Data API |
| `ref_number` | TEXT | Department reference number (DDD-YYYY-YYYY-QX-XXXXX) |
| `amendment_number` | TEXT | Amendment number (0 = original) |
| `amendment_date` | DATE | Date of amendment |
| `agreement_type` | TEXT | G=Grant, C=Contribution, O=Other transfer payment |
| `agreement_number` | TEXT | Agreement number |
| `recipient_type` | TEXT | A=Indigenous, F=For-profit, G=Government, I=International, N=Not-for-profit, O=Other, P=Individual, S=Academia |
| `recipient_business_number` | TEXT | 9-digit CRA business number |
| `recipient_legal_name` | TEXT | Legal name (English\|French) |
| `recipient_operating_name` | TEXT | Operating/trade name |
| `research_organization_name` | TEXT | Academic partner organization |
| `recipient_country` | TEXT | ISO country code (e.g., CA) |
| `recipient_province` | TEXT | Province/territory code (e.g., AB, ON, QC) |
| `recipient_city` | TEXT | City name |
| `recipient_postal_code` | TEXT | Canadian postal code (A1A 1A1) |
| `federal_riding_name_en` | TEXT | Federal riding name (English) |
| `federal_riding_name_fr` | TEXT | Federal riding name (French) |
| `federal_riding_number` | TEXT | 5-digit federal riding code |
| `prog_name_en` | TEXT | Program name (English) |
| `prog_name_fr` | TEXT | Program name (French) |
| `prog_purpose_en` | TEXT | Program purpose (English) |
| `prog_purpose_fr` | TEXT | Program purpose (French) |
| `agreement_title_en` | TEXT | Agreement title (English) |
| `agreement_title_fr` | TEXT | Agreement title (French) |
| `agreement_value` | DECIMAL(15,2) | Agreement value in CAD |
| `foreign_currency_type` | TEXT | Foreign currency code (e.g., USD) |
| `foreign_currency_value` | DECIMAL(15,2) | Amount in foreign currency |
| `agreement_start_date` | DATE | Agreement start date |
| `agreement_end_date` | DATE | Agreement end date |
| `coverage` | TEXT | Coverage information |
| `description_en` | TEXT | Description (English) |
| `description_fr` | TEXT | Description (French) |
| `expected_results_en` | TEXT | Expected results (English) |
| `expected_results_fr` | TEXT | Expected results (French) |
| `additional_information_en` | TEXT | Additional info (English) |
| `additional_information_fr` | TEXT | Additional info (French) |
| `naics_identifier` | TEXT | NAICS industry classification code |
| `owner_org` | TEXT | Department code |
| `owner_org_title` | TEXT | Department name (bilingual) |

## Reference/Lookup Tables

### `fed.agreement_type_lookup`
| Code | English | French |
|------|---------|--------|
| G | Grant | subvention |
| C | Contribution | contribution |
| O | Other transfer payment | autre |

### `fed.recipient_type_lookup`
| Code | English | French |
|------|---------|--------|
| A | Indigenous recipients | beneficiaire autochtone |
| F | For-profit organizations | organisme a but lucratif |
| G | Government | gouvernement |
| I | International (non-government) | organisation internationale |
| N | Not-for-profit organizations and charities | organisme a but non lucratif |
| O | Other | autre |
| P | Individual or sole proprietorships | particulier |
| S | Academia | etablissement universitaire |

### `fed.country_lookup`
249+ countries with ISO 3166 codes. English and French names.

### `fed.province_lookup`
13 Canadian provinces and territories (AB, BC, MB, NB, NL, NS, NT, NU, ON, PE, QC, SK, YT).

### `fed.currency_lookup`
100+ world currencies with ISO 4217 codes.

## Views

### `fed.vw_grants_decoded`
Joins grants_contributions with all lookup tables to provide human-readable names for codes.

### `fed.vw_grants_by_department`
Aggregated summary: grant count, total value, avg value by department and agreement type.

### `fed.vw_grants_by_province`
Aggregated summary: grant count, total value, avg value by province.

## Key Indexes

- Agreement type, recipient type, province, country (filter queries)
- Start date, end date (date range queries)
- Agreement value (range queries)
- Owner org (department analysis)
- Full-text search on recipient name and program name (GIN indexes)
- NAICS identifier, federal riding number (classification queries)
