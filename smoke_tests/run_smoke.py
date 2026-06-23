import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("manifest.json")


PRODUCTION_ENV = {
    "SWITCHMAP_DEBUG": "False",
    "SWITCHMAP_SECRET_KEY": "switchmap-production-smoke-secret-key-with-more-than-fifty-characters",
    "SWITCHMAP_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
    "SWITCHMAP_SECURE_SSL_REDIRECT": "True",
    "SWITCHMAP_SESSION_COOKIE_SECURE": "True",
    "SWITCHMAP_CSRF_COOKIE_SECURE": "True",
    "SWITCHMAP_SECURE_HSTS_SECONDS": "31536000",
    "SWITCHMAP_SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
    "SWITCHMAP_SECURE_HSTS_PRELOAD": "True",
}


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def files_for_category(manifest, category):
    if category == "all":
        files = []
        for key in ("current", "production", "legacy"):
            files.extend(manifest[key])
        return files
    if category not in manifest:
        raise SystemExit(f"Unknown smoke category: {category}")
    return manifest[category]


def env_for_category(category):
    env = os.environ.copy()
    if category == "production":
        env.update(PRODUCTION_ENV)
    return env


def run(category):
    manifest = load_manifest()
    files = files_for_category(manifest, category)
    env = env_for_category(category)
    results = []

    for rel_path in files:
        path = ROOT / rel_path
        if not path.exists():
            results.append(("FAIL", rel_path, "missing file"))
            continue

        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        output_lines = (proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or [""])
        status = "PASS" if proc.returncode == 0 else "FAIL"
        results.append((status, rel_path, output_lines[-1]))

    for status, rel_path, detail in results:
        print(f"{status} {rel_path} | {detail}")

    failed = [item for item in results if item[0] != "PASS"]
    print(f"SUMMARY {len(results) - len(failed)} pass {len(failed)} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "current"
    raise SystemExit(run(category))
