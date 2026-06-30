# SwitchMap Phase 37.1 - VM Deployment

## Scope

This phase prepares deployment to a dedicated internal Windows VM.

Changed/added only:

- VM deployment scripts
- Production env generator
- Deployment ZIP generator
- VM deployment documentation

Not changed:

- Dashboard UI
- Cisco 3850 visual layout
- Nexus visual layout
- Models
- Migrations
- SQLite data
- SSH behavior
- Alarm / SFP / Topology behavior

## Source PC - create deployment ZIP

Run on the current working SwitchMap PC:

```cmd
cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
venv\Scripts\activate
scripts\00_create_vm_deploy_zip.cmd
```

Output:

```text
DEPLOY_ZIP_OK C:\Users\a-mortazavi.WINAC-CO\SwitchMap\deploy\SwitchMap_VM_DEPLOY_YYYYMMDD_HHMMSS.zip
```

Copy this ZIP to the VM.

## VM - recommended base

- Windows Server 2022
- Static IP
- Python 3 installed and available as `py -3`
- Project path recommended: `C:\SwitchMap`

## VM - first install

Extract the deployment ZIP so the final path is:

```text
C:\SwitchMap
```

Then run:

```cmd
cd /d C:\SwitchMap
scripts\01_vm_first_prepare.cmd
```

This script does:

- Create venv if missing
- Install requirements, including Waitress
- Create production `switchmap.env` if missing
- Run migrate
- Run collectstatic
- Run manage.py check
- Run backup check
- Run production check

## VM - run manually

```cmd
cd /d C:\SwitchMap
scripts\02_vm_run_waitress_manual.cmd
```

Local test:

```text
http://127.0.0.1:8000/
```

Network test after firewall rule and ALLOWED_HOSTS update:

```text
http://VM-IP:8000/
```

## VM - firewall rule

Expected result: clients can reach TCP 8000.
Risk: exposes SwitchMap on port 8000 inside the internal network.
Rollback: run `06_vm_close_firewall_8000.cmd`.

```cmd
cd /d C:\SwitchMap
scripts\05_vm_open_firewall_8000.cmd
```

Rollback:

```cmd
cd /d C:\SwitchMap
scripts\06_vm_close_firewall_8000.cmd
```

## VM - daily SQLite backup task

Expected result: daily backup at 23:30.
Risk: if the task user has no permission to project path, backup fails.
Rollback: remove scheduled task.

```cmd
cd /d C:\SwitchMap
scripts\03_vm_install_backup_task.cmd
```

Rollback:

```cmd
cd /d C:\SwitchMap
scripts\04_vm_remove_backup_task.cmd
```

## Production check target output

```text
BACKUP_CHECK_OK ...
PRODUCTION_WARN HTTPS redirect is disabled. This is acceptable only for trusted internal HTTP.
PRODUCTION_CHECK_OK
```

The HTTPS warning is acceptable for trusted internal HTTP.

## Important

Do not install service yet. First confirm:

- Manual Waitress works on the VM
- Login works
- Dashboard loads
- Static files load
- Backup check is OK
- Smoke tests pass if copied
