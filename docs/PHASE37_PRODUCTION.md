# SwitchMap Phase 37 - Production روی سرور داخلی

## Scope

این فاز فقط اجرای Production، Static، Backup زمان‌بندی‌شده و مستند نصب/بازیابی را آماده می‌کند.
ظاهر Cisco 3850، Nexus، Dashboard، Topology، SSH و Alarm تغییر داده نشده‌اند.

## فایل‌های تغییرکرده

- `requirements.txt`
- `config/settings.py`
- `switchmap.env.example`
- `switchmap.production.env.example`

## فایل‌های جدید

- `run_waitress.py`
- `inventory/management/commands/production_check.py`
- `scripts/phase37_prepare_production.cmd`
- `scripts/run_waitress.cmd`
- `scripts/install_waitress_startup_task.cmd`
- `scripts/remove_waitress_startup_task.cmd`
- `scripts/install_backup_task.cmd`
- `scripts/remove_backup_task.cmd`
- `scripts/generate_secret.cmd`
- `scripts/install_service_nssm.cmd`
- `scripts/remove_service_nssm.cmd`
- `switchmap_37_production_smoke_test.py`

## فایل‌هایی که نباید در این فاز تغییر کنند

- `inventory/templates/inventory/switch_list.html`
- `inventory/templates/inventory/switch_detail.html`
- `inventory/static/inventory/switchmap.css`
- `inventory/static/inventory/switchmap.js`
- مدل‌ها و Migration ها
- دیتابیس `db.sqlite3`

## آماده‌سازی Production

۱. یک Secret جدید بساز.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\generate_secret.cmd
```

۲. فایل `switchmap.production.env.example` را باز کن و مقدارهای واقعی را داخل `switchmap.env` بگذار.

حداقل این موارد باید اصلاح شوند:

```text
SWITCHMAP_DEBUG=False
SWITCHMAP_SECRET_KEY=<generated-secret>
SWITCHMAP_ALLOWED_HOSTS=127.0.0.1,localhost,<server-name>,<server-ip>
SWITCHMAP_CSRF_TRUSTED_ORIGINS=http://<server-name>:8000,http://<server-ip>:8000
```

۳. آماده‌سازی را اجرا کن.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\phase37_prepare_production.cmd
```

این دستور این کارها را انجام می‌دهد:

- نصب Dependency ها از `requirements.txt`
- اجرای `migrate`
- اجرای `collectstatic`
- اجرای `manage.py check`
- اجرای `manage.py production_check`

## اجرای دستی Waitress

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\run_waitress.cmd
```

آدرس تست:

```text
http://<server-ip>:8000/
```

## اجرای خودکار بعد از Boot با Task Scheduler

این روش به ابزار خارجی نیاز ندارد.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\install_waitress_startup_task.cmd
```

حذف Task:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\remove_waitress_startup_task.cmd
```

## Windows Service واقعی با NSSM

این پکیج فایل `nssm.exe` ندارد.
اگر سرویس واقعی می‌خواهی، فایل `nssm.exe` را اینجا بگذار:

```text
C:\Users\a-mortazavi.WINAC-CO\SwitchMap\tools\nssm\nssm.exe
```

بعد اجرا کن:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\install_service_nssm.cmd
```

حذف سرویس:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\remove_service_nssm.cmd
```

## Backup زمان‌بندی‌شده

Backup روزانه ساعت 23:30 ساخته می‌شود.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\install_backup_task.cmd
```

حذف زمان‌بندی Backup:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
scripts\remove_backup_task.cmd
```

تست دستی Backup:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
switchmap_backup_sqlite.cmd
```

محل Backup پیش‌فرض:

```text
C:\Users\a-mortazavi.WINAC-CO\SwitchMap\backups\sqlite
```

## بازیابی اضطراری SQLite

Restore داخل سایت عمداً اجرا نمی‌شود.
برای بازیابی دستی:

۱. سرویس یا Task اجرای Waitress را متوقف کن.

۲. از دیتابیس فعلی کپی بگیر.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
copy db.sqlite3 db.sqlite3.before_restore
```

۳. فایل Backup معتبر را Extract کن و فایل `.sqlite3` داخل آن را جایگزین `db.sqlite3` کن.

۴. سلامت دیتابیس را بررسی کن.

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
venv\Scripts\activate
python manage.py production_check --skip-static
```

۵. Waitress را دوباره اجرا کن.

## Rollback فاز ۳۷

- فایل‌های اضافه‌شده این فاز را حذف کن.
- `requirements.txt` را به نسخه قبل برگردان.
- بخش Phase 37 را از انتهای `config/settings.py` حذف کن.
- اگر Task ساخته شده:

```cmd
scripts\remove_waitress_startup_task.cmd
scripts\remove_backup_task.cmd
```

- اگر NSSM نصب شده:

```cmd
scripts\remove_service_nssm.cmd
```

## ریسک

- `DEBUG=False` اگر `ALLOWED_HOSTS` درست نباشد باعث خطای `DisallowedHost` می‌شود.
- اگر `collectstatic` اجرا نشود، Static در Production ناقص می‌شود.
- اگر Task با یوزری ساخته شود که به مسیر پروژه دسترسی ندارد، سرویس بالا نمی‌آید.
- اگر Backup روی همان دیسک پروژه بماند، خرابی دیسک اصلی را پوشش نمی‌دهد.
