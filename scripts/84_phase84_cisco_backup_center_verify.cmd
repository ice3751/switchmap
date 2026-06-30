@echo off
setlocal
cd /d C:\SwitchMap
set PYTHONPATH=C:\SwitchMap
set DJANGO_SETTINGS_MODULE=config.settings
python manage.py check || goto :fail
python scripts\84_phase84_cisco_backup_center_apply.py || goto :fail
python manage.py check || goto :fail
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import django; django.setup(); from django.urls import reverse; names=['cisco_backup_center','cisco_backup_run','cisco_backup_batch','cisco_backup_detail','cisco_backup_download','cisco_backup_validate_restore']; [print('URL_OK', n, reverse('inventory:'+n, kwargs={'backup_id':'test'}) if 'detail' in n or 'download' in n or 'validate' in n else reverse('inventory:'+n)) for n in names]; from inventory.cisco_backup_tools import COMMANDS, setup_storage; setup_storage(); print('COMMANDS_OK', ','.join(sorted(COMMANDS)))" || goto :fail
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import django; django.setup(); from django.test import Client; c=Client(HTTP_HOST='it-tools.winac-co.com:8000'); paths=['/cisco-backups/','/']; [print('HTTP_OK', p, c.get(p).status_code) for p in paths]" || goto :fail
schtasks /End /TN "SwitchMap Waitress"
timeout /t 3
schtasks /Run /TN "SwitchMap Waitress" || goto :fail
echo PHASE84_CISCO_BACKUP_CENTER_VERIFY_OK
exit /b 0
:fail
echo PHASE84_CISCO_BACKUP_CENTER_VERIFY_FAIL
exit /b 1
