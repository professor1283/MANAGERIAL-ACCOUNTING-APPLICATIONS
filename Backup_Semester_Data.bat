@echo off
setlocal
cd /d "%~dp0"
if not exist "data\budget_simulation.db" (
  echo No semester database exists yet. Launch the simulation first.
  pause
  exit /b 1
)
if not exist "backups" mkdir "backups"
powershell -NoProfile -Command "$ts=Get-Date -Format 'yyyyMMdd_HHmmss'; Copy-Item -LiteralPath 'data\budget_simulation.db' -Destination ('backups\budget_simulation_'+$ts+'.db'); Write-Host ('Backup created: backups\budget_simulation_'+$ts+'.db')"
pause
endlocal
