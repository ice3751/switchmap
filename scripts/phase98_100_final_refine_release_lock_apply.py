from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.dont_write_bytecode = True

PHASE = "PHASE98_100"
ROOT = Path(r"C:\SwitchMap")
if not ROOT.exists():
    ROOT = Path.cwd()
ROOT = ROOT.resolve()
PAYLOAD = ROOT / "payload_phase98_100_final_refine_release_lock"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = LOG_DIR / f"phase98_100_final_refine_release_lock_apply_{STAMP}.json"
REPORT_TXT = LOG_DIR / f"phase98_100_final_refine_release_lock_apply_{STAMP}.txt"
BACKUP_ROOT = ROOT / "backups" / f"phase98_100_final_refine_release_lock_{STAMP}"
BACKUP_FILES = BACKUP_ROOT / "files"
MANIFEST_JSON = BACKUP_ROOT / "manifest.json"

CHANGED_FILES = [
    Path("inventory/alarm_policy.py"),
    Path("inventory/views.py"),
    Path("inventory/management/commands/phase97_alarm_policy_characterization_check.py"),
    Path("inventory/management/commands/phase98_100_final_release_lock_check.py"),
]

PAYLOAD_COPY_FILES = [
    Path("inventory/alarm_policy.py"),
    Path("inventory/management/commands/phase97_alarm_policy_characterization_check.py"),
    Path("inventory/management/commands/phase98_100_final_release_lock_check.py"),
]

report: Dict[str, object] = {
    "phase": PHASE,
    "root": str(ROOT),
    "stamp": STAMP,
    "changed_files": [str(p).replace("\\", "/") for p in CHANGED_FILES],
    "steps": [],
    "rollback_performed": False,
    "service_restart": "NO",
    "db_mutation": "NO",
    "migration_write": "NO",
    "restore_enable_change": "NO",
    "ssh_execution": "NO",
    "backup_write": "NO",
    "visible_test_data_created": "NO",
}


def line(text: str) -> None:
    print(text)


def add_step(name: str, status: str, detail: object = None) -> None:
    report.setdefault("steps", []).append({"name": name, "status": status, "detail": detail})


def save_report() -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"PHASE={PHASE}",
        f"ROOT={ROOT}",
        f"FINAL_OK={report.get('final_ok')}",
        f"ROLLBACK_PERFORMED={report.get('rollback_performed')}",
        f"SERVICE_RESTART={report.get('service_restart')}",
        f"DB_MUTATION={report.get('db_mutation')}",
        f"MIGRATION_WRITE={report.get('migration_write')}",
        f"RESTORE_ENABLE_CHANGE={report.get('restore_enable_change')}",
        f"SSH_EXECUTION={report.get('ssh_execution')}",
        f"BACKUP_WRITE={report.get('backup_write')}",
        f"VISIBLE_TEST_DATA_CREATED={report.get('visible_test_data_created')}",
        f"REPORT_JSON={REPORT_JSON}",
        f"BACKUP_ROOT={BACKUP_ROOT}",
    ]
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: List[str], name: str, *, check: bool = True, allow_codes: Optional[List[int]] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    allow = set(allow_codes or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    line(f"STEP_START={name}")
    line("CMD=" + " ".join(args))
    proc = subprocess.run(args, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if proc.stdout:
        line(proc.stdout.rstrip())
    line(f"STEP_EXIT={name}:{proc.returncode}")
    ok = proc.returncode == 0 or proc.returncode in allow
    add_step(name, "ok" if ok else "fail", {"rc": proc.returncode})
    if check and not ok:
        raise RuntimeError(f"{name} failed rc={proc.returncode}")
    return proc


def preflight() -> None:
    line("STEP_START=preflight")
    if not (ROOT / "manage.py").exists():
        raise RuntimeError("missing manage.py")
    if not Path(sys.executable).exists():
        raise RuntimeError("missing python executable")
    if not PAYLOAD.exists():
        raise RuntimeError(f"missing payload: {PAYLOAD}")
    missing_payload = [str(p).replace("\\", "/") for p in PAYLOAD_COPY_FILES if not (PAYLOAD / p).exists()]
    if missing_payload:
        raise RuntimeError("missing payload files: " + ",".join(missing_payload))
    protected_roots = {"venv", ".git", "logs", "secrets", "staticfiles", "media", "backups", "_phase91_backup", "_phase91_quarantine", "db.sqlite3"}
    for rel in CHANGED_FILES:
        if rel.parts and rel.parts[0] in protected_roots:
            raise RuntimeError(f"refusing protected path: {rel}")
    line(f"ROOT={ROOT}")
    line(f"PAYLOAD={PAYLOAD}")
    line(f"BACKUP_ROOT={BACKUP_ROOT}")
    line("STEP_EXIT=preflight:0")
    add_step("preflight", "ok")


def backup_current_files() -> None:
    line("STEP_START=backup_current_files")
    BACKUP_FILES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for rel in CHANGED_FILES:
        src = ROOT / rel
        dst = BACKUP_FILES / rel
        entry = {"path": str(rel).replace("\\", "/"), "existed": src.exists()}
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            line(f"BACKUP_FILE={rel}")
        else:
            line(f"BACKUP_NEW_FILE_MARKER={rel}")
        manifest.append(entry)
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    line(f"BACKUP_MANIFEST={MANIFEST_JSON}")
    line("STEP_EXIT=backup_current_files:0")
    add_step("backup_current_files", "ok", manifest)


def patch_views_text(text: str) -> str:
    if "PHASE99_RESTORE_VALIDATE_SAFETY_GUARD" in text:
        return text
    text = text.replace(
        "from django.http import Http404, HttpResponse, JsonResponse",
        "from django.http import FileResponse, Http404, HttpResponse, JsonResponse",
        1,
    )

    replacements = []
    replacements.append((
'''def _restore_candidate_dir():
    candidate_dir = _switchmap_backup_dir() / "restore_candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    return candidate_dir


def _safe_backup_filename(filename):
''',
'''def _restore_candidate_dir():
    candidate_dir = _switchmap_backup_dir() / "restore_candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    return candidate_dir


# PHASE99_RESTORE_VALIDATE_SAFETY_GUARD
RESTORE_CANDIDATE_MAX_UPLOAD_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
RESTORE_CANDIDATE_MAX_SQLITE_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_SQLITE_BYTES", 250 * 1024 * 1024))
RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES = int(getattr(settings, "SWITCHMAP_RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES", 250 * 1024 * 1024))
RESTORE_CANDIDATE_CHUNK_BYTES = 1024 * 1024


def _path_is_under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def _delete_file_quietly(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _safe_backup_filename(filename):
'''))
    replacements.append((
'''def _backup_file_path(filename):
    name = _safe_backup_filename(filename)
    backup_dir = _switchmap_backup_dir().resolve()
    candidate_dir = _restore_candidate_dir().resolve()
    candidates = [backup_dir / name, candidate_dir / name]
    for path in candidates:
        try:
            resolved = path.resolve()
        except FileNotFoundError:
            continue
        if path.exists() and (str(resolved).startswith(str(backup_dir)) or str(resolved).startswith(str(candidate_dir))):
            return path
    raise Http404("Backup file not found.")
''',
'''def _backup_file_path(filename):
    name = _safe_backup_filename(filename)
    backup_dir = _switchmap_backup_dir().resolve()
    candidate_dir = _restore_candidate_dir().resolve()
    candidates = [backup_dir / name, candidate_dir / name]
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        if _path_is_under(path, backup_dir) or _path_is_under(path, candidate_dir):
            return path
    raise Http404("Backup file not found.")
'''))
    replacements.append((
'''def _validate_backup_file(path):
    suffix = path.suffix.lower()
    if suffix == ".sqlite3":
        return _validate_sqlite_file(path)
    if suffix != ".zip":
        return False, "Only .zip or .sqlite3 is allowed."

    with zipfile.ZipFile(path) as archive:
        sqlite_members = [name for name in archive.namelist() if name.lower().endswith(".sqlite3") and not name.endswith("/")]
        if len(sqlite_members) != 1:
            return False, f"ZIP must contain exactly one .sqlite3 file. Found={len(sqlite_members)}"
        member = sqlite_members[0]
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as temp_file:
            temp_name = temp_file.name
            with archive.open(member) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    temp_file.write(chunk)
        try:
            return _validate_sqlite_file(Path(temp_name))
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
''',
'''def _validate_backup_file(path):
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError as exc:
        return False, f"Cannot read candidate file: {exc}"

    if suffix == ".sqlite3":
        if size > RESTORE_CANDIDATE_MAX_SQLITE_BYTES:
            return False, "SQLite candidate is larger than the allowed validation limit."
        return _validate_sqlite_file(path)
    if suffix != ".zip":
        return False, "Only .zip or .sqlite3 is allowed."
    if size > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
        return False, "ZIP candidate is larger than the allowed upload limit."

    temp_name = None
    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            sqlite_infos = [info for info in infos if info.filename.lower().endswith(".sqlite3")]
            if len(sqlite_infos) != 1 or len(infos) != 1:
                return False, f"ZIP must contain only one .sqlite3 file. Found sqlite={len(sqlite_infos)} files={len(infos)}"
            info = sqlite_infos[0]
            member_name = info.filename.replace("\\\\", "/")
            if member_name.startswith("/") or "../" in member_name or member_name.startswith("../"):
                return False, "ZIP member path is not safe."
            if info.file_size > RESTORE_CANDIDATE_MAX_SQLITE_BYTES or info.file_size > RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES:
                return False, "ZIP SQLite member is larger than the allowed validation limit."
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as temp_file:
                temp_name = temp_file.name
                written = 0
                with archive.open(info) as source:
                    for chunk in iter(lambda: source.read(RESTORE_CANDIDATE_CHUNK_BYTES), b""):
                        written += len(chunk)
                        if written > RESTORE_CANDIDATE_MAX_ZIP_UNCOMPRESSED_BYTES:
                            return False, "ZIP uncompressed data exceeds the allowed validation limit."
                        temp_file.write(chunk)
        return _validate_sqlite_file(Path(temp_name))
    except zipfile.BadZipFile:
        return False, "Invalid ZIP file."
    finally:
        if temp_name:
            _delete_file_quietly(temp_name)
'''))
    replacements.append((
'''def backup_download_view(request, filename):
    path = _backup_file_path(filename)
    _log_system_action(request, "backup_download", path.name)
    content_type = "application/zip" if path.suffix.lower() == ".zip" else "application/x-sqlite3"
    response = HttpResponse(path.read_bytes(), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{path.name}"'
    response["Content-Length"] = str(path.stat().st_size)
    return response
''',
'''def backup_download_view(request, filename):
    path = _backup_file_path(filename)
    _log_system_action(request, "backup_download", path.name)
    content_type = "application/zip" if path.suffix.lower() == ".zip" else "application/x-sqlite3"
    response = FileResponse(open(path, "rb"), content_type=content_type, as_attachment=True, filename=path.name)
    response["Content-Length"] = str(path.stat().st_size)
    return response
'''))
    replacements.append((
'''def backup_validate_restore_view(request):
    upload = request.FILES.get("restore_file")
    if not upload:
        messages.error(request, "Restore candidate file is required.")
        return redirect("inventory:backup_center")

    original_name = Path(upload.name).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".zip", ".sqlite3"}:
        messages.error(request, "Only .zip or .sqlite3 files are allowed.")
        return redirect("inventory:backup_center")

    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    safe_original = re.sub(r"[^A-Za-z0-9_.-]+", "_", original_name).strip("._") or f"upload{suffix}"
    candidate_name = f"restore_candidate_{timestamp}_{safe_original}"
    candidate_path = _restore_candidate_dir() / candidate_name

    with open(candidate_path, "wb") as destination:
        for chunk in upload.chunks():
            destination.write(chunk)

    ok, validation_message = _validate_backup_file(candidate_path)
    action = "restore_candidate_valid" if ok else "restore_candidate_invalid"
    _log_system_action(request, action, f"{candidate_name} | {validation_message}")

    if ok:
        messages.success(request, f"Restore candidate validated. {validation_message}. Restore is NOT executed automatically.")
    else:
        messages.error(request, f"Restore candidate rejected: {validation_message}")
    return redirect("inventory:backup_center")
''',
'''def backup_validate_restore_view(request):
    upload = request.FILES.get("restore_file")
    if not upload:
        messages.error(request, "Restore candidate file is required.")
        return redirect("inventory:backup_center")

    original_name = Path(upload.name).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".zip", ".sqlite3"}:
        messages.error(request, "Only .zip or .sqlite3 files are allowed.")
        return redirect("inventory:backup_center")

    upload_size = int(getattr(upload, "size", 0) or 0)
    if upload_size > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
        messages.error(request, "Restore candidate rejected: file is larger than the allowed validation limit.")
        _log_system_action(request, "restore_candidate_rejected_size", f"{original_name} | size={upload_size}")
        return redirect("inventory:backup_center")

    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    safe_original = re.sub(r"[^A-Za-z0-9_.-]+", "_", original_name).strip("._") or f"upload{suffix}"
    candidate_name = f"restore_candidate_{timestamp}_{safe_original}"
    candidate_path = _restore_candidate_dir() / candidate_name

    written = 0
    with open(candidate_path, "wb") as destination:
        for chunk in upload.chunks():
            written += len(chunk)
            if written > RESTORE_CANDIDATE_MAX_UPLOAD_BYTES:
                destination.close()
                _delete_file_quietly(candidate_path)
                messages.error(request, "Restore candidate rejected: file is larger than the allowed validation limit.")
                _log_system_action(request, "restore_candidate_rejected_size", f"{candidate_name} | size>{RESTORE_CANDIDATE_MAX_UPLOAD_BYTES}")
                return redirect("inventory:backup_center")
            destination.write(chunk)

    ok, validation_message = _validate_backup_file(candidate_path)
    action = "restore_candidate_valid" if ok else "restore_candidate_invalid"
    _log_system_action(request, action, f"{candidate_name} | {validation_message}")

    if ok:
        messages.success(request, f"Restore candidate validated. {validation_message}. Restore is NOT executed automatically.")
    else:
        _delete_file_quietly(candidate_path)
        _log_system_action(request, "restore_candidate_invalid_deleted", candidate_name)
        messages.error(request, f"Restore candidate rejected: {validation_message}")
    return redirect("inventory:backup_center")
'''))

    for old, new in replacements:
        if old not in text:
            raise RuntimeError("views.py patch anchor not found")
        text = text.replace(old, new, 1)
    if "PHASE99_RESTORE_VALIDATE_SAFETY_GUARD" not in text:
        raise RuntimeError("views.py safety marker not applied")
    return text


def apply_payload() -> None:
    line("STEP_START=apply_payload")
    for rel in PAYLOAD_COPY_FILES:
        src = PAYLOAD / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        line(f"APPLIED_FILE={rel}")

    views_path = ROOT / "inventory" / "views.py"
    patched = patch_views_text(views_path.read_text(encoding="utf-8"))
    views_path.write_text(patched, encoding="utf-8")
    line("PATCHED_FILE=inventory\\views.py")
    line("STEP_EXIT=apply_payload:0")
    add_step("apply_payload", "ok")


def rollback() -> None:
    line("STEP_START=rollback")
    report["rollback_performed"] = True
    if not MANIFEST_JSON.exists():
        line("ROLLBACK_SKIP=no_manifest")
        add_step("rollback", "skipped", "no_manifest")
        return
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    for entry in reversed(manifest):
        rel = Path(entry["path"])
        dst = ROOT / rel
        backup = BACKUP_FILES / rel
        if entry.get("existed"):
            if backup.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, dst)
                line(f"ROLLBACK_RESTORED={rel}")
            else:
                line(f"ROLLBACK_MISSING_BACKUP={rel}")
        else:
            if dst.exists():
                dst.unlink()
                line(f"ROLLBACK_REMOVED_NEW_FILE={rel}")
    line("STEP_EXIT=rollback:0")
    add_step("rollback", "ok")


def verify_after_apply() -> None:
    line("STEP_START=verify_after_apply")
    run([sys.executable, "-m", "py_compile", "inventory/alarm_policy.py", "inventory/views.py", "inventory/management/commands/phase97_alarm_policy_characterization_check.py", "inventory/management/commands/phase98_100_final_release_lock_check.py"], "py_compile_changed")
    run([sys.executable, "manage.py", "check"], "django_manage_check")
    run([sys.executable, "manage.py", "phase97_alarm_policy_characterization_check", "--strict", "--output", str(LOG_DIR / f"phase98_100_alarm_policy_characterization_{STAMP}.json")], "phase97_alarm_policy_characterization_check", timeout=180)
    run([sys.executable, "manage.py", "phase98_100_final_release_lock_check", "--strict", "--output", str(LOG_DIR / f"phase98_100_final_release_lock_{STAMP}.json")], "phase98_100_final_release_lock_check", timeout=180)
    if (ROOT / "smoke_tests" / "run_smoke.py").exists():
        run([sys.executable, "smoke_tests/run_smoke.py", "--strict", "--output", str(LOG_DIR / f"phase98_100_phase94_smoke_runner_{STAMP}.json")], "phase94_smoke_runner", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "phase77_stabilization_check.py").exists():
        run([sys.executable, "manage.py", "phase77_stabilization_check", "--output", str(LOG_DIR / f"phase98_100_phase77_stabilization_{STAMP}.txt")], "phase77_stabilization_check", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "phase80_alarm_normalization_check.py").exists():
        run([sys.executable, "manage.py", "phase80_alarm_normalization_check"], "phase80_alarm_normalization_check", timeout=180)
    if (ROOT / "inventory" / "management" / "commands" / "backup_storage_verify.py").exists():
        run([sys.executable, "manage.py", "backup_storage_verify", "--strict"], "backup_storage_verify_strict", timeout=300)
    if (ROOT / "inventory" / "management" / "commands" / "backup_health_report.py").exists():
        run([sys.executable, "manage.py", "backup_health_report", "--strict"], "backup_health_report_strict", timeout=300)
    line("STEP_EXIT=verify_after_apply:0")
    add_step("verify_after_apply", "ok")


def main() -> int:
    line("PHASE98_100_FINAL_REFINE_RELEASE_LOCK_START")
    line("MODE=file_only_alarm_cleanup_restore_validate_safety_final_verify_no_restart_no_ssh")
    line(f"ROOT={ROOT}")
    line("EXPECTED_RESULT=alarm_policy_canonical_restore_validate_hardened_final_release_lock_ok")
    line("RISK=file_only_changes_no_runtime_restart")
    line("ROLLBACK=automatic_on_apply_or_verify_failure")
    try:
        preflight()
        backup_current_files()
        apply_payload()
        verify_after_apply()
        report["final_ok"] = True
        save_report()
        line("PHASE98_100_FINAL_OK=True")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line(f"ROLLBACK_SOURCE={BACKUP_ROOT}")
        line("SERVICE_RESTART=NO")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE98_100_FINAL_REFINE_RELEASE_LOCK_OK")
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
        line(f"PHASE98_100_ERROR={type(exc).__name__}:{exc}")
        try:
            rollback()
        except Exception as rb_exc:
            report["rollback_error"] = f"{type(rb_exc).__name__}:{rb_exc}"
            line(f"PHASE98_100_ROLLBACK_ERROR={type(rb_exc).__name__}:{rb_exc}")
        report["final_ok"] = False
        save_report()
        line("PHASE98_100_FINAL_OK=False")
        line(f"REPORT_JSON={REPORT_JSON}")
        line(f"REPORT_TXT={REPORT_TXT}")
        line("SERVICE_RESTART=NO")
        line("DB_MUTATION=NO")
        line("MIGRATION_WRITE=NO")
        line("RESTORE_ENABLE_CHANGE=NO")
        line("SSH_EXECUTION=NO")
        line("BACKUP_WRITE=NO")
        line("VISIBLE_TEST_DATA_CREATED=NO")
        line("PHASE98_100_FINAL_REFINE_RELEASE_LOCK_FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
