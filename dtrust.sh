#!/usr/bin/env bash
set -Eeuo pipefail

# dtrust.sh — orchestrator wrapper
# Now delegates Tier 1 to the Python CLI for stability and schema consistency.
# Other tiers fall back to legacy modules (if/when added back).

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
CLI="${SCRIPT_DIR}/dtrust_cli.py"

TIER="${TIER:-1}"
OUT="${OUT:-}"
ROOTFS="${ROOTFS:-/}"
MAX_SECONDS="${MAX_SECONDS:-15}"

# Simple getopt-ish parsing (supports both env vars and flags)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="${2:-1}"; shift 2;;
    --out) OUT="${2:-}"; shift 2;;
    --rootfs) ROOTFS="${2:-/}"; shift 2;;
    --max-seconds) MAX_SECONDS="${2:-15}"; shift 2;;
    -h|--help)
      cat <<'EOF'
dtrust.sh — audit orchestrator

Usage:
  ./dtrust.sh [--tier N] [--rootfs PATH] [--out FILE|-] [--max-seconds N]

Environment overrides:
  TIER, ROOTFS, OUT, MAX_SECONDS

Notes:
  - Tier 1 is handled by the Python CLI (dtrust_cli.py) for consistent JSON.
  - Other tiers will print a placeholder until implemented in Python.
EOF
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ "${TIER}" == "1" ]]; then
  # Delegate to Python CLI
  if [[ -z "${OUT}" ]]; then
    exec python3 "${CLI}" --tier 1 --rootfs "${ROOTFS}" --out - --max-seconds "${MAX_SECONDS}"
  else
    exec python3 "${CLI}" --tier 1 --rootfs "${ROOTFS}" --out "${OUT}" --max-seconds "${MAX_SECONDS}"
  fi
else
  echo "Tier ${TIER} not yet implemented in Python CLI. Please use Tier 1 for now." >&2
  exit 3
fi
