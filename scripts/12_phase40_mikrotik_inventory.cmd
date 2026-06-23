@echo off
setlocal
cd /d C:\SwitchMap
C:\SwitchMap\venv\Scripts\python.exe manage.py migrate
C:\SwitchMap\venv\Scripts\python.exe manage.py seed_mikrotik_devices
C:\SwitchMap\venv\Scripts\python.exe manage.py check
C:\SwitchMap\venv\Scripts\python.exe switchmap_40_mikrotik_inventory_topology_smoke_test.py
echo PHASE40_APPLY_OK
endlocal
