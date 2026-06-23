SwitchMap Phase 37.1 - VM Deploy Prep

Apply this patch on the current SwitchMap project.

Path:
C:\Users\a-mortazavi.WINAC-CO\SwitchMap

After Extract + Replace, run:

cd /d C:\Users\a-mortazavi.WINAC-CO\SwitchMap
venv\Scripts\activate
python manage.py check
scripts\00_create_vm_deploy_zip.cmd

Then copy the generated ZIP from deploy\ to the new VM.
