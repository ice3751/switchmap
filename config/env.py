import os
from pathlib import Path


def read_env_file(path):
    env_path = Path(path)
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name, default=None):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def bool_env(name, default=False):
    value = env(name, None)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def list_env(name, default=""):
    value = env(name, default)
    if value is None:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]
