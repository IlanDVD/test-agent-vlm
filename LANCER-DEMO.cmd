@echo off
setlocal
cd /d "%~dp0"
call "%~dp0agent.cmd" --pas-a-pas
echo.
pause
