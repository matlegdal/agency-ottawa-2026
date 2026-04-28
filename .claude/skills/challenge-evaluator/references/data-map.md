# Per-Challenge Data Map

Lookup table mapping each of the 10 challenges in `challenges.md` to the schemas, tables/views, existing scripts, and known caveats. Use this as the starting point for the **Data** dimension. Always verify against the per-module `CLAUDE.md` and `KNOWN-DATA-ISSUES.md` before scoring — this map can drift.

Source of truth for the canonical mapping is the table in the **root** `CLAUDE.md` ("Working on hackathon challenges"). This file extends it with the data-completeness and external-data notes needed for evaluation.

---

## 1. Zombie Recipients

- **Schemas:** `fed`, `cra`, `ab`, `general`
- **Core tables/views:**
  - `fed.grants_contributions`, `fed.vw_agreement_current` (committed values — avoids the cumulative-snapshot trap)
  - `cra.cra_identification` (registration/revocation status, designation)
  - `ab.ab_non_profit` (status = dissolved / struck-off)
  - `general.entity_golden_records` (BN-aware cross-dataset key)
- **Existing scripts:** `FED/scripts/advanced/05-zombie-and-ghost.js`, plan `plans/zombie_agent_build_manual_v2.md`
- **Completeness:** strong — revocation/dissolution signals exist directly. Gap: post-funding "ceased operations" for FED-only recipients (no CRA registration, no AB record) must be inferred from absence of subsequent filings.
- **External data that could help:** federal corporate registry (Corporations Canada), provincial registries beyond AB, OpenSanctions PEP list to spot ex-public-servant principals.

## 2. Ghost Capacity

- **Schemas:** `cra`, `fed`, `general`
- **Core tables:** `cra.cra_compensation` (employee counts + comp brackets), `cra.cra_financial_details` (revenue mix, expenditure ratios), `fed.grants_contributions`
- **Existing scripts:** `FED/scripts/advanced/05-zombie-and-ghost.js` (shared with Challenge 1)
- **Completeness:** strong for CRA-registered entities. Gap: non-charity FED/AB recipients have no employee/revenue panel — must rely on CRA-only or accept the scope limit.
- **External data that could help:** SimplyAnalytics / Statistics Canada Business Register for headcount, LinkedIn/Crunchbase for evidence-of-operations.

## 3. Funding Loops

- **Schemas:** `cra`
- **Core tables:** `cra.cra_qualified_donees` (gift-giving records); pre-computed circular-flow / SCC / Johnson-cycle / overhead / risk-scoring tables already exist in `cra` schema (see `CRA/CLAUDE.md`).
- **Existing scripts:** `CRA/scripts/advanced/01-detect-all-loops.js`, `03-scc-decomposition.js`, `06-johnson-cycles.js`
- **Completeness:** very strong — most heavy lifting already done. Gap: dollar amounts on `cra_qualified_donees` are charity-reported and may be partial.
- **Caveat:** **designation A vs B vs C completely changes interpretation** (see `CRA/CLAUDE.md`). Public foundations (A) cycle by design; charitable orgs (C) cycling are the actual signal.
- **External data that could help:** denominational hierarchy mappings (United Church, Catholic dioceses) to whitelist structurally-normal loops.

## 4. Sole Source and Amendment Creep

- **Schemas:** `fed`, `ab`
- **Core tables/views:** `fed.grants_contributions` (`is_amendment`, `vw_agreement_current`, `vw_agreement_originals`), `ab.ab_sole_source`, `ab.ab_contracts`
- **Existing scripts:** `FED/scripts/advanced/03-amendment-creep.js`, `AB/scripts/advanced/04-sole-source-deep-dive.js`
- **Completeness:** strong on FED with the views. AB has explicit sole-source records. Gap: contracts split below competitive thresholds requires inferring threshold from procurement policy (TBS Contracting Policy threshold = $25K for goods, $40K for services historically).
- **Caveat:** `fed.agreement_value` is cumulative per amendment — never `SUM` raw. `fed.ref_number` is not unique across recipients (F-1).
- **External data that could help:** TBS proactive-disclosure contracts (richer original-vs-amended trail than the open dataset).

## 5. Vendor Concentration

- **Schemas:** `fed`, `ab`
- **Core tables:** `fed.grants_contributions`, `ab.ab_contracts`, `ab.ab_sole_source`
- **Existing scripts:** `FED/scripts/advanced/04-recipient-concentration.js`
- **Completeness:** very strong. HHI / top-N share / per-category concentration are well-defined and the data supports them.
- **Caveat:** AB contracts must be name-matched (no BNs) — route through `general.entity_golden_records`.
- **External data that could help:** GSIN/UNSPSC code mappings for category normalization across FED and AB.

## 6. Related Parties and Governance Networks

- **Schemas:** `cra`, `general`, `fed`, `ab`
- **Core tables:** `cra.cra_directors` (director names per filing year), `general.entity_golden_records`, contract/grant tables
- **Existing scripts:** none yet
- **Completeness:** medium. Director names exist but **person-level entity resolution is not done** — `general` resolves organizations, not people. Names like "John Smith" must be disambiguated by co-occurring orgs / time / role.
- **Caveat:** corporate directors (companies, not charities) require an external corporate-registry feed.
- **External data that could help:** Corporations Canada bulk download, OpenSanctions PEP list, provincial corporate registries.

## 7. Policy Misalignment

- **Schemas:** `fed`, `ab` (spending side); none for policy commitments
- **Core tables:** any spending table tagged by program/department
- **Existing scripts:** none
- **Completeness:** low. Spending side is fine. **Stated policy commitments do not exist in the DB** — must be ingested from Mandate Letters, Budget tables, Speech from the Throne, departmental plans.
- **External data that could help:** GC InfoBase, Budget table CSVs from Finance Canada, Treasury Board departmental plans.
- **Score implication:** Data score capped at ~2 unless the team commits to ingesting policy commitments as part of the build.

## 8. Duplicative Funding (and Funding Gaps)

- **Schemas:** `fed`, `ab`, `general`
- **Core tables:** `fed.grants_contributions`, `ab.ab_grants` (and equivalents), `general.entity_golden_records`
- **Existing scripts:** none
- **Completeness:** medium-strong for the duplication side (entity + program-purpose join through `general`). Weak for the gap side: detecting *absence* of funding for a stated priority requires policy-side data (see Challenge 7).
- **Caveat:** "same purpose" is fuzzy — requires program-name matching or LLM categorization.
- **External data that could help:** provincial spending datasets beyond AB (BC, ON, QC) for fuller "multiple levels of government" coverage.

## 9. Contract Intelligence

- **Schemas:** `fed`, `ab`
- **Core tables:** `fed.grants_contributions`, `ab.ab_contracts`
- **Existing scripts:** none
- **Completeness:** medium. Year-over-year cost growth is computable but **unit cost is not directly recorded** — must infer from category + dollar + (optional) quantity fields, which are sparse.
- **Caveat:** decomposition into volume vs unit cost vs concentration requires GSIN/UNSPSC normalization (same gap as Challenge 5).
- **External data that could help:** GSIN catalog, historical TBS price benchmarks if obtainable.

## 10. Adverse Media

- **Schemas:** `general` (recipient list); none for media
- **Core tables:** `general.entity_golden_records` to anchor the entity list
- **Existing scripts:** none
- **Completeness:** very low. **The repo has no media corpus.** Entire pipeline must be built: ingestion, source-quality filter, entity matching, severity classification.
- **External data that could help (essential):** GDELT, OpenSanctions, regulatory enforcement registries (CRA charity sanctions, Competition Bureau, OSFI), news APIs.
- **Score implication:** Data score 1 unless an external feed is in scope; Implementation difficulty 1–2 because the LLM judgment-at-scale problem is hard to make demo-stable in one day.

---

## Cross-cutting reminders

- **Always go through `general.entity_golden_records` for cross-dataset joins.** Do not BN-join AB directly.
- **Always normalize BNs via `general.extract_bn_root()` and validate via `general.is_valid_bn_root()`.**
- **Always use `fed.vw_agreement_current` / `fed.vw_agreement_originals` instead of `SUM(agreement_value)`.**
- **Always check `KNOWN-DATA-ISSUES.md`** for the F-/C-/A- entries on tables you cite. If an entry is **Active** (no mitigation), call it out as a risk.
