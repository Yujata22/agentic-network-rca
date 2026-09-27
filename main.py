from __future__ import annotations

import uuid

from langchain_core.messages import HumanMessage

from agent.graph import build_graph


def print_rca(rca: dict) -> None:
    """Render a structured RCA result in a readable CLI format."""

    print("\n=== ROOT CAUSE ANALYSIS ===")
    print(f"Root cause : {rca.get('root_cause', 'N/A')}")
    print(f"Confidence : {rca.get('confidence', 'N/A')}")
    print(f"Timeframe  : {rca.get('timeframe', 'N/A')}")

    devices = rca.get("affected_devices", [])
    if devices:
        print("\nAffected devices:")
        for device in devices:
            print(f"  - {device}")

    evidence = rca.get("supporting_evidence", [])
    if evidence:
        print("\nSupporting evidence:")
        for item in evidence:
            evidence_id = item.get("evidence_id", "?")
            source = item.get("source", "unknown")
            description = item.get("description", "")
            print(f"  [{evidence_id}] {source}: {description}")

    missing = rca.get("contradictory_or_missing_evidence", [])
    if missing:
        print("\nUncertainty / missing evidence:")
        for item in missing:
            print(f"  - {item}")

    impacts = rca.get("downstream_impacts", [])
    if impacts:
        print("\nDownstream impacts:")
        for item in impacts:
            print(f"  - {item}")

    checks = rca.get("recommended_next_checks", [])
    if checks:
        print("\nRecommended next checks:")
        for item in checks:
            print(f"  - {item}")

    print()


def main() -> None:
    app = build_graph()

    # One thread per CLI session preserves conversational investigation state.
    thread_id = f"cli-{uuid.uuid4()}"

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    print("Network Investigation Agent")
    print("=" * 40)
    print("Enter an anomaly ID, ask a networking question,")
    print("or ask follow-up questions about the current investigation.")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        if not user_input:
            continue

        try:
            result = app.invoke(
                {
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=config,
            )

            intent = result.get("intent")

            if intent == "investigation" and result.get("rca"):
                print_rca(result["rca"])
            else:
                messages = result.get("messages", [])
                if messages:
                    print(f"\n{messages[-1].content}\n")
                else:
                    print("\nNo response generated.\n")

        except Exception as exc:
            print(f"\nError: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
