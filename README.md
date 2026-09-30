# Network Investigation Agent for Root Cause Analysis

A stateful, tool-using **LangGraph Network Investigation Agent** that investigates detected network anomalies and produces structured root cause analyses (RCAs) using evidence stored in PostgreSQL.

The system starts **after anomaly detection**.

Given an `anomaly_id`, the agent can:

1. retrieve the detected anomaly,
2. decide what additional evidence is useful,
3. query controlled network evidence sources,
4. correlate events across devices and time,
5. assess whether the evidence is sufficient,
6. gather more evidence when needed,
7. produce a structured RCA with confidence and uncertainty,
8. retain the investigation so the user can ask follow-up questions without repeating the anomaly ID.

The same application can also answer general networking questions without unnecessarily querying the investigation database.

---

# 1. Challenge Boundary: What Was Provided vs. What I Built

A key distinction in this project is between the infrastructure/data supplied with the challenge and the investigation agent I built on top of it.

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

The PostgreSQL database, seeded anomalies, Docker environment, Jupyter environment, and source dataset were therefore **not built as part of this submission**.

## What I Implemented

I built the investigation layer on top of the supplied environment:

- LangGraph investigation workflow
- explicit investigation state
- intent classification and routing
- generic read-only PostgreSQL evidence tools
- LLM-based investigation planning
- deterministic tool validation and execution
- evidence sufficiency assessment
- bounded iterative investigation
- structured RCA generation
- explicit uncertainty handling
- conversational memory
- follow-up question handling
- general networking Q&A
- Pydantic output contracts
- isolated LLM configuration
- end-to-end evaluation across all seeded anomalies
- retrieval-quality evaluation
- claim-level groundedness evaluation
- thin-evidence behavior testing
- completed CLI
- optional Streamlit demonstration UI

The main design idea is to separate:

**LLM reasoning → LangGraph orchestration → controlled data access → structured state → validated output**

The LLM can reason about what to investigate, but it does not have unrestricted control over the application or database.

---

# 2. System Architecture

The investigation follows a controlled loop:

**Reason → Act → Observe → Assess → Conclude**

```text
┌─────────────────────────────────────────────────────────────────────┐
│                            USER / CLI                               │
│                                                                     │
│    anomaly_id          follow-up question       networking question │
└──────────┬──────────────────────┬───────────────────────┬───────────┘
           │                      │                       │
           └──────────────────────┴──────────┬────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LANGGRAPH INVESTIGATION AGENT                      │
│                  agent/graph.py + agent/nodes.py                    │
│                                                                     │
│                         ┌───────────────┐                            │
│                         │ ROUTE REQUEST │                            │
│                         └───────┬───────┘                            │
│                                 │                                   │
│              ┌──────────────────┼──────────────────┐                │
│              ▼                  ▼                  ▼                │
│        investigation        follow_up          general_qa           │
│              │                  │                  │                │
│              ▼                  ▼                  ▼                │
│       ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│       │ LOAD ANOMALY│    │   ANSWER    │    │ GENERAL Q&A │        │
│       └──────┬──────┘    │  FOLLOW-UP  │    └─────────────┘        │
│              │           └─────────────┘                           │
│              ▼                                                      │
│       ┌─────────────┐                                               │
│       │    PLAN     │                                               │
│       │INVESTIGATION│                                               │
│       └──────┬──────┘                                               │
│              ▼                                                      │
│       ┌─────────────┐         ┌──────────────────────────┐          │
│       │   EXECUTE   │────────►│ Controlled Evidence Tools│          │
│       │    TOOLS    │         │ PostgreSQL (read-only)   │          │
│       └──────┬──────┘         └──────────────────────────┘          │
│              ▼                                                      │
│       ┌─────────────┐                                               │
│       │   ANALYZE   │                                               │
│       │   EVIDENCE  │                                               │
│       └──────┬──────┘                                               │
│              │                                                      │
│       ┌──────┴───────────────┐                                     │
│       │                      │                                     │
│  more evidence         evidence sufficient                         │
│       │                      │                                     │
│       ▼                      ▼                                     │
│      PLAN              ┌──────────────┐                            │
│       ▲                │SYNTHESIZE RCA│                            │
│       └────────────────┤              │                            │
│                        └──────┬───────┘                            │
└───────────────────────────────┼─────────────────────────────────────┘
                                ▼
                         STRUCTURED RESPONSE
```

The investigation loop is limited to a maximum of **three investigation rounds**.

This prevents an uncontrolled LLM/tool loop while still allowing the agent to gather more evidence when its first investigation round is not enough.

---

# 3. LangGraph Concepts Used

The implementation uses LangGraph's main concepts directly: **nodes, edges, state, routing, and checkpointing**.

## Node

A **node** performs one step of the workflow.

Most nodes are implemented in:

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

In simple terms:

> A node answers: **"What work happens at this stage?"**

---

## Edge

An **edge** decides which node runs next.

Edges are defined in:

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

Conditional edges handle decisions such as:

```text
                    analyze_evidence
                           │
                    ┌──────┴──────┐
                    │             │
             need more        sufficient
              evidence          evidence
                    │             │
                    ▼             ▼
            plan again      synthesize_rca
```

This gives the LLM room to reason while keeping the overall execution path controlled by the application.

---

## Intent

`intent` represents the type of request the user is making.

It is stored in:

```text
agent/state.py
```

Supported intents are:

```text
investigation
follow_up
general_qa
```

The routing flow is:

```text
                       USER INPUT
                           │
                           ▼
                     route_request
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
      investigation    follow_up     general_qa
```

---

## State

State is the agent's structured working memory.

It is defined in:

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

An important design choice is that:

> **Chat history and investigation state are not the same thing.**

Messages preserve the conversation.

Structured state preserves the actual investigation: anomaly information, evidence, investigation progress, evidence assessment, and final RCA.

---

# 4. End-to-End Investigation Workflow

For a new anomaly:

```text
User provides anomaly_id
          │
          ▼
     route_request
          │
          │ intent = investigation
          ▼
      load_anomaly
          │
          │ retrieve anomaly metadata
          ▼
   plan_investigation
          │
          │ What evidence would help?
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
          │ Is the evidence sufficient?
          │
      ┌───┴───────────────┐
      │                   │
      NO                  YES
      │                   │
      ▼                   ▼
plan_investigation   synthesize_rca
      │                   │
      └── next round      ▼
                    Structured RCA
```

The workflow is deliberately **not** hardcoded like this:

```python
if detector == "interface_flap":
    query_syslogs()
    query_telemetry()
```

Instead, the planner receives the current anomaly and evidence already collected and decides which evidence source would be useful next.

That allows the same investigation workflow to work across different anomaly types.

---

# 5. Why LangGraph?

A normal Python loop could repeatedly call an LLM and tools, but the workflow would be harder to control, inspect, and maintain.

LangGraph gives this project:

- explicit state,
- named workflow stages,
- controlled transitions,
- conditional routing,
- bounded investigation loops,
- checkpointing,
- conversational continuity,
- clearer debugging and testing.

The responsibilities are separated like this:

```text
LLM
 │
 │ decides what evidence is useful
 │ and interprets the evidence
 ▼
LangGraph
 │
 │ controls workflow and allowed transitions
 ▼
Application Code
 │
 │ validates tool calls and parameters
 ▼
PostgreSQL Evidence Tools
```

In one sentence:

> The LLM handles semantic reasoning, LangGraph controls the workflow, and Python validates and executes the allowed tools.

---

# 6. Why a Single Agent?

This implementation is intentionally a **single stateful Network Investigation Agent**, not a multi-agent system.

Planning, evidence analysis, RCA synthesis, follow-up handling, and general Q&A are specialized nodes inside the same LangGraph workflow.

They all share the same `AgentState`.

```text
             Network Investigation Agent
                        │
          ┌─────────────┼─────────────┐
          │             │             │
       Planning      Evidence     Conversation
         Node        Analysis        Nodes
          │             │             │
          └─────────────┼─────────────┘
                        │
                   Shared State
```

For this challenge, all investigation stages work on the same incident context.

Using multiple autonomous agents would introduce extra coordination and state synchronization without a clear benefit for this scope.

---

# 7. Evidence Tools

Evidence tools are implemented in:

```text
agent/tools.py
```

They are organized around **data sources**, not anomaly types.

| Tool | PostgreSQL Source | Purpose |
|---|---|---|
| `get_anomaly` | `detected_anomalies` | Retrieve anomaly metadata and detector output |
| `get_device_context` | `network_devices` | Retrieve device inventory and topology context |
| `get_syslogs` | `device_syslogs` | Retrieve time-bounded network/device events |
| `get_telemetry` | `device_telemetry` | Retrieve time-series device/network measurements |

I deliberately did not create functions such as:

```text
investigate_interface_flap()
investigate_bgp()
investigate_policy_deny()
```

because that would hardcode the investigation path by anomaly type.

Instead:

```text
Anomaly
   │
   ▼
Planner
   │
   │ decides what evidence is useful
   ▼
Validated Tool Call
   │
   ▼
PostgreSQL
```

The LLM also cannot generate arbitrary SQL and execute it directly.

Only known read-only application tools are allowed.

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

The rest of the architecture is not tied directly to that provider.

During development, the workflow was initially tested with Gemini. Because model configuration is isolated, the provider could be changed without redesigning:

- LangGraph topology,
- state,
- PostgreSQL tools,
- investigation logic,
- memory,
- evaluation code.

This keeps provider-specific configuration separate from the main application logic.

---

# 9. Structured Outputs

Important LLM outputs are validated using Pydantic schemas in:

```text
agent/schemas.py
```

Key schemas include:

```text
IntentDecision
InvestigationAction
InvestigationPlan
EvidenceAssessment
EvidenceItem
RCAResult
```

For example, the final `RCAResult` separates:

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

This is easier to inspect and evaluate than one unrestricted paragraph.

Some normalization is also performed at the schema boundary so minor differences in provider output format do not unnecessarily break an otherwise valid response.

---

# 10. Conversational Memory

Conversation continuity uses three pieces:

```text
AgentState
    │
    │ WHAT is remembered
    ▼
MemorySaver
    │
    │ HOW state is checkpointed
    ▼
thread_id
    │
    │ WHICH conversation the state belongs to
```

## AgentState

Stores:

- messages,
- anomaly,
- retrieved evidence,
- evidence assessment,
- investigation progress,
- final RCA.

## MemorySaver

The LangGraph application is compiled with:

```text
MemorySaver
```

as its checkpointer.

## thread_id

The CLI creates one `thread_id` before entering the conversation loop and reuses it for later requests.

The relevant implementation is in:

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

does not require the user to enter the anomaly ID again.

The existing investigation is recovered from the same LangGraph thread.

---

# 11. Grounding and Hallucination Controls

Grounding is handled in two ways:

1. **architectural controls**, which restrict what evidence the agent can use and how it can access it;
2. **evaluation**, which tests whether relevant evidence was retrieved and whether generated claims are supported by that evidence.

## Controlled Evidence Sources

Investigation evidence comes from the supplied PostgreSQL sources:

```text
detected_anomalies
network_devices
device_syslogs
device_telemetry
```

The investigation workflow does not freely search for external evidence.

---

## Evidence Stored in State

Retrieved evidence is stored in `AgentState`.

Later reasoning therefore operates on evidence that was actually collected during the investigation.

---

## Controlled Tool Execution

The LLM can propose what evidence it wants.

Application code validates the requested:

- tool,
- device,
- time range,
- parameters,

before executing it.

The model cannot directly execute arbitrary SQL or database writes.

---

## Evidence References in the RCA

The final RCA contains structured supporting-evidence entries.

For example:

```text
[LOG-002117] device_syslogs:
High pre-FEC BER and degraded Rx optical power...
```

This makes it easier to trace a conclusion back to the evidence used to support it.

---

## Explicit Missing Evidence

The agent is also expected to say what it does **not** know.

For example:

```text
Likely domain:
physical / optical degradation

Known:
- link flaps
- optical degradation
- OSPF disruption

Still unknown:
- fiber vs transceiver vs connector
```

The goal is to stop at the level of detail supported by the evidence rather than inventing a more specific explanation.

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

The most likely cause identified by the agent was:

> **Physical-layer degradation on the backbone uplink causing intermittent link flaps.**

Confidence:

```text
high
```

## Evidence Chain

The investigation correlated:

1. high pre-FEC BER,
2. Rx optical power around `-18.2 dBm`,
3. a logged threshold around `-15.0 dBm`,
4. physical link-down/up events,
5. matching events at both ends of the link,
6. OSPF neighbor loss after the link problem,
7. downstream BGP disruption,
8. device context showing the interfaces are opposite ends of the same backbone link.

The sequence is consistent with:

```text
Physical / optical degradation
             │
             ▼
      Physical link flap
             │
             ▼
      OSPF adjacency loss
             │
             ▼
        BGP disruption
```

This is why the agent treats the OSPF and BGP events as downstream effects rather than the initiating cause.

## Remaining Uncertainty

The available evidence does not identify the exact failed physical component.

It could be related to:

- fiber,
- transceiver,
- connector,
- patch cable.

The RCA therefore reports the broader **physical/optical failure domain** while keeping the exact component unresolved.

---

# 13. Follow-Up Conversation

After the RCA is generated:

```text
> Why do you believe this was a physical-layer problem?

[intent: follow_up]
```

The response uses the retained investigation and supporting evidence rather than starting over.

Another example:

```text
> What uncertainty remains?

[intent: follow_up]
```

The agent can explain what evidence is still missing.

A third tested follow-up was:

```text
> what are different anomalies being reported?

[intent: follow_up]
```

The agent can reason over the retained investigation and distinguish between:

- physical interface flaps,
- OSPF neighbor-down events,
- downstream BGP disruption.

This demonstrates the conversational-memory requirement.

---

# 14. General Networking Q&A

General networking questions use a separate graph path.

Example:

```text
> What is the difference between a physical interface flap
  and an OSPF adjacency failure?

[intent: general_qa]
```

The response explains that:

- an interface flap is mainly a Layer 1 / Layer 2 link-state event,
- an OSPF adjacency failure is a Layer 3 routing relationship failure,
- a physical flap can cause an OSPF adjacency failure,
- but an OSPF failure does not necessarily mean the physical link failed.

This path does not require investigation-specific PostgreSQL retrieval.

---

# 15. Evaluation Strategy

The system is evaluated at several different levels because an agent can fail in different ways.

For example:

- it may retrieve the wrong evidence,
- retrieve incomplete evidence,
- generate claims that are not supported,
- become overconfident when evidence is missing,
- or fail to complete the workflow.

For that reason, the evaluation is split into:

1. **retrieval quality**,
2. **generation groundedness**,
3. **thin-evidence behavior**,
4. **end-to-end execution robustness**.

---

# 16. Retrieval Quality Evaluation

A small human-curated benchmark was created for three representative anomaly types:

```text
interface_flap
policy_deny
sdwan_path_quality
```

For each benchmark incident, a set of evidence concepts that should ideally be retrieved was defined.

Examples include:

```text
optical degradation
physical link flap
topology relationship
OSPF disruption
policy deny events
affected firewall
packet-loss degradation
WAN circuit context
SD-WAN path event
```

Across the three benchmark incidents:

```text
Benchmark incidents:          3
Required evidence concepts:  16
Retrieved concepts:          13
Evidence Recall:          0.812
```

So the agent retrieved:

```text
13 / 16 = 81.2%
```

of the manually defined evidence concepts.

The missed concepts were:

```text
deny_count_telemetry
affected_branch_device
path_quality_telemetry
```

This is useful because it shows that the retrieval layer is not perfect.

The agent can still reach a useful investigation result without retrieving every possible evidence item, but the misses identify where the planner/retrieval process could be improved.

The evaluation can be run with:

```bash
PYTHONPATH=/home/jovyan/work python eval/evaluate_retrieval.py
```

Results are written to:

```text
eval/results/retrieval_results.csv
```

## What Evidence Recall Means Here

For this benchmark:

```text
Evidence Recall =
retrieved required evidence concepts
------------------------------------
total required evidence concepts
```

This is a **small curated benchmark**, not a production-wide retrieval score.

Its purpose is to provide a transparent way to test whether the investigation is finding evidence that a human reviewer considered important.

---

# 17. Generation Groundedness Evaluation

Retrieval quality answers:

> **Did the agent collect the evidence it should have collected?**

Generation groundedness asks a different question:

> **Are the factual claims in the RCA supported by the evidence the agent actually retrieved?**

The groundedness evaluator takes the generated RCA and breaks it into factual claims.

Each claim is then evaluated against the evidence collected during that investigation.

A claim can be classified as:

```text
SUPPORTED
UNSUPPORTED
CONTRADICTED
NOT_VERIFIABLE
```

Across the same three benchmark incidents:

```text
Total factual claims:       25
Supported:                  24
Unsupported:                 0
Contradicted:                0
Not verifiable:              1

Supported Claim Ratio:   0.960
```

So:

```text
24 / 25 = 96.0%
```

of the evaluated factual claims were supported by retrieved evidence.

The one `NOT_VERIFIABLE` claim concerned whether the observed firewall-policy behavior was intentionally designed that way.

The evidence showed that the policy blocked traffic, but it did not prove operator intent.

That distinction is important: the evaluator did not automatically treat every generated statement as supported.

The evaluation can be run with:

```bash
PYTHONPATH=/home/jovyan/work python eval/evaluate_groundedness.py
```

Results are written to:

```text
eval/results/groundedness_results.csv
```

## Important Interpretation

The **96.0% supported-claim ratio is not 96% RCA accuracy**.

It means that, on this small benchmark, 24 of the 25 factual claims evaluated by the groundedness process were supported by evidence retrieved during the investigation.

End-to-end RCA correctness would require a larger set of incidents with SME-reviewed final resolutions.

---

# 18. Retrieval Completeness vs. Generation Grounding

The two evaluation results measure different things:

```text
Retrieval Evidence Recall        81.2%
Generation Supported Claims      96.0%
```

These numbers are not expected to be the same.

Retrieval evaluation asks:

> Did the investigation retrieve all evidence concepts that the benchmark expected?

Generation evaluation asks:

> Given the evidence that was retrieved, did the RCA stay supported by that evidence?

The results suggest that the agent did not retrieve every potentially useful evidence concept, but it was relatively conservative about the factual claims it generated from the evidence it did retrieve.

In other words:

```text
Retrieval completeness
        │
        │ 81.2%
        ▼
Evidence available to the agent
        │
        ▼
RCA generation
        │
        │ 96.0% of evaluated claims supported
        ▼
Structured RCA
```

This helps separate two different improvement areas:

- **retrieval improvement** — find more of the relevant evidence,
- **generation grounding** — avoid making claims beyond the evidence that was found.

---

# 19. Thin-Evidence Behavior

A separate test checks what happens when corroborating evidence is intentionally removed.

The test provides:

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

The evidence-analysis stage explicitly reports missing information such as:

- device context,
- syslogs,
- interface counters,
- physical-layer/error telemetry,
- topology information.

Instead of forcing a precise RCA, it reports that the available evidence is insufficient.

This demonstrates an important behavior:

> **Missing evidence is represented as uncertainty rather than automatically being converted into a confident root-cause story.**

Run with:

```bash
PYTHONPATH=/home/jovyan/work python eval/test_thin_evidence.py
```

---

# 20. End-to-End Dataset Evaluation

The same LangGraph investigation workflow was also run across all **10 supplied anomalies**.

The dataset covers six detector types:

```text
interface_flap
policy_deny
sdwan_path_quality
bgp_session
interface_availability
interface_error
```

Observed execution results:

```text
Total anomalies:          10
Successful executions:    10
Failed executions:         0
Detector types covered:    6
Average investigation:    ~2 rounds
Average runtime:          ~11 seconds
```

This evaluates:

- graph completion,
- detector coverage,
- structured RCA generation,
- investigation depth,
- runtime,
- workflow robustness across different anomaly types.

## Important Interpretation

The `10/10` result means that all ten workflows completed successfully.

It does **not** mean that the system achieved 100% RCA accuracy.

The supplied dataset does not provide SME-reviewed final root causes for every incident.

---

# 21. Evaluation Summary

The evaluation currently covers four different behaviors:

| Evaluation Layer | Scope | Result |
|---|---|---:|
| Retrieval quality | 3 curated incidents / 16 evidence concepts | **81.2% evidence recall** |
| Generation grounding | 25 factual claims | **96.0% supported-claim ratio** |
| Thin-evidence behavior | Evidence ablation test | **medium confidence / insufficient evidence** |
| Workflow robustness | 10 seeded anomalies / 6 detector types | **10/10 completed** |

These metrics answer different questions and should not be combined into one overall "accuracy" number.

---

# 22. Evaluation Limitations and Future Improvements

The evaluation is intentionally small and should not be treated as a production-calibrated benchmark.

## Small Curated Retrieval Benchmark

The retrieval benchmark currently covers three incidents and 16 manually defined evidence concepts.

A stronger benchmark would include many more resolved incidents across additional detector types and network conditions.

## Automated Groundedness Evaluation

The claim-level groundedness evaluator provides a useful automated check, but it is not a replacement for expert review.

A production evaluation should compare claims against:

- SME-reviewed incident resolutions,
- authoritative network state,
- known root causes,
- verified remediation outcomes.

## No Complete RCA Ground Truth

The supplied dataset does not contain final SME-reviewed root causes for every anomaly.

Therefore, semantic RCA accuracy cannot currently be measured reliably across the full dataset.

## Future Metrics

With a larger labeled dataset, useful metrics would include:

| Evaluation Dimension | Example Metric |
|---|---|
| RCA correctness | SME agreement / root-cause accuracy |
| Evidence retrieval | Recall@K / evidence recall |
| Tool selection | tool-selection accuracy |
| Tool parameters | argument correctness |
| Grounding | supported-claim ratio |
| Efficiency | unnecessary/repeated tool calls |
| Confidence | calibration / reliability |
| Runtime | p50 / p95 latency |
| Cost | tokens / investigation |
| Reliability | provider failure rate |

For larger-scale evaluation I would also add:

- controlled concurrency,
- provider-aware rate limiting,
- retry/backoff,
- resumable runs,
- persistent result storage,
- token/cost tracking,
- prompt versioning,
- model-version tracking.

---

# 23. Confidence Interpretation

Confidence is currently an LLM-assessed categorical value:

```text
high
medium
low
```

It represents the model's assessment of the strength and consistency of the available evidence.

It is **not a statistically calibrated probability**.

For example, during testing, one planned-maintenance anomaly contained a strong change reference directly in its anomaly metadata. The model returned `high` confidence even though additional syslogs and telemetry were unavailable.

That behavior shows why the current confidence field should be understood as an evidence-based LLM judgment rather than a probability.

A production implementation could improve this with:

- deterministic evidence-quality signals,
- SME-reviewed incidents,
- confidence calibration,
- historical reliability analysis,
- separate confidence dimensions.

For example:

```text
Failure-domain confidence: HIGH
Exact-component confidence: LOW
```

The interface-flap example demonstrates this distinction:

```text
HIGH confidence:
physical / optical degradation

LOWER confidence:
fiber vs transceiver vs connector vs cable
```

---

# 24. Known Limitations

## 1. Retrieval Is Not Complete

The curated retrieval benchmark achieved **81.2% evidence recall**.

The current planner therefore does not always retrieve every evidence source that a human benchmark considers useful.

This is a clear area for improvement.

---

## 2. Groundedness Benchmark Is Small

Claim-level evaluation achieved a **96.0% supported-claim ratio** on 25 factual claims across three benchmark incidents.

This is useful evidence of current behavior, but the sample is too small to treat the result as a general production guarantee.

---

## 3. No Complete RCA Ground Truth

The supplied dataset does not provide SME-reviewed final incident resolutions for every anomaly.

End-to-end semantic RCA accuracy therefore cannot be reliably calculated across the full dataset.

---

## 4. Confidence Is Not Calibrated

Confidence is an LLM-generated categorical assessment.

It should not be interpreted as a probability.

---

## 5. In-Memory Checkpointing

`MemorySaver` preserves conversation state while the application process is running.

The state does not survive a process/container restart.

A production system should use a persistent LangGraph checkpointer or external state store.

---

## 6. External LLM Dependency

The reasoning layer depends on an external LLM provider and can therefore be affected by:

- latency,
- quota limits,
- rate limits,
- temporary provider errors,
- model behavior changes.

The provider configuration is isolated so the backend can be changed without redesigning the workflow.

---

## 7. Limited Physical Diagnostics

The dataset can indicate a physical/optical problem but may not contain enough information to distinguish between:

```text
fiber
transceiver
connector
patch cable
```

---

## 8. Limited Explicit Topology Model

Some topology relationships are inferred from device metadata and notes.

A production implementation should ideally query an authoritative topology or CMDB source.

---

## 9. No Autonomous Remediation

The agent investigates incidents and recommends next checks.

It intentionally does **not**:

- modify network configuration,
- restart devices,
- shut interfaces,
- execute remediation.

This keeps the system focused on investigation and avoids unsafe autonomous network changes.

---

# 25. Development Environment

The project uses the Docker/Compose environment supplied with the challenge.

## First Build

For a fresh environment:

```bash
docker compose -f podman-compose.yml up --build -d
```

The first local build took approximately **80 minutes** on the development machine.

This was environment setup time, **not investigation runtime**.

Likely contributors include:

- downloading the Python dependency stack,
- dependency resolution,
- installation of larger packages,
- Docker layer creation,
- local disk/network performance,
- an empty Docker/package cache on the first build.

Once the environment is built, the full build does not need to be repeated for normal startup.

## Normal Startup

```bash
docker compose -f podman-compose.yml up -d
```

Check containers:

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

# 26. Improving the Container Setup

For a production environment, setup time could be improved by:

- pinning dependency versions,
- maintaining a reproducible lock file,
- separating dependency layers from application-code layers,
- making better use of Docker layer caching,
- using a prebuilt dependency image,
- publishing the final image to a container registry.

A production delivery flow could look like:

```text
Developer / CI
      │
      ▼
 Build + Test Image
      │
      ▼
Container Registry
      │
      ▼
Deployment / Reviewer
      │
      ▼
   docker pull
```

This avoids requiring every user to rebuild the full dependency stack locally.

---

# 27. Running the CLI

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

Continue in the same session:

```text
> Why do you believe this was a physical-layer problem?

[intent: follow_up]
...
```

---

# 28. Database Inspection

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

The investigation agent accesses these tables through controlled application tools rather than unrestricted model-generated SQL.

---

# 29. Repository Structure

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
│   │   └── end-to-end evaluation across seeded anomalies
│   │
│   ├── reference_cases.py
│   │   └── curated evidence benchmark definitions
│   │
│   ├── evaluate_retrieval.py
│   │   └── retrieval evidence-recall evaluation
│   │
│   ├── evaluate_groundedness.py
│   │   └── claim-level generation-groundedness evaluation
│   │
│   ├── test_thin_evidence.py
│   │   └── evidence-scarcity behavior test
│   │
│   └── results/
│       ├── evaluation_results.csv
│       ├── retrieval_results.csv
│       └── groundedness_results.csv
│
├── main.py
│   └── stateful CLI and thread lifecycle
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

# 30. Requirement Coverage

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
| Evidence selection not hardcoded by anomaly type | Yes |
| LangGraph | Yes |
| Explicit state | Yes |
| Explicit nodes and edges | Yes |
| Tool integration | Yes |
| Memory/checkpointing | Yes |
| Thin-evidence behavior | Tested |
| Retrieval evaluation | Yes |
| Generation-grounding evaluation | Yes |
| End-to-end evaluation | Yes |
| Required interface-flap example | Yes |
| Follow-up example | Yes |

---

# 31. Design Summary

The main design principle is **controlled agent autonomy**.

```text
                    LLM
                     │
                     │ decides what evidence is useful
                     │ and interprets evidence
                     ▼
                  LangGraph
                     │
                     │ controls workflow,
                     │ state and loops
                     ▼
              Python Tool Layer
                     │
                     │ validates actions
                     ▼
                  PostgreSQL
                     │
                     │ returns evidence
                     ▼
                  AgentState
                     │
                     ▼
               Structured RCA
```

The design avoids two extremes:

```text
Fully hardcoded workflow                  Unrestricted LLM agent
          │                                         │
          └────────────────┐       ┌────────────────┘
                           ▼       ▼
                       THIS DESIGN
                Controlled Agent Autonomy
```

The responsibilities are intentionally separated:

- **LLM** — semantic reasoning and evidence interpretation
- **LangGraph** — state, routing, control flow, and investigation loops
- **Python** — deterministic validation and tool execution
- **PostgreSQL** — investigation evidence
- **Pydantic** — structured output validation
- **Evaluation layer** — retrieval coverage, claim grounding, uncertainty behavior, and execution robustness

The final RCA is designed to distinguish three things clearly:

> **What the evidence supports, what remains uncertain, and what should be checked next.**
