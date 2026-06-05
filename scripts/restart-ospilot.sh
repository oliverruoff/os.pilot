#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${OSPILOT_LOG_FILE:-$ROOT/ospilot.log}"

cd "$ROOT"

load_dotenv() {
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#export }"
    [[ -z "$line" || "${line:0:1}" == "#" || "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$1"
}

if [[ -f "$ROOT/.env" ]]; then
  load_dotenv "$ROOT/.env"
fi

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
  else
    echo "No Python found. Create .venv or install python3." >&2
    exit 1
  fi
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

stop_existing() {
  local pids=""
  pids="$(pgrep -f "python.*-m ospilot\.app" || true)"
  pids="$pids $(pgrep -f "$ROOT/.venv/bin/ospilot" || true)"
  pids="$(tr ' ' '\n' <<<"$pids" | awk -v self="$$" 'NF && $1 != self { print }' | sort -u)"

  if [[ -z "$pids" ]]; then
    return
  fi

  echo "Stopping existing OSPilot process(es): $pids"
  kill $pids 2>/dev/null || true

  for _ in {1..30}; do
    local remaining=""
    for pid in $pids; do
      if ps -p "$pid" >/dev/null 2>&1; then
        remaining="$remaining $pid"
      fi
    done
    if [[ -z "$remaining" ]]; then
      return
    fi
    sleep 0.1
  done

  echo "Force stopping OSPilot process(es): $pids"
  kill -9 $pids 2>/dev/null || true
}

stop_existing

echo "Starting OSPilot from $ROOT"
nohup "$PYTHON" -m ospilot.app >"$LOG_FILE" 2>&1 &
pid="$!"

sleep 0.3
if ps -p "$pid" >/dev/null 2>&1; then
  echo "OSPilot started: pid=$pid log=$LOG_FILE"
else
  echo "OSPilot failed to start. See log: $LOG_FILE" >&2
  exit 1
fi
