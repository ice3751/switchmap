from pathlib import Path

ROOT = Path(__file__).resolve().parent

CSS_ASSETS = [
    ROOT / "inventory" / "static" / "inventory" / "switchmap.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-sfp.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-topology-base.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-ssh.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-alarms.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-users.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-topology.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-backups.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-notifications.css",
    ROOT / "inventory" / "static" / "inventory" / "css" / "switchmap-assets.css",
]


def read_static_css():
    missing = [str(path) for path in CSS_ASSETS if not path.exists()]
    if missing:
        raise AssertionError("missing css assets: " + ", ".join(missing))
    return "\n".join(path.read_text(encoding="utf-8") for path in CSS_ASSETS)

