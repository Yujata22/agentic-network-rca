"""
Minimal CLI entry point. Optional -- use this, the notebook, or your own
script. See CHALLENGE.md for requirements.
"""
from agent.graph import build_graph


def main():
    app = build_graph()
    print("Network Investigation Agent - CLI")
    print("Type an anomaly_id from detected_anomalies, a question, or 'exit'.\n")

    while True:
        user_input = input("> ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue
        # TODO: invoke your graph with user_input and print the response


if __name__ == "__main__":
    main()
