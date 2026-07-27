"""Private read-only transport implementation.

This module deliberately exposes no create, update, delete, patch, upsert,
emit, mutation, or rollback operation.
"""

from __future__ import annotations

import json
import secrets
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Mapping, Protocol, Sequence

from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
from datahub.ingestion.graph.openapi import RelationshipDirection
from datahub.metadata.schema_classes import (
    CorpGroupInfoClass,
    CorpUserInfoClass,
    DataJobInputOutputClass,
    DocumentInfoClass,
    DomainPropertiesClass,
    DataPlatformInstanceClass,
    DatasetPropertiesClass,
    GlossaryNodeInfoClass,
    GlossaryTermInfoClass,
    SchemaMetadataClass,
    TagPropertiesClass,
    UpstreamLineageClass,
)
from datahub.metadata.urns import DatasetUrn

from .config import DataHubConfig
from .errors import (
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    ContextRelationshipUnavailable,
    FineGrainedLineageUnavailable,
    GovernanceRetrievalUnavailable,
    MalformedGovernanceAspect,
    UnexpectedDataHubError,
    redact_secrets,
)
from .schema_types import normalize_datahub_type


@dataclass(frozen=True)
class HealthObservation:
    reachable: bool
    healthy: bool
    latency_ms: float | None
    http_status: int | None
    diagnostic: str


@dataclass(frozen=True)
class EnvironmentObservation:
    gms_version: str | None
    sdk_version: str | None
    server_type: str | None
    server_environment: str | None
    diagnostic: str | None = None


@dataclass(frozen=True)
class DatasetIdentity:
    urn: str
    platform: str
    name: str
    environment: str


@dataclass(frozen=True)
class SchemaFieldObservation:
    name: str
    normalized_type: str
    native_type: str | None
    description: str | None = None
    schema_field_urn: str | None = None


@dataclass(frozen=True)
class SchemaFieldMetadataObservation:
    field_path: str | None
    datahub_type: str | None
    native_type: str | None
    description: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    is_partitioning_key: bool | None
    json_path: str | None
    label: str | None
    recursive: bool | None
    schema_field_urn: str | None = None


@dataclass(frozen=True)
class SchemaMetadataObservation:
    dataset_urn: str
    schema_name: str | None
    platform: str | None
    version: int | None
    schema_hash: str | None
    fields: tuple[SchemaFieldMetadataObservation, ...]
    created_time: int | None
    last_modified_time: int | None
    dataset_reference: str | None
    cluster: str | None
    primary_keys: tuple[str, ...] | None


@dataclass(frozen=True)
class LineageEntityObservation:
    urn: str
    entity_type: str
    degree: int


@dataclass(frozen=True)
class FineGrainedLineageGroupObservation:
    source_entity_urn: str
    source_entity_type: str
    source_aspect: str
    group_index: int
    upstream_type: str | None
    downstream_type: str | None
    upstreams: tuple[object, ...]
    downstreams: tuple[object, ...]
    transform_operation: object | None
    confidence_score: object | None
    query: object | None
    match_type: object | None


@dataclass(frozen=True)
class FineGrainedLineageAspectObservation:
    source_entity_urn: str
    source_entity_type: str
    source_aspect: str
    interface: str
    groups: tuple[FineGrainedLineageGroupObservation, ...]


@dataclass(frozen=True)
class OwnerAssignmentObservation:
    owner_urn: str
    owner_kind: str
    ownership_type: str | None
    ownership_type_urn: str | None


@dataclass(frozen=True)
class FieldGovernanceObservation:
    field_path: str
    tag_urns: tuple[str, ...]
    term_urns: tuple[str, ...]


@dataclass(frozen=True)
class GovernanceAspectObservation:
    dataset_urn: str
    owners: tuple[OwnerAssignmentObservation, ...]
    domain_urns: tuple[str, ...]
    tag_urns: tuple[str, ...]
    term_urns: tuple[str, ...]
    field_governance: tuple[FieldGovernanceObservation, ...]
    interface: str


@dataclass(frozen=True)
class MetadataReferenceObservation:
    urn: str
    entity_type: str
    name: str | None
    parent_urn: str | None
    resolved: bool
    interface: str


@dataclass(frozen=True)
class StructuredPropertyDefinitionObservation:
    property_urn: str
    qualified_name: str
    display_name: str | None
    value_type: str
    value_type_urn: str
    interface: str


@dataclass(frozen=True)
class StructuredPropertyAssignmentObservation:
    property_urn: str
    qualified_name: str
    display_name: str | None
    value_type: str
    value_type_urn: str
    values: tuple[str | float, ...]
    assignment_target: str
    interface: str


@dataclass(frozen=True)
class DataProductMembershipObservation:
    product_urn: str
    name: str
    asset_urn: str
    relationship: str
    interface: str


@dataclass(frozen=True)
class DocumentRelationshipObservation:
    document_urn: str
    title: str | None
    related_asset_urn: str
    relationship: str
    interface: str


@dataclass(frozen=True)
class PipelineEntityObservation:
    job_urn: str
    job_name: str
    job_platform: str | None
    flow_urn: str | None
    flow_name: str | None
    flow_platform: str | None
    interface: str


@dataclass(frozen=True)
class ContextLineageEntityObservation:
    urn: str
    entity_type: str
    degree: int
    interface: str


@dataclass(frozen=True)
class BusinessIntelligenceEntityObservation:
    urn: str
    entity_type: str
    platform: str
    name: str
    interface: str


@dataclass(frozen=True)
class DatasetMetadataObservation:
    urn: str
    platform: str
    environment: str
    urn_name: str
    logical_name: str
    schema_name: str
    properties_qualified_name: str | None
    platform_instance: str | None


class AuthenticationEnforcement(str, Enum):
    ENFORCED = "enforced"
    NOT_ENFORCED = "not_enforced"


@dataclass(frozen=True)
class AuthenticationObservation:
    principal: str
    enforcement: AuthenticationEnforcement
    diagnostic: str


class ReadOnlyTransport(Protocol):
    def health(self) -> HealthObservation: ...

    def authentication(self) -> AuthenticationObservation: ...

    def environment_information(self) -> EnvironmentObservation: ...

    def graphql_type_fields(self) -> Mapping[str, frozenset[str]]: ...

    def search_dataset_urns(
        self, *, platform: str, environment: str, query: str
    ) -> Sequence[str]: ...

    def dataset_identity(self, urn: str) -> DatasetIdentity: ...

    def dataset_metadata(self, urn: str) -> DatasetMetadataObservation: ...

    def schema_fields(self, urn: str) -> Sequence[SchemaFieldObservation]: ...

    def schema_metadata(self, urn: str) -> SchemaMetadataObservation | None: ...


class LineageReadOnlyTransport(ReadOnlyTransport, Protocol):
    """Phase 1.4 extension that does not widen earlier public boundaries."""

    def direct_downstream_lineage_entities(
        self,
        dataset_urn: str,
    ) -> Sequence[LineageEntityObservation]: ...

    def fine_grained_lineage(
        self,
        entity_urn: str,
        entity_type: str,
    ) -> FineGrainedLineageAspectObservation | None: ...

    def schema_field_exists(self, schema_field_urn: str) -> bool: ...


class ContextReadOnlyTransport(LineageReadOnlyTransport, Protocol):
    """Phase 1.5 read-only extension for stored business context."""

    def governance_aspects(
        self,
        dataset_urn: str,
    ) -> GovernanceAspectObservation: ...

    def metadata_reference(
        self,
        urn: str,
        entity_type: str,
    ) -> MetadataReferenceObservation: ...

    def structured_property_definitions(
        self,
    ) -> Sequence[StructuredPropertyDefinitionObservation]: ...

    def structured_property_assignments(
        self,
        dataset_urn: str,
    ) -> Sequence[StructuredPropertyAssignmentObservation]: ...

    def data_product_memberships(
        self,
        asset_urn: str,
    ) -> Sequence[DataProductMembershipObservation]: ...

    def related_documents(
        self,
        asset_urn: str,
    ) -> Sequence[DocumentRelationshipObservation]: ...

    def pipeline_entity(
        self,
        job_urn: str,
    ) -> PipelineEntityObservation | None: ...

    def direct_context_lineage_entities(
        self,
        entity_urn: str,
    ) -> Sequence[ContextLineageEntityObservation]: ...

    def business_intelligence_entity(
        self,
        urn: str,
        entity_type: str,
    ) -> BusinessIntelligenceEntityObservation | None: ...


_CAPABILITY_QUERY = """
query ChronosCapabilityProbe {
  __schema {
    types {
      name
      fields { name }
    }
  }
}
"""

_AUTH_QUERY = """
query ChronosAuthenticationProbe {
  me { corpUser { urn } }
}
"""

_DIRECT_DOWNSTREAM_LINEAGE_QUERY = """
query ChronosDirectDownstreamLineage(
  $urn: String!
  $scrollId: String
) {
  scrollAcrossLineage(
    input: {
      urn: $urn
      direction: DOWNSTREAM
      types: [DATASET, DATA_JOB]
      query: "*"
      count: 500
      scrollId: $scrollId
    }
  ) {
    nextScrollId
    isPartial
    searchResults {
      degree
      entity { urn type }
    }
  }
}
"""

_STRUCTURED_PROPERTY_DEFINITIONS_QUERY = """
query ChronosStructuredPropertyDefinitions($start: Int!) {
  searchAcrossEntities(
    input: {
      types: [STRUCTURED_PROPERTY]
      query: "*"
      start: $start
      count: 100
    }
  ) {
    total
    searchResults {
      entity {
        ... on StructuredPropertyEntity {
          urn
          definition {
            qualifiedName
            displayName
            valueType {
              urn
              info { type qualifiedName displayName }
            }
          }
        }
      }
    }
  }
}
"""

_STRUCTURED_PROPERTY_ASSIGNMENTS_QUERY = """
query ChronosStructuredPropertyAssignments($urn: String!) {
  dataset(urn: $urn) {
    structuredProperties {
      properties {
        associatedUrn
        structuredProperty {
          urn
          definition {
            qualifiedName
            displayName
            valueType {
              urn
              info { type qualifiedName displayName }
            }
          }
        }
        values {
          ... on StringValue { stringValue }
          ... on NumberValue { numberValue }
        }
      }
    }
  }
}
"""

_DATA_PRODUCT_MEMBERSHIPS_QUERY = """
query ChronosDataProductMemberships($urn: String!) {
  dataset(urn: $urn) {
    relationships(
      input: {
        types: ["DataProductContains"]
        direction: INCOMING
        start: 0
        count: 100
      }
    ) {
      total
      relationships {
        type
        direction
        entity {
          urn
          type
          ... on DataProduct { properties { name } }
        }
      }
    }
  }
}
"""

_PIPELINE_ENTITY_QUERY = """
query ChronosPipelineEntity($urn: String!) {
  dataJob(urn: $urn) {
    urn
    jobId
    properties { name }
    platform { name }
    dataFlow {
      urn
      flowId
      properties { name }
      platform { name }
    }
  }
}
"""

_DIRECT_CONTEXT_LINEAGE_QUERY = """
query ChronosDirectContextLineage(
  $urn: String!
  $scrollId: String
) {
  scrollAcrossLineage(
    input: {
      urn: $urn
      direction: DOWNSTREAM
      types: [DATASET, CHART, DASHBOARD]
      query: "*"
      count: 500
      scrollId: $scrollId
    }
  ) {
    nextScrollId
    isPartial
    searchResults {
      degree
      entity { urn type }
    }
  }
}
"""

_CHART_CONTEXT_QUERY = """
query ChronosChartContext($urn: String!) {
  chart(urn: $urn) {
    urn
    tool
    properties { name }
    platform { name properties { displayName } }
  }
}
"""

_DASHBOARD_CONTEXT_QUERY = """
query ChronosDashboardContext($urn: String!) {
  dashboard(urn: $urn) {
    urn
    tool
    properties { name }
    platform { name properties { displayName } }
  }
}
"""

_CONFIGURED_CREDENTIAL = object()


class DataHubSdkReadOnlyTransport:
    """Concrete read-only adapter over the official SDK and GraphQL."""

    def __init__(self, config: DataHubConfig) -> None:
        self._config = config
        self._graph = DataHubGraph(
            DatahubClientConfig(
                server=config.gms_url,
                token=config._credential,
                timeout_sec=config.timeout_seconds,
            )
        )

    def health(self) -> HealthObservation:
        started = time.perf_counter()
        request = urllib.request.Request(
            f"{self._config.gms_url}/health",
            method="GET",
            headers={"User-Agent": "chronos-datahub-gate/0.1"},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.timeout_seconds
            ) as response:
                response.read(1024)
                latency = (time.perf_counter() - started) * 1000
                status = int(response.status)
                return HealthObservation(
                    reachable=True,
                    healthy=200 <= status < 300,
                    latency_ms=round(latency, 3),
                    http_status=status,
                    diagnostic="GMS health endpoint responded.",
                )
        except urllib.error.HTTPError as exc:
            latency = (time.perf_counter() - started) * 1000
            return HealthObservation(
                reachable=True,
                healthy=False,
                latency_ms=round(latency, 3),
                http_status=exc.code,
                diagnostic=f"GMS health endpoint returned HTTP {exc.code}.",
            )
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise ConnectionError(
                "DataHub GMS is unreachable.",
                diagnostic=redact_secrets(exc, (self._config._credential,)),
            ) from exc

    def authentication(self) -> AuthenticationObservation:
        data = self._graphql_request(_AUTH_QUERY)
        principal = _principal_from_auth_response(data)

        invalid_credential = secrets.token_urlsafe(32)
        invalid_succeeded = self._authentication_probe_succeeded(
            token=invalid_credential
        )
        anonymous_succeeded = self._authentication_probe_succeeded(token=None)

        if invalid_succeeded and anonymous_succeeded:
            return AuthenticationObservation(
                principal=principal,
                enforcement=AuthenticationEnforcement.NOT_ENFORCED,
                diagnostic=(
                    "Configured, anonymous, and invalid-credential metadata "
                    "reads succeeded."
                ),
            )
        if not invalid_succeeded and not anonymous_succeeded:
            return AuthenticationObservation(
                principal=principal,
                enforcement=AuthenticationEnforcement.ENFORCED,
                diagnostic=(
                    "Configured metadata read succeeded and unauthenticated "
                    "probes were rejected."
                ),
            )
        raise UnexpectedDataHubError(
            "DataHub authentication enforcement produced inconsistent results.",
            diagnostic=(
                "Anonymous and invalid-credential probes did not produce the "
                "same access result."
            ),
        )

    def _authentication_probe_succeeded(self, *, token: str | None) -> bool:
        try:
            data = self._graphql_request(_AUTH_QUERY, token=token)
            _principal_from_auth_response(data)
            return True
        except (AuthenticationError, AuthorizationError):
            return False

    def environment_information(self) -> EnvironmentObservation:
        try:
            server_config = self._graph.get_server_config()
            version_info = (
                server_config.get("versions", {})
                .get("acryldata/datahub", {})
                .get("version")
            )
            datahub_info = server_config.get("datahub", {})
            try:
                sdk_version = version("acryl-datahub")
            except PackageNotFoundError:
                sdk_version = None
            return EnvironmentObservation(
                gms_version=version_info,
                sdk_version=sdk_version,
                server_type=datahub_info.get("serverType"),
                server_environment=datahub_info.get("serverEnv"),
            )
        except Exception as exc:  # informational check; caller decides severity
            return EnvironmentObservation(
                gms_version=None,
                sdk_version=None,
                server_type=None,
                server_environment=None,
                diagnostic=redact_secrets(exc, (self._config._credential,)),
            )

    def graphql_type_fields(self) -> Mapping[str, frozenset[str]]:
        data = self._graphql_request(_CAPABILITY_QUERY)
        try:
            types = data["__schema"]["types"]
        except (KeyError, TypeError) as exc:
            raise UnexpectedDataHubError(
                "GraphQL capability response was incomplete."
            ) from exc
        result: dict[str, frozenset[str]] = {}
        for item in types:
            name = item.get("name")
            if not name:
                continue
            result[name] = frozenset(
                field.get("name")
                for field in (item.get("fields") or [])
                if field.get("name")
            )
        return result

    def search_dataset_urns(
        self, *, platform: str, environment: str, query: str
    ) -> Sequence[str]:
        try:
            return tuple(
                self._graph.get_urns_by_filter(
                    entity_types=["dataset"],
                    platform=platform,
                    env=environment,
                    query=query,
                    batch_size=100,
                    skip_cache=True,
                )
            )
        except Exception as exc:
            raise self._classify_sdk_exception(
                exc, "Dataset search failed."
            ) from exc

    def dataset_identity(self, urn: str) -> DatasetIdentity:
        try:
            parsed = DatasetUrn.from_string(urn)
            platform = str(parsed.platform)
            if platform.startswith("urn:li:dataPlatform:"):
                platform = platform.rsplit(":", 1)[-1]
            return DatasetIdentity(
                urn=urn,
                platform=platform,
                name=parsed.name,
                environment=parsed.env,
            )
        except Exception as exc:
            raise UnexpectedDataHubError(
                "DataHub returned an invalid dataset URN.",
                diagnostic=redact_secrets(exc, (self._config._credential,)),
            ) from exc

    def dataset_metadata(self, urn: str) -> DatasetMetadataObservation:
        try:
            parsed = self.dataset_identity(urn)
            properties = self._graph.get_aspect(urn, DatasetPropertiesClass)
            platform_instance = self._graph.get_aspect(
                urn,
                DataPlatformInstanceClass,
            )
            schema = self._graph.get_aspect(urn, SchemaMetadataClass)
        except Exception as exc:
            if isinstance(exc, UnexpectedDataHubError):
                raise
            raise self._classify_sdk_exception(
                exc,
                "Dataset identity metadata read failed.",
            ) from exc

        if properties is None or not properties.name:
            raise UnexpectedDataHubError(
                "Dataset properties required for identity verification are absent."
            )
        if platform_instance is None or not platform_instance.platform:
            raise UnexpectedDataHubError(
                "Dataset platform metadata required for identity verification is absent."
            )
        if schema is None or not schema.schemaName:
            raise UnexpectedDataHubError(
                "Dataset schema metadata required for identity verification is absent."
            )

        observed_platform = platform_instance.platform
        if observed_platform.startswith("urn:li:dataPlatform:"):
            observed_platform = observed_platform.rsplit(":", 1)[-1]

        return DatasetMetadataObservation(
            urn=urn,
            platform=observed_platform,
            environment=parsed.environment,
            urn_name=parsed.name,
            logical_name=properties.name,
            schema_name=schema.schemaName,
            properties_qualified_name=properties.qualifiedName,
            platform_instance=platform_instance.instance,
        )

    def schema_fields(self, urn: str) -> Sequence[SchemaFieldObservation]:
        aspect = self.schema_metadata(urn)
        if aspect is None:
            return ()
        return tuple(
            SchemaFieldObservation(
                name=field.field_path or "",
                normalized_type=normalize_datahub_type(
                    field.datahub_type
                ).value,
                native_type=field.native_type,
                description=field.description,
                schema_field_urn=field.schema_field_urn,
            )
            for field in aspect.fields
        )

    def schema_metadata(self, urn: str) -> SchemaMetadataObservation | None:
        try:
            aspect = self._graph.get_aspect(urn, SchemaMetadataClass)
        except Exception as exc:
            raise self._classify_sdk_exception(
                exc, "Schema metadata read failed."
            ) from exc
        if aspect is None:
            return None

        fields = tuple(
            SchemaFieldMetadataObservation(
                field_path=getattr(field, "fieldPath", None),
                datahub_type=_datahub_type_name(field),
                native_type=getattr(field, "nativeDataType", None),
                description=getattr(field, "description", None),
                nullable=getattr(field, "nullable", None),
                is_part_of_key=getattr(field, "isPartOfKey", None),
                is_partitioning_key=getattr(
                    field,
                    "isPartitioningKey",
                    None,
                ),
                json_path=getattr(field, "jsonPath", None),
                label=getattr(field, "label", None),
                recursive=getattr(field, "recursive", None),
            )
            for field in (getattr(aspect, "fields", None) or ())
        )
        primary_keys = getattr(aspect, "primaryKeys", None)
        return SchemaMetadataObservation(
            dataset_urn=urn,
            schema_name=getattr(aspect, "schemaName", None),
            platform=getattr(aspect, "platform", None),
            version=getattr(aspect, "version", None),
            schema_hash=getattr(aspect, "hash", None),
            fields=fields,
            created_time=_audit_time(getattr(aspect, "created", None)),
            last_modified_time=_audit_time(
                getattr(aspect, "lastModified", None)
            ),
            dataset_reference=getattr(aspect, "dataset", None),
            cluster=getattr(aspect, "cluster", None),
            primary_keys=(
                tuple(str(item) for item in primary_keys)
                if primary_keys is not None
                else None
            ),
        )

    def direct_downstream_lineage_entities(
        self,
        dataset_urn: str,
    ) -> Sequence[LineageEntityObservation]:
        results: dict[tuple[str, str], LineageEntityObservation] = {}
        scroll_id: str | None = None
        seen_scroll_ids: set[str] = set()
        while True:
            data = self._graphql_request(
                _DIRECT_DOWNSTREAM_LINEAGE_QUERY,
                variables={
                    "urn": dataset_urn,
                    "scrollId": scroll_id,
                },
            )
            try:
                page = data["scrollAcrossLineage"]
                if page.get("isPartial") is True:
                    raise FineGrainedLineageUnavailable(
                        "DataHub returned a partial lineage page.",
                    )
                for item in page["searchResults"]:
                    entity = item["entity"]
                    degree = item["degree"]
                    entity_urn = entity["urn"]
                    entity_type = entity["type"]
                    if (
                        degree == 1
                        and entity_type in {"DATASET", "DATA_JOB"}
                        and isinstance(entity_urn, str)
                        and entity_urn
                    ):
                        results[(entity_type, entity_urn)] = (
                            LineageEntityObservation(
                                urn=entity_urn,
                                entity_type=entity_type,
                                degree=degree,
                            )
                        )
                next_scroll_id = page.get("nextScrollId")
            except FineGrainedLineageUnavailable:
                raise
            except (KeyError, TypeError) as exc:
                raise FineGrainedLineageUnavailable(
                    "DataHub lineage response was incomplete.",
                ) from exc
            if next_scroll_id is None:
                break
            if (
                not isinstance(next_scroll_id, str)
                or not next_scroll_id
                or next_scroll_id in seen_scroll_ids
            ):
                raise FineGrainedLineageUnavailable(
                    "DataHub lineage pagination cursor was invalid.",
                )
            seen_scroll_ids.add(next_scroll_id)
            scroll_id = next_scroll_id
        return tuple(
            results[key]
            for key in sorted(results)
        )

    def fine_grained_lineage(
        self,
        entity_urn: str,
        entity_type: str,
    ) -> FineGrainedLineageAspectObservation | None:
        normalized_type = entity_type.upper()
        if normalized_type == "DATASET":
            aspect_class = UpstreamLineageClass
            aspect_name = "upstreamLineage"
        elif normalized_type == "DATA_JOB":
            aspect_class = DataJobInputOutputClass
            aspect_name = "dataJobInputOutput"
        else:
            raise FineGrainedLineageUnavailable(
                "Fine-grained lineage is unsupported for this entity type.",
                diagnostic=f"Entity type: {entity_type}.",
            )
        try:
            aspect = self._graph.get_aspect(entity_urn, aspect_class)
        except Exception as exc:
            raise self._classify_sdk_exception(
                exc,
                "Fine-grained lineage aspect read failed.",
            ) from exc
        if aspect is None:
            return None

        raw_groups = getattr(aspect, "fineGrainedLineages", None) or ()
        groups = tuple(
            FineGrainedLineageGroupObservation(
                source_entity_urn=entity_urn,
                source_entity_type=normalized_type,
                source_aspect=aspect_name,
                group_index=index,
                upstream_type=_optional_string(
                    getattr(group, "upstreamType", None)
                ),
                downstream_type=_optional_string(
                    getattr(group, "downstreamType", None)
                ),
                upstreams=tuple(getattr(group, "upstreams", None) or ()),
                downstreams=tuple(
                    getattr(group, "downstreams", None) or ()
                ),
                transform_operation=getattr(
                    group,
                    "transformOperation",
                    None,
                ),
                confidence_score=getattr(group, "confidenceScore", None),
                query=getattr(group, "query", None),
                match_type=getattr(group, "matchType", None),
            )
            for index, group in enumerate(raw_groups)
        )
        return FineGrainedLineageAspectObservation(
            source_entity_urn=entity_urn,
            source_entity_type=normalized_type,
            source_aspect=aspect_name,
            interface=(
                f"DataHubGraph.get_aspect({aspect_class.__name__})"
            ),
            groups=groups,
        )

    def schema_field_exists(self, schema_field_urn: str) -> bool:
        try:
            return self._graph.exists(schema_field_urn)
        except Exception as exc:
            raise self._classify_sdk_exception(
                exc,
                "Schema-field existence read failed.",
            ) from exc

    def governance_aspects(
        self,
        dataset_urn: str,
    ) -> GovernanceAspectObservation:
        aspect_names = (
            "ownership",
            "domains",
            "globalTags",
            "glossaryTerms",
            "editableSchemaMetadata",
        )
        try:
            aspects = self._graph.get_entity_semityped(
                dataset_urn,
                aspects=list(aspect_names),
            )
            ownership = aspects.get("ownership")
            domains = aspects.get("domains")
            tags = aspects.get("globalTags")
            terms = aspects.get("glossaryTerms")
            editable_schema = aspects.get("editableSchemaMetadata")
            owners = tuple(
                OwnerAssignmentObservation(
                    owner_urn=_required_string(
                        getattr(owner, "owner", None),
                        "Ownership owner URN",
                    ),
                    owner_kind=_owner_kind(
                        _required_string(
                            getattr(owner, "owner", None),
                            "Ownership owner URN",
                        )
                    ),
                    ownership_type=_optional_string(
                        getattr(owner, "type", None)
                    ),
                    ownership_type_urn=_optional_string(
                        getattr(owner, "typeUrn", None)
                    ),
                )
                for owner in (
                    getattr(ownership, "owners", None) or ()
                )
            )
            domain_urns = _sorted_required_urns(
                getattr(domains, "domains", None) or (),
                "Domain reference",
            )
            tag_urns = _association_urns(
                getattr(tags, "tags", None) or (),
                "tag",
                "Tag reference",
            )
            term_urns = _association_urns(
                getattr(terms, "terms", None) or (),
                "urn",
                "Glossary term reference",
            )
            field_governance = tuple(
                sorted(
                    (
                        FieldGovernanceObservation(
                            field_path=_required_string(
                                getattr(field, "fieldPath", None),
                                "Field governance path",
                            ),
                            tag_urns=_association_urns(
                                getattr(
                                    getattr(field, "globalTags", None),
                                    "tags",
                                    None,
                                )
                                or (),
                                "tag",
                                "Field tag reference",
                            ),
                            term_urns=_association_urns(
                                getattr(
                                    getattr(field, "glossaryTerms", None),
                                    "terms",
                                    None,
                                )
                                or (),
                                "urn",
                                "Field glossary term reference",
                            ),
                        )
                        for field in (
                            getattr(
                                editable_schema,
                                "editableSchemaFieldInfo",
                                None,
                            )
                            or ()
                        )
                        if (
                            getattr(field, "globalTags", None) is not None
                            or getattr(field, "glossaryTerms", None) is not None
                        )
                    ),
                    key=lambda item: item.field_path,
                )
            )
        except MalformedGovernanceAspect:
            raise
        except Exception as exc:
            raise GovernanceRetrievalUnavailable(
                "Dataset governance metadata could not be retrieved.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc
        return GovernanceAspectObservation(
            dataset_urn=dataset_urn,
            owners=tuple(
                sorted(
                    owners,
                    key=lambda item: (
                        item.owner_urn,
                        item.ownership_type or "",
                        item.ownership_type_urn or "",
                    ),
                )
            ),
            domain_urns=domain_urns,
            tag_urns=tag_urns,
            term_urns=term_urns,
            field_governance=field_governance,
            interface=(
                "DataHubGraph.get_entity_semityped("
                "ownership,domains,globalTags,glossaryTerms,"
                "editableSchemaMetadata)"
            ),
        )

    def metadata_reference(
        self,
        urn: str,
        entity_type: str,
    ) -> MetadataReferenceObservation:
        normalized_type = entity_type.upper()
        mapping: dict[str, tuple[type, str, str | None]] = {
            "CORP_USER": (CorpUserInfoClass, "corpUserInfo", None),
            "CORP_GROUP": (CorpGroupInfoClass, "corpGroupInfo", None),
            "DOMAIN": (DomainPropertiesClass, "domainProperties", "parentDomain"),
            "TAG": (TagPropertiesClass, "tagProperties", None),
            "GLOSSARY_TERM": (
                GlossaryTermInfoClass,
                "glossaryTermInfo",
                "parentNode",
            ),
            "GLOSSARY_NODE": (
                GlossaryNodeInfoClass,
                "glossaryNodeInfo",
                "parentNode",
            ),
        }
        selected = mapping.get(normalized_type)
        if selected is None:
            raise GovernanceRetrievalUnavailable(
                "Unsupported governance reference type.",
                diagnostic=f"Entity type: {entity_type}.",
            )
        aspect_type, aspect_name, parent_attribute = selected
        try:
            aspect = self._graph.get_aspect(urn, aspect_type)
        except Exception as exc:
            raise GovernanceRetrievalUnavailable(
                "Governance reference could not be resolved.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc
        name = _reference_name(normalized_type, aspect)
        parent_urn = (
            _optional_string(getattr(aspect, parent_attribute, None))
            if aspect is not None and parent_attribute is not None
            else None
        )
        return MetadataReferenceObservation(
            urn=urn,
            entity_type=normalized_type,
            name=name,
            parent_urn=parent_urn,
            resolved=aspect is not None and name is not None,
            interface=f"DataHubGraph.get_aspect({aspect_name})",
        )

    def structured_property_definitions(
        self,
    ) -> Sequence[StructuredPropertyDefinitionObservation]:
        results: dict[str, StructuredPropertyDefinitionObservation] = {}
        start = 0
        while True:
            data = self._graphql_request(
                _STRUCTURED_PROPERTY_DEFINITIONS_QUERY,
                variables={"start": start},
            )
            try:
                page = data["searchAcrossEntities"]
                items = page["searchResults"]
                total = page["total"]
                for item in items:
                    entity = item["entity"]
                    observation = _structured_property_definition(entity)
                    results[observation.property_urn] = observation
            except (KeyError, TypeError, ValueError) as exc:
                raise MalformedGovernanceAspect(
                    "Structured-property definition response was malformed.",
                    diagnostic=redact_secrets(
                        exc,
                        (self._config._credential,),
                    ),
                ) from exc
            start += len(items)
            if start >= total:
                break
            if not items:
                raise GovernanceRetrievalUnavailable(
                    "Structured-property definition pagination stalled."
                )
        return tuple(results[key] for key in sorted(results))

    def structured_property_assignments(
        self,
        dataset_urn: str,
    ) -> Sequence[StructuredPropertyAssignmentObservation]:
        data = self._graphql_request(
            _STRUCTURED_PROPERTY_ASSIGNMENTS_QUERY,
            variables={"urn": dataset_urn},
        )
        try:
            dataset = data["dataset"]
            if dataset is None:
                raise KeyError("dataset")
            container = dataset.get("structuredProperties") or {}
            items = container.get("properties") or ()
            observations = tuple(
                _structured_property_assignment(item) for item in items
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedGovernanceAspect(
                "Structured-property assignment response was malformed.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc
        return tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.property_urn,
                    tuple(str(value) for value in item.values),
                ),
            )
        )

    def data_product_memberships(
        self,
        asset_urn: str,
    ) -> Sequence[DataProductMembershipObservation]:
        data = self._graphql_request(
            _DATA_PRODUCT_MEMBERSHIPS_QUERY,
            variables={"urn": asset_urn},
        )
        try:
            dataset = data["dataset"]
            if dataset is None:
                raise KeyError("dataset")
            page = dataset["relationships"]
            items = page["relationships"]
            if page["total"] > len(items):
                raise ContextRelationshipUnavailable(
                    "Data-product membership response exceeded its bound."
                )
            observations = []
            for item in items:
                entity = item["entity"]
                if (
                    item["type"] != "DataProductContains"
                    or item["direction"] != "INCOMING"
                    or entity["type"] != "DATA_PRODUCT"
                ):
                    continue
                observations.append(
                    DataProductMembershipObservation(
                        product_urn=_required_response_string(
                            entity.get("urn"),
                            "Data product URN",
                        ),
                        name=_required_response_string(
                            (entity.get("properties") or {}).get("name"),
                            "Data product name",
                        ),
                        asset_urn=asset_urn,
                        relationship="DataProductContains",
                        interface=(
                            "GraphQL Dataset.relationships("
                            "DataProductContains,INCOMING)"
                        ),
                    )
                )
        except ContextRelationshipUnavailable:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ContextRelationshipUnavailable(
                "Data-product membership response was malformed.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc
        return tuple(
            sorted(observations, key=lambda item: item.product_urn)
        )

    def related_documents(
        self,
        asset_urn: str,
    ) -> Sequence[DocumentRelationshipObservation]:
        try:
            related = tuple(
                self._graph.get_related_entities(
                    asset_urn,
                    ["RelatedAsset"],
                    RelationshipDirection.INCOMING,
                )
            )
            observations = []
            for item in related:
                document_urn = _required_string(
                    getattr(item, "urn", None),
                    "Related document URN",
                )
                info = self._graph.get_aspect(
                    document_urn,
                    DocumentInfoClass,
                )
                if info is None:
                    observations.append(
                        DocumentRelationshipObservation(
                            document_urn=document_urn,
                            title=None,
                            related_asset_urn=asset_urn,
                            relationship="RelatedAsset",
                            interface=(
                                "DataHubGraph.get_related_entities("
                                "RelatedAsset,INCOMING)"
                            ),
                        )
                    )
                    continue
                observations.append(
                    DocumentRelationshipObservation(
                        document_urn=document_urn,
                        title=_optional_string(getattr(info, "title", None)),
                        related_asset_urn=asset_urn,
                        relationship="RelatedAsset",
                        interface=(
                            "DataHubGraph.get_related_entities("
                            "RelatedAsset,INCOMING) + "
                            "DataHubGraph.get_aspect(documentInfo)"
                        ),
                    )
                )
        except MalformedGovernanceAspect:
            raise
        except Exception as exc:
            raise ContextRelationshipUnavailable(
                "Related documents could not be retrieved.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc
        return tuple(
            sorted(observations, key=lambda item: item.document_urn)
        )

    def pipeline_entity(
        self,
        job_urn: str,
    ) -> PipelineEntityObservation | None:
        data = self._graphql_request(
            _PIPELINE_ENTITY_QUERY,
            variables={"urn": job_urn},
        )
        try:
            job = data["dataJob"]
            if job is None:
                return None
            flow = job.get("dataFlow")
            return PipelineEntityObservation(
                job_urn=_required_response_string(
                    job.get("urn"),
                    "Data Job URN",
                ),
                job_name=_required_response_string(
                    (job.get("properties") or {}).get("name")
                    or job.get("jobId"),
                    "Data Job name",
                ),
                job_platform=_optional_response_string(
                    (job.get("platform") or {}).get("name")
                ),
                flow_urn=(
                    _required_response_string(
                        flow.get("urn"),
                        "Data Flow URN",
                    )
                    if flow is not None
                    else None
                ),
                flow_name=(
                    _required_response_string(
                        (flow.get("properties") or {}).get("name")
                        or flow.get("flowId"),
                        "Data Flow name",
                    )
                    if flow is not None
                    else None
                ),
                flow_platform=(
                    _optional_response_string(
                        (flow.get("platform") or {}).get("name")
                    )
                    if flow is not None
                    else None
                ),
                interface="GraphQL Query.dataJob + DataJob.dataFlow",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContextRelationshipUnavailable(
                "Pipeline context response was malformed.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc

    def direct_context_lineage_entities(
        self,
        entity_urn: str,
    ) -> Sequence[ContextLineageEntityObservation]:
        results: dict[
            tuple[str, str],
            ContextLineageEntityObservation,
        ] = {}
        scroll_id: str | None = None
        seen_scroll_ids: set[str] = set()
        while True:
            data = self._graphql_request(
                _DIRECT_CONTEXT_LINEAGE_QUERY,
                variables={
                    "urn": entity_urn,
                    "scrollId": scroll_id,
                },
            )
            try:
                page = data["scrollAcrossLineage"]
                if page.get("isPartial") is True:
                    raise ContextRelationshipUnavailable(
                        "DataHub returned a partial context-lineage page."
                    )
                for item in page["searchResults"]:
                    entity = item["entity"]
                    degree = item["degree"]
                    urn = entity["urn"]
                    entity_type = entity["type"]
                    if (
                        degree == 1
                        and entity_type
                        in {"DATASET", "CHART", "DASHBOARD"}
                        and isinstance(urn, str)
                        and urn
                    ):
                        results[(entity_type, urn)] = (
                            ContextLineageEntityObservation(
                                urn=urn,
                                entity_type=entity_type,
                                degree=degree,
                                interface=(
                                    "GraphQL Query.scrollAcrossLineage("
                                    "DOWNSTREAM,degree=1)"
                                ),
                            )
                        )
                next_scroll_id = page.get("nextScrollId")
            except ContextRelationshipUnavailable:
                raise
            except (KeyError, TypeError) as exc:
                raise ContextRelationshipUnavailable(
                    "DataHub context-lineage response was incomplete.",
                    diagnostic=redact_secrets(
                        exc,
                        (self._config._credential,),
                    ),
                ) from exc
            if next_scroll_id is None:
                break
            if (
                not isinstance(next_scroll_id, str)
                or not next_scroll_id
                or next_scroll_id in seen_scroll_ids
            ):
                raise ContextRelationshipUnavailable(
                    "DataHub context-lineage pagination cursor was invalid."
                )
            seen_scroll_ids.add(next_scroll_id)
            scroll_id = next_scroll_id
        return tuple(results[key] for key in sorted(results))

    def business_intelligence_entity(
        self,
        urn: str,
        entity_type: str,
    ) -> BusinessIntelligenceEntityObservation | None:
        normalized_type = entity_type.upper()
        if normalized_type == "CHART":
            root = "chart"
            query = _CHART_CONTEXT_QUERY
        elif normalized_type == "DASHBOARD":
            root = "dashboard"
            query = _DASHBOARD_CONTEXT_QUERY
        else:
            raise ContextRelationshipUnavailable(
                "Unsupported BI context entity type.",
                diagnostic=f"Entity type: {entity_type}.",
            )
        data = self._graphql_request(query, variables={"urn": urn})
        try:
            entity = data[root]
            if entity is None:
                return None
            platform_data = entity.get("platform") or {}
            platform = (
                _optional_response_string(
                    (platform_data.get("properties") or {}).get(
                        "displayName"
                    )
                )
                or _optional_response_string(platform_data.get("name"))
                or _optional_response_string(entity.get("tool"))
            )
            if platform is None:
                raise ValueError("BI platform was absent.")
            name = _required_response_string(
                (entity.get("properties") or {}).get("name"),
                "BI entity name",
            )
            return BusinessIntelligenceEntityObservation(
                urn=_required_response_string(
                    entity.get("urn"),
                    "BI entity URN",
                ),
                entity_type=normalized_type,
                platform=platform,
                name=name,
                interface=f"GraphQL Query.{root}",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContextRelationshipUnavailable(
                "BI context response was malformed.",
                diagnostic=redact_secrets(
                    exc,
                    (self._config._credential,),
                ),
            ) from exc

    def _graphql_request(
        self,
        query: str,
        *,
        token: object = _CONFIGURED_CREDENTIAL,
        variables: Mapping[str, object] | None = None,
    ) -> dict:
        bearer_token = (
            self._config._credential
            if token is _CONFIGURED_CREDENTIAL
            else token
        )
        request_secrets = (
            self._config._credential,
            bearer_token if isinstance(bearer_token, str) else "",
        )
        payload: dict[str, object] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        body = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "chronos-datahub-gate/0.1",
        }
        if isinstance(bearer_token, str):
            headers["Authorization"] = f"Bearer {bearer_token}"
        request = urllib.request.Request(
            f"{self._config.gms_url}/api/graphql",
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.timeout_seconds
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            safe_detail = f"GraphQL returned HTTP {exc.code}."
            if exc.code == 401:
                raise AuthenticationError(
                    "DataHub rejected the configured credential.",
                    diagnostic=safe_detail,
                    status_code=exc.code,
                ) from exc
            if exc.code == 403:
                raise AuthorizationError(
                    "DataHub denied the required metadata read.",
                    diagnostic=safe_detail,
                    status_code=exc.code,
                ) from exc
            raise UnexpectedDataHubError(
                "DataHub GraphQL request failed.",
                diagnostic=safe_detail,
                status_code=exc.code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise ConnectionError(
                "DataHub GMS is unreachable.",
                diagnostic=redact_secrets(exc, request_secrets),
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnexpectedDataHubError(
                "DataHub returned an invalid GraphQL response.",
                diagnostic=redact_secrets(exc, request_secrets),
            ) from exc

        errors = payload.get("errors") or []
        if errors:
            message = " ".join(str(item.get("message", "")) for item in errors)
            lowered = message.lower()
            diagnostic = redact_secrets(message, request_secrets)
            if "unauth" in lowered or "invalid token" in lowered:
                raise AuthenticationError(
                    "DataHub rejected the configured credential.",
                    diagnostic=diagnostic,
                )
            if "forbidden" in lowered or "permission" in lowered:
                raise AuthorizationError(
                    "DataHub denied the required metadata read.",
                    diagnostic=diagnostic,
                )
            raise UnexpectedDataHubError(
                "DataHub GraphQL returned errors.",
                diagnostic=diagnostic,
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise UnexpectedDataHubError(
                "DataHub GraphQL response did not contain data."
            )
        return data

    def _classify_sdk_exception(
        self, exc: Exception, safe_message: str
    ) -> Exception:
        diagnostic = redact_secrets(exc, (self._config._credential,))
        lowered = diagnostic.lower()
        if "401" in lowered or "unauth" in lowered or "invalid token" in lowered:
            return AuthenticationError(
                "DataHub rejected the configured credential.",
                diagnostic=diagnostic,
            )
        if "403" in lowered or "forbidden" in lowered or "permission" in lowered:
            return AuthorizationError(
                "DataHub denied the required metadata read.",
                diagnostic=diagnostic,
            )
        if any(
            marker in lowered
            for marker in (
                "connection",
                "timed out",
                "timeout",
                "name resolution",
                "refused",
            )
        ):
            return ConnectionError(safe_message, diagnostic=diagnostic)
        return UnexpectedDataHubError(safe_message, diagnostic=diagnostic)


def _datahub_type_name(field: object) -> str | None:
    schema_type = getattr(field, "type", None)
    type_object = getattr(schema_type, "type", None)
    if type_object is None:
        return None
    return type(type_object).__name__


def _audit_time(audit_stamp: object | None) -> int | None:
    if audit_stamp is None:
        return None
    value = getattr(audit_stamp, "time", None)
    return value if isinstance(value, int) else None


def _optional_string(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_string(value: object | None, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MalformedGovernanceAspect(f"{label} was malformed.")
    return value


def _required_response_string(value: object | None, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} was malformed.")
    return value


def _optional_response_string(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional GraphQL string was malformed.")
    return value


def _sorted_required_urns(
    values: Sequence[object],
    label: str,
) -> tuple[str, ...]:
    return tuple(
        sorted({_required_string(value, label) for value in values})
    )


def _association_urns(
    values: Sequence[object],
    attribute: str,
    label: str,
) -> tuple[str, ...]:
    return _sorted_required_urns(
        tuple(getattr(value, attribute, None) for value in values),
        label,
    )


def _owner_kind(owner_urn: str) -> str:
    if owner_urn.startswith("urn:li:corpuser:"):
        return "CORP_USER"
    if owner_urn.startswith("urn:li:corpGroup:"):
        return "CORP_GROUP"
    return "UNKNOWN"


def _reference_name(
    entity_type: str,
    aspect: object | None,
) -> str | None:
    if aspect is None:
        return None
    if entity_type == "CORP_USER":
        for attribute in ("displayName", "fullName", "email"):
            value = getattr(aspect, attribute, None)
            if isinstance(value, str) and value:
                return value
        return None
    if entity_type == "CORP_GROUP":
        value = getattr(aspect, "displayName", None)
    else:
        value = getattr(aspect, "name", None)
    return value if isinstance(value, str) and value else None


def _structured_property_definition(
    entity: Mapping[str, object],
) -> StructuredPropertyDefinitionObservation:
    definition = entity.get("definition")
    if not isinstance(definition, Mapping):
        raise ValueError("Structured-property definition was absent.")
    value_type = definition.get("valueType")
    if not isinstance(value_type, Mapping):
        raise ValueError("Structured-property value type was absent.")
    value_info = value_type.get("info")
    if not isinstance(value_info, Mapping):
        raise ValueError("Structured-property value type info was absent.")
    return StructuredPropertyDefinitionObservation(
        property_urn=_required_response_string(
            entity.get("urn"),
            "Structured property URN",
        ),
        qualified_name=_required_response_string(
            definition.get("qualifiedName"),
            "Structured property qualified name",
        ),
        display_name=_optional_response_string(
            definition.get("displayName")
        ),
        value_type=_required_response_string(
            value_info.get("type"),
            "Structured property value type",
        ),
        value_type_urn=_required_response_string(
            value_type.get("urn"),
            "Structured property value type URN",
        ),
        interface=(
            "GraphQL Query.searchAcrossEntities(STRUCTURED_PROPERTY)"
        ),
    )


def _structured_property_assignment(
    item: Mapping[str, object],
) -> StructuredPropertyAssignmentObservation:
    property_entity = item.get("structuredProperty")
    if not isinstance(property_entity, Mapping):
        raise ValueError("Structured-property entity was absent.")
    definition = _structured_property_definition(property_entity)
    raw_values = item.get("values")
    if not isinstance(raw_values, Sequence) or isinstance(
        raw_values,
        (str, bytes),
    ):
        raise ValueError("Structured-property values were malformed.")
    values: list[str | float] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, Mapping):
            raise ValueError("Structured-property value was malformed.")
        if "stringValue" in raw_value:
            value = raw_value["stringValue"]
            if not isinstance(value, str):
                raise ValueError("Structured-property string was malformed.")
            values.append(value)
        elif "numberValue" in raw_value:
            value = raw_value["numberValue"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Structured-property number was malformed.")
            values.append(float(value))
        else:
            raise ValueError("Structured-property value type was unsupported.")
    return StructuredPropertyAssignmentObservation(
        property_urn=definition.property_urn,
        qualified_name=definition.qualified_name,
        display_name=definition.display_name,
        value_type=definition.value_type,
        value_type_urn=definition.value_type_urn,
        values=tuple(values),
        assignment_target=_required_response_string(
            item.get("associatedUrn"),
            "Structured property assignment target",
        ),
        interface=(
            "GraphQL Dataset.structuredProperties + "
            "StructuredPropertiesEntry"
        ),
    )


def _principal_from_auth_response(data: Mapping[str, object]) -> str:
    try:
        me = data["me"]
        corp_user = me["corpUser"]  # type: ignore[index]
        principal = corp_user["urn"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise AuthenticationError(
            "Configured metadata read did not return a principal.",
            diagnostic="GraphQL me response was incomplete.",
        ) from exc
    if not isinstance(principal, str) or not principal:
        raise AuthenticationError(
            "Configured metadata read did not return a principal."
        )
    return principal
