@echo off
rem PPF Tester - Desarrollado por Angel Cm (https://angelcm.com)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0ppf_tester\qt_main.py" %*
) else (
  start "" pyw -3 "%~dp0ppf_tester\qt_main.py" %*
)
