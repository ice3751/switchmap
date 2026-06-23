import os
import secrets
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "switchmap.env"

if ENV_FILE.exists():
    print(f"ENV_EXISTS {ENV_FILE}")
    raise SystemExit(0)

hostname = socket.gethostname().strip() or "switchmap"
secret = "swm-" + secrets.token_urlsafe(64)

hosts = ["127.0.0.1", "localhost", hostname]
trusted = [f"http://{hostname}:8000"]

content = f"""# SwitchMap VM production environment.
# Edit SWITCHMAP_ALLOWED_HOSTS after assigning the final VM IP/DNS name.

SWITCHMAP_DEBUG=False
SWITCHMAP_SECRET_KEY={secret}
SWITCHMAP_ALLOWED_HOSTS={','.join(hosts)}
SWITCHMAP_CSRF_TRUSTED_ORIGINS={','.join(trusted)}
SWITCHMAP_SQLITE_PATH=db.sqlite3
SWITCHMAP_SQLITE_BACKUP_DIR=backups/sqlite
SWITCHMAP_SQLITE_BACKUP_RETENTION=30
SWITCHMAP_LOG_DIR=logs
SWITCHMAP_LOG_LEVEL=INFO

SWITCHMAP_WAITRESS_HOST=0.0.0.0
SWITCHMAP_WAITRESS_PORT=8000
SWITCHMAP_WAITRESS_THREADS=8
SWITCHMAP_WAITRESS_URL_SCHEME=http

SWITCHMAP_SECURE_SSL_REDIRECT=False
SWITCHMAP_SESSION_COOKIE_SECURE=False
SWITCHMAP_CSRF_COOKIE_SECURE=False
SWITCHMAP_SECURE_HSTS_SECONDS=0
SWITCHMAP_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SWITCHMAP_SECURE_HSTS_PRELOAD=False
"""

ENV_FILE.write_text(content, encoding="utf-8")
print(f"ENV_CREATED {ENV_FILE}")
print("EDIT_ALLOWED_HOSTS_AFTER_STATIC_IP")
