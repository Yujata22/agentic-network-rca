from pprint import pprint

from agent.nodes import analyze_evidence
from agent.tools import get_anomaly


ANOMALY_ID = "a1f0c8e2-1b44-4d90-9c31-000000000001"


# ---------------------------------------------------------------------------
# 1. Load a real anomaly from the supplied PostgreSQL database
# ---------------------------------------------------------------------------

result = get_anomaly.invoke(
    {
        "anomaly_id": ANOMALY_ID,
    }
)

anomaly = result["anomaly"]


# ---------------------------------------------------------------------------
# 2. Deliberately construct a THIN-EVIDENCE investigation state
#
# We retain the real anomaly metadata but provide no corroborating:
# - device context
# - syslogs
# - telemetry
#
# This is an evaluation / ablation test.
# ---------------------------------------------------------------------------

thin_state = {
    "anomaly_id": ANOMALY_ID,
    "anomaly": anomaly,

    "device_context": [],
    "syslogs": [],
    "telemetry": [],

    "investigation_round": 1,
    "investigation_summary": (
        "Thin-evidence evaluation: only anomaly metadata is available. "
        "No corroborating device context, syslogs, or telemetry were supplied."
    ),
}


# ---------------------------------------------------------------------------
# 3. Run the SAME evidence-assessment node used by the production graph
# ---------------------------------------------------------------------------

assessment_update = analyze_evidence(thin_state)

assessment = assessment_update["evidence_assessment"]


print("\n" + "=" * 70)
print("THIN-EVIDENCE EVALUATION")
print("=" * 70)

print(f"\nAnomaly ID: {ANOMALY_ID}")

print("\nEvidence supplied:")
print("  anomaly metadata : YES")
print("  device context   : NO")
print("  syslogs          : NO")
print("  telemetry        : NO")

print("\nEvidence assessment:")
pprint(assessment)

print("\nKey behavior:")
print("  Confidence          :", assessment.get("confidence"))
print("  Evidence sufficient :", assessment.get("evidence_sufficient"))

print("\nMissing evidence:")
for item in assessment.get("missing_evidence", []):
    print(" -", item)

print("\nContradictory findings:")
for item in assessment.get("contradictory_findings", []):
    print(" -", item)

print("\nReasoning:")
print(assessment.get("reasoning_summary"))
