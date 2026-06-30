@echo off
netsh advfirewall firewall add rule name="SwitchMap Waitress 8000" dir=in action=allow protocol=TCP localport=8000
