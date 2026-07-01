from __future__ import annotations

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .access_control import is_admin, user_role
from .mikrotik_backup_tools import (
    BACKUP_TYPE_LABELS,
    COMMANDS,
    find_backup,
    latest_previous_backup,
    list_backups,
    mask_sensitive_export,
    mikrotik_switches,
    read_backup_bytes,
    read_backup_content,
    run_single_backup,
    safe_diff,
    save_backup_failure,
    setup_storage,
    validate_restore_candidate,
)
from .models import Switch, SystemAuditLog
from .ssh_tools import SshActionError
try:
    from .secure_credentials import credential_status
except Exception:  # pragma: no cover
    credential_status = None

PHASE85_MARKER = "PHASE85_MIKROTIK_BACKUP_CENTER"


def _actor(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user.get_username()
    return ""


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def _audit(request, action: str, target: str, message: str = ""):
    try:
        SystemAuditLog.objects.create(
            category=SystemAuditLog.Category.SYSTEM,
            action=action,
            target_username=target,
            actor_username=_actor(request),
            actor_role=user_role(request.user),
            client_ip=_client_ip(request),
            request_path=request.path,
            message=message,
        )
    except Exception:
        pass


def _record_failure(request, switch, backup_type: str, error: Exception | str, source: str):
    command = COMMANDS.get(backup_type, backup_type)
    try:
        return save_backup_failure(
            switch=switch,
            backup_type=backup_type,
            command=command,
            error=str(error),
            created_by=_actor(request),
            source=source,
        )
    except Exception:
        return None


class MikroTikBackupForm(forms.Form):
    switch = forms.ModelChoiceField(queryset=Switch.objects.none(), label="Device")
    backup_type = forms.ChoiceField(choices=[(key, label) for key, label in BACKUP_TYPE_LABELS.items()], label="Type")
    username = forms.CharField(max_length=100, label="SSH Username")
    password = forms.CharField(widget=forms.PasswordInput, label="SSH Password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ids = [sw.id for sw in mikrotik_switches()]
        self.fields["switch"].queryset = Switch.objects.filter(id__in=ids).order_by("topology_position", "name")
        first = Switch.objects.filter(id__in=ids).order_by("topology_position", "name").first()
        if first:
            self.fields["username"].initial = first.ssh_username
        _decorate_form_fields(self)


class MikroTikBatchBackupForm(forms.Form):
    target = forms.ChoiceField(choices=(("selected", "Selected"), ("all", "All MikroTik")), initial="selected")
    switches = forms.ModelMultipleChoiceField(queryset=Switch.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    backup_types = forms.MultipleChoiceField(choices=[(key, label) for key, label in BACKUP_TYPE_LABELS.items()], initial=["export"], widget=forms.CheckboxSelectMultiple)
    username = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ids = [sw.id for sw in mikrotik_switches()]
        self.fields["switches"].queryset = Switch.objects.filter(id__in=ids).order_by("topology_position", "name")
        first = Switch.objects.filter(id__in=ids).order_by("topology_position", "name").first()
        if first:
            self.fields["username"].initial = first.ssh_username
        _decorate_form_fields(self)


def _decorate_form_fields(form):
    for field in form.fields.values():
        css = field.widget.attrs.get("class", "")
        if "phase85-input" not in css:
            field.widget.attrs["class"] = (css + " phase85-input").strip()
    return form


def _backup_type_choices():
    return [("", "All Types")] + [(key, label) for key, label in BACKUP_TYPE_LABELS.items()]


def _backup_stats(rows):
    rows = list(rows or [])
    success_rows = [row for row in rows if row.get("success")]
    failed_rows = [row for row in rows if not row.get("success")]
    sensitive_total = 0
    for row in success_rows:
        try:
            sensitive_total += int(row.get("sensitive_line_count") or 0)
        except Exception:
            pass
    return {
        "total": len(rows),
        "success": len(success_rows),
        "failed": len(failed_rows),
        "export": len([row for row in success_rows if row.get("backup_type") == "export"]),
        "full": len([row for row in success_rows if row.get("backup_type") == "full-backup"]),
        "sensitive_total": sensitive_total,
        "last_success": success_rows[0] if success_rows else None,
    }


def _scheduled_prepare_context(switches):
    switches = list(switches or [])
    first_two = switches[:2]
    selected_args = " ".join(f"--switch-id {sw.id}" for sw in first_two) or "--switch-id <ID>"
    selected_names = ", ".join(sw.name for sw in first_two) or "Selected MikroTik devices"
    status = {"exists": False, "file": "", "legacy": False}
    if credential_status is not None:
        try:
            status = credential_status("mikrotik")
        except Exception as exc:
            status = {"exists": False, "file": f"status error: {exc}", "legacy": False}
    return {
        "credential_status": status,
        "credential_commands": [
            "python manage.py set_ssh_monitor_credentials --profile mikrotik",
            "python manage.py set_ssh_monitor_credentials --profile mikrotik --status",
            "python manage.py set_ssh_monitor_credentials --profile mikrotik --test --switch RB5009",
        ],
        "scheduled_selected_label": selected_names,
        "scheduled_selected_command": f"python manage.py mikrotik_backup_scheduled {selected_args} --type export --type full-backup",
        "scheduled_all_command": "python manage.py mikrotik_backup_scheduled --all --type export --type full-backup",
        "scheduled_task_example": r'schtasks /Create /TN "SwitchMap MikroTik Backup" /SC DAILY /ST 23:55 /TR "\"C:\SwitchMap\venv\Scripts\python.exe\" \"C:\SwitchMap\manage.py\" mikrotik_backup_scheduled --all --type export --type full-backup" /RU "%USERNAME%"',
    }


def mikrotik_backup_center_view(request):
    setup_storage()
    switch_filter = request.GET.get("switch", "").strip()
    type_filter = request.GET.get("type", "").strip()
    device_id = int(switch_filter) if switch_filter.isdigit() else None
    switches = mikrotik_switches()
    backups = list_backups(limit=250, device_id=device_id, backup_type=type_filter)
    all_recent_backups = list_backups(limit=1000)
    return render(
        request,
        "inventory/mikrotik_backup_center.html",
        {
            "phase85_marker": PHASE85_MARKER,
            "switches": switches,
            "backups": backups,
            "backup_form": MikroTikBackupForm(),
            "batch_form": MikroTikBatchBackupForm(),
            "type_choices": _backup_type_choices(),
            "switch_filter": switch_filter,
            "type_filter": type_filter,
            "backup_stats": _backup_stats(all_recent_backups),
            "scheduled_prepare": _scheduled_prepare_context(switches),
        },
    )


@require_POST
def mikrotik_backup_run_view(request):
    form = MikroTikBackupForm(request.POST)
    if not form.is_valid():
        messages.error(request, "فرم Backup نامعتبر است.")
        return redirect("inventory:mikrotik_backup_center")
    switch = form.cleaned_data["switch"]
    backup_type = form.cleaned_data["backup_type"]
    try:
        row = run_single_backup(
            switch=switch,
            backup_type=backup_type,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
            created_by=_actor(request),
            source="manual-ssh",
        )
        _audit(request, "mikrotik_backup_create", switch.name, f"{backup_type} backup created: {row.get('filename')}")
        messages.success(request, "MikroTik Backup ذخیره شد.")
        return redirect("inventory:mikrotik_backup_detail", backup_id=row["backup_id"])
    except Exception as exc:
        _record_failure(request, switch, backup_type, exc, "manual-ssh")
        _audit(request, "mikrotik_backup_fail", switch.name, str(exc))
        messages.error(request, f"Backup failed: {exc}")
    return redirect("inventory:mikrotik_backup_center")


@require_POST
def mikrotik_backup_batch_view(request):
    form = MikroTikBatchBackupForm(request.POST)
    if not form.is_valid():
        messages.error(request, "فرم Batch Backup نامعتبر است.")
        return redirect("inventory:mikrotik_backup_center")
    switches = mikrotik_switches() if form.cleaned_data["target"] == "all" else list(form.cleaned_data["switches"])
    if not switches:
        messages.error(request, "هیچ MikroTik انتخاب نشده است.")
        return redirect("inventory:mikrotik_backup_center")
    created = 0
    failed = 0
    for switch in switches:
        for backup_type in form.cleaned_data["backup_types"]:
            try:
                run_single_backup(switch=switch, backup_type=backup_type, username=form.cleaned_data["username"], password=form.cleaned_data["password"], created_by=_actor(request), source="batch-ssh")
                created += 1
            except Exception as exc:
                failed += 1
                _record_failure(request, switch, backup_type, exc, "batch-ssh")
                _audit(request, "mikrotik_backup_batch_fail", switch.name, f"{backup_type}: {exc}")
    _audit(request, "mikrotik_backup_batch", "MikroTik", f"created={created} failed={failed}")
    if failed:
        messages.warning(request, f"Batch Backup: موفق {created} / ناموفق {failed}")
    else:
        messages.success(request, f"Batch Backup: موفق {created} / ناموفق {failed}")
    return redirect("inventory:mikrotik_backup_center")


def _detail_context(row, *, request=None, validation_override=None):
    content = read_backup_content(row) if row.get("backup_type") == "export" else ""
    masked_content, sensitive_count = mask_sensitive_export(content) if content else ("", 0)
    previous = latest_previous_backup(row.get("device_id"), row.get("backup_type"), before_backup_id=row.get("backup_id"))
    diff_text = ""
    if previous and content and row.get("backup_type") == "export":
        previous_content = read_backup_content(previous)
        if previous_content:
            diff_text = safe_diff(previous_content, content, previous_name=previous.get("filename", "previous"), current_name=row.get("filename", "current"))
    validation = validation_override
    if validation is None and row.get("success"):
        validation = validate_restore_candidate(row)
    safe_backup = dict(row)
    safe_backup["file_path"] = "admin-only / direct web access blocked"
    safe_backup["sensitive_line_count"] = sensitive_count
    safe_backup["download_scope"] = "admin-only"
    return {
        "backup": safe_backup,
        "content_preview": masked_content[:80000],
        "previous": previous,
        "diff_text": diff_text,
        "validation": validation,
        "download_allowed": bool(request is not None and is_admin(request.user)),
        "is_export": row.get("backup_type") == "export",
        "is_full_backup": row.get("backup_type") == "full-backup",
    }


def mikrotik_backup_detail_view(request, backup_id):
    row = find_backup(backup_id)
    if not row:
        raise Http404("Backup not found")
    return render(request, "inventory/mikrotik_backup_detail.html", _detail_context(row, request=request))


def mikrotik_backup_download_view(request, backup_id):
    if not is_admin(request.user):
        return HttpResponseForbidden("Download فقط برای Admin مجاز است.")
    row = find_backup(backup_id)
    if not row:
        raise Http404("Backup not found")
    data = read_backup_bytes(row)
    if not row.get("success") or not data:
        raise Http404("Backup file not available")
    content_type = "application/octet-stream" if row.get("backup_type") == "full-backup" else "text/plain; charset=utf-8"
    response = HttpResponse(data, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{row.get("filename") or "mikrotik-backup"}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    _audit(request, "mikrotik_backup_download", row.get("device", ""), row.get("filename", ""))
    return response


@require_POST
def mikrotik_backup_validate_restore_view(request, backup_id):
    row = find_backup(backup_id)
    if not row:
        raise Http404("Backup not found")
    result = validate_restore_candidate(row)
    _audit(request, "mikrotik_restore_prepare", row.get("device", ""), "dry-run-only validate")
    messages.success(request, "Restore Prepare / Dry-run انجام شد. اجرای واقعی Restore در این فاز غیرفعال است.")
    return render(request, "inventory/mikrotik_backup_detail.html", _detail_context(row, request=request, validation_override=result))
