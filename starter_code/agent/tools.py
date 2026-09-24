from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from db import run_query


@tool
def get_anomaly(anomaly_id: str) -> dict[str, Any]:
    """
    Retrieve one detected anomaly by anomaly_id.

    Returns the anomaly metadata and detector-specific model_output payload.
    """
    rows = run_query(
        """
        SELECT
            anomaly_id,
            severity,
            anomaly_date,
            model_output
        FROM detected_anomalies
        WHERE anomaly_id = %s;
        """,
        (anomaly_id,),
    )

    if not rows:
        return {
            "found": False,
            "anomaly_id": anomaly_id,
            "message": "No anomaly found for the provided anomaly_id.",
        }

    return {
        "found": True,
        "anomaly": rows[0],
    }


@tool
def get_device_context(hostnames: list[str]) -> list[dict[str, Any]]:
    """
    Retrieve inventory, site, topology, and WAN context for one or more hostnames.

    Hostnames come from detected_anomalies.model_output.impacted_hostnames.
    Matching is case-sensitive because the provided schema documents hostname
    matching as case-sensitive and as-is.
    """
    if not hostnames:
        return []

    placeholders = ", ".join(["%s"] * len(hostnames))

    sql = f"""
        SELECT
            device_id,
            hostname,
            mgmt_ip,
            device_type,
            vendor,
            model,
            role,
            site_code,
            site_name,
            city,
            state,
            region,
            install_date,
            os_version,
            status,
            wan_provider,
            wan_circuit_id,
            wan_circuit_group,
            notes
        FROM network_devices
        WHERE hostname IN ({placeholders})
        ORDER BY hostname;
    """

    return run_query(sql, tuple(hostnames))


@tool
def get_syslogs(
    device_ids: list[str],
    start_time: str,
    end_time: str,
    message_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve timestamped syslog evidence for one or more devices.

    start_time and end_time should be UTC timestamps compatible with PostgreSQL,
    for example: '2026-07-08 06:00:00'.

    message_type is optional and can be used to narrow results to categories
    such as interface, routing, bgp, policy, sdwan, or bfd.
    """
    if not device_ids:
        return []

    placeholders = ", ".join(["%s"] * len(device_ids))
    params: list[Any] = [*device_ids, start_time, end_time]

    sql = f"""
        SELECT
            log_id,
            device_id,
            timestamp,
            severity,
            message_type,
            message
        FROM device_syslogs
        WHERE device_id IN ({placeholders})
          AND timestamp BETWEEN %s AND %s
    """

    if message_type:
        sql += " AND message_type = %s"
        params.append(message_type)

    sql += " ORDER BY timestamp;"

    return run_query(sql, tuple(params))


@tool
def get_telemetry(
    device_ids: list[str],
    start_time: str,
    end_time: str,
) -> list[dict[str, Any]]:
    """
    Retrieve hourly telemetry for one or more devices within a UTC time window.

    The table is wide and contains device-type-specific metrics. NULL means
    unavailable or not applicable and should not be interpreted as zero.
    """
    if not device_ids:
        return []

    placeholders = ", ".join(["%s"] * len(device_ids))
    params: list[Any] = [*device_ids, start_time, end_time]

    sql = f"""
        SELECT
            device_id,
            timestamp,
            cpu_utilization_pct,
            memory_utilization_pct,
            temperature_celsius,
            active_sessions,
            bgp_established_peers,
            interfaces_up_ratio,
            interface_error_count,
            interface_flap_count,
            policy_deny_count,
            latency_ms,
            jitter_ms,
            packet_loss_pct
        FROM device_telemetry
        WHERE device_id IN ({placeholders})
          AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp, device_id;
    """

    return run_query(sql, tuple(params))