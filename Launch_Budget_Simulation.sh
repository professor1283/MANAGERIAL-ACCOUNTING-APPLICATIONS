#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export BUDGET_SIM_HOST="${BUDGET_SIM_HOST:-0.0.0.0}"
export BUDGET_SIM_PORT="${BUDGET_SIM_PORT:-8080}"
python3 server.py
