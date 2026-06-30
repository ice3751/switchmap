from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect


ROLE_VIEW_ONLY = "View Only"
ROLE_OPERATOR = "Operator"
ROLE_ADMIN = "Admin"

ROLE_ORDER = {
    ROLE_VIEW_ONLY: 1,
    ROLE_OPERATOR: 2,
    ROLE_ADMIN: 3,
}

OPERATOR_SSH_ACTIONS = {
    "set_access_vlan",
    "set_description",
    "clear_description",
    "shutdown",
    "no_shutdown",
    "poe_auto",
    "poe_never",
}

ADMIN_ONLY_SSH_ACTIONS = {
    "set_voice_vlan",
    "remove_voice_vlan",
    "set_trunk_allowed",
    "add_trunk_vlan",
    "remove_trunk_vlan",
    "force_trunk",
}


def user_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ROLE_VIEW_ONLY
    if getattr(user, "is_superuser", False):
        return ROLE_ADMIN
    group_names = set(user.groups.values_list("name", flat=True))
    if ROLE_ADMIN in group_names:
        return ROLE_ADMIN
    if ROLE_OPERATOR in group_names:
        return ROLE_OPERATOR
    return ROLE_VIEW_ONLY


def role_level(role_name):
    return ROLE_ORDER.get(role_name or ROLE_VIEW_ONLY, 1)


def is_admin(user):
    return user_role(user) == ROLE_ADMIN


def is_operator_or_admin(user):
    return role_level(user_role(user)) >= role_level(ROLE_OPERATOR)


def can_view(user):
    return bool(user and getattr(user, "is_authenticated", False))


def can_refresh(user):
    return is_operator_or_admin(user)


def can_edit_port(user):
    return is_operator_or_admin(user)


def can_run_ssh(user):
    return is_operator_or_admin(user)


def can_sfp_poll(user):
    return is_operator_or_admin(user)


def can_pull_cisco_logs(user):
    return is_operator_or_admin(user)


def can_import_cisco_logs(user):
    return is_admin(user)


def can_import_switches(user):
    return is_admin(user)


def can_admin_panel(user):
    return is_admin(user) or bool(user and getattr(user, "is_staff", False))


def can_manage_users(user):
    return is_admin(user)


def can_manage_backups(user):
    return is_admin(user)


def allowed_ssh_actions(user, choices=None):
    role = user_role(user)
    allowed = set()
    if role == ROLE_ADMIN:
        allowed = OPERATOR_SSH_ACTIONS | ADMIN_ONLY_SSH_ACTIONS
    elif role == ROLE_OPERATOR:
        allowed = set(OPERATOR_SSH_ACTIONS)
    if choices is None:
        return allowed
    return [(value, label) for value, label in choices if value in allowed]


def can_run_ssh_action(user, action):
    return action in allowed_ssh_actions(user)


def _wants_json(request):
    accept = request.headers.get("accept", "")
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in accept
        or request.path.endswith("/data/")
        or request.path.endswith("/payload/")
        or request.path.endswith("/preview/")
        or request.path.endswith("/ssh-port-action/")
        or "ssh-action" in request.path
        or "port-action" in request.path
    )


def deny_response(request, message="Access denied.", status=403):
    if _wants_json(request):
        return JsonResponse({"ok": False, "message": message, "error": message}, status=status)
    messages.error(request, message)
    return HttpResponseForbidden(message)


def role_required(check_func, message="Access denied."):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not check_func(request.user):
                return deny_response(request, message=message, status=403)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


view_required = login_required
operator_or_admin_required = role_required(
    is_operator_or_admin,
    "این عملیات فقط برای Operator یا Admin مجاز است.",
)
admin_required = role_required(
    is_admin,
    "این عملیات فقط برای Admin مجاز است.",
)
refresh_required = role_required(
    can_refresh,
    "Refresh فقط برای Operator یا Admin مجاز است.",
)
sfp_poll_required = role_required(
    can_sfp_poll,
    "SFP Poll فقط برای Operator یا Admin مجاز است.",
)
cisco_pull_required = role_required(
    can_pull_cisco_logs,
    "Pull Cisco Logs فقط برای Operator یا Admin مجاز است.",
)
cisco_import_required = role_required(
    can_import_cisco_logs,
    "Import Cisco Logs فقط برای Admin مجاز است.",
)

user_management_required = role_required(
    can_manage_users,
    "مدیریت کاربران فقط برای Admin مجاز است.",
)

backup_management_required = role_required(
    can_manage_backups,
    "Backup Center فقط برای Admin مجاز است.",
)
