@echo off
setlocal
cd /d "%~dp0"
title Northbridge MBA Budget Simulation

set "PYTHON_EXE=%CD%\runtime\python.exe"
if exist "%PYTHON_EXE%" goto RUN_APP

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_EXE=py -3"
  goto RUN_APP
)

where python >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_EXE=python"
  goto RUN_APP
)

echo A private portable Python runtime is being downloaded from python.org.
echo This occurs only on the first launch and does not install Python in Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\Prepare_Portable_Runtime.ps1"
if not exist "%CD%\runtime\python.exe" (
  echo.
  echo Portable runtime setup failed. Review README.html for manual deployment options.
  pause
  exit /b 1
)
set "PYTHON_EXE=%CD%\runtime\python.exe"

:RUN_APP
%PYTHON_EXE% "%CD%\server.py"
if errorlevel 1 pause
endlocal
