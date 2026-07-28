"""Immutable CHRONOS Phase 3.1 counterfactual source-state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.proposal import ChangeType


COUNTERFACTUAL_SOURCE_SCHEMA_VERSION = "1.0"
CANONICAL_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


class SourceStateClassification(str, Enum):
    CERTIFIED_CURRENT = "certified_current"
    COUNTERFACTUAL = "counterfactual"


class FieldMappingClassification(str, Enum):
    RENAMED = "renamed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class InputArtifactHash:
    artifact_name: str
    before_sha256: str
    after_sha256: str

    def __post_init__(self) -> None:
        if not self.artifact_name:
            raise ValueError("Input artifact name must not be empty.")
        for value in (self.before_sha256, self.after_sha256):
            if not _is_file_sha256(value):
                raise ValueError("Input artifact hash must be SHA-256 hex.")

    @property
    def unchanged(self) -> bool:
        return self.before_sha256 == self.after_sha256


@dataclass(frozen=True)
class SourceFieldIdentity:
    dataset_urn: str
    field_path: str
    state_classification: SourceStateClassification

    @property
    def machine_key(self) -> tuple[str, str]:
        return (self.dataset_urn, self.field_path)


@dataclass(frozen=True)
class CounterfactualDatasetIdentity:
    dataset_urn: str
    platform: str
    environment: str
    qualified_name: str | None
    logical_name: str | None
    schema_name: str
    source_platform: str
    state_classification: SourceStateClassification


@dataclass(frozen=True)
class CurrentSourceSchemaReference:
    snapshot_id: str
    snapshot_fingerprint: str
    dataset_urn: str
    schema_name: str
    field_count: int
    field_paths: tuple[str, ...]
    target_field: SourceFieldIdentity
    state_classification: SourceStateClassification


@dataclass(frozen=True)
class CandidateSourceField:
    position: int
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: str
    datahub_type: str | None
    description: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    is_partitioning_key: bool | None
    json_path: str | None
    label: str | None
    recursive: bool | None
    schema_field_urn: str | None
    current_evidence_ids: tuple[str, ...]
    state_classification: SourceStateClassification
    current_source_identity: SourceFieldIdentity


@dataclass(frozen=True)
class CandidateSourceSchema:
    dataset_identity: CounterfactualDatasetIdentity
    schema_name: str
    schema_version: int | None
    schema_hash: str | None
    created_time: int | None
    last_modified_time: int | None
    dataset_reference: str | None
    cluster: str | None
    primary_keys: tuple[str, ...] | None
    current_evidence_ids: tuple[str, ...]
    fields: tuple[CandidateSourceField, ...]
    state_classification: SourceStateClassification


@dataclass(frozen=True)
class FieldIdentityMapping:
    current_identity: SourceFieldIdentity
    candidate_identity: SourceFieldIdentity
    classification: FieldMappingClassification


@dataclass(frozen=True)
class TransformationSummary:
    unchanged_field_count: int
    renamed_field_count: int
    added_field_count: int
    deleted_field_count: int
    downstream_field_count: int
    lineage_edge_count: int
    governance_record_count: int


@dataclass(frozen=True)
class CounterfactualSourceState:
    schema_version: str
    demonstration_id: str
    state_classification: SourceStateClassification
    operation: ChangeType
    dataset_identity: CounterfactualDatasetIdentity
    current_snapshot_fingerprint: str
    proposal_fingerprint: str
    validation_fingerprint: str
    semantic_contract_fingerprint: str
    phase_2_certification_fingerprint: str
    current_source_schema_reference: CurrentSourceSchemaReference
    candidate_source_schema: CandidateSourceSchema
    field_identity_mappings: tuple[FieldIdentityMapping, ...]
    transformation_summary: TransformationSummary
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != COUNTERFACTUAL_SOURCE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported counterfactual source-state schema version."
            )
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Phase 3.1 demonstration identity is invalid.")
        if self.state_classification is not (
            SourceStateClassification.COUNTERFACTUAL
        ):
            raise ValueError("Source state must be COUNTERFACTUAL.")
        if self.operation is not ChangeType.FIELD_RENAME:
            raise ValueError("Phase 3.1 supports FIELD_RENAME only.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include a timezone.")
        for value, label in (
            (self.current_snapshot_fingerprint, "snapshot fingerprint"),
            (self.proposal_fingerprint, "proposal fingerprint"),
            (self.validation_fingerprint, "validation fingerprint"),
            (
                self.semantic_contract_fingerprint,
                "semantic-contract fingerprint",
            ),
            (
                self.phase_2_certification_fingerprint,
                "Phase 2 certification fingerprint",
            ),
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError(f"{label} is not canonical sha256.")
        if self.dataset_identity.dataset_urn != CANONICAL_DATASET_URN:
            raise ValueError("Candidate Dataset URN must remain canonical.")
        if self.dataset_identity.state_classification is not (
            SourceStateClassification.COUNTERFACTUAL
        ):
            raise ValueError("Candidate Dataset must be COUNTERFACTUAL.")
        if self.candidate_source_schema.state_classification is not (
            SourceStateClassification.COUNTERFACTUAL
        ):
            raise ValueError("Candidate schema must be COUNTERFACTUAL.")
        if self.candidate_source_schema.dataset_identity != (
            self.dataset_identity
        ):
            raise ValueError("Candidate schema Dataset identity is inconsistent.")
        _validate_candidate_structure(self)
        from .serialization import source_state_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            source_state_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import source_state_to_dict

        return source_state_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import source_state_to_json

        return source_state_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import source_state_to_json

        return source_state_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> CounterfactualSourceState:
        from .serialization import source_state_from_json

        return source_state_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, CounterfactualSourceState)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> str:
        target = next(
            item
            for item in self.candidate_source_schema.fields
            if item.field_path == "order_amount"
        )
        return "\n".join(
            (
                f"Demonstration: {self.demonstration_id}",
                f"Operation: {self.operation.name}",
                "State: COUNTERFACTUAL",
                f"Dataset: {self.dataset_identity.dataset_urn}",
                (
                    "Source transformation: "
                    "order_total -> order_amount"
                ),
                (
                    "Candidate target: "
                    f"position={target.position}; "
                    f"native_type={target.native_type}; "
                    f"normalized_type={target.normalized_type}"
                ),
                (
                    "Fields: "
                    f"{len(self.candidate_source_schema.fields)} total; "
                    "14 unchanged; 1 renamed; 0 added; 0 deleted"
                ),
                "Downstream fields transformed: 0",
                "Lineage edges transformed: 0",
            )
        )


def _validate_candidate_structure(state: CounterfactualSourceState) -> None:
    fields = state.candidate_source_schema.fields
    paths = tuple(item.field_path for item in fields)
    positions = tuple(item.position for item in fields)
    if len(fields) != 15:
        raise ValueError("Candidate source schema must contain 15 fields.")
    if len(set(paths)) != len(paths):
        raise ValueError("Candidate field paths must be unique.")
    if len(set(positions)) != len(positions):
        raise ValueError("Candidate field positions must be unique.")
    if positions != tuple(range(15)):
        raise ValueError("Candidate field ordering must preserve positions 0-14.")
    if paths.count("order_total") != 0:
        raise ValueError("Candidate schema cannot contain order_total.")
    if paths.count("order_amount") != 1:
        raise ValueError("Candidate schema must contain one order_amount.")
    target = fields[paths.index("order_amount")]
    if target.position != 5:
        raise ValueError("Candidate order_amount must remain at position 5.")
    if target.schema_field_urn is not None:
        raise ValueError("Candidate order_amount schema-field URN is fabricated.")
    if any(
        item.state_classification
        is not SourceStateClassification.COUNTERFACTUAL
        for item in fields
    ):
        raise ValueError("Every candidate field must be COUNTERFACTUAL.")
    if any(
        item.current_source_identity.state_classification
        is not SourceStateClassification.CERTIFIED_CURRENT
        for item in fields
    ):
        raise ValueError("Current field references must be CERTIFIED_CURRENT.")
    mappings = state.field_identity_mappings
    if len(mappings) != 15:
        raise ValueError("Exactly 15 current-to-candidate mappings are required.")
    if any(
        item.current_identity.state_classification
        is not SourceStateClassification.CERTIFIED_CURRENT
        or item.candidate_identity.state_classification
        is not SourceStateClassification.COUNTERFACTUAL
        for item in mappings
    ):
        raise ValueError("Mapping identity classifications are invalid.")
    if len({item.current_identity.machine_key for item in mappings}) != 15:
        raise ValueError("Current mapping identities must be unique.")
    if len({item.candidate_identity.machine_key for item in mappings}) != 15:
        raise ValueError("Candidate mapping identities must be unique.")
    renamed = tuple(
        item
        for item in mappings
        if item.classification is FieldMappingClassification.RENAMED
    )
    unchanged = tuple(
        item
        for item in mappings
        if item.classification is FieldMappingClassification.UNCHANGED
    )
    if len(renamed) != 1 or len(unchanged) != 14:
        raise ValueError("Mappings must contain 1 RENAMED and 14 UNCHANGED.")
    if (
        renamed[0].current_identity.machine_key
        != (CANONICAL_DATASET_URN, "order_total")
        or renamed[0].candidate_identity.machine_key
        != (CANONICAL_DATASET_URN, "order_amount")
    ):
        raise ValueError("The rename mapping is inconsistent.")
    if any(
        item.current_identity.machine_key
        != item.candidate_identity.machine_key
        for item in unchanged
    ):
        raise ValueError("UNCHANGED mappings must preserve machine identity.")
    summary = state.transformation_summary
    if summary != TransformationSummary(14, 1, 0, 0, 0, 0, 0):
        raise ValueError("Transformation summary exceeds Phase 3.1 scope.")
    if state.current_source_schema_reference.state_classification is not (
        SourceStateClassification.CERTIFIED_CURRENT
    ):
        raise ValueError("Current schema reference must be CERTIFIED_CURRENT.")
    if state.current_source_schema_reference.field_count != 15:
        raise ValueError("Current schema reference must contain 15 fields.")
    reference_paths = state.current_source_schema_reference.field_paths
    if len(reference_paths) != 15 or len(set(reference_paths)) != 15:
        raise ValueError("Current schema field-path references are invalid.")
    expected_artifacts = {
        "current_metadata_snapshot.json",
        "change_proposal.json",
        "change_proposal_validation.json",
        "change_semantic_contract.json",
        "phase_2_certification.json",
    }
    observed_artifacts = {
        item.artifact_name for item in state.input_artifact_hashes
    }
    if observed_artifacts != expected_artifacts:
        raise ValueError("Authoritative input artifact hash set is invalid.")
    if any(not item.unchanged for item in state.input_artifact_hashes):
        raise ValueError("An authoritative input artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _is_file_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )
