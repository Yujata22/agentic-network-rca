# Network Investigation Agent for Root Cause Analysis

A stateful, tool-using **LangGraph Network Investigation Agent** for investigating detected network anomalies and producing structured, evidence-grounded root cause analyses from PostgreSQL network data.

The system begins **after anomaly detection**.

Given an `anomaly_id`, the agent:

1. retrieves the anomaly,
2. determines what additional evidence is relevant,
3. queries controlled network evidence sources,
4. correlates observations across devices and time,
5. evaluates whether the available evidence is sufficient,
6. gathers more evidence when necessary,
7. produces a structured RCA with explicit confidence and uncertainty,
8. retains the investigation so follow-up questions can be answered without repeating the anomaly ID.

It also supports general networking questions without unnecessarily querying the database.

---

# 1. Challenge Boundary: What Was Provided vs. What I Built

A useful distinction in this project is between the **provided infrastructure/data layer** and the **investigation agent implemented for the challenge**.

## Provided by the Challenge

The challenge supplied the underlying development environment and network dataset:

| Component | Provided |
|---|---|
| PostgreSQL 16 | Yes |
| Seeded network dataset | Yes |
| `detected_anomalies` | Yes |
| `network_devices` | Yes |
| `device_syslogs` | Yes |
| `device_telemetry` | Yes |
| Docker / Compose environment | Yes |
| JupyterLab | Yes |
| Adminer | Yes |
| Database helper (`db.py`) | Yes |
| Starter `graph.py` | Yes |
| Starter `main.py` | Yes |
| Schema documentation | Yes |
| Seed data | Yes |

The PostgreSQL database, anomaly detection results, Docker infrastructure, Jupyter environment, and dataset were **not built as part of this submission**.

## What I Implemented

I built the investigation layer on top of the supplied environment:

- LangGraph orchestration workflow
- explicit `AgentState`
- intent classification and routing
- generic read-only PostgreSQL evidence tools
- LLM-driven investigation planning
- deterministic tool validation and execution
- evidence sufficiency assessment
- bounded iterative investigation
- structured RCA generation
- explicit uncertainty representation
- conversational memory
- follow-up question handling
- general networking Q&A
- structured Pydantic contracts
- provider-isolated LLM configuration
- evaluation across all seeded anomalies
- thin-evidence behavior evaluation
- completed CLI
- optional Streamlit demonstration UI

The resulting architecture intentionally separates:

**reasoning → orchestration → data access → state → output validation**

rather than allowing an LLM to freely execute actions.

---

# 2. System Architecture

The system follows a controlled:

**Reason → Act → Observe → Assess → Conclude**

architecture.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER / CLI                                      │
│                                                                             │
│  anomaly_id          follow-up question          networking question        │
└───────────────┬────────────────────┬──────────────────────────┬──────────────┘
                │                    │                          │
                └────────────────────┴────────────┬─────────────┘
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH INVESTIGATION AGENT                             │
│                    agent/graph.py + agent/nodes.py                           │
│                                                                             │
│                         ┌──────────────────┐                                  │
│                         │  ROUTE REQUEST   │                                  │
│                         │     [NODE]       │                                  │
│                         └────────┬─────────┘                                  │
│                                  │                                            │
│               ┌──────────────────┼──────────────────┐                         │
│               │                  │                  │                         │
│               ▼                  ▼                  ▼                         │
│        investigation         follow_up          general_qa                    │
│               │                  │                  │                         │
│               ▼                  ▼                  ▼                         │
│      ┌────────────────┐  ┌────────────────┐  ┌────────────────┐             │
│      │ LOAD ANOMALY   │  │ ANSWER FOLLOW- │  │ GENERAL Q&A    │             │
│      │    [NODE]      │  │ UP [NODE]      │  │    [NODE]      │             │
│      └───────┬────────┘  └────────┬───────┘  └────────┬───────┘             │
│              │                    │                   │                      │
│              ▼                    │                   │                      │
│      ┌────────────────┐           │                   │                      │
│      │ PLAN           │           │                   │                      │
│      │ INVESTIGATION  │           │                   │                      │
│      │    [NODE]      │           │                   │                      │
│      └───────┬────────┘           │                   │                      │
│              │                    │                   │                      │
│              ▼                    │                   │                      │
│      ┌────────────────┐           │                   │                      │
│      │ EXECUTE        │───────────────┐               │                      │
│      │ EVIDENCE TOOLS │               │               │                      │
│      │    [NODE]      │               │               │                      │
│      └───────┬────────┘               │               │                      │
│              │                        │               │                      │
│              ▼                        │               │                      │
│      ┌────────────────┐               │               │                      │
│      │ ANALYZE        │               │               │                      │
│      │ EVIDENCE       │               │               │                      │
│      │    [NODE]      │               │               │                      │
│      └───────┬────────┘               │               │                      │
│              │                        │               │                      │
│       conditional edge                │               │                      │
│              │                        │               │                      │
│       ┌──────┴────────────┐           │               │                      │
│       │                   │           │               │                      │
│ needs more           sufficient       │               │                      │
│ evidence             evidence         │               │                      │
│       │                   │           │               │                      │
│       │                   ▼           │               │                      │
│       │           ┌────────────────┐  │               │                      │
│       └──────────►│ SYNTHESIZE RCA │  │               │                      │
│   loop to PLAN    │     [NODE]     │  │               │                      │
│                   └───────┬────────┘  │               │                      │
│                           │           │               │                      │
└───────────────────────────┼───────────┼───────────────┼──────────────────────┘
                            │           │               │
                            └───────────┴───────────────┘
                                        │
                                        ▼
                              STRUCTURED RESPONSE
```

The investigation loop is bounded to a maximum of **three investigation rounds**, preventing an uncontrolled LLM/tool loop.

---

# 3. LangGraph Concepts Used

The implementation deliberately uses the main LangGraph primitives explicitly.

## Node

A **node** performs one unit of work.

Implemented primarily in:

```text
agent/nodes.py
```

Examples:

```text
route_request
load_anomaly
plan_investigation
execute_planned_actions
analyze_evidence
synthesize_rca
answer_follow_up
answer_general_qa
```

A node answers:

> "What work happens at this stage?"

---

## Edge

An **edge** determines which node executes next.

Defined in:

```text
agent/graph.py
```

For example:

```text
load_anomaly
      │
      ▼
plan_investigation
      │
      ▼
execute_planned_actions
      │
      ▼
analyze_evidence
```

Conditional edges allow the graph to make controlled decisions.

For example:

```text
                    analyze_evidence
                           │
                    ┌──────┴──────┐
                    │             │
             more evidence     sufficient
                    │             │
                    ▼             ▼
            plan_investigation   synthesize_rca
```

The LLM can therefore influence the investigation without controlling arbitrary program execution.

---

## Intent

`intent` represents what kind of request the current user input is.

Stored in:

```text
agent/state.py
```

Supported values are:

```text
investigation
follow_up
general_qa
```

The routing node classifies the request and LangGraph follows the corresponding edge.

```text
                       USER INPUT
                           │
                           ▼
                    route_request
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   investigation       follow_up        general_qa
```

---

## State

State is the agent's structured working memory.

Defined in:

```text
agent/state.py
```

Conceptually:

```text
AgentState
│
├── Conversation
│   └── messages
│
├── Routing
│   └── intent
│
├── Investigation
│   ├── anomaly_id
│   └── anomaly
│
├── Retrieved Evidence
│   ├── device_context
│   ├── syslogs
│   └── telemetry
│
├── Planning / Control
│   ├── planned_actions
│   ├── investigation_summary
│   ├── evidence_assessment
│   ├── needs_more_evidence
│   └── investigation_round
│
└── Result
    └── rca
```

This distinction is important:

> **Chat history is not the same thing as investigation state.**

Conversation messages retain dialogue.

Structured state retains the actual investigation context.

---

# 4. End-to-End Investigation Workflow

For a new anomaly:

```text
User
 │
 │ anomaly_id
 ▼
route_request
 │
 │ intent = investigation
 ▼
load_anomaly
 │
 │ get anomaly metadata
 ▼
plan_investigation
 │
 │ LLM asks:
 │ "What evidence would help test the current hypothesis?"
 ▼
execute_planned_actions
 │
 ├── get_device_context
 ├── get_syslogs
 └── get_telemetry
 │
 ▼
PostgreSQL
 │
 │ evidence returned
 ▼
AgentState
 │
 ▼
analyze_evidence
 │
 │ "Is the evidence sufficient?"
 │
 ├──────────── NO ──────────────┐
 │                              │
 │                              ▼
 │                     plan_investigation
 │                              │
 │                       another evidence
 │                           round
 │
 └──────────── YES
                │
                ▼
        synthesize_rca
                │
                ▼
         Structured RCA
```

This is **not**:

```python
if detector == "interface_flap":
    query_syslogs()
    query_telemetry()
```

The planner receives the current anomaly and already-collected evidence and decides what evidence is useful next.

That allows the same workflow to operate across different detector types.

---

# 5. Why LangGraph?

A plain Python loop could repeatedly call an LLM, but that would make control flow, memory, termination, and tool boundaries much less explicit.

LangGraph provides:

- explicit state
- named nodes
- deterministic edges
- conditional routing
- bounded loops
- checkpointing
- conversational continuity
- inspectable control flow
- separation between reasoning and execution

The architecture follows:

```text
LLM
 │
 │ semantic reasoning
 ▼
LangGraph
 │
 │ controls allowed transitions
 ▼
Application Code
 │
 │ validates tool + parameters
 ▼
PostgreSQL Tools
```

A concise description is:

> The LLM decides what evidence it wants and interprets that evidence. LangGraph controls when those decisions occur and what paths are allowed. Python validates and executes the approved tools.

---

# 6. Single-Agent Design

This implementation is intentionally a **single stateful Network Investigation Agent**.

It is not presented as a multi-agent system.

The planner, evidence analyzer, RCA synthesizer, follow-up handler, and Q&A handler are specialized **nodes within one LangGraph agent**, sharing the same `AgentState`.

```text
              Network Investigation Agent
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
    Planning         Evidence          Conversation
      Node            Analysis             Nodes
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                    shared state
```

For this problem, the investigation stages are tightly coupled around one incident context. Introducing independent autonomous agents would add coordination and state-synchronization complexity without a clear benefit.

---

# 7. Evidence Tools

Implemented in:

```text
agent/tools.py
```

The tools are organized around **evidence sources**, not anomaly types.

| Tool | PostgreSQL Source | Purpose |
|---|---|---|
| `get_anomaly` | `detected_anomalies` | Retrieve anomaly metadata and detector output |
| `get_device_context` | `network_devices` | Resolve devices and obtain inventory/topology context |
| `get_syslogs` | `device_syslogs` | Retrieve time-bounded system/network events |
| `get_telemetry` | `device_telemetry` | Retrieve time-series network/device metrics |

I deliberately did not implement:

```text
investigate_interface_flap()
investigate_bgp()
investigate_policy_deny()
```

because those would encode anomaly-specific investigation paths.

Instead:

```text
Anomaly
   │
   ▼
Planner
   │
   │ chooses evidence source
   ▼
Validated Tool Call
   │
   ▼
PostgreSQL
```

The LLM also does **not** generate and execute arbitrary SQL.

Only known, read-only application tools can execute.

---

# 8. LLM Integration

LLM configuration is isolated in:

```text
agent/llm.py
```

The current runtime uses:

```text
ChatOpenAI
gpt-4.1-mini
temperature = 0
```

The investigation architecture itself is provider-independent because nodes obtain the model through the isolated LLM configuration module.

During development, the workflow was initially exercised using Gemini. The provider could subsequently be changed without modifying:

- LangGraph topology
- state representation
- PostgreSQL tools
- investigation logic
- memory mechanism
- evaluation structure

This separation keeps model configuration outside the business logic.

---

# 9. Structured Contracts

Implemented in:

```text
agent/schemas.py
```

Pydantic schemas constrain important model outputs.

Key structures include:

```text
IntentDecision
InvestigationAction
InvestigationPlan
EvidenceAssessment
EvidenceItem
RCAResult
```

For example, `RCAResult` explicitly separates:

```text
root_cause
confidence
affected_devices
timeframe
supporting_evidence
contradictory_or_missing_evidence
downstream_impacts
recommended_next_checks
```

This is preferable to asking the model to return an unrestricted paragraph because important RCA components can be inspected and evaluated independently.

Provider-output normalization is also applied at the schema boundary where appropriate so semantically valid outputs with minor structural variation can still be validated safely.

---

# 10. Conversational Memory

Conversational continuity uses three pieces.

```text
             AgentState
                 │
        WHAT is remembered
                 │
                 ▼
             MemorySaver
                 │
        HOW state is checkpointed
                 │
                 ▼
              thread_id
                 │
        WHICH conversation owns it
```

## 1. AgentState

Stores:

- messages
- anomaly
- evidence
- evidence assessment
- investigation progress
- final RCA

## 2. MemorySaver

The graph is compiled with LangGraph's:

```text
MemorySaver
```

checkpointer.

## 3. thread_id

The CLI creates one thread ID before entering the conversation loop and reuses it for subsequent invocations.

Implemented through:

```text
main.py
agent/graph.py
agent/state.py
```

Therefore:

```text
> a1f0c8e2-1b44-4d90-9c31-000000000001

[RCA generated]

> Why do you believe this was a physical-layer problem?

[intent: follow_up]
```

does not require the anomaly ID again.

The previous investigation is recovered from the same LangGraph thread.

---

# 11. Grounding and Hallucination Controls

Grounding is enforced primarily through architecture and evidence flow.

## Controlled Evidence Sources

Investigation evidence comes from four supplied PostgreSQL sources:

```text
detected_anomalies
network_devices
device_syslogs
device_telemetry
```

The LLM cannot freely access arbitrary external evidence.

---

## Evidence Stored in State

Retrieved evidence is stored in structured `AgentState`.

Therefore subsequent reasoning operates over evidence that was actually retrieved during the investigation.

---

## Controlled Tool Execution

The LLM proposes evidence needs.

Application code validates:

- tool name
- device IDs / hostnames
- time ranges
- required parameters

before executing a tool.

The model cannot directly execute arbitrary SQL or database writes.

---

## Structured Supporting Evidence

The final RCA contains explicit `EvidenceItem` entries identifying the source and observation.

Example:

```text
[LOG-002117] device_syslogs:
High pre-FEC BER and degraded Rx optical power...
```

This makes the evidence chain auditable.

---

## Explicit Missing Evidence

The model is required to represent uncertainty.

For example:

```text
Likely domain:
physical / optical degradation

Known:
link flaps
optical degradation
OSPF disruption

Unknown:
fiber vs transceiver vs connector
```

The agent should therefore stop at the level of specificity supported by the evidence.

---

## Grounding Limitation

The current implementation does **not** calculate a formal numerical groundedness metric.

The architecture reduces hallucination risk, but a stronger production evaluation would perform claim-level verification against retrieved evidence and SME-reviewed incident resolutions.

---

# 12. Worked Example — Interface Flap

Required anomaly:

```text
a1f0c8e2-1b44-4d90-9c31-000000000001
```

Detector:

```text
interface_flap
```

Investigation window:

```text
2026-07-08T06:00:00Z
to
2026-07-08T07:47:00Z
```

Affected devices:

```text
FAIRVIEW-EDG01
stonebridge-edg01
```

Interfaces:

```text
FAIRVIEW-EDG01       xe-0/0/21
stonebridge-edg01    xe-0/0/0
```

## RCA

The agent concluded that the most likely cause was:

> **Physical-layer degradation on the backbone uplink causing intermittent link flaps.**

Confidence:

```text
high
```

## Evidence Chain

The agent correlated:

1. high pre-FEC BER,
2. Rx optical power around `-18.2 dBm`,
3. a logged threshold around `-15.0 dBm`,
4. physical link-down/up events,
5. matching events at both ends of the link,
6. subsequent OSPF neighbor loss,
7. subsequent BGP disruption,
8. device context showing the interfaces are opposite ends of the same backbone link.

The temporal ordering supports:

```text
Optical / physical degradation
             │
             ▼
       physical link flap
             │
             ▼
      OSPF adjacency loss
             │
             ▼
        BGP disruption
```

rather than treating OSPF or BGP as the initiating root cause.

## Uncertainty

The evidence does **not** establish whether the exact physical failure is:

- fiber
- transceiver
- connector
- patch cable

The final RCA therefore reports the broader supported failure domain and explicitly preserves this uncertainty.

---

# 13. Follow-Up Conversation Example

After the investigation:

```text
> Why do you believe this was a physical-layer problem?

[intent: follow_up]
```

The response uses the retained RCA and evidence rather than requiring another investigation.

A second example:

```text
> What uncertainty remains?

[intent: follow_up]
```

The agent identifies the missing opposite-side optical diagnostics and inability to distinguish the exact physical component.

Another tested follow-up:

```text
> what are different anomalies being reported?

[intent: follow_up]
```

The agent can reason over the retained investigation and distinguish:

- physical interface flaps,
- OSPF neighbor-down events,
- downstream BGP peer disruption.

This validates the conversational-memory requirement.

---

# 14. General Networking Q&A

General networking questions follow a separate graph path.

Example:

```text
> What is the difference between a physical interface flap
  and an OSPF adjacency failure?

[intent: general_qa]
```

The model explains that:

- an interface flap is primarily a Layer 1 / Layer 2 link-state event,
- an OSPF adjacency failure is a Layer 3 routing-protocol relationship failure,
- a physical flap can cause OSPF adjacency loss,
- but an OSPF failure does not necessarily imply physical link failure.

No investigation-specific PostgreSQL retrieval is required for this path.

This satisfies the requirement that domain questions can be answered without unnecessary database queries.

---

# 15. Thin-Evidence Behavior

A separate thin-evidence test was added to verify that the evidence-analysis component does not automatically produce high confidence when supporting context is intentionally removed.

The test supplies:

```text
anomaly metadata : YES
device context   : NO
syslogs          : NO
telemetry        : NO
```

Observed behavior:

```text
Confidence          : medium
Evidence sufficient : False
```

The assessment explicitly reports missing evidence such as:

- device/configuration context,
- syslogs,
- interface counters,
- error-rate/physical-layer telemetry,
- topology context.

The reasoning correctly states that the available anomaly metadata suggests link instability but is insufficient to confidently isolate the root-cause domain.

This is an important behavior:

> **Evidence scarcity is represented as uncertainty rather than being converted into a fabricated precise RCA.**

The test can be run with:

```bash
PYTHONPATH=/home/jovyan/work python eval/test_thin_evidence.py
```

---

# 16. Evaluation

Evaluation was performed at two levels.

## A. End-to-End Dataset Evaluation

The same investigation graph was run across all **10 supplied anomalies**.

The anomalies span six detector types:

```text
interface_flap
policy_deny
sdwan_path_quality
bgp_session
interface_availability
interface_error
```

Final execution results:

```text
Total anomalies:          10
Successful executions:    10
Failed executions:         0
Detector types covered:    6
Average investigation:    ~2 rounds
Average runtime:          ~11 seconds
```

The evaluation therefore tests:

- graph completion
- detector coverage
- structured RCA generation
- investigation depth
- latency
- robustness across anomaly types

### Important Interpretation

The `10/10` result is an **execution success rate**.

It is **not** a claim of 100% RCA semantic accuracy.

The supplied dataset does not contain SME-reviewed ground-truth root causes for every anomaly.

---

## B. Thin-Evidence Evaluation

A targeted test removes corroborating evidence before invoking the evidence-analysis stage.

Observed:

```text
confidence          = medium
evidence_sufficient = False
```

This specifically tests the requirement:

> An anomaly where evidence is thin should report lower confidence rather than inventing a tidy story.

---

# 17. Evaluation Scalability

The evaluation framework is detector-agnostic.

It does not require:

```text
evaluate_interface_flap()
evaluate_bgp()
evaluate_policy()
```

Instead, additional anomaly IDs can be passed through the same graph.

This makes the execution evaluation naturally extensible to larger anomaly datasets.

For larger-scale production evaluation I would add:

- controlled concurrency,
- provider-aware rate limiting,
- retry/backoff,
- resumable execution,
- persistent result storage,
- token/cost tracking,
- versioned prompts,
- model-version tracking,
- SME-labeled benchmark cases.

With labeled incident data, additional metrics could include:

| Evaluation Dimension | Example Metric |
|---|---|
| RCA correctness | SME agreement / classification accuracy |
| Evidence retrieval | Recall@K |
| Tool selection | tool-selection accuracy |
| Tool parameters | argument correctness |
| Grounding | supported-claim ratio |
| Efficiency | unnecessary tool-call rate |
| Confidence | calibration / reliability |
| Runtime | p50 / p95 latency |
| Cost | tokens / investigation |
| Reliability | provider failure rate |

---

# 18. Confidence Interpretation

Confidence is currently an LLM-assessed categorical field constrained to:

```text
high
medium
low
```

It reflects the model's assessment of the strength and consistency of the available evidence.

It is **not a statistically calibrated probability**.

This distinction became visible during testing.

For example, a planned-maintenance anomaly contained an explicit change reference in anomaly metadata. The model returned `high` confidence even though corroborating syslogs and telemetry were unavailable.

The metadata itself was highly diagnostic, so the model was confident in the explanation, but this demonstrates that the confidence value is a semantic LLM judgment rather than a calibrated probability.

A production implementation should improve this through:

- deterministic evidence-quality signals,
- SME-reviewed resolved incidents,
- confidence calibration,
- historical reliability analysis,
- separate confidence dimensions.

For example:

```text
Failure-domain confidence: HIGH
Exact-component confidence: LOW
```

may be more useful than a single confidence value.

The interface-flap example illustrates this distinction:

```text
HIGH confidence:
physical-layer degradation

LOWER confidence:
fiber vs SFP vs connector vs cable
```

---

# 19. Known Limitations

## 1. No Complete RCA Ground Truth

The supplied dataset does not contain SME-reviewed final incident resolutions for every anomaly.

Therefore semantic RCA accuracy cannot be measured reliably across the full dataset.

---

## 2. Confidence Is Not Calibrated

Confidence is currently an LLM-generated categorical assessment.

It should not be interpreted as a probability.

Production confidence should be calibrated against resolved incidents and potentially combined with deterministic evidence-quality criteria.

---

## 3. In-Memory Checkpointing

`MemorySaver` supports conversational continuity while the application is running.

State does not survive process/container restart.

A production system should use a persistent LangGraph checkpointer or external state store.

---

## 4. External LLM Dependency

The reasoning layer depends on an external LLM provider and is therefore exposed to:

- latency,
- quota limits,
- rate limits,
- transient provider errors,
- model behavior changes.

The provider configuration is isolated so the model backend can be changed without redesigning the graph.

---

## 5. Physical Diagnostics Are Limited

The supplied dataset can indicate a physical/optical problem but does not always contain enough diagnostics to distinguish:

```text
fiber
SFP/transceiver
connector
patch cable
```

---

## 6. Limited Explicit Topology Model

Some topology relationships are inferred from device metadata and notes.

A production network investigation system would ideally query an authoritative topology/CMDB source.

---

## 7. Grounding Is Not Formally Scored

The architecture strongly constrains evidence sources and preserves evidence references, but no quantitative claim-level groundedness metric is currently calculated.

---

## 8. No Autonomous Remediation

The agent investigates and recommends next checks.

It intentionally does **not**:

- modify network configuration,
- restart devices,
- shut interfaces,
- execute remediation.

This keeps the challenge focused on investigation rather than operational automation.

---

# 20. Development Environment Setup

The project uses the Docker/Compose environment supplied with the challenge.

## Initial Build / Setup

For a fresh environment:

```bash
docker compose -f podman-compose.yml up --build -d
```

The initial local build took approximately **~80 minutes** on the development machine.

This was environment setup time — **not agent investigation runtime**.

The long initial build was associated with constructing the supplied container environment and installing the relatively large Python / ML / LangChain / LangGraph dependency stack.

Contributing factors can include:

- downloading Python packages,
- dependency resolution,
- large package installation,
- Docker layer creation,
- local disk/network performance,
- cache misses.

Once the environment was built, normal startup does not require repeating the full build.

## Normal Startup

```bash
docker compose -f podman-compose.yml up -d
```

Check:

```bash
docker ps
```

Enter the application container:

```bash
docker exec -it rca-jupyter bash
```

Then:

```bash
cd /home/jovyan/work
python main.py
```

---

# 21. Improving Container Setup for Production

The initial setup time could be improved by:

- pinning dependency versions,
- maintaining a reproducible lock file,
- separating dependency layers from application-code layers,
- maximizing Docker layer caching,
- avoiding dependency-layer invalidation when only Python source changes,
- using a pre-built dependency base image,
- publishing the application image to a container registry.

For example, production distribution could become:

```text
Developer CI
     │
     ▼
Build + Test Image
     │
     ▼
Container Registry
     │
     ▼
Reviewer / Deployment
     │
     ▼
docker pull
```

rather than requiring every reviewer to rebuild the full dependency stack locally.

---

# 22. Running the CLI

Start the environment:

```bash
docker compose -f podman-compose.yml up -d
```

Enter the container:

```bash
docker exec -it rca-jupyter bash
cd /home/jovyan/work
```

Run:

```bash
python main.py
```

Example:

```text
Network Investigation Agent
============================

> a1f0c8e2-1b44-4d90-9c31-000000000001

[intent: investigation]

=== ROOT CAUSE ANALYSIS ===
...
```

Then continue in the same session:

```text
> Why do you believe this was a physical-layer problem?

[intent: follow_up]
...
```

---

# 23. Database Inspection

The supplied Adminer interface is available at:

```text
http://localhost:8081
```

Primary evidence tables:

| Table | Purpose |
|---|---|
| `detected_anomalies` | Detector/anomaly metadata |
| `network_devices` | Device inventory and topology context |
| `device_syslogs` | Timestamped device/network events |
| `device_telemetry` | Time-series network/device measurements |

The agent accesses these through controlled application tools rather than unrestricted model-generated SQL.

---

# 24. Repository Structure

```text
.
├── agent/
│   ├── graph.py
│   │   └── LangGraph topology, edges and checkpointing
│   │
│   ├── nodes.py
│   │   └── routing, planning, evidence analysis,
│   │       RCA synthesis and conversational nodes
│   │
│   ├── state.py
│   │   └── AgentState definition
│   │
│   ├── tools.py
│   │   └── controlled PostgreSQL evidence tools
│   │
│   ├── schemas.py
│   │   └── structured Pydantic contracts
│   │
│   └── llm.py
│       └── LLM provider/model configuration
│
├── eval/
│   ├── run_eval.py
│   │   └── end-to-end anomaly evaluation
│   │
│   ├── test_thin_evidence.py
│   │   └── evidence-scarcity behavior test
│   │
│   └── results/
│       └── evaluation outputs
│
├── main.py
│   └── stateful CLI / thread lifecycle
│
├── streamlit_app.py
│   └── optional demonstration UI
│
├── db.py
│   └── supplied database helper
│
└── requirements.txt
```

---

# 25. Requirement Coverage

| Requirement | Implementation |
|---|---|
| Accept `anomaly_id` | Yes |
| Retrieve PostgreSQL evidence | Yes |
| Correlate multiple evidence sources | Yes |
| Produce structured RCA | Yes |
| Root cause | Yes |
| Supporting evidence | Yes |
| Devices/timeframe | Yes |
| Confidence | Yes |
| Explicit missing evidence | Yes |
| Conversational follow-up | Yes |
| No repeated anomaly ID required | Yes |
| General networking Q&A | Yes |
| Avoid unnecessary DB query for general Q&A | Yes |
| Evidence selection not hardcoded per anomaly | Yes |
| LangGraph required | Yes |
| Explicit state | Yes |
| Explicit nodes/edges | Yes |
| Tool integration | Yes |
| Memory/checkpointing | Yes |
| Thin-evidence behavior | Tested |
| Evaluation | Yes |
| Required interface-flap example | Yes |
| Follow-up example | Yes |

---

# 26. Design Summary

The central design principle is **controlled agent autonomy**.

```text
                    LLM
                     │
          decides what evidence
           is useful + interprets
                     │
                     ▼
                 LangGraph
                     │
            controls workflow,
             state and loops
                     │
                     ▼
              Python Tool Layer
                     │
             validates actions
                     │
                     ▼
                 PostgreSQL
                     │
             grounded evidence
                     │
                     ▼
                 AgentState
                     │
                     ▼
              Structured RCA
```

The implementation deliberately avoids two extremes:

```text
Fully hardcoded workflow                    Unconstrained LLM agent
         │                                            │
         └──────────────────┐      ┌──────────────────┘
                            ▼      ▼
                       THIS DESIGN
                  Controlled Agent Autonomy
```

The LLM handles semantic reasoning.

LangGraph handles state and control flow.

Python handles deterministic validation and tool execution.

PostgreSQL provides the evidence.

Pydantic schemas constrain the reasoning outputs.

The final RCA explicitly distinguishes:

**what the evidence supports, what remains uncertain, and what should be checked next.**
