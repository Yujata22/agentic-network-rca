from __future__ import annotations

import csv
import time
import uuid
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from agent.graph import build_graph
from db import run_query


OUTPUT_DIR = Path("eval/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "evaluation_results.csv"


def get_seeded_anomalies() -> list[dict[str, Any]]:
    """
    Load all seeded anomalies used for the evaluation.

    Detector and severity are retrieved directly from Postgres so the
    evaluation harness does not hardcode anomaly metadata.
    """

    return run_query(
        """
        SELECT
            anomaly_id,
            severity,
            model_output->>'detector' AS detector,
            model_output->>'criticality' AS criticality
        FROM detected_anomalies
        ORDER BY anomaly_id;
        """
    )



def load_existing_results() -> dict[str, dict[str, Any]]:
    """Load prior evaluation rows keyed by anomaly_id.

    Successful rows are preserved so a later run resumes only incomplete cases.
    """

    if not OUTPUT_FILE.exists():
        return {}

    with OUTPUT_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["anomaly_id"]: row for row in reader}


def is_quota_error(error_text: str | None) -> bool:
    """Return True when a failure is clearly a provider quota/rate-limit error."""

    if not error_text:
        return False

    text = error_text.lower()
    return (
        "resourceexhausted" in text
        or "429" in text
        or "quota exceeded" in text
        or "rate limit" in text
    )


def retry_after_seconds(error_text: str | None, default: int = 65) -> int:
    """Extract Gemini's suggested retry delay when present.

    Falls back to a conservative delay slightly above the free-tier minute window.
    """

    if not error_text:
        return default

    patterns = [
        r"Please retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retry_delay\s*\{\s*seconds:\s*([0-9]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return max(int(float(match.group(1))) + 3, 5)

    return default


def normalize_existing_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert selected numeric CSV fields back to useful Python types."""

    numeric_int_fields = {
        "investigation_rounds",
        "affected_device_count",
        "device_context_count",
        "syslog_count",
        "telemetry_count",
        "supporting_evidence_count",
        "missing_evidence_count",
    }

    for field in numeric_int_fields:
        value = row.get(field)
        if value not in (None, ""):
            try:
                row[field] = int(value)
            except ValueError:
                pass

    value = row.get("latency_seconds")
    if value not in (None, ""):
        try:
            row["latency_seconds"] = float(value)
        except ValueError:
            pass

    return row


def safe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def evaluate_one(app, anomaly: dict[str, Any]) -> dict[str, Any]:
    """
    Execute one complete RCA investigation and record operational metrics.

    Each anomaly gets its own LangGraph thread so checkpoint state cannot
    leak between evaluation cases.
    """

    anomaly_id = anomaly["anomaly_id"]

    thread_id = f"eval-{anomaly_id[-4:]}-{uuid.uuid4().hex[:8]}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    started = time.perf_counter()

    try:
        result = app.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=f"Investigate anomaly {anomaly_id}"
                    )
                ]
            },
            config=config,
        )

        latency_seconds = round(
            time.perf_counter() - started,
            2,
        )

        rca = result.get("rca") or {}

        evidence_assessment = (
            result.get("evidence_assessment") or {}
        )

        return {
            "anomaly_id": anomaly_id,
            "detector": anomaly.get("detector"),
            "severity": anomaly.get("severity"),
            "status": "success",
            "intent": result.get("intent"),
            "investigation_rounds": result.get(
                "investigation_round"
            ),
            "needs_more_evidence": result.get(
                "needs_more_evidence"
            ),
            "confidence": rca.get("confidence"),
            "affected_device_count": len(
                rca.get("affected_devices", [])
            ),
            "device_context_count": safe_len(
                result.get("device_context")
            ),
            "syslog_count": safe_len(
                result.get("syslogs")
            ),
            "telemetry_count": safe_len(
                result.get("telemetry")
            ),
            "supporting_evidence_count": len(
                rca.get("supporting_evidence", [])
            ),
            "missing_evidence_count": len(
                evidence_assessment.get(
                    "missing_evidence",
                    [],
                )
            ),
            "root_cause": rca.get("root_cause"),
            "latency_seconds": latency_seconds,
            "error": None,
        }

    except Exception as exc:
        latency_seconds = round(
            time.perf_counter() - started,
            2,
        )

        return {
            "anomaly_id": anomaly_id,
            "detector": anomaly.get("detector"),
            "severity": anomaly.get("severity"),
            "status": "failed",
            "intent": None,
            "investigation_rounds": None,
            "needs_more_evidence": None,
            "confidence": None,
            "affected_device_count": 0,
            "device_context_count": 0,
            "syslog_count": 0,
            "telemetry_count": 0,
            "supporting_evidence_count": 0,
            "missing_evidence_count": 0,
            "root_cause": None,
            "latency_seconds": latency_seconds,
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_results(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, Any]]) -> None:
    total = len(rows)

    success_rows = [
        row
        for row in rows
        if row["status"] == "success"
    ]

    failed_rows = [
        row
        for row in rows
        if row["status"] == "failed"
    ]

    print("\n" + "=" * 72)
    print("NETWORK RCA AGENT EVALUATION SUMMARY")
    print("=" * 72)

    print(f"Total anomalies:        {total}")
    print(f"Successful runs:        {len(success_rows)}")
    print(f"Failed runs:            {len(failed_rows)}")

    if success_rows:
        avg_latency = sum(
            row["latency_seconds"]
            for row in success_rows
        ) / len(success_rows)

        avg_rounds = sum(
            row["investigation_rounds"]
            for row in success_rows
            if row["investigation_rounds"] is not None
        ) / len(success_rows)

        print(
            f"Average latency:        "
            f"{avg_latency:.2f} sec"
        )

        print(
            f"Average investigation:  "
            f"{avg_rounds:.2f} rounds"
        )

    detectors = sorted(
        {
            row["detector"]
            for row in rows
            if row["detector"]
        }
    )

    print("\nDetector coverage:")

    for detector in detectors:
        detector_rows = [
            row
            for row in rows
            if row["detector"] == detector
        ]

        detector_success = sum(
            row["status"] == "success"
            for row in detector_rows
        )

        print(
            f"  {detector:<28}"
            f"{detector_success}/{len(detector_rows)} successful"
        )

    if failed_rows:
        print("\nFailures:")

        for row in failed_rows:
            print(
                f"  {row['anomaly_id']} "
                f"({row['detector']}): "
                f"{row['error']}"
            )

    print(
        f"\nDetailed results written to: "
        f"{OUTPUT_FILE}"
    )


def main() -> None:
    anomalies = get_seeded_anomalies()

    print(f"Loaded {len(anomalies)} seeded anomalies.")

    app = build_graph()
    existing = load_existing_results()

    # Preserve prior rows by anomaly_id so successful work is never rerun.
    results_by_id: dict[str, dict[str, Any]] = {
        anomaly_id: normalize_existing_row(dict(row))
        for anomaly_id, row in existing.items()
    }

    max_attempts = 3
    inter_case_delay_seconds = 10

    for index, anomaly in enumerate(anomalies, start=1):
        anomaly_id = anomaly["anomaly_id"]

        print(
            f"\n[{index}/{len(anomalies)}] "
            f"{anomaly['detector']} | {anomaly_id}"
        )

        previous = results_by_id.get(anomaly_id)
        if previous and previous.get("status") == "success":
            print("  skipping: already successful in prior evaluation")
            continue

        result: dict[str, Any] | None = None

        for attempt in range(1, max_attempts + 1):
            result = evaluate_one(app, anomaly)

            if result["status"] == "success":
                break

            error_text = result.get("error")

            if not is_quota_error(error_text):
                break

            if attempt < max_attempts:
                wait_seconds = retry_after_seconds(error_text)
                print(
                    f"  quota/rate limit hit; waiting {wait_seconds}s "
                    f"before retry {attempt + 1}/{max_attempts}"
                )
                time.sleep(wait_seconds)

        assert result is not None
        results_by_id[anomaly_id] = result

        ordered_results = [
            results_by_id[a["anomaly_id"]]
            for a in anomalies
            if a["anomaly_id"] in results_by_id
        ]

        # Persist after every case so progress survives interruption/quota exhaustion.
        write_results(ordered_results)

        print(
            f"  status={result['status']} "
            f"rounds={result['investigation_rounds']} "
            f"confidence={result['confidence']} "
            f"latency={result['latency_seconds']}s"
        )

        if result["status"] == "success":
            print(f"  RCA: {result['root_cause']}")
        else:
            print(f"  ERROR: {result['error']}")

        # Small spacing reduces immediate back-to-back pressure on the provider.
        if index < len(anomalies):
            time.sleep(inter_case_delay_seconds)

    final_results = [
        results_by_id[a["anomaly_id"]]
        for a in anomalies
        if a["anomaly_id"] in results_by_id
    ]

    print_summary(final_results)


if __name__ == "__main__":
    main()
