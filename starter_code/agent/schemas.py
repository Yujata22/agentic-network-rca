from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    A single evidence-gathering action proposed by the investigation planner.
    """

    tool: Literal[
        "get_device_context",
        "get_syslogs",
        "get_telemetry",
    ]

    reason: str

    parameters: dict = Field(
        default_factory=dict,
        description=(
            "Arguments required by the selected tool. "
            "Examples include hostnames, device_ids, start_time, and end_time."
        ),
    )


class InvestigationPlan(BaseModel):
    """
    Structured investigation plan produced before tool execution.
    """

    next_actions: list[InvestigationAction]

    analysis_focus: list[str]


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