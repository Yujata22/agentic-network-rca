from __future__ import annotations
from agent.tools import (
    get_device_context,
    get_syslogs,
    get_telemetry,
)
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm
from agent.schemas import IntentDecision, InvestigationPlan
from agent.state import AgentState


ANOMALY_ID_PATTERN = re.compile(
    r"a1f0c8e2-1b44-4d90-9c31-\d{12}",
    re.IGNORECASE,
)


def route_request(state: AgentState) -> dict:
    """
    Classify the latest user request into one of three routes:

    - investigation
    - follow_up
    - general_qa
    """

    messages = state.get("messages", [])

    if not messages:
        raise ValueError("route_request requires at least one message.")

    latest_message = messages[-1]
    user_text = latest_message.content.strip()

    # Deterministic fast path for explicit anomaly IDs.
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
                "You are an intent router for a network investigation agent.\n\n"
                "Classify the latest user request into exactly one category:\n\n"
                "investigation: the user wants to start a new RCA investigation "
                "of a detected anomaly.\n\n"
                "follow_up: the user is asking about the current or previous "
                "investigation and relies on existing conversational context.\n\n"
                "general_qa: a general networking question that does not require "
                "a specific anomaly investigation.\n\n"
                f"Existing investigation context available: "
                f"{has_existing_investigation}.\n\n"
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


def plan_investigation(state: AgentState) -> dict:
    """
    Decide what evidence should be gathered next based on:
    - the anomaly
    - evidence already collected
    - the current investigation round

    This node plans evidence collection but does not execute tools.
    """

    anomaly = state.get("anomaly")

    if not anomaly:
        raise ValueError(
            "plan_investigation requires anomaly context."
        )

    evidence_summary = {
        "device_context_available": bool(
            state.get("device_context")
        ),
        "syslogs_available": bool(
            state.get("syslogs")
        ),
        "telemetry_available": bool(
            state.get("telemetry")
        ),
        "investigation_round": state.get(
            "investigation_round",
            0,
        ),
    }

    llm = get_llm().with_structured_output(
        InvestigationPlan
    )

    prompt = [
        SystemMessage(
            content=(
                "You are planning a network root-cause investigation.\n\n"

                "You may choose only from these read-only evidence tools:\n\n"

                "1. get_device_context\n"
                "Purpose: resolve impacted hostnames into device IDs and retrieve "
                "inventory, role, site, topology notes, and WAN context.\n"
                "Required parameters:\n"
                '{"hostnames": ["hostname1", "hostname2"]}\n\n'

                "2. get_syslogs\n"
                "Purpose: retrieve fine-grained network/device events during a "
                "UTC time window.\n"
                "Required parameters:\n"
                '{"device_ids": ["DEV-0001"], '
                '"start_time": "YYYY-MM-DD HH:MM:SS", '
                '"end_time": "YYYY-MM-DD HH:MM:SS"}\n'
                "Optional parameter:\n"
                '{"message_type": "interface"}\n\n'

                "3. get_telemetry\n"
                "Purpose: retrieve hourly quantitative metrics for devices during "
                "a UTC time window.\n"
                "Required parameters:\n"
                '{"device_ids": ["DEV-0001"], '
                '"start_time": "YYYY-MM-DD HH:MM:SS", '
                '"end_time": "YYYY-MM-DD HH:MM:SS"}\n\n'

                "Planning rules:\n"
                "1. Do not assume a fixed tool sequence based only on detector type.\n"
                "2. Select evidence based on the anomaly and evidence already collected.\n"
                "3. Prefer the minimum evidence required to test plausible hypotheses.\n"
                "4. Do not request evidence already available unless there is a "
                "clear reason to inspect it again.\n"
                "5. Detector fields such as event_summary and flap_timeline are "
                "investigation clues, not final RCA conclusions.\n"
                "6. If a tool requires device_ids but only hostnames are currently "
                "known, request get_device_context first.\n"
                "7. Use the anomaly window as the primary evidence time range. "
                "A modest surrounding context window may be used if justified.\n"
                "8. All timestamps are UTC.\n"
                "9. Do not propose remediation or write actions.\n"
                "10. Every planned action must contain valid parameters for that tool.\n"
            )
        ),
        HumanMessage(
            content=(
                f"Anomaly:\n{anomaly}\n\n"
                f"Current evidence state:\n{evidence_summary}\n\n"
                "Produce the next investigation plan."
            )
        ),
    ]

    plan = llm.invoke(prompt)

    return {
        "planned_actions": [
            action.model_dump()
            for action in plan.next_actions
        ],
        "investigation_summary": (
            " | ".join(plan.analysis_focus)
            if plan.analysis_focus
            else None
        ),
    }

def execute_planned_actions(state: AgentState) -> dict:
    """
    Execute the read-only evidence actions selected by the planner.

    The LLM decides what evidence is needed. This node deterministically
    validates and executes only the tools explicitly allowed by the application.
    """

    planned_actions = state.get("planned_actions", [])

    if not planned_actions:
        return {
            "investigation_round": state.get("investigation_round", 0) + 1
        }

    tool_registry = {
        "get_device_context": get_device_context,
        "get_syslogs": get_syslogs,
        "get_telemetry": get_telemetry,
    }

    state_field_registry = {
        "get_device_context": "device_context",
        "get_syslogs": "syslogs",
        "get_telemetry": "telemetry",
    }

    updates = {}

    for action in planned_actions:
        tool_name = action.get("tool")
        parameters = action.get("parameters", {})

        if tool_name not in tool_registry:
            raise ValueError(
                f"Unsupported investigation tool: {tool_name}"
            )

        if not isinstance(parameters, dict):
            raise ValueError(
                f"Parameters for {tool_name} must be a dictionary."
            )

        tool = tool_registry[tool_name]

        result = tool.invoke(parameters)

        if not isinstance(result, list):
            raise TypeError(
                f"{tool_name} returned {type(result).__name__}; "
                "expected a list."
            )

        state_field = state_field_registry[tool_name]
        updates[state_field] = result

    updates["investigation_round"] = (
        state.get("investigation_round", 0) + 1
    )

    return updates