"""
LangGraph orchestration for the Network Investigation Agent.

The graph supports:
1. New anomaly investigations
2. Conversational follow-up on an existing investigation
3. General networking Q&A
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    analyze_evidence,
    answer_follow_up,
    answer_general_qa,
    execute_planned_actions,
    load_anomaly,
    plan_investigation,
    route_request,
    synthesize_rca,
)
from agent.state import AgentState


MAX_INVESTIGATION_ROUNDS = 3


def route_after_request(state: AgentState) -> str:
    """
    Route the user's latest request into one of the three supported flows.
    """

    intent = state.get("intent")

    if intent == "investigation":
        return "investigation"

    if intent == "follow_up":
        return "follow_up"

    if intent == "general_qa":
        return "general_qa"

    raise ValueError(f"Unsupported request intent: {intent}")


def route_after_analysis(state: AgentState) -> str:
    """
    Decide whether to gather more evidence or synthesize the RCA.

    Semantic sufficiency comes from the evidence-analysis node.
    The deterministic round limit prevents unbounded agent loops.
    """

    needs_more_evidence = state.get(
        "needs_more_evidence",
        True,
    )

    investigation_round = state.get(
        "investigation_round",
        0,
    )

    if (
        needs_more_evidence
        and investigation_round < MAX_INVESTIGATION_ROUNDS
    ):
        return "plan_more"

    return "synthesize"


def build_graph():
    """
    Build and compile the complete conversational RCA agent.
    """

    builder = StateGraph(AgentState)

    # ---------------------------------------------------------------
    # Request-routing layer
    # ---------------------------------------------------------------

    builder.add_node(
        "route_request",
        route_request,
    )

    # ---------------------------------------------------------------
    # Investigation nodes
    # ---------------------------------------------------------------

    builder.add_node(
        "load_anomaly",
        load_anomaly,
    )

    builder.add_node(
        "plan_investigation",
        plan_investigation,
    )

    builder.add_node(
        "execute_planned_actions",
        execute_planned_actions,
    )

    builder.add_node(
        "analyze_evidence",
        analyze_evidence,
    )

    builder.add_node(
        "synthesize_rca",
        synthesize_rca,
    )

    # ---------------------------------------------------------------
    # Conversational nodes
    # ---------------------------------------------------------------

    builder.add_node(
        "answer_follow_up",
        answer_follow_up,
    )

    builder.add_node(
        "answer_general_qa",
        answer_general_qa,
    )

    # ---------------------------------------------------------------
    # Entry routing
    # ---------------------------------------------------------------

    builder.add_edge(
        START,
        "route_request",
    )

    builder.add_conditional_edges(
        "route_request",
        route_after_request,
        {
            "investigation": "load_anomaly",
            "follow_up": "answer_follow_up",
            "general_qa": "answer_general_qa",
        },
    )

    # ---------------------------------------------------------------
    # Investigation path
    # ---------------------------------------------------------------

    builder.add_edge(
        "load_anomaly",
        "plan_investigation",
    )

    builder.add_edge(
        "plan_investigation",
        "execute_planned_actions",
    )

    builder.add_edge(
        "execute_planned_actions",
        "analyze_evidence",
    )

    builder.add_conditional_edges(
        "analyze_evidence",
        route_after_analysis,
        {
            "plan_more": "plan_investigation",
            "synthesize": "synthesize_rca",
        },
    )

    builder.add_edge(
        "synthesize_rca",
        END,
    )

    # ---------------------------------------------------------------
    # Conversational terminal paths
    # ---------------------------------------------------------------

    builder.add_edge(
        "answer_follow_up",
        END,
    )

    builder.add_edge(
        "answer_general_qa",
        END,
    )

    # ---------------------------------------------------------------
    # Conversation memory
    # ---------------------------------------------------------------

    memory = MemorySaver()

    return builder.compile(
        checkpointer=memory
    )