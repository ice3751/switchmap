Phase 37.2 - Static files fix for Waitress production.

Problem:
The site opens but CSS/JS is not loaded correctly under Waitress with DEBUG=False.

Files changed:
- config/settings.py
- requirements.txt
- scripts/07_vm_fix_static_waitress.cmd

Apply on VM:
1. Stop Waitress window with Ctrl+C.
2. Extract this ZIP into C:\SwitchMap and Replace files.
3. Run:
   cd /d C:\SwitchMap
   scripts\07_vm_fix_static_waitress.cmd
4. Run again:
   scripts\02_vm_run_waitress_manual.cmd
5. Open:
   http://127.0.0.1:8000/
