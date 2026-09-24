from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Conversation state
    messages: Annotated[list, add_messages]

    # Request classification
    intent: Literal["investigation", "follow_up", "general_qa"]

    # Current investigation
    anomaly_id: str | None
    anomaly: dict[str, Any] | None

    # Evidence gathered during the investigation
    device_context: list[dict[str, Any]]
    syslogs: list[dict[str, Any]]
    telemetry: list[dict[str, Any]]

    # Agent reasoning/control state
    investigation_summary: str | None
    needs_more_evidence: bool
    investigation_round: int

    # Final structured result
    rca: dict[str, Any] | None