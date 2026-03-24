#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
CLI="${SCRIPT_DIR}/dtrust_cli.py"

TIER="${TIER:-1}"
OUT="${OUT:-}"
ROOTFS="${ROOTFS:-/}"
MAX_SECONDS="${MAX_SECONDS:-15}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="${2:-1}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    --rootfs) ROOTFS="${2:-/}"; shift 2 ;;
    --max-seconds) MAX_SECONDS="${2:-15}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
dtrust.sh - audit orchestrator

Usage:
  ./dtrust.sh [--tier N] [--rootfs PATH] [--out FILE|-] [--max-seconds N]

Supported tiers:
  1  Baseline trust signals
  2  Tier 1 plus supply-chain and locality checks
  3  Tier 2 plus advanced-check scaffolding
EOF
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${OUT}" ]]; then
  exec python3 "${CLI}" --tier "${TIER}" --rootfs "${ROOTFS}" --out - --max-seconds "${MAX_SECONDS}"
else
  exec python3 "${CLI}" --tier "${TIER}" --rootfs "${ROOTFS}" --out "${OUT}" --max-seconds "${MAX_SECONDS}"
fi
