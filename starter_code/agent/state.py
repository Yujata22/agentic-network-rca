from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    Shared state carried through the LangGraph workflow.

    Conversation history and structured investigation context are kept
    separately so the agent does not need to reconstruct critical state
    from chat history on every turn.
    """

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    messages: Annotated[list, add_messages]

    # ------------------------------------------------------------------
    # Request routing
    # ------------------------------------------------------------------

    intent: Literal[
        "investigation",
        "follow_up",
        "general_qa",
    ]

    # ------------------------------------------------------------------
    # Current investigation
    # ------------------------------------------------------------------

    anomaly_id: str | None

    anomaly: dict[str, Any] | None

    # ------------------------------------------------------------------
    # Evidence gathered
    # ------------------------------------------------------------------

    device_context: list[dict[str, Any]]

    syslogs: list[dict[str, Any]]

    telemetry: list[dict[str, Any]]

    # ------------------------------------------------------------------
    # Investigation planning / control
    # ------------------------------------------------------------------

    planned_actions: list[dict[str, Any]]

    investigation_summary: str | None

    evidence_assessment: dict[str, Any] | None

    needs_more_evidence: bool

    investigation_round: int

    # ------------------------------------------------------------------
    # Final RCA
    # ------------------------------------------------------------------

    rca: dict[str, Any] | None