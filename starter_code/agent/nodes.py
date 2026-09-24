from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm
from agent.schemas import IntentDecision
from agent.state import AgentState


ANOMALY_ID_PATTERN = re.compile(
    r"a1f0c8e2-1b44-4d90-9c31-\d{12}",
    re.IGNORECASE,
)


def route_request(state: AgentState) -> dict:
    """
    Classify the current user request into one of three routes:

    - investigation: starts a new anomaly investigation
    - follow_up: refers to an existing investigation/conversation context
    - general_qa: general networking/domain question
    """

    messages = state.get("messages", [])

    if not messages:
        raise ValueError("route_request requires at least one message.")

    latest_message = messages[-1]
    user_text = latest_message.content.strip()

    # Deterministic fast path:
    # An explicit anomaly ID clearly starts a new investigation.
    anomaly_match = ANOMALY_ID_PATTERN.search(user_text)

    if anomaly_match:
        return {
            "intent": "investigation",
            "anomaly_id": anomaly_match.group(0),
        }

    has_existing_investigation = bool(
        state.get("anomaly_id")
        or state.get("anomaly")
        or state.get("rca")
    )

    llm = get_llm().with_structured_output(IntentDecision)

    prompt = [
        SystemMessage(
            content=(
                "You are an intent router for a network investigation agent. "
                "Classify the latest user request into exactly one category:\n"
                "\n"
                "investigation: the user wants to start a new RCA investigation "
                "of a detected anomaly.\n"
                "\n"
                "follow_up: the user is asking about the current/previous "
                "investigation and relies on existing conversational context.\n"
                "\n"
                "general_qa: a general networking question that does not require "
                "a specific anomaly investigation.\n"
                "\n"
                f"Existing investigation context available: "
                f"{has_existing_investigation}.\n"
                "\n"
                "If there is no existing investigation context, do not classify "
                "an ambiguous standalone question as follow_up."
            )
        ),
        HumanMessage(content=user_text),
    ]

    decision = llm.invoke(prompt)

    return {
        "intent": decision.intent,
    }
