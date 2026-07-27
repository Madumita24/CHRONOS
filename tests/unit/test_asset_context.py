from __future__ import annotations

import inspect
import unittest
from collections import Counter
from datetime import datetime, timezone

from chronos.context import (
    AssetContextRetriever,
    AssignmentScope,
    BusinessIntelligenceClassification,
    ContextRetrievalState,
    MetadataState,
)
from chronos.datahub._transport import (
    BusinessIntelligenceEntityObservation,
    ContextLineageEntityObservation,
    DataProductMembershipObservation,
    DocumentRelationshipObservation,
    FieldGovernanceObservation,
    GovernanceAspectObservation,
    MetadataReferenceObservation,
    OwnerAssignmentObservation,
    PipelineEntityObservation,
    StructuredPropertyAssignmentObservation,
    StructuredPropertyDefinitionObservation,
)
from chronos.datahub.errors import GovernanceRetrievalUnavailable
from chronos.lineage.models import (
    DatasetLineageIndexEntry,
    FieldLineageGraph,
    FieldLineageNode,
    FieldReference,
    FieldReferenceResolution,
    LineageEvidence,
    LineageMappingGroup,
    LineageRelationshipClassification,
    LineageValidationState,
    MappingExpansionState,
)


A = "urn:li:dataset:(urn:li:dataPlatform:postgres,a,PROD)"
B = "urn:li:dataset:(urn:li:dataPlatform:snowflake,b,PROD)"
USER = "urn:li:corpuser:user"
GROUP = "urn:li:corpGroup:group"
DOMAIN = "urn:li:domain:domain"
TAG_A = "urn:li:tag:a"
TAG_B = "urn:li:tag:b"
TERM = "urn:li:glossaryTerm:term"
MISSING_TERM = "urn:li:glossaryTerm:missing"
NODE = "urn:li:glossaryNode:node"
PROPERTY = "urn:li:structuredProperty:test"
PRODUCT = "urn:li:dataProduct:product"
DOCUMENT = "urn:li:document:document"
JOB = "urn:li:dataJob:(urn:li:dataFlow:(spark,flow,prod),job)"
FLOW = "urn:li:dataFlow:(spark,flow,prod)"
LOOKER_CHART = "urn:li:chart:(looker,chart)"
TABLEAU_CHART = "urn:li:chart:(tableau,chart)"
LOOKER_DASHBOARD = "urn:li:dashboard:(looker,dashboard)"
TABLEAU_DASHBOARD = "urn:li:dashboard:(tableau,dashboard)"


def reference(
    dataset_urn: str,
    field_path: str,
    platform: str,
) -> FieldReference:
    return FieldReference(
        dataset_urn=dataset_urn,
        field_path=field_path,
        field_name=field_path,
        platform=platform,
        dataset_name=dataset_urn,
        environment="PROD",
        canonical_identity=None,
        display_identity=None,
        schema_field_urn=None,
        resolution=FieldReferenceResolution.SCHEMA_MEMBER,
    )


def graph() -> FieldLineageGraph:
    source = reference(A, "order_total", "postgres")
    downstream = reference(B, "order_total", "snowflake")
    group = LineageMappingGroup(
        group_id="job:0",
        source_entity_urn=JOB,
        source_entity_type="DATA_JOB",
        source_aspect="dataJobInputOutput",
        source_interface="DataHubGraph.get_aspect(DataJobInputOutputClass)",
        source_group_index=0,
        upstream_type="FIELD_SET",
        downstream_type="FIELD",
        raw_upstream_references=(),
        raw_downstream_references=(),
        upstream_fields=(source,),
        downstream_fields=(downstream,),
        transform_operation=None,
        confidence_score=1.0,
        query=None,
        match_type=None,
        expansion_state=MappingExpansionState.EXPANDED,
        ambiguity_reason=None,
        observed_at="2026-01-01T00:00:00+00:00",
    )
    return FieldLineageGraph(
        source=source,
        nodes=(
            FieldLineageNode(source, 0, 1, False),
            FieldLineageNode(downstream, 1, 1, False),
        ),
        edges=(),
        mapping_groups=(group,),
        paths=(),
        cycles=(),
        dataset_index=(
            DatasetLineageIndexEntry(
                dataset_urn=A,
                platform="postgres",
                dataset_name="a",
                environment="PROD",
                field_keys=((A, "order_total"),),
            ),
            DatasetLineageIndexEntry(
                dataset_urn=B,
                platform="snowflake",
                dataset_name="b",
                environment="PROD",
                field_keys=((B, "order_total"),),
            ),
        ),
        evidence=LineageEvidence(
            source_field=(A, "order_total"),
            interfaces=("test",),
            observed_at="2026-01-01T00:00:00+00:00",
            candidate_dataset_count=2,
            aspect_entity_count=1,
            mapping_group_count=1,
            explicit_edge_count=1,
            downstream_field_count=1,
            downstream_dataset_count=1,
            maximum_field_depth=1,
            validation_state=LineageValidationState.VALID,
        ),
        findings=(),
    )


class FakeContextTransport:
    def __init__(self) -> None:
        self.calls: Counter[tuple[str, str]] = Counter()

    def governance_aspects(self, dataset_urn: str):
        self.calls[("governance", dataset_urn)] += 1
        if dataset_urn == A:
            return GovernanceAspectObservation(
                dataset_urn=A,
                owners=(
                    OwnerAssignmentObservation(
                        USER,
                        "CORP_USER",
                        "TECHNICAL_OWNER",
                        None,
                    ),
                    OwnerAssignmentObservation(
                        GROUP,
                        "CORP_GROUP",
                        "BUSINESS_OWNER",
                        "urn:li:ownershipType:business",
                    ),
                ),
                domain_urns=(DOMAIN,),
                tag_urns=(TAG_B, TAG_A),
                term_urns=(TERM, MISSING_TERM),
                field_governance=(
                    FieldGovernanceObservation(
                        "order_total",
                        (TAG_A,),
                        (TERM,),
                    ),
                    FieldGovernanceObservation(
                        "unrelated_field",
                        (TAG_B,),
                        (),
                    ),
                ),
                interface="sdk:governance",
            )
        return GovernanceAspectObservation(
            dataset_urn=B,
            owners=(),
            domain_urns=(),
            tag_urns=(TAG_A,),
            term_urns=(),
            field_governance=(),
            interface="sdk:governance",
        )

    def metadata_reference(self, urn: str, entity_type: str):
        self.calls[(entity_type, urn)] += 1
        values = {
            (USER, "CORP_USER"): ("User", None, True),
            (GROUP, "CORP_GROUP"): ("Group", None, True),
            (DOMAIN, "DOMAIN"): ("Commerce", None, True),
            (TAG_A, "TAG"): ("A", None, True),
            (TAG_B, "TAG"): ("B", None, True),
            (TERM, "GLOSSARY_TERM"): ("Order Total", NODE, True),
            (NODE, "GLOSSARY_NODE"): ("Metrics", None, True),
            (MISSING_TERM, "GLOSSARY_TERM"): (None, None, False),
        }
        name, parent, resolved = values[(urn, entity_type)]
        return MetadataReferenceObservation(
            urn=urn,
            entity_type=entity_type,
            name=name,
            parent_urn=parent,
            resolved=resolved,
            interface=f"sdk:{entity_type}",
        )

    def structured_property_definitions(self):
        return (
            StructuredPropertyDefinitionObservation(
                PROPERTY,
                "test.property",
                "Property",
                "STRING",
                "urn:li:dataType:datahub.string",
                "graphql:definition",
            ),
        )

    def structured_property_assignments(self, dataset_urn: str):
        self.calls[("properties", dataset_urn)] += 1
        if dataset_urn != A:
            return ()
        return (
            StructuredPropertyAssignmentObservation(
                PROPERTY,
                "test.property",
                "Property",
                "STRING",
                "urn:li:dataType:datahub.string",
                ("value",),
                A,
                "graphql:assignment",
            ),
        )

    def data_product_memberships(self, asset_urn: str):
        self.calls[("products", asset_urn)] += 1
        if asset_urn != A:
            return ()
        return (
            DataProductMembershipObservation(
                PRODUCT,
                "Product",
                A,
                "DataProductContains",
                "graphql:product",
            ),
        )

    def related_documents(self, asset_urn: str):
        self.calls[("documents", asset_urn)] += 1
        if asset_urn != A:
            return ()
        return (
            DocumentRelationshipObservation(
                DOCUMENT,
                "Runbook",
                A,
                "RelatedAsset",
                "sdk:document",
            ),
        )

    def pipeline_entity(self, job_urn: str):
        self.calls[("pipeline", job_urn)] += 1
        return PipelineEntityObservation(
            JOB,
            "Job",
            "spark",
            FLOW,
            "Flow",
            "spark",
            "graphql:pipeline",
        )

    def direct_context_lineage_entities(self, entity_urn: str):
        self.calls[("lineage", entity_urn)] += 1
        mapping = {
            A: (
                ContextLineageEntityObservation(
                    B,
                    "DATASET",
                    1,
                    "graphql:lineage",
                ),
            ),
            B: (
                ContextLineageEntityObservation(
                    LOOKER_CHART,
                    "CHART",
                    1,
                    "graphql:lineage",
                ),
                ContextLineageEntityObservation(
                    TABLEAU_CHART,
                    "CHART",
                    1,
                    "graphql:lineage",
                ),
            ),
            LOOKER_CHART: (
                ContextLineageEntityObservation(
                    LOOKER_DASHBOARD,
                    "DASHBOARD",
                    1,
                    "graphql:lineage",
                ),
            ),
            TABLEAU_CHART: (
                ContextLineageEntityObservation(
                    TABLEAU_DASHBOARD,
                    "DASHBOARD",
                    1,
                    "graphql:lineage",
                ),
            ),
        }
        return mapping.get(entity_urn, ())

    def business_intelligence_entity(
        self,
        urn: str,
        entity_type: str,
    ):
        self.calls[(entity_type, urn)] += 1
        platform = "Looker" if "looker" in urn else "Tableau"
        name = "Order Entry Dashboard" if entity_type == "DASHBOARD" else "Chart"
        return BusinessIntelligenceEntityObservation(
            urn,
            entity_type,
            platform,
            name,
            f"graphql:{entity_type}",
        )


class AssetContextRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeContextTransport()
        self.retriever = AssetContextRetriever(
            self.transport,
            clock=lambda: datetime(
                2026,
                1,
                1,
                tzinfo=timezone.utc,
            ),
        )
        self.result = self.retriever.retrieve(graph())
        self.assertEqual(
            self.result.state,
            ContextRetrievalState.RETRIEVED,
            self.result.to_dict(),
        )
        self.a, self.b = self.result.snapshot.assets

    def test_dataset_with_multiple_owners(self) -> None:
        self.assertEqual(len(self.a.owners), 2)
        self.assertEqual(self.a.ownership_state, MetadataState.PRESENT)

    def test_dataset_with_zero_owners(self) -> None:
        self.assertEqual(self.b.owners, ())
        self.assertEqual(self.b.ownership_state, MetadataState.ABSENT)

    def test_user_and_group_ownership_remain_distinct(self) -> None:
        self.assertEqual(
            {item.owner_kind for item in self.a.owners},
            {"CORP_USER", "CORP_GROUP"},
        )

    def test_domain_present_and_absent(self) -> None:
        self.assertEqual(self.a.domains[0].display_name, "Commerce")
        self.assertEqual(self.b.domains, ())
        self.assertEqual(self.b.domain_state, MetadataState.ABSENT)

    def test_domain_absence_is_not_an_unknown_domain(self) -> None:
        self.assertEqual(self.b.domains, ())
        self.assertNotEqual(self.b.domain_state, MetadataState.UNRESOLVED)

    def test_multiple_tags_are_ordered(self) -> None:
        entity_tags = tuple(
            item.tag_urn
            for item in self.a.tags
            if item.scope is AssignmentScope.ENTITY
        )
        self.assertEqual(entity_tags, (TAG_A, TAG_B))

    def test_entity_and_field_terms_are_distinct(self) -> None:
        scopes = {
            (item.term_urn, item.scope)
            for item in self.a.glossary_terms
        }
        self.assertIn((TERM, AssignmentScope.ENTITY), scopes)
        self.assertIn((TERM, AssignmentScope.FIELD), scopes)

    def test_field_level_term_retains_exact_target(self) -> None:
        term = next(
            item
            for item in self.a.glossary_terms
            if item.scope is AssignmentScope.FIELD
        )
        self.assertEqual(term.target_urn, A)
        self.assertEqual(term.field_path, "order_total")

    def test_unresolved_glossary_reference_is_retained(self) -> None:
        unresolved = next(
            item
            for item in self.a.glossary_terms
            if item.term_urn == MISSING_TERM
        )
        self.assertEqual(unresolved.state, MetadataState.UNRESOLVED)
        self.assertIsNone(unresolved.name)
        self.assertTrue(
            any(
                finding.reference_urn == MISSING_TERM
                for finding in self.result.findings
            )
        )

    def test_unrelated_field_governance_is_out_of_scope(self) -> None:
        self.assertFalse(
            any(item.field_path == "unrelated_field" for item in self.a.tags)
        )

    def test_property_definition_and_assignment_are_distinct(self) -> None:
        self.assertEqual(
            self.result.snapshot.structured_property_definitions[0]
            .property_urn,
            PROPERTY,
        )
        self.assertEqual(self.a.structured_properties[0].values, ("value",))

    def test_dataset_with_no_property_values_is_absent(self) -> None:
        self.assertEqual(self.b.structured_properties, ())
        self.assertEqual(
            self.b.structured_property_state,
            MetadataState.ABSENT,
        )

    def test_data_product_membership_and_absence(self) -> None:
        self.assertEqual(self.a.data_products[0].product_urn, PRODUCT)
        self.assertEqual(self.b.data_products, ())
        self.assertEqual(self.b.data_product_state, MetadataState.ABSENT)

    def test_no_product_membership_is_not_fabricated(self) -> None:
        self.assertEqual(self.b.data_products, ())
        self.assertNotEqual(
            self.b.data_product_state,
            MetadataState.UNRESOLVED,
        )

    def test_related_document_relationship(self) -> None:
        self.assertEqual(self.a.documents[0].document_urn, DOCUMENT)
        self.assertEqual(
            self.a.documents[0].evidence.aspect_or_relationship,
            "RelatedAsset",
        )

    def test_pipeline_context_does_not_change_dataset_count(self) -> None:
        self.assertEqual(self.result.snapshot.dataset_count, 2)
        self.assertEqual(len(self.result.snapshot.pipeline_context), 1)
        self.assertEqual(
            self.result.snapshot.pipeline_context[0].job_urn,
            JOB,
        )

    def test_bi_context_is_reachable_not_confirmed(self) -> None:
        self.assertTrue(self.result.snapshot.bi_context)
        self.assertTrue(
            all(
                item.classification
                is BusinessIntelligenceClassification.REACHABLE_CONTEXT
                for item in self.result.snapshot.bi_context
            )
        )

    def test_same_name_dashboards_are_platform_qualified(self) -> None:
        dashboards = tuple(
            item
            for item in self.result.snapshot.bi_context
            if item.entity_type == "DASHBOARD"
        )
        self.assertEqual(len(dashboards), 2)
        self.assertEqual(
            {item.qualified_name for item in dashboards},
            {
                "Looker / Order Entry Dashboard",
                "Tableau / Order Entry Dashboard",
            },
        )
        self.assertEqual(len({item.urn for item in dashboards}), 2)

    def test_relationship_path_is_retained(self) -> None:
        dashboard = next(
            item
            for item in self.a.bi_context
            if item.urn == LOOKER_DASHBOARD
        )
        self.assertEqual(
            dashboard.relationship_path,
            (A, B, LOOKER_CHART, LOOKER_DASHBOARD),
        )

    def test_deterministic_output_excludes_observation_time(self) -> None:
        repeated = AssetContextRetriever(
            FakeContextTransport(),
            clock=lambda: datetime(
                2027,
                1,
                1,
                tzinfo=timezone.utc,
            ),
        ).retrieve(graph())
        self.assertTrue(
            self.result.snapshot.semantically_equals(repeated.snapshot)
        )

    def test_cache_is_keyed_by_machine_identity(self) -> None:
        self.assertEqual(self.transport.calls[("TAG", TAG_A)], 1)
        self.assertEqual(self.transport.calls[("lineage", B)], 1)

    def test_evidence_is_retained(self) -> None:
        self.assertTrue(self.a.evidence)
        self.assertTrue(
            all(item.interface for item in self.a.evidence)
        )
        self.assertTrue(
            any(
                item.aspect_or_relationship == "ownership"
                and item.target_urn is None
                for item in self.b.evidence
            )
        )

    def test_optional_metadata_absence_does_not_fail(self) -> None:
        self.assertEqual(
            self.result.state,
            ContextRetrievalState.RETRIEVED,
        )
        self.assertEqual(self.b.document_state, MetadataState.ABSENT)

    def test_secret_redaction(self) -> None:
        secret = "phase15-secret"

        class FailingTransport(FakeContextTransport):
            def governance_aspects(self, dataset_urn: str):
                raise GovernanceRetrievalUnavailable(
                    "Governance read failed.",
                    diagnostic=f"token={secret}",
                )

        result = AssetContextRetriever(FailingTransport()).retrieve(graph())
        self.assertEqual(result.state, ContextRetrievalState.PARTIAL)
        self.assertNotIn(secret, str(result.to_dict()))

    def test_public_boundary_is_read_only(self) -> None:
        forbidden = {
            "create",
            "update",
            "delete",
            "patch",
            "upsert",
            "emit",
            "rollback",
            "mutation",
        }
        public = {
            name.casefold()
            for name, value in inspect.getmembers(
                AssetContextRetriever,
                predicate=callable,
            )
            if not name.startswith("_")
        }
        self.assertFalse(
            any(word in name for name in public for word in forbidden)
        )


if __name__ == "__main__":
    unittest.main()
