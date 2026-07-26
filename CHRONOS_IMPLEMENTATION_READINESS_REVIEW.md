# CHRONOS — Final Engineering Review and Implementation Readiness

**Verified:** This review treats Phases 0.1 through 0.5 as immutable source material:

- **Verified:** [Phase 0.1 — DataHub Environment](./CHRONOS_DATAHUB_LEARNING_REPORT.md)
- **Verified:** [Phase 0.2 — Showcase Graph](./CHRONOS_SHOWCASE_ECOMMERCE_GRAPH_REPORT.md)
- **Verified:** [Phase 0.3 — DataHub Interfaces](./CHRONOS_DATAHUB_INTERFACE_REPORT.md)
- **Verified:** [Phase 0.4 — Frozen Demonstration](./CHRONOS_CANONICAL_DEMONSTRATION_SPECIFICATION.md)
- **Verified:** [Phase 0.5 — Complete Technical Specification](./CHRONOS_COMPLETE_TECHNICAL_SPECIFICATION.md)

**Inference:** This document resolves terminology and behavioral ambiguity without adding features or changing the frozen demonstration.

## Classification

- **Verified** — established by the immutable Phase 0.1–0.5 documents or the locally verified DataHub graph.
- **Inference** — a binding clarification, boundary, invariant, or engineering decision derived from the verified material.
- **Unknown** — evidence not available in the immutable source material; every remaining Unknown has a non-blocking implementation default.

## 1. Executive Summary

**Inference:** The Technical Design Review Board approves CHRONOS for implementation of one narrowly bounded, read-only demonstration.

**Inference:** The only supported demonstration is identified by **`CHRONOS-DEMO-001`**.

**Verified:** Its source metadata is PostgreSQL dataset `orders`, field `order_total`, type Number.

**Inference:** Its proposed change is `order_total` → `order_amount`; `order_amount` is a proposal value and is not represented as existing DataHub metadata.

**Verified:** The canonical field-level Blast Radius is 25 unique downstream schema fields contained by 20 unique downstream datasets, with maximum verified field-lineage depth 5.

**Inference:** Jobs, flows, charts, dashboards, data products, owners, terms, tags, domains, structured properties, and documents provide path or business context but are not included in the 25-field/20-dataset Blast Radius count.

**Inference:** CHRONOS captures an immutable Metadata Snapshot, derives a Current Graph, creates a separate temporary Future Graph, analyzes impact and governance, produces Repair Recommendations, verifies the result, and emits a Review Package whose outcome is **Hold for downstream compatibility review**.

**Inference:** CHRONOS never mutates DataHub or any source, pipeline, transformation, warehouse, or BI system.

**Inference:** Implementation may begin because all product-behavior ambiguities have a canonical resolution in this review; the Remaining Unknowns are non-blocking evidence or technology details.

## 2. Consistency Review

### 2.1 Review result

**Verified:** Phase 0.1 is an environment and platform-learning report and does not select a demonstration.

**Verified:** Phase 0.2 evaluates five candidate demonstrations and explicitly says none is selected at that phase.

**Verified:** Phase 0.4 selects C01, freezes the proposed `order_total` → `order_amount` rename, and excludes all alternative scenarios.

**Verified:** Phase 0.5 carries that same source field, proposed name, 25-field/20-dataset baseline, read-only behavior, and Hold outcome into the complete technical specification.

**Inference:** The documents are chronologically consistent about scenario selection; Phase 0.2's alternatives are historical analysis, not current options.

### 2.2 Ambiguities and canonical resolutions

| ID | Source ambiguity or inconsistency | Evidence | Canonical version | Classification |
|---|---|---|---|---|
| CR01 | Phase 0.2 says no scenario was selected while Phase 0.4 selects C01 | The statements occur in different sequential phases | Only `CHRONOS-DEMO-001` is supported; Phase 0.2 scenarios are historical | Verified history; Inference resolution |
| CR02 | C01 initially says “rename to a proposed new name,” while later documents use `order_amount` | Phase 0.4 freezes `order_amount` | Proposed name is exactly `order_amount` | Verified |
| CR03 | Source is variously written `orders.order_total`, PostgreSQL `orders.order_total`, or dataset `orders`, field `order_total` | All refer to the same verified source | Display name is `PostgreSQL / order_entry_db / order_entry / orders / order_total`; runtime URNs are resolved from DataHub | Verified components; Inference canonical display |
| CR04 | Snowflake analytical hub is written `ORDER_DETAILS`, `ANALYTICS.ORDER_DETAILS`, and Snowflake `order_details` in descriptive text | Phase 0.2 catalogs the warehouse object under database `ORDER_ENTRY_DB`, schema `ANALYTICS` | Always display `Snowflake / ORDER_ENTRY_DB / ANALYTICS / ORDER_DETAILS` | Verified components; Inference canonical display |
| CR05 | Snowflake source `ORDERS` can be confused with PostgreSQL `orders` | Both assets exist and differ by platform and layer | Always include platform; use `PostgreSQL … / orders` and `Snowflake / ORDER_ENTRY_DB / ORDER_ENTRY / ORDERS` | Verified |
| CR06 | dbt `order_details` is referenced by logical name, schema name, and full URN | Phase 0.2 verifies the full URN | Display `dbt / b2fd91.ORDER_ENTRY_DB.analytics.order_details`; retain its resolved DataHub URN as machine identity | Verified |
| CR07 | “Depth 5” and root-to-dashboard path lengths 10–11 both appear | One is field-lineage depth; the other is heterogeneous relationship length | `Field Depth` means schema-field lineage hops; `Path Length` must state the relationship families counted | Verified facts; Inference terminology |
| CR08 | 25 fields/20 datasets, 41 heterogeneous descendants, 34 hub descendants, 3 dashboards, and 12 charts can all be called blast radius | They answer different graph questions | `Blast Radius` means only the field-level 25/20 count for `CHRONOS-DEMO-001`; all other counts are named `Context Reach` or asset-specific descendants | Verified counts; Inference resolution |
| CR09 | Phase 0.2 sometimes describes dashboard reach as field impact | Chart input references are not verified column-use references | All three BI/dashboard branches are Reachable Context; a chart is Confirmed Field Impact only with field-level evidence | Verified limitation; Inference resolution |
| CR10 | “Affected Asset” can mean a proven field consumer or merely a reachable business object | Both appear in prior prose | Every affected item carries exactly one Impact Status: Confirmed Direct, Confirmed Derived, Reachable Context, or Unknown | Inference |
| CR11 | Phase 0.4 leaves open external proposal versus temporary mutation in a disposable copy | Phase 0.5 resolves all execution as read-only | The Proposal remains external; no DataHub mutation is allowed in any environment | Verified progression; Inference final rule |
| CR12 | “Metadata Proposal” may be confused with DataHub Metadata Change Proposal (MCP) | Phase 0.3 defines MCP as a write unit; Phase 0.5 says its artifact is external | Canonical artifact name is `Change Review Proposal`; it is never a DataHub MCP | Verified ambiguity; Inference resolution |
| CR13 | Phase 0.5 uses both `Repair Proposal` and repair recommendations | Both describe advisory, non-executable actions | Canonical term and artifact name is `Repair Recommendation` | Inference |
| CR14 | `Current Metadata Snapshot`, `Current Graph`, and `Current Graph View` are used near-interchangeably | Phase 0.5 defines snapshot assembly and graph presentation separately | Metadata Snapshot is captured evidence; Current Graph is the graph derived from it; a Graph View is only a presentation of either graph | Inference |
| CR15 | `Future Graph`, `Future Graph View`, `future projection`, and “repaired future graph” can imply different behavior | Phase 0.5 projects only the source rename and does not execute repairs | `Graph Projection` is the operation; `Future Graph` is its temporary result; no Repaired Graph exists | Inference |
| CR16 | Verification could mean metadata completeness, repaired runtime validation, or pipeline execution | Phase 0.5 verifies artifacts/invariants and performs no external repair | `Verification` checks evidence, counts, invariants, and artifact completeness only | Inference |
| CR17 | The proposed name is sometimes described as Verified because Phase 0.4 froze it | It is verified as a planning decision but not as current DataHub metadata | Classify `order_amount` as Inference/Proposal; classify current `order_total` and Number type as Verified | Verified distinction; Inference rule |
| CR18 | Interface research lists many APIs, but Phase 0.5 requires only two at runtime | Phase 0.3 operation matrix and Phase 0.5 interface boundary agree | M03 uses Python SDK for dataset/schema/lineage/governance/bulk/document reads and GraphQL for BI/pipeline/product/structured-property reads; all others are forbidden at runtime | Verified decisions |
| CR19 | DataHub server, CLI, and SDK versions differ | Server is `v1.5.0.6`; CLI is `1.6.0.15`; SDK v2 warns it is experimental | Capability and baseline checks are mandatory; implementation never silently adapts the canonical scenario | Verified risk; Inference rule |
| CR20 | “Deterministic output” can conflict with timestamps and unordered service responses | Phase 0.5 requires deterministic behavior but includes retrieval timestamps | Determinism applies to semantic content, classification, normalized ordering, counts, and outcome for the same sealed snapshot/proposal; diagnostic timestamps are excluded | Inference |
| CR21 | The two dashboards named Order Entry Dashboard can be confused | Looker and Tableau each use that display name | Always prefix dashboard names with platform; Power BI remains `Power BI / datahub_order_entries` | Verified |
| CR22 | The source field path crosses job mappings, but the 20 count is datasets | Job and flow entities are not datasets | Jobs/flows appear in evidence paths but never increment field or dataset Blast Radius counts | Verified graph types; Inference rule |
| CR23 | `ORDER_TOTAL` in Power BI and `order_total` in Looker may be mistaken for one identity | They are separate downstream schema fields | Preserve platform-qualified field identity; names alone never establish identity | Verified descendants; Inference rule |
| CR24 | Assertions, contracts, and ML are mentioned as possible platform capabilities | Showcase instances are zero | They are excluded and cannot appear in the canonical Review Package except as an exclusion statement | Verified |

### 2.3 Canonical asset names

| Role | Canonical display name | Machine-identity rule | Classification |
|---|---|---|---|
| Source dataset | `PostgreSQL / order_entry_db / order_entry / orders` | Resolve the unique DataHub dataset URN at runtime; do not fabricate a URN | Verified hierarchy; Inference resolution |
| Source column | `PostgreSQL / order_entry_db / order_entry / orders / order_total` | Resolve from the source dataset's `schemaMetadata` | Verified |
| Proposed column | `order_amount` | External Proposal value only; no current URN | Inference |
| Snowflake source | `Snowflake / ORDER_ENTRY_DB / ORDER_ENTRY / ORDERS` | Use resolved DataHub URN | Verified |
| dbt model | `dbt / b2fd91.ORDER_ENTRY_DB.analytics.order_details` | `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)` | Verified |
| Analytical hub | `Snowflake / ORDER_ENTRY_DB / ANALYTICS / ORDER_DETAILS` | Use resolved DataHub URN | Verified |
| Looker dashboard | `Looker / Order Entry Dashboard` | Use resolved dashboard URN | Verified |
| Power BI dashboard | `Power BI / datahub_order_entries` | Use resolved dashboard URN | Verified |
| Tableau dashboard | `Tableau / Order Entry Dashboard` | Use resolved dashboard URN | Verified |

### 2.4 Canonical Blast Radius

| Dimension | Canonical rule | Frozen expected value | Classification |
|---|---|---:|---|
| Source inclusion | Source field and source dataset are excluded from downstream counts | 0 source items counted | Inference |
| Field count | Count unique downstream schema-field URNs reachable by verified fine-grained lineage | 25 | Verified baseline; Inference counting rule |
| Dataset count | Count unique downstream dataset URNs containing those 25 fields | 20 | Verified baseline; Inference counting rule |
| Maximum Field Depth | Count field-to-field lineage hops from source field to deepest descendant | 5 | Verified baseline; Inference counting rule |
| Jobs and flows | Include in evidence paths; exclude from 25/20 | Excluded | Inference |
| Charts and dashboards | Report as Confirmed Field Impact only with field evidence; otherwise Reachable Context | Three BI branches reachable | Verified reach; Inference status rule |
| Governance and products | Attach as context; exclude from 25/20 | Excluded | Inference |
| Duplicates | Deduplicate only by full URN, never by display name | No duplicate URN counted twice | Inference |

## 3. CANONICAL DEMONSTRATION

| Required field | Frozen value | Classification |
|---|---|---|
| Unique Demonstration ID | **`CHRONOS-DEMO-001`** | Inference |
| Canonical title | **The Revenue Column Rename Impact Review** | Verified Phase 0.4 decision |
| Business Problem | A local-looking source-column rename can affect verified pipeline mappings, analytical transformations, derived revenue metrics, BI datasets, governance context, and reachable dashboards | Verified graph basis; Inference problem framing |
| Source Dataset | `PostgreSQL / order_entry_db / order_entry / orders` | Verified |
| Source Column | `order_total` | Verified |
| Current Type | Number | Verified |
| Proposed Change | Rename `order_total` to `order_amount` before deployment | Inference |
| Direction | Downstream | Inference |
| Canonical Blast Radius | 25 unique downstream schema fields in 20 unique downstream datasets; maximum Field Depth 5 | Verified |
| Expected Outcome | Produce a verified Review Package and conclude **Hold for downstream compatibility review** | Inference |
| DataHub mutation | None | Inference |
| Out-of-Scope Changes | Any deletion, type change, masking, split, merge, table rename, primary-key/foreign-key change, assertion/contract/ML scenario, alternate field, or alternate proposed name | Verified Phase 0.4 exclusions; Inference boundary |

**Inference:** All implementation artifacts, run records, tests, and future documents must reference `CHRONOS-DEMO-001`; descriptive titles may accompany the identifier but may not replace it.

**Inference:** A request that does not exactly match `CHRONOS-DEMO-001` is Unsupported and must be rejected before DataHub retrieval.

## 4. SYSTEM INVARIANTS

| ID | Invariant | Classification |
|---|---|---|
| INV-001 | CHRONOS never mutates live or disposable DataHub metadata | Inference |
| INV-002 | CHRONOS never writes to PostgreSQL, S3, Spark, Snowflake, dbt, Looker, Power BI, or Tableau | Inference |
| INV-003 | CHRONOS never publishes a DataHub MCP or a direct Kafka event | Inference |
| INV-004 | M03 is the only subsystem allowed to call DataHub at runtime | Inference |
| INV-005 | M03 may use only the Python SDK and GraphQL operation mapping frozen in Section 7 of Phase 0.5 | Verified decision; Inference invariant |
| INV-006 | No subsystem reads DataHub MySQL, Kafka, or OpenSearch directly | Inference |
| INV-007 | The only accepted demonstration is `CHRONOS-DEMO-001` | Inference |
| INV-008 | The Proposal is external and never represented as current DataHub truth | Inference |
| INV-009 | Every displayed dependency is backed by captured verified metadata | Inference |
| INV-010 | CHRONOS never creates, guesses, or repairs a lineage edge | Inference |
| INV-011 | Unknown relationships are never presented as Verified or Inference facts | Inference |
| INV-012 | Reachable Context is never presented as Confirmed Field Impact without field-level evidence | Inference |
| INV-013 | Every user-visible statement has exactly one primary classification: Verified, Inference, or Unknown | Inference |
| INV-014 | Every Verified statement has immutable provenance in the Evidence Ledger | Inference |
| INV-015 | Captured Evidence is immutable for the life of a run | Inference |
| INV-016 | A sealed Metadata Snapshot is read-only | Inference |
| INV-017 | Current Graph is derived only from one sealed Metadata Snapshot | Inference |
| INV-018 | Current Graph and Future Graph never share mutable state | Inference |
| INV-019 | Future Graph is temporary and cannot become DataHub source truth | Inference |
| INV-020 | Future Graph differs from Current Graph only by the canonical Proposal and explicit derived annotations | Inference |
| INV-021 | No Repaired Graph is created; repairs remain recommendations | Inference |
| INV-022 | Blast Radius always uses the 25-field/20-dataset unique-URN definition in Section 2.4 | Inference |
| INV-023 | Source field and source dataset are excluded from downstream Blast Radius counts | Inference |
| INV-024 | Jobs, flows, charts, dashboards, products, governance entities, and documents do not increment the 25/20 counts | Inference |
| INV-025 | Platform-qualified URNs, not display names, determine identity and deduplication | Inference |
| INV-026 | A baseline other than 25 fields, 20 datasets, Number type, and Field Depth 5 blocks a successful run | Verified baseline; Inference invariant |
| INV-027 | Partial required evidence cannot produce a successful Verification or Completed state | Inference |
| INV-028 | Missing optional governance evidence is labeled Unknown and does not become fabricated context | Inference |
| INV-029 | The same Proposal and sealed Metadata Snapshot produce the same semantic results, classifications, normalized ordering, and outcome | Inference |
| INV-030 | Diagnostic timestamps and run identifiers are excluded from deterministic semantic equality | Inference |
| INV-031 | No credential or token value is stored in Evidence, artifacts, logs, or errors | Inference |
| INV-032 | The Change Review Proposal is never labeled as a DataHub Metadata Change Proposal | Inference |
| INV-033 | The successful final outcome is always **Hold for downstream compatibility review** | Inference |
| INV-034 | CHRONOS never autonomously approves, applies, or blocks an external system change | Inference |
| INV-035 | No cross-run metadata cache is part of canonical correctness | Inference |
| INV-036 | A failed, rejected, blocked, or cancelled run is terminal; retry creates a new run | Inference |
| INV-037 | The Review Package is not Complete unless every mandatory artifact and Evidence classification check passes | Inference |
| INV-038 | Assertions, contracts, ML assets, primary-key behavior, and financial-loss estimates never appear as supported demo capabilities | Verified absences; Inference invariant |

**Inference:** Any implementation behavior that violates an invariant is a release-blocking defect.

## 5. Terminology

| Term | Canonical meaning | Explicitly not | Classification |
|---|---|---|---|
| `CHRONOS-DEMO-001` | Unique identifier for the sole canonical demonstration | A family of scenarios | Inference |
| Proposal | External, immutable request to rename `order_total` to `order_amount` | Current metadata or DataHub MCP | Inference |
| Evidence | One captured metadata fact, relationship, response element, or frozen baseline fact with provenance and classification | An unsupported narrative claim | Inference |
| Evidence Ledger | Immutable run-scoped collection of Evidence and derivation references | An operational metadata store | Inference |
| Metadata Snapshot | Immutable, bounded set of captured Evidence used by one run | A historical DataHub snapshot feature or live graph | Inference |
| Current Graph | Graph representation derived solely from the sealed Metadata Snapshot | A direct view of mutable DataHub state after sealing | Inference |
| Graph Projection | The temporary operation that applies the Proposal to an isolated copy of relevant Current Graph state | A DataHub write or deployment | Inference |
| Future Graph | Temporary result of Graph Projection containing the proposed source rename and derived review annotations | A persisted or repaired DataHub graph | Inference |
| Graph View | User-visible presentation of Current Graph or Future Graph | A distinct source of truth | Inference |
| Field Depth | Number of verified fine-grained field-lineage hops from the source field | Dataset/job/chart path length | Inference |
| Path Length | Number of explicitly named relationship edges in a particular heterogeneous path | Field Depth unless the path contains only field edges | Inference |
| Blast Radius | 25 unique downstream schema-field URNs and their 20 unique containing dataset URNs for `CHRONOS-DEMO-001` | All heterogeneous descendants or business context | Verified baseline; Inference definition |
| Context Reach | Jobs, flows, BI branches, charts, dashboards, products, owners, terms, tags, domains, properties, and documents reachable from affected technical assets | Confirmed field consumption | Inference |
| Impact | Evidence-backed consequence or review obligation produced by comparing Current Graph with the Proposal/Future Graph | Guaranteed runtime failure | Inference |
| Impact Status | Exactly one of Confirmed Direct, Confirmed Derived, Reachable Context, or Unknown | An unlabeled affected item | Inference |
| Confirmed Direct | Downstream field connected by verified fine-grained lineage and preserving the source metric directly | A derived metric or name-only match | Inference |
| Confirmed Derived | Downstream field connected by verified fine-grained lineage whose semantic output differs, such as total revenue or average order value | A blind rename target | Inference |
| Reachable Context | Entity connected through verified dataset/job/chart/dashboard/governance relationships without proof of field consumption | Confirmed Field Impact | Inference |
| Unknown | Required truth is unavailable, incomplete, conflicting, or not verified | False, absent, low risk, or permission to infer | Inference |
| Verified | Directly supported by immutable Phase evidence or captured DataHub Evidence | Merely plausible | Inference |
| Inference | Derived decision, interpretation, recommendation, or projected consequence explicitly grounded in Verified Evidence | A hidden assumption or invented edge | Inference |
| Affected Field | Schema field with Confirmed Direct, Confirmed Derived, or Unknown field-impact status in the downstream field set | A field matched only by name | Inference |
| Affected Dataset | Dataset containing at least one Affected Field | Any reachable dataset without a field descendant | Inference |
| Affected Asset | Umbrella record for an Affected Field, Affected Dataset, or Reachable Context entity; it must carry Impact Status | Proof that the asset will fail | Inference |
| At-Risk Dependency | Verified dependency that may require compatibility work but is not proven broken in Future Graph | Broken Dependency | Inference |
| Broken Dependency | Verified dependency that cannot resolve in Future Graph because it still refers to the pre-change field identity/name | Any reachable or uncertain relation | Inference |
| Governance Context | Captured owners/gaps, tags, terms, domains, products, documents, structured properties, and unresolved references attached to affected assets | Runtime policy enforcement | Inference |
| Repair Recommendation | Non-executable, evidence-linked review action for a direct, derived, pipeline, model, BI, or governance obligation | Automatic repair or code change | Inference |
| Verification | Evaluation of invariants, frozen counts, provenance, classification, artifact completeness, and read-only execution | Pipeline execution, query correctness, or production validation | Inference |
| Change Review Proposal | External review artifact containing the Proposal, Evidence, impacts, Repair Recommendations, Verification, and Hold outcome | DataHub Metadata Change Proposal | Inference |
| Review Package | Complete ordered set of mandatory CHRONOS artifacts delivered to the reviewer | A partially generated report | Inference |
| Hold | Advisory conclusion that downstream compatibility review is required before an external change proceeds | Automated control-plane enforcement | Inference |
| Run | One forward-only lifecycle from Proposal Received to a terminal state using one sealed Metadata Snapshot | A resumable distributed workflow | Inference |
| Baseline Drift | Current captured metadata no longer matches the frozen source/type/25/20/depth expectations | Permission to update the scenario automatically | Inference |

**Inference:** Future specifications, artifact labels, tests, and user-visible content must reuse these terms exactly.

## 6. Architecture Boundaries

### 6.1 Global boundary rules

**Inference:** The twelve Phase 0.5 logical subsystem identifiers remain canonical.

**Inference:** Dependencies are one-directional; a downstream analysis/presentation subsystem may not be called by an upstream retrieval/snapshot subsystem.

**Inference:** No subsystem except M03 has a DataHub client, credential, endpoint, SDK, GraphQL, REST, Kafka, database, MCP Server, ACK, or Skills dependency.

### 6.2 Subsystem contracts

| ID and subsystem | Purpose | Inputs | Outputs | Responsibilities | Non-responsibilities | Allowed dependencies | Forbidden dependencies | Classification |
|---|---|---|---|---|---|---|---|---|
| M01 Session Coordinator | Enforce forward-only Run lifecycle | Start/cancel/status requests; Proposal | State transitions, run status, artifact references | Invoke subsystems in canonical order; stop on terminal failure | Metadata retrieval, graph analysis, artifact content decisions | M02–M12 | Direct DataHub, external stores, mutation APIs | Inference |
| M02 Proposal Boundary | Enforce `CHRONOS-DEMO-001` | Raw Proposal | Accepted canonical Proposal or Rejected result | Exact scenario validation before retrieval | Source lookup, metadata interpretation, scenario generalization | Canonical Demonstration registry; M11 for evidence of rejection | M03–M10 execution; DataHub; alternate scenarios | Inference |
| M03 DataHub Read Adapter | Own all authenticated DataHub reads | Bounded retrieval requests | Typed Evidence records and Retrieval Manifest | SDK/GraphQL mapping, pagination, errors, provenance, secret protection | Snapshot construction, projection, impact, recommendation, presentation, writes | Python SDK; GraphQL; GMS; M11 | REST/OpenAPI runtime calls, MCP/Kafka/writes, direct stores, M06–M12 analysis | Verified interface mapping; Inference boundary |
| M04 Source Resolver and Baseline Guard | Resolve exact source and detect drift | Accepted Proposal; M03 Evidence | Source Resolution Record; baseline status | Unique dataset/field/type resolution and frozen-baseline gate | Fetching outside M03, changing counts, adapting scenario | M03, M11 | M06–M12; direct DataHub; mutation | Inference |
| M05 Snapshot Assembler | Seal immutable run Evidence | M03 Evidence; M04 result | Metadata Snapshot | Identity normalization, completeness checks, snapshot sealing | Future changes, traversal conclusions, recommendations | M03, M04, M11 | Direct DataHub, M06–M12 feedback, mutation | Inference |
| M06 Future-State Projector | Produce isolated Future Graph | Proposal; Metadata Snapshot/Current Graph | Future Graph; explicit change set | Copy relevant graph, apply proposed source rename, annotate projection | DataHub write, automatic downstream repair, impact conclusion | M02, M05, M11 | M03 direct reads, M07–M12 feedback, external systems | Inference |
| M07 Impact Analysis | Produce canonical Blast Radius and path/status evidence | Current Graph; Future Graph; change set | Affected Field/Dataset registers, paths, Impact Report | 25/20/depth reconciliation; direct/derived/reachable/Unknown status | Governance joining, repair execution, invented lineage | M05, M06, M11 | Direct DataHub, M08–M12 feedback, mutation | Inference |
| M08 Governance Analysis | Attach governance and business context | Affected Assets; Metadata Snapshot | Governance Report | Owners/gaps, tags, terms, domains, products, documents, properties, unresolved refs | Creating governance metadata, resolving unknown identities, policy enforcement | M05, M07, M11 | Direct DataHub, M09–M12 feedback, mutation | Inference |
| M09 Repair Recommendation | Produce advisory compatibility actions | Impact Report; Governance Report; Future Graph difference | Repair Recommendations | Group direct remaps, derived review, pipeline/model/BI validation, manual review | Editing code/metadata, creating Repaired Graph, approval | M06, M07, M08, M11 | Direct DataHub, external source/BI systems, mutation | Inference |
| M10 Verification | Decide whether a Review Package may be completed | Proposal, manifest, snapshot/graphs, impacts, governance, recommendations, ledger | Verification Report and pass/fail | Invariant, baseline, provenance, classification, artifact, read-only checks | Repair execution, evidence creation, scenario changes | M02–M09, M11 | Direct DataHub except manifest evidence, M12 content mutation | Inference |
| M11 Evidence Ledger | Preserve immutable evidence/classification/provenance | Captured facts and derived statements from all modules | Evidence Ledger; classification coverage | Append immutable entries, provenance links, contradiction/Unknown recording | Metadata retrieval, analysis, recommendation, artifact presentation | Inputs from M02–M10 and M12 | Direct DataHub, mutation, rewriting prior Evidence | Inference |
| M12 Artifact Composer | Assemble and deliver Review Package | Mandatory artifacts; Verification Report; Evidence Ledger | Review Package and Hold outcome | Canonical ordering, labels, partial/failure presentation, export | Re-querying DataHub, altering evidence/counts, approval or mutation | M01, M02, M05–M11 | Direct DataHub, external system writes, agents/LLMs | Inference |

### 6.3 Boundary enforcement

**Inference:** A build that bypasses M03 for a DataHub read, allows feedback from presentation into Evidence, or permits any module to mutate a source is non-conformant.

**Inference:** Internal serialization, programming language, UI framework, and process topology may vary only if the logical boundaries and forbidden dependencies remain intact.

## 7. State Machine

### 7.1 States

| State | Entry conditions | Exit conditions | Produced artifacts | Failure conditions | Classification |
|---|---|---|---|---|---|
| S00 `IDLE` | No active Run | Start request creates new Run ID | Empty run record | Invalid coordinator state | Inference |
| S01 `READINESS_CHECK` | New Run exists | Required DataHub health/auth/capabilities pass | Readiness Result | Unavailable GMS, auth failure, required capability absent | Inference |
| S02 `PROPOSAL_RECEIVED` | Readiness passed and raw Proposal submitted | Raw Proposal is structurally present | Raw Proposal record | Missing submission | Inference |
| S03 `PROPOSAL_VALIDATED` | M02 confirms exact `CHRONOS-DEMO-001` values | Canonical Proposal sealed | Canonical Proposal | Unsupported value or scenario | Inference |
| S04 `SOURCE_RESOLVED` | Proposal valid; M03/M04 resolve unique source | Source field exists, type Number, baseline identity valid | Source Resolution Record | Zero/multiple matches, missing field, type mismatch, soft deletion | Inference |
| S05 `EVIDENCE_CAPTURED` | Source resolved; bounded retrieval completes | Required pages/categories complete or explicitly optional | Retrieval Manifest; raw Evidence entries | Required read/permission/page/schema failure | Inference |
| S06 `SNAPSHOT_SEALED` | Evidence complete enough for canonical analysis | Metadata Snapshot immutable and Current Graph derived | Metadata Snapshot; Current Graph | Identity conflict, incomplete required aspect, snapshot inconsistency | Inference |
| S07 `FUTURE_PROJECTED` | Snapshot sealed; Proposal available | Isolated Future Graph contains only canonical change and annotations | Future Graph; change set | Shared mutable state, duplicate projected field, unsupported mutation | Inference |
| S08 `IMPACT_ANALYZED` | Current/Future Graphs available | 25/20/depth-5 baseline reconciled; statuses assigned | Affected registers; Impact Report | Missing lineage, count/depth mismatch, unclassified affected item | Verified expected baseline; Inference state |
| S09 `GOVERNANCE_ANALYZED` | Impact artifacts complete | Governance Context and gaps attached or Unknown | Governance Report | Required context retrieval absent from snapshot; contradiction | Inference |
| S10 `RECOMMENDATIONS_PRODUCED` | Impact and governance complete | Every affected obligation has a Repair Recommendation or Unknown/manual-review status | Repair Recommendations | Unsupported automatic repair claim, missing evidence link | Inference |
| S11 `VERIFICATION_COMPLETED` | Mandatory analysis artifacts complete | All release-blocking checks pass | Verification Report | Any invariant, baseline, evidence, classification, or read-only check fails | Inference |
| S12 `REVIEW_PACKAGE_READY` | Verification passed | A01–A14-equivalent mandatory artifacts assembled and labeled | Review Package; Change Review Proposal; Summary; Hold outcome | Missing artifact, inconsistent count, composition failure | Inference |
| S13 `COMPLETED` | Review Package delivered to reviewer | Run closed and immutable | Final Run Record | Delivery acknowledgement failure | Inference |
| T01 `REJECTED` | Proposal validation fails | Terminal | Rejection Report | None; state is terminal | Inference |
| T02 `BLOCKED` | Environment, permission, baseline, or required evidence prevents analysis | Terminal | Blocking Report and completed diagnostics | None; state is terminal | Inference |
| T03 `FAILED` | Internal projection/analysis/verification/composition fails | Terminal | Failure Report and safe completed artifacts | None; state is terminal | Inference |
| T04 `CANCELLED` | User cancels any non-terminal active state | Terminal | Cancellation Record | None; state is terminal | Inference |

### 7.2 Transition rules

**Inference:** The successful path is strictly `S00 → S01 → S02 → S03 → S04 → S05 → S06 → S07 → S08 → S09 → S10 → S11 → S12 → S13`.

**Inference:** S02 or S03 may transition only to T01 for proposal rejection.

**Inference:** S01, S04, S05, or S06 may transition to T02 when environment or evidence blocks safe analysis.

**Inference:** S07 through S12 may transition to T03 for internal or verification failure.

**Inference:** Any non-terminal state may transition to T04.

**Inference:** No terminal state resumes, and no successful state transition moves backward.

**Inference:** Artifact composition may be retried inside S12 from intact verified artifacts; it may not return to metadata retrieval or analysis.

**Inference:** A rerun always starts at S00 with a new Run ID and captures new Evidence.

## 8. Risk Review

### 8.1 Rating scale

| Rating | Likelihood meaning | Impact meaning | Classification |
|---|---|---|---|
| Low | Not observed and unlikely in canonical local run | Does not prevent a trustworthy Review Package | Inference |
| Medium | Plausible or dependent on environment state | Causes partial output, manual review, or demo disruption | Inference |
| High | Already observed, structurally likely, or version-sensitive | Blocks trustworthy completion or violates invariants | Inference |

### 8.2 Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Residual risk | Classification |
|---|---|---|---|---|---|---|
| R01 | Missing required fine-grained lineage | Low | High | Baseline guard, 25/20/depth verification, fail Blocked | Low | Verified current completeness; Inference rating |
| R02 | Partial lineage page or incomplete retrieval | Medium | High | Retrieval Manifest, page completion checks, no partial success | Low | Inference |
| R03 | Disconnected graph due to index/reference issue | Medium | High | Seal only reconciled snapshot; show last verified boundary; Blocked | Medium | Verified possible gaps; Inference rating |
| R04 | Missing ownership | High | Medium | Display verified owner gaps; do not block technical impact | High | Verified current gaps |
| R05 | Missing glossary/tag/domain metadata | Medium | Medium | Label Unknown/absent; continue unless required baseline fact conflicts | Medium | Verified uneven governance; Inference |
| R06 | Unresolved owner/tag/term references | High | Medium | Preserve raw URN and unresolved status; never guess | High | Verified |
| R07 | Power BI unresolved dataset references | High | Medium | Keep as Reachable Context/integrity gap; exclude from confirmed counts | High | Verified |
| R08 | Chart-field consumption ambiguity | High | Medium | Separate Confirmed Field Impact from Reachable Context | Medium | Verified |
| R09 | Derived-field semantic ambiguity | Medium | High | Confirm dependency, mark semantic meaning Unknown when absent, require manual review | Medium | Inference |
| R10 | Dataset/field identity collision by name | Medium | High | Resolve/deduplicate by full URN and platform-qualified identity | Low | Inference |
| R11 | Schema type ambiguity or drift | Low | High | Require Number type; Blocked on mismatch | Low | Verified baseline; Inference |
| R12 | Blast-radius counting divergence | Medium | High | Enforce Section 2.4 unique-URN definition and fixed acceptance fixtures | Low | Inference |
| R13 | DataHub server/CLI/SDK version mismatch | High | High | Pin tested versions, capability contract checks, isolate M03 | Medium | Verified |
| R14 | SDK v2 experimental change | High | Medium | Adapter isolation and contract tests; no silent fallback | Medium | Verified |
| R15 | Graph index staleness | Medium | High | Timestamp/manifest evidence, snapshot reconciliation, fail rather than combine reads | Medium | Verified architecture; Inference |
| R16 | Authentication or permission failure | Medium | High | Fail closed, sanitize error, least-required read scope, new run after correction | Low | Inference |
| R17 | Secret leakage | Low | High | M03-only credential handling; artifact/log redaction acceptance test | Low | Inference |
| R18 | Large or unexpectedly expanded graph | Low | Medium | Bounded canonical scope, pagination, count guard; no generalization | Low | Verified current scale; Inference |
| R19 | Mid-run DataHub changes | Low | High | One sealed snapshot; version conflict detection; rerun | Low | Inference |
| R20 | Current/Future mutable-state aliasing | Low | High | Isolation invariant and verification test | Low | Inference |
| R21 | Artifact mistaken for DataHub MCP | Medium | High | Rename to Change Review Proposal; explicit external/read-only label | Low | Inference |
| R22 | Repair Recommendation treated as executable repair | Medium | High | Advisory labeling; no external write dependencies; invariant test | Low | Inference |
| R23 | Partial report presented as success | Medium | High | Verification gate and terminal Blocked/Failed states | Low | Inference |
| R24 | Non-deterministic ordering changes output | Medium | Medium | Normalize by canonical identity/path/status; exclude timestamps from semantic equality | Low | Inference |
| R25 | Five-minute demo overload | Medium | High | Fixed state/artifact order and executive-first summary | Medium | Inference |
| R26 | Financial or business-severity overclaim | Medium | Medium | No monetary/SLA claims; preserve Unknown | Low | Unknown source evidence; Inference |
| R27 | Scope expansion during implementation | Medium | High | M02 exact boundary, demonstration ID, checklist, change-control requirement | Low | Inference |
| R28 | Technology choice breaks logical boundaries | Medium | High | Architecture conformance review independent of language/framework | Low | Inference |
| R29 | Official datapack drift before demo | Medium | High | Baseline guard; fail explicitly; do not auto-update canonical values | Medium | Unknown future state; Inference |
| R30 | Missing structured-property assignments | Medium | Low | Show only verified values; mark missing values Unknown | Medium | Unknown exact assignments; Inference |

## 9. Acceptance Checklist

**Inference:** Every checkbox is binary and release-blocking; an unchecked item means CHRONOS is not complete.

### Canonical demonstration

- [ ] **Inference:** `CHRONOS-DEMO-001` is the only accepted Demonstration ID.
- [ ] **Inference:** The accepted Proposal is exactly PostgreSQL `orders.order_total` → `order_amount`.
- [ ] **Verified baseline / Inference test:** The source field resolves uniquely and its current type is Number.
- [ ] **Inference:** Every non-canonical source, field, name, direction, or change type is rejected before metadata retrieval.
- [ ] **Inference:** The successful outcome is exactly **Hold for downstream compatibility review**.

### Read-only safety and boundaries

- [ ] **Inference:** No DataHub mutation occurs.
- [ ] **Inference:** No source, pipeline, warehouse, transformation, or BI mutation occurs.
- [ ] **Inference:** No MCP, direct Kafka event, REST/OpenAPI runtime write, or direct MySQL/OpenSearch operation occurs.
- [ ] **Inference:** M03 is the only subsystem with DataHub connectivity and credentials.
- [ ] **Inference:** M03 uses only the approved Python SDK/GraphQL operation mapping.
- [ ] **Inference:** Tokens and secrets never appear in logs, errors, Evidence, or artifacts.
- [ ] **Inference:** Architecture dependencies satisfy every allowed/forbidden boundary in Section 6.

### Evidence and graph integrity

- [ ] **Inference:** Every displayed dependency is backed by captured verified metadata.
- [ ] **Inference:** No lineage edge is inferred, generated, or repaired.
- [ ] **Inference:** Every Verified statement has provenance in the Evidence Ledger.
- [ ] **Inference:** Every user-visible statement is classified Verified, Inference, or Unknown.
- [ ] **Inference:** Unknown evidence is never promoted to fact.
- [ ] **Inference:** Platform-qualified URNs determine identity and deduplication.
- [ ] **Inference:** Captured Evidence cannot be modified after recording.
- [ ] **Inference:** Metadata Snapshot cannot be modified after sealing.
- [ ] **Inference:** Current Graph is derived from exactly one Metadata Snapshot.
- [ ] **Inference:** Current Graph and Future Graph share no mutable state.
- [ ] **Inference:** Future Graph is temporary and never persisted to DataHub.

### Blast Radius and impact

- [ ] **Verified baseline / Inference test:** Exactly 25 unique downstream schema-field URNs are reported.
- [ ] **Verified baseline / Inference test:** Exactly 20 unique downstream containing dataset URNs are reported.
- [ ] **Verified baseline / Inference test:** Maximum Field Depth is exactly 5.
- [ ] **Inference:** Source field and source dataset are excluded from downstream counts.
- [ ] **Inference:** Jobs, flows, charts, dashboards, products, governance entities, and documents are excluded from the 25/20 counts.
- [ ] **Inference:** Jobs and flows still appear in applicable evidence paths.
- [ ] **Inference:** Every affected item has exactly one Impact Status.
- [ ] **Inference:** Direct descendants are separated from derived descendants.
- [ ] **Inference:** Tableau `TOTAL_REVENUE` and `AVERAGE_ORDER_VALUE`, Power BI `ORDER_TOTAL`, Looker `order_total`, and order-history context appear with provenance.
- [ ] **Inference:** Looker, Power BI, and Tableau branches are represented.
- [ ] **Inference:** Reachable dashboards/charts are not called confirmed field consumers without field evidence.

### Governance and recommendations

- [ ] **Inference:** Governance Context includes available owners/gaps, tags, terms, domains, products, documents, and structured properties.
- [ ] **Inference:** Unresolved owner/tag/term/Power BI references remain visibly unresolved.
- [ ] **Inference:** Returns & Refunds, Promotions Performance, and Order Entry Analytics context is included where verified affected assets participate.
- [ ] **Inference:** Every At-Risk or Broken Dependency has an Evidence link.
- [ ] **Inference:** Repair Recommendations are non-executable and classified as Inference.
- [ ] **Inference:** Direct mappings receive rename/remap review actions.
- [ ] **Inference:** Derived or semantically Unknown fields receive manual-review actions, not blind rename instructions.
- [ ] **Inference:** No Repaired Graph is created.

### Lifecycle, artifacts, and failures

- [ ] **Inference:** The state machine follows only transitions allowed by Section 7.
- [ ] **Inference:** Failed, Blocked, Rejected, and Cancelled Runs cannot resume.
- [ ] **Inference:** Retry creates a new Run and new Evidence capture.
- [ ] **Inference:** Baseline drift blocks successful completion.
- [ ] **Inference:** Missing required lineage blocks successful completion.
- [ ] **Inference:** Missing optional governance is labeled Unknown without fabricating content.
- [ ] **Inference:** Partial data cannot produce a passing Verification Report.
- [ ] **Inference:** Every mandatory Review Package artifact is present.
- [ ] **Inference:** Change Review Proposal is clearly labeled external and not a DataHub MCP.
- [ ] **Inference:** Verification covers invariants, 25/20/depth, provenance, classification, artifact completeness, and read-only behavior.
- [ ] **Inference:** Semantic output is deterministic for the same Proposal and sealed Metadata Snapshot.
- [ ] **Inference:** The complete narrated successful path is no longer than five minutes.
- [ ] **Inference:** A non-technical rehearsal reviewer can identify the change, impact, and Hold outcome without additional technical explanation.

### Scope exclusions

- [ ] **Inference:** No alternate change scenario is implemented.
- [ ] **Verified absence / Inference test:** Assertions, contracts, ML, and primary-key behavior are not presented as supported.
- [ ] **Inference:** No agent, LLM, RAG, ACK, MCP Server, or Skill is required or invoked.
- [ ] **Inference:** No continuous monitoring, workflow engine, collaboration system, notification system, or production deployment capability is included.
- [ ] **Inference:** No financial-loss, SLA, or incident-severity value is invented.

## 10. Implementation Readiness

### 10.1 Board decision

**Inference:** **Yes—implementation may begin for `CHRONOS-DEMO-001`.**

**Inference:** There are no blocking product, scenario, data-flow, module-boundary, state-machine, interface, artifact, or acceptance ambiguities after applying this review.

**Inference:** Approval is limited to the behavior and boundaries in Phases 0.5 and this document; it is not approval for any excluded capability.

### 10.2 Assumptions implementation may rely on

1. **Verified:** The official showcase graph contains PostgreSQL `orders.order_total` with DataHub type Number.
2. **Verified:** The frozen field-level baseline is 25 downstream fields, 20 downstream datasets, and maximum Field Depth 5.
3. **Verified:** The path evidence includes PostgreSQL, Spark export, S3, Spark import, Snowflake, dbt, analytical Snowflake, and three BI branches.
4. **Verified:** The local DataHub GMS and GraphQL endpoints described in Phase 0.1 are available for development.
5. **Inference:** A valid read credential will be supplied outside artifacts and logs.
6. **Inference:** The implementation operates on one Run and one sealed Metadata Snapshot at a time.
7. **Inference:** The official showcase graph is not intentionally mutated during a Run.
8. **Inference:** Python SDK and GraphQL access are isolated behind M03.
9. **Inference:** Missing optional governance data may be represented as Unknown.
10. **Inference:** Missing required source/schema/lineage evidence blocks completion.
11. **Inference:** Runtime URNs not frozen in the planning documents are resolved from DataHub and never invented.
12. **Inference:** Artifact serialization and presentation technology may vary without changing logical contents or terms.
13. **Inference:** Active-session artifact availability is sufficient; durable operational persistence is not required.
14. **Inference:** Human review, not CHRONOS, decides whether external remediation is adequate.

### 10.3 Conditions before declaring implementation complete

**Inference:** The implementation must pass every checkbox in Section 9.

**Inference:** It must demonstrate all successful and induced-failure acceptance behavior from Phase 0.5 AC01–AC37.

**Inference:** It must pass an architecture conformance review showing that actual dependencies match Section 6.

**Inference:** It must pass a timed rehearsal using the unchanged official showcase graph.

## 11. Remaining Unknowns

| Unknown | Why it remains | Frozen implementation behavior | Blocking? | Classification |
|---|---|---|---|---|
| Exact field consumption of each chart | Current metadata proves dataset/chart reach, not every field binding | Use Reachable Context unless field evidence exists | No | Unknown |
| Complete executable transformation expressions | Fine-grained mappings do not guarantee expression text | Confirm dependency; mark semantics Unknown; recommend review | No | Unknown |
| Exact value of every structured-property assignment | Prior report did not enumerate every value | Show only captured values; absent values remain Unknown | No | Unknown |
| Intent behind unresolved Power BI, owner, tag, and term references | Datapack intent is undocumented | Preserve raw unresolved references | No | Unknown |
| Stable Python SDK version at implementation time | Installed v2 surface is experimental | Pin and contract-test chosen compatible version inside M03 | No | Unknown |
| Artifact serialization and visual technology | Technology selection is intentionally outside logical review | Implement A01–A14-equivalent logical contracts | No | Unknown |
| Numeric timeout/retry configuration | No target-machine benchmark exists | Configuration may be tuned without changing failure semantics | No | Unknown |
| Whether the judging datapack will drift | Future environment is unavailable | Baseline guard blocks and reports drift | No for implementation; may block a future Run | Unknown |
| Exact PostgreSQL source dataset URN string | Immutable reports verify hierarchy/logical identity but do not freeze the full URN | Resolve uniquely at runtime and record it in Evidence | No | Unknown |
| Formal financial/SLA criticality | Not present in the graph | Do not display or estimate it | No | Unknown |

**Inference:** No Remaining Unknown permits automatic adaptation of `CHRONOS-DEMO-001`, the Blast Radius, system invariants, final Hold outcome, or subsystem boundaries.

## 12. Final Recommendation

**Inference:** **APPROVED FOR IMPLEMENTATION WITH FROZEN SCOPE.**

**Inference:** The implementation team should treat `CHRONOS-DEMO-001`, INV-001 through INV-038, the Section 5 glossary, the Section 6 subsystem boundaries, the Section 7 state machine, and the Section 9 checklist as normative.

**Inference:** Phase 0.5 remains the detailed system specification; this review is the controlling interpretation when Phase 0.1–0.5 wording differs.

**Inference:** Any request to add a scenario, mutate DataHub, introduce an agent, change Blast Radius counting, alter the final outcome, or weaken evidence classification requires reopening the design review and issuing a new demonstration identifier.

**Inference:** Implementation should begin with the Phase 0.5 Phase 1 contract/baseline milestone and may not be declared complete until every binary acceptance item passes.
