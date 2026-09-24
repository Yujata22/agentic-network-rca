# Take-Home Challenge: Network Investigation Agent for Root Cause Analysis
### Track: Agentic AI (Data Scientist — IIA, Agent Developer & Evaluator)

---

## 1. Executive Summary

The vision behind this work is a semi-autonomous Agentic AI system that can investigate network anomalies and perform Root Cause Analysis (RCA) with explainable reasoning — moving Spectrum's network operations from manual troubleshooting toward an AI-driven system that can autonomously investigate anomalies and reduce mean time to resolution (MTTR) for network events.


## 2. Business Case

**Problem:** Network operations teams face high alert volumes, many of which require manual triage and root cause analysis. Investigations are time-consuming and depend on subject-matter-expert knowledge that doesn't scale with alert volume.

**This exercise** is about building a small-scale version of the agent this role owns in production: given a network anomaly, investigate it, determine the most likely root cause with supporting evidence, and make that investigation available conversationally — so an engineer can ask follow-up questions rather than reading a static report.

## 3. Objective

Build a **Network Investigation Agent**, using LangGraph, that can:

1. **Perform structured root cause analysis** on a network anomaly by retrieving and correlating evidence from the provided PostgreSQL database and producing a conclusion with clear reasoning.
2. **Support conversational interaction** — follow-up questions about an investigation, and general networking questions — grounded in the same data.

This challenge is about **agent development, not infrastructure or data engineering**. The environment and database are fully provided and pre-seeded; you are advised to spend essentially all of your time on the agent itself.

## 4. Provided Resources

- **A fully preconfigured environment** (`podman-compose.yml` + `Dockerfile`): a Postgres 16 database, a JupyterLab container with LangGraph, LangChain, and provider SDKs already installed, and Adminer (a web DB browser at `localhost:8081`) for inspecting the schema. You do not need to install or configure anything beyond Docker / Podman itself and an LLM API key.
- **A seeded PostgreSQL database** (`network_rca`) with 4 tables: `detected_anomalies`, `network_devices`, `device_telemetry`, and `device_syslogs`. Full column-level documentation is in `docs/schema_reference.md`.
- **Starter code** (`starter_code/`): a `db.py` connection/query helper, an empty `agent/graph.py` for your implementation, a minimal `main.py` CLI entry point, and a Jupyter notebook to verify your environment and iterate in.

## 5. Functional Requirements

Your agent must:

1. **Accept an anomaly as investigation input** (an `anomaly_id` from `detected_anomalies`), retrieve and correlate evidence from the provided tables, and produce a root cause conclusion: what most likely happened, what evidence supports it, which device(s)/timeframe are implicated, and how confident the agent is. If the evidence is genuinely insufficient, the agent should say so rather than fabricate a confident answer.
2. **Support conversational follow-up** — after an investigation, answer follow-up questions grounded in that investigation's context, without requiring the anomaly_id or prior context to be repeated.
3. **Support general networking questions** within the scope of the provided data, independent of any specific investigation.

Your agent should decide what evidence is relevant for a given anomaly — not follow a hardcoded lookup path written per anomaly.

## 6. Technical Requirements

- **You must build the agent using [LangGraph](https://langchain-ai.github.io/langgraph/).** This is a hard requirement — no-code/low-code agent builders or an unstructured "call the LLM in a loop" script do not satisfy it. We would like to see explicit control over agent state, control flow, and tool integration.
- Tools should query the provided PostgreSQL database (via the provided `db.py` helper or your own data access code — your choice).
- LLM API key — any provider is fine (OpenAI, Anthropic, and Google Gemini all work with the pre-installed packages; see `INSTRUCTIONS.md` for how to get a free Gemini key). Open-source/self-hosted models are also acceptable.
- Use whatever LangGraph memory/state mechanism you think is appropriate for the conversational requirement.
- Keep your code reasonably clean and organized — version-controlled, testable, reviewable agent code is part of the job this challenge maps to.

## 7. Expected Agent Behaviour

Illustrative (not exhaustive) examples of interactions your agent should handle reasonably:

- Investigate an anomaly by its `anomaly_id` → agent returns a structured RCA: likely root cause, supporting evidence, affected device(s)/timeframe, and confidence.
- A follow-up question about the investigation just performed → agent answers using that context, without the anomaly_id being repeated.
- A general networking question (e.g. "what's a BGP flap, in plain terms?") → agent answers as domain knowledge without an unnecessary database query.
- An anomaly where the evidence is thin → agent reports lower confidence rather than inventing a tidy story.

## 8. Deliverables

Submit:

1. **Your code**: the completed `agent/` implementation (and any supporting modules/tools you added), in a state that runs against the provided environment.
2. **A brief write-up** (README section, markdown file, or notes in your notebook) covering: your architecture and why you chose it, what tools you built, how you handled conversational memory, and known limitations.
3. **At least one worked example** showing an end-to-end investigation of an interface/link-flap anomaly (detector `interface_flap` — e.g. anomaly `a1f0c8e2-1b44-4d90-9c31-000000000001`), plus at least one follow-up conversational turn.
4. *(Optional)* Any evaluation you ran on your own agent's output.


We are explicitly **not** scoring you on infrastructure/DevOps work, dataset design, prompt polish for its own sake, or UI/front-end.

## 9. Constraints and Assumptions

- LangGraph is mandatory, as stated in Technical Requirements.
- The provided database schema and seed data are fixed — please don't modify `db/init/` or the seed CSVs.
- Autonomous *remediation* (changing device configuration) is out of scope — investigate and recommend, don't act.
- Deployment, CI/CD, and LangSmith Deployments are out of scope — running locally via the provided Docker environment is sufficient.
- If you get stuck on environment/setup issues (as opposed to the agent-building work itself), flag it to your contact rather than spending your time budget on it.
