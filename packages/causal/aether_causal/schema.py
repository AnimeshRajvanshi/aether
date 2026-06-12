"""Schema for ranked source-attribution hypotheses (Stage B).

These Pydantic models are the contract for ``hypotheses.json``. Every model is
``extra="forbid"`` so unknown fields fail loudly. The design encodes the cardinal
rule structurally:

  - A candidate that names an OGIM entity MUST carry its ``ogim_id`` + ``ogim_layer``
    so the no-fabrication guard can verify it against the committed subset.
  - Confidence is a qualitative tier PLUS transparent, weighted score components
    (each with a rationale). The score is explicitly a documented heuristic, not a
    calibrated probability (``HypothesisSet.scoring_disclaimer``).
  - Evidence items carry an optional ``temporal_caveat`` so time-mismatched
    corroboration (e.g. a later VIIRS flare) cannot be read as evidence about the
    specific plume.
  - Assumptions and counter-considerations are required, first-class fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceTier(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class CandidateKind(StrEnum):
    OGIM_FIELD = "ogim_field"  # a named OGIM field polygon (real record)
    OGIM_FACILITY = "ogim_facility"  # a named OGIM facility/well point (real record)
    SECTOR = "sector"  # a sector-level descriptor (no OGIM point record)


class Candidate(_Base):
    """What a hypothesis attributes the plume to. OGIM-backed candidates must
    carry the real record identifiers so they are verifiable."""

    kind: CandidateKind
    descriptor: str
    ogim_layer: str | None = None
    ogim_id: int | None = None
    ogim_name: str | None = None
    operator: str | None = None  # from OGIM if present (blank for these records)


class SourceRef(_Base):
    """Traceability pointer: the committed file/record a fact comes from."""

    dataset: str
    locator: str
    ogim_id: int | None = None
    ogim_layer: str | None = None


class EvidenceItem(_Base):
    kind: str
    statement: str
    source: SourceRef
    temporal_caveat: str | None = None


class ScoreComponent(_Base):
    name: str
    value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    rationale: str
    # Always recomputed = value * weight so it stays consistent (and round-trips).
    contribution: float = 0.0

    @model_validator(mode="after")
    def _set_contribution(self) -> ScoreComponent:
        object.__setattr__(self, "contribution", round(self.value * self.weight, 4))
        return self


class SourceHypothesis(_Base):
    id: str
    rank: int = Field(ge=1)
    candidate: Candidate
    claim: str
    confidence_tier: ConfidenceTier
    confidence_rationale: str
    score: float = Field(ge=0.0, le=1.0)
    score_components: list[ScoreComponent]
    evidence: list[EvidenceItem]
    assumptions: list[str]
    counter_considerations: list[str]
    falsification: str
    generation_method: str


class HypothesisSet(_Base):
    """The full Stage B output: the ranked hypotheses plus the honesty framing."""

    event_id: str
    phenomenon: str
    generated_method: str
    headline_finding: str
    scoring_disclaimer: str
    confidence_cap: str
    plume_summary: dict[str, str]
    global_assumptions: list[str]
    hypotheses: list[SourceHypothesis]
    provenance: dict[str, str]


# --------------------------------------------------------------------------- #
# Factor hypotheses (Sprint 9 Stage C — heat vertical, ADR 0005)
# --------------------------------------------------------------------------- #


class FactorRole(StrEnum):
    """How a factor participates in the explanation.

    WARMING_CONTRIBUTOR — a physical driver ranked for its contribution.
    SEVERITY_FRAMING — modulates experienced severity, not the temperature
    anomaly itself (e.g., humidity).
    COUNTER_EVIDENCE — the data argues AGAINST this factor at the observed
    time; it is listed so a popular prior cannot be silently presumed.
    """

    WARMING_CONTRIBUTOR = "warming_contributor"
    SEVERITY_FRAMING = "severity_framing"
    COUNTER_EVIDENCE = "counter_evidence"


class Diagnostic(_Base):
    """One computed number a factor claim binds to (no-fabrication-for-factors).

    Every diagnostic names the committed artifact / cached dataset it was
    computed from. A factor with no diagnostics cannot exist (schema-enforced).
    """

    name: str
    value: float
    unit: str
    definition: str
    source: SourceRef


class FactorHypothesis(_Base):
    """A ranked contributing FACTOR with mandatory computed diagnostics.

    The heat vertical's analogue of SourceHypothesis: candidates become
    physical factors; the bearing wedge becomes a diagnostics list. The
    ``diagnostics`` field is required and non-empty — the structural form of
    the no-fabrication-for-factors rule: no diagnostic, no factor.
    """

    id: str
    rank: int = Field(ge=1)
    factor_name: str
    role: FactorRole
    claim: str
    confidence_tier: ConfidenceTier
    confidence_rationale: str
    score: float = Field(ge=0.0, le=1.0)
    score_components: list[ScoreComponent]
    diagnostics: list[Diagnostic] = Field(min_length=1)
    evidence: list[EvidenceItem]
    assumptions: list[str]
    counter_considerations: list[str]
    falsification: str
    generation_method: str


class FactorHypothesisSet(_Base):
    """The Stage C heat-attribution output: ranked factors + honesty framing.

    ``external_published_attribution`` is the ONLY place published
    extreme-event attribution (e.g., WWA/Zachariah) may appear — cited
    evidence with a source, never blended into factor scores
    (``attribution_boundary`` states this in the artifact itself).
    """

    event_id: str
    phenomenon: str
    generated_method: str
    headline_finding: str
    scoring_disclaimer: str
    confidence_cap: str
    attribution_boundary: str
    event_summary: dict[str, str]
    global_assumptions: list[str]
    factors: list[FactorHypothesis]
    external_published_attribution: list[EvidenceItem]
    provenance: dict[str, str]
