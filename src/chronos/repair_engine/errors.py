"""Bounded Phase 6.4 repair-generation failures."""


class RepairEngineError(Exception):
    """Base class for expected, user-facing repair-generation failures."""


class RepairProposalError(RepairEngineError):
    """The repair proposal is not strict, complete, or internally consistent."""


class PredecessorTrustError(RepairEngineError):
    """The predecessor analysis or matching repository evidence is not trusted."""


class RepairSelectionError(RepairEngineError):
    """Requested roots or logical groups do not belong to the predecessor."""


class RepairPlanningError(RepairEngineError):
    """A deterministic repair plan cannot be constructed."""


class UnsupportedRepairError(RepairEngineError):
    """A proposed target falls outside the supported static repair boundary."""


class RepairEditError(RepairEngineError):
    """An exact parser-backed edit could not be generated safely."""


class RepairValidationError(RepairEngineError):
    """A generated candidate or patch failed static validation."""


class RepairCertificationError(RepairEngineError):
    """The repair artifact package failed deterministic certification."""


class RepairOutputError(RepairEngineError):
    """The isolated repair output boundary is unsafe or already occupied."""
