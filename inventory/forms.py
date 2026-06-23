from django import forms
from django.contrib.auth import get_user_model

from .access_control import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEW_ONLY
from .models import Port, Switch

User = get_user_model()

ROLE_CHOICES = (
    (ROLE_VIEW_ONLY, "View Only"),
    (ROLE_OPERATOR, "Operator"),
    (ROLE_ADMIN, "Admin"),
)


class PortForm(forms.ModelForm):
    class Meta:
        model = Port
        fields = [
            "interface_name",
            "display_order",
            "description",
            "connected_device",
            "device_type",
            "owner",
            "ip_address",
            "mac_address",
            "port_mode",
            "access_vlan",
            "native_vlan",
            "voice_vlan",
            "trunk_vlans",
            "vlan",
            "status",
            "poe_enabled",
            "documentation_status",
            "asset_tag",
            "room",
            "rack",
            "rack_unit",
            "patch_panel",
            "patch_panel_port",
            "outlet",
            "cable_label",
            "cable_type",
            "cable_length",
            "prtg_url",
            "notes",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"dir": "ltr"}),
            "connected_device": forms.TextInput(attrs={"dir": "ltr"}),
            "owner": forms.TextInput(attrs={"dir": "ltr"}),
            "asset_tag": forms.TextInput(attrs={"dir": "ltr"}),
            "mac_address": forms.TextInput(attrs={"dir": "ltr"}),
            "trunk_vlans": forms.TextInput(attrs={"dir": "ltr", "placeholder": "1,100,101,200"}),
            "rack": forms.TextInput(attrs={"dir": "ltr"}),
            "rack_unit": forms.TextInput(attrs={"dir": "ltr"}),
            "patch_panel": forms.TextInput(attrs={"dir": "ltr"}),
            "patch_panel_port": forms.TextInput(attrs={"dir": "ltr"}),
            "outlet": forms.TextInput(attrs={"dir": "ltr"}),
            "cable_label": forms.TextInput(attrs={"dir": "ltr"}),
            "cable_type": forms.TextInput(attrs={"dir": "ltr"}),
            "cable_length": forms.TextInput(attrs={"dir": "ltr"}),
            "prtg_url": forms.URLInput(attrs={"dir": "ltr"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }



class SwitchForm(forms.ModelForm):
    class Meta:
        model = Switch
        fields = [
            "name",
            "management_ip",
            "model",
            "vendor",
            "device_family",
            "device_role",
            "site",
            "location",
            "topology_position",
            "winbox_port",
            "needs_review",
            "port_count",
            "notes",
            "is_active",
            "snmp_enabled",
            "snmp_community",
            "snmp_port",
            "snmp_timeout",
            "ssh_enabled",
            "ssh_username",
            "ssh_port",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"dir": "ltr"}),
            "management_ip": forms.TextInput(attrs={"dir": "ltr"}),
            "model": forms.TextInput(attrs={"dir": "ltr"}),
            "site": forms.TextInput(attrs={"dir": "ltr"}),
            "location": forms.TextInput(attrs={"dir": "ltr"}),
            "topology_position": forms.NumberInput(attrs={"min": 1, "max": 999}),
            "winbox_port": forms.NumberInput(attrs={"min": 1, "max": 65535}),
            "port_count": forms.NumberInput(attrs={"min": 1, "max": 256}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "snmp_community": forms.TextInput(attrs={"dir": "ltr"}),
            "snmp_port": forms.NumberInput(attrs={"min": 1, "max": 65535}),
            "snmp_timeout": forms.NumberInput(attrs={"min": 1, "max": 30}),
            "ssh_username": forms.TextInput(attrs={"dir": "ltr"}),
            "ssh_port": forms.NumberInput(attrs={"min": 1, "max": 65535}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            base_class = field.widget.attrs.get("class", "")
            classes = [item for item in base_class.split() if item]
            if not isinstance(field.widget, forms.CheckboxInput) and "input" not in classes:
                classes.append("input")
            if name in {"name", "management_ip", "model", "site", "location", "snmp_community", "ssh_username"}:
                field.widget.attrs.setdefault("dir", "ltr")
                if "ltr" not in classes:
                    classes.append("ltr")
            if classes:
                field.widget.attrs["class"] = " ".join(classes)

    def clean_port_count(self):
        value = self.cleaned_data.get("port_count") or 1
        if value < 1 or value > 256:
            raise forms.ValidationError("Port count باید بین 1 تا 256 باشد.")
        return value


class SwitchBulkImportForm(forms.Form):
    csv_text = forms.CharField(
        label="CSV",
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "dir": "ltr",
                "placeholder": "name,management_ip,model,location,port_count,snmp_community\nEdari-1,172.20.1.6,Cisco Catalyst 3850,Rack 2,48,RO",
            }
        ),
    )
    create_ports = forms.BooleanField(
        label="Create Gi1/0/x ports",
        required=False,
        initial=True,
    )
    default_port_count = forms.IntegerField(
        label="Default port count",
        min_value=1,
        max_value=96,
        initial=48,
    )


class SSHPortActionForm(forms.Form):
    ACTION_SET_ACCESS_VLAN = "set_access_vlan"
    ACTION_SET_DESCRIPTION = "set_description"
    ACTION_CLEAR_DESCRIPTION = "clear_description"
    ACTION_SET_VOICE_VLAN = "set_voice_vlan"
    ACTION_REMOVE_VOICE_VLAN = "remove_voice_vlan"
    ACTION_SET_TRUNK_ALLOWED = "set_trunk_allowed"
    ACTION_ADD_TRUNK_VLAN = "add_trunk_vlan"
    ACTION_REMOVE_TRUNK_VLAN = "remove_trunk_vlan"
    ACTION_SHUTDOWN = "shutdown"
    ACTION_NO_SHUTDOWN = "no_shutdown"
    ACTION_POE_AUTO = "poe_auto"
    ACTION_POE_NEVER = "poe_never"
    ACTION_FORCE_TRUNK = "force_trunk"

    ACTION_CHOICES = [
        (ACTION_SET_ACCESS_VLAN, "تغییر VLAN دسترسی"),
        (ACTION_SET_DESCRIPTION, "ثبت Description"),
        (ACTION_CLEAR_DESCRIPTION, "حذف Description"),
        (ACTION_SET_VOICE_VLAN, "تغییر Voice VLAN"),
        (ACTION_REMOVE_VOICE_VLAN, "حذف Voice VLAN"),
        (ACTION_SET_TRUNK_ALLOWED, "تنظیم VLAN های Trunk"),
        (ACTION_ADD_TRUNK_VLAN, "افزودن VLAN به Trunk"),
        (ACTION_REMOVE_TRUNK_VLAN, "حذف VLAN از Trunk"),
        (ACTION_SHUTDOWN, "Shutdown"),
        (ACTION_NO_SHUTDOWN, "No Shutdown"),
        (ACTION_POE_AUTO, "PoE Auto"),
        (ACTION_POE_NEVER, "PoE Off"),
        (ACTION_FORCE_TRUNK, "Force Trunk"),
    ]

    port_id = forms.IntegerField()
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    value = forms.CharField(required=False)
    ssh_username = forms.CharField(max_length=100)
    ssh_password = forms.CharField(widget=forms.PasswordInput)
    enable_password = forms.CharField(required=False, widget=forms.PasswordInput)
    force = forms.BooleanField(required=False)
    confirmed = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        value = (cleaned_data.get("value") or "").strip()
        force = cleaned_data.get("force") or False

        value_required_actions = {
            self.ACTION_SET_ACCESS_VLAN: "VLAN لازم است.",
            self.ACTION_SET_DESCRIPTION: "Description لازم است.",
            self.ACTION_SET_VOICE_VLAN: "Voice VLAN لازم است.",
            self.ACTION_SET_TRUNK_ALLOWED: "VLAN های Trunk لازم است.",
            self.ACTION_ADD_TRUNK_VLAN: "VLAN برای افزودن لازم است.",
            self.ACTION_REMOVE_TRUNK_VLAN: "VLAN برای حذف لازم است.",
        }

        if action in value_required_actions and not value:
            self.add_error("value", value_required_actions[action])

        trunk_actions = {
            self.ACTION_SET_TRUNK_ALLOWED,
            self.ACTION_ADD_TRUNK_VLAN,
            self.ACTION_REMOVE_TRUNK_VLAN,
            self.ACTION_FORCE_TRUNK,
        }

        risky_actions = {
            self.ACTION_SHUTDOWN,
            self.ACTION_POE_NEVER,
            self.ACTION_SET_VOICE_VLAN,
            self.ACTION_REMOVE_VOICE_VLAN,
            self.ACTION_SET_TRUNK_ALLOWED,
            self.ACTION_ADD_TRUNK_VLAN,
            self.ACTION_REMOVE_TRUNK_VLAN,
            self.ACTION_FORCE_TRUNK,
        }

        if action in trunk_actions and not force:
            self.add_error("force", "برای تغییر Trunk باید تیک اجازه تغییر روی پورت Trunk فعال باشد.")

        if action in risky_actions and not cleaned_data.get("confirmed"):
            self.add_error("confirmed", "برای این عملیات تأیید نهایی لازم است.")

        return cleaned_data



class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150, label="Username")
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField(required=False, label="Email")
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial=ROLE_VIEW_ONLY, label="Role")
    is_active = forms.BooleanField(required=False, initial=True, label="Active")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("این Username قبلاً ساخته شده است.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "تکرار رمز عبور یکسان نیست.")
        if password1 and len(password1) < 8:
            self.add_error("password1", "رمز عبور حداقل باید 8 کاراکتر باشد.")
        return cleaned


class UserUpdateForm(forms.Form):
    username = forms.CharField(max_length=150, label="Username")
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField(required=False, label="Email")
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial=ROLE_VIEW_ONLY, label="Role")
    is_active = forms.BooleanField(required=False, label="Active")
    is_staff = forms.BooleanField(required=False, label="Django staff")

    def __init__(self, *args, user_instance=None, **kwargs):
        self.user_instance = user_instance
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        queryset = User.objects.filter(username__iexact=username)
        if self.user_instance is not None:
            queryset = queryset.exclude(pk=self.user_instance.pk)
        if queryset.exists():
            raise forms.ValidationError("این Username قبلاً استفاده شده است.")
        return username


class UserPasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput, label="New password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "تکرار رمز عبور یکسان نیست.")
        if password1 and len(password1) < 8:
            self.add_error("password1", "رمز عبور حداقل باید 8 کاراکتر باشد.")
        return cleaned
