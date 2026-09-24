# Implementation Notes

## 1. Environment and data understanding

- Used the supplied Docker Compose environment without changing the infrastructure.
- PostgreSQL database: `network_rca`.
- Four supplied evidence tables:
  - `detected_anomalies`
  - `network_devices`
  - `device_syslogs`
  - `device_telemetry`
- Dataset contains 10 detected anomalies across 6 detector types.
- Telemetry covers 21 devices and is sampled hourly.
- Syslogs provide finer-grained event evidence.
- All timestamps represent UTC.

## 2. Reference investigation

Manually investigated the required `interface_flap` anomaly before implementing
the agent.

Purpose:
- Understand how evidence is distributed across the supplied tables.
- Establish an expected/reference RCA.
- Avoid blindly designing tools without understanding the data.

Important finding:
- The two impacted interfaces are opposite ends of the same backbone link.
- Telemetry showed interface errors/flaps.
- Syslogs showed optical degradation immediately preceding repeated physical
  link flaps.
- Routing/BGP disruption followed the physical-layer events.

This investigation is used as a reference case, not as hardcoded agent logic.

## 3. Tool-layer design

Kept the supplied `db.py` as the low-level PostgreSQL access abstraction.

Added generic read-only agent tools:

- `get_anomaly(anomaly_id)`
- `get_device_context(hostnames)`
- `get_syslogs(device_ids, start_time, end_time, message_type=None)`
- `get_telemetry(device_ids, start_time, end_time)`

Design principle:
Tools are organized around evidence sources rather than anomaly types. There is
no `investigate_interface_flap()` or other detector-specific database workflow.

This allows the reasoning layer to choose which evidence is relevant for each
investigation.

## 4. Tool validation

Tools were tested independently before integration with LangGraph.

### get_anomaly
Validated using the required interface-flap anomaly.
Confirmed retrieval of detector-specific JSON, impacted hosts/interfaces,
investigation window, severity, and detector signals.

### get_device_context
Validated hostname-to-device resolution and topology enrichment.
Confirmed that device notes exposed the backbone relationship between the
two affected routers.

### get_syslogs
Queried both affected device IDs over the anomaly window without initially
filtering by message type.

Returned 16 events and recovered the expected multi-signal sequence:
optical degradation -> physical link transitions -> OSPF/BGP effects.

This confirmed that evidence retrieval works without hardcoding the expected
interface/routing event types.
