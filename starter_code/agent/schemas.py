from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Intent routing
# ---------------------------------------------------------------------------

class IntentDecision(BaseModel):
    """Structured output used by the intent-routing node."""

    intent: Literal[
        "investigation",
        "follow_up",
        "general_qa",
    ]
    reason: str


# ---------------------------------------------------------------------------
# Investigation planning
# ---------------------------------------------------------------------------

class InvestigationAction(BaseModel):
    """
    One evidence-gathering action selected by the planner.

    Tool-specific arguments are represented explicitly and validated
    deterministically before execution.
    """

    tool: Literal[
        "get_device_context",
        "get_syslogs",
        "get_telemetry",
    ]

    reason: str

    hostnames: list[str] | None = None
    device_ids: list[str] | None = None
    start_time: str | None = None
    end_time: str | None = None
    message_type: str | None = None


class InvestigationPlan(BaseModel):
    """
    Structured investigation plan produced before tool execution.

    Some LLM providers may emit a single action object when only one
    evidence action is required. The schema deliberately accepts both
    a single action and a list; application code normalizes to a list.
    """

    next_actions: list[InvestigationAction] | InvestigationAction

    analysis_focus: list[str] | str = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_shape(cls, value):
        """
        Tolerate common structured-output variations from the LLM.

        The contract remains list-based, but some providers occasionally emit:
        - a single action object instead of a list; or
        - a JSON-encoded action/plan string.

        Normalize those shapes before normal Pydantic validation.
        """
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value

        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        actions = normalized.get("next_actions", [])

        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except json.JSONDecodeError:
                actions = [actions]

        if isinstance(actions, dict):
            actions = [actions]

        if isinstance(actions, list):
            parsed_actions = []
            for action in actions:
                if isinstance(action, str):
                    try:
                        action = json.loads(action)
                    except json.JSONDecodeError:
                        pass
                parsed_actions.append(action)
            normalized["next_actions"] = parsed_actions

        focus = normalized.get("analysis_focus", [])
        if focus is None:
            normalized["analysis_focus"] = []
        elif isinstance(focus, str):
            normalized["analysis_focus"] = [focus]

        return normalized


class EvidenceAssessment(BaseModel):
    """
    Structured assessment of the evidence collected during an investigation.
    """

    likely_cause_hypothesis: str = Field(
        description=(
            "Most plausible cause supported by the currently available evidence. "
            "Must not be more specific than the evidence supports."
        )
    )

    supporting_findings: list[str] = Field(
        default_factory=list,
        description="Important observations that support the current hypothesis.",
    )

    contradictory_findings: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence that conflicts with or weakens the current hypothesis."
        ),
    )

    missing_evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence that would materially improve or validate the investigation."
        ),
    )

    evidence_sufficient: bool = Field(
        description=(
            "True when the available evidence is sufficient to produce a "
            "responsible RCA; false when another evidence-gathering round is needed."
        )
    )

    confidence: Literal["high", "medium", "low"]

    reasoning_summary: str

# ---------------------------------------------------------------------------
# RCA evidence
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """A single piece of evidence supporting the final RCA."""

    evidence_id: str = Field(
        description="Stable identifier such as E1, E2, E3."
    )

    source: Literal[
        "detected_anomalies",
        "network_devices",
        "device_syslogs",
        "device_telemetry",
    ]

    description: str

    device: str | None = None

    timestamp: str | None = None


# ---------------------------------------------------------------------------
# Final RCA
# ---------------------------------------------------------------------------

class RCAResult(BaseModel):
    """Structured final root-cause analysis returned by the agent."""

    root_cause: str

    confidence: Literal[
        "high",
        "medium",
        "low",
    ]

    affected_devices: list[str]

    timeframe: str

    supporting_evidence: list[EvidenceItem]

    contradictory_or_missing_evidence: list[str]

    downstream_impacts: list[str]

    recommended_next_checks: list[str]

    @model_validator(mode="before")
    @classmethod
    def normalize_list_fields(cls, value):
        """
        Normalize common LLM structured-output variations.

        Some providers may emit a single string/object instead of a list
        when only one item is present. Convert those shapes into lists
        before normal Pydantic validation.
        """
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value

        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        string_list_fields = [
            "affected_devices",
            "contradictory_or_missing_evidence",
            "downstream_impacts",
            "recommended_next_checks",
        ]

        for field_name in string_list_fields:
            field_value = normalized.get(field_name)

            if field_value is None:
                normalized[field_name] = []

            elif isinstance(field_value, str):
                normalized[field_name] = [field_value]

        evidence = normalized.get("supporting_evidence")

        if evidence is None:
            normalized["supporting_evidence"] = []

        elif isinstance(evidence, dict):
            normalized["supporting_evidence"] = [evidence]

        return normalized