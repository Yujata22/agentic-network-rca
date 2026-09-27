from __future__ import annotations
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agent.llm import get_llm
from agent.state import AgentState
from agent.schemas import (
    IntentDecision,
    InvestigationPlan,
    EvidenceAssessment,
    RCAResult,
)

from agent.tools import (
    get_anomaly,
    get_device_context,
    get_syslogs,
    get_telemetry,
)

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

    device_context = state.get("device_context", [])
    syslogs = state.get("syslogs", [])
    telemetry = state.get("telemetry", [])

    evidence_summary = {
        "device_context_available": bool(device_context),
        "device_context": device_context,

        "syslogs_available": bool(syslogs),
        "syslogs_count": len(syslogs),

        "telemetry_available": bool(telemetry),
        "telemetry_count": len(telemetry),

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

                "IMPORTANT OUTPUT SHAPE:\n"
                "- next_actions MUST always be a JSON array, even when there is only one action.\n"
                "- analysis_focus MUST always be a JSON array of strings.\n"
                "Example wrapper: {\"next_actions\": [{...}], \"analysis_focus\": [\"...\"]}.\n\n"

                "IMPORTANT TOOL ARGUMENT FORMAT:\n\n"

                "For get_device_context, return a flat action object like:\n"
                '{"tool": "get_device_context", '
                '"reason": "...", '
                '"hostnames": ["hostname1", "hostname2"]}\n\n'

                "For get_syslogs, return a flat action object like:\n"
                '{"tool": "get_syslogs", '
                '"reason": "...", '
                '"device_ids": ["DEV-001", "DEV-002"], '
                '"start_time": "YYYY-MM-DD HH:MM:SS", '
                '"end_time": "YYYY-MM-DD HH:MM:SS", '
                '"message_type": null}\n\n'

                "For get_telemetry, return a flat action object like:\n"
                '{"tool": "get_telemetry", '
                '"reason": "...", '
                '"device_ids": ["DEV-001", "DEV-002"], '
                '"start_time": "YYYY-MM-DD HH:MM:SS", '
                '"end_time": "YYYY-MM-DD HH:MM:SS"}\n\n'

                "Do not nest tool arguments inside a parameters object.\n"
                "Only populate arguments accepted by the selected tool.\n\n"

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
                "11. If device_context is already present, do not request "
                "get_device_context again unless the existing context is clearly incomplete "
                "for the impacted hosts.\n"
                "12. Use the actual evidence already provided in Current evidence state "
                "when deciding the next tool. Do not rely only on availability flags.\n"
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

    # Defensive handling for occasional provider-side structured-output nulls.
    if plan is None:
        model_output = anomaly.get("model_output") or {}
        impacted_hostnames = model_output.get("impacted_hostnames") or []

        if impacted_hostnames and not device_context:
            return {
                "planned_actions": [
                    {
                        "tool": "get_device_context",
                        "reason": (
                            "Structured planner output was empty; recover by "
                            "resolving impacted hostnames to device context first."
                        ),
                        "parameters": {
                            "hostnames": impacted_hostnames,
                        },
                    }
                ],
                "investigation_summary": (
                    "Planner returned no structured action. Falling back to "
                    "deterministic device-context resolution from anomaly metadata."
                ),
            }

        raise ValueError(
            "Planner returned no structured investigation plan."
        )

    actions = (
        plan.next_actions
        if isinstance(plan.next_actions, list)
        else [plan.next_actions]
    )

    analysis_focus = (
        plan.analysis_focus
        if isinstance(plan.analysis_focus, list)
        else [plan.analysis_focus]
    )

    model_output = anomaly.get("model_output") or {}
    anomaly_window = model_output.get("window") or {}

    default_start_time = anomaly_window.get("start")
    default_end_time = anomaly_window.get("end")

    # Tools accept naive UTC timestamps; anomaly window values may contain Z.
    if isinstance(default_start_time, str):
        default_start_time = (
            default_start_time
            .replace("T", " ")
            .replace("Z", "")
        )

    if isinstance(default_end_time, str):
        default_end_time = (
            default_end_time
            .replace("T", " ")
            .replace("Z", "")
        )

    resolved_device_ids = [
        device.get("device_id")
        for device in device_context
        if isinstance(device, dict) and device.get("device_id")
    ]

    planned_actions = []

    for action in actions:
        if action is None:
            continue

        if action.tool == "get_device_context":
            hostnames = action.hostnames

            if not hostnames:
                hostnames = (
                    model_output.get("impacted_hostnames")
                    or []
                )

            if not hostnames:
                raise ValueError(
                    "Planner selected get_device_context, but no hostnames "
                    "were supplied by the planner or available in the anomaly."
                )

            parameters = {
                "hostnames": hostnames,
            }

        elif action.tool == "get_syslogs":
            device_ids = (
                action.device_ids
                or resolved_device_ids
            )

            start_time = (
                action.start_time
                or default_start_time
            )

            end_time = (
                action.end_time
                or default_end_time
            )

            if not device_ids or not start_time or not end_time:
                raise ValueError(
                    "Planner selected get_syslogs but required arguments "
                    "could not be resolved from either planner output or "
                    "existing investigation state."
                )

            parameters = {
                "device_ids": device_ids,
                "start_time": start_time,
                "end_time": end_time,
            }

            if action.message_type:
                parameters["message_type"] = action.message_type

        elif action.tool == "get_telemetry":
            device_ids = (
                action.device_ids
                or resolved_device_ids
            )

            start_time = (
                action.start_time
                or default_start_time
            )

            end_time = (
                action.end_time
                or default_end_time
            )

            if not device_ids or not start_time or not end_time:
                raise ValueError(
                    "Planner selected get_telemetry but required arguments "
                    "could not be resolved from either planner output or "
                    "existing investigation state."
                )

            parameters = {
                "device_ids": device_ids,
                "start_time": start_time,
                "end_time": end_time,
            }

        else:
            raise ValueError(
                f"Unsupported planner tool: {action.tool}"
            )

        planned_actions.append(
            {
                "tool": action.tool,
                "reason": action.reason,
                "parameters": parameters,
            }
        )

    if not planned_actions:
        raise ValueError(
            "Planner produced no executable investigation actions."
        )

    return {
        "planned_actions": planned_actions,
        "investigation_summary": (
            " | ".join(analysis_focus)
            if analysis_focus
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

def analyze_evidence(state: AgentState) -> dict:
    """
    Assess the evidence collected so far and decide whether it is sufficient
    to produce a responsible RCA.

    This node does not retrieve new evidence and does not produce the final RCA.
    It only evaluates the current evidence set.
    """

    anomaly = state.get("anomaly")
    device_context = state.get("device_context", [])
    syslogs = state.get("syslogs", [])
    telemetry = state.get("telemetry", [])
    investigation_round = state.get("investigation_round", 0)

    if not anomaly:
        raise ValueError(
            "analyze_evidence requires anomaly context."
        )

    llm = get_llm().with_structured_output(
        EvidenceAssessment
    )

    prompt = [
        SystemMessage(
            content=(
                "You are evaluating evidence for a network root-cause investigation.\n\n"

                "Your job is to assess the evidence currently available, not to "
                "retrieve additional data and not to write the final RCA.\n\n"

                "Important rules:\n"
                "1. Distinguish likely cause from downstream symptoms.\n"
                "2. Base conclusions only on the supplied anomaly, device context, "
                "syslogs, and telemetry.\n"
                "3. Do not invent device state, topology, measurements, or events.\n"
                "4. Do not claim a specific failed physical component unless the "
                "evidence directly establishes it.\n"
                "5. NULL or missing telemetry means unavailable/not applicable, "
                "not zero.\n"
                "6. Detector payload fields are clues, not ground truth RCA.\n"
                "7. Consider temporal ordering: evidence that precedes an event can "
                "be more causally informative than downstream effects.\n"
                "8. Identify contradictory or missing evidence explicitly.\n"
                "9. Set evidence_sufficient=True only if the evidence supports a "
                "responsible RCA conclusion with an appropriate confidence level.\n"
                "10. If evidence is still thin or multiple materially different "
                "causes remain plausible, set evidence_sufficient=False.\n"
                "11. Confidence must reflect evidence quality, not writing certainty.\n"
                "12. Avoid absolute terms such as 'conclusive', 'definitive', or "
                "'proven' unless the evidence directly establishes the exact cause.\n"
                "13. Distinguish the supported failure domain from the exact failed "
                "component. For example, evidence may support optical/physical-layer "
                "degradation without establishing whether the fiber, transceiver, "
                "connector, or another physical component failed.\n"
                "14. When the exact physical component or mechanism is not directly "
                "observed, include that limitation under missing_evidence even if the "
                "overall RCA is sufficiently supported.\n"
                "15. Use corroborating evidence from multiple available sources when "
                "relevant. Do not ignore telemetry if it materially supports or weakens "
                "the hypothesis.\n"
            )
        ),
        HumanMessage(
            content=(
                f"Anomaly:\n{anomaly}\n\n"
                f"Device context:\n{device_context}\n\n"
                f"Syslogs:\n{syslogs}\n\n"
                f"Telemetry:\n{telemetry}\n\n"
                f"Investigation round: {investigation_round}\n\n"
                "Assess the current evidence."
            )
        ),
    ]

    assessment = llm.invoke(prompt)

    return {
        "needs_more_evidence": not assessment.evidence_sufficient,
        "investigation_summary": assessment.reasoning_summary,
        "evidence_assessment": assessment.model_dump(),
    }

def synthesize_rca(state: AgentState) -> dict:
    """
    Produce the final structured RCA from the collected evidence
    and the prior evidence assessment.
    """

    anomaly = state.get("anomaly")
    device_context = state.get("device_context", [])
    syslogs = state.get("syslogs", [])
    telemetry = state.get("telemetry", [])
    evidence_assessment = state.get("evidence_assessment")

    if not anomaly:
        raise ValueError("synthesize_rca requires anomaly context.")

    if not evidence_assessment:
        raise ValueError(
            "synthesize_rca requires an evidence assessment."
        )

    llm = get_llm().with_structured_output(RCAResult)

    prompt = [
        SystemMessage(
            content=(
                "You are producing the final root-cause analysis for a "
                "network investigation.\n\n"

                "Use only the supplied evidence and prior evidence assessment.\n\n"

                "Rules:\n"
                "1. Distinguish root cause from downstream symptoms.\n"
                "2. Do not claim a more specific failure than the evidence supports.\n"
                "3. Preserve uncertainty and known evidence gaps.\n"
                "4. Supporting evidence must be concrete and traceable to one of "
                "the supplied data sources.\n"
                "5. Recommended next checks may suggest investigation or validation "
                "steps, but must not perform remediation.\n"
                "6. Do not invent measurements, devices, events, or timestamps.\n"
                "7. Use concise operational language suitable for a network engineer.\n"
            )
        ),
        HumanMessage(
            content=(
                f"Anomaly:\n{anomaly}\n\n"
                f"Device context:\n{device_context}\n\n"
                f"Syslogs:\n{syslogs}\n\n"
                f"Telemetry:\n{telemetry}\n\n"
                f"Evidence assessment:\n{evidence_assessment}\n\n"
                "Produce the final structured RCA."
            )
        ),
    ]

    rca = llm.invoke(prompt)

    rca_dict = rca.model_dump()

    summary = (
    f"Root cause: {rca.root_cause}\n\n"
    f"Confidence: {rca.confidence}\n\n"
    f"Affected devices: {', '.join(rca.affected_devices)}\n\n"
    f"Timeframe: {rca.timeframe}"
)

    return {
    "rca": rca_dict,
    "messages": [
        AIMessage(content=summary)
    ],
}



def answer_follow_up(state: AgentState) -> dict:
    """
    Answer a follow-up question using the investigation context already
    retained in LangGraph state.

    This node does not restart the investigation or query the database
    unless we explicitly add that behavior later.
    """

    messages = state.get("messages", [])

    if not messages:
        raise ValueError("answer_follow_up requires conversation messages.")

    latest_question = messages[-1].content.strip()

    anomaly = state.get("anomaly")
    device_context = state.get("device_context", [])
    syslogs = state.get("syslogs", [])
    telemetry = state.get("telemetry", [])
    evidence_assessment = state.get("evidence_assessment")
    rca = state.get("rca")

    if not anomaly and not rca:
        raise ValueError(
            "Follow-up requested but no prior investigation context is available."
        )

    llm = get_llm()

    prompt = [
        SystemMessage(
            content=(
                "You are answering a follow-up question about an existing "
                "network root-cause investigation.\n\n"
                "Rules:\n"
                "1. Use the retained investigation context supplied below.\n"
                "2. Do not invent evidence, measurements, events, or topology.\n"
                "3. Distinguish root cause from downstream symptoms.\n"
                "4. Preserve uncertainty and known evidence gaps.\n"
                "5. Do not claim a more specific physical failure than the "
                "evidence supports.\n"
                "6. Answer the user's specific question directly.\n"
                "7. Do not require the user to repeat the anomaly ID.\n"
                "8. If the retained evidence cannot answer the question, say "
                "what is missing rather than guessing.\n"
            )
        ),
        HumanMessage(
            content=(
                f"Prior anomaly:\n{anomaly}\n\n"
                f"Device context:\n{device_context}\n\n"
                f"Syslogs:\n{syslogs}\n\n"
                f"Telemetry:\n{telemetry}\n\n"
                f"Evidence assessment:\n{evidence_assessment}\n\n"
                f"Final RCA:\n{rca}\n\n"
                f"Follow-up question:\n{latest_question}"
            )
        ),
    ]

    response = llm.invoke(prompt)

    return {
        "messages": [
            AIMessage(content=response.content)
        ]
    }


def answer_general_qa(state: AgentState) -> dict:
    """
    Answer a general networking question without invoking investigation
    database tools.
    """

    messages = state.get("messages", [])

    if not messages:
        raise ValueError("answer_general_qa requires conversation messages.")

    latest_question = messages[-1].content.strip()

    llm = get_llm()

    prompt = [
        SystemMessage(
            content=(
                "You are a network engineering assistant.\n\n"
                "Answer general networking questions clearly and accurately.\n"
                "This is not an active anomaly investigation, so do not claim "
                "to have inspected device logs, telemetry, topology, or database "
                "records.\n"
                "Use concise operational language and explain terminology when useful."
            )
        ),
        HumanMessage(content=latest_question),
    ]

    response = llm.invoke(prompt)

    return {
        "messages": [
            AIMessage(content=response.content)
        ]
    }



def load_anomaly(state: AgentState) -> dict:
    """
    Load the anomaly identified by anomaly_id into graph state.

    This initializes a fresh investigation and clears evidence from any
    previous investigation.
    """

    anomaly_id = state.get("anomaly_id")

    if not anomaly_id:
        raise ValueError("load_anomaly requires anomaly_id.")

    result = get_anomaly.invoke({
        "anomaly_id": anomaly_id
    })

    anomaly = result.get("anomaly")

    if not anomaly:
        raise ValueError(
            f"Anomaly not found: {anomaly_id}"
        )

    return {
        "anomaly": anomaly,
        "device_context": [],
        "syslogs": [],
        "telemetry": [],
        "planned_actions": [],
        "evidence_assessment": None,
        "investigation_summary": None,
        "needs_more_evidence": True,
        "investigation_round": 0,
        "rca": None,
    }