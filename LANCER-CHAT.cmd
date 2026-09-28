@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto bundled
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 goto launcher
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.10 ou plus est introuvable.
pause
exit /b 1
:bundled
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%~dp0chat_local.py" --ouvrir %*
goto fin
:launcher
py -3 "%~dp0chat_local.py" --ouvrir %*
goto fin
:python
python "%~dp0chat_local.py" --ouvrir %*
:fin
if errorlevel 1 pause
