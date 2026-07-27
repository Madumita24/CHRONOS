from __future__ import annotations

import copy
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from chronos.change_semantics import (
    ChangedProperty,
    RuleDisposition,
    SemanticRuleCode,
    UnchangedProperty,
    load_contract,
)
from chronos.phase2_certification import (
    ArtifactHashEvidence,
    CertificationCheckStatus,
    Phase2CertificationResult,
    Phase2CertificationState,
    certify_phase2,
    certify_phase2_from_artifacts,
    load_certification,
)
from chronos.proposal import (
    ClaimedFieldState,
    RequestedFieldState,
    SchemaFieldTarget,
    load_proposal,
)
from chronos.proposal_validation import (
    ProposalValidationFinding,
    ProposalValidationState,
    ValidationFindingCode,
    ValidationFindingSeverity,
    load_validation_result,
)
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
PROPOSAL_PATH = ROOT / "artifacts" / "change_proposal.json"
VALIDATION_PATH = ROOT / "artifacts" / "change_proposal_validation.json"
CONTRACT_PATH = ROOT / "artifacts" / "change_semantic_contract.json"
CERTIFICATION_PATH = ROOT / "artifacts" / "phase_2_certification.json"


def clock(hour: int):
    return lambda: datetime(2026, 7, 27, hour, tzinfo=timezone.utc)


class Phase2CertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)
        cls.validation = load_validation_result(VALIDATION_PATH)
        cls.contract = load_contract(CONTRACT_PATH)
        cls.result = certify_phase2_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            clock=clock(7),
        )

    def test_01_canonical_phase_2_package_certifies(self) -> None:
        self.assertEqual(
            self.result.certification_state,
            Phase2CertificationState.CERTIFIED,
        )
        self.assertFalse(self.result.findings)
        self.assertFalse(self.result.warnings)

    def test_02_all_four_artifacts_load_through_public_deserializers(
        self,
    ) -> None:
        self.assertEqual(
            self.snapshot.metadata.demonstration_id,
            "CHRONOS-DEMO-001",
        )
        self.assertEqual(
            self.proposal.proposal_id,
            "CHRONOS-DEMO-001-PROPOSAL-001",
        )
        self.assertEqual(
            self.validation.validation_state,
            ProposalValidationState.VALID,
        )
        self.assertEqual(self.contract.change_type.value, "field_rename")

    def test_03_wrong_snapshot_fingerprint_blocks(self) -> None:
        snapshot = replace(
            self.snapshot,
            semantic_fingerprint="sha256:" + ("1" * 64),
        )
        self.assertNotCertified(self.certify(snapshot=snapshot))

    def test_04_wrong_proposal_fingerprint_blocks(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        object.__setattr__(
            proposal,
            "semantic_fingerprint",
            "sha256:" + ("2" * 64),
        )
        self.assertNotCertified(self.certify(proposal=proposal))

    def test_05_wrong_validation_fingerprint_blocks(self) -> None:
        validation = copy.deepcopy(self.validation)
        object.__setattr__(
            validation,
            "semantic_fingerprint",
            "sha256:" + ("3" * 64),
        )
        self.assertNotCertified(self.certify(validation=validation))

    def test_06_wrong_contract_baseline_blocks(self) -> None:
        contract = replace(
            self.contract,
            baseline_snapshot_fingerprint="sha256:" + ("4" * 64),
        )
        self.assertNotCertified(self.certify(contract=contract))

    def test_07_demonstration_mismatch_blocks(self) -> None:
        proposal = replace(self.proposal, demonstration_id="OTHER-DEMO")
        result = self.certify(proposal=proposal)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "demonstration_identity")

    def test_08_target_identity_mismatch_blocks(self) -> None:
        target = SchemaFieldTarget(
            dataset_urn=(
                "urn:li:dataset:(urn:li:dataPlatform:postgres,"
                "wrong.orders,PROD)"
            ),
            field_path="order_total",
        )
        proposal = replace(
            self.proposal,
            change=replace(self.proposal.change, target=target),
        )
        result = self.certify(proposal=proposal)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "target_machine_identity")

    def test_09_before_state_mismatch_blocks(self) -> None:
        before = ClaimedFieldState(
            field_path="order_total",
            field_name="order_total",
            native_type="BIGINT",
            normalized_type="Number",
        )
        proposal = replace(
            self.proposal,
            change=replace(self.proposal.change, before=before),
        )
        result = self.certify(proposal=proposal)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "before_state_consistency")

    def test_10_requested_state_mismatch_blocks(self) -> None:
        requested = RequestedFieldState(
            field_path="total_amount",
            field_name="total_amount",
        )
        proposal = replace(
            self.proposal,
            change=replace(
                self.proposal.change,
                requested_after=requested,
            ),
        )
        result = self.certify(proposal=proposal)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "requested_state_consistency")

    def test_11_invalid_validation_result_blocks(self) -> None:
        validation = replace(
            self.validation,
            validation_state=ProposalValidationState.INVALID,
        )
        result = self.certify(validation=validation)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "validation_state")

    def test_12_warning_validation_finding_blocks(self) -> None:
        warning = ProposalValidationFinding(
            code=ValidationFindingCode.RENAME_NOT_ADMISSIBLE,
            severity=ValidationFindingSeverity.WARNING,
            message="test warning",
        )
        validation = replace(
            self.validation,
            findings=self.validation.findings + (warning,),
        )
        result = self.certify(validation=validation)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "validation_required_checks")

    def test_13_missing_changed_field_blocks(self) -> None:
        contract = replace(
            self.contract,
            changed_properties=self.contract.changed_properties[:1],
        )
        result = self.certify(contract=contract)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "semantic_contract_changed_set")

    def test_14_extra_changed_property_blocks(self) -> None:
        contract = replace(
            self.contract,
            changed_properties=self.contract.changed_properties
            + (
                ChangedProperty(
                    property_name="native_type",
                    before="DOUBLE PRECISION",
                    after="BIGINT",
                ),
            ),
        )
        result = self.certify(contract=contract)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "semantic_contract_changed_set")

    def test_15_downstream_auto_propagation_rule_blocks(self) -> None:
        rules = tuple(
            replace(item, disposition=RuleDisposition.ALLOWED)
            if item.code is SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME
            else item
            for item in self.contract.semantic_rules
        )
        contract = replace(self.contract, semantic_rules=rules)
        result = self.certify(contract=contract)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "non_propagation_rules")

    def test_16_unknown_marked_unchanged_blocks(self) -> None:
        contract = replace(
            self.contract,
            unchanged_properties=self.contract.unchanged_properties
            + (
                UnchangedProperty(
                    "downstream_field_names_change",
                    "unchanged",
                ),
            ),
        )
        result = self.certify(contract=contract)
        self.assertNotCertified(result)
        self.assertCheckFailed(
            result,
            "semantic_contract_unknown_consequences",
        )

    def test_17_order_amount_as_current_metadata_blocks(self) -> None:
        first = self.snapshot.source_schema.fields[0]
        changed = replace(
            first,
            field_path="order_amount",
            field_name="order_amount",
        )
        schema = replace(
            self.snapshot.source_schema,
            fields=(changed,) + self.snapshot.source_schema.fields[1:],
        )
        snapshot = replace(self.snapshot, source_schema=schema)
        result = self.certify(snapshot=snapshot)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "requested_state_consistency")

    def test_18_snapshot_cardinality_mismatch_blocks(self) -> None:
        schema = replace(
            self.snapshot.source_schema,
            fields=self.snapshot.source_schema.fields[:-1],
        )
        snapshot = replace(self.snapshot, source_schema=schema)
        result = self.certify(snapshot=snapshot)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "source_schema_cardinality")

    def test_19_proposal_mutation_is_detected(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        object.__setattr__(
            proposal.change.before,
            "native_type",
            "BIGINT",
        )
        result = self.certify(proposal=proposal)
        self.assertNotCertified(result)
        self.assertCheckFailed(result, "proposal_fingerprint_recomputed")

    def test_20_input_artifact_hash_mutation_is_detected(self) -> None:
        hashes = (
            ArtifactHashEvidence(
                artifact_name="change_proposal.json",
                before_sha256="a" * 64,
                after_sha256="b" * 64,
            ),
        )
        result = certify_phase2(
            self.snapshot,
            self.proposal,
            self.validation,
            self.contract,
            artifact_hashes=hashes,
            clock=clock(7),
        )
        self.assertNotCertified(result)
        self.assertCheckFailed(
            result,
            "artifact_hash_unchanged:change_proposal.json",
        )

    def test_21_stored_fingerprints_recompute(self) -> None:
        for name in (
            "snapshot_fingerprint_recomputed",
            "proposal_fingerprint_recomputed",
            "validation_fingerprint_recomputed",
            "contract_fingerprint_recomputed",
        ):
            self.assertCheckPassed(self.result, name)

    def test_22_certification_is_deterministic_across_timestamps(self) -> None:
        later = certify_phase2_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            clock=clock(9),
        )
        self.assertNotEqual(self.result.certified_at, later.certified_at)
        self.assertTrue(self.result.semantically_equals(later))

    def test_23_certification_serialization_round_trip(self) -> None:
        reloaded = Phase2CertificationResult.from_json(
            self.result.to_json()
        )
        self.assertEqual(reloaded, self.result)

    def test_24_all_artifact_round_trips_pass(self) -> None:
        self.assertCheckPassed(self.result, "deterministic_round_trips")

    def test_25_secret_audit_passes(self) -> None:
        self.assertCheckPassed(self.result, "credential_content_audit")

    def test_26_no_live_datahub_client_is_required(self) -> None:
        source = inspect.getsource(certify_phase2).casefold()
        for term in ("datahubgraph", "graphql", "requests.", "httpx", "gms"):
            self.assertNotIn(term, source)
        self.assertCheckPassed(self.result, "no_live_datahub_dependency")

    def test_27_no_future_graph_is_present(self) -> None:
        self.assertFalse(hasattr(self.contract, "future_graph"))
        self.assertFalse(hasattr(self.result, "future_graph"))
        self.assertCheckPassed(
            self.result,
            "current_counterfactual_boundary",
        )

    def test_28_no_forbidden_impact_or_repair_states(self) -> None:
        self.assertCheckPassed(self.result, "forbidden_semantic_states")
        payload = self.result.to_json().casefold()
        for term in (
            "high_risk",
            "requires_repair",
            "safe_to_deploy",
            "auto_renamed",
        ):
            self.assertNotIn(term, payload)

    def test_29_all_phase_2_domain_objects_are_immutable(self) -> None:
        self.assertCheckPassed(self.result, "phase2_domain_immutability")
        with self.assertRaises(FrozenInstanceError):
            self.result.certification_state = (
                Phase2CertificationState.NOT_CERTIFIED
            )
        with self.assertRaises(FrozenInstanceError):
            self.result.checks[0].status = CertificationCheckStatus.FAIL

    def test_30_all_input_artifact_hashes_are_unchanged(self) -> None:
        self.assertEqual(len(self.result.artifact_hashes), 4)
        self.assertTrue(
            all(
                item.before_sha256 == item.after_sha256
                for item in self.result.artifact_hashes
            )
        )

    def test_31_target_and_before_state_audits_pass(self) -> None:
        for name in (
            "target_machine_identity",
            "before_state_consistency",
            "requested_state_consistency",
        ):
            self.assertCheckPassed(self.result, name)

    def test_32_contract_exactness_audits_pass(self) -> None:
        for name in (
            "semantic_contract_changed_set",
            "semantic_contract_unchanged_set",
            "semantic_contract_unknown_consequences",
            "source_schema_cardinality",
            "non_propagation_rules",
        ):
            self.assertCheckPassed(self.result, name)

    def test_33_artifact_chain_has_no_dangling_reference(self) -> None:
        for name in (
            "proposal_baseline_to_snapshot",
            "validation_proposal_to_proposal",
            "validation_snapshot_to_snapshot",
            "contract_proposal_to_proposal",
            "contract_validation_to_validation",
            "contract_baseline_to_snapshot",
        ):
            self.assertCheckPassed(self.result, name)

    def test_34_final_certification_artifact_loads(self) -> None:
        artifact = load_certification(CERTIFICATION_PATH)
        self.assertEqual(
            artifact.certification_state,
            Phase2CertificationState.CERTIFIED,
        )
        self.assertTrue(artifact.semantically_equals(self.result))

    def certify(
        self,
        *,
        snapshot=None,
        proposal=None,
        validation=None,
        contract=None,
    ) -> Phase2CertificationResult:
        return certify_phase2(
            snapshot or self.snapshot,
            proposal or self.proposal,
            validation or self.validation,
            contract or self.contract,
            clock=clock(7),
        )

    def assertNotCertified(
        self,
        result: Phase2CertificationResult,
    ) -> None:
        self.assertEqual(
            result.certification_state,
            Phase2CertificationState.NOT_CERTIFIED,
        )
        self.assertTrue(result.findings)

    def assertCheckFailed(
        self,
        result: Phase2CertificationResult,
        name: str,
    ) -> None:
        check = next(item for item in result.checks if item.name == name)
        self.assertEqual(check.status, CertificationCheckStatus.FAIL)

    def assertCheckPassed(
        self,
        result: Phase2CertificationResult,
        name: str,
    ) -> None:
        check = next(item for item in result.checks if item.name == name)
        self.assertEqual(check.status, CertificationCheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
