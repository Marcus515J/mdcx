@echo off
setlocal
chcp 65001 >nul
title MDCx Hy-MT2
if not exist "%~dp0start-local-hymt2.ps1" goto missing
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local-hymt2.ps1" -FromLauncher %*
set "MDCX_LAUNCH_RESULT=%ERRORLEVEL%"
goto finish
:missing
echo 找不到启动脚本。请先解压整个 ZIP，再双击 Start-HyMT2.cmd。
set "MDCX_LAUNCH_RESULT=1"
:finish
echo.
echo 本窗口会保留到你按键关闭。错误日志位于启动包的 logs 文件夹。
pause
exit /b %MDCX_LAUNCH_RESULT%
