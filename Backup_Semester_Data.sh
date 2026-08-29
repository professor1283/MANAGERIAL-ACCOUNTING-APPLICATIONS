#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -f data/budget_simulation.db ]; then
  echo "No semester database exists yet. Launch the simulation first."
  exit 1
fi
mkdir -p backups
ts="$(date +%Y%m%d_%H%M%S)"
cp data/budget_simulation.db "backups/budget_simulation_${ts}.db"
echo "Backup created: backups/budget_simulation_${ts}.db"
