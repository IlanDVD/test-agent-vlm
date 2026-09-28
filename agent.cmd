@echo off
setlocal
set "PYTHONUTF8=1"
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto bundled
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 goto launcher
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.10 ou plus est introuvable. Consultez GUIDE.md.
exit /b 1
:bundled
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%~dp0agent.py" %*
exit /b %errorlevel%
:launcher
py -3 "%~dp0agent.py" %*
exit /b %errorlevel%
:python
python "%~dp0agent.py" %*
exit /b %errorlevel%
