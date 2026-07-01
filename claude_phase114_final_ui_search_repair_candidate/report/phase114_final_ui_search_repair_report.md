# SwitchMap — Phase114 Final UI / Search Repair

## Exact problem summary

The lower **Current Connected Device** card was already classified correctly by
the server-side display policy, but the upper **Modal / Detail** fields and the
port-button **data attributes** were still populated from *raw* legacy port
fields (`connected_device`, `ip_address`, `mac_address`, `neighbor_source`).
As a result an aggregate/behind-AP/behind-trunk port could show a raw gateway
IP or a single "Multi-MAC / Network Device" value up top while the lower card
correctly said "Behind AP / Multi-MAC" or "Aggregate behind link".

Separately, Dashboard **Quick Search** (`input[data-switch-search]`) was being
hijacked by the endpoint search bridge, which injected ~90 endpoint rows into
the dashboard dropdown for an infrastructure IP such as `172.16.25.204`.
Dashboard Quick Search must stay switch/port-oriented.

The fix is one **deterministic visual-field policy** used by every visual
consumer, plus **search isolation** so the endpoint bridge only runs on the
endpoint UI.

## Exact render path — lower "Current Connected Device" card

`inventory/views.py`
`_phase79_effective_last_connection_payload(port)` →
`_phase79_current_connection_payload(port)` /
`_phase79_history_payload(history)` →
`classify_port_connection_display(evidence)`
(`inventory/endpoint_display_policy.py`). This path was already correct and is
**unchanged**.

## Exact render path — upper Modal / Detail fields

`_port_payload(port)` builds `port.device / ip_address / mac_address /
neighbor / neighbor_source`. `switchmap.js fillModal()/fillDetailPanel()` write
`d.device / d.ipAddress / …` into `[data-field=*]` / `[data-detail=*]`, then
`switchmap-phase79-lc-override.js updatePanelFields()` re-writes the same fields
from `/port/<id>/payload/`. Because the payload previously carried **raw**
values, the upper fields reverted to raw even though `switchmap.js`
`phase114r2ApplyVisualFields()` tried to correct them.

**Repair:** `_port_payload()` now derives the top-level visual fields from
`port_visual_display_fields(port)` (new pure helper in
`endpoint_display_policy.py`). Both JS consumers therefore write classified
values, and the raw overwrite path is closed at the source.

## Exact render path — port button data attributes

- `generic_port_button.html` / `cisco_3850_svg.html`: `data-device / data-ip-address /
  data-mac-address` already used the `port_device / port_ip / port_mac` filters;
  `data-neighbor-source` was raw. The filters (`switchmap_extras.py`) now delegate
  to the visual policy, and `data-neighbor-source` uses the new
  `port_neighbor_source` filter.
- `nexus_svg.html`: used **raw** `port.connected_device / port.ip_address /
  port.mac_address / port.neighbor_source`. It now `{% load switchmap_extras %}`
  and uses `port|port_device / port|port_ip / port|port_mac /
  port|port_neighbor_source`, and adds `data-device`.

## Exact render path — `switchmap-phase79-lc-override.js` overwrite

`applyPayloadToButton(button, port)` copies payload → button dataset;
`updatePanelFields(root, attrName, port)` copies payload → modal/detail fields.
These now receive the classified payload (visual policy). `payloadValue()` also
prefers the payload's `neighbor` (policy value) instead of recomputing from raw
`neighbor_device/neighbor_port`.

## Exact render path — dashboard quick search

`switchmap.js setupSearch()` binds `input[data-switch-search]` and filters
`[data-switch-card]` / `[data-sm-port-button]` using `data-search` (card) and
`data-search-code` (port). This remains the **only** dashboard search owner.
`data-search-code` (all three port templates) and card `data-search` now include
neighbor/visual terms (via `port_search_terms`) so infrastructure IPs such as
`172.16.25.204` remain findable without exposing them as direct device IPs.

## Exact render path — endpoint bridge

`endpoint_search_bridge_r8_5_4.js` previously bound any dashboard-like input
(including `data-switch-search`) via `isLikelyDashboardSearchInput()`. It now:
- returns early (`start()`) unless `isEndpointPage()` is true
  (`[data-phase112r8-3-endpoint-search]`, `form[data-endpoint-search]`,
  `input[data-endpoint-search-input]`, or a `/endpoints` path);
- `isEndpointSearchInput()` explicitly **excludes** `[data-switch-search]` and
  binds only endpoint-specific inputs.

## Exact render path — switch detail and poll buttons

`switch_detail(request, switch_id)` renders the device visual includes
(generic/cisco/nexus) and the port modal/detail. The Poll / Discovery / SNMP /
Sync forms resolve via `switch_snmp_test`, `switch_poll_now`,
`switch_discovery_now`, `switch_sync_snmp_ports`, and `port_payload_json`; all
reverse cleanly (verified). No view logic for these actions was changed.

## Why Phase114 passed but UI stayed wrong

Phase114 fixed the **lower** card (server classification) but left
`_port_payload` and the template filters emitting raw values, so the **upper**
fields still showed raw data.

## Why Phase114R2 verify passed but UI stayed wrong

Phase114R2 added `phase114r2ApplyVisualFields()` in `switchmap.js`, but
`switchmap-phase79-lc-override.js` loads **after** it and its
`updatePanelFields()` re-wrote the raw payload values on top of the R2
correction. Marker-only verification did not catch the runtime overwrite.

## Why the final UI/Search package broke Search / Switch pages

The prior package added JS guards that fought the override and broadened the
endpoint bridge, producing 0-result search, `/switch/7/` 500s, and
`discovery-now` timeouts. This repair instead fixes the **single source**
(`_port_payload` + the display policy) and makes the bridge inert on the
dashboard, so no JS layer competes and the server paths are untouched.

## Files changed

1. `inventory/endpoint_display_policy.py` — add `NON_DIRECT_CLASSIFICATIONS`,
   `_inferred_fallback`, and `port_visual_display_fields()`.
2. `inventory/views.py` — `_port_payload()` uses the visual policy; import it;
   `VISIBLE_PORT_PREFETCH` `select_related("switch")` to avoid N+1.
3. `inventory/templatetags/switchmap_extras.py` — `port_device/port_ip/port_mac/
   port_neighbor/port_title` use the policy; add `port_neighbor_source`,
   `port_search_terms`, memoized `_visual_fields`.
4. `inventory/templates/inventory/includes/generic_port_button.html` — visual
   `data-neighbor-source`, enriched `data-search-code`.
5. `inventory/templates/inventory/includes/cisco_3850_svg.html` — same.
6. `inventory/templates/inventory/includes/nexus_svg.html` — `{% load %}`, visual
   filters for device/ip/mac/neighbor-source, add `data-device`, enriched search.
7. `inventory/templates/inventory/includes/dashboard_device_browser.html` — add
   `port.ip_address` and `port_search_terms` to card `data-search`.
8. `inventory/templates/inventory/base.html` — cache-bust the three scripts.
9. `inventory/static/inventory/switchmap-phase79-lc-override.js` — `payloadValue`
   prefers policy `neighbor`; document the closed raw overwrite path.
10. `inventory/static/inventory/js/endpoint_search_bridge_r8_5_4.js` — endpoint-only
    activation; never bind `data-switch-search`.
- Production mirrors (copied by apply if `staticfiles\` exists):
  `staticfiles/inventory/switchmap-phase79-lc-override.js`,
  `staticfiles/inventory/js/endpoint_search_bridge_r8_5_4.js`.

## Files intentionally not changed

`switchmap.js` (its Phase114R2 logic is already correct once payload is
classified), models, migrations, SNMP/SSH/discovery, scheduled tasks, alarms,
SFP, topology, backup/restore, roles, dashboard card layout, SVG geometry, port
dimensions, and CSS.

## Safety constraints

Pure, read-only display policy — no DB write, no SNMP/SSH/discovery, no network,
no model mutation, no request/session dependence. Raw evidence remains only in
`last_connection.raw_evidence` / debug output.

## Apply command

    C:\SwitchMap\claude_phase114_final_ui_search_repair_candidate\scripts\00_apply_phase114_final_ui_search_repair.cmd

## Verify command

    C:\SwitchMap\claude_phase114_final_ui_search_repair_candidate\scripts\01_verify_phase114_final_ui_search_repair.cmd

## Rollback command

    C:\SwitchMap\claude_phase114_final_ui_search_repair_candidate\scripts\99_rollback_phase114_final_ui_search_repair.cmd

## Expected target outputs

**Cap-Managment / ether1** — classification `behind_ap`, direct `false`;
`device = Behind AP / Multi-MAC (N)`; `ip = -`; `mac = -`; raw `172.16.25.1`
only in `raw_evidence`.

**CRS354 / ether47** — classification `physical_neighbor`, direct `true`;
`device / neighbor = CAP-XL-Managment / Bridge/ether1`; `ip = 172.16.25.204`;
`neighbor_source = LLDP`.

**NEXUS / Ethernet1/40** — classification `physical_neighbor_conflict`, direct
`false`; `device = Network neighbor evidence / Aggregate behind link (N MACs)`;
`ip = -`; `mac = -`; `neighbor = CAP-XL-Managment / Bridge/ether1`;
`neighbor_source = CDP / aggregate conflict`; raw `172.16.25.204` only in
`raw_evidence` / search terms.

**Dashboard search `172.16.25.204`** — switch/port results (not 0, not an
endpoint-row dump); the endpoint bridge does not touch the dashboard input.

Verified end-to-end against a seeded DB: `OVERALL: PASS (25 passed, 0 failed,
0 skipped)`.

## Remaining risks

- Production serves static JS from `staticfiles\` via WhiteNoise; the apply
  script updates those copies only if `staticfiles\` exists (no collectstatic).
  If a site serves static differently, run its normal static refresh.
- AP detection relies on switch `device_role/device_family` or AP-like port
  text; a mislabelled AP switch would fall back to gateway/aggregate wording
  (still non-raw, still safe).

---

NO_LIVE_CHANGE_DONE=True
DB_MUTATION=NO
SERVICE_RESTART=NO
MIGRATION_WRITE=NO
RESTORE_ENABLE_CHANGE=NO
SSH_EXECUTION=NO
SNMP_EXECUTION=NO
DISCOVERY_EXECUTION=NO
REPORT_ONLY_AND_CANDIDATE_FILES=YES
