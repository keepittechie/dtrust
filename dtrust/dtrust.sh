#!/bin/bash
# dtrust.sh - Distro Trust Profiling CLI
# Author: Josh @KeepItTechie
# License: MIT

set -e

TIER=${1:-1}
OUTPUT_DIR="./profiles"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOSTNAME=$(hostname)
DISTRO_NAME=$(grep -oP '(?<=^PRETTY_NAME=).+' /etc/os-release | tr -d '"')

# 🧼 Clean the distro name for filesystem-safe JSON names
SAFE_DISTRO_NAME=$(echo "$DISTRO_NAME" | sed 's/[][(){}\/\\:;*?"<>|]/_/g' | tr ' ' '_' | tr -s '_')
FILENAME="${OUTPUT_DIR}/${SAFE_DISTRO_NAME}-${TIMESTAMP}.json"

# Create output directory if needed
mkdir -p "$OUTPUT_DIR"

case "$TIER" in
  --tier1|1)
    export DISTRO_NAME HOSTNAME TIMESTAMP
    source ./modules/tier1.sh
    run_tier1_audit "$FILENAME"
    echo "✅ Tier 1 audit complete. Report saved to: $FILENAME"
    ;;
  --tier2|2)
    export DISTRO_NAME HOSTNAME TIMESTAMP
    source ./modules/tier2.sh
    run_tier2_audit "$FILENAME"
    echo "✅ Tier 2 audit complete. Report saved to: $FILENAME"
    ;;
  --tier3|3)
    export DISTRO_NAME HOSTNAME TIMESTAMP
    source ./modules/tier3.sh
    run_tier3_audit "${FILENAME%.json}-tier3.json" "$DISTRO_NAME" "$HOSTNAME" "$TIMESTAMP"
    echo "✅ Tier 3 audit complete. Report saved to: ${FILENAME%.json}-tier3.json"
    ;;
  --tier4|4)
    export DISTRO_NAME HOSTNAME TIMESTAMP
    source ./modules/tier4.sh
    run_tier4_audit "${FILENAME%.json}-tier4.json"
    echo "✅ Tier 4 audit complete. Report saved to: ${FILENAME%.json}-tier4.json"
    ;;
  --tier5|5)
    ROOT_ARG="$2"
    if [ -z "$ROOT_ARG" ]; then
      echo "Usage: $0 --tier5 /mnt/suspect"
      exit 1
    fi
    export DISTRO_NAME HOSTNAME TIMESTAMP
    source ./modules/tier5.sh
    run_tier5_audit "$ROOT_ARG" "$FILENAME"
    echo "✅ Tier 5 audit complete. Report saved to: $FILENAME"
    ;;
  --tier-all|all)
    export DISTRO_NAME HOSTNAME TIMESTAMP

    source ./modules/tier1.sh
    run_tier1_audit "${FILENAME%.json}-tier1.json"
    echo "✅ Tier 1 audit saved to ${FILENAME%.json}-tier1.json"

    source ./modules/tier2.sh
    run_tier2_audit "${FILENAME%.json}-tier2.json"
    echo "✅ Tier 2 audit saved to ${FILENAME%.json}-tier2.json"

    source ./modules/tier3.sh
    run_tier3_audit "${FILENAME%.json}-tier3.json" "$DISTRO_NAME" "$HOSTNAME" "$TIMESTAMP"
    echo "✅ Tier 3 audit saved to ${FILENAME%.json}-tier3.json"

    source ./modules/tier4.sh
    run_tier4_audit "${FILENAME%.json}-tier4.json"
    echo "✅ Tier 4 audit saved to ${FILENAME%.json}-tier4.json"

    echo "✅ All audit tiers complete. Reports saved to: ${FILENAME%.json}-tier*.json"
    ;;
  --help|-h)
    echo "Usage: $0 [--tier1|--tier2|--tier3|--tier4|--tier5 /path|--tier-all]"
    echo "Runs the DistroTrust audit for a specific tier or all tiers."
    exit 0
    ;;
  *)
    echo "Usage: $0 [--tier1|--tier2|--tier3|--tier4|--tier5 /path|--tier-all]"
    exit 1
    ;;
esac
