# CHRONOS Phase 1.5 — Integration Verification Result

**Demonstration:** `CHRONOS-DEMO-001`
**Verification date:** 2026-07-26 America/Phoenix
**Scope:** Read-only governance and business context for the verified Phase
1.4 lineage graph

## Final result

**Verified:** Phase 1.5 completed successfully against the current local
DataHub showcase.

**Verified:** The result is context, not impact analysis. No metadata in this
report proves that an asset is broken by the proposed
`order_total` → `order_amount` rename.

## Prerequisites

| Prerequisite | Observed result |
|---|---|
| Phase 1.1 readiness | `ready` |
| Phase 1.2 PostgreSQL `orders` identity | `resolved` |
| Phase 1.2 `order_total` identity | `resolved` |
| Phase 1.3 source schema | `retrieved`, 15 fields |
| Phase 1.4 downstream fields | 25 |
| Phase 1.4 downstream datasets | 20 |
| Phase 1.4 maximum field depth | 5 |

**Verified:** Phase 1.5 did not modify the Phase 1.4 graph or its counts.

## Context scope

The context scope is built from `FieldLineageGraph.dataset_index`, not a
global showcase search.

| Scope item | Count |
|---|---:|
| Canonical source datasets | 1 |
| Unique downstream datasets | 20 |
| Total context-enriched datasets | 21 |

**Verified:** Every dataset that appears as a source, intermediate, or
downstream dataset in the verified field graph is included.

**Verified:** Data Jobs, Data Flows, Charts, Dashboards, Data Products,
Documents, owners, domains, tags, and glossary entities remain context. They
do not increment the 25-field or 20-downstream-dataset counts.

## Ownership

| Observation | Count |
|---|---:|
| Stored ownership assignments | 27 |
| Corporate-user assignments | 19 |
| Corporate-group assignments | 8 |
| Datasets with one or more assignments | 8 |
| Datasets with zero assignments | 13 |

The 13 ownership gaps are stored as `owners = []` and
`ownership_state = absent`. They are descriptive metadata states, not risk or
governance conclusions.

The datasets with zero owner assignments are:

- dbt `order_history`
- canonical PostgreSQL `orders`
- S3 `orders`
- Snowflake source `ORDERS`
- Snowflake `ORDER_DETAILS_REPLICA`
- Snowflake `ORDER_HISTORY`
- five Power BI measure datasets other than `ORDER_DETAILS`
- two Tableau datasets in the verified field graph

**Verified:** Corporate users and corporate groups remain distinct by URN
type. DataHub-provided ownership type and ownership-type URN values are
preserved when present. No owner is inferred from a domain, platform,
description, or name.

## Domains

| Resolved domain | Scoped dataset assignments |
|---|---:|
| Data Platform Team | 4 |
| Ecommerce Operations | 1 |
| E-Commerce | 1 |

**Verified:** 15 scoped datasets have no stored domain assignment. Absence is
represented by an empty domain collection and `domain_state = absent`.

## Tags

| Stored reference | Scope | Assignments |
|---|---|---:|
| `Authoritative Source` | entity | 1 |
| `PII_Data` | entity | 1 |
| `💲 Large Table` | entity | 3 |
| `📈 Most Queried` | entity | 2 |
| `urn:li:tag:b2fd91.ecommerce` | entity, unresolved | 1 |

**Verified:** No tag is inferred from descriptions or glossary terms.

**Verified:** No field-level tag is stored on `order_total` or the relevant
verified downstream fields in this scope. Field tags on unrelated fields are
not included merely because their parent dataset is scoped.

## Glossary terms

| Resolved term | Scope | Assignments |
|---|---|---:|
| PII | entity | 20 |
| PII | relevant field | 1 |
| Order Total | entity | 6 |
| Order Total | relevant field | 3 |
| Revenue by Customer Class | entity | 4 |
| GDPR | entity | 2 |
| Certified | entity | 1 |
| SOC2 Auditable | entity | 1 |

**Verified:** Entity-level and field-level assignments remain separate.
Relevant field assignments retain the exact `(dataset URN, field path)`
target. Glossary parent-node URNs and names are retained when stored and
resolvable.

## Canonical-field governance

### PostgreSQL `orders.order_total`

- Entity terms on the parent dataset: PII and Order Total.
- Field tags on `order_total`: none observed.
- Field glossary terms on `order_total`: none observed.

### Relevant downstream fields

- dbt `order_details.order_total`: PII and Order Total field terms.
- Snowflake `ANALYTICS.ORDER_DETAILS.order_total`: Order Total field term.
- One additional relevant downstream field stores the Order Total term.

**Verified:** Governance is reported only where DataHub stores the assignment.
Nothing is propagated through lineage by CHRONOS.

## Structured properties

### Definitions

| Property | URN | Value type |
|---|---|---|
| Cost Center | `urn:li:structuredProperty:showcase.costCenter` | `STRING` |
| Data Freshness SLA | `urn:li:structuredProperty:showcase.dataFreshnessSla` | `STRING` |
| Data Quality Score | `urn:li:structuredProperty:showcase.dataQualityScore` | `NUMBER` |
| Data Owner Escalation Contact | `urn:li:structuredProperty:showcase.escalationContact` | `URN` |
| Retention Period | `urn:li:structuredProperty:showcase.retentionPeriod` | `STRING` |

### Assignments

**Verified:** Each of the five definitions has an assigned value on each of
the 21 scoped datasets: 105 assignments total.

Definitions and assigned values are separate immutable types. A definition
does not create a value on an asset; only the observed
`StructuredPropertiesEntry` produces an assignment.

## Data products

| Product | Scoped membership relationships |
|---|---:|
| Order Entry Analytics | 2 |
| Promotions Performance | 1 |
| Returns & Refunds | 1 |

**Verified:** Four stored `DataProductContains` relationships connect scoped
datasets to three products.

**Verified:** Inventory & Fulfilment and Customer Analytics exist in the
showcase but have no membership relationship to the 21-dataset Phase 1.5
scope. They were not attached by name or description.

## Documents

| Observation | Count |
|---|---:|
| Stored `RelatedAsset` relationships in scope | 18 |
| Unique related documents in scope | 9 |

The nine documents are:

- Analytics Layer
- Core Transactional Tables
- Key Metrics Reference
- Operational Runbooks
- Order Details View
- Order History View
- Orders Table
- Runbook: Order Count Discrepancy
- Runbook: Promotion Attribution Issues

**Verified:** Only document URN, title, `RelatedAsset` relationship, related
asset URN, and evidence are retained. Phase 1.5 does not summarize document
contents and does not perform RAG.

## Pipeline context

Two Data Jobs and their Data Flows are verified by Phase 1.4 mapping-group
evidence:

| Job / Flow | Relevant field relationship |
|---|---|
| `export_table_orders_to_s3` | PostgreSQL `orders.order_total` → S3 `orders.order_total` |
| `import_table_orders_to_snowflake` | S3 `orders.order_total` → Snowflake source `ORDERS.order_total` |

The model retains job URN, flow URN, platform, names, mapping-group IDs, and
the related field keys.

**Verified:** These entities are pipeline context and do not change the
field or dataset counts.

## BI reachable context

| Platform | Charts | Dashboard |
|---|---:|---|
| Looker | 4 | `Looker / Order Entry Dashboard` |
| Power BI | 4 | `Power BI / datahub_order_entries` |
| Tableau | 4 | `Tableau / Order Entry Dashboard` |

### Dashboard machine identities

| Platform-qualified identity | DataHub URN |
|---|---|
| Looker / Order Entry Dashboard | `urn:li:dashboard:(looker,b2fd91.dashboards.53)` |
| Power BI / datahub_order_entries | `urn:li:dashboard:(powerbi,b2fd91.reports.66666666-7777-8888-9999-000000000000)` |
| Tableau / Order Entry Dashboard | `urn:li:dashboard:(tableau,b2fd91.843bf583-900b-f1ba-0532-b5e67a0373dc)` |

### Verified relationship paths

- Looker Explore `order_details` → Looker chart → Looker dashboard.
- A scoped Power BI dataset → Power BI chart or dashboard.
- Snowflake `ANALYTICS.ORDER_DETAILS` → Tableau custom-SQL dataset →
  Tableau embedded dataset → Tableau chart → Tableau dashboard.

Every stored path consists of DataHub-supplied URNs discovered through
degree-one downstream lineage reads. Same-name Looker and Tableau dashboards
remain distinct by URN and platform.

**Classification:** All 12 charts and all three dashboards are
`Reachable Context`.

**Verified limitation:** Phase 1.5 does not claim that every chart or
dashboard consumes `order_total`. The Phase 1.4 field graph proves relevant
BI dataset fields; the chart/dashboard relationships available here are
dataset/entity-level lineage. Therefore none of the chart or dashboard
records is labeled `Confirmed Field Impact`, `Broken Dashboard`, or
`Confirmed Impact`.

## High-value asset verification

### dbt / `b2fd91.ORDER_ENTRY_DB.analytics.order_details`

| Metadata | Current observed value |
|---|---|
| Owners | 12 stored assignments |
| Domain | Data Platform Team |
| Entity tags | PII_Data; Authoritative Source |
| Entity glossary terms | 5 |
| Relevant `order_total` field terms | PII; Order Total |
| Structured-property assignments | 5 |
| Data product | Order Entry Analytics |
| Related documents | Analytics Layer; Order Details View |

Current structured-property values are:

- Cost Center: `Data Platform`
- Data Freshness SLA: `Daily`
- Data Quality Score: `86.8`
- Data Owner Escalation Contact:
  `urn:li:corpuser:b2fd91.sam@example.com`
- Retention Period: `90 days`

### Snowflake / ORDER_ENTRY_DB / ANALYTICS / ORDER_DETAILS

| Metadata | Current observed value |
|---|---|
| Owners | 3 stored assignments |
| Domain | Ecommerce Operations |
| Entity tags | `💲 Large Table`; `📈 Most Queried` |
| Entity glossary terms | 4 |
| Relevant `order_total` field term | Order Total |
| Structured-property assignments | 5 |
| Data product | Promotions Performance |
| Related documents | Analytics Layer; Key Metrics Reference; Order Details View |

Current structured-property values are:

- Cost Center: `Marketing`
- Data Freshness SLA: `Daily`
- Data Quality Score: `97.5`
- Data Owner Escalation Contact:
  `urn:li:corpuser:b2fd91.EMP006`
- Retention Period: `1 year`

### Canonical PostgreSQL source

| Metadata | Current observed value |
|---|---|
| Owners | none |
| Domain | none |
| Entity tags | none |
| Entity glossary terms | PII; Order Total |
| `order_total` field tags/terms | none |
| Structured-property assignments | 5 |
| Data products | none |
| Related documents | Orders Table; Runbook: Order Count Discrepancy |
| Pipeline context | export Data Job and Data Flow |

Current structured-property values are:

- Cost Center: `Analytics`
- Data Freshness SLA: `Real-time`
- Data Quality Score: `84.5`
- Data Owner Escalation Contact:
  `urn:li:corpuser:b2fd91.sam@example.com`
- Retention Period: `90 days`

## Unresolved references

One stored scoped reference did not resolve:

| Assignment target | Stored reference | State |
|---|---|---|
| Looker Explore `order_details` | `urn:li:tag:b2fd91.ecommerce` | `unresolved` |

The tag assignment is retained with its raw URN. No replacement tag entity or
name is fabricated.

No unresolved owner or glossary-term reference was encountered inside the
21-dataset scope. Phase 0's other unresolved references remain global
showcase observations outside this bounded enrichment result.

## Evidence sources

| Context | Verified read source |
|---|---|
| Ownership, domains, tags, terms, field governance | SDK `get_entity_semityped` restricted to `ownership`, `domains`, `globalTags`, `glossaryTerms`, and `editableSchemaMetadata` |
| Owner/domain/tag/term display metadata | SDK `DataHubGraph.get_aspect` using the exact reference URN and entity type |
| Structured-property definitions | GraphQL `searchAcrossEntities` restricted to `STRUCTURED_PROPERTY` |
| Structured-property assignments | GraphQL `Dataset.structuredProperties` |
| Data-product membership | GraphQL `Dataset.relationships`, `DataProductContains`, `INCOMING` |
| Documents | SDK `get_related_entities`, `RelatedAsset`, `INCOMING`, followed by typed `documentInfo` |
| Pipelines | Phase 1.4 `dataJobInputOutput` mapping groups plus GraphQL `dataJob` / `dataFlow` |
| BI paths | GraphQL `scrollAcrossLineage`, downstream degree one |
| BI names and platforms | GraphQL `chart` and `dashboard` roots |

Every relationship model retains its interface, aspect or relationship name,
source URN, target URN, relationship path when applicable, and observation
time.

Successful category reads are also retained when they return no assignments,
so states such as `owners = []` carry evidence of the completed `ownership`
aspect read.

## Determinism and cache verification

**Verified:** All collections are normalized by machine identity:

- owners by owner URN and ownership type;
- domains by URN;
- tags by scope, field path, and URN;
- glossary terms by scope, field path, and URN;
- properties, products, and documents by URN;
- pipelines by job URN;
- BI entities by entity type, URN, and relationship path.

**Verified:** Repeated live retrieval over unchanged metadata produced
semantically equal snapshots after excluding observation timestamps.

**Verified:** Request-local caches use URN plus aspect/entity type where
needed. Cache contents are bounded by the 21-dataset scope and the verified
reachable relationship graph. Caching did not change semantic output.

## Tests

### Unit tests

Command:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

Result: **124 passed**.

The Phase 1.5 unit matrix covers multiple and absent owners, user/group
identity, present/absent domains, tags, entity/field terms, unresolved
references, structured definitions versus values, products, documents,
pipeline separation, BI classification and identity, relationship paths,
determinism, cache behavior, evidence, optional absence, secret redaction,
and the read-only boundary.

### Live integration tests

Command:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

Result: **5 passed**.

The five tests cover readiness, canonical resolution, schema retrieval,
field lineage, and governance/business context.

## Deviations and clarifications from Phase 0

1. **Current verified detail:** Phase 0 did not enumerate every structured
   property value. Phase 1.5 now verifies all five assignments on every
   scoped dataset.
2. **Current verified display values:** The two Snowflake tag display names
   currently include emoji: `💲 Large Table` and `📈 Most Queried`. Phase 0
   used text-only labels.
3. **Current scoped integrity finding:** The stored
   `urn:li:tag:b2fd91.ecommerce` reference on the Looker Explore does not
   resolve. It remains unresolved.
4. **Scope clarification:** Phase 0 counted five products and 18 documents
   across the whole showcase. The lineage-derived Phase 1.5 scope reaches
   three products, nine unique documents, and 18 document-to-asset
   relationships. This is a scope difference, not missing enumeration.
5. **No conflicting high-value result:** The current dbt and Snowflake
   governance counts match the Phase 0 findings for owners, domains, tags,
   entity terms, and product membership.

## Read-only and scope guarantee

Phase 1.5 contains no:

- Metadata Change Proposal or Metadata Change Event;
- GraphQL mutation;
- REST write;
- create, update, delete, patch, upsert, emit, or rollback operation;
- impact or severity score;
- automatic impact conclusion;
- chart-column inference;
- Future Graph;
- rename propagation;
- repair recommendation;
- approval decision;
- agent;
- frontend.

Phase 1.5 stops at observed governance and business context. Phase 1.6 has
not begun.
