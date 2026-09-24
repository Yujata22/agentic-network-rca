from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class IntentDecision(BaseModel):
    intent: Literal["investigation", "follow_up", "general_qa"]
    reason: str


class EvidenceItem(BaseModel):
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


class RCAResult(BaseModel):
    root_cause: str
    confidence: Literal["high", "medium", "low"]
    affected_devices: list[str]
    timeframe: str
    supporting_evidence: list[EvidenceItem]
    contradictory_or_missing_evidence: list[str]
    downstream_impacts: list[str]
    recommended_next_checks: list[str]