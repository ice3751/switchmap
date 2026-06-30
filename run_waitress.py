import os
from pathlib import Path

from config.env import env, read_env_file

BASE_DIR = Path(__file__).resolve().parent
read_env_file(BASE_DIR / "switchmap.env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402
from waitress import serve  # noqa: E402


def _int_env(name, default):
    try:
        return int(env(name, str(default)))
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    host = env("SWITCHMAP_WAITRESS_HOST", "0.0.0.0")
    port = _int_env("SWITCHMAP_WAITRESS_PORT", 8000)
    threads = _int_env("SWITCHMAP_WAITRESS_THREADS", 8)
    url_scheme = env("SWITCHMAP_WAITRESS_URL_SCHEME", "http")

    serve(
        application,
        host=host,
        port=port,
        threads=threads,
        url_scheme=url_scheme,
        clear_untrusted_proxy_headers=True,
    )
