"""Public Phase 6.4 repair-generation API."""

from .engine import REPAIR_ARTIFACT_FILENAMES, generate_repair
from .errors import (
    PredecessorTrustError,
    RepairCertificationError,
    RepairEditError,
    RepairEngineError,
    RepairOutputError,
    RepairPlanningError,
    RepairProposalError,
    RepairSelectionError,
    RepairValidationError,
    UnsupportedRepairError,
)
from .models import (
    EditOperation,
    RepairCompleteness,
    RepairDisposition,
    RepairGenerationProposal,
    RepairGenerationResult,
    RepairMode,
    RepairOperation,
    RepairabilityState,
)
from .proposals import parse_repair_proposal, repair_proposal_to_dict
from .rules import RepairRuleRegistry

__all__ = [
    "EditOperation",
    "PredecessorTrustError",
    "REPAIR_ARTIFACT_FILENAMES",
    "RepairCertificationError",
    "RepairCompleteness",
    "RepairDisposition",
    "RepairEditError",
    "RepairEngineError",
    "RepairGenerationProposal",
    "RepairGenerationResult",
    "RepairMode",
    "RepairOperation",
    "RepairOutputError",
    "RepairPlanningError",
    "RepairProposalError",
    "RepairRuleRegistry",
    "RepairSelectionError",
    "RepairValidationError",
    "RepairabilityState",
    "UnsupportedRepairError",
    "generate_repair",
    "parse_repair_proposal",
    "repair_proposal_to_dict",
]
