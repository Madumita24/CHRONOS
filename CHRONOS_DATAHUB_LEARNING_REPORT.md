# CHRONOS — DataHub Environment Learning Report

**Phase:** Knowledge acquisition only<br>
**Inspection date:** 2026-07-25 (America/Phoenix)<br>
**Scope:** Local DataHub Community Edition quickstart and the official `showcase-ecommerce` datapack<br>
**Explicitly out of scope:** CHRONOS design, application code, frontend work, backend work, and production architecture

## 1. Evidence policy

This report uses the following labels:

- **Verified locally** — observed directly in this installation through health checks, container inspection, authenticated APIs, or read-only queries.
- **Verified in official documentation** — supported by a linked DataHub documentation page or official DataHub repository.
- **Inference** — a conclusion drawn from verified evidence; the reasoning is stated.
- **Unknown** — not established by this investigation.

No synthetic metadata was created. All business-facing sample metadata came from DataHub's official `showcase-ecommerce` datapack.

## 2. Outcome

**Verified locally:** DataHub is running successfully in Docker Compose. The UI, Generalized Metadata Service (GMS), GraphQL API, OpenAPI UI, MySQL, Kafka, and OpenSearch all respond. The official ecommerce showcase is committed to the primary metadata store.

| Item | Verified result |
|---|---|
| DataHub CLI and Python SDK | `acryl-datahub 1.6.0.15` in Python `3.10.19` virtual environment |
| DataHub server images | `v1.5.0.6` |
| Docker Desktop | `4.49.0` |
| Docker Engine | `28.5.1` |
| Docker Compose | `v2.40.3-desktop.1` |
| MySQL | `8.2.0` |
| OpenSearch | `2.19.3` |
| Kafka image | Confluent Platform Kafka `8.0.0` |
| UI | [http://localhost:9002](http://localhost:9002), HTTP 200 |
| GMS health | [http://localhost:8080/health](http://localhost:8080/health), HTTP 200 |
| GMS GraphQL | `http://localhost:8080/api/graphql`, authenticated query succeeded |
| OpenAPI UI | [http://localhost:8080/openapi/swagger-ui/index.html](http://localhost:8080/openapi/swagger-ui/index.html), HTTP 200 |
| OpenSearch | [http://localhost:9200](http://localhost:9200), HTTP response identified OpenSearch `2.19.3` |
| Official datapack | Loaded; 3 official files, 3,571 accepted metadata events |

**Important version finding:** the current `1.6.0.15` CLI's unpinned quickstart selected the coordinated server plan `v1.5.0.6`. The current official quickstart documentation also explains how to pin a server release with `--version`. This report therefore distinguishes installed CLI behavior from installed server behavior. See the [official quickstart version controls](https://docs.datahub.com/docs/quickstart#upgrade-datahub).

## 3. Installation

### 3.1 Official prerequisites

DataHub's [official quickstart](https://docs.datahub.com/docs/quickstart#prerequisites) requires Docker with Compose v2 and Python 3.10 or newer. It reports a tested Docker allocation of 2 CPUs, 8 GB RAM, 2 GB swap, and 13 GB disk.

**Verified locally:** Docker Desktop, Engine, and Compose meet the software requirements. Python 3.10.19 is used for DataHub. The complete Docker memory allocation could not be read with the available Windows permissions, so conformance to the documented 8 GB/2 GB allocation is **unknown**. Successful operation does not prove that allocation.

### 3.2 Python environment and CLI

The active development environment is:

```powershell
C:\Users\kmadu\anaconda3\envs\llmrouter\python.exe -m venv .venv-datahub-310
.\.venv-datahub-310\Scripts\python.exe -m pip install --upgrade pip wheel setuptools
.\.venv-datahub-310\Scripts\python.exe -m pip install acryl-datahub==1.6.0.15
.\.venv-datahub-310\Scripts\datahub.exe version
```

Command explanations:

1. `python.exe -m venv .venv-datahub-310` creates an isolated Python 3.10 environment so DataHub packages do not modify the system Python.
2. `python.exe -m pip install --upgrade pip wheel setuptools` updates the packaging tools. This is part of the official pip installation sequence.
3. `python.exe -m pip install acryl-datahub==1.6.0.15` installs the DataHub CLI and Python SDK. The exact version is pinned so this investigation is reproducible.
4. `datahub.exe version` verifies that the CLI is importable and reports its version.

The [official quickstart installation commands](https://docs.datahub.com/docs/quickstart#install-the-datahub-cli) use the same package, normally without a version pin.

**Verified locally:** an initial Python 3.13 environment produced the CLI warning that versions above 3.11 are not actively tested. It was replaced by Python 3.10.19 and removed. This was an environment correction, not a DataHub runtime change.

### 3.3 Start DataHub

```powershell
.\.venv-datahub-310\Scripts\datahub.exe docker quickstart
```

This official command downloads DataHub's quickstart Compose file, pulls coordinated container images, creates the network and persistent volumes, runs one-time setup/migration work, and starts the services. The official description is in [Start DataHub](https://docs.datahub.com/docs/quickstart#start-datahub).

**Verified locally:**

- Compose file: `C:\Users\kmadu\.datahub\quickstart\docker-compose.yml`
- Version mapping: `C:\Users\kmadu\.datahub\quickstart\quickstart_version_mapping.yaml`
- Selected plan: DataHub `v1.5.0.6`, MySQL tag `8.2`
- Persistent volumes: `datahub_mysqldata`, `datahub_osdata`, and `datahub_broker`

The CLI process returned a non-zero exit after startup because the Windows `cp1252` console could not encode the CLI's Unicode checkmark. The official `datahub docker check` later reached its internal “No issues detected” result and then hit the same output-encoding exception. Container and HTTP health checks independently proved that startup succeeded. This is a console-output defect, not a server failure.

### 3.4 Authenticate the CLI

```powershell
.\.venv-datahub-310\Scripts\datahub.exe init --username datahub --password datahub --force
```

This exchanges the quickstart credentials for a personal access token and writes the local client configuration to `C:\Users\kmadu\.datahubenv`. `--force` makes the local configuration update non-interactive. The token is intentionally not reproduced in this report.

The official quickstart uses the same initialization flow at [Load Sample Data](https://docs.datahub.com/docs/quickstart#load-sample-data).

### 3.5 Normal local lifecycle

```powershell
# Start or update the quickstart
.\.venv-datahub-310\Scripts\datahub.exe docker quickstart

# Stop containers without deleting their persistent volumes
.\.venv-datahub-310\Scripts\datahub.exe docker quickstart --stop

# Back up the quickstart's MySQL state
.\.venv-datahub-310\Scripts\datahub.exe docker quickstart --backup
```

The official lifecycle and backup limitations are documented in [Managing Your Local Instance](https://docs.datahub.com/docs/quickstart#managing-your-local-instance). The destructive `datahub docker nuke` command was **not** run.

## 4. Installed services

### 4.1 Runtime inventory

| Component | Local container/image | URL or port | State | What it does |
|---|---|---|---|---|
| Frontend | `datahub-frontend-react:v1.5.0.6` | [http://localhost:9002](http://localhost:9002) | Healthy | Serves the React web UI and handles browser-facing authentication/proxy behavior. |
| Metadata Service / GMS | `datahub-gms:v1.5.0.6` | `http://localhost:8080` | Healthy | Validates metadata writes, serves entity/aspect reads, search, graph, authorization, REST, OpenAPI, and GraphQL. |
| DataHub Actions | `datahub-actions:v1.5.0.6-slim` | No host port | Running | Consumes metadata changes and runs event-driven actions. In this load it processed documentation propagation events. |
| System update | `datahub-upgrade:v1.5.0.6` | No host port | Exited `0` | One-time bootstrap/migration/index setup. An exited-success state is expected. |
| Kafka | `confluentinc/cp-kafka:8.0.0` | `localhost:9092` | Healthy | Durable metadata-change/event stream used for asynchronous processing and subscribers. |
| MySQL | `mysql:8.2` | `localhost:3306` | Healthy | Primary store for versioned metadata aspects and operational DataHub records. |
| OpenSearch | `opensearchproject/opensearch:2.19.3` | [http://localhost:9200](http://localhost:9200) | Healthy | Secondary search indexes, relationship/graph index, and time-series indexes in this quickstart. |

The high-level roles agree with DataHub's [component documentation](https://docs.datahub.com/docs/components), [serving-tier documentation](https://docs.datahub.com/docs/architecture/metadata-serving), and [Docker container architecture](https://docs.datahub.com/docs/architecture/docker-containers).

### 4.2 URLs and API endpoints

| Surface | Endpoint | Verification and access note |
|---|---|---|
| UI | [http://localhost:9002](http://localhost:9002) | HTTP 200. Official quickstart credentials are `datahub` / `datahub`; these defaults are development-only. |
| Backend / GMS base | `http://localhost:8080` | This is the backend service, not a separate component from the Metadata Service. |
| Health | [http://localhost:8080/health](http://localhost:8080/health) | HTTP 200 with `{}`. |
| GraphQL | `http://localhost:8080/api/graphql` | Authenticated CLI query succeeded with a PAT. |
| Browser-proxied GraphQL | `http://localhost:9002/api/graphql` | Returned 401 with only a PAT; it is intended for the frontend's authenticated browser session. |
| OpenAPI/REST explorer | [http://localhost:8080/openapi/swagger-ui/index.html](http://localhost:8080/openapi/swagger-ui/index.html) | HTTP 200. |
| OpenSearch API | [http://localhost:9200](http://localhost:9200) | HTTP response identified cluster `docker-cluster`, OpenSearch `2.19.3`. |
| Kafka broker | `localhost:9092` | Broker health was healthy and topic listing succeeded. It is not an HTTP URL. |
| MySQL | `localhost:3306`, database `datahub` | Read-only SQL inspection succeeded; server reported `8.2.0`. It is not an HTTP URL. |

DataHub's [GraphQL getting-started guide](https://docs.datahub.com/docs/api/graphql/getting-started/) documents `/api/graphql`, token authentication, and checking the GraphQL response body for errors even when HTTP status is 200.

### 4.3 Graph Service clarification

**Verified locally:** there is no standalone “Graph Service” container. GMS is configured with `GRAPH_SERVICE_IMPL=elasticsearch`; therefore graph traversal is a logical GMS capability backed by the OpenSearch `graph_service_v1` index. At the final inspection checkpoint that index held 2,343 relationship documents.

This is distinct from a dedicated graph database. The [serving-tier documentation](https://docs.datahub.com/docs/architecture/metadata-serving) describes GMS routing relationship queries to the graph index.

### 4.4 Kafka topics

**Verified locally:** the broker exposes:

- `MetadataChangeProposal_v1`
- `MetadataChangeEvent_v4`
- `MetadataChangeLog_Versioned_v1`
- `MetadataChangeLog_Timeseries_v1`
- `FailedMetadataChangeProposal_v1`
- `PlatformEvent_v1`
- `DataHubUsageEvent_v1`
- `DataHubUpgradeHistory_v1`
- Kafka's `__consumer_offsets`

The [APIs overview](https://docs.datahub.com/docs/api/datahub-apis) explains the normal asynchronous write path: GMS validates a Metadata Change Proposal, publishes accepted changes, and consumers update derived stores. Publishing directly to Kafka bypasses GMS authentication and validation and should therefore be treated as a lower-level integration path.

### 4.5 Persistence

**Verified locally:**

- MySQL data persists in `datahub_mysqldata`.
- OpenSearch data persists in `datahub_osdata`.
- Kafka data persists in `datahub_broker`.
- The MySQL table `metadata_aspect_v2` stores the current and versioned entity aspects. Its identifying key is `(urn, aspect, version)`; metadata and system metadata are serialized in columns.

**Interpretation grounded in official architecture:** MySQL is the authoritative store for versioned aspects in this quickstart. OpenSearch is a derived read model for full-text/secondary search and graph traversal. Kafka carries the change log that keeps the derived models and subscribers updated. See [Serving Tier](https://docs.datahub.com/docs/architecture/metadata-serving).

## 5. Official showcase datapack

### 5.1 Official command

```powershell
.\.venv-datahub-310\Scripts\datahub.exe datapack load showcase-ecommerce
```

DataHub's [quickstart](https://docs.datahub.com/docs/quickstart#load-sample-data) identifies this as the official showcase: approximately 1,050 entities across Snowflake, Looker, Power BI, and Tableau, including lineage, governance, glossary terms, domains, and data products. The documentation marks the datapack command experimental.

### 5.2 Windows defect and verified workaround

**Verified locally:** on Windows, CLI `1.6.0.15` downloaded the official pack but interpreted the drive prefix in its temporary `C:\...` file path as a filesystem scheme named `c`. It failed with:

```text
KeyError: Did not find a registered class for c
```

The failed attempt emitted no metadata.

To preserve the official command and official data without manufacturing metadata, the datapack command was run from a temporary Linux Python container:

```powershell
docker run -d --name datahub-datapack-cli python:3.11-slim sleep infinity
docker exec datahub-datapack-cli python -m pip install acryl-datahub==1.6.0.15
docker exec datahub-datapack-cli datahub init --host http://host.docker.internal:8080 --username datahub --password datahub --force
docker exec datahub-datapack-cli datahub datapack load showcase-ecommerce
docker stop datahub-datapack-cli
docker rm datahub-datapack-cli
```

Command explanations:

1. `docker run` starts an isolated, temporary Linux Python environment. It is not a DataHub server component.
2. `docker exec ... pip install` installs the same pinned official DataHub CLI inside that environment.
3. `docker exec ... datahub init` points the temporary CLI at the already-running host GMS through Docker Desktop's `host.docker.internal` address.
4. `docker exec ... datapack load` executes the unchanged official datapack command.
5. `docker stop` and `docker rm` remove the temporary helper after successful ingestion. The official Python base image may remain in Docker's image cache, but no helper container remains.

### 5.3 Source and load evidence

**Verified locally:** the command downloaded the official manifest and payloads from the `datahub-project/static-assets` repository:

- `showcase-ecommerce/index.json`
- `01-definitions.json`
- `02-data.json`
- `03-context.json`

The loader completed with exit code `0`.

| Payload result | Count |
|---|---:|
| Definition events accepted | 10 |
| Main data proposals in file | 3,809 |
| Proposals filtered as incompatible with the older server schema | 248 |
| Main data proposals accepted | 3,561 |
| Total accepted events | 3,571 |

**Verified reason for filtering:** the server is `v1.5.0.6`, while the loader/datapack is `1.6.0.15`. The loader explicitly filtered aspects unknown to the server registry. Major filtered categories included `entityInferenceMetadata`, `lineageFeatures`, `usageFeatures`, `storageFeatures`, and `assertionsSummary`.

**Inference:** core showcase metadata loaded successfully, but some 1.6-era derived/enrichment aspects are absent. This is version-skew degradation, not synthetic substitution.

## 6. Loaded-environment inspection

### 6.1 Counting method

Two views were inspected:

1. **Primary-store count:** distinct current URNs in MySQL where aspect `version=0`. This is the authoritative committed-state count for this quickstart.
2. **Search-visible count:** GraphQL/OpenSearch results. These are eventually consistent derived indexes.

This distinction follows the [official serving architecture](https://docs.datahub.com/docs/architecture/metadata-serving).

### 6.2 Primary-store totals

**Verified locally after datapack completion:**

| Measure | Count |
|---|---:|
| Distinct current entity URNs, all technical and business types | **1,315** |
| Current aspect rows | **4,211** |
| Distinct current aspect names | **94** |
| Registered entity types | **63** |

The 1,315 total includes DataHub's system entities, policies, roles, platforms, schema-field entities, upgrade records, and the showcase. It should not be compared directly to the documentation's approximate 1,050 showcase count, which describes the datapack rather than the fully bootstrapped local database.

### 6.3 Requested entity summary

| Requested category | Primary-store count | Notes |
|---|---:|---|
| Datasets | **67** | All 67 have `schemaMetadata`. |
| Dashboards | **3** | Tableau, Looker, and Power BI metadata are represented. |
| Pipelines | **23 data flows** | DataHub's pipeline entity is `dataFlow`. |
| Pipeline tasks | **23 data jobs** | DataHub models jobs/tasks separately from their containing flow. |
| ML entities | **0 instances** | ML entity types are registered, but this datapack loaded no ML model, feature, feature-table, deployment, or model-group instances. |
| Domains | **6** | All visible in the primary store. |
| Glossary terms | **10** | Plus 4 glossary nodes. |
| Tags | **6** | Tag entities, not merely tag assignments. |
| Assertions | **0** | The registry supports assertions; this datapack contains no assertion instances. |
| Data contracts | **0** | The registry supports data contracts; this datapack contains no contract instances. |

Other useful loaded counts:

| Entity type | Count |
|---|---:|
| Schema-field entities | 873 |
| Data platforms | 91 |
| Charts | 12 |
| Containers | 14 |
| Documents | 18 |
| Data products | 5 |
| Glossary nodes | 4 |
| Users | 12 |
| Groups | 8 |

### 6.4 Search-index state

**Verified locally at the inspection checkpoint:** GraphQL search returned 54/67 datasets, 1/3 dashboards, 20/23 data flows, 17/23 data jobs, 6/6 domains, 10/10 glossary terms, 6/6 tags, and 0 assertions. GMS logged successful OpenSearch bulk updates, while Kafka's `generic-mae-consumer-job-client` still had 1,919 versioned metadata-change records to process across three partitions.

**Interpretation:** ingestion is complete in MySQL, while search indexing remains in progress. A search result of fewer than 67 datasets at this checkpoint is not evidence of a missing primary-store entity. The operator can use the official `datahub docker quickstart --restore-indices` facility if indexing stalls; that command was **not** run during this study.

### 6.5 Ownership

**Verified locally:**

- 58 entity URNs have a current `ownership` aspect.
- Those aspects contain 98 owner assignments in total.
- 20 datasets contain ownership, accounting for 51 assignments.
- Ownership also appears on data jobs, data products, glossary terms/nodes, charts, domains, tags, groups, dashboards, and one container.

An owner assignment contains:

- an owner URN such as a user or group,
- an ownership type URN such as technical owner, business owner, or data steward,
- provenance such as manual assignment,
- modification metadata.

The [official metadata model](https://docs.datahub.com/docs/metadata-modeling/metadata-model) describes `ownership` as a reusable aspect shared across entity types. The [ownership API tutorial](https://docs.datahub.com/docs/api/tutorials/owners) shows owner URNs and ownership types.

### 6.6 Lineage

**Verified locally:**

- 55 entities have an `upstreamLineage` aspect.
- Those aspects contain 55 direct upstream dataset edges.
- They contain 835 fine-grained/column-lineage mappings.
- All 23 data jobs have a `dataJobInputOutput` aspect.
- Data jobs contain 24 input-dataset edges, 23 output-dataset edges, and 199 fine-grained lineage mappings.
- The OpenSearch graph index contained 2,321 relationship documents at the checkpoint.

Lineage is therefore available at both dataset and field level, and pipeline/job connectivity is present. DataHub's [lineage guide](https://docs.datahub.com/docs/features/feature-guides/lineage) documents table-, column-, and pipeline-level lineage.

### 6.7 Schemas

**Verified locally:**

- 67 datasets have a `schemaMetadata` aspect.
- Their embedded schema metadata contains 816 fields.
- There are 873 `schemaField` entities overall; additional schema-field URNs are used by chart/input-field and relationship metadata.

Each observed field contains a field path, typed DataHub field type, native source type, nullability, key flag, and optional description. The schema aspect also records the platform, schema name, version/hash, platform-specific schema, and audit timestamps.

### 6.8 Dashboards and datasets

**Verified locally:** the relationship can be represented in several compatible ways:

- `dashboardInfo.charts[]` links a dashboard to chart URNs.
- A chart's `chartInfo.inputs[]` links the chart to dataset URNs.
- `inputFields` links dashboard or chart inputs to dataset schema-field URNs.
- The inspected Power BI dashboard also had direct `datasetEdges[]`.

Thus the common traversal is dashboard → chart → dataset, with direct dashboard → dataset edges also possible when the source emits them. The [official dashboard/chart API tutorial](https://docs.datahub.com/docs/api/tutorials/dashboard-chart) documents dashboard-chart relationships.

## 7. Architecture learned from DataHub

This section explains DataHub itself. “Possible later reuse” identifies an existing platform capability for future evaluation; it is **not** a CHRONOS design decision.

### 7.1 Frontend

- **What:** a React web application served by the frontend container.
- **Why it exists:** provides catalog search, entity pages, lineage, governance, and administration through a human interface.
- **Possible later reuse:** CHRONOS stakeholders could use DataHub's existing UI if a later requirements phase determines it is suitable. No custom frontend is proposed here.

Official basis: [Architecture overview](https://docs.datahub.com/docs/architecture/architecture) and [Components](https://docs.datahub.com/docs/components).

### 7.2 Metadata Service / GMS

- **What:** the central Java service that owns metadata APIs, entity/aspect validation, authorization, reads/writes, search, and relationship queries.
- **Why it exists:** gives all clients a consistent, governed metadata boundary.
- **Possible later reuse:** it is the supported system boundary for any future metadata interaction.

Official basis: [Serving Tier](https://docs.datahub.com/docs/architecture/metadata-serving).

### 7.3 Graph Service

- **What:** a logical relationship-query capability inside GMS. In this installation it uses OpenSearch, not a separate graph database.
- **Why it exists:** resolves neighbors, lineage, impact, and multi-hop paths from typed relationships derived from aspects.
- **Possible later reuse:** future investigation can evaluate traversal and impact-analysis queries without introducing another graph store.

### 7.4 Kafka

- **What:** the event log for metadata proposals, committed change logs, platform events, usage, and failures.
- **Why it exists:** decouples authoritative writes from indexing, actions, and external subscribers while preserving per-key ordering.
- **Possible later reuse:** metadata-change subscriptions are a candidate integration mechanism if later requirements need event-driven reactions.

Official basis: [Architecture overview](https://docs.datahub.com/docs/architecture/architecture) and [APIs overview](https://docs.datahub.com/docs/api/datahub-apis).

### 7.5 Search index

- **What:** OpenSearch indexes for searchable entities, relationships/graph, and time-series aspects.
- **Why it exists:** relational primary-key access is not sufficient for full-text search, faceting, secondary filters, or efficient graph traversal.
- **Possible later reuse:** existing catalog search, filtering, and relationship traversal can be evaluated before building any separate metadata index.

### 7.6 Storage

- **What:** MySQL is the quickstart's primary aspect store; Docker volumes persist MySQL, OpenSearch, and Kafka state.
- **Why it exists:** the relational store provides authoritative aspect versions and transactions; derived stores optimize other access patterns.
- **Possible later reuse:** DataHub's versioned aspect model is a candidate system of record for metadata, subject to later requirements and production validation.

### 7.7 CLI

- **What:** the `datahub` command installed from `acryl-datahub`.
- **Why it exists:** configures clients, runs ingestion, manages quickstart, loads datapacks, inspects the graph, and invokes GraphQL.
- **Possible later reuse:** local administration, repeatable ingestion, and diagnostics.

Official basis: [DataHub CLI documentation](https://docs.datahub.com/docs/cli).

### 7.8 Python SDK

- **What:** typed Python clients and builders distributed with `acryl-datahub`.
- **Why it exists:** provides a higher-level programmatic interface for metadata CRUD, search, lineage, and bulk operations.
- **Possible later reuse:** preferred candidate for Python-based metadata integration, if future requirements authorize implementation.

DataHub's [APIs and SDKs overview](https://docs.datahub.com/docs/api/datahub-apis) recommends SDKs for common CRUD and bulk operations.

### 7.9 GraphQL API

- **What:** a high-level typed API used by the DataHub frontend and available to authenticated clients.
- **Why it exists:** retrieves entity views and relationship-rich responses efficiently and supports UI-oriented mutations.
- **Possible later reuse:** interactive search, entity detail, and lineage queries.

Official basis: [GraphQL overview](https://docs.datahub.com/docs/api/graphql/overview/) and [getting started](https://docs.datahub.com/docs/api/graphql/getting-started/).

### 7.10 REST APIs

- **What:** GMS exposes generated OpenAPI endpoints and lower-level Rest.li resources.
- **Why they exist:** support direct entity/aspect operations, operational endpoints, and language-neutral integration.
- **Possible later reuse:** integrations that do not use Python/Java or need lower-level aspect control.

DataHub's [APIs overview](https://docs.datahub.com/docs/api/datahub-apis) characterizes OpenAPI as powerful and lower-level. The local OpenAPI UI is verified.

### 7.11 MCP Server

- **What:** an official Model Context Protocol server exposing tools such as search, entity retrieval, schema fields, lineage, paths, and dataset queries to AI clients.
- **Why it exists:** gives agents a bounded, tool-oriented metadata interface instead of requiring them to construct raw API calls.
- **Possible later reuse:** a candidate read interface for agents, with mutation tools disabled unless explicitly required and governed.

Official basis: [DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp).

**Local availability:** not installed by quickstart. `http://localhost:8080/mcp` returned 404 on server `v1.5.0.6`. The official external Core-compatible MCP server can be run separately, but it was not installed because this phase required environment learning, not agent integration.

### 7.12 Agent Context Kit

- **What:** the official `datahub-agent-context` Python package and guidance for exposing DataHub search, entity, schema, lineage, query, and controlled mutation tools to agent frameworks.
- **Why it exists:** supplies reusable agent-tool abstractions above the underlying APIs/MCP.
- **Possible later reuse:** evaluate as an agent integration library after version compatibility, authentication, permissions, and mutation policy are defined.

Official basis: [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context).

**Local availability:** not installed. PyPI reports the matching `1.6.0.15` package, but the current server is `1.5.0.6`; compatibility is an open question.

### 7.13 Skills

- **What:** DataHub's official open-source agent skill repository contains workflow instructions for search, enrichment, lineage, quality, setup, and connector planning/review.
- **Why it exists:** teaches compatible agents how to use DataHub tools consistently; it is not a metadata runtime service.
- **Possible later reuse:** provide repeatable agent procedures after the underlying MCP/API connection is governed.

Official basis: [datahub-project/datahub-skills](https://github.com/datahub-project/datahub-skills).

**Local availability:** not installed.

### 7.14 DataHub Agents product

DataHub's hosted “Agents” feature is distinct from MCP, Agent Context Kit, and skills. The [official Agents documentation](https://docs.datahub.com/docs/features/feature-guides/agents) marks it as DataHub Cloud and private beta. It is not part of this Community Edition quickstart.

## 8. Metadata model learning report

### 8.1 How DataHub stores metadata

DataHub is schema-first. An **entity** has an entity type, a globally unique URN, and a collection of independently writable **aspects**. Aspects are the smallest atomic write unit. Common aspects such as ownership, tags, glossary terms, status, and subtypes can be reused across entity types. The model is defined in Pegasus Data Language and registered with the entity registry. Official basis: [The Metadata Model](https://docs.datahub.com/docs/metadata-modeling/metadata-model).

In this quickstart, current and historical aspect versions live in MySQL. After a successful change, Kafka change logs drive OpenSearch search/graph projections and actions. This is why an entity can be committed but temporarily absent from search.

### 8.2 How lineage is represented

Lineage is metadata expressed through typed relationships:

- datasets use `upstreamLineage`,
- jobs use `dataJobInputOutput`,
- dataset-level edges connect entity URNs,
- fine-grained lineage maps upstream schema-field URNs to downstream schema-field URNs,
- job inputs/outputs connect pipeline execution structure to datasets.

GMS derives graph edges from relationship-bearing aspects and serves traversal from the graph index. Official basis: [Lineage](https://docs.datahub.com/docs/features/feature-guides/lineage) and [metadata serving](https://docs.datahub.com/docs/architecture/metadata-serving).

The UI's lineage time filter shows edges whose latest observed timestamps fall in the selected window; the official lineage guide cautions that this is not a complete historical snapshot model.

### 8.3 How schemas are represented

Dataset-level `schemaMetadata` contains the source platform, schema identity/version/hash, platform schema, and field definitions. Fields have paths, native and normalized types, nullability/key attributes, descriptions, and audit data. DataHub also materializes schema-field URNs so fields can participate in tags, glossary links, and column lineage.

### 8.4 How ownership is represented

The reusable `ownership` aspect holds assignments. Each assignment points to a user or group URN and an ownership-type URN, with audit/provenance information. Ownership therefore is metadata attached to an entity, not a column directly embedded in every entity type.

### 8.5 How dashboards connect to datasets

The observed model supports dashboard → chart and chart → dataset relationships, field-level input references, and direct dashboard → dataset edges where a connector supplies them. This accommodates BI tools that expose different levels of structure.

### 8.6 How contracts are represented

The current server registry contains a `dataContract` entity type, but this environment contains zero instances. DataHub's [data-contract API tutorial](https://docs.datahub.com/docs/api/tutorials/data-contracts) describes a contract as a bundle of important assertions grouped into freshness, schema, and data-quality categories and linked to a governed entity. Contract status derives from the latest results of those assertions.

**Edition caution:** the referenced tutorial is explicitly labeled DataHub Cloud. The open metadata model is present locally, but this study did not verify a Community Edition-native contract authoring or execution workflow. That capability is **unknown**, not assumed.

### 8.7 How assertions work

An assertion is a first-class entity describing a quality expectation and its target. Assertion run-event/time-series aspects record evaluations and outcomes. DataHub documents freshness, volume, column, schema, and custom SQL assertion workflows in its [assertions API tutorial](https://docs.datahub.com/docs/api/tutorials/assertions).

**Edition caution:** the native monitoring workflow in that tutorial is labeled DataHub Cloud. Community Edition can model assertion entities and can ingest compatible assertion metadata/results, but native scheduling/execution was not verified here. The showcase contains zero assertions.

### 8.8 How graph traversal works

1. An aspect contains a field declared as a relationship to another entity URN.
2. GMS commits the aspect to the primary store.
3. the metadata change log is published to Kafka.
4. consumers update search and graph documents in OpenSearch.
5. GraphQL, REST, SDK, or MCP clients request lineage/neighbors/paths.
6. GMS executes the relationship query against the graph index and resolves entity details as needed.

This sequence is a concise restatement of the [official serving-tier architecture](https://docs.datahub.com/docs/architecture/metadata-serving), confirmed locally by `GRAPH_SERVICE_IMPL=elasticsearch`, Kafka topics, and `graph_service_v1`.

### 8.9 How agents can query DataHub

In increasing order of abstraction:

1. REST/OpenAPI for direct HTTP access.
2. GraphQL for search and relationship-rich entity views.
3. Python SDK for typed programmatic operations.
4. CLI for operator and scripted access.
5. MCP Server for standardized agent tools.
6. Agent Context Kit for framework-ready tools.
7. Skills for reusable agent operating procedures.

Only the first four are installed and verified locally. MCP, Agent Context Kit, and skills are officially available but not installed in this environment. Cloud-only Agents are not available in the Community quickstart.

## 9. Important repository folders

The DataHub source repository was inspected remotely at [datahub-project/datahub](https://github.com/datahub-project/datahub). It was not cloned because this phase does not modify DataHub core.

| Folder | Relevant contents |
|---|---|
| `metadata-models` | Core Pegasus entity/aspect schemas and generated-model foundations. |
| `metadata-models-custom` | Custom-model extension support. |
| `entity-registry` | Entity/aspect registration and model assembly. |
| `metadata-service` | GMS implementation: metadata APIs and serving behavior. |
| `metadata-io` | Persistence, search, and graph access layers. |
| `metadata-events` | Metadata proposal/change-log event definitions and processing contracts. |
| `datahub-graphql-core` | GraphQL schema and resolvers used by the API/UI. |
| `datahub-web-react` | React web application. |
| `datahub-frontend` | Frontend server/proxy/authentication integration. |
| `metadata-ingestion` | Python ingestion framework, CLI, SDK, connectors, and recipes. |
| `metadata-ingestion-modules` | Additional modular ingestion functionality. |
| `datahub-actions` | Event-driven metadata actions. |
| `datahub-agent-context` | Agent Context Kit implementation. |
| `datahub-upgrade` | Bootstrap, model/index migration, and upgrade tasks. |
| `docker` | Container definitions and quickstart Compose assets. |
| `datahub-kubernetes` | Kubernetes-related deployment support. |
| `metadata-auth` | Authentication/authorization components. |
| `docs`, `docs-website` | Product and developer documentation. |
| `e2e-test`, `smoke-test`, `perf-test` | End-to-end, smoke, and performance validation. |
| `scripts`, `gradle`, `buildSrc` | Repository build and developer tooling. |

Folders such as editor settings, general CI configuration, and unrelated test fixtures were intentionally omitted because they do not materially improve platform understanding at this phase.

## 10. APIs and access guidance

| Need | DataHub surface | Status here | Guidance from evidence |
|---|---|---|---|
| Human exploration | UI | Verified | Use for browsing, lineage, governance, and administration. |
| Common Python CRUD/bulk | Python SDK | Installed | Official API guide's preferred high-level route. |
| UI-shaped reads/relationships | GraphQL | Verified | Check both HTTP status and GraphQL `errors`. |
| Low-level entity/aspect HTTP | OpenAPI/REST | Verified | Powerful; requires more model knowledge. |
| Legacy/internal REST resources | Rest.li | Present in GMS | Use only when the supported higher-level API does not meet the need. |
| Event subscription | Kafka MCL topics | Verified | Appropriate for metadata-change consumers; direct writes bypass GMS safeguards. |
| Agent tool calls | MCP | Available separately | Not installed; current GMS `/mcp` is absent. |
| Agent framework integration | Agent Context Kit | Available separately | Not installed; version compatibility must be tested. |

## 11. DataHub capabilities that CHRONOS can potentially reuse

These are inventory items for a later design phase, not selected architecture:

- typed entities, URNs, and independently versioned aspects,
- datasets, schema fields, dashboards, charts, data flows, data jobs, and data products,
- dataset-, job-, and field-level lineage,
- ownership types and user/group owner assignments,
- domains, glossary terms/nodes, tags, and structured properties,
- assertion and data-contract entity models, subject to edition/workflow validation,
- catalog UI, full-text search, filters, and graph traversal,
- ingestion framework and official connectors,
- Python SDK, GraphQL, OpenAPI/REST, CLI, and Kafka change streams,
- optional MCP, Agent Context Kit, and agent skills.

No claim is made that every item should be used.

## 12. Unknowns

- Why CLI `1.6.0.15` selected the `v1.5.0.6` default quickstart plan on this host, beyond the locally observed version mapping.
- Whether search indexing will converge without intervention under the current Docker resource allocation.
- Exact Docker Desktop RAM and swap allocation.
- Community Edition-native authoring, scheduling, and execution boundaries for assertions and data contracts.
- Compatibility of MCP Server and Agent Context Kit `1.6.0.15` with GMS `1.5.0.6`.
- Which of the 248 filtered enrichment aspects are essential to future requirements.
- Required production scale, availability, authentication, authorization, retention, backup, and disaster-recovery objectives.
- Which real metadata sources and connectors will be in scope.
- Whether custom entities/aspects will be necessary.
- Whether DataHub Cloud-only capabilities are acceptable or prohibited.

## 13. Risks

| Risk | Evidence | Consequence |
|---|---|---|
| Quickstart is not production-safe | Official docs cite default credentials, exposed ports, single-host limits, and limited management. | This installation must remain local/development only. |
| CLI/server version skew | CLI/datapack `1.6.0.15`; server `1.5.0.6`; 248 aspects filtered. | Missing enrichment metadata and uncertain compatibility for newer tools. |
| Windows datapack path defect | Reproduced before emission. | Direct official command fails on this Windows path; Linux helper is currently required. |
| Eventual indexing lag | MySQL contains all requested entities while search remains partial. | UI/API search can temporarily undercount or miss entities. |
| OpenSearch quickstart is single-node | Indexes report yellow because one replica cannot be allocated on one node. | Acceptable for local development; not a production health model. |
| Default credentials and open ports | Verified and officially documented. | Local services should not be exposed to untrusted networks. |
| Assertions/contracts absent from showcase | Zero instances in the primary store. | Their behavior cannot be learned empirically from this datapack alone. |
| Cloud/Core documentation boundaries | Some assertion, contract, and agent features are explicitly Cloud-only. | Feature assumptions could cause incorrect future design decisions. |

## 14. Questions for the next investigation

1. Should the environment be pinned and upgraded to server `v1.6.0` to eliminate CLI/server skew?
2. Does a reindex on the current hardware converge, and what Docker resource allocation is needed?
3. Which official connectors match the future source-system inventory?
4. Which metadata is authoritative in source systems versus curated in DataHub?
5. What authentication and authorization model will be required beyond quickstart defaults?
6. Are Community Edition-only constraints mandatory, or can Cloud capabilities be considered?
7. How will externally evaluated data-quality results be mapped to assertion entities and run events?
8. Are data contracts required as governed objects, and which edition provides the needed workflow?
9. What lineage granularity and freshness are required: dataset, column, job, query, or all?
10. What backup, restore, index-rebuild, retention, and disaster-recovery objectives apply?
11. Will agents be read-only, and which MCP mutation tools, if any, could ever be enabled?
12. Are standard entities/aspects sufficient, or is an approved custom metadata model required?

## 15. Verification checklist

- [x] DataHub Community Edition installed through the official CLI quickstart
- [x] Docker Compose deployment running
- [x] UI verified
- [x] GMS/Metadata Service health verified
- [x] Authenticated GraphQL verified
- [x] OpenAPI UI verified
- [x] OpenSearch verified
- [x] Kafka verified and topics listed
- [x] MySQL verified and primary metadata inspected
- [x] Official `showcase-ecommerce` datapack loaded
- [x] No synthetic metadata created
- [x] Entity/type counts reported
- [x] Ownership and lineage inspected
- [x] Architecture and APIs explained
- [x] MCP, Agent Context Kit, skills, and Cloud Agents availability distinguished
- [x] Important repository folders explained
- [x] Unknowns, risks, and investigation questions recorded
- [ ] Search index fully converged at the inspection checkpoint
- [ ] Assertions and contracts empirically demonstrated (not present in the official datapack)

## 16. Official source index

- [DataHub Quickstart](https://docs.datahub.com/docs/quickstart)
- [Architecture Overview](https://docs.datahub.com/docs/architecture/architecture)
- [Components](https://docs.datahub.com/docs/components)
- [Serving Tier](https://docs.datahub.com/docs/architecture/metadata-serving)
- [Docker Container Architecture](https://docs.datahub.com/docs/architecture/docker-containers)
- [The Metadata Model](https://docs.datahub.com/docs/metadata-modeling/metadata-model)
- [DataHub APIs and SDKs Overview](https://docs.datahub.com/docs/api/datahub-apis)
- [GraphQL Overview](https://docs.datahub.com/docs/api/graphql/overview/)
- [GraphQL Getting Started](https://docs.datahub.com/docs/api/graphql/getting-started/)
- [Lineage](https://docs.datahub.com/docs/features/feature-guides/lineage)
- [Ownership API Tutorial](https://docs.datahub.com/docs/api/tutorials/owners)
- [Dashboard and Chart API Tutorial](https://docs.datahub.com/docs/api/tutorials/dashboard-chart)
- [Assertions API Tutorial](https://docs.datahub.com/docs/api/tutorials/assertions)
- [Data Contracts API Tutorial](https://docs.datahub.com/docs/api/tutorials/data-contracts)
- [DataHub MCP Server](https://docs.datahub.com/docs/features/feature-guides/mcp)
- [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context)
- [DataHub Agents](https://docs.datahub.com/docs/features/feature-guides/agents)
- [DataHub Core Repository](https://github.com/datahub-project/datahub)
- [DataHub Skills Repository](https://github.com/datahub-project/datahub-skills)
