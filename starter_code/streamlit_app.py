from __future__ import annotations

import uuid

import streamlit as st
from langchain_core.messages import HumanMessage

from agent.graph import build_graph


# -------------------------------------------------------------------
# Page configuration
# -------------------------------------------------------------------

st.set_page_config(
    page_title="Network RCA Agent",
    page_icon="🛰️",
    layout="wide",
)


# -------------------------------------------------------------------
# Session initialization
# -------------------------------------------------------------------

if "app" not in st.session_state:
    st.session_state.app = build_graph()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4()}"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "latest_result" not in st.session_state:
    st.session_state.latest_result = None


def get_config() -> dict:
    return {
        "configurable": {
            "thread_id": st.session_state.thread_id,
        }
    }


def reset_session() -> None:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4()}"
    st.session_state.chat_history = []
    st.session_state.latest_result = None


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def render_rca(rca: dict) -> None:
    """Render structured RCA output."""

    confidence = rca.get("confidence", "unknown")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Confidence",
            str(confidence).upper(),
        )

    with col2:
        st.metric(
            "Affected devices",
            len(rca.get("affected_devices", [])),
        )

    with col3:
        st.metric(
            "Evidence items",
            len(rca.get("supporting_evidence", [])),
        )

    st.subheader("Root cause")
    st.write(
        rca.get(
            "root_cause",
            "No root cause generated.",
        )
    )

    timeframe = rca.get("timeframe")

    if timeframe:
        st.caption(f"Investigation timeframe: {timeframe}")

    affected_devices = rca.get("affected_devices", [])

    if affected_devices:
        st.subheader("Affected devices")

        for device in affected_devices:
            st.markdown(f"- `{device}`")

    evidence = rca.get("supporting_evidence", [])

    if evidence:
        st.subheader("Supporting evidence")

        for item in evidence:
            evidence_id = item.get("evidence_id", "?")
            source = item.get("source", "unknown")
            device = item.get("device", "unknown")
            timestamp = item.get("timestamp", "")
            description = item.get("description", "")

            with st.expander(
                f"{evidence_id} · {device} · {source}"
            ):
                if timestamp:
                    st.caption(timestamp)

                st.write(description)

    missing = rca.get(
        "contradictory_or_missing_evidence",
        [],
    )

    if missing:
        st.subheader("Uncertainty / missing evidence")

        for item in missing:
            st.markdown(f"- {item}")

    impacts = rca.get("downstream_impacts", [])

    if impacts:
        st.subheader("Downstream impacts")

        for item in impacts:
            st.markdown(f"- {item}")

    checks = rca.get(
        "recommended_next_checks",
        [],
    )

    if checks:
        st.subheader("Recommended next checks")

        for item in checks:
            st.markdown(f"- {item}")


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.title("Network RCA Agent")

    st.caption(
        "LangGraph-based network investigation assistant"
    )

    st.divider()

    st.markdown("**Capabilities**")

    st.markdown(
        """
        - Autonomous anomaly investigation
        - Dynamic evidence selection
        - Evidence-sufficiency loop
        - Structured RCA synthesis
        - Conversational follow-up
        - General networking Q&A
        """
    )

    st.divider()

    st.caption("Conversation thread")

    st.code(
        st.session_state.thread_id,
        language=None,
    )

    if st.button(
        "Start new investigation",
        use_container_width=True,
    ):
        reset_session()
        st.rerun()


# -------------------------------------------------------------------
# Main header
# -------------------------------------------------------------------

st.title("Network Investigation Agent")

st.caption(
    "Evidence-driven root-cause analysis across network telemetry, "
    "device context, and syslogs."
)

st.info(
    "Try an anomaly ID such as "
    "`a1f0c8e2-1b44-4d90-9c31-000000000001`, "
    "ask a follow-up question, or ask a general networking question."
)


# -------------------------------------------------------------------
# Existing conversation
# -------------------------------------------------------------------

for message in st.session_state.chat_history:

    role = message["role"]

    with st.chat_message(role):
        st.markdown(message["content"])


# -------------------------------------------------------------------
# Chat input
# -------------------------------------------------------------------

user_input = st.chat_input(
    "Investigate an anomaly or ask a networking question..."
)

if user_input:

    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):

        with st.spinner("Investigating..."):

            try:
                result = st.session_state.app.invoke(
                    {
                        "messages": [
                            HumanMessage(
                                content=user_input
                            )
                        ]
                    },
                    config=get_config(),
                )

                st.session_state.latest_result = result

                intent = result.get(
                    "intent",
                    "unknown",
                )

                st.caption(
                    f"Intent: `{intent}`"
                )

                if (
                    intent == "investigation"
                    and result.get("rca")
                ):
                    rca = result["rca"]

                    root_cause = rca.get(
                        "root_cause",
                        "RCA completed.",
                    )

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": root_cause,
                        }
                    )

                    render_rca(rca)

                else:
                    messages = result.get(
                        "messages",
                        [],
                    )

                    if messages:
                        answer = messages[-1].content
                    else:
                        answer = (
                            "No response was generated."
                        )

                    st.markdown(answer)

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": answer,
                        }
                    )

            except Exception as exc:
                error_message = (
                    f"{type(exc).__name__}: {exc}"
                )

                st.error(error_message)

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": (
                            "The request failed: "
                            f"{error_message}"
                        ),
                    }
                )


# -------------------------------------------------------------------
# Optional investigation-state panel
# -------------------------------------------------------------------

result = st.session_state.latest_result

if result:

    st.divider()

    with st.expander(
        "Investigation state / debugging details"
    ):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Rounds",
                result.get(
                    "investigation_round",
                    0,
                ),
            )

        with col2:
            st.metric(
                "Device context",
                len(
                    result.get(
                        "device_context",
                        [],
                    )
                ),
            )

        with col3:
            st.metric(
                "Syslogs",
                len(
                    result.get(
                        "syslogs",
                        [],
                    )
                ),
            )

        with col4:
            st.metric(
                "Telemetry",
                len(
                    result.get(
                        "telemetry",
                        [],
                    )
                ),
            )

        st.markdown("**Evidence sufficiency**")

        st.write(
            not result.get(
                "needs_more_evidence",
                False,
            )
        )

        investigation_summary = result.get(
            "investigation_summary"
        )

        if investigation_summary:
            st.markdown(
                "**Investigation summary**"
            )
            st.write(
                investigation_summary
            )

        planned_actions = result.get(
            "planned_actions"
        )

        if planned_actions:
            st.markdown(
                "**Last planned tool actions**"
            )

            st.json(
                planned_actions
            )
