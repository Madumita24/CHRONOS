# CHRONOS — Reverse Engineering the DataHub `showcase-ecommerce` Graph

**Phase:** Metadata graph knowledge acquisition only<br>
**Snapshot date:** 2026-07-25, America/Phoenix<br>
**Environment:** Local DataHub Community Edition, GMS `v1.5.0.6`, CLI/SDK `1.6.0.15`<br>
**Source:** The already-loaded official `showcase-ecommerce` datapack<br>
**Out of scope:** CHRONOS design, application code, frontend/backend implementation, agents, synthetic metadata, and metadata mutation

## Evidence and interpretation rules

Every factual statement in this report is labeled or covered by one of these evidence classes:

- **Verified — SDK/REST:** enumerated through `DataHubGraph.list_all_entity_urns` and read through GMS entity/aspect endpoints.
- **Verified — GraphQL/CLI:** cross-checked through the authenticated `datahub graphql` CLI.
- **Verified — UI:** authenticated successfully to the local UI and opened catalog search. The UI search page did not finish rendering during the earlier indexing backlog; it is not used as the source for counts.
- **Inference:** a ranking or business-impact conclusion calculated from verified graph structure or wording already stored in metadata.
- **Unknown:** the datapack does not contain evidence sufficient to answer.

No metadata was created, edited, or deleted during this analysis.

## Executive findings

**Verified — SDK/REST and GraphQL/CLI:**

- The registry defines **63 entity types**; **30** currently have instances.
- GMS lists **1,372 current entity URNs** across those types.
- **1,106 URNs contain the datapack namespace `b2fd91`**. This is a namespace count, not a claim that every other entity was created by bootstrap.
- The business graph contains **67 datasets, 12 charts, 3 dashboards, 23 data flows, 23 data jobs, 14 containers, 18 documents, 6 domains, 10 glossary terms, 4 glossary nodes, 6 tags, 5 data products, 12 users, and 8 groups**.
- There are **no assertion, data-contract, ML, form, incident, query, notebook, or ML-feature instances**.
- The graph's physical-to-consumption backbone is:

  `PostgreSQL → Spark export job → S3 → Spark import job → Snowflake → dbt → Snowflake analytics → BI semantic layer → chart → dashboard`

- The longest verified root-to-dashboard chains have **11 edges**.
- The graph has **55 dataset-level upstream edges**, **24 job-input edges**, **23 job-output edges**, **12 dashboard-to-chart links**, **32 chart-input references**, and **8 Power BI dashboard dataset references**.
- Column lineage contains **835 dataset fine-grained mapping groups** plus **199 data-job mapping groups**, for **1,034 fine-grained mapping groups**. A mapping group can contain sets of fields; it is not necessarily one scalar edge.
- `ORDER_DETAILS` on Snowflake is the structural hub: **12 immediate upstream datasets, 14 immediate downstream datasets, all 3 dashboards, and all 12 charts** are reachable from it.
- The most governance-rich asset is the dbt `order_details` model: a 13,912-character description, 12 owner assignments, 2 tags, 5 entity-level glossary terms, a domain, structured properties, field governance, and lineage.
- Assertions and contracts are absent. Stored `testResults` references exist on 14 Snowflake datasets, but these are not assertion entities.

**Inference:** The strongest demonstration surface is the order-entry path centered on the dbt and Snowflake `order_details` assets. This conclusion follows from measured fan-in, fan-out, field lineage, governance richness, and dashboard reach; it is not a CHRONOS architecture decision.

# 1. Entity Inventory

## 1.1 Business and governance entity types

Counts below come from the primary GMS entity-list endpoint, not search-result estimates.

| Entity type | Count | Observed purpose in this graph | Examples | Future relevance to evaluate |
|---|---:|---|---|---|
| `dataset` | 67 | Physical tables, files, dbt sources/models, BI semantic tables, and BI embedded/query datasets | Snowflake `ORDER_DETAILS`; dbt `order_details`; Power BI `ORDER_DETAILS` | High: primary asset and change-impact surface |
| `schemaField` | 917 REST-listed; 916 search-indexed | Addressable columns used by schema metadata, governance, and fine-grained lineage | `orders.order_total`; `order_details.customer_id` | High: column-change analysis |
| `chart` | 12 | Dashboard visualizations consuming BI datasets | `Executive Summary`; `Popular Products`; `Orders By Month` | High: final-consumer impact |
| `dashboard` | 3 | BI reports containing four charts each | Looker and Tableau `Order Entry Dashboard`; Power BI `datahub_order_entries` | High: business-facing impact |
| `dataFlow` | 23 | Spark pipelines; 12 exports and 11 imports | `export_table_orders_to_s3`; `import_table_orders_to_snowflake` | High: pipeline dependency analysis |
| `dataJob` | 23 | One job inside each observed flow, with input/output datasets and field mappings | `export_table_customers_to_s3` | High: operational lineage |
| `document` | 18 | Published catalog documents and runbooks related to datasets | `Orders Table`; `Key Metrics Reference`; inventory-staleness runbook | High: explanations and operational context |
| `container` | 14 | Platform-native hierarchy such as database/schema, bucket/prefix, project, workbook, and BI workspace | `ORDER_ENTRY_DB/ANALYTICS`; `demo-data-bucket/order_entry` | Medium: browsing and scope |
| `domain` | 6 | Organizational/business grouping | `Ecommerce Operations`; `Data Platform Team`; `Marketing` | High: governance context |
| `glossaryTerm` | 10 | Business, privacy, compliance, and metric semantics | `PII`; `Order Total`; `Revenue by Customer Class` | High: semantic impact |
| `glossaryNode` | 4 | Glossary hierarchy | `Classification`; `Order Metrics`; `SOC2 Compliance` | Medium: semantic organization |
| `tag` | 6 | Classification and usage labels | `PII_Data`; `Authoritative Source`; `Most Queried` | High: risk classification |
| `dataProduct` | 5 | Curated business groupings of datasets/dashboards | `Order Entry Analytics`; `Customer Analytics` | High: business grouping |
| `corpuser` | 12 | People represented as owners and actors | Ian Chen; Sarah Chen; Fiona Green | High: accountability |
| `corpGroup` | 8 | Teams represented as owners | Data Platform Team; Business Intelligence; Data Governance | High: accountability |
| `structuredProperty` | 5 | Custom governance attributes | cost center, freshness SLA, quality score, escalation contact, retention period | Medium/high: policy context |
| `assertion` | 0 | Registry capability exists; no assertion instance is present | None | Unknown until real assertion metadata exists |
| `dataContract` | 0 | Registry capability exists; no contract instance is present | None | Unknown until a contract exists |
| ML family | 0 | Six ML-related types are registered but unused | No model, deployment, group, feature, feature table, or primary key | No graph evidence in this datapack |

**Pipeline terminology:** “pipeline” is the business concept represented here by a `dataFlow`; it is not an additional entity type. The inventory therefore contains 23 pipelines/data flows, not 23 plus a second pipeline count.

## 1.2 Platform, model, and administrative entity types

| Entity type | Count | Observed role | Example | Future relevance |
|---|---:|---|---|---|
| `dataPlatform` | 91 | Platform-definition registry, broader than platforms used by the showcase | Snowflake, dbt, S3, PostgreSQL, Looker, Tableau, Power BI, Spark | Supporting reference metadata |
| `entityType` | 63 | Installed entity-type registry | `datahub.dataset`; `datahub.assertion` | Model discovery |
| `dataType` | 5 | Structured-property value-type registry | string, number, date, rich text | Model support |
| `ownershipType` | 4 | Ownership-role registry | business owner, technical owner, data steward, none | Governance support |
| `dataHubUpgrade` | 29 | Completed upgrade/backfill markers | browse-path and lineage-index backfills | Operational only |
| `dataHubPolicy` | 13 | Bootstrap authorization policies | Policy URNs `0`, `1`, `7` | Operational/security only |
| `dataHubPageModule` | 9 | UI page-module definitions | assets, columns, child hierarchy | UI configuration only |
| `dataHubRole` | 3 | Built-in DataHub roles | Admin, Editor, Reader | Operational/security only |
| `dataHubExecutionRequest` | 3 | Operational execution records created by local activity | UUID request URNs | Operational only |
| `dataHubAccessToken` | 2 | Access-token records | Values intentionally omitted | Operational/security only |
| `dataHubIngestionSource` | 2 | Ingestion-source definitions | `datahub-documents`; `datahub-gc` | Ingestion operations |
| `dataHubRetention` | 2 | Retention policies | wildcard and execution-request retention | Operational only |
| `dataHubPageTemplate` | 1 | Default UI home-page template | `home_default_1` | UI configuration only |
| `globalSettings` | 1 | Global platform settings | `globalSettings:0` | Operational only |

## 1.3 Registered types with zero instances

**Verified — SDK/REST:** each type below is registered but returns zero URNs. “Registry capability” is the only purpose evidenced by this instance; detailed behavior cannot be learned from the datapack.

| Entity type | Count | Purpose evidenced here | Example | Future relevance |
|---|---:|---|---|---|
| `application` | 0 | Registry capability only | None | Unknown |
| `assertion` | 0 | Registry capability only | None | Potentially relevant, but untestable here |
| `businessAttribute` | 0 | Registry capability only | None | Unknown |
| `dataContract` | 0 | Registry capability only | None | Potentially relevant, but untestable here |
| `dataHubAction` | 0 | Registry capability only | None | Unknown |
| `dataHubConnection` | 0 | Registry capability only | None | Unknown |
| `dataHubFile` | 0 | Registry capability only | None | Unknown |
| `dataHubOpenAPISchema` | 0 | Registry capability only | None | Unknown |
| `dataHubPersona` | 0 | Registry capability only | None | Unknown |
| `dataHubSecret` | 0 | Registry capability only | None | Operational only if used |
| `dataHubStepState` | 0 | Registry capability only | None | Operational only if used |
| `dataHubView` | 0 | Registry capability only | None | Unknown |
| `dataPlatformInstance` | 0 | Registry capability only | None | Unknown |
| `dataProcess` | 0 | Registry capability only | None | Unknown |
| `dataProcessInstance` | 0 | Registry capability only | None | Unknown |
| `erModelRelationship` | 0 | Registry capability only | None | Unknown |
| `form` | 0 | Registry capability only | None | Unknown |
| `incident` | 0 | Registry capability only | None | Potentially relevant, but untestable here |
| `inviteToken` | 0 | Registry capability only | None | Operational only if used |
| `mlFeature` | 0 | Registry capability only | None | No showcase evidence |
| `mlFeatureTable` | 0 | Registry capability only | None | No showcase evidence |
| `mlModel` | 0 | Registry capability only | None | No showcase evidence |
| `mlModelDeployment` | 0 | Registry capability only | None | No showcase evidence |
| `mlModelGroup` | 0 | Registry capability only | None | No showcase evidence |
| `mlPrimaryKey` | 0 | Registry capability only | None | No showcase evidence |
| `notebook` | 0 | Registry capability only | None | Unknown |
| `platformResource` | 0 | Registry capability only | None | Unknown |
| `post` | 0 | Registry capability only | None | Unknown |
| `query` | 0 | Registry capability only | None | Potentially relevant, but untestable here |
| `role` | 0 | Registry capability only; distinct from the three `dataHubRole` instances | None | Operational only if used |
| `telemetry` | 0 | Registry capability only | None | Operational only if used |
| `test` | 0 | Registry capability only; unresolved test URNs are referenced by `testResults` | None | Requires integrity investigation |
| `versionSet` | 0 | Registry capability only | None | Unknown |

The presence of a registered type is not evidence that the showcase uses the corresponding feature.

## 1.4 Dataset distribution

| Platform | Datasets | Observed role |
|---|---:|---|
| Snowflake | 14 | 11 source tables plus `ORDER_DETAILS`, `ORDER_DETAILS_REPLICA`, and `ORDER_HISTORY` |
| dbt | 13 | 11 dbt sources plus the `order_details` and `order_history` models |
| PostgreSQL | 12 | Physical pipeline roots |
| S3 | 12 | Intermediate exported datasets |
| Tableau | 8 | Four custom SQL datasets and four embedded data sources |
| Power BI | 6 | `ORDER_DETAILS` plus five measure tables |
| Looker | 2 | One view and one Explore |
| **Total** | **67** | |

# 2. Metadata Graph Summary

## 2.1 Physical and analytical topology

**Verified — SDK/REST:**

1. Twelve PostgreSQL datasets are pipeline roots.
2. Twelve Spark export jobs write one S3 dataset each.
3. Eleven Spark import jobs load Snowflake. The promotions import is unusual: it has two inputs, S3 `promotions` and S3 `product_information`, and one Snowflake `PROMOTIONS` output.
4. Eleven Snowflake `ORDER_ENTRY` tables feed eleven dbt source datasets.
5. The dbt `order_details` model joins all eleven dbt sources.
6. Snowflake `ANALYTICS.ORDER_DETAILS` records the dbt model plus all eleven Snowflake source tables as immediate upstreams.
7. Snowflake `ORDER_DETAILS` fans out to Looker, Power BI, Tableau, order-history, and replica datasets.
8. Each BI platform has four charts and one dashboard.

## 2.2 Graph edge inventory

| Relationship family | Verified count | Meaning |
|---|---:|---|
| Dataset `upstreamLineage` edges | 55 | Table/view/model lineage |
| Data-job input edges | 24 | Dataset → Spark job |
| Data-job output edges | 23 | Spark job → dataset |
| Dataset fine-grained mappings | 835 groups | Field-set lineage stored on downstream datasets |
| Job fine-grained mappings | 199 groups | Field-set lineage through Spark jobs |
| Dashboard → chart links | 12 | Four charts per dashboard |
| Chart input references | 32 | 4 Looker, 24 Power BI, 4 Tableau |
| Power BI dashboard direct dataset references | 8 | Six current datasets plus two unresolved URNs |
| Data-product asset references | 11 | Four products with two assets; one product with three |
| Document related-asset references | 56 | Across 18 published documents |

## 2.3 Structural centers

| Asset | Immediate incoming | Immediate outgoing | Dataset-only downstream reach | Heterogeneous descendants | Dashboard reach |
|---|---:|---:|---:|---:|---:|
| Snowflake `ANALYTICS.ORDER_DETAILS` | 12 | 14 | 19 | 34 | 3 |
| dbt `order_details` | 11 | 1 | 20 | 35 | 3 |
| Snowflake `ORDERS` | 0 dataset inputs; pipeline-loaded | 2 | 22 | 37 | 3 |
| Snowflake `CUSTOMERS` | 0 dataset inputs; pipeline-loaded | 2 | 22 | 37 | 3 |
| Each PostgreSQL root used by the main model | 0 | 1 job | — | 41 | 3 |

**Inference:** `ORDER_DETAILS` is the graph's analytical convergence and distribution hub. PostgreSQL roots have deeper paths and more heterogeneous descendants, but `ORDER_DETAILS` has substantially higher immediate fan-out and richer governance.

## 2.4 Core business datasets

The following are called “core” because of verified graph centrality, explicit data-product membership, detailed stored descriptions, or direct dashboard consumption:

- PostgreSQL/Snowflake `ORDERS`
- PostgreSQL/Snowflake `CUSTOMERS`
- PostgreSQL/Snowflake `ORDER_ITEMS`
- PostgreSQL/Snowflake `PRODUCTS`
- PostgreSQL/Snowflake `INVENTORIES`
- PostgreSQL/Snowflake `PROMOTIONS`
- PostgreSQL/Snowflake `ADDRESSES`
- dbt `order_details`
- Snowflake `ANALYTICS.ORDER_DETAILS`
- dbt/Snowflake `order_history`
- Looker `order_details` view and `Order Details` Explore
- Power BI `ORDER_DETAILS` and measure datasets
- Tableau custom-SQL and embedded data sources

# 3. Dataset Catalog

## 3.1 Complete logical catalog

### PostgreSQL and S3

The two platforms contain the same 12 logical names:

`addresses`, `countries`, `customers`, `inventories`, `order_items`, `orders`, `product_categories`, `product_information`, `products`, `promotions`, `regions`, `warehouses`.

PostgreSQL assets are job inputs. S3 assets are job outputs of the exports and inputs to the Snowflake imports.

### Snowflake

- Source schema `order_entry_db.order_entry`: `ADDRESSES`, `COUNTRIES`, `CUSTOMERS`, `INVENTORIES`, `ORDER_ITEMS`, `ORDERS`, `PRODUCT_CATEGORIES`, `PRODUCTS`, `PROMOTIONS`, `REGIONS`, `WAREHOUSES`.
- Analytics schema `order_entry_db.analytics`: `ORDER_DETAILS`, `ORDER_DETAILS_REPLICA`, `ORDER_HISTORY`.

### dbt

- Sources: `addresses`, `countries`, `customers`, `inventories`, `order_items`, `orders`, `product_categories`, `products`, `promotions`, `regions`, `warehouses`.
- Models: `order_details`, `order_history`.

### Looker

- View: `order_details`, 57 fields.
- Explore: `Order Details`, 63 fields.

### Power BI

- `ORDER_DETAILS`, 57 fields.
- `Essential KPI Measures`, 12 fields.
- `Product Perfromance Measures`, 5 fields. The misspelling is present in the metadata.
- `Time Inteligence Measures`, 5 fields. The misspelling is present in the metadata.
- `Geographic Measures`, 4 fields.
- `Customer Analytics Measures`, 2 fields.

### Tableau

- Four `Custom SQL Query` entities, distinguished by URNs ending:
  - `37fcfb15-34ae-973a-5ae3-cf63691d48e3`
  - `4a3af1dd-fd0c-7077-d5fd-aa2fdf87cb23`
  - `8bfe7483-1c9a-a0e1-ec84-57207dd37a15`
  - `f32082e5-06b8-f46e-9047-4611fffe66b0`
- Embedded sources: `Promotions`, `Order Mode`, `Orders By Day`, `Top Product Category`.

## 3.2 Key-column caveat

**Verified — SDK/REST:** none of the inspected important-dataset fields is marked `isPartOfKey=true`.

Therefore this report does not claim that columns such as `order_id` are formally declared primary keys in DataHub schema metadata. “Key-like” below is an **inference from stored names and document text**, not a database-constraint claim.

## 3.3 Important source datasets

| Dataset | Platform/schema | Stored description | Key-like and principal columns with DataHub types | Governance | Immediate lineage | Quality/contracts |
|---|---|---|---|---|---|---|
| `ORDERS` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published `Orders Table` document has 3,683 characters | `order_id` Number, `order_date` String, `customer_id` Number, `order_total` Number, `promotion_id` Number, `warehouse_id` Number, address IDs Number, `payment_method_code` String | 0 owners; `Large Table`, `Most Queried`; terms PII, Order Total, Revenue by Customer Class; no domain | Out to dbt `orders` and Snowflake `ORDER_DETAILS`; pipeline-loaded from S3 | 0 assertions/contracts; `testResults` 6 failing, 3 passing |
| `CUSTOMERS` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published `Customers Table` document has 2,478 characters | `customer_id` Number, names/email/phone String, `dob` String, address fields String, location IDs Number | 0 owners; `Large Table`, `Most Queried`; 4 entity terms and PII field terms; no domain | Out to dbt `customers` and `ORDER_DETAILS` | 0 assertions/contracts; tests 7 failing, 2 passing |
| `ORDER_ITEMS` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published 2,186-character document | `order_id`, `line_item_id`, `product_id` Number; `unit_price` Number; `quantity` Number; dispatch/return dates String | 0 owners; `Large Table`; PII, Order Total, Revenue by Customer Class terms | Out to dbt `order_items` and `ORDER_DETAILS` | 0 assertions/contracts; tests 8 failing, 1 passing |
| `PRODUCTS` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published 2,296-character document | `product_id` Number, `product_name` String, `category_id` Number, status String, list/min price Number | 0 owners; `Large Table`, `Most Queried`; PII term | Out to dbt `products` and `ORDER_DETAILS` | 0 assertions/contracts; tests 7 failing, 2 passing |
| `INVENTORIES` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published 2,207-character document | `product_id`, `warehouse_id`, `quantity_on_hand`, `restock_level`, `max_stock_level`, `reorder_quantity`: Number | 0 owners; `Large Table`; PII term | Out to dbt `inventories` and `ORDER_DETAILS` | 0 assertions/contracts; tests 8 failing, 1 passing |
| `PROMOTIONS` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published 1,532-character document | `promotion_id` Number, name/dates/description String, `promotion_cost` Number | 0 owners; `Large Table`, `No Sample Values`; PII term | Out to dbt `promotions` and `ORDER_DETAILS` | 0 assertions/contracts; tests 8 failing, 1 passing |
| `ADDRESSES` | Snowflake `order_entry_db.order_entry` | Dataset description empty; published 1,390-character document | `address_id`, `customer_id`, country/region IDs Number; address/city fields String; document explicitly labels line-level address as PII | 0 owners; `Large Table`; PII term and field terms | Out to dbt `addresses` and `ORDER_DETAILS` | 0 assertions/contracts; tests 8 failing, 1 passing |

All seven corresponding PostgreSQL roots have no owner or domain assignment. Each feeds one Spark export job. Their S3 versions then feed one Spark import job, except S3 `product_information`, which joins S3 `promotions` as a second input to the promotions import.

## 3.4 Core analytical datasets

### dbt `order_details`

**Verified — SDK/REST:**

- URN: `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)`
- Schema: `model.order_entry_db.order_details`
- Fields: 55
- Stored description: 13,912 characters describing a denormalized order view and its reporting/operational purpose.
- Upstream: all 11 dbt source datasets.
- Downstream: Snowflake `ANALYTICS.ORDER_DETAILS`.
- Fine-grained lineage: 54 mapping groups.
- Ownership: 12 assignments spanning DataHub SE Team, Data Platform Team, Ian Chen, David Kim, Ben Porter, Julia Novak, James Wilson, Karen Okonkwo, Fiona Green, and Sarah Chen.
- Tags: `PII_Data`, `Authoritative Source`.
- Domain: Data Platform Team.
- Entity glossary terms: PII, Certified, GDPR, Order Total, Revenue by Customer Class.
- Field governance: 24 field-term assignments and one `PII_Data` field tag.
- Documentation: one institutional-memory link.
- Assertions/contracts: zero.

Principal fields include:

| Area | Fields and DataHub types |
|---|---|
| Order | `order_id` Number, `order_date` String, `order_mode` String, `order_status` Number, `order_total` Number |
| Customer/PII | `customer_id` Number, names/email/phone String, billing/shipping address fields String/Number |
| Product | `product_id` Number, `product_name` String, `category_id` Number, prices/quantity Number |
| Fulfilment | `warehouse_id` Number, `dispatch_date` String, `estimated_delivery` String, `quantity_on_hand` Number, `stock_status` String |
| Derived | `line_total`, `discount_amount`, `discount_percent` Number; `delivery_status`, `return_status` String; `updated_at` Time |

### Snowflake `ANALYTICS.ORDER_DETAILS`

**Verified — SDK/REST:**

- Fields: 55.
- Immediate upstream: the dbt model plus all 11 Snowflake source tables.
- Immediate downstream: 14 datasets.
- Fine-grained lineage: 108 mapping groups.
- Ownership: DataHub SE Team, David Kim, Julia Novak.
- Tags: `Large Table`, `Most Queried`.
- Domain: Ecommerce Operations.
- Terms: PII, SOC2 Auditable, Order Total, Revenue by Customer Class.
- Data-product membership: Promotions Performance.
- Assertions/contracts: zero.
- Non-assertion `testResults`: 4 failing and 10 passing.

This is the only dataset with both double-digit immediate fan-in and fan-out.

### Order history

| Asset | Fields | Upstream | Downstream | Governance | Quality |
|---|---:|---|---|---|---|
| dbt `order_history` | 5 | Snowflake `ORDER_DETAILS` | Snowflake `ORDER_HISTORY` | Domain E-Commerce; PII term; no owner | No assertions/contracts |
| Snowflake `ORDER_HISTORY` | 5 | dbt `order_history`, Snowflake `ORDER_DETAILS`, and a self-represented history edge in stored lineage | None | `Large Table`; PII term; no owner/domain | No assertions/contracts; tests 8 failing, 1 passing |

Fields are `order_id` Number, `customer_id` Number, `order_status` Number, `order_total` Number, and `as_of_date` Date.

### BI semantic datasets

| Asset | Fields | Upstream | Governance | Consumer |
|---|---:|---|---|---|
| Looker view `order_details` | 57 | Snowflake `ORDER_DETAILS` | 4 owners; domain Data Platform Team; PII term | Looker Explore |
| Looker Explore `Order Details` | 63 | Looker view | 3 owners; Data Platform Team domain; ecommerce tag; PII term | Four Looker charts |
| Power BI `ORDER_DETAILS` | 57 | Snowflake `ORDER_DETAILS` | Karen Okonkwo; PII term | Four Power BI charts |
| Five Power BI measure tables | 2–12 each | Snowflake `ORDER_DETAILS` | No owners; PII term | All four Power BI charts |
| Four Tableau custom-SQL datasets | 4–5 each | Snowflake `ORDER_DETAILS` | No owners; one or two terms | Four embedded sources |
| Four Tableau embedded sources | 5–6 each | One custom-SQL dataset each | One owner assignment each; one term | One Tableau chart each |

All these assets have zero assertions and zero contracts.

## 3.5 Field-level impact examples

| Verified source field | Downstream fields | Downstream datasets | Maximum field depth | Examples at the edge |
|---|---:|---:|---:|---|
| PostgreSQL `orders.order_total` | 25 | 20 | 5 | Tableau `TOTAL_REVENUE`, `AVERAGE_ORDER_VALUE`; Power BI `ORDER_TOTAL`; Looker `order_total` |
| PostgreSQL `inventories.quantity_on_hand` | 25 | 14 | 7 | `STOCK_STATUS`, `QUANTITY_ON_HAND` across dbt, Snowflake, Power BI, Looker |
| PostgreSQL `order_items.return_date` | 25 | 14 | 5 | `return_date` and derived `return_status` across BI layers |
| PostgreSQL `addresses.address_line1` | 25 | 14 | 5 | Billing and shipping address fields across dbt, Snowflake, Power BI, Looker |
| PostgreSQL `orders.order_id` | 24 | 24 | 5 | Tableau order-count fields, order history, Power BI, Looker |
| PostgreSQL `orders.order_date` | 19 | 16 | 5 | Tableau `ORDER_DATE`, Power BI revenue-by-month, Looker date dimensions |
| PostgreSQL `customers.customer_id` | 17 | 16 | 5 | Power BI Customer LTV and IDs; order-history IDs; Looker customer ID |
| PostgreSQL `customers.cust_email` | 14 | 14 | 5 | PII-bearing email fields in dbt, Snowflake, Power BI, Looker |
| PostgreSQL `promotions.promotion_id` | 14 | 14 | 5 | Promotion IDs across the analytical and BI layers |
| PostgreSQL `products.product_id` | 14 | 14 | 5 | Product IDs across the analytical and BI layers |

# 4. Governance Analysis

## 4.1 Ownership

There are 98 owner assignments across the inspected business/governance types:

| Entity type | Assignments |
|---|---:|
| Dataset | 51 |
| Data job | 16 |
| Data product | 8 |
| Dashboard | 5 |
| Chart | 4 |
| Domain | 3 |
| Tag | 3 |
| Glossary term | 3 |
| Glossary node | 2 |
| Container | 1 |

Most frequently referenced owners:

| Owner URN/identity | Assignments |
|---|---:|
| Data Platform Team group | 23 |
| Ian Chen | 22 |
| David Kim | 12 |
| Fiona Green | 10 |
| `owner+bryan.prosser@datahub.com` | 5 |
| Andrea Garcia | 4 |

**Verified gap:** several source datasets have no owner. Some data-product owner references use URNs that do not resolve to the 12 loaded user entities, including `owner+bryan.prosser@datahub.com`, un-namespaced `EMP006`, and un-namespaced `ORG_DATA_PLATFORM`.

## 4.2 Domains

Hierarchy stored in `domainProperties.parentDomain`:

- Acme Corporation
  - Engineering Division
    - Data Platform Team
  - Ecommerce Operations
- E-Commerce, standalone
- Marketing, standalone

Membership counts:

| Domain | Asset memberships |
|---|---:|
| Data Platform Team | 23 |
| Ecommerce Operations | 6 |
| E-Commerce | 1 |
| Marketing | 1 |

The remaining two hierarchy-only domains have no direct asset membership in this snapshot.

## 4.3 Tags

Entity-level assignment counts:

| Tag reference | Assignments |
|---|---:|
| `Large Table` | 13 |
| `__default_gold` | 5 |
| `Most Queried` | 4 |
| `No Sample Values` | 2 |
| `PII_Data` | 1 |
| `Authoritative Source` | 1 |
| `b2fd91.ecommerce` | 1 |

Field-level assignments are two `PII_Data` and one `No Sample Values`.

**Verified gap:** `__default_gold` is referenced five times but has no corresponding loaded tag entity. The five references occur on the five data products.

## 4.4 Glossary

Glossary hierarchy:

- Classification: PII, GDPR
- Order Metrics: Order Total, Revenue by Customer Class
- Certification: Certified
- SOC2 Compliance: SOC2 Auditable
- Standalone: Email Address, Phone Number, First Name, Last Name

Assignment counts:

- Entity-level: PII 69; Order Total 21; Revenue by Customer Class 17; GDPR 3; SOC2 Auditable 2; Certified 1.
- Field-level: PII 163; Order Total 3.

**Verified gap:** two entity assignments point to an un-namespaced PII term URN rather than the loaded `b2fd91` PII term.

## 4.5 Descriptions and documents

Entity types with non-empty descriptions/content:

| Type | Described / total |
|---|---:|
| Documents | 18 / 18 |
| Data flows | 23 / 23 |
| Datasets | 13 / 67 |
| Glossary terms | 9 / 10 |
| Domains | 5 / 6 |
| Data products | 5 / 5 |
| Charts | 4 / 12 |
| Tags | 4 / 6 |
| Containers | 2 / 14 |
| Dashboards | 0 / 3 |

All 18 documents are `PUBLISHED`. Together they contain 35,785 characters and 56 related-asset references. They cover:

- catalog and analytics overviews,
- source-table documentation,
- order-details and order-history documentation,
- a key-metrics reference,
- operational runbooks for inventory staleness, order-count discrepancies, and promotion attribution.

## 4.6 Data products

| Product | Assets | Owner assignments | Domain | Stored business claim |
|---|---|---:|---|---|
| Inventory & Fulfilment | Snowflake `INVENTORIES`, `PRODUCTS` | 1 | Ecommerce Operations | Primary product for supply-chain, operations, and logistics reporting |
| Promotions Performance | Snowflake `PROMOTIONS`, `ORDER_DETAILS` | 1 | Ecommerce Operations | Authoritative source for promotion reporting |
| Returns & Refunds | Snowflake `ORDER_ITEMS`, `ORDERS` | 1 | Ecommerce Operations | Authoritative source for returns/refunds |
| Customer Analytics | Snowflake `CUSTOMERS`, `ADDRESSES` | 1 | Ecommerce Operations | Unified customer identity/segmentation/behavior view |
| Order Entry Analytics | dbt `order_details`, Snowflake `ORDERS`, Looker dashboard | 4 | Data Platform Team | Consolidated order-lifecycle analytics |

The business claims above are paraphrases of the stored data-product descriptions, not external assumptions.

## 4.7 Container hierarchy

Verified major branches:

- `demo-data-bucket`
  - `order_entry`: 12 S3 datasets
- PostgreSQL `order_entry_db`
  - `order_entry`: 12 PostgreSQL datasets
- Snowflake `ORDER_ENTRY_DB`
  - `ORDER_ENTRY`: 11 source datasets
  - `ANALYTICS`: `ORDER_DETAILS`, `ORDER_DETAILS_REPLICA`, `ORDER_HISTORY`
- Looker `Shared`
  - `Order Entry`: Looker dashboard
- Tableau `Order Entry`
  - `order_entries_dashboard`: 8 datasets plus dashboard
- Power BI `Order Entry`: 6 current datasets plus dashboard
- Separate Looker view and Explore containers

Thirteen dbt datasets have no container assignment.

## 4.8 Richest metadata

**Inference from verified aspect counts and content:**

1. dbt `order_details`
2. Snowflake `ORDER_DETAILS`
3. Order Entry Analytics data product
4. The other four data products
5. Eleven dbt source datasets
6. The 18 document entities as a documentation collection

The ranking uses description length, owners, domain, tags, terms, field governance, structured properties, documentation, and lineage. It does not use an invented business-usage number.

# 5. Lineage Analysis

## 5.1 Connectivity leaders

| Question | Verified answer |
|---|---|
| Most direct incoming dataset edges | Snowflake `ORDER_DETAILS`: 12 |
| Second-most incoming | dbt `order_details`: 11 |
| Most direct outgoing dataset edges | Snowflake `ORDER_DETAILS`: 14 |
| Highest direct dataset degree | Snowflake `ORDER_DETAILS`: 26 combined |
| Largest heterogeneous downstream set | Main PostgreSQL roots: 41 descendants each |
| Longest root-to-dashboard paths | 11 edges |
| Dashboard coverage of main roots | All 3 dashboards |
| Chart coverage of main roots | All 12 charts |

## 5.2 Table and column lineage

- **Table-level:** dataset `upstreamLineage`, data-job inputs/outputs, chart inputs, and dashboard/chart relations.
- **Column-level:** schema-field URNs in dataset and job fine-grained lineage.
- **Pipeline-level:** PostgreSQL → Spark job → S3 and S3 → Spark job → Snowflake.
- **BI-level:** Snowflake → Looker/Power BI/Tableau dataset → chart → dashboard.

Column lineage is materially richer than simple same-name copying. Verified examples include:

- `quantity_on_hand` producing `stock_status`,
- `return_date` producing `return_status`,
- `order_total` producing Tableau `TOTAL_REVENUE` and `AVERAGE_ORDER_VALUE`,
- `customer_id` producing Power BI `Customer LTV`,
- `order_date` producing Power BI `Revenue by Month`.

## 5.3 Datasets feeding dbt, pipelines, dashboards, and ML

- **dbt:** Eleven dbt source datasets feed dbt `order_details`; Snowflake `ORDER_DETAILS` feeds dbt `order_history`.
- **Pipelines:** 12 PostgreSQL datasets feed export jobs. Twelve S3 datasets supply 24 job-input edges to 11 import jobs because the promotions import has two inputs.
- **Dashboards:** Snowflake `ORDER_DETAILS` reaches all three dashboards through platform-specific BI layers.
- **ML:** no ML entity exists, so no dataset-to-ML lineage can be reported.

## 5.4 Ten verified dependency chains

Lengths count relationship edges. Business impact is an inference from chart names, stored documents, and data-product descriptions.

| # | Verified chain | Length | Owner coverage | Business purpose and inferred break impact |
|---:|---|---:|---|---|
| 1 | PostgreSQL `orders` → export job → S3 `orders` → import job → Snowflake `ORDERS` → dbt `orders` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Power BI `Essential KPI Measures` → `Executive Summary` chart → Power BI dashboard | 10 | Source unowned; governed at dbt/model/dashboard | Executive order KPIs; break could remove order/revenue metrics |
| 2 | PostgreSQL `customers` → export → S3 → import → Snowflake `CUSTOMERS` → dbt `customers` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Power BI Customer Analytics → `Customer Analysis` → dashboard | 10 | Source unowned; model and dashboard owned | Customer analysis/LTV; break could affect customer segmentation and PII-bearing fields |
| 3 | PostgreSQL `addresses` → export → S3 → import → Snowflake `ADDRESSES` → dbt `addresses` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Power BI Geographic Measures → `Geographics` → dashboard | 10 | Source unowned; model/dashboard owned | Geographic reporting; break could remove billing/shipping location analysis |
| 4 | PostgreSQL `products` → export → S3 → import → Snowflake `PRODUCTS` → dbt `products` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Looker view → Looker Explore → `Popular Products` → Looker dashboard | 11 | Product source unowned; Explore/model owned | Product-popularity reporting; break could affect merchandising analysis |
| 5 | PostgreSQL `promotions` → export → S3 → import → Snowflake `PROMOTIONS` → dbt `promotions` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Looker view → Explore → `Promotions` → dashboard | 11 | Source unowned; downstream governed | Promotion performance; break could disrupt campaign reporting |
| 6 | PostgreSQL `orders` → export → S3 → import → Snowflake `ORDERS` → dbt `orders` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Looker view → Explore → `Orders by Day` → dashboard | 11 | Source unowned; downstream governed | Daily order trend; break could suppress time-series order reporting |
| 7 | PostgreSQL `order_items` → export → S3 → import → Snowflake `ORDER_ITEMS` → dbt `order_items` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Tableau custom SQL → `Orders By Day` source → `Orders By Month` → Tableau dashboard | 11 | Source unowned; Tableau source/dashboard owned | Monthly orders; break could affect volume and line-item-derived reporting |
| 8 | PostgreSQL `products` → export → S3 → import → Snowflake `PRODUCTS` → dbt `products` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Tableau custom SQL → `Top Product Category` → `Popular Products Categories` → dashboard | 11 | Source unowned; Tableau layer owned | Category performance; break could affect category ranking |
| 9 | PostgreSQL `inventories` → export → S3 → import → Snowflake `INVENTORIES` → dbt `inventories` → dbt `order_details` → Snowflake `ORDER_DETAILS` → Power BI Product Performance → `Executive Summary` → dashboard | 10 | Source unowned; model/dashboard owned | Stock and fulfilment metrics; `quantity_on_hand` has 25 field descendants |
| 10 | PostgreSQL `orders` → export → S3 → import → Snowflake `ORDERS` → dbt `orders` → dbt `order_details` → Snowflake `ORDER_DETAILS` → dbt `order_history` → Snowflake `ORDER_HISTORY` | 9 | History assets unowned; core model owned | Historical order tracking; no dashboard is linked downstream in the stored graph |

No chain contains an ML asset because the ML entity count is zero.

# 6. Dashboard Analysis

Dashboard descriptions are empty, so business purpose and relative criticality are inferred only from chart titles, source datasets, owners, and graph reach.

## 6.1 Looker — Order Entry Dashboard

**Verified:**

- Platform: Looker.
- Four charts: Popular Products, Orders by Day, Promotions, Order Mode.
- Direct source: Looker Explore `Order Details`.
- Upstream dataset depth: 5 from the Explore to a Snowflake root; 11 from a PostgreSQL root when jobs are included.
- Upstream dataset set: 26; root sources: 11 Snowflake tables.
- Owners: none on the dashboard.
- Domain: Ecommerce Operations.
- Container: `Shared / Order Entry`.

**Inference:** broad commercial/operational dashboard, but weaker ownership metadata than the other dashboards.

## 6.2 Power BI — `datahub_order_entries`

**Verified:**

- Four charts/pages: Executive Summary, Customer Analysis, Geographics, DAX Visual.
- Each chart reads six current Power BI datasets.
- Dashboard also stores eight direct dataset references; two references (`DAX_ORDER_DETAILS` and `DateTable`) do not resolve to current dataset entities.
- Current sources: `ORDER_DETAILS`, Essential KPI Measures, Time Inteligence Measures, Customer Analytics Measures, Product Perfromance Measures, Geographic Measures.
- Upstream depth: 4 at dataset-only level; 10 from a PostgreSQL root through jobs.
- Upstream dataset set: 30; root sources: 11 Snowflake tables.
- Owners: Sarah Chen, Marco Santos, Priya Sharma, Andrea Garcia.
- Domain: none.
- Container: Power BI `Order Entry`.

**Inference:** strongest executive-demo dashboard because it has the widest explicit source set, four owners, and an Executive Summary chart.

## 6.3 Tableau — Order Entry Dashboard

**Verified:**

- Four charts: Orders By Month, Popular Products Categories, Promotions, Order Mode.
- Direct chart sources: four embedded Tableau datasets.
- Those sources are fed by four custom-SQL datasets, all ultimately from Snowflake `ORDER_DETAILS`.
- Upstream dataset depth: 5; 11 from a PostgreSQL root through jobs.
- Upstream dataset set: 32; root sources: 11 Snowflake tables.
- Owner: David Kim.
- Domain: Marketing.
- Container: `Order Entry / order_entries_dashboard`.

**Inference:** strongest marketing/commercial scenario because the dashboard is in the Marketing domain and explicitly covers promotions, product categories, order mode, and monthly trends.

## 6.4 Relative criticality

**Inference, not a stored rating:**

1. Power BI `datahub_order_entries`
2. Tableau Order Entry Dashboard
3. Looker Order Entry Dashboard

Basis: current source breadth, owner coverage, domain context, chart names, and unresolved references. No usage volume, SLA, revenue tier, or formal criticality attribute exists, so the ordering is provisional.

# 7. Assertions Analysis

## 7.1 Assertion inventory

| Requested attribute | Verified result |
|---|---|
| Assertion count | 0 |
| Assertion types | None |
| Target datasets | None |
| Target columns | None |
| Validation purposes | None |
| Failure severities | None |
| Data contracts | 0 |

There is nothing to enumerate as an assertion. Any claim about assertion severity or behavior would be invented.

## 7.2 `testResults` are not assertions

Fourteen Snowflake datasets have a `testResults` aspect:

- 14 assets have test-result references.
- 13 have at least one failure.
- Total references: 95 failing, 28 passing.
- Snowflake `ORDER_DETAILS`: 4 failing, 10 passing.
- `ORDER_DETAILS_REPLICA`: 0 failing, 1 passing.
- The other 12 Snowflake source/history datasets have 6–8 failures and 1–3 passes.

The references describe governance, cost, quality, and compliance checks such as ownership, documentation, domain, zero queries, and GDPR-form completion. The referenced `test` URNs do not resolve to current `test` entities, whose count is zero.

**Verified distinction:** these results must not be presented as DataHub assertion entities.

## 7.3 Future impact-analysis relevance

**Inference:** if real assertion metadata is later added, the existing dataset/field lineage could connect an assertion failure to downstream dashboards and data products. This is only a capability to investigate; the current graph provides no assertion instance with which to verify it.

# 8. High-Risk Assets

## 8.1 Ranking method

This is an **inference** built from verified graph values. The comparison index weights:

- all heterogeneous descendants,
- number of reachable dashboards and charts,
- direct fan-out,
- maximum downstream depth,
- pipeline-input use,
- data-product membership,
- owners, tags, terms, domains, and documentation.

It is not a DataHub-provided score. ML usage contributes zero for every asset because ML assets are absent.

## 8.2 Top 10

| Rank | Asset | Verified impact evidence | Why high impact |
|---:|---|---|---|
| 1 | Snowflake `ANALYTICS.ORDER_DETAILS` | 12 in, 14 out, 34 heterogeneous descendants, 3 dashboards, 12 charts, 1 data product | Central distribution hub for every BI platform |
| 2 | Snowflake `ORDERS` | 2 direct dataset children, 37 descendants, depth 7, 3 dashboards, 12 charts, 2 data products | Core order header and high-value metrics |
| 3 | dbt `order_details` | 11 in, 35 descendants, depth 5, 3 dashboards, 12 charts, 12 owners, richest metadata | Transformation convergence point and authoritative-tagged model |
| 4 | Snowflake `CUSTOMERS` | 2 direct children, 37 descendants, 3 dashboards, 12 charts, Customer Analytics product | Customer identity and PII propagate broadly |
| 5 | PostgreSQL `orders` | 41 descendants, depth 11, pipeline input, 3 dashboards, 12 charts | Deep root; `order_total` alone reaches 25 fields in 20 datasets |
| 6 | PostgreSQL `inventories` | 41 descendants, depth 11, pipeline input; `quantity_on_hand` reaches 25 fields | Drives stock-status derivations and Inventory & Fulfilment reporting |
| 7 | PostgreSQL `order_items` | 41 descendants, depth 11; `return_date` reaches 25 fields | Drives return status, quantities, prices, and Returns & Refunds |
| 8 | PostgreSQL `addresses` | 41 descendants, depth 11; `address_line1` reaches 25 fields | PII and geographics fan out to billing/shipping fields |
| 9 | PostgreSQL `customers` | 41 descendants, depth 11; customer ID reaches 17 fields, email 14 | Root for customer analysis and PII |
| 10 | PostgreSQL `products` | 41 descendants, depth 11; product ID reaches 14 fields | Feeds product-performance and inventory products |

PostgreSQL `promotions` is effectively tied with ranks 6–10 on graph-level impact and is the next candidate; it was separated only by the selected field-fanout and data-product evidence.

# 9. Candidate Demo Scenarios

These are recommendations, not a selected design.

## Scenario 1 — Rename `orders.order_total`

- **Verified basis:** 25 downstream fields in 20 datasets, depth 5; reaches Tableau total/average revenue, Power BI order-total measures, Looker order total, and order history.
- **Affected assets:** PostgreSQL/S3/Snowflake/dbt order datasets, Snowflake `ORDER_DETAILS`, Power BI measure tables, Tableau sources, Looker, order history, all three dashboards.
- **Expected propagation:** schema-field change through two Spark jobs, dbt sources/model, Snowflake analytics, and BI semantic layers.
- **Difficulty:** Medium/high, because the graph contains both direct mappings and derived measures.
- **Demo quality:** Very high.
- **Novelty:** High; shows one physical monetary field becoming multiple business measures.

## Scenario 2 — Change `inventories.quantity_on_hand` from numeric to an incompatible type

- **Verified basis:** 25 downstream fields in 14 datasets, maximum field depth 7; produces `stock_status` in downstream layers.
- **Affected assets:** inventory pipeline, dbt `order_details`, Snowflake `ORDER_DETAILS`, replica, Power BI measure tables, Looker.
- **Expected propagation:** direct type impact plus derived stock-status logic.
- **Difficulty:** High because derived-field compatibility must be explained.
- **Demo quality:** Very high for transformation-aware impact.
- **Novelty:** High; combines direct and semantic derivations.

## Scenario 3 — Delete or mask `customers.cust_email`

- **Verified basis:** 14 downstream fields in 14 datasets; the email is governed as PII.
- **Affected assets:** customer pipeline, dbt/Snowflake `order_details`, Power BI, Looker, and customer-oriented reporting.
- **Expected propagation:** removal or policy-driven masking through the customer and analytics layers.
- **Difficulty:** Medium.
- **Demo quality:** High because it combines schema change, PII governance, and lineage.
- **Novelty:** High governance relevance.

## Scenario 4 — Remove Snowflake `ANALYTICS.ORDER_DETAILS`

- **Verified basis:** 14 immediate downstream datasets, 34 heterogeneous descendants, 3 dashboards, 12 charts.
- **Affected assets:** order history, replica, all Looker datasets/charts, six current Power BI datasets/four charts, eight Tableau datasets/four charts, three dashboards, data products.
- **Expected propagation:** broad table-level outage across every BI platform.
- **Difficulty:** Low/medium to explain because the fan-out is explicit.
- **Demo quality:** Extremely high visually.
- **Novelty:** Medium; classic blast-radius scenario, but unusually well supported by this graph.

## Scenario 5 — Missing quality assertion on `ORDER_DETAILS`

- **Verified basis:** the most connected dataset has zero assertion and contract entities. Its `testResults` references are not assertions.
- **Affected assets:** no assertion currently exists to break. The risk is the absence of a quality guard on 34 descendants and all dashboards.
- **Expected propagation:** an impact view could identify downstream exposure but cannot show an assertion failure from current metadata.
- **Difficulty:** Medium because the demo must distinguish absence of control from a failed control.
- **Demo quality:** High if framed as a governance gap; lower if a real assertion result is required.
- **Novelty:** High.

### Scenarios not currently justified

- **Primary-key or constraint change:** no inspected field is marked as a key and no contract exists. A constraint scenario would require evidence not present here.
- **ML breakage:** no ML entity exists.
- **Existing assertion violation:** no assertion exists.

# 10. Open Questions

1. Why do the Power BI dashboard references include missing `DAX_ORDER_DETAILS` and `DateTable` entities?
2. Should the two un-namespaced PII glossary references resolve to the namespaced PII term?
3. Should the five `__default_gold` references have a loaded tag entity?
4. Should un-namespaced data-product owners be reconciled with the namespaced loaded users/groups?
5. Why are key-like source columns not marked `isPartOfKey`?
6. Is Snowflake `ORDER_HISTORY` intentionally represented with a self-history lineage relationship?
7. Why does `import_table_promotions_to_snowflake` consume both promotions and product-information S3 datasets?
8. Which of the 95 failing `testResults` are intended showcase signals versus missing-governance examples?
9. Are dashboard descriptions intentionally empty?
10. Which business SLA or criticality source should supersede this report's structural inference?
11. Are the 248 aspects filtered during the CLI/server version mismatch needed for graph-feature analysis?
12. Should the remaining Kafka MAE backlog be allowed to drain fully before freezing a long-lived baseline?

# 11. Unknowns

- Actual query volume and end-user counts for each dashboard.
- Financial value, formal tier, SLA, RTO/RPO, or incident severity of any asset.
- Whether empty dashboard descriptions are intentional.
- The semantics of missing Power BI references beyond their stored URNs.
- Primary-key and database-constraint truth.
- Assertion behavior, failure severity, and contract enforcement.
- ML dependency behavior.
- Whether every owner reference is expected to resolve locally.
- Whether the showcase's business names represent a fictional Acme organization or another intended identity; this report preserves the stored wording.
- Production behavior: this analysis concerns only the local quickstart graph.

# 12. Opportunities for CHRONOS

These are evidence-backed areas for later evaluation, not architecture or feature commitments:

- table- and column-level blast-radius analysis centered on `ORDER_DETAILS`,
- multi-system path explanations from PostgreSQL through Spark/S3/Snowflake/dbt to BI,
- governance-aware impact using PII, glossary, ownership, domain, and data-product context,
- dashboard and chart consumer impact,
- derived-field impact such as stock status, return status, revenue, and Customer LTV,
- detection and explanation of unresolved metadata references,
- detection of missing controls such as assertions, contracts, owners, domains, or keys,
- comparison of physical-source risk versus governed analytical-hub risk,
- use of published documents and runbooks as explanatory context.

No opportunity in this list has been selected for implementation.

# Verification Checklist

- [x] Complete registered entity-type inventory
- [x] Counts taken from GMS primary entity listing
- [x] GraphQL cross-check: 67 datasets and 3 dashboards
- [x] CLI used for authenticated GraphQL execution
- [x] UI authentication and catalog route inspected
- [x] All 67 datasets cataloged by platform/logical identity
- [x] Important schemas and field types inspected
- [x] Ownership, domains, tags, glossary, data products, documents, and containers inspected
- [x] Dataset, job, field, chart, and dashboard lineage analyzed
- [x] Longest chains and connectivity leaders calculated
- [x] All three dashboards analyzed
- [x] Assertion count verified as zero
- [x] `testResults` explicitly distinguished from assertions
- [x] High-impact assets ranked using disclosed evidence
- [x] Five demo scenarios recommended without selecting one
- [x] Unknowns and metadata-integrity questions recorded
- [x] No metadata mutation or synthetic entity creation
