# Database Schema Reference

Database: `network_rca` (Postgres 16). Connection string is in `.env` / `DATABASE_URL`. All tables live in the `public` schema and are already created and seeded when the `postgres` container starts (see `db/init/`). You do not need to write any DDL or loading code yourself.

There are four tables: `detected_anomalies`, `network_devices`, `device_telemetry`, `device_syslogs`. There is no separate topology, incident, or change-management table — related context is carried as plain columns on `network_devices` and as log lines in `device_syslogs`.

**Timestamps are UTC.** `detected_anomalies.model_output` uses ISO8601 with a `Z` suffix (e.g. `2026-07-08T07:02:30Z`); `device_telemetry.timestamp` and `device_syslogs.timestamp` store the same UTC instants as naive Postgres `TIMESTAMP` (e.g. `2026-07-08 07:02:30`). Join anomaly `window` bounds against telemetry/syslog timestamps directly — no timezone offset is needed.

## 1. `detected_anomalies`

Provided as-is by the hiring team. Columns:

| Column | Type | Notes |
|---|---|---|
| `anomaly_id` | text (PK) | UUID-format identifier, uniform across rows (a shared prefix with a zero-padded sequential suffix, `…000000000001` through `…000000000010`). |
| `severity` | text | Model-reported severity. One of `critical`, `high`, `medium`, `low`. |
| `model_output` | jsonb | Structured detection payload. The shape is **detector-specific** — see [`model_output` shape](#model_output-shape) below. Query with Postgres JSON operators, e.g. `model_output->>'detector'`, `model_output->'impacted_hostnames'`, `model_output->'event_summary'->>'upstream_trigger_hint'`. |
| `anomaly_date` | date | The date the underlying anomaly window falls on. |

### `model_output` shape

The payload is **not uniform** — its shape depends on the `detector` that produced the anomaly. There is a common set of fields present on every row, plus detector-specific blocks. Part of the investigation is discovering this structure; the summary below describes what is actually in the data.

**Common fields (all rows):**

- `detector`: string identifying the detector. One of: `interface_flap`, `interface_error`, `interface_availability`, `bgp_session`, `policy_deny`, `sdwan_path_quality`.
- `window`: `{start, end}` — ISO8601 timestamps bounding the event (e.g. `model_output->'window'->>'start'`).
- `impacted_hostnames`: array of hostname strings. Join these against `network_devices.hostname` (case-sensitive, as-is) to resolve `device_id`, role, site, and topology `notes`. Note: this is a plain array of hostnames — there is no `device_id` embedded in the payload, so resolve it via the join.
- `host_count`: integer count of impacted hosts.
- `criticality`: overall severity string, mirroring the top-level `severity` column (`critical` / `high` / `medium` / `low`).
- Per-signal impact fields: one or more `<SIGNAL>_impact_score` (numeric) and `<SIGNAL>_criticality` (string) pairs, where `<SIGNAL>` describes the affected control-plane/data-plane signal. Signals seen in the data: `SNMP_LINK`, `OSPF_NBR`, `LLDP_NBR`, `BGP`, `VPN`, `POLICY`, `BFD`, `SDWAN`. Which pairs are present depends on the detector.

**Interface fields (present on `interface_flap`, `interface_error`, `interface_availability`; also on `bgp_session`):**

- `impacted_interfaces`: array of interface-name strings (e.g. `["xe-0/0/21", "xe-0/0/0"]`).
- `interface_count`: integer count of impacted interfaces.

**Detector-specific block — exactly one of the following:**

- `flap_timeline` (on `interface_flap` and `interface_error`): a nested object
  `{hostname: {interface: [ {timestamp, signal, status}, ... ]}}` giving the ordered up/down transitions per interface. `signal` is one of the signals above (e.g. `SNMP_LINK`, `OSPF_NBR`); `status` is `"up"` / `"down"`.
- `event_summary` (on `bgp_session`, `policy_deny`, `sdwan_path_quality`, `interface_availability`): a flat object of detector-specific hints. Keys observed in the data include:
  - `upstream_trigger_hint` — free-text pointer to the likely upstream cause (e.g. `"xe-0/0/21 backbone flap on FAIRVIEW-EDG01"`); follow it.
  - `bgp_peer_loss_events`, `vpn_rekey_events` — event counts (bgp_session).
  - `deny_signal`, `zone_hint` — policy-deny context (e.g. `"internet_facing"`).
  - `breached_metric`, `wan_circuit_group_hint` — SD-WAN path-quality context (e.g. `"packet_loss"`, `"Southeast-04"`; the group hint maps to `network_devices.wan_circuit_group`).
  - `change_ref_hint`, `planned` — change/ticket reference and a planned-maintenance flag (e.g. `"CHG-2026-0611"`, `true`); cross-reference against `device_syslogs`.

**Example (`interface_flap`, id `a1f0c8e2-…-000000000001`):**

```json
{
  "detector": "interface_flap",
  "window": {"start": "2026-07-08T06:00:00Z", "end": "2026-07-08T07:47:00Z"},
  "impacted_hostnames": ["FAIRVIEW-EDG01", "stonebridge-edg01"],
  "impacted_interfaces": ["xe-0/0/21", "xe-0/0/0"],
  "host_count": 2,
  "interface_count": 2,
  "SNMP_LINK_impact_score": 4.0, "SNMP_LINK_criticality": "high",
  "OSPF_NBR_impact_score": 3.0, "OSPF_NBR_criticality": "high",
  "BGP_impact_score": 2.0,       "BGP_criticality": "medium",
  "LLDP_NBR_impact_score": 0.0,  "LLDP_NBR_criticality": "low",
  "criticality": "critical",
  "flap_timeline": {
    "FAIRVIEW-EDG01": {
      "xe-0/0/21": [
        {"timestamp": "2026-07-08T07:02:30Z", "signal": "SNMP_LINK", "status": "down"},
        {"timestamp": "2026-07-08T07:02:40Z", "signal": "SNMP_LINK", "status": "up"}
      ]
    }
  }
}
```

**Example (`policy_deny`, id `a1f0c8e2-…-000000000003`) — note `event_summary` instead of `flap_timeline`, and no interface fields:**

```json
{
  "detector": "policy_deny",
  "window": {"start": "2026-07-05T03:00:00Z", "end": "2026-07-05T04:00:00Z"},
  "impacted_hostnames": ["cedarhollow-fw01"],
  "host_count": 1,
  "POLICY_impact_score": 4.0, "POLICY_criticality": "critical",
  "criticality": "critical",
  "event_summary": {"deny_signal": "policy", "zone_hint": "internet_facing"}
}
```

## 2. `network_devices`

Device inventory, plus lightweight topology and WAN-circuit context as plain columns:

| Column | Notes |
|---|---|
| `device_id`, `hostname`, `mgmt_ip` | `hostname` matches (case-sensitively, as-is) what appears in `detected_anomalies.model_output`. |
| `device_type` | `router` \| `switch` \| `firewall` \| `sdwan_edge` |
| `role` | `core_router` \| `core_switch` \| `internet_zone_router` \| `firewall` \| `sdwan_branch_edge` |
| `vendor`, `model`, `os_version`, `install_date`, `status` | standard inventory fields |
| `site_code`, `site_name`, `city`, `state`, `region` | devices sharing a `site_code` are co-located |
| `wan_provider`, `wan_circuit_id`, `wan_circuit_group` | populated for SD-WAN edge devices only. Devices sharing a `wan_circuit_group` are on different circuits within the same upstream provider's infrastructure grouping. |
| `notes` | plain-language description of what this device's key interfaces connect to, in place of a separate topology table. |

## 3. `device_telemetry`

Hourly, per-device, wide.

| Column | Populated for | Notes |
|---|---|---|
| `cpu_utilization_pct`, `memory_utilization_pct`, `temperature_celsius` | all devices | |
| `active_sessions` | firewalls, SD-WAN edges | else `NULL` |
| `bgp_established_peers` | BGP-speaking routers/firewalls | else `NULL` |
| `interfaces_up_ratio` | all devices | 1.0 = all monitored interfaces up |
| `interface_error_count`, `interface_flap_count` | devices with a monitored uplink | see `network_devices.notes` for which interface |
| `policy_deny_count` | firewalls | else `NULL` |
| `latency_ms`, `jitter_ms`, `packet_loss_pct` | SD-WAN edges | else `NULL` |

Covers 2026-07-01 through 2026-08-20 at hourly granularity.

## 4. `device_syslogs`

Free-text device log lines.

| Column | Notes |
|---|---|
| `severity` | `info` \| `warning` \| `error` \| `critical` |
| `message_type` | `interface` \| `routing` \| `bgp` \| `vpn` \| `policy` \| `threat` \| `system` \| `auth` \| `ha` \| `sdwan` \| `bfd` |
| `message` | free text |

This table also contains references to prior tickets/changes, firewall rule names for policy events, and cross-references to related devices by hostname, where applicable.
