# CHRONOS Phase 0.3 — DataHub Interface Learning Report

**V-L:** Report date: 2026-07-25.<br>
**V-L:** Scope: how a future CHRONOS system could communicate with DataHub; no CHRONOS design or implementation.

## Evidence classification

- **Verified — Official (`V-O`)**: stated in current DataHub 1.6.0 documentation, an official DataHub repository, or an official schema/reference.
- **Verified — Local (`V-L`)**: observed directly against the local DataHub installation during this phase.
- **Inference (`I`)**: a recommendation or conclusion derived from cited verified facts; it is not represented as a DataHub guarantee.
- **Unknown (`U`)**: not established by the official sources or the local checks completed in this phase.

> **V-L:** The local environment runs DataHub server images `v1.5.0.6`, while the installed CLI and current documentation are `1.6.0.15` and `1.6.0`, respectively. Version-specific findings are identified below.

> **V-O:** Primary sources used throughout this report are the [APIs and SDKs overview](https://docs.datahub.com/docs/api/datahub-apis), [GraphQL documentation](https://docs.datahub.com/docs/api/graphql/overview/), [Python SDK documentation](https://docs.datahub.com/docs/python-sdk/sdk-v2/main-client), [OpenAPI guide](https://docs.datahub.com/docs/api/openapi/openapi-usage-guide), [metadata event model](https://docs.datahub.com/docs/what/mxe), [metadata serving architecture](https://docs.datahub.com/docs/architecture/metadata-serving), [MCP Server guide](https://docs.datahub.com/docs/features/feature-guides/mcp), [Agent Context Kit guide](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context), and the official [DataHub Skills repository](https://github.com/datahub-project/datahub-skills).

> **V-O:** DataHub uses “MCP” for two different concepts: the Model Context Protocol used by the MCP Server, and the Metadata Change Proposal used for aspect-level metadata writes; this report spells out the intended meaning where ambiguity is possible.

## 1. Interface Overview

### Catalog

| Interface | Purpose and primary users | Authentication | Operations | Limitations and performance | Maturity | Typical use | Status |
|---|---|---|---|---|---|---|---|
| GraphQL API | High-level, typed metadata reads and mutations; used by the DataHub frontend and interactive API clients | Bearer personal access token (PAT) when Metadata Service authentication is enabled | Entity reads, search, browse, lineage, and high-level mutations | Intentionally exposes a curated surface rather than every low-level capability; clients must inspect GraphQL `errors` even when HTTP status is 200 | Primary, production interface used by the DataHub UI | Interactive reads, precisely shaped responses, typed metadata exploration | V-O |
| Python SDK | Python-native entity, search, lineage, aspect, ingestion, and emission clients | Server URL plus PAT; environment/profile configuration is supported | Typed entity CRUD, search, lineage, low-level aspect reads, MCP emission, ingestion | SDK v2 currently emits an experimental warning; the older `DataHubGraph` and emitter APIs remain relevant | SDK v2 experimental; legacy clients established | Programmatic reads/writes, bulk work, ingestion, automation | V-O, V-L |
| Java SDK | Java-native builders, CRUD, patches, and emitters | GMS URL and token/client configuration | Type-safe entity/aspect creation and mutation; REST or Kafka emission depending on API generation | This report does not test Java locally; the V1 API is described as legacy | V2 recommended for new Java projects; V1 legacy | JVM ingestion and metadata integrations | V-O |
| REST/OpenAPI | Low-level HTTP access to entities, aspects, relationships, health, and platform operations | Bearer PAT when GMS authentication is enabled | Aspect upsert/get/delete, entity batch/scroll, relationships, health, plus generated endpoints | Lower-level and more verbose; official docs warn generated-client maturity varies by language | Official and broad; OpenAPI 2.0 document locally exposes 352 paths | Cross-language integrations and capabilities absent from GraphQL/SDK helpers | V-O, V-L |
| CLI | Operator/developer command surface around ingestion, Docker quickstart, GraphQL, delete, rollback, telemetry, and profiles | Profile/environment URL and PAT | Operational workflows, ingestion, schema discovery, one-off GraphQL execution | Process-start and text/JSON serialization overhead make it a poor hot-path library interface | Official, established | Setup, diagnostics, CI jobs, administrator-controlled batch work | V-O |
| MCP Server | Model Context Protocol tool server that exposes DataHub context to compatible AI clients | Managed Cloud: OAuth2/DCR or PAT; Core/self-hosted: GMS URL and PAT | Search, entity/schema inspection, lineage, documents, query context, governed proposals; optional mutations | Agent/tool abstraction rather than a deterministic general application API; output is constrained by tool token budgets | Official server; mutation tools require server v0.5.0+ and opt-in | Agent context and natural-language metadata workflows | V-O |
| Agent Context Kit (ACK) | Umbrella of guides, SDKs, and the MCP server for DataHub-aware agents | DataHub PAT; framework/platform-specific credentials may also be required | Makes search, entity, lineage, query, document, and selected mutation tools available to agent frameworks | It is not documented as a general application data-access layer | Official developer capability; Python package requires Python 3.10+ | LangChain, Google ADK, coding assistants, managed agent platforms | V-O |
| DataHub Skills | Reusable, host-executed instruction/workflow packages for agents working with DataHub | Uses the CLI/MCP credentials available to the agent host | Search, enrichment, lineage, quality, setup, connector planning/review, standards loading, and MFE workflows | Skills are not DataHub endpoints; behavior depends on a compatible agent host and the selected underlying interface | Official open-source repository; rapidly evolving | Repeatable agent workflows around DataHub | V-O |
| Metadata Change Proposal (MCP) | Request to change one aspect of one entity | Depends on transport: GMS auth for REST; broker controls for direct Kafka | `CREATE`, `UPSERT`, `DELETE`, and limited `PATCH` at aspect scope | Direct Kafka bypasses GMS accept-time authentication and validation; asynchronous application delays read-after-write visibility | Current recommended metadata event | Normal metadata write unit and ingestion transport | V-O |
| Metadata Change Event (MCE) | Older snapshot event capable of carrying multiple aspects | Depends on transport | Snapshot-style multi-aspect update | Deprecated; official docs say not to build new dependencies on it | Deprecated | Compatibility with older producers only | V-O |
| Graph Service | Internal GMS service/index used to answer relationship and lineage traversals | Reached through authenticated public GMS APIs, not authenticated separately by a normal client | Relationship lookup and graph traversal | Not documented as a public standalone client interface | Internal serving component | Supports GraphQL/REST lineage and relationship queries | V-O, V-L |

> **V-O:** The official API overview recommends SDKs for programmatic CRUD and bulk work, GraphQL for high-level/frontend-aligned access, and OpenAPI for the broadest low-level HTTP surface.

> **I:** For deterministic CHRONOS-to-DataHub communication, Python SDK, GraphQL, and OpenAPI are the relevant direct interfaces; MCP Server, ACK, and Skills become relevant only if a later phase explicitly introduces agent-facing use cases.

> **V-L:** The local GMS is reachable at `http://localhost:8080`; GraphQL is at `http://localhost:8080/api/graphql`; Swagger UI is at `http://localhost:8080/openapi/swagger-ui/index.html`.

### Official source index

| Interface | Official source | Status |
|---|---|---|
| GraphQL | [Overview](https://docs.datahub.com/docs/api/graphql/overview/), [getting started](https://docs.datahub.com/docs/api/graphql/getting-started/), [best practices](https://docs.datahub.com/docs/api/graphql/graphql-best-practices/) | V-O |
| Python SDK | [Main client](https://docs.datahub.com/docs/python-sdk/sdk-v2/main-client), [entity client](https://docs.datahub.com/docs/python-sdk/sdk-v2/entity-client), [search client](https://docs.datahub.com/docs/python-sdk/sdk-v2/search-client), [lineage client](https://docs.datahub.com/docs/python-sdk/sdk-v2/lineage-client), [legacy graph client](https://docs.datahub.com/docs/python-sdk/clients/graph-client) | V-O |
| Java SDK | [Java as a library](https://docs.datahub.com/docs/metadata-integration/java/as-a-library) | V-O |
| REST/OpenAPI | [OpenAPI usage guide](https://docs.datahub.com/docs/api/openapi/openapi-usage-guide) | V-O |
| CLI | [DataHub CLI](https://docs.datahub.com/docs/cli) | V-O |
| MCP Server | [Feature guide](https://docs.datahub.com/docs/features/feature-guides/mcp), [official server repository](https://github.com/acryldata/mcp-server-datahub) | V-O |
| Agent Context Kit | [ACK overview](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context) | V-O |
| DataHub Skills | [Skills repository](https://github.com/datahub-project/datahub-skills) | V-O |
| MCP/MCE/MCL | [Core metadata events](https://docs.datahub.com/docs/what/mxe) | V-O |
| Graph Service | [Metadata serving architecture](https://docs.datahub.com/docs/architecture/metadata-serving) | V-O |

## 2. GraphQL Deep Dive

### Endpoint, authentication, and response rules

> **V-O:** The endpoint is `POST /api/graphql`, the request media type is JSON, and authenticated deployments accept `Authorization: Bearer <PAT>`. See [GraphQL getting started](https://docs.datahub.com/docs/api/graphql/getting-started/).

> **V-O:** A GraphQL response can contain an `errors` array with HTTP 200, so success handling must inspect both `data` and `errors`.

> **V-L:** Local introspection found 98 root queries and 161 root mutations on server `v1.5.0.6`.

### Schema and supported operations

| Concern | Verified capability | Status |
|---|---|---|
| Root entity queries | `dataset`, `dashboard`, `dataFlow`, `dataJob`, `tag`, `glossaryTerm`, `domain`, `assertion`, `dataProduct`, `entities` | V-L |
| Search | `search`, `searchAcrossEntities`, `scrollAcrossEntities`, `searchAcrossLineage`, `scrollAcrossLineage` | V-L |
| Browse | `browse` and `browseV2` | V-L |
| Dataset metadata | Properties, ownership, schema metadata, tags, glossary terms, domain, assertions, lineage, structured properties | V-L |
| Dashboard metadata | Properties, ownership, tags, glossary terms, domain, generic relationships, lineage | V-L |
| Mutations | Dataset/dashboard/flow updates; owner/tag/term/domain changes; lineage updates; data products; structured properties; assertions; contracts; generic patch operations | V-L |
| Lineage paging | Direction, `start`, `count`, sibling handling, time range, and ghost-entity inclusion on entity lineage; root scroll APIs support deep traversal | V-L, V-O |
| Batch retrieval | `entities(urns: [String!]!)` accepts multiple URNs | V-L |

> **V-O:** Search queries are appropriate for shallow paging; the official [GraphQL best-practices guide](https://docs.datahub.com/docs/api/graphql/graphql-best-practices/) recommends scroll APIs for deep paging and explains that search cannot page beyond 10,000 results.

> **V-O:** Deep scrolling should use a stable sort such as URN rather than relevance score; requests should select only needed fields and avoid deeply nested result shapes.

> **U:** No official per-client request rate limit was found for the self-hosted GraphQL endpoint.

> **U:** No official GraphQL query-complexity or depth ceiling was found.

> **I:** Deployment owners must establish their own request budgets until the selected production edition and gateway limits are known.

### Documentation-only query examples

> **V-O, V-L:** The examples below use fields present in the official tutorials and confirmed by local schema introspection. They are API-learning snippets, not CHRONOS application logic.

#### Retrieve a dataset, schema, ownership, glossary terms, and tags

```graphql
query DatasetContext($urn: String!) {
  dataset(urn: $urn) {
    urn
    properties { name description }
    schemaMetadata {
      platformSchema { __typename }
      fields { fieldPath type nativeDataType description }
    }
    ownership {
      owners { type owner { urn type } }
    }
    glossaryTerms {
      terms { term { urn glossaryTermInfo { name description } } }
    }
    tags {
      tags { tag { urn name properties { description colorHex } } }
    }
    domain { domain { urn properties { name } } }
  }
}
```

> **V-O:** Variables keep URNs and user input out of query text and allow reuse through a GraphQL client.

#### Retrieve upstream or downstream lineage

```graphql
query Lineage($urn: String!, $direction: LineageDirection!, $count: Int!) {
  scrollAcrossLineage(
    input: { urn: $urn, direction: $direction, query: "*", count: $count }
  ) {
    nextScrollId
    total
    searchResults {
      degree
      entity { urn type }
    }
  }
}
```

> **V-O:** Supply `UPSTREAM` to retrieve dependencies and `DOWNSTREAM` to retrieve consumers; follow `nextScrollId` for subsequent pages. See the [lineage tutorial](https://docs.datahub.com/docs/api/tutorials/lineage).

#### Retrieve dashboard dependencies

```graphql
query DashboardDependencies($dashboardUrn: String!, $count: Int!) {
  scrollAcrossLineage(
    input: {
      urn: $dashboardUrn
      direction: UPSTREAM
      query: "*"
      count: $count
    }
  ) {
    total
    nextScrollId
    searchResults {
      degree
      entity { urn type }
    }
  }
}
```

> **V-L:** The local `Dashboard` type does not expose a direct `datasets` field; its dependencies are exposed through lineage or generic relationships.

#### Search datasets

```graphql
query SearchDatasets($query: String!, $start: Int!, $count: Int!) {
  search(input: { type: DATASET, query: $query, start: $start, count: $count }) {
    start
    count
    total
    searchResults {
      entity {
        urn
        type
        ... on Dataset { properties { name description } }
      }
    }
  }
}
```

> **V-O:** Filtering is available on entity search/scroll inputs; sorting is available on the corresponding cross-entity/scroll inputs, and exact supported fields are discoverable from the deployed schema.

> **I:** Prefer one consolidated dataset query when its fields share the same access pattern; prefer separate paged lineage/search requests when result cardinality can grow independently.

## 3. Python SDK Deep Dive

### Core clients and maturity

| Client/class | Purpose | Status |
|---|---|---|
| `DataHubClient` | SDK v2 entry point for entity, search, and lineage clients | V-O, V-L |
| `client.entities` | Get, create, update, and upsert typed entities | V-O, V-L |
| `client.search` | Search and return entity URNs with filter DSL | V-O, V-L |
| `client.lineage` | Read and add table/column lineage | V-O, V-L |
| `DataHubGraph` | Established lower-level client for aspects, batch entities, and raw GraphQL | V-O, V-L |
| `DatahubRestEmitter` / `DatahubKafkaEmitter` | Emit MCPs through GMS or Kafka | V-O |
| Typed entity/URN classes | `Dataset`, `DatasetUrn`, and peers model DataHub entities | V-O, V-L |

> **V-L:** Importing `datahub.sdk.*` with CLI package `1.6.0.15` emits `ExperimentalWarning` and says normal backward-compatibility and stability guarantees do not yet apply.

> **V-O:** SDK v2 authentication can be supplied through `DataHubClient(server=..., token=...)` or `DataHubClient.from_env()`. See the [main client guide](https://docs.datahub.com/docs/python-sdk/sdk-v2/main-client).

### Documentation-only examples

> **V-O, V-L:** The following snippets demonstrate individual SDK calls only; they do not implement an application.

#### Connect and verify

```python
from datahub.sdk import DataHubClient

client = DataHubClient.from_env()
client.test_connection()
```

#### Search entities, tags, and glossary terms

```python
from datahub.sdk.search_filters import FilterDsl as F

dataset_urns = client.search.get_urns(
    query="orders",
    filter=F.entity_type("dataset"),
)
tagged_urns = client.search.get_urns(
    query="*",
    filter=F.entity_type("dataset") & F.tag("urn:li:tag:PII"),
)
termed_urns = client.search.get_urns(
    query="*",
    filter=F.entity_type("dataset")
    & F.glossary_term("urn:li:glossaryTerm:CustomerData"),
)
```

> **V-L:** `FilterDsl.entity_type`, `tag`, `glossary_term`, `domain`, and `owner` are present in the installed SDK.

#### Retrieve a typed entity, schema, and ownership

```python
from datahub.sdk import DatasetUrn

urn = DatasetUrn(
    platform="snowflake",
    name="analytics.orders",
    env="PROD",
)
dataset = client.entities.get(urn)

schema = dataset.schema
owners = dataset.owners
tags = dataset.tags
terms = dataset.terms
domain = dataset.domain
```

#### Retrieve a low-level aspect

```python
from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
from datahub.metadata.schema_classes import SchemaMetadataClass

graph = DataHubGraph(
    DatahubClientConfig(
        server="http://localhost:8080",
        token="<PAT>",
    )
)
schema_aspect = graph.get_aspect(
    entity_urn=str(urn),
    aspect_type=SchemaMetadataClass,
)
```

#### Traverse lineage

```python
upstream = client.lineage.get_lineage(
    source_urn=urn,
    direction="upstream",
    max_hops=3,
    count=500,
)
downstream = client.lineage.get_lineage(
    source_urn=urn,
    direction="downstream",
    max_hops=3,
    count=500,
)
```

> **V-O:** The official lineage tutorial generally recommends the Python SDK for lineage operations and also documents GraphQL scroll traversal.

#### Bulk entity retrieval

```python
entities = graph.get_entities_v2(
    entity_name="dataset",
    urns=[str(item) for item in dataset_urns],
    aspects=["datasetProperties", "schemaMetadata", "ownership"],
)
```

> **V-L:** The installed `DataHubGraph.get_entities_v2` accepts entity name, URNs, selected aspects, and optional system metadata.

#### Write and update metadata

```python
from datahub.sdk import Dataset

dataset = Dataset(
    platform="snowflake",
    name="analytics.orders",
    description="Curated orders dataset.",
)
client.entities.upsert(dataset)

existing = client.entities.get(dataset.urn)
existing.set_description("Updated curated orders dataset.")
client.entities.update(existing)
```

> **V-O:** SDK v2 entity methods include `create`, `update`, and `upsert`; an update can also accept a `MetadataPatchProposal`. See the [entity client guide](https://docs.datahub.com/docs/python-sdk/sdk-v2/entity-client).

### Errors, retries, and bulk semantics

> **V-L:** The installed SDK defines `ItemNotFoundError` for absent entities and `SdkUsageError` for invalid SDK usage.

```python
from datahub.errors import ItemNotFoundError, SdkUsageError

try:
    dataset = client.entities.get(urn)
except ItemNotFoundError:
    dataset = None
except SdkUsageError as error:
    raise ValueError("The SDK request is invalid.") from error
```

> **V-L:** The exception imports and the `client.entities.get` call above exist in the installed `1.6.0.15` package; the handling is illustrative rather than a prescribed application policy.

> **V-O:** REST emitter modes include `SYNC_WAIT`, `SYNC_PRIMARY`, `ASYNC`, and `ASYNC_WAIT`; synchronous modes provide stronger acknowledgement/read-after-write behavior, while asynchronous modes favor throughput. See [using ingestion as a library](https://docs.datahub.com/docs/metadata-ingestion/as-a-library).

> **U:** The reviewed SDK v2 documentation does not define one universal automatic retry contract for every client method.

> **I:** Callers should classify not-found, authorization, validation, transient transport, timeout, and server failures separately and retry only transient/idempotent operations with bounded exponential backoff and jitter.

> **I:** Chunk bulk reads/writes, cap concurrency, and measure response size rather than assuming a single unbounded batch is safe.

## 4. REST/OpenAPI Analysis

### Coverage observed locally

> **V-L:** The local raw OpenAPI document is available at `GET /openapi/v3/api-docs`, identifies itself as DataHub OpenAPI version `2.0.0`, is approximately 1.13 MB, and declares 352 paths.

| Category | Representative local paths | Status |
|---|---|---|
| Entity/aspect v2 | `GET/POST /openapi/v2/entity/{entityName}`, `GET/DELETE /openapi/v2/entity/{entityName}/{entityUrn}`, `GET/POST/DELETE/PATCH /openapi/v2/entity/{entityName}/{entityUrn}/{aspectName}` | V-L |
| Entity platform v1 | `POST /openapi/v2/platform/entities/v1/` | V-L |
| Legacy entity/aspect | `POST/DELETE /openapi/entities/v1/`, `GET /openapi/entities/v1/latest` | V-L |
| Search/scroll | `GET /openapi/v2/entity/{entityName}` supports query, count, scroll ID, sorting, and selected aspects; operations-level search/scroll endpoints also appear in the specification | V-L |
| Relationships | `GET /openapi/relationships/v1/` | V-L |
| Health | `GET /health`, `/health/live`, `/health/detailed` | V-L |
| OpenLineage | OpenLineage ingestion endpoint is declared in the local specification | V-L |
| Interactive reference | `/openapi/swagger-ui/index.html` | V-L |

> **V-O:** `/openapi/entities/v1/` accepts aspect-level upserts; aspect version checks can use `If-Version-Match`. The official guide describes both JSON and YAML specifications and warns that generated-client maturity differs by language.

> **V-L:** The local OpenAPI document does not declare a root `security` requirement or reusable `securitySchemes`.

> **V-O:** GMS authentication documentation nevertheless requires `Authorization: Bearer <PAT>` when Metadata Service authentication is enabled.

> **I:** Treat the missing OpenAPI security declaration as a specification-documentation gap, not evidence that production endpoints are unauthenticated.

### REST compared with GraphQL

| Dimension | REST/OpenAPI | GraphQL | Status |
|---|---|---|---|
| Surface | Broad, low-level entity/aspect/platform operations | Curated, high-level entity graph and UI-oriented operations | V-O |
| Response shaping | Fixed endpoint schemas | Caller selects fields | V-O |
| Discovery | Swagger/OpenAPI document | GraphQL introspection | V-O, V-L |
| Search/lineage ergonomics | Lower-level endpoints and relationships | First-class typed search/scroll/lineage queries | I |
| Aspect control | Strong, explicit aspect paths and versions | High-level mutations plus generic patch capabilities | V-O, V-L |
| Cross-language use | Direct HTTP and generated clients | Any GraphQL client | V-O |
| Failure handling | HTTP status plus response body | GraphQL `errors` may accompany HTTP 200 | V-O |

> **I:** Prefer OpenAPI when a needed low-level aspect/platform operation is not cleanly exposed by the chosen SDK or GraphQL schema.

> **I:** Do not choose OpenAPI solely because its generated schema contains more endpoints; a smaller typed interface is safer when it fully covers the operation.

## 5. MCP Server Analysis

### Purpose, deployment, and execution model

> **V-O:** The official DataHub MCP Server implements Model Context Protocol so compatible AI clients can discover and call DataHub metadata tools. It is available as a managed DataHub Cloud service and as the official open-source [self-hosted server](https://github.com/acryldata/mcp-server-datahub).

> **V-O:** The server translates tool requests into authenticated DataHub reads or writes and returns model-oriented, bounded results; the LLM selects tools through its MCP client rather than directly composing DataHub GraphQL or REST calls.

> **V-L:** `GET http://localhost:8080/mcp` returned 404 on the local `v1.5.0.6` GMS, and no separate MCP server is installed.

> **V-O:** Current 1.6.0 ACK documentation lists self-hosted `http://<gms-host>:8080/mcp`; this does not establish that the older local server includes that route.

### Tools

| Tool group | Official tools/capabilities | Status |
|---|---|---|
| Discovery | `search`, batch `get_entities`, `list_schema_fields`, `get_me` | V-O |
| Lineage | `get_lineage`, `get_lineage_paths_between` | V-O |
| Documents | `search_documents`, `grep_documents` | V-O |
| SQL context | `get_dataset_queries`, `find_sql_context`, `draft_sql_for_tables` | V-O |
| Governance reads | lifecycle/term-version tools and pending-proposal listing | V-O |
| Optional metadata edits | tags, terms, owners, domains, descriptions, structured properties, lifecycle stages, documents | V-O |
| Optional glossary/proposal workflows | create/version/relate terms; propose or accept/reject selected changes | V-O |

> **V-O:** Mutation tools require open-source server v0.5.0+ or the documented Cloud version and are disabled unless `TOOLS_IS_MUTATION_ENABLED=true`.

> **V-O:** Tools declare MCP hints such as read-only, destructive, and idempotent so compatible clients can display appropriate confirmation.

> **V-O:** Managed Cloud MCP supports OAuth2 with Dynamic Client Registration for interactive users; PAT/service-account access is available for unattended or Core/self-hosted use.

> **V-O:** The open-source server documents token budgets, including `TOOL_RESPONSE_TOKEN_LIMIT` and `ENTITY_SCHEMA_TOKEN_BUDGET`, to bound tool output.

> **U:** The reviewed official server documentation does not describe DataHub-specific MCP Resources or Prompts in addition to its Tools.

> **U:** Exact truncation behavior for every tool and entity shape is not documented as a stable API contract.

### Example workflows and suitability

> **V-O:** A read workflow can search for datasets, batch-fetch selected entities, inspect schema fields, and traverse lineage.

> **V-O:** A governed write workflow can list a pending proposal and, when permissions and mutation tools permit, accept or reject it.

> **I:** CHRONOS should use MCP directly only for an explicitly approved agent-context operation; deterministic metadata reads/writes should use SDK, GraphQL, or OpenAPI.

> **I:** If a future agent is outside CHRONOS but needs DataHub context, MCP should be used indirectly by that agent host rather than inserted into a deterministic application path.

## 6. Agent Context Kit Analysis

> **V-O:** ACK is a set of guides, SDKs, and the MCP server for giving agents DataHub business definitions, documents, ownership, lineage, quality signals, and sample-query context.

> **V-O:** The quickest documented connection is MCP; the Python package installation is `pip install datahub-agent-context`, requires Python 3.10+, a DataHub instance, and a PAT.

| Requested concern | Finding | Status |
|---|---|---|
| Architecture | ACK is documented as an umbrella of guides, SDKs, and MCP rather than a single standalone runtime | V-O |
| Available abstractions | MCP tools plus framework-specific integrations/guides | V-O |
| Context retrieval | Search, entity details, schemas, lineage, query examples, documents, and quality/governance metadata | V-O |
| Metadata retrieval | Uses DataHub-backed tools listed in the ACK/MCP guides | V-O |
| Prompt construction | No general prompt-builder contract was found in the reviewed overview | U |
| Caching | No ACK-wide caching contract was found | U |
| Conversation state | No ACK-owned conversation-state store was documented | U |
| Context compression | No ACK-wide context-compression algorithm or guarantee was documented | U |
| Supported coding assistants | Cursor, Claude, Gemini CLI, Snowflake Cortex Code | V-O |
| Supported SDK frameworks | LangChain and Google ADK | V-O |
| Supported managed platforms | Databricks, Snowflake, Google Vertex AI, Microsoft Copilot Studio | V-O |

> **V-O:** The [ACK guide](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context) presents analytics, quality, and governance agent examples; it does not claim to replace DataHub's deterministic APIs.

> **I:** ACK does not fit the core deterministic communication requirement in this phase.

> **I:** ACK fits only if Phase 0.4 confirms that CHRONOS itself must host or support an AI-agent interaction.

## 7. Skills Analysis

### Official inventory

| Skill/folder | Purpose | Inputs | Outputs/operations | Status |
|---|---|---|---|---|
| `using-datahub` | Auto-injected router to appropriate DataHub skill | User intent and available interfaces | Chooses the relevant workflow; not normally invoked directly | V-O |
| `datahub-search` | Find and explain catalog entities | Natural-language or structured search request | Evidence-backed search/inspection result; MCP preferred, CLI fallback | V-O |
| `datahub-enrich` | Apply governance/documentation metadata | Target entities and requested enrichment | Resolve, plan, approve, execute, and verify descriptions, tags, terms, owners, domains, products, and properties | V-O |
| `datahub-lineage` | Trace and analyze dependencies | Entity/column plus direction/path question | Upstream/downstream, impact, paths, and column-lineage findings | V-O |
| `datahub-quality` | Inspect or manage quality metadata | Entity scope and quality objective | Core reads/diagnosis; broader Cloud assertion/incident/subscription workflows | V-O |
| `datahub-setup` | Configure and validate access | Deployment URL, auth/profile requirements | CLI/MCP detection, profile setup, connectivity checks | V-O |
| `datahub-connector-planning` | Plan a connector change | Connector requirements/repository context | Connector-specific `_PLANNING.md` | V-O |
| `datahub-connector-pr-review` | Review connector contributions | Pull-request/repository changes | Review against 22 connector standards | V-O |
| `load-standards` | Load connector standards | Standards request | Adds the 22 standards to agent context | V-O |
| `datahub-mfe-create-app` | Scaffold a DataHub micro-frontend | MFE creation request | Frontend scaffold | V-O |
| `datahub-mfe-configure-app` | Configure a DataHub micro-frontend | Existing MFE and configuration request | Frontend configuration changes | V-O |
| `shared-references` | Shared support material, not an executable skill | Internal skill references | Reusable reference content | V-O |

> **V-O:** The repository installs skills with `npx skills add datahub-project/datahub-skills` into supported agent hosts; execution happens in that host and uses MCP or CLI as directed by the skill.

> **V-O:** Skills are instruction/workflow artifacts, not services registered with DataHub GMS and not API endpoints.

> **V-O:** Existing Skills demonstrate extensibility through repository-hosted skill folders and shared references; installation registers the collection with the compatible host rather than with DataHub GMS.

> **U:** The repository does not establish a DataHub server-side Skill registry or a stable remote execution API.

> **V-O:** The MFE skills produce frontend work and are outside this phase's explicit scope.

> **I:** Reuse an existing interaction skill only if a later approved agent workflow matches it; do not create a CHRONOS-specific Skill now because no agent workflow has been authorized or specified.

> **U:** Whether CHRONOS will ever need to trigger Skills is not yet established.

## 8. Metadata Write Options

| Write path | Purpose and when to use | Atomicity/versioning | Validation and rollback | Recommendation | Status |
|---|---|---|---|---|---|
| MCP through GMS/REST | Current aspect-level write unit; normal SDK/ingestion path | One MCP targets one aspect; versioned aspects gain stored versions, while timeseries aspects follow their time semantics | GMS authenticates and validates before acceptance; no generic multi-MCP transaction rollback is documented | Preferred underlying write model through the Python SDK | V-O, I |
| MCP through Kafka | High-throughput asynchronous ingestion | One proposal per aspect; application is asynchronous | Direct Kafka bypasses GMS accept-time authentication/validation; rollback guarantee is not documented | Reserve for trusted, high-volume ingestion after broker controls and reconciliation exist | V-O, I |
| Python SDK | Typed entity/patch helpers and emitters | Helpers produce aspect-level updates; emitter mode controls acknowledgement, not a documented all-or-nothing multi-aspect transaction | SDK/GMS validation; caller handles failures and reconciliation | Preferred CHRONOS-facing write interface | V-O, I |
| GraphQL mutation | High-level UI-aligned edits such as ownership, tags, terms, domains, lineage, assertions, products, and structured properties | Per-mutation transactional scope is not specified as a general contract | Typed input validation; GraphQL errors must be inspected; generic rollback is not documented | Use only when a needed high-level mutation lacks a suitable SDK path | V-L, U, I |
| REST/OpenAPI | Explicit aspect/entity writes and version-aware HTTP integration | Aspect-scoped endpoints; batch all-or-nothing behavior is not documented | HTTP/GMS validation; conditional version header supported; generic rollback is not documented | Fallback for low-level cross-language operations | V-O, U, I |
| MCE | Deprecated snapshot containing multiple aspects | Multi-aspect payload; atomicity guarantee was not found | Deprecated event; general rollback guarantee not documented | Do not create a new dependency | V-O, U, I |

> **V-O:** After durable metadata application, DataHub emits Metadata Change Log events to Kafka for downstream indexing and reactions.

> **V-O:** MCE uses the deprecated Snapshot model, and Metadata Audit Event is also deprecated/not emitted; new dependencies should use MCP/MCL semantics.

> **U:** Official sources reviewed here do not promise a general transaction spanning multiple aspects, entities, GraphQL mutations, or OpenAPI batch members.

> **U:** Official sources reviewed here do not provide a universal arbitrary-write rollback API.

> **I:** When reversal is required, retain prior aspect values and issue a validated compensating MCP; treat ingestion-run rollback as a separate operator feature, not a universal transaction guarantee.

## 9. Performance Comparison

> **U:** No official, controlled benchmark comparing GraphQL, Python SDK, OpenAPI, MCP Server, and CLI on the same workload was found.

> **I:** The rankings below are ordinal engineering expectations derived from transport shape and official usage guidance; they must be benchmarked with production-shaped data before becoming SLO claims.

| Workload | Rank, best to least suitable | Basis | Status |
|---|---|---|---|
| Targeted entity read | GraphQL → Python SDK → OpenAPI → MCP Server → CLI | Field selection lowers response size; SDK adds typed convenience; MCP/CLI add orchestration/process overhead | I |
| Bulk metadata retrieval | Python SDK → OpenAPI scroll/batch → GraphQL scroll/batch → MCP Server → CLI | SDK officially recommended for bulk; MCP has context budgets | I |
| Large lineage traversal | Python SDK → GraphQL `scrollAcrossLineage` → MCP Server → CLI → raw relationship OpenAPI | SDK is officially recommended; GraphQL has dedicated scroll semantics | I |
| Controlled metadata update | Python SDK via GMS → OpenAPI → GraphQL mutation → MCP mutation → CLI | Typed SDK plus authenticated GMS gives the clearest deterministic write path | I |
| Maximum streaming throughput | Direct Kafka MCP → SDK REST async → OpenAPI/REST async → GraphQL → MCP/CLI | Direct broker path avoids synchronous request handling but sacrifices accept-time auth/validation and immediate visibility | I |
| Lowest network overhead for selected nested fields | GraphQL → SDK/OpenAPI → MCP → CLI | GraphQL selects fields; MCP may add model-oriented context | I |
| Lowest client memory risk for deep result sets | Any correctly paginated scroll client; no universal winner | Page size and retained objects dominate interface label | I |
| Ease of deterministic Python implementation | Python SDK → GraphQL client → OpenAPI client → CLI → MCP | SDK offers native models and helpers; MCP requires an agent/tool runtime | I |

> **V-O:** Primary-key entity reads are served from the relational store, secondary/search queries from the search index, and lineage/relationship queries from the graph index. See [metadata serving](https://docs.datahub.com/docs/architecture/metadata-serving).

> **I:** Interface choice does not remove server-side search/index latency; asynchronous writes can become durable before secondary indexes are observable.

> **I:** Cache immutable reference data or explicitly versioned results only when staleness is acceptable; do not cache ownership, quality, or lineage without a freshness policy.

## 10. Decision Matrix

> **I:** Each operation below has exactly one preferred interface. These are interface recommendations, not a CHRONOS application design.

| Future operation | Exactly one preferred interface | Why | Status |
|---|---|---|---|
| Retrieve dataset | Python SDK | Typed entity retrieval and reusable entity model | I |
| Retrieve schema | Python SDK | Typed dataset schema plus low-level aspect fallback | I |
| Retrieve ownership | Python SDK | Direct typed ownership access and owner filtering | I |
| Retrieve glossary | Python SDK | Typed terms plus glossary-term search filters | I |
| Retrieve tags | Python SDK | Typed tags plus tag search filters | I |
| Retrieve domains | Python SDK | Typed domain access and domain filter DSL | I |
| Retrieve assertions | GraphQL | Locally verified typed assertion queries and run-oriented fields/mutations provide the clearest explicit surface | I |
| Retrieve lineage | Python SDK | Official lineage tutorial generally recommends it; multi-hop API is typed | I |
| Search entities | Python SDK | `SearchClient` and filter DSL provide the official programmatic search abstraction | I |
| Read dashboard metadata | GraphQL | Dashboard is a typed root with metadata and lineage fields in the deployed schema | I |
| Read pipeline metadata | GraphQL | `dataFlow` and `dataJob` are typed roots in the deployed schema | I |
| Read data products | GraphQL | Typed data-product query/mutation surface is locally verified | I |
| Read structured properties | GraphQL | Typed structured-property roots and entity fields are locally verified | I |
| Bulk metadata retrieval | Python SDK | SDKs are officially recommended for bulk operations; `get_entities_v2` supports selected aspects | I |
| Write metadata | Python SDK | Typed entity/MCP helpers use authenticated GMS and expose acknowledgement modes | I |
| Update metadata | Python SDK | Typed update/patch/upsert paths avoid raw aspect payload handling | I |
| Publish prevention records | No DataHub interface | “Prevention record” is not a verified official DataHub entity or aspect; selecting an interface would invent a capability | U |
| Trigger Skills | DataHub Skills host/runtime | Skills execute in a compatible agent host and are not triggered through GMS APIs | I |
| Agent context retrieval | MCP Server | It is the official interface specifically designed for model/agent context retrieval | I |

> **V-O:** Python SDK and GraphQL can coexist: the SDK is recommended for programmatic CRUD/bulk, while GraphQL is the primary high-level frontend interface.

> **I:** Coexistence should be operation-driven rather than using two interfaces for the same operation without a measured reason.

## 11. Best Practices

| Practice | Recommendation | Status |
|---|---|---|
| Connection management | Reuse long-lived HTTP/SDK clients, set explicit connect/read timeouts, and bound concurrency | I |
| Authentication | Use HTTPS outside local development, store PATs in a secret manager, prefer least-privilege service identities, rotate tokens, and never log them | I |
| Auth enforcement | Keep GMS authentication enabled and restrict direct Kafka access to trusted producers | V-O, I |
| Retry strategy | Retry only transient/idempotent work with bounded exponential backoff and jitter; honor server status and stop on authorization/validation failures | I |
| Write acknowledgement | Use synchronous acknowledgement where read-after-write correctness matters; use async only with reconciliation | V-O, I |
| GraphQL errors | Inspect both HTTP status and GraphQL `errors`; tolerate partial `data` only when explicitly safe | V-O, I |
| Pagination | Use search for shallow result pages and scroll with stable URN sorting for deep enumeration; persist scroll state only for the operation lifetime | V-O, I |
| Lineage bounds | Set direction, hop count, page count, time range, and entity filters explicitly | I |
| Field selection | Request only required GraphQL fields and only required aspects in SDK/OpenAPI bulk reads | V-O, I |
| Caching | Key caches by URN, aspect, and relevant version; define TTL/invalidation by metadata volatility | I |
| Read/write separation | Use read-optimized queries for inspection and explicit SDK MCP/patch calls for mutation; do not mutate as a side effect of a read | I |
| Interface ownership | Assign one preferred interface per operation and review exceptions during version upgrades | I |
| Schema discovery | Pin tested DataHub/CLI/SDK versions and diff GraphQL/OpenAPI schemas before upgrades | I |
| Testing | Test against a disposable DataHub instance with representative metadata, authorization cases, pagination, partial errors, and index-consistency delay | I |
| Contract tests | Verify endpoint availability, selected GraphQL fields, SDK signatures, and write/read-back behavior for every supported version | I |
| MCP/agent safety | Leave mutation tools disabled by default and require explicit confirmation/authorization before enabling them | V-O, I |

> **I:** A practical retry taxonomy is: no retry for 400/401/403 or GraphQL validation errors; conditional retry for 408/429/5xx and transport timeouts; idempotency must be established before repeating a write.

> **U:** Production gateway rate limits, timeout ceilings, token scopes, and DataHub edition are not yet known, so final numeric connection and retry settings cannot be selected in this phase.

## 12. Risks

| Risk | Evidence and consequence | Status |
|---|---|---|
| Version skew | Local server is `v1.5.0.6`; CLI/docs are 1.6.x, so a documented route or field may not exist locally | V-L, I |
| SDK v2 instability | Installed SDK explicitly emits an experimental stability warning | V-L |
| MCP not locally available | Local `/mcp` returns 404 and no separate server is installed | V-L |
| GraphQL evolution | GraphQL is high-level/UI-oriented; fields and mutations must be checked against the deployed schema | V-O, I |
| OpenAPI auth omission | Local specification has no declared security scheme although GMS auth docs require bearer tokens | V-L, V-O |
| Generated-client variability | Official OpenAPI guide says language support/maturity varies | V-O |
| Eventual index consistency | Kafka/MCL-driven search and graph indexing can lag durable storage, especially with async writes | V-O, I |
| Direct Kafka trust boundary | Direct producers bypass GMS accept-time authentication and validation | V-O |
| No generic rollback guarantee | No universal transaction/rollback contract was found | U |
| Unpublished GraphQL limits | No official rate or complexity ceiling was found | U |
| ACK semantic gaps | Prompt construction, caching, conversation state, and compression are not specified by the overview | U |
| Skills evolution and scope | Skills are host workflows and include out-of-scope frontend skills; they are not stable GMS APIs | V-O, I |
| Cloud/Core capability mismatch | Some assertions, quality workflows, MCP features, and managed OAuth capabilities are edition/version dependent | V-O |

## 13. Unknowns

- **U:** The production DataHub version, edition (Core or Cloud), topology, and upgrade policy.
- **U:** Production authentication method, PAT/service-account policy, token scopes, rotation interval, and authorization policies.
- **U:** Required read latency, write acknowledgement, index-freshness, availability, and recovery objectives.
- **U:** Expected entity counts, schema widths, lineage depth/fan-out, bulk sizes, and request concurrency.
- **U:** Whether “prevention record” is external domain terminology, a proposed new metadata type, or a mapping to an existing verified aspect.
- **U:** Whether CHRONOS will include any AI-agent interaction and therefore need MCP, ACK, or Skills.
- **U:** Whether a separate MCP server will be installed or the DataHub server upgraded to a version exposing the documented self-hosted route.
- **U:** Effective production GraphQL, gateway, load-balancer, and OpenAPI request limits.
- **U:** Which Python SDK release will be stable and supported when implementation begins.
- **U:** Required assertion/data-contract features and whether they are available in the selected Core/Cloud edition.
- **U:** Actual cross-interface latency, throughput, memory, and network measurements on production-shaped metadata.
- **U:** Required consistency and rollback behavior for multi-aspect or multi-entity updates.

## 14. Questions for Phase 0.4

1. **U:** Which exact DataHub server, CLI, Python SDK, and MCP Server versions will Phase 0.4 target?
2. **U:** Is the target DataHub Core or DataHub Cloud, and which licensed/edition-specific capabilities are available?
3. **U:** Which future operations are mandatory, and what consistency and latency objective applies to each?
4. **U:** What is a “prevention record,” and is there an approved official DataHub entity/aspect mapping?
5. **U:** What production-scale dataset, lineage, assertion, dashboard, and pipeline volumes should benchmarks reproduce?
6. **U:** Which service identity, scopes, policies, token rotation, and secret-storage controls are required?
7. **U:** Are direct Kafka writes prohibited, restricted to ingestion, or permitted for any trusted producer?
8. **U:** Must writes be immediately visible through primary-key reads, search, and lineage, or is eventual consistency acceptable?
9. **U:** What failure recovery is required across multiple aspects/entities, and is compensating-write recovery acceptable?
10. **U:** Does CHRONOS itself need agent context, or will MCP/ACK/Skills remain external operator tooling?
11. **U:** Should the local environment be upgraded and the official MCP server installed for a controlled compatibility test?
12. **U:** What rate, concurrency, timeout, and payload limits exist at the production gateway and DataHub services?
13. **U:** Which GraphQL fields and OpenAPI endpoints will be supported as a pinned compatibility contract?
14. **U:** Which test metadata may be written, deleted, or rolled back in a disposable Phase 0.4 environment?

> **I:** Phase 0.4 should answer these questions with deployed-version contract tests and production-shaped benchmarks before any CHRONOS design begins.
