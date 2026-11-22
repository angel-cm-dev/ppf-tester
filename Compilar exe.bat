@echo off
rem Compila PPF-Tester.exe localmente (carpeta dist\)
python -m pip install --upgrade pyinstaller -r "%~dp0requirements.txt"
python "%~dp0build.py"
pause
