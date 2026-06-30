import random
import re
import socket
from dataclasses import dataclass
from collections import defaultdict

from django.utils import timezone

from inventory.models import Port, Switch
from inventory.phase79_history import record_port_connection_event, record_port_identity_snapshot

SYS_DESCR = (1, 3, 6, 1, 2, 1, 1, 1, 0)
IF_DESCR = (1, 3, 6, 1, 2, 1, 2, 2, 1, 2)
IF_SPEED = (1, 3, 6, 1, 2, 1, 2, 2, 1, 5)
IF_ADMIN_STATUS = (1, 3, 6, 1, 2, 1, 2, 2, 1, 7)
IF_OPER_STATUS = (1, 3, 6, 1, 2, 1, 2, 2, 1, 8)
IF_NAME = (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 1)
IF_HIGH_SPEED = (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 15)
IF_ALIAS = (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 18)

DOT1D_BASE_PORT_IFINDEX = (1, 3, 6, 1, 2, 1, 17, 1, 4, 1, 2)
DOT1D_TP_FDB_PORT = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 2)
DOT1D_TP_FDB_STATUS = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 3)
IP_NET_TO_MEDIA_PHYS_ADDRESS = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)
IP_NET_TO_MEDIA_NET_ADDRESS = (1, 3, 6, 1, 2, 1, 4, 22, 1, 3)
DOT1Q_PVID = (1, 3, 6, 1, 2, 1, 17, 7, 1, 4, 5, 1, 1)

VM_VLAN = (1, 3, 6, 1, 4, 1, 9, 9, 68, 1, 2, 2, 1, 2)
VM_VOICE_VLAN_ID = (1, 3, 6, 1, 4, 1, 9, 9, 68, 1, 5, 1, 1, 1)

VLAN_TRUNK_PORT_IFINDEX = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 1)
VLAN_TRUNK_PORT_ENABLED = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 4)
VLAN_TRUNK_PORT_NATIVE = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 5)
VLAN_TRUNK_PORT_ENABLED_2K = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 17)
VLAN_TRUNK_PORT_ENABLED_3K = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 18)
VLAN_TRUNK_PORT_ENABLED_4K = (1, 3, 6, 1, 4, 1, 9, 9, 46, 1, 6, 1, 1, 19)

PETH_PSE_PORT_ADMIN_ENABLE = (1, 3, 6, 1, 2, 1, 105, 1, 1, 1, 3)
PETH_PSE_PORT_DETECTION_STATUS = (1, 3, 6, 1, 2, 1, 105, 1, 1, 1, 6)

CDP_CACHE_DEVICE_ID = (1, 3, 6, 1, 4, 1, 9, 9, 23, 1, 2, 1, 1, 6)
CDP_CACHE_DEVICE_PORT = (1, 3, 6, 1, 4, 1, 9, 9, 23, 1, 2, 1, 1, 7)

LLDP_LOC_PORT_ID = (1, 0, 8802, 1, 1, 2, 1, 3, 7, 1, 3)
LLDP_REM_PORT_ID = (1, 0, 8802, 1, 1, 2, 1, 4, 1, 1, 7)
LLDP_REM_PORT_DESC = (1, 0, 8802, 1, 1, 2, 1, 4, 1, 1, 8)
LLDP_REM_SYS_NAME = (1, 0, 8802, 1, 1, 2, 1, 4, 1, 1, 9)

ADMIN_STATUS = {
    1: "up",
    2: "down",
    3: "testing",
}

OPER_STATUS = {
    1: "up",
    2: "down",
    3: "testing",
    4: "unknown",
    5: "dormant",
    6: "notPresent",
    7: "lowerLayerDown",
}


class SnmpError(Exception):
    pass


@dataclass
class SnmpValue:
    tag: int
    value: object
    raw: bytes = b""


class BerReader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read_tlv(self):
        if self.pos >= len(self.data):
            raise SnmpError("Unexpected end of BER data.")

        tag = self.data[self.pos]
        self.pos += 1
        length = self.read_length()
        end = self.pos + length

        if end > len(self.data):
            raise SnmpError("Invalid BER length.")

        value = self.data[self.pos:end]
        self.pos = end
        return tag, value

    def read_length(self):
        if self.pos >= len(self.data):
            raise SnmpError("Missing BER length.")

        first = self.data[self.pos]
        self.pos += 1

        if first < 0x80:
            return first

        count = first & 0x7F
        if count == 0 or count > 4:
            raise SnmpError("Unsupported BER length.")

        if self.pos + count > len(self.data):
            raise SnmpError("Invalid BER length bytes.")

        value = int.from_bytes(self.data[self.pos:self.pos + count], "big")
        self.pos += count
        return value


def encode_length(length):
    if length < 0x80:
        return bytes([length])

    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def tlv(tag, content):
    return bytes([tag]) + encode_length(len(content)) + content


def encode_integer(value):
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw

    return tlv(0x02, raw)


def encode_octet_string(value):
    return tlv(0x04, str(value).encode("utf-8"))


def encode_null():
    return tlv(0x05, b"")


def encode_oid(oid):
    first = oid[0] * 40 + oid[1]
    encoded = bytearray([first])

    for part in oid[2:]:
        chunks = [part & 0x7F]
        part >>= 7
        while part:
            chunks.insert(0, 0x80 | (part & 0x7F))
            part >>= 7
        encoded.extend(chunks)

    return tlv(0x06, bytes(encoded))


def decode_integer(data, signed=True):
    if not data:
        return 0
    return int.from_bytes(data, "big", signed=signed)


def decode_oid(data):
    if not data:
        return tuple()

    first = data[0]
    oid = [first // 40, first % 40]
    value = 0

    for byte in data[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            oid.append(value)
            value = 0

    return tuple(oid)


def decode_value(tag, data):
    if tag == 0x02:
        return decode_integer(data, signed=True)

    if tag == 0x04:
        return data.decode("utf-8", errors="replace").strip("\x00").strip()

    if tag == 0x05:
        return None

    if tag == 0x06:
        return ".".join(str(part) for part in decode_oid(data))

    if tag in (0x40, 0x41, 0x42, 0x43, 0x46, 0x47):
        return decode_integer(data, signed=False)

    if tag in (0x80, 0x81, 0x82):
        return None

    return data.hex()


class SnmpClient:
    def __init__(self, host, community, port=161, timeout=5, retries=1):
        self.host = str(host)
        self.community = str(community)
        self.port = int(port)
        self.timeout = int(timeout)
        self.retries = int(retries)
        self.last_local_address = ""
        self.last_remote_address = f"{self.host}:{self.port}"
        self.last_packet_size = 0

    def get(self, oid):
        return self._request(oid, pdu_tag=0xA0)

    def get_next(self, oid):
        return self._request(oid, pdu_tag=0xA1)

    def walk(self, base_oid, max_steps=10000):
        results = {}
        table = self.walk_indexed(base_oid, max_steps=max_steps)

        for index, value in table.items():
            if len(index) == 1:
                results[index[0]] = value

        return results

    def walk_raw(self, base_oid, max_steps=10000):
        results = {}
        table = self.walk_indexed(base_oid, max_steps=max_steps, raw=True)

        for index, value in table.items():
            if len(index) == 1:
                results[index[0]] = value

        return results

    def walk_indexed(self, base_oid, max_steps=10000, raw=False):
        results = {}
        current_oid = base_oid
        steps = 0

        while True:
            steps += 1
            if steps > max_steps:
                raise SnmpError(f"SNMP walk exceeded {max_steps} steps for {base_oid}")

            next_oid, value = self.get_next(current_oid)

            if not next_oid[:len(base_oid)] == base_oid:
                break

            if value.tag in (0x80, 0x81, 0x82):
                break

            index = next_oid[len(base_oid):]
            results[index] = value.raw if raw else value.value
            current_oid = next_oid

        return results

    def _request(self, oid, pdu_tag):
        request_id = random.randint(1, 2147483647)
        packet = self._build_packet(oid, request_id, pdu_tag)
        self.last_packet_size = len(packet)
        last_error = None

        for _ in range(self.retries + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(self.timeout)
                    sock.sendto(packet, (self.host, self.port))
                    self.last_local_address = f"{sock.getsockname()[0]}:{sock.getsockname()[1]}"
                    response, _ = sock.recvfrom(65535)
                    return self._parse_response(response)
            except OSError as exc:
                last_error = exc

        raise SnmpError(
            f"timed out or unreachable; target={self.host}:{self.port}; "
            f"local={self.last_local_address or '-'}; packet_size={self.last_packet_size}"
        ) from last_error

    def _build_packet(self, oid, request_id, pdu_tag):
        varbind = tlv(
            0x30,
            encode_oid(oid) + encode_null(),
        )
        varbind_list = tlv(0x30, varbind)
        pdu = tlv(
            pdu_tag,
            encode_integer(request_id)
            + encode_integer(0)
            + encode_integer(0)
            + varbind_list,
        )
        return tlv(
            0x30,
            encode_integer(1)
            + encode_octet_string(self.community)
            + pdu,
        )

    def _parse_response(self, response):
        packet_reader = BerReader(response)
        tag, packet = packet_reader.read_tlv()

        if tag != 0x30:
            raise SnmpError("Invalid SNMP packet.")

        reader = BerReader(packet)
        reader.read_tlv()
        reader.read_tlv()

        pdu_tag, pdu_data = reader.read_tlv()
        if pdu_tag != 0xA2:
            raise SnmpError("Invalid SNMP response PDU.")

        pdu_reader = BerReader(pdu_data)
        pdu_reader.read_tlv()

        _, error_status_raw = pdu_reader.read_tlv()
        error_status = decode_integer(error_status_raw)
        pdu_reader.read_tlv()

        if error_status:
            raise SnmpError(f"SNMP error status: {error_status}")

        varbind_list_tag, varbind_list_data = pdu_reader.read_tlv()
        if varbind_list_tag != 0x30:
            raise SnmpError("Invalid SNMP varbind list.")

        list_reader = BerReader(varbind_list_data)
        varbind_tag, varbind_data = list_reader.read_tlv()
        if varbind_tag != 0x30:
            raise SnmpError("Invalid SNMP varbind.")

        varbind_reader = BerReader(varbind_data)
        oid_tag, oid_raw = varbind_reader.read_tlv()
        if oid_tag != 0x06:
            raise SnmpError("Invalid SNMP OID.")

        value_tag, value_raw = varbind_reader.read_tlv()
        oid = decode_oid(oid_raw)
        value = SnmpValue(
            tag=value_tag,
            value=decode_value(value_tag, value_raw),
            raw=value_raw,
        )
        return oid, value


def normalize_interface_name(name):
    name = str(name or "").strip()

    mikrotik_physical_patterns = [
        r"(ether\d+)(?:[-_].*)?$",
        r"(sfp-sfpplus\d+)(?:[-_].*)?$",
    ]
    for pattern in mikrotik_physical_patterns:
        match = re.match(pattern, name, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower()

    replacements = [
        (r"GigabitEthernet", "Gi"),
        (r"TenGigabitEthernet", "Te"),
        (r"FastEthernet", "Fa"),
        (r"FortyGigabitEthernet", "Fo"),
        (r"TwentyFiveGigE", "Twe"),
        (r"TwoGigabitEthernet", "Tw"),
    ]

    for pattern, replacement in replacements:
        name = re.sub(pattern, replacement, name)

    return name


def speed_to_mbps(if_high_speed, if_speed):
    try:
        high_speed = int(if_high_speed or 0)
    except (TypeError, ValueError):
        high_speed = 0

    if high_speed > 0:
        return high_speed

    try:
        speed_bps = int(if_speed or 0)
    except (TypeError, ValueError):
        return None

    if speed_bps <= 0:
        return None

    return max(1, round(speed_bps / 1_000_000))


def status_from_snmp(admin_status, oper_status):
    # PHASE83R4_IFMIB_SAFE_STATUS_MAP
    # IF-MIB ifOperStatus values:
    # 1=up, 2=down, 3=testing, 4=unknown, 5=dormant, 6=notPresent, 7=lowerLayerDown.
    # Values 3/4/5/6/7 are not evidence of a physical/interface fault by themselves.
    if admin_status == 2:
        return Port.Status.DISABLED

    if oper_status == 1:
        return Port.Status.UP

    if oper_status in (2, 3, 4, 5, 6, 7):
        return Port.Status.DOWN

    return Port.Status.DOWN


def format_mac(mac_index):
    if len(mac_index) < 6:
        return ""

    mac_bytes = mac_index[-6:]
    return ":".join(f"{part:02x}" for part in mac_bytes)


def format_mac_value(value):
    if value is None:
        return ""

    if isinstance(value, bytes):
        data = value
    elif isinstance(value, bytearray):
        data = bytes(value)
    elif isinstance(value, str):
        text = value.strip().lower()
        if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", text):
            return text
        hex_text = re.sub(r"[^0-9a-fA-F]", "", value)
        if len(hex_text) == 12:
            return ":".join(hex_text[i:i + 2].lower() for i in range(0, 12, 2))
        return ""
    else:
        try:
            data = bytes(value)
        except Exception:
            return ""

    if len(data) != 6:
        return ""
    if not any(data):
        return ""
    return ":".join(f"{part:02x}" for part in data)


def ipv4_from_index_parts(parts):
    try:
        values = [int(part) for part in parts[-4:]]
    except Exception:
        return ""
    if len(values) != 4 or any(part < 0 or part > 255 for part in values):
        return ""
    return ".".join(str(part) for part in values)


def clean_identity_value(value):
    text = str(value or "").replace("\x00", "").strip()
    return text


def is_meaningful_neighbor(value):
    text = clean_identity_value(value).lower()
    return bool(text and text not in {"-", "unknown", "none", "null"})


PROJECT_NEIGHBOR_IDENTITY_ALIASES = {
    # Project-specific LLDP/MNDP/CDP identities observed from MikroTik/Cisco devices.
    # Values are the Switch.name records currently stored in SwitchMap.
    "switchcorefactory": "CRS354",
    "capxlmanagment": "Cap-Managment",
    "capxlmanagement": "Cap-Managment",
    "capxltolid": "Cap-Tolid",
    "capxledari": "Cap-Edari",
    "rbcoreghazvin": "RB5009",
    "n3kcoresw": "NEXUS",
    "ppstehraniranmall": "RB2011-Iranmall",
}


def normalize_identity_key(value):
    text = clean_identity_value(value).lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace(".winac-co.com", "")
    text = text.replace(".local", "")
    if "." in text:
        text = text.split(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", "", text)


def add_identity_lookup(lookup, key, switch):
    key = normalize_identity_key(key)
    if key and key not in lookup:
        lookup[key] = switch


def build_managed_switch_lookup():
    lookup = {}
    switches = list(Switch.objects.filter(is_active=True).only("name", "management_ip"))
    by_name_key = {}
    for sw in switches:
        for value in (sw.name, str(sw.management_ip or "")):
            add_identity_lookup(lookup, value, sw)
        by_name_key[normalize_identity_key(sw.name)] = sw

    for alias, target_name in PROJECT_NEIGHBOR_IDENTITY_ALIASES.items():
        target = by_name_key.get(normalize_identity_key(target_name))
        if target:
            add_identity_lookup(lookup, alias, target)
    return lookup


def resolve_managed_switch_by_identity(identity, lookup):
    key = normalize_identity_key(identity)
    if not key:
        return None
    if key in lookup:
        return lookup[key]
    # Allow suffixes/serial text such as N3K-Core-SW.winac-co.com(FOC...) to still match a known alias.
    for saved_key, sw in lookup.items():
        if len(saved_key) >= 5 and (key.startswith(saved_key) or saved_key.startswith(key)):
            return sw
    return None


def vlan_bitmap_to_list(raw_bytes, base_vlan=0):
    if not raw_bytes:
        return []

    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode("latin1", errors="ignore")

    vlans = []
    for byte_index, byte in enumerate(raw_bytes):
        for bit_index in range(8):
            if byte & (1 << (7 - bit_index)):
                vlan = base_vlan + (byte_index * 8) + bit_index
                if 1 <= vlan <= 4094:
                    vlans.append(vlan)
    return vlans


def compress_vlan_list(vlans):
    values = sorted(set(int(vlan) for vlan in vlans if vlan))
    if not values:
        return ""

    ranges = []
    start = previous = values[0]

    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue

        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = value

    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ",".join(ranges)


def poe_admin_label(value):
    labels = {
        1: "enabled",
        2: "disabled",
    }
    return labels.get(value, str(value or ""))


def poe_detection_label(value):
    labels = {
        1: "unknown",
        2: "disabled",
        3: "searching",
        4: "delivering power",
        5: "fault",
        6: "test",
        7: "other fault",
    }
    return labels.get(value, str(value or ""))


PHYSICAL_INTERFACE_RE = re.compile(r"^(Gi|Te|Tw|Twe|Fo|Hu)\d+/\d+/\d+$")
ACCESS_INTERFACE_RE = re.compile(r"^Gi\d+/0/\d+$")
TE_UPLINK_INTERFACE_RE = re.compile(r"^Te\d+/1/[1-4]$")
LEGACY_GI_SFP_INTERFACE_RE = re.compile(r"^Gi\d+/1/[1-4]$")


def is_physical_interface(interface_name):
    return bool(PHYSICAL_INTERFACE_RE.match(str(interface_name or "")))


def is_access_panel_interface(interface_name):
    return bool(ACCESS_INTERFACE_RE.match(str(interface_name or "")))


def is_te_uplink_interface(interface_name):
    return bool(TE_UPLINK_INTERFACE_RE.match(str(interface_name or "")))


def is_legacy_gi_sfp_interface(interface_name):
    return bool(LEGACY_GI_SFP_INTERFACE_RE.match(str(interface_name or "")))


def is_uplink_interface(interface_name):
    return is_te_uplink_interface(interface_name)


def is_visible_switchmap_interface(interface_name):
    return is_access_panel_interface(interface_name) or is_uplink_interface(interface_name)


def display_order_for_interface(interface_name, if_index):
    interface_name = str(interface_name or "")
    match = re.search(r"/(\d+)$", interface_name)
    number = int(match.group(1)) if match else int(if_index or 0)

    if is_access_panel_interface(interface_name):
        return number

    if is_te_uplink_interface(interface_name):
        return 1000 + number

    return 2000 + int(if_index or number)


def make_client(switch, retries=1):
    if not switch.snmp_enabled:
        raise SnmpError("SNMP is not enabled for this switch in SwitchMap.")

    if not switch.snmp_community:
        raise SnmpError("SNMP community is empty for this switch.")

    return SnmpClient(
        host=switch.management_ip,
        community=switch.snmp_community,
        port=switch.snmp_port,
        timeout=switch.snmp_timeout,
        retries=retries,
    )


def test_snmp_connection(switch):
    client = make_client(switch, retries=0)
    now = timezone.now()

    try:
        oid, value = client.get(SYS_DESCR)
        switch.snmp_last_poll = now
        switch.snmp_last_error = ""
        switch.save(update_fields=["snmp_last_poll", "snmp_last_error"])
        return {
            "ok": True,
            "message": "SNMP_TEST_OK",
            "target": client.last_remote_address,
            "local": client.last_local_address,
            "oid": ".".join(str(part) for part in oid),
            "value": str(value.value)[:300],
        }
    except Exception as exc:
        switch.snmp_last_poll = now
        switch.snmp_last_error = str(exc)
        switch.save(update_fields=["snmp_last_poll", "snmp_last_error"])
        return {
            "ok": False,
            "message": "SNMP_TEST_FAILED",
            "target": client.last_remote_address,
            "local": client.last_local_address,
            "error": str(exc),
        }


def poll_switch_ports(switch, dry_run=False, show_ignored=False):
    client = make_client(switch, retries=1)
    now = timezone.now()

    try:
        if_descr = client.walk(IF_DESCR)
        if_name = client.walk(IF_NAME)
        if_speed = client.walk(IF_SPEED)
        if_high_speed = client.walk(IF_HIGH_SPEED)
        if_admin = client.walk(IF_ADMIN_STATUS)
        if_oper = client.walk(IF_OPER_STATUS)
        if_alias = client.walk(IF_ALIAS)
        dot1d_base_port = client.walk(DOT1D_BASE_PORT_IFINDEX)
        dot1q_pvid = client.walk(DOT1Q_PVID)
        vm_vlan = client.walk(VM_VLAN)
        vm_voice_vlan = client.walk(VM_VOICE_VLAN_ID)
        trunk_ifindex = client.walk(VLAN_TRUNK_PORT_IFINDEX)
        trunk_native_vlan = client.walk(VLAN_TRUNK_PORT_NATIVE)
        trunk_enabled = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED, raw=True)
        trunk_enabled_2k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_2K, raw=True)
        trunk_enabled_3k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_3K, raw=True)
        trunk_enabled_4k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_4K, raw=True)
        peth_admin = client.walk_indexed(PETH_PSE_PORT_ADMIN_ENABLE)
        peth_detection = client.walk_indexed(PETH_PSE_PORT_DETECTION_STATUS)
    except Exception as exc:
        switch.snmp_last_error = str(exc)
        switch.snmp_last_poll = now
        switch.save(update_fields=["snmp_last_error", "snmp_last_poll"])
        raise SnmpError(str(exc)) from exc

    bridge_port_by_ifindex = {
        int(if_index): int(bridge_port)
        for bridge_port, if_index in dot1d_base_port.items()
    }
    trunk_row_by_ifindex = {
        int(if_index): int(row_index)
        for row_index, if_index in trunk_ifindex.items()
    }

    trunk_vlans_by_ifindex = {}
    for row_index, if_index in trunk_ifindex.items():
        vlans = []
        key = (row_index,)
        vlans.extend(vlan_bitmap_to_list(trunk_enabled.get(key, b""), 0))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_2k.get(key, b""), 1024))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_3k.get(key, b""), 2048))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_4k.get(key, b""), 3072))
        trunk_vlans_by_ifindex[int(if_index)] = compress_vlan_list(vlans)

    poe_by_interface = {}
    for index, admin_value in peth_admin.items():
        if len(index) < 2:
            continue
        member = int(index[0])
        port_number = int(index[1])
        interface_name = f"Gi{member}/0/{port_number}"
        detection_value = peth_detection.get(index)
        poe_by_interface[interface_name] = {
            "enabled": admin_value == 1,
            "admin": poe_admin_label(admin_value),
            "detection": poe_detection_label(detection_value),
        }

    matched_count = 0
    updated_count = 0
    ignored_interfaces = []
    indexes = sorted(set(if_descr) | set(if_name))

    for if_index in indexes:
        raw_name = if_name.get(if_index) or if_descr.get(if_index)
        interface_name = normalize_interface_name(raw_name)

        port = Port.objects.filter(
            switch=switch,
            interface_name=interface_name,
        ).first()

        if not port:
            ignored_interfaces.append(interface_name)
            continue

        matched_count += 1

        admin_value = if_admin.get(if_index)
        oper_value = if_oper.get(if_index)
        alias_value = if_alias.get(if_index, "")
        speed_mbps = speed_to_mbps(
            if_high_speed.get(if_index),
            if_speed.get(if_index),
        )

        new_status = status_from_snmp(admin_value, oper_value)
        bridge_port = bridge_port_by_ifindex.get(int(if_index or 0))
        pvid_value = dot1q_pvid.get(bridge_port) if bridge_port else None
        vm_vlan_value = vm_vlan.get(if_index)
        voice_vlan_value = vm_voice_vlan.get(if_index)
        trunk_row = trunk_row_by_ifindex.get(int(if_index or 0))
        native_vlan_value = trunk_native_vlan.get(trunk_row) if trunk_row else None
        trunk_vlans_value = trunk_vlans_by_ifindex.get(int(if_index or 0), "")
        poe_data = poe_by_interface.get(interface_name, {})

        if trunk_row or is_uplink_interface(interface_name):
            new_port_mode = Port.PortMode.TRUNK
            new_access_vlan = None
            new_native_vlan = int(native_vlan_value) if native_vlan_value else None
        elif vm_vlan_value and int(vm_vlan_value) > 0:
            new_port_mode = Port.PortMode.ACCESS
            new_access_vlan = int(vm_vlan_value)
            new_native_vlan = None
        elif pvid_value:
            new_port_mode = Port.PortMode.ACCESS
            new_access_vlan = int(pvid_value)
            new_native_vlan = None
        else:
            new_port_mode = port.port_mode
            new_access_vlan = port.access_vlan
            new_native_vlan = port.native_vlan

        if dry_run:
            continue

        phase79_old_status = port.status

        port.snmp_if_index = if_index
        port.snmp_raw_name = str(raw_name or "")
        port.snmp_alias = str(alias_value or "")
        port.snmp_admin_status = ADMIN_STATUS.get(admin_value, str(admin_value or ""))
        port.snmp_oper_status = OPER_STATUS.get(oper_value, str(oper_value or ""))
        port.snmp_speed_mbps = speed_mbps
        port.snmp_last_poll = now
        port.status = new_status
        port.port_mode = new_port_mode
        port.access_vlan = new_access_vlan
        port.native_vlan = new_native_vlan

        if voice_vlan_value is not None and int(voice_vlan_value) > 0:
            port.voice_vlan = int(voice_vlan_value)

        if trunk_vlans_value:
            port.trunk_vlans = trunk_vlans_value

        if new_access_vlan:
            port.vlan = new_access_vlan
        elif new_native_vlan:
            port.vlan = new_native_vlan

        if poe_data:
            port.poe_enabled = bool(poe_data.get("enabled"))
            port.poe_admin_status = str(poe_data.get("admin", ""))
            port.poe_detection_status = str(poe_data.get("detection", ""))

        port.save(
            update_fields=[
                "snmp_if_index",
                "snmp_raw_name",
                "snmp_alias",
                "snmp_admin_status",
                "snmp_oper_status",
                "snmp_speed_mbps",
                "snmp_last_poll",
                "status",
                "port_mode",
                "access_vlan",
                "native_vlan",
                "voice_vlan",
                "trunk_vlans",
                "vlan",
                "poe_enabled",
                "poe_admin_status",
                "poe_detection_status",
                "updated_at",
            ]
        )
        try:
            if phase79_old_status != new_status:
                if phase79_old_status == Port.Status.UP and new_status != Port.Status.UP:
                    record_port_connection_event(port, event_type="down", source="snmp_status", observed_at=now, previous_status=phase79_old_status)
                elif new_status == Port.Status.UP and phase79_old_status != Port.Status.UP:
                    record_port_connection_event(port, event_type="up", source="snmp_status", observed_at=now, previous_status=phase79_old_status)
        except Exception:
            pass
        updated_count += 1

    if not dry_run:
        switch.snmp_last_poll = now
        switch.snmp_last_error = ""
        switch.save(update_fields=["snmp_last_poll", "snmp_last_error"])

    return {
        "ok": True,
        "dry_run": dry_run,
        "matched": matched_count,
        "updated": updated_count,
        "ignored": len(ignored_interfaces),
        "ignored_interfaces": ignored_interfaces if show_ignored else [],
        "target": client.last_remote_address,
        "local": client.last_local_address,
    }

def sync_missing_snmp_ports(switch, dry_run=False):
    client = make_client(switch, retries=1)
    now = timezone.now()

    try:
        if_descr = client.walk(IF_DESCR)
        if_name = client.walk(IF_NAME)
        if_speed = client.walk(IF_SPEED)
        if_high_speed = client.walk(IF_HIGH_SPEED)
        if_admin = client.walk(IF_ADMIN_STATUS)
        if_oper = client.walk(IF_OPER_STATUS)
        if_alias = client.walk(IF_ALIAS)
        dot1d_base_port = client.walk(DOT1D_BASE_PORT_IFINDEX)
        dot1q_pvid = client.walk(DOT1Q_PVID)
        vm_vlan = client.walk(VM_VLAN)
        vm_voice_vlan = client.walk(VM_VOICE_VLAN_ID)
        trunk_ifindex = client.walk(VLAN_TRUNK_PORT_IFINDEX)
        trunk_native_vlan = client.walk(VLAN_TRUNK_PORT_NATIVE)
        trunk_enabled = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED, raw=True)
        trunk_enabled_2k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_2K, raw=True)
        trunk_enabled_3k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_3K, raw=True)
        trunk_enabled_4k = client.walk_indexed(VLAN_TRUNK_PORT_ENABLED_4K, raw=True)
        peth_admin = client.walk_indexed(PETH_PSE_PORT_ADMIN_ENABLE)
        peth_detection = client.walk_indexed(PETH_PSE_PORT_DETECTION_STATUS)
    except Exception as exc:
        switch.snmp_last_error = str(exc)
        switch.snmp_last_poll = now
        switch.save(update_fields=["snmp_last_error", "snmp_last_poll"])
        raise SnmpError(str(exc)) from exc

    bridge_port_by_ifindex = {
        int(if_index): int(bridge_port)
        for bridge_port, if_index in dot1d_base_port.items()
    }
    trunk_row_by_ifindex = {
        int(if_index): int(row_index)
        for row_index, if_index in trunk_ifindex.items()
    }
    trunk_vlans_by_ifindex = {}
    for row_index, if_index in trunk_ifindex.items():
        key = (row_index,)
        vlans = []
        vlans.extend(vlan_bitmap_to_list(trunk_enabled.get(key, b""), 0))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_2k.get(key, b""), 1024))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_3k.get(key, b""), 2048))
        vlans.extend(vlan_bitmap_to_list(trunk_enabled_4k.get(key, b""), 3072))
        trunk_vlans_by_ifindex[int(if_index)] = compress_vlan_list(vlans)

    poe_by_interface = {}
    for index, admin_value in peth_admin.items():
        if len(index) < 2:
            continue
        interface_name = f"Gi{int(index[0])}/0/{int(index[1])}"
        detection_value = peth_detection.get(index)
        poe_by_interface[interface_name] = {
            "enabled": admin_value == 1,
            "admin": poe_admin_label(admin_value),
            "detection": poe_detection_label(detection_value),
        }

    existing = set(
        Port.objects.filter(switch=switch).values_list("interface_name", flat=True)
    )

    created_names = []
    existing_names = []
    skipped_names = []
    indexes = sorted(set(if_descr) | set(if_name))

    for if_index in indexes:
        raw_name = if_name.get(if_index) or if_descr.get(if_index)
        interface_name = normalize_interface_name(raw_name)

        if not is_visible_switchmap_interface(interface_name):
            skipped_names.append(interface_name)
            continue

        if interface_name in existing:
            existing_names.append(interface_name)
            continue

        admin_value = if_admin.get(if_index)
        oper_value = if_oper.get(if_index)
        alias_value = if_alias.get(if_index, "")
        speed_mbps = speed_to_mbps(
            if_high_speed.get(if_index),
            if_speed.get(if_index),
        )

        bridge_port = bridge_port_by_ifindex.get(int(if_index or 0))
        pvid_value = dot1q_pvid.get(bridge_port) if bridge_port else None
        vm_vlan_value = vm_vlan.get(if_index)
        voice_vlan_value = vm_voice_vlan.get(if_index)
        trunk_row = trunk_row_by_ifindex.get(int(if_index or 0))
        native_vlan = trunk_native_vlan.get(trunk_row) if trunk_row else None
        trunk_vlans = trunk_vlans_by_ifindex.get(int(if_index or 0), "")
        poe_data = poe_by_interface.get(interface_name, {})

        if trunk_row or is_uplink_interface(interface_name):
            port_mode = Port.PortMode.TRUNK
            access_vlan = None
            native_vlan = int(native_vlan) if native_vlan else None
        else:
            port_mode = Port.PortMode.ACCESS
            access_vlan = int(vm_vlan_value or pvid_value or 0) or None
            native_vlan = None

        if dry_run:
            created_names.append(interface_name)
            continue

        Port.objects.create(
            switch=switch,
            interface_name=interface_name,
            display_order=display_order_for_interface(interface_name, if_index),
            description=str(alias_value or ""),
            device_type=Port.DeviceType.UPLINK if is_uplink_interface(interface_name) else Port.DeviceType.UNKNOWN,
            port_mode=port_mode,
            access_vlan=access_vlan,
            native_vlan=native_vlan,
            voice_vlan=int(voice_vlan_value) if voice_vlan_value and int(voice_vlan_value) > 0 else None,
            trunk_vlans=trunk_vlans,
            vlan=access_vlan or native_vlan,
            status=status_from_snmp(admin_value, oper_value),
            poe_enabled=bool(poe_data.get("enabled")) if poe_data else False,
            poe_admin_status=str(poe_data.get("admin", "")) if poe_data else "",
            poe_detection_status=str(poe_data.get("detection", "")) if poe_data else "",
            snmp_if_index=if_index,
            snmp_raw_name=str(raw_name or ""),
            snmp_alias=str(alias_value or ""),
            snmp_admin_status=ADMIN_STATUS.get(admin_value, str(admin_value or "")),
            snmp_oper_status=OPER_STATUS.get(oper_value, str(oper_value or "")),
            snmp_speed_mbps=speed_mbps,
            snmp_last_poll=now,
        )
        existing.add(interface_name)
        created_names.append(interface_name)

    if not dry_run:
        switch.snmp_last_poll = now
        switch.snmp_last_error = ""
        switch.save(update_fields=["snmp_last_poll", "snmp_last_error"])

    return {
        "ok": True,
        "dry_run": dry_run,
        "created": len(created_names),
        "existing": len(existing_names),
        "skipped": len(skipped_names),
        "created_names": created_names,
        "target": client.last_remote_address,
        "local": client.last_local_address,
    }

def build_ifindex_port_map(switch, client):
    if_name = client.walk(IF_NAME)
    if_descr = client.walk(IF_DESCR)
    ports = list(Port.objects.filter(switch=switch))
    by_ifindex = {}
    by_interface = {port.interface_name: port for port in ports}

    for port in ports:
        if port.snmp_if_index:
            by_ifindex[port.snmp_if_index] = port

    for if_index, raw_name in if_name.items():
        interface_name = normalize_interface_name(raw_name)
        port = by_interface.get(interface_name)
        if port:
            by_ifindex[if_index] = port

    for if_index, raw_name in if_descr.items():
        interface_name = normalize_interface_name(raw_name)
        port = by_interface.get(interface_name)
        if port:
            by_ifindex[if_index] = port

    return by_ifindex, by_interface, if_name, if_descr


def poll_switch_discovery(switch, dry_run=False):
    client = make_client(switch, retries=1)
    now = timezone.now()
    optional_errors = {}

    def optional_walk(label, oid, indexed=False, raw=False, max_steps=10000):
        try:
            if indexed:
                return client.walk_indexed(oid, max_steps=max_steps, raw=raw)
            if raw:
                return client.walk_raw(oid, max_steps=max_steps)
            return client.walk(oid, max_steps=max_steps)
        except Exception as exc:
            optional_errors[label] = str(exc)
            return {}

    try:
        by_ifindex, by_interface, _, _ = build_ifindex_port_map(switch, client)
    except Exception as exc:
        switch.discovery_last_error = str(exc)
        switch.discovery_last_poll = now
        if not dry_run:
            switch.save(update_fields=["discovery_last_error", "discovery_last_poll"])
        raise SnmpError(str(exc)) from exc

    dot1d_base_port = optional_walk("DOT1D_BASE_PORT_IFINDEX", DOT1D_BASE_PORT_IFINDEX)
    dot1d_fdb_port = optional_walk("DOT1D_TP_FDB_PORT", DOT1D_TP_FDB_PORT, indexed=True)
    dot1d_fdb_status = optional_walk("DOT1D_TP_FDB_STATUS", DOT1D_TP_FDB_STATUS, indexed=True)
    arp_mac_raw = optional_walk("IP_NET_TO_MEDIA_PHYS_ADDRESS", IP_NET_TO_MEDIA_PHYS_ADDRESS, indexed=True, raw=True)
    cdp_device_id = optional_walk("CDP_CACHE_DEVICE_ID", CDP_CACHE_DEVICE_ID, indexed=True)
    cdp_device_port = optional_walk("CDP_CACHE_DEVICE_PORT", CDP_CACHE_DEVICE_PORT, indexed=True)
    lldp_loc_port_id = optional_walk("LLDP_LOC_PORT_ID", LLDP_LOC_PORT_ID)
    lldp_rem_sys_name = optional_walk("LLDP_REM_SYS_NAME", LLDP_REM_SYS_NAME, indexed=True)
    lldp_rem_port_id = optional_walk("LLDP_REM_PORT_ID", LLDP_REM_PORT_ID, indexed=True)
    lldp_rem_port_desc = optional_walk("LLDP_REM_PORT_DESC", LLDP_REM_PORT_DESC, indexed=True)

    managed_switch_lookup = build_managed_switch_lookup()

    discovery = defaultdict(lambda: {
        "source": "",
        "device": "",
        "port": "",
        "macs": set(),
        "ips": set(),
        "inventory_ip": "",
        "inventory_match": "",
        "confidence": "none",
    })

    arp_ips_by_mac = defaultdict(set)
    arp_ips_by_ifindex = defaultdict(set)
    for index, raw_mac in arp_mac_raw.items():
        if len(index) < 5:
            continue
        try:
            if_index = int(index[0])
        except Exception:
            continue
        ip_address = ipv4_from_index_parts(index[-4:])
        mac = format_mac_value(raw_mac)
        if not ip_address or not mac:
            continue
        arp_ips_by_mac[mac].add(ip_address)
        arp_ips_by_ifindex[if_index].add(ip_address)

    for mac_index, bridge_port in dot1d_fdb_port.items():
        status = dot1d_fdb_status.get(mac_index)
        if status not in (None, 3):
            continue

        try:
            bridge_port_int = int(bridge_port or 0)
            if_index = int(dot1d_base_port.get(bridge_port_int) or 0)
        except Exception:
            continue

        port = by_ifindex.get(if_index)
        mac = format_mac(mac_index)

        if port and mac:
            current = discovery[port.id]
            current["macs"].add(mac)
            for ip_address in arp_ips_by_mac.get(mac, set()):
                current["ips"].add(ip_address)
            if not current["confidence"] or current["confidence"] == "none":
                current["confidence"] = "fdb"

    # ARP-only fallback: safe only when the interface maps directly to a known port.
    # It does not set a topology neighbor by itself; it only enriches IP/MAC on single-endpoint ports.
    for mac, ip_addresses in arp_ips_by_mac.items():
        # Index-based ARP mapping is handled via arp_ips_by_ifindex below; keep this for MAC/IP lookup only.
        pass

    for if_index, ip_addresses in arp_ips_by_ifindex.items():
        port = by_ifindex.get(if_index)
        if not port:
            continue
        current = discovery[port.id]
        for ip_address in ip_addresses:
            current["ips"].add(ip_address)
        if current["confidence"] == "none":
            current["confidence"] = "arp-ifindex"

    for index, device_id in lldp_rem_sys_name.items():
        if len(index) < 3:
            continue

        local_port_number = index[1]
        local_port_id = lldp_loc_port_id.get(local_port_number, "")
        interface_name = normalize_interface_name(local_port_id)
        port = by_interface.get(interface_name) or by_ifindex.get(local_port_number)

        if not port:
            continue

        remote_port = lldp_rem_port_desc.get(index) or lldp_rem_port_id.get(index) or ""
        current = discovery[port.id]
        if is_meaningful_neighbor(device_id):
            remote_device = clean_identity_value(device_id)
            current["source"] = "LLDP"
            current["device"] = remote_device
            current["port"] = clean_identity_value(remote_port)
            current["confidence"] = "lldp"
            matched_switch = resolve_managed_switch_by_identity(remote_device, managed_switch_lookup)
            if matched_switch:
                current["inventory_ip"] = str(matched_switch.management_ip or "")
                current["inventory_match"] = matched_switch.name

    for index, device_id in cdp_device_id.items():
        if len(index) < 2:
            continue

        if_index = index[0]
        port = by_ifindex.get(if_index)

        if not port:
            continue

        remote_port = cdp_device_port.get(index, "")
        current = discovery[port.id]
        if is_meaningful_neighbor(device_id):
            remote_device = clean_identity_value(device_id)
            current["source"] = "CDP"
            current["device"] = remote_device
            current["port"] = clean_identity_value(remote_port)
            current["confidence"] = "cdp"
            matched_switch = resolve_managed_switch_by_identity(remote_device, managed_switch_lookup)
            if matched_switch:
                current["inventory_ip"] = str(matched_switch.management_ip or "")
                current["inventory_match"] = matched_switch.name

    matched_count = 0
    updated_count = 0
    neighbor_count = 0
    mac_port_count = 0
    arp_entry_count = len(arp_ips_by_mac)
    single_endpoint_count = 0
    skipped_trunk_ip_count = 0
    inventory_match_count = 0
    dryrun_rows = []

    ports = list(Port.objects.filter(switch=switch))

    for port in ports:
        data = discovery.get(port.id, {})
        macs = sorted(set(data.get("macs", set())))
        ips = sorted(set(data.get("ips", set())))
        source = data.get("source", "")
        device = data.get("device", "")
        remote_port = data.get("port", "")
        inventory_ip = data.get("inventory_ip", "")
        inventory_match = data.get("inventory_match", "")
        confidence = data.get("confidence", "none")

        if source or macs or ips:
            matched_count += 1

        if source:
            neighbor_count += 1

        if inventory_match:
            inventory_match_count += 1

        if macs:
            mac_port_count += 1

        single_endpoint = len(macs) == 1 and len(ips) == 1
        should_set_endpoint_identity = single_endpoint and not source
        should_set_neighbor_ip = len(ips) == 1 and (source or single_endpoint)
        if not should_set_neighbor_ip and source and inventory_ip:
            # LLDP/CDP identity matched an existing SwitchMap device. This is safer than picking a random IP from a trunk.
            should_set_neighbor_ip = True
        if single_endpoint:
            single_endpoint_count += 1
        if len(ips) > 1 or len(macs) > 1:
            skipped_trunk_ip_count += 1

        neighbor_ip_value = ips[0] if (should_set_neighbor_ip and len(ips) == 1) else (inventory_ip if should_set_neighbor_ip else None)
        primary_mac_value = macs[0] if single_endpoint else ""

        if dry_run:
            if source or macs or ips:
                dryrun_rows.append({
                    "interface": port.interface_name,
                    "source": source or ("ARP/FDB" if should_set_endpoint_identity else "FDB/ARP" if macs or ips else ""),
                    "device": device or (neighbor_ip_value or ""),
                    "remote_port": remote_port,
                    "neighbor_ip": neighbor_ip_value or "",
                    "inventory_match": inventory_match,
                    "mac_count": len(macs),
                    "ip_count": len(ips),
                    "confidence": confidence + ("+inventory" if inventory_match else ""),
                })
            continue

        update_fields = ["discovery_last_poll", "updated_at"]
        port.discovery_last_poll = now

        # CDP/LLDP are authoritative for topology. ARP/FDB-only single endpoints are searchable identity,
        # not forced switch-to-switch topology unless the port has no better neighbor data.
        port.neighbor_source = source
        port.neighbor_device = device
        port.neighbor_port = remote_port
        port.neighbor_ip = neighbor_ip_value
        update_fields.extend(["neighbor_source", "neighbor_device", "neighbor_port", "neighbor_ip"])

        port.mac_count = min(len(macs), 65535)
        port.mac_addresses = "\n".join(macs[:50])
        update_fields.extend(["mac_count", "mac_addresses"])

        if primary_mac_value and not (port.mac_address or "").strip():
            port.mac_address = primary_mac_value
            update_fields.append("mac_address")

        if neighbor_ip_value and not port.ip_address:
            port.ip_address = neighbor_ip_value
            update_fields.append("ip_address")

        port.save(update_fields=sorted(set(update_fields)))
        try:
            if source or macs or ips:
                record_port_identity_snapshot(port, source="discovery", observed_at=now)
        except Exception:
            pass
        updated_count += 1

    if not dry_run:
        switch.discovery_last_poll = now
        # Optional table failures such as RB5009 FDB_PORT timeout should not mark discovery failed when
        # IF/LLDP/ARP data was still collected successfully.
        switch.discovery_last_error = ""
        switch.save(update_fields=["discovery_last_poll", "discovery_last_error"])

    return {
        "ok": True,
        "dry_run": dry_run,
        "matched": matched_count,
        "updated": updated_count,
        "neighbors": neighbor_count,
        "mac_ports": mac_port_count,
        "arp_entries": arp_entry_count,
        "single_endpoints": single_endpoint_count,
        "skipped_trunk_ip": skipped_trunk_ip_count,
        "inventory_matches": inventory_match_count,
        "optional_errors": optional_errors,
        "dryrun_rows": dryrun_rows[:20],
        "target": client.last_remote_address,
        "local": client.last_local_address,
    }
