from django import template
from django.urls import NoReverseMatch, reverse
import re

register = template.Library()

_PORT_ORDER_FIELDS = (
    "display_order",
    "sort_order",
    "order",
    "slot",
    "module",
    "port_number",
    "number",
    "if_index",
    "name",
    "interface_name",
    "id",
)

_LABEL_FIELDS = (
    "label",
    "port_label",
    "display_name",
    "name",
    "interface",
    "interface_name",
    "if_name",
    "port_name",
    "number",
    "port_number",
)

_STATUS_FIELDS = (
    "status",
    "oper_status",
    "link_status",
    "admin_status",
    "state",
)

_SNMP_ADMIN_FIELDS = (
    "snmp_admin_status",
    "admin_status",
)

_SNMP_OPER_FIELDS = (
    "snmp_oper_status",
    "oper_status",
    "link_status",
)

_DEVICE_FIELDS = (
    "device_name",
    "device",
    "device_type",
    "connected_device",
    "owner",
    "description",
)

_NEIGHBOR_FIELDS = (
    "neighbor",
    "neighbor_name",
    "lldp_neighbor",
    "cdp_neighbor",
    "remote_device",
    "neighbor_device",
)

_VLAN_FIELDS = (
    "vlan",
    "vlan_id",
    "access_vlan",
    "native_vlan",
)

_IP_FIELDS = (
    "ip",
    "ip_address",
    "management_ip",
)

_MAC_FIELDS = (
    "mac",
    "mac_address",
)

_EMPTY_WORDS = {"", "none", "null", "unknown", "unknow", "not known", "n/a", "na", "-", "--"}


def _field_names(model):
    try:
        return {field.name for field in model._meta.get_fields() if hasattr(field, "name")}
    except Exception:
        return set()


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    if text.lower() in _EMPTY_WORDS:
        return ""
    return text


def _first_attr(obj, names, default=""):
    for name in names:
        try:
            if not hasattr(obj, name):
                continue
            value = getattr(obj, name)
            if callable(value):
                continue
            value = _clean(value)
            if value != "":
                return value
        except Exception:
            continue
    return default


def _name_list(names):
    if isinstance(names, str):
        return [name.strip() for name in names.split(",") if name.strip()]
    return list(names or [])


@register.simple_tag
def object_first(obj, names, default=""):
    return _first_attr(obj, _name_list(names), default)


def _has_bool(obj, names):
    for name in names:
        try:
            if hasattr(obj, name) and bool(getattr(obj, name)):
                return True
        except Exception:
            continue
    return False


def _find_port_manager(switch):
    try:
        rels = switch._meta.get_fields()
    except Exception:
        return None

    candidates = []
    for rel in rels:
        try:
            if not getattr(rel, "one_to_many", False):
                continue
            accessor = rel.get_accessor_name()
            related_model = rel.related_model
            model_name = related_model.__name__.lower()
            fields = _field_names(related_model)
            score = 0
            if "port" in model_name:
                score += 5
            if {"number", "port_number", "name", "status", "interface_name"} & fields:
                score += 3
            if {"switch", "switch_id"} & fields:
                score += 2
            if score:
                candidates.append((score, accessor, related_model))
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda item: item[0])
    try:
        return getattr(switch, candidates[0][1])
    except Exception:
        return None


@register.simple_tag
def switch_ports(switch):
    cached = getattr(switch, "_dashboard_ports_cache", None)
    if cached is not None:
        return cached

    manager = _find_port_manager(switch)
    if manager is None:
        setattr(switch, "_dashboard_ports_cache", [])
        return []

    try:
        qs = manager.all()
        names = _field_names(qs.model)
        order_fields = [name for name in _PORT_ORDER_FIELDS if name in names]
        if order_fields:
            qs = qs.order_by(*order_fields)
        ports = list(qs)
    except Exception:
        ports = []

    setattr(switch, "_dashboard_ports_cache", ports)
    return ports


def _is_auto_visual_placeholder(port):
    desc = str(_first_attr(port, ("description", "desc", "notes", "comment"), "")).strip().lower()
    if "auto visual placeholder" not in desc:
        return False

    # If SNMP/Discovery later fills real data, stop treating it as placeholder.
    real_fields = (
        "snmp_last_poll", "snmp_oper_status", "snmp_admin_status",
        "neighbor_device", "neighbor_port", "connected_device", "owner",
        "ip_address", "mac_address", "vlan", "access_vlan", "native_vlan",
    )
    for name in real_fields:
        try:
            value = getattr(port, name, None)
        except Exception:
            value = None
        if value not in (None, "", 0):
            return False
    return True


def _state_from_text(text):
    text = str(text or "").strip().lower()
    if any(word in text for word in ("err", "error", "fault", "problem")):
        return "error"
    if any(word in text for word in ("disable", "disabled", "shutdown", "admin-down", "administratively down")):
        return "disabled"
    if any(word in text for word in ("up", "active", "connected", "ok", "online", "running", "link-ok")):
        return "up"
    if any(word in text for word in ("down", "inactive", "disconnect", "notconnect", "offline", "lowerlayerdown", "no-link")):
        return "down"
    return ""


def _state(port):
    if _is_auto_visual_placeholder(port):
        return "unknown"

    if _has_bool(port, ("is_disabled", "disabled")):
        return "disabled"

    admin_state = _state_from_text(_first_attr(port, _SNMP_ADMIN_FIELDS, ""))
    oper_state = _state_from_text(_first_attr(port, _SNMP_OPER_FIELDS, ""))
    if admin_state == "disabled":
        return "disabled"
    if oper_state:
        return oper_state

    enabled = _first_attr(port, ("enabled", "is_enabled"), "")
    if enabled is False or str(enabled).lower() == "false":
        return "disabled"

    connected = _first_attr(port, ("connected", "is_connected", "is_active", "active"), "")
    if connected is True or str(connected).lower() == "true":
        return "up"

    raw = _first_attr(port, _STATUS_FIELDS, "")
    state = _state_from_text(raw)
    if state:
        return state

    return "unknown"


def _is_trunk(port):
    if _is_auto_visual_placeholder(port):
        return False
    if _has_bool(port, ("is_trunk", "trunk")):
        return True
    text = str(_first_attr(port, ("mode", "port_mode", "switchport_mode", "type"), "")).lower()
    return "trunk" in text


def _is_uplink(port):
    if _has_bool(port, ("is_uplink", "uplink")):
        return True
    text = " ".join(
        str(_first_attr(port, names, ""))
        for names in ((_LABEL_FIELDS), (_DEVICE_FIELDS), (_NEIGHBOR_FIELDS), ("description", "notes", "comment"))
    ).lower()
    return "uplink" in text or "up-link" in text


def _label_text(port):
    return str(port_label(port)).strip().replace(" ", "")


def _is_front_copper(port):
    label = _label_text(port).lower()
    return bool(re.match(r"^(gi|gigabitethernet|fa|fastethernet|eth|ethernet)?1/0/([1-9]|[1-3][0-9]|4[0-8])$", label))


def _is_module_uplink(port):
    label = _label_text(port).lower()
    return bool(re.match(r"^(te|ten|tengigabitethernet)1/1/[1-9][0-9]*$", label))


@register.simple_tag
def switch_port_groups(switch):
    ports = switch_ports(switch)
    copper = []
    uplinks = []

    for port in ports:
        if _is_module_uplink(port):
            uplinks.append(port)
        elif _is_front_copper(port):
            copper.append(port)

    return {"copper": copper, "uplink": uplinks}


@register.simple_tag
def switch_port_summary(switch):
    groups = switch_port_groups(switch)
    visible_ports = list(groups["copper"]) + list(groups["uplink"])
    summary = {"total": len(visible_ports), "up": 0, "down": 0, "disabled": 0, "error": 0, "trunk": 0, "uplink": len(groups["uplink"])}

    for port in visible_ports:
        state = _state(port)
        summary[state] = summary.get(state, 0) + 1
        if _is_trunk(port):
            summary["trunk"] += 1

    return summary


@register.filter
def port_css_class(port):
    classes = ["port-" + _state(port)]
    if _is_trunk(port):
        classes.append("port-trunk")
    if _is_module_uplink(port) or _is_uplink(port):
        classes.append("port-uplink")
    return " ".join(classes)


@register.filter
def port_label(port):
    value = _first_attr(port, _LABEL_FIELDS, "")
    return value or "?"


@register.filter
def port_short_label(port):
    text = str(port_label(port)).strip()
    text = text.replace("TenGigabitEthernet", "Te")
    text = text.replace("GigabitEthernet", "Gi")
    text = text.replace("FastEthernet", "Fa")
    text = text.replace("Ethernet", "Eth")
    text = text.replace(" ", "")

    lower = text.lower()

    mikrotik_ether = re.match(r"^(?:ether|eth|er)(\d+)$", lower)
    if mikrotik_ether:
        return mikrotik_ether.group(1)

    mikrotik_sfp = re.match(r"^(?:sfp-sfpplus|sfpplus|sfp\+|sfp)(\d+)$", lower)
    if mikrotik_sfp:
        return f"SFP{mikrotik_sfp.group(1)}"

    mikrotik_qsfp = re.match(r"^qsfp(?:plus)?(\d+)(?:[-/](\d+))?$", lower)
    if mikrotik_qsfp:
        suffix = mikrotik_qsfp.group(2) or ""
        return f"Q{mikrotik_qsfp.group(1)}{('-' + suffix) if suffix else ''}"

    wlan = re.match(r"^wlan(\d+)$", lower)
    if wlan:
        return f"WiFi{wlan.group(1)}"

    match = re.match(r"^(Gi|Fa|Te|Eth)(.+)$", text, re.IGNORECASE)
    if match:
        return match.group(2)
    return text


@register.filter
def port_device(port):
    value = _first_attr(port, _DEVICE_FIELDS, "")
    if value == "":
        value = _first_attr(port, _NEIGHBOR_FIELDS, "")
    if str(value).strip().lower() in _EMPTY_WORDS:
        return ""
    return value


@register.filter
def port_subtitle(port):
    if _is_module_uplink(port) or _is_uplink(port):
        return "uplink"
    if _is_trunk(port):
        return "trunk"
    device = port_device(port)
    if device:
        return device
    return ""


@register.filter
def port_title(port):
    parts = []
    label = port_label(port)
    if label:
        parts.append(f"Port: {label}")

    parts.append(f"Status: {_state(port)}")

    vlan = _first_attr(port, _VLAN_FIELDS, "")
    if vlan:
        parts.append(f"VLAN: {vlan}")

    device = port_device(port)
    if device:
        parts.append(f"Device: {device}")

    ip = _first_attr(port, _IP_FIELDS, "")
    if ip:
        parts.append(f"IP: {ip}")

    mac = _first_attr(port, _MAC_FIELDS, "")
    if mac:
        parts.append(f"MAC: {mac}")

    return " | ".join(parts)


@register.filter
def model_badge(value):
    text = str(value or "").strip()
    if not text:
        return "3850"
    lower = text.lower()
    if "hap ax" in lower or "ax3" in lower:
        return "hAP ax"
    if "cap" in lower and "cap" == lower[:3]:
        return "cAP"
    if "hex" in lower:
        return "hEX S" if "s" in lower else "hEX"
    found = re.findall(r"\b(2960x|2960-x|2960|3560|3650|3750|3850|9300|9500|crs\d+|rb\d+|nexus\s*\d+)\b", text, re.IGNORECASE)
    if found:
        item = found[-1].upper().replace(" ", "")
        item = item.replace("2960X", "2960X")
        return item
    if len(text) > 10:
        return text[:10]
    return text


@register.simple_tag
def port_edit_url(port):
    pk = getattr(port, "pk", None) or getattr(port, "id", None)
    if not pk:
        return "#"

    for name in ("port_edit", "edit_port", "inventory:port_edit", "inventory:edit_port"):
        try:
            return reverse(name, args=[pk])
        except NoReverseMatch:
            continue
        except Exception:
            continue
    return f"/port/{pk}/edit/"


@register.filter
def port_pk(port):
    return getattr(port, "pk", None) or getattr(port, "id", "") or ""


@register.filter
def port_state_label(port):
    state = _state(port)
    return {"up": "فعال", "down": "قطع", "disabled": "غیرفعال", "error": "خطا"}.get(state, state)


@register.filter
def port_mode(port):
    if _is_trunk(port):
        return "Trunk"
    return _first_attr(port, ("mode", "port_mode", "switchport_mode", "type"), "Access") or "Access"


@register.filter
def port_vlan(port):
    return _first_attr(port, _VLAN_FIELDS, "-") or "-"


@register.filter
def port_neighbor(port):
    return _first_attr(port, _NEIGHBOR_FIELDS, "-") or "-"


@register.filter
def port_ip(port):
    return _first_attr(port, _IP_FIELDS, "-") or "-"


@register.filter
def port_mac(port):
    return _first_attr(port, _MAC_FIELDS, "-") or "-"


@register.filter
def port_description(port):
    return _first_attr(port, ("description", "desc", "notes", "comment"), "-") or "-"


@register.filter
def port_poe(port):
    value = _first_attr(port, ("poe", "poe_status", "is_poe", "poe_enabled"), "-")
    if value is True:
        return "فعال"
    if value is False:
        return "غیرفعال"
    return value or "-"


@register.filter
def port_mac_count(port):
    return _first_attr(port, ("mac_count", "learned_mac_count", "macs_count", "client_count"), "0") or "0"

@register.filter
def svg_copper_x(index):
    try:
        idx = int(index)
    except Exception:
        idx = 0
    port_w = 25
    gap = 7
    group_gap = 18
    group = idx // 6
    offset = idx % 6
    return 214 + group * (6 * port_w + 5 * gap + group_gap) + offset * (port_w + gap)


@register.filter
def svg_te_x(index):
    try:
        idx = int(index)
    except Exception:
        idx = 0
    return 1050 + (idx % 2) * 48


@register.filter
def svg_te_y(index):
    try:
        idx = int(index)
    except Exception:
        idx = 0
    return 62 + (idx // 2) * 30


def _chunk(items, size):
    size = max(int(size or 1), 1)
    return [items[index:index + size] for index in range(0, len(items), size)]


def _model_text(switch):
    return f"{getattr(switch, 'name', '')} {getattr(switch, 'model', '')} {getattr(switch, 'device_family', '')}".lower()


@register.simple_tag
def dynamic_device_visual_context(switch, map_mode="dashboard"):
    ports = switch_ports(switch)
    text = _model_text(switch)
    family = getattr(switch, "device_family", "") or ""
    vendor = getattr(switch, "vendor", "") or ""

    def port_label_lower(port):
        return str(port_label(port)).strip().lower().replace(" ", "")

    def is_fiber(port):
        label = port_label_lower(port)
        return label.startswith(("sfp", "qsfp", "xq", "combo"))

    def is_wireless(port):
        label = port_label_lower(port)
        return label.startswith(("wlan", "wifi", "radio"))

    def natural_key(port):
        label = port_label_lower(port)
        nums = [int(x) for x in re.findall(r"\d+", label)]
        prefix = re.sub(r"\d+", "", label)
        return (prefix, nums, getattr(port, "display_order", 0) or 0, label)

    ports = sorted(ports, key=natural_key)
    copper_ports = [port for port in ports if not is_fiber(port) and not is_wireless(port)]
    fiber_ports = [port for port in ports if is_fiber(port)]
    wireless_ports = [port for port in ports if is_wireless(port)]

    def chunks(items, size):
        return _chunk(items, size)

    def odd_even_rows(items):
        if len(items) > 12:
            return [items[0::2], items[1::2]]
        if len(items) > 6:
            half = (len(items) + 1) // 2
            return [items[:half], items[half:]]
        return [items]

    def compact_rows(items):
        if len(items) <= 6:
            return [items]
        if len(items) <= 12:
            half = (len(items) + 1) // 2
            return [items[:half], items[half:]]
        return chunks(items, 12)

    context = {
        "layout_key": "generic",
        "title": getattr(switch, "model", "") or getattr(switch, "name", "Device"),
        "subtitle": "Generic network device",
        "ports": ports,
        "port_rows": chunks(ports, 12 if map_mode == "dashboard" else 16),
        "uplink_ports": [],
        "wireless_ports": [],
        "status_chips": [],
        "map_mode": map_mode,
        "brand": str(getattr(switch, "vendor", "") or "Network").title(),
        "badge": model_badge(getattr(switch, "model", "") or getattr(switch, "name", "")),
        "face_min_width": 720,
        "port_width": 34,
        "port_height": 30,
        "fiber_width": 58,
        "bay_min_width": 360,
        "side_width": 112,
    }

    if vendor == "mikrotik":
        context.update({
            "layout_key": "mikrotik-router",
            "brand": "MikroTik",
            "subtitle": "RouterOS device",
            "port_rows": compact_rows(copper_ports),
            "uplink_ports": fiber_ports,
            "wireless_ports": wireless_ports,
            "face_min_width": 700,
            "bay_min_width": 300,
            "side_width": 104,
            "port_width": 34,
            "port_height": 30,
            "fiber_width": 58,
        })

        if "crs354" in text or family == "mikrotik_switch":
            context.update({
                "layout_key": "mikrotik-crs354",
                "subtitle": "Core switch / server aggregation",
                "port_rows": odd_even_rows(copper_ports),
                "uplink_ports": fiber_ports,
                "face_min_width": 1030 if map_mode == "dashboard" else 1140,
                "bay_min_width": 780 if map_mode == "dashboard" else 860,
                "side_width": 104,
                "port_width": 26 if map_mode == "dashboard" else 28,
                "port_height": 25 if map_mode == "dashboard" else 27,
                "fiber_width": 54,
            })
        elif "rb5009" in text:
            context.update({
                "layout_key": "mikrotik-rb5009",
                "subtitle": "Core router",
                "port_rows": [copper_ports[:8]],
                "uplink_ports": fiber_ports or copper_ports[8:],
                "face_min_width": 690,
                "bay_min_width": 330,
                "side_width": 100,
                "port_width": 36,
                "port_height": 32,
                "fiber_width": 62,
            })
        elif "rb2011" in text:
            context.update({
                "layout_key": "mikrotik-rb2011",
                "subtitle": "Remote office router",
                "port_rows": compact_rows(copper_ports),
                "uplink_ports": fiber_ports,
                "face_min_width": 680,
                "bay_min_width": 330,
            })
        elif "hex" in text:
            context.update({
                "layout_key": "mikrotik-hex",
                "subtitle": "Edge router",
                "port_rows": [copper_ports],
                "uplink_ports": fiber_ports,
                "face_min_width": 640,
                "bay_min_width": 280,
            })
        elif "ax3" in text or "hap" in text:
            context.update({
                "layout_key": "mikrotik-ax3",
                "subtitle": "Remote office router / WiFi",
                "port_rows": [copper_ports],
                "uplink_ports": fiber_ports,
                "wireless_ports": wireless_ports,
                "status_chips": ["WiFi 2.4G", "WiFi 5G"],
                "face_min_width": 640,
                "bay_min_width": 280,
            })
        elif family == "mikrotik_ap" or "cap" in text:
            context.update({
                "layout_key": "mikrotik-cap",
                "subtitle": "Access Point",
                "port_rows": [copper_ports],
                "uplink_ports": fiber_ports,
                "wireless_ports": wireless_ports,
                "status_chips": ["CAP", "Wireless"],
                "face_min_width": 560,
                "bay_min_width": 200,
                "side_width": 96,
                "port_width": 42,
                "port_height": 34,
            })
        elif "chr" in text or "vps" in text:
            context.update({
                "layout_key": "mikrotik-chr",
                "subtitle": "Cloud Router / VPS",
                "port_rows": compact_rows(copper_ports),
                "uplink_ports": fiber_ports,
                "status_chips": ["Cloud", "VPN"],
                "face_min_width": 520,
                "bay_min_width": 160,
            })

    elif "nexus" in text or family == "cisco_nexus":
        context["layout_key"] = "cisco-nexus"
        context["subtitle"] = "Cisco Nexus"
    elif "3850" in text or family == "cisco_3850":
        context["layout_key"] = "cisco-3850"
        context["subtitle"] = "Cisco Catalyst 3850"
    elif ports:
        context["layout_key"] = "generic-switch"
        context["subtitle"] = "Dynamic generic switch"

    return context
