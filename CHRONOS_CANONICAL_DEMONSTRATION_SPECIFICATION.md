# CHRONOS — Canonical Demonstration Scenario

**Verified:** This document is based on the locally verified official DataHub `showcase-ecommerce` datapack documented in [CHRONOS_SHOWCASE_ECOMMERCE_GRAPH_REPORT.md](./CHRONOS_SHOWCASE_ECOMMERCE_GRAPH_REPORT.md).

**Verified:** No metadata was created, changed, or deleted while preparing this document.

**Inference:** Candidate changes are hypothetical pre-change proposals evaluated against the verified graph; they are not represented as events that have already occurred.

## Classification

- **Verified** — observed in the local showcase graph during the prior verification phase.
- **Inference** — scenario choice, score, predicted consequence, or recommendation derived from verified metadata.
- **Unknown** — information not established by the verified graph.

## 1. Showcase Graph Summary

### 1.1 Inventory

| Graph element | Verified state | Classification |
|---|---|---|
| Datasets | 67 across PostgreSQL, S3, Snowflake, dbt, Looker, Power BI, and Tableau | Verified |
| Schema fields | 917 REST-listed and 916 search-indexed | Verified |
| Pipelines | 23 Spark data flows and 23 data jobs | Verified |
| Dashboards and charts | 3 dashboards and 12 charts; each dashboard contains four charts | Verified |
| Dataset lineage | 55 stored dataset `upstreamLineage` edges | Verified |
| Pipeline lineage | 24 job-input and 23 job-output edges | Verified |
| Fine-grained lineage | 835 dataset mapping groups and 199 job mapping groups | Verified |
| Governance | 98 owner assignments, 6 domains, 6 loaded tags, 10 glossary terms, and 4 glossary nodes | Verified |
| Business context | 5 data products and 18 published documents with 56 related-asset references | Verified |
| Structured properties | 5 definitions: cost center, freshness SLA, quality score, escalation contact, and retention period | Verified |
| Assertions and contracts | 0 assertion entities and 0 data-contract entities | Verified |
| ML entities | 0 across the registered ML entity family | Verified |

### 1.2 Primary business workflow

**Verified:** Twelve PostgreSQL source datasets feed twelve Spark export jobs, which write twelve S3 datasets.

**Verified:** Eleven Spark import jobs load eleven Snowflake source tables; the promotions import uniquely consumes both S3 `promotions` and S3 `product_information`.

**Verified:** Eleven Snowflake source tables feed eleven dbt sources, and all eleven dbt sources feed the dbt `order_details` model.

**Verified:** Snowflake `ANALYTICS.ORDER_DETAILS` has the dbt model and all eleven Snowflake source tables as immediate upstreams.

**Verified:** Snowflake `ANALYTICS.ORDER_DETAILS` fans out to order history, a replica, and the Looker, Power BI, and Tableau semantic layers that support all three dashboards.

**Inference:** The graph represents a realistic ecommerce metadata supply chain: operational capture, file transfer, warehouse loading, transformation, analytical distribution, and business consumption.

### 1.3 Core datasets and critical chains

| Asset | Verified importance | Classification |
|---|---|---|
| PostgreSQL `orders` | Pipeline root with 41 heterogeneous descendants; `order_total` alone reaches 25 fields in 20 datasets | Verified |
| PostgreSQL `customers` | Pipeline root for customer identity; `cust_email` reaches 14 fields in 14 datasets | Verified |
| PostgreSQL `inventories` | Pipeline root whose `quantity_on_hand` reaches 25 fields in 14 datasets and produces `stock_status` | Verified |
| PostgreSQL `order_items` | Pipeline root whose `return_date` reaches 25 fields and produces `return_status` | Verified |
| dbt `order_details` | Joins 11 dbt sources; 55 fields; 54 fine-grained mapping groups; richest governance metadata | Verified |
| Snowflake `ANALYTICS.ORDER_DETAILS` | 12 immediate inputs, 14 immediate outputs, 34 heterogeneous descendants, all 3 dashboards, all 12 charts | Verified |

**Verified:** Root-to-dashboard paths reach 10 or 11 relationship edges through PostgreSQL, Spark, S3, Snowflake, dbt, BI semantic datasets, charts, and dashboards.

**Verified:** Fine-grained lineage includes non-trivial derivations: `order_total` to revenue and average-order-value fields, `quantity_on_hand` to `stock_status`, `return_date` to `return_status`, `customer_id` to Customer LTV, and `order_date` to Revenue by Month.

### 1.4 Governance metadata

**Verified:** dbt `order_details` has 12 ownership assignments, tags `PII_Data` and `Authoritative Source`, domain Data Platform Team, five entity glossary terms, 24 field-term assignments, one field tag, structured properties, and a 13,912-character description.

**Verified:** Snowflake `ANALYTICS.ORDER_DETAILS` has three owners, tags `Large Table` and `Most Queried`, domain Ecommerce Operations, four glossary terms, and membership in Promotions Performance.

**Verified:** Snowflake source datasets including `ORDERS`, `CUSTOMERS`, `ORDER_ITEMS`, `PRODUCTS`, `INVENTORIES`, `PROMOTIONS`, and `ADDRESSES` have no owners and no domains.

**Verified:** The glossary contains Classification terms PII and GDPR; Order Metrics terms Order Total and Revenue by Customer Class; Certified; SOC2 Auditable; and four standalone personal-data terms.

**Verified:** Five data products group eleven asset references: Inventory & Fulfilment, Promotions Performance, Returns & Refunds, Customer Analytics, and Order Entry Analytics.

**Verified:** Five data products reference an unresolved `__default_gold` tag; some owner and glossary references are also unresolved or inconsistently namespaced.

**Unknown:** The exact assigned value of every structured property on every asset was not enumerated in the prior frozen graph report.

### 1.5 Dashboards and charts

| Dashboard | Verified charts | Verified context | Classification |
|---|---|---|---|
| Looker Order Entry Dashboard | Popular Products, Orders by Day, Promotions, Order Mode | One Explore source; no dashboard owner; Ecommerce Operations domain | Verified |
| Power BI `datahub_order_entries` | Executive Summary, Customer Analysis, Geographics, DAX Visual | Six current source datasets; four owners; two unresolved direct dataset references | Verified |
| Tableau Order Entry Dashboard | Orders By Month, Popular Products Categories, Promotions, Order Mode | Four embedded sources over four custom-SQL datasets; David Kim; Marketing domain | Verified |

**Inference:** Power BI is the strongest executive-facing endpoint, Tableau provides the strongest marketing narrative, and Looker provides a clear semantic-model chain.

### 1.6 Why this graph is suitable

**Inference:** The graph is suitable because a single verified field can be traced across physical systems, jobs, transformation models, analytical tables, semantic datasets, charts, dashboards, data products, owners, tags, terms, domains, and documents.

**Inference:** It supports explanations that simple document retrieval cannot produce: exact multi-hop dependency paths, column derivations, blast-radius counts, accountability gaps, and business-consumer impact.

**Inference:** Its ecommerce language—orders, revenue, customers, inventory, promotions, and dashboards—is immediately understandable to both technical and non-technical judges.

## 2. Candidate Metadata Changes

**Inference:** Every candidate below is a hypothetical change to an asset, field, relationship, or governance assignment that is verified to exist in the showcase.

| ID | Candidate change | Verified baseline | Classification |
|---|---|---|---|
| C01 | Rename PostgreSQL `orders.order_total` to a proposed new name | `order_total` is Number and has 25 downstream fields across 20 datasets, depth 5 | Verified baseline; Inference change |
| C02 | Change PostgreSQL `inventories.quantity_on_hand` from Number to an incompatible type | The field has 25 downstream fields in 14 datasets, depth 7, including derived `stock_status` | Verified baseline; Inference change |
| C03 | Delete or mask PostgreSQL `customers.cust_email` | The field has 14 downstream fields in 14 datasets and PII governance context | Verified baseline; Inference change |
| C04 | Delete PostgreSQL `order_items.return_date` | The field reaches 25 downstream fields and produces derived `return_status` | Verified baseline; Inference change |
| C05 | Delete Snowflake `ANALYTICS.ORDER_DETAILS` | The dataset has 14 immediate outputs, 34 heterogeneous descendants, 3 dashboards, and 12 charts | Verified baseline; Inference change |
| C06 | Rename the dbt `order_details` model | The model joins 11 dbt sources, has 35 heterogeneous descendants, and carries the richest governance metadata | Verified baseline; Inference change |
| C07 | Remove Spark job/flow `import_table_orders_to_snowflake` | The verified order pipeline is PostgreSQL `orders` → export → S3 `orders` → import → Snowflake `ORDERS` | Verified baseline; Inference change |
| C08 | Remove the stored lineage relationship from dbt `order_details` to Snowflake `ANALYTICS.ORDER_DETAILS` | The relationship is a verified bridge between the governed model and the analytical distribution hub | Verified baseline; Inference change |
| C09 | Remove David Kim from Snowflake `ANALYTICS.ORDER_DETAILS` ownership | David Kim is one of the dataset's three verified owners | Verified baseline; Inference change |
| C10 | Remove `PII_Data` from dbt `order_details` | `PII_Data` is one of the model's two verified entity tags | Verified baseline; Inference change |
| C11 | Remove the Order Total glossary term from Snowflake `ANALYTICS.ORDER_DETAILS` | Order Total is one of the dataset's four verified entity terms | Verified baseline; Inference change |
| C12 | Move Snowflake `ANALYTICS.ORDER_DETAILS` from Ecommerce Operations to Data Platform Team | The current and proposed domains both exist; the current assignment is Ecommerce Operations | Verified baseline; Inference change |
| C13 | Remove Snowflake `ANALYTICS.ORDER_DETAILS` from Promotions Performance | The dataset is a verified asset of that data product | Verified baseline; Inference change |
| C14 | Remove the 13,912-character description from dbt `order_details` | The description is verified and is the richest dataset documentation in the graph | Verified baseline; Inference change |
| C15 | Remove the Power BI dashboard-to-chart relationship for Executive Summary | The chart is one of four verified children of `datahub_order_entries` | Verified baseline; Inference change |
| C16 | Delete the Looker Explore `Order Details` | The Explore has 63 fields, three owners, a domain, a tag, a glossary term, and feeds four Looker charts | Verified baseline; Inference change |

**Verified:** Primary-key modification is excluded because no inspected field is marked `isPartOfKey=true`.

**Verified:** Existing assertion-failure and ML-impact candidates are excluded because the graph contains no assertion, data-contract, or ML entity instances.

**Inference:** Column split/merge and creation of a new synthetic asset are excluded because they would require metadata not present in the official datapack.

## 3. Evaluation Matrix

### 3.1 Scoring rules

**Inference:** All scores are comparative judgments for this showcase, not stored DataHub ratings.

**Inference:** A score of 1 is low and 10 is high for every category; high Engineering Difficulty, Implementation Effort, and Risk mean more difficulty, effort, and risk rather than higher desirability.

| Code | Category | Interpretation | Classification |
|---|---|---|---|
| BR | Business realism | Plausibility and recognizable production relevance | Inference |
| FP | Frequency in production | Expected frequency of the change class | Inference |
| ED | Engineering difficulty | Technical depth required to handle it correctly | Inference |
| MC | Metadata complexity | Number and richness of metadata dimensions involved | Inference |
| LI | Lineage impact | Breadth/depth of graph consequences | Inference |
| CI | Column-level impact | Importance of fine-grained lineage | Inference |
| GI | Governance impact | Owners, terms, tags, domains, products, or documentation | Inference |
| DI | Dashboard impact | Strength of business-consumer consequence | Inference |
| VQ | Visualization quality | Potential for a compelling visual narrative | Inference |
| EX | Ease of explaining | Five-minute clarity | Inference |
| HO | Hackathon originality | Differentiation from generic catalog/RAG demos | Inference |
| IE | Implementation effort | Relative work likely required later | Inference |
| RK | Risk | Likelihood of ambiguity, instability, or demo failure | Inference |

### 3.2 Scores

| ID | BR | FP | ED | MC | LI | CI | GI | DI | VQ | EX | HO | IE | RK | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| C01 | 9 | 8 | 8 | 10 | 10 | 10 | 7 | 10 | 10 | 9 | 9 | 7 | 4 | Inference |
| C02 | 8 | 7 | 9 | 9 | 9 | 10 | 6 | 8 | 9 | 8 | 9 | 8 | 6 | Inference |
| C03 | 9 | 8 | 7 | 9 | 8 | 8 | 10 | 7 | 9 | 10 | 9 | 7 | 5 | Inference |
| C04 | 8 | 6 | 7 | 8 | 8 | 9 | 5 | 6 | 8 | 8 | 8 | 6 | 4 | Inference |
| C05 | 8 | 5 | 6 | 9 | 10 | 6 | 9 | 10 | 10 | 10 | 6 | 5 | 4 | Inference |
| C06 | 9 | 7 | 8 | 10 | 10 | 9 | 10 | 10 | 10 | 9 | 8 | 8 | 5 | Inference |
| C07 | 8 | 5 | 7 | 8 | 10 | 8 | 6 | 10 | 9 | 9 | 8 | 6 | 4 | Inference |
| C08 | 7 | 7 | 5 | 8 | 10 | 8 | 5 | 10 | 10 | 8 | 9 | 5 | 3 | Inference |
| C09 | 8 | 8 | 3 | 5 | 2 | 1 | 10 | 7 | 7 | 10 | 6 | 2 | 2 | Inference |
| C10 | 8 | 7 | 3 | 6 | 3 | 5 | 10 | 8 | 8 | 10 | 8 | 3 | 2 | Inference |
| C11 | 8 | 6 | 4 | 7 | 4 | 6 | 10 | 8 | 8 | 9 | 8 | 3 | 2 | Inference |
| C12 | 7 | 5 | 3 | 5 | 2 | 1 | 9 | 8 | 7 | 9 | 6 | 2 | 2 | Inference |
| C13 | 7 | 5 | 4 | 6 | 4 | 1 | 9 | 8 | 8 | 9 | 8 | 3 | 2 | Inference |
| C14 | 8 | 7 | 3 | 4 | 1 | 1 | 8 | 6 | 6 | 10 | 5 | 2 | 2 | Inference |
| C15 | 7 | 5 | 5 | 7 | 8 | 4 | 5 | 10 | 9 | 10 | 8 | 4 | 3 | Inference |
| C16 | 8 | 6 | 7 | 8 | 9 | 9 | 8 | 8 | 9 | 9 | 7 | 6 | 4 | Inference |

### 3.3 Score reasoning

- **C01 — Inference:** It combines a familiar production refactor with the graph's best verified field fan-out, derived financial measures, three BI platforms, and a compact “one field, many consequences” story.
- **C02 — Inference:** It is more transformation-aware than a rename because type compatibility affects both direct numeric fields and derived stock status, but the inventory narrative is narrower and harder to explain quickly.
- **C03 — Inference:** It provides the strongest privacy/governance narrative and a clear PII field, but masking semantics are not represented in the current metadata and must remain a proposal.
- **C04 — Inference:** It demonstrates direct and derived column impact, but return-date consequences have less executive visibility than revenue.
- **C05 — Inference:** It has the largest and clearest table-level blast radius, but “delete a hub, everything breaks” is less original and uses less fine-grained reasoning.
- **C06 — Inference:** It spans lineage, identity, governance, and all consumers, but a model rename affects nearly everything and may be too broad for a five-minute explanation.
- **C07 — Inference:** It makes pipeline lineage visible and produces a clear operational outage path, but it demonstrates less semantic governance than C01.
- **C08 — Inference:** It strongly differentiates graph correctness from data correctness, but missing metadata lineage is more abstract for non-technical judges.
- **C09 — Inference:** Accountability loss is realistic and easy to understand, but its graph and column-level content are weak.
- **C10 — Inference:** Removing a PII tag demonstrates governance-aware discovery and propagation gaps, but tags do not themselves alter lineage.
- **C11 — Inference:** Removing the business term weakens metric meaning across a central hub, but the actual data and dependency graph remain intact.
- **C12 — Inference:** Domain reassignment is understandable organizationally, but it produces primarily catalog/governance impact rather than deep graph reasoning.
- **C13 — Inference:** Product membership connects technical assets to a business product, but the change is a single governance relationship.
- **C14 — Inference:** Documentation loss is common and easy to explain, but it resembles content completeness analysis more than graph reasoning.
- **C15 — Inference:** A missing dashboard-chart relationship is visually immediate and graph-native, but it affects one presentation edge rather than the full supply chain.
- **C16 — Inference:** Deleting the Looker Explore combines semantic-model, field, ownership, and dashboard impact, but it affects only one of three BI ecosystems.

## 4. Propagation Analysis

**Inference:** “Propagation” below means the consequences discoverable from current metadata if the hypothetical change were proposed; it does not claim that DataHub automatically edits downstream systems.

| ID | Predicted propagation | Downstream consequence | Classification |
|---|---|---|---|
| C01 | PostgreSQL field → export job mapping → S3 field → import job mapping → Snowflake `ORDERS` → dbt source/model → Snowflake `ORDER_DETAILS` → Looker, Power BI, Tableau, and order history | 25 descendant fields in 20 datasets may require rename/remapping; derived revenue and average-order-value fields may become invalid or semantically stale; all three dashboards are in the affected graph | Inference from Verified lineage |
| C02 | Inventory field follows both Spark jobs, Snowflake/dbt layers, and analytical/BI datasets; some descendants are direct numeric fields and others are derived `stock_status` | Type incompatibility may break arithmetic/comparisons and stock classification; Inventory & Fulfilment context and inventory-related BI consumers become review targets | Inference from Verified lineage |
| C03 | Customer email follows the customer pipeline into dbt/Snowflake analytical datasets and Power BI/Looker customer layers | Delete removes dependent fields; masking may preserve schema while changing semantics; PII terms/tags and Customer Analytics context must be inspected; exact masking compatibility is unknown | Inference; masking behavior Unknown |
| C04 | Return date follows the order-items pipeline and produces direct date descendants plus derived `return_status` | Return/refund analytics may lose status derivation; Returns & Refunds assets and BI consumers become review targets | Inference from Verified lineage |
| C05 | The central Snowflake hub disappears between 12 inputs and 14 direct dataset consumers | Replica, order history, all BI semantic datasets, 12 charts, 3 dashboards, and product-linked assets lose their central upstream; upstream jobs and sources still exist but no longer reach consumers through this hub | Inference from Verified lineage |
| C06 | The dbt model identity changes between 11 dbt sources and Snowflake `ORDER_DETAILS` | All model fields, fine-grained mappings, owners, tags, terms, domain, structured properties, documentation, and downstream relationships require identity continuity review | Inference |
| C07 | S3 `orders` loses its verified import job/output path to Snowflake `ORDERS` | The order branch no longer reaches dbt/order analytics through the verified pipeline; revenue, order history, three dashboards, and associated products become downstream review targets | Inference from Verified lineage |
| C08 | Data remains present, but the stored bridge from dbt `order_details` to Snowflake `ORDER_DETAILS` is removed | Graph traversals from the governed model stop before the BI distribution hub, under-reporting downstream impact even if physical processing continues | Inference |
| C09 | Only the ownership aspect on Snowflake `ORDER_DETAILS` changes | Schema and lineage remain unchanged; the hub has reduced accountability while three dashboards and product context remain attached | Inference |
| C10 | Only the model's entity-level tag association changes | Lineage remains intact, but tag-based PII discovery, filtering, and governance explanation weaken; existing terms and one field tag may still provide partial classification | Inference |
| C11 | Only the Order Total term association on Snowflake `ORDER_DETAILS` changes | Data and lineage remain intact, but the central analytical table loses explicit business-metric semantics while downstream revenue fields remain | Inference |
| C12 | The domain relationship moves from Ecommerce Operations to Data Platform Team | Lineage and schema remain intact; organizational browsing, stewardship context, and business ownership interpretation change for a hub reaching three dashboards | Inference |
| C13 | The data-product asset relationship is removed | Promotions Performance loses one of its two verified assets; lineage and the dataset itself remain, but product-level completeness and impact views change | Inference |
| C14 | Dataset description content is removed from dbt `order_details` | All graph edges and governance assignments remain; human and agent explanations lose the graph's richest dataset narrative and institutional context | Inference |
| C15 | The containment relationship between Power BI dashboard and Executive Summary is removed | The chart and its six input datasets still exist, and direct dashboard dataset references may remain; the dashboard loses one visible child and the chart-to-dashboard presentation path | Inference |
| C16 | The Looker Explore between the Looker view and four charts is deleted | Four Looker chart paths are disconnected from their semantic source; the Looker dashboard loses meaningful upstream reach through those charts, while Power BI and Tableau remain unaffected | Inference |

### Cross-cutting entity consequences

| Entity family | Verified baseline | Predicted relevance across candidates | Classification |
|---|---|---|---|
| Datasets/columns | 67 datasets and more than 900 fields with rich fine-grained lineage | Primary propagation surface for C01–C08 and C16 | Verified baseline; Inference relevance |
| Jobs/flows | 23 job/flow pairs with job input/output and 199 mapping groups | Essential for C01–C04 and C07; upstream context for C05–C06 | Verified baseline; Inference relevance |
| Dashboards/charts | Three dashboards and 12 charts | Business endpoints for C01–C08, C15, and C16 | Verified baseline; Inference relevance |
| Owners | 98 assignments plus verified missing/unresolved owners | Accountability overlay for all high-impact candidates; direct change surface for C09 | Verified baseline; Inference relevance |
| Tags/terms/domains | Loaded governance relationships on core assets | Direct surfaces for C10–C12 and contextual evidence for C01–C08 | Verified baseline; Inference relevance |
| Structured properties | Five definitions and assignments on governance-rich assets | Context to inspect on C06 and the selected hub/model; exact per-asset values require verification | Verified baseline; Unknown exact values |
| Data products | Five products and 11 asset references | Business grouping for C01–C07 and direct surface for C13 | Verified baseline; Inference relevance |

## 5. Information Requirements

**Inference:** The table identifies required information and metadata operations only; it does not define an algorithm, service, or implementation.

| ID | Required metadata and schema | Required lineage/traversal | Required governance inspection | Required comparison | Potential metadata write, only if the hypothetical change is persisted | Classification |
|---|---|---|---|---|---|---|
| C01 | Source field identity/type plus descendant field schemas | Downstream field traversal through job and dataset fine-grained mappings, then BI/chart/dashboard relations | Order Total terms, owners, tags, domains, products, documents | Existing field path/type/name versus proposed name; direct versus derived descendants | No write for preview; a persisted source change would update schema metadata and later lineage mappings | Inference |
| C02 | `quantity_on_hand` type and every descendant type/expression label | Downstream fine-grained traversal to `stock_status` and BI layers | Inventory product, owners, terms, domain, runbook context | Number versus proposed incompatible type; direct numeric versus derived semantic fields | No preview write; persisted state would require schema metadata update | Inference |
| C03 | Email field schema and descendant fields | Customer-field traversal through both jobs, dbt, Snowflake, and BI | PII terms/tags, Customer Analytics, owners, policies if present | Existing field versus delete or masking proposal | No preview write; deletion would alter schema metadata; masking representation is Unknown | Inference; Unknown masking representation |
| C04 | Return-date schema and derived return-status fields | Order-item downstream field traversal | Returns & Refunds product, owners, documents | Existing date field versus deletion; direct versus derived fields | No preview write; persisted state would update schema metadata/lineage | Inference |
| C05 | Dataset identity, schema, status, all immediate consumers | Full downstream heterogeneous traversal and upstream context | Owners, domain, tags, terms, product memberships, documents | Existing entity versus proposed deletion/deprecation | No preview write; persisted removal would require an official entity deletion/deprecation operation | Inference |
| C06 | Model URN/name, schema, properties, all aspects | Eleven-input upstream and full downstream traversal; all fine-grained mappings | All owners, tags, terms, domain, structured properties, links, products | Existing identity versus proposed identity and aspect continuity | Exact official rename semantics must be verified; likely identity/deprecation/relationship changes | Inference; write semantics Unknown |
| C07 | Flow/job properties, inputs, outputs, and mappings | Both upstream S3 path and all downstream Snowflake/dbt/BI paths | Flow/job owners, affected dataset/product owners, documents | Existing job/flow and edges versus removal | No preview write; persisted state would delete/deprecate job/flow and remove lineage | Inference |
| C08 | Stored `upstreamLineage` and fine-grained mappings on Snowflake hub | Compare paths with and without the bridge | Governance on both endpoints to show lost contextual reach | Existing edge set versus missing edge set | No preview write; persisted change would modify lineage metadata | Inference |
| C09 | Ownership aspect and owner identities/types | Dataset downstream reach only for prioritization | Remaining owners and unresolved-owner context | Current three-owner set versus proposed two-owner set | Ownership aspect update | Inference |
| C10 | Tag association at entity and field levels | Downstream reach only for exposure context | PII tag, PII terms, other classifications | Current tags versus proposed tags | Tag-association update | Inference |
| C11 | Glossary association and term definition | Downstream field/dataset reach for semantic exposure | Order Total and Revenue by Customer Class terms | Current terms versus proposed terms | Glossary-term association update | Inference |
| C12 | Current domain and domain hierarchy | Downstream reach for business exposure context | Both domains, owners, products, dashboard domains | Ecommerce Operations versus Data Platform Team | Domain association update | Inference |
| C13 | Data-product properties and asset list | Asset lineage only for product impact context | Product owners/domain/tag plus dataset governance | Current two-asset set versus one-asset set | Data-product asset membership update | Inference |
| C14 | Dataset description and related document links | No lineage required for direct change; downstream reach provides importance context | Owners, terms, domain, links, documents | Existing content versus empty content | Dataset-properties description update | Inference |
| C15 | Dashboard info, chart identity, chart inputs, direct dataset refs | Chart-to-dashboard and upstream chart-input paths | Dashboard/chart owners and domain | Four-child versus three-child dashboard | Dashboard chart-membership relationship update | Inference |
| C16 | Explore entity, 63-field schema, properties, chart consumers | View → Explore → four charts → dashboard, plus Snowflake upstream | Explore owners, domain, tag, term, container | Existing Explore and relationships versus deletion | Entity deletion/deprecation plus relationship updates | Inference |

**Unknown:** The official datapack does not contain a proposed-change entity, prevention record, or universal change-request aspect to store these hypothetical inputs.

**Inference:** The canonical demo therefore requires no DataHub write to establish its starting state; the proposed change can remain an external demonstration input.

## 6. Judge Evaluation

### 6.1 Legend

| Mark | Meaning | Classification |
|---|---|---|
| Y | Strong yes | Inference |
| P | Partial or presentation-dependent | Inference |
| N | No | Inference |

### 6.2 Six-question evaluation

| ID | Immediate DataHub value? | Visually compelling? | Clear graph reasoning? | Beyond simple RAG? | Fits five minutes? | Non-technical clarity? | Judge rationale | Classification |
|---|---|---|---|---|---|---|---|---|
| C01 | Y | Y | Y | Y | Y | Y | One money field becomes many technical and business metrics across the full stack | Inference |
| C02 | Y | Y | Y | Y | P | Y | Type change plus derived stock status is deep, but requires more technical explanation | Inference |
| C03 | Y | Y | Y | Y | Y | Y | Privacy impact is universal and graph-grounded; masking representation needs care | Inference |
| C04 | Y | Y | Y | Y | Y | Y | Derived return status is clear, but executive impact is narrower | Inference |
| C05 | Y | Y | Y | P | Y | Y | Massive blast radius is memorable but resembles a standard lineage demo | Inference |
| C06 | Y | Y | Y | Y | P | Y | Excellent metadata breadth, but model identity migration can overwhelm five minutes | Inference |
| C07 | Y | Y | Y | Y | Y | Y | Shows operational and analytical graph continuity with a clear missing-load story | Inference |
| C08 | Y | Y | Y | Y | Y | P | Demonstrates metadata integrity, but “data works while lineage lies” is more abstract | Inference |
| C09 | P | P | N | P | Y | Y | Accountability matters, but one owner edge does not showcase graph depth | Inference |
| C10 | Y | P | P | Y | Y | Y | Strong governance story with limited structural propagation | Inference |
| C11 | Y | P | P | Y | Y | Y | Business-semantic loss is useful but less visually dramatic | Inference |
| C12 | P | P | N | P | Y | Y | Organizational reclassification is understandable but graph-light | Inference |
| C13 | Y | P | P | Y | Y | Y | Connects assets to products but changes one membership edge | Inference |
| C14 | P | P | N | P | Y | Y | Easy to explain, but closest to document completeness/RAG | Inference |
| C15 | Y | Y | Y | P | Y | Y | Visible broken dashboard composition, but limited multi-platform depth | Inference |
| C16 | Y | Y | Y | Y | Y | Y | Strong semantic-layer outage, but only the Looker branch is affected | Inference |

### 6.3 Judge conclusion

**Inference:** C01 most clearly proves that DataHub contributes structured graph evidence rather than retrieved prose: it requires schema identity, fine-grained lineage, derived-field interpretation, heterogeneous traversal, governance overlays, and business-consumer explanation.

**Inference:** C05 would be the easiest theatrical demo, but it is less differentiated because table-level blast-radius visualization is already a familiar catalog capability.

**Inference:** C03 is the best governance alternative and C02 is the best transformation-type alternative, but both introduce more semantic ambiguity than C01.

## 7. Selected Demonstration

### Selected: C01 — Rename PostgreSQL `orders.order_total`

**Inference:** This is the one and only canonical CHRONOS demonstration scenario.

### Why it is the strongest choice

**Verified:** The source field has 25 downstream field descendants across 20 datasets and a maximum field depth of 5.

**Verified:** Its descendants include Tableau `TOTAL_REVENUE` and `AVERAGE_ORDER_VALUE`, Power BI `ORDER_TOTAL` fields, Looker `order_total`, and order-history fields.

**Verified:** Its dataset path crosses PostgreSQL, two Spark jobs, S3, Snowflake, dbt, Snowflake analytics, three BI platforms, charts, and dashboards.

**Inference:** The scenario is stronger than a table deletion because it must distinguish direct renames from derived business measures instead of marking every downstream node equally.

### Why it is technically interesting

**Inference:** Correct explanation requires both dataset-level and fine-grained field lineage, cross-platform identity resolution, derived-field awareness, and transitions between jobs, datasets, charts, and dashboards.

**Inference:** It exposes a realistic engineering challenge: a harmless-looking source refactor can leave derived metrics semantically correct, technically broken, or silently stale depending on downstream mapping.

### Why it showcases DataHub and metadata graphs

**Verified:** DataHub stores the exact multi-hop table/job/field relationships and governance context needed to explain the impact.

**Inference:** The graph can show not merely related documents but why each downstream field is connected, at what depth, through which systems, and which business consumers sit at the end.

### Why it demonstrates business value

**Inference:** Order total, total revenue, and average order value are understandable commercial metrics, so the scenario translates technical lineage into potential reporting and decision risk.

**Inference:** Owners, glossary terms, data products, dashboards, and documents provide the information needed to route and explain a review before the change.

### Why it is feasible and memorable

**Verified:** All baseline assets, mappings, dashboards, terms, owners, and product relationships already exist in the official graph.

**Inference:** No synthetic dataset, assertion, contract, or ML entity is required.

**Inference:** “Rename one column; reveal 25 fields, 20 datasets, three BI ecosystems, and derived revenue metrics” is concise enough to remember and explain within five minutes.

## 8. Frozen Demonstration Specification

### 8.1 Canonical name

**Inference:** **The Revenue Column Rename Impact Review** is the frozen demonstration name.

### 8.2 Starting metadata state

| Baseline element | Frozen state | Classification |
|---|---|---|
| Source | PostgreSQL dataset `orders`, field `order_total` | Verified |
| Source type | Number | Verified |
| Pipeline | PostgreSQL `orders` → Spark export → S3 `orders` → Spark import → Snowflake `ORDERS` | Verified |
| Transformation | Snowflake/dbt order sources → dbt `order_details` → Snowflake `ANALYTICS.ORDER_DETAILS` | Verified |
| Field impact | 25 downstream fields, 20 downstream datasets, maximum depth 5 | Verified |
| Derived examples | Tableau total revenue and average order value; Power BI order-total context; Looker order total; order history | Verified |
| Business endpoints | Looker, Power BI, and Tableau dashboard branches | Verified |
| Governance context | Order Total and Revenue by Customer Class terms on core order assets; governed dbt model and Snowflake hub | Verified |
| Accountability context | Upstream source layers include missing ownership; downstream model/hub and some BI assets have owners | Verified |
| Product context | Downstream affected order assets participate in Returns & Refunds, Promotions Performance, and Order Entry Analytics | Verified |

### 8.3 Trigger event

**Inference:** The fixed trigger is a proposed pre-deployment rename of PostgreSQL `orders.order_total` to `order_amount`.

**Inference:** The trigger is an analysis input only; it does not modify the official showcase graph.

**Inference:** The scenario is specifically a rename, not a deletion, type change, masking request, or table rename.

### 8.4 Affected assets

**Verified:** The affected field graph contains 25 downstream fields across 20 datasets.

**Inference:** The demonstration must group affected assets into these layers:

1. **Inference:** PostgreSQL source field.
2. **Inference:** Spark export job and S3 intermediate field.
3. **Inference:** Spark import job and Snowflake `ORDERS`.
4. **Inference:** dbt source and dbt `order_details`.
5. **Inference:** Snowflake `ANALYTICS.ORDER_DETAILS`, replica, and order history where field lineage applies.
6. **Inference:** Looker, Power BI, and Tableau semantic datasets and derived measures.
7. **Inference:** Reachable charts, dashboards, data products, owners, glossary terms, and documents as business context.

**Unknown:** Exact field-level consumption by every chart is not proven merely by a chart's dataset input reference.

**Inference:** The demonstration must label chart-level impact as confirmed only when a verified field path exists; otherwise it must label the chart/dashboard as reachable context rather than confirmed field use.

### 8.5 Expected downstream impact

| Impact class | Expected result | Classification |
|---|---|---|
| Direct field mappings | Same-semantic descendants named `order_total` require rename/remapping review | Inference |
| Derived metrics | `TOTAL_REVENUE` and `AVERAGE_ORDER_VALUE` require expression/dependency review rather than blind rename | Inference |
| Pipeline mappings | Both Spark job mapping layers must be included | Inference from Verified mappings |
| Analytical models | dbt and Snowflake analytical fields must be included | Inference from Verified lineage |
| BI consumers | All three BI branches must appear in the reachable impact view | Inference from Verified reach |
| Governance | Order Total/Revenue terms, owners, domains, products, and documentation must accompany the technical impact | Inference |
| Decision | The change is held for review until downstream compatibility is confirmed | Inference |

### 8.6 Expected visualizations

**Inference:** The frozen demonstration requires these conceptual visual outputs; their implementation is not decided:

1. **Inference:** A before/after change card showing `order_total` → `order_amount`.
2. **Inference:** A layered field-lineage path from PostgreSQL through Spark, S3, Snowflake, dbt, and BI.
3. **Inference:** A blast-radius summary showing 25 downstream fields, 20 datasets, three BI ecosystems, and the verified maximum field depth.
4. **Inference:** A direct-versus-derived split, with revenue and average-order-value examples highlighted.
5. **Inference:** A business-consumer view for reachable dashboards, charts, and data products, with confirmed impact distinguished from reachability.
6. **Inference:** A governance/accountability panel containing owners, missing-owner gaps, terms, tags, domains, and relevant documents.
7. **Inference:** A final review outcome explaining why the rename should not proceed without downstream confirmation.

**Inference:** No visualization architecture, frontend technology, layout system, or component design is selected here.

### 8.7 Expected user journey

1. **Inference:** The presenter selects the verified PostgreSQL `orders.order_total` field.
2. **Inference:** The presenter submits the fixed proposed rename to `order_amount`.
3. **Inference:** The demonstration resolves the current field, type, governance, and lineage baseline.
4. **Inference:** The demonstration expands downstream fine-grained paths and groups them by system and semantic role.
5. **Inference:** The demonstration separates direct mappings from derived revenue measures.
6. **Inference:** The demonstration shows affected datasets, jobs, BI branches, dashboards, data products, owners, terms, and documentation.
7. **Inference:** The demonstration ends with a concise review outcome and the evidence paths supporting it.

### 8.8 Expected inputs

| Input | Frozen value | Classification |
|---|---|---|
| Change class | Column rename | Inference |
| Source platform | PostgreSQL | Verified |
| Source dataset | `orders` | Verified |
| Source field | `order_total` | Verified |
| Current type | Number | Verified |
| Proposed field name | `order_amount` | Inference |
| Direction | Downstream impact | Inference |
| Scope | Jobs, datasets, fields, BI consumers, products, and governance context | Inference |

### 8.9 Expected outputs

| Output | Frozen expectation | Classification |
|---|---|---|
| Change summary | Old name, proposed name, source asset, current type | Inference |
| Impact counts | 25 downstream fields and 20 datasets; other entity counts shown only when verified by traversal | Verified baseline; Inference presentation |
| Paths | Evidence-backed paths through physical, pipeline, transformation, analytics, and BI layers | Inference |
| Semantic classification | Direct copies separated from derived metrics | Inference |
| Business context | Reachable dashboards/charts, three relevant product contexts, glossary terms, owners, domains, and documents | Inference from Verified graph |
| Uncertainty | Explicit unknowns such as unverified chart-field binding | Inference |
| Review outcome | Hold for downstream compatibility review | Inference |

### 8.10 Success criteria

1. **Inference:** The demonstration starts from the exact verified field and never substitutes a synthetic dataset or lineage edge.
2. **Inference:** It identifies all 25 verified descendant fields across all 20 verified downstream datasets.
3. **Inference:** It includes both Spark job mapping layers and the dbt/Snowflake analytical layers.
4. **Inference:** It distinguishes direct mappings from derived revenue and average-order-value fields.
5. **Inference:** It reaches the Looker, Power BI, and Tableau branches without claiming unsupported chart-column certainty.
6. **Inference:** It attaches verified governance, ownership, data-product, and document context.
7. **Inference:** Every displayed fact is labeled as verified, inferred, or unknown.
8. **Inference:** A non-technical viewer can state the business risk after one viewing.
9. **Inference:** The core story can be completed within five minutes.
10. **Inference:** The official showcase graph remains unchanged.

### 8.11 Permanently excluded variants

**Inference:** The canonical demo will not switch to table deletion, inventory type change, email masking, missing assertion, ML impact, primary-key change, or another source field without reopening this frozen specification.

## 9. Open Questions

1. **Unknown:** Which exact field descendants have explicit expressions or transformation text, rather than only fine-grained input/output sets?
2. **Unknown:** Which individual charts use `order_total` or a derived descendant at column level, as opposed to merely reading the containing dataset?
3. **Unknown:** Which structured-property values are assigned to every affected asset?
4. **Unknown:** Which of the unresolved owner, tag, glossary, and Power BI references are intentional showcase defects?
5. **Unknown:** Whether the `order_total` rename would be represented later as an external proposal only or as a temporary metadata mutation in a disposable copy.
6. **Unknown:** The exact expected behavior of a future review outcome, because no official “prevention record” entity is verified.
7. **Unknown:** Whether the remaining CLI/server version skew changes any lineage or aspect returned by the local server.
8. **Unknown:** The formal business criticality, usage volume, revenue exposure, SLA, and incident severity of the affected assets.
9. **Unknown:** Whether a judge environment will have the same official datapack version and entity identities.

## 10. Risks

| Risk | Consequence | Mitigation required by the frozen scenario | Classification |
|---|---|---|---|
| Overclaiming chart impact | Dataset reach could be misrepresented as field use | Label confirmed field paths separately from reachable dashboards/charts | Inference |
| Treating derived fields as simple renames | Revenue formulas may be semantically affected without sharing the source name | Preserve direct-versus-derived classification | Inference |
| Version skew | Local server `v1.5.0.6` and CLI/docs 1.6.x may differ | Reverify the frozen baseline in the implementation environment | Verified risk; Inference mitigation |
| Unresolved references | Missing owners/tags/Power BI datasets can create confusing paths | Display them as verified integrity gaps, never silently resolve them | Verified risk; Inference mitigation |
| No assertion/contract evidence | A quality-enforcement story would be invented | Keep assertions and contracts out of the canonical scenario | Verified risk; Inference mitigation |
| No formal keys | A primary-key consequence would be invented | Do not describe `order_id` or another field as a declared primary key | Verified risk; Inference mitigation |
| Graph mutation | Changing the official datapack could invalidate the frozen baseline | Keep the trigger external and the graph read-only for the canonical demo | Inference |
| Five-minute overload | Full graph depth can obscure the simple business story | Lead with the one-field outcome, then reveal layers progressively | Inference |
| Quantified business loss | No revenue/SLA figures exist | Do not invent financial exposure or severity | Unknown evidence; Inference mitigation |

## 11. Assumptions

1. **Inference:** The demonstration is a pre-change impact review, not a claim that the rename has already occurred.
2. **Inference:** `order_amount` is a fixed proposed input name, not an existing field in the verified graph.
3. **Inference:** The official showcase graph remains the source of truth for baseline assets and relationships.
4. **Inference:** Reachability indicates review scope, not proof that every consumer will fail.
5. **Inference:** A fine-grained lineage relationship indicates dependency evidence but does not by itself reveal complete executable transformation logic.
6. **Inference:** Owners, terms, tags, domains, products, and documents are explanatory context rather than proof of runtime behavior.
7. **Inference:** Missing ownership and unresolved references are preserved as graph facts, not repaired for presentation.
8. **Inference:** No synthetic metadata is required to demonstrate the selected scenario.
9. **Unknown:** The eventual hackathon judging rubric and presentation environment have not been provided.

## 12. Future Implementation Notes

### Intentionally not decided

| Topic | Status | Classification |
|---|---|---|
| Application architecture | Not decided | Unknown |
| Programming language | Not decided | Unknown |
| Frameworks and libraries | Not decided | Unknown |
| Frontend or visualization implementation | Not decided | Unknown |
| Backend implementation | Not decided | Unknown |
| Graph traversal algorithms | Not decided | Unknown |
| Change-comparison algorithms | Not decided | Unknown |
| Agent orchestration or model choice | Not decided | Unknown |
| Storage or cache | Not decided | Unknown |
| Deployment topology | Not decided | Unknown |
| Authentication integration | Not decided | Unknown |
| Persistent change/prevention record | Not decided; no verified official entity exists | Unknown |
| Production evaluation metrics and thresholds | Not decided | Unknown |
| Test framework and automation | Not decided | Unknown |
| Mutation versus read-only demonstration environment | Read-only is assumed here; later implementation mechanism is not decided | Inference, Unknown |

### Constraints carried forward

1. **Inference:** Future implementation must preserve C01 as the sole canonical scenario unless this document is explicitly reopened.
2. **Inference:** Future implementation must use the official `showcase-ecommerce` assets and verified lineage rather than synthetic replacements.
3. **Inference:** Future implementation must preserve the verified/inference/unknown distinction in every user-visible result.
4. **Inference:** Future implementation must keep the core five-minute narrative: proposed rename, field-level propagation, derived revenue effects, business consumers, governance context, and review outcome.
5. **Inference:** Future implementation work may choose interfaces and technologies only after the scenario requirements in Section 8 are treated as fixed inputs.
