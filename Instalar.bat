@echo off
rem PPF Tester - Desarrollado por Angel Cm (https://angelcm.com)
echo Instalando dependencias de PPF Tester...
python -m pip install --upgrade -r "%~dp0requirements.txt"
if %errorlevel%==0 (
  echo.
  echo Listo. Abre "PPF Tester.bat".
) else (
  echo.
  echo Hubo un error. Verifica que Python este instalado y en el PATH.
)
pause
