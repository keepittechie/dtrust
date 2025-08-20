#!/bin/bash
# json-to-md.sh - Convert dtrust JSON reports to readable Markdown with scoring

INPUT="$1"
[ -z "$INPUT" ] && echo "Usage: $0 report.json" && exit 1
[ ! -f "$INPUT" ] && echo "File not found: $INPUT" && exit 1

DISTRO=$(jq -r .distro "$INPUT" 2>/dev/null || echo "Unknown")
HOST=$(jq -r .hostname "$INPUT" 2>/dev/null || echo "N/A")
DATE=$(jq -r .timestamp "$INPUT")
TIER=$(jq -r .tier "$INPUT")
SCORE=100
PENALTIES=()

deduct() {
  local pts="$1"
  local msg="$2"
  SCORE=$(( SCORE - pts ))
  PENALTIES+=("-${pts}: $msg")
}

case "$TIER" in
  1)
    HIDDEN=$(jq '.hidden_files | length' "$INPUT")
    [ "$HIDDEN" -gt 0 ] && deduct "$(( HIDDEN * 5 < 20 ? HIDDEN * 5 : 20 ))" "$HIDDEN hidden dotfiles"
    SUID=$(jq '.suid_files | length' "$INPUT")
    [ "$SUID" -gt 0 ] && deduct "$(( SUID * 3 < 15 ? SUID * 3 : 15 ))" "$SUID SUID files"
    ;;
  2)
    UNSIGNED=$(jq '.unsigned_packages | length' "$INPUT")
    [ "$UNSIGNED" -gt 0 ] && deduct "$(( UNSIGNED * 10 ))" "$UNSIGNED unsigned packages"
    REPOS=$(jq '.third_party_repos | length' "$INPUT")
    [ "$REPOS" -gt 0 ] && deduct "$(( REPOS * 15 ))" "$REPOS third-party repos"
    ;;
  3)
    PROCS=$(jq '.unusual_processes | length' "$INPUT")
    [ "$PROCS" -gt 0 ] && deduct "$(( PROCS * 15 ))" "$PROCS unusual processes"
    ;;
  4)
    if jq -r '.rootkit_scan' "$INPUT" | grep -iq 'infected\|found'; then
      deduct 30 "Possible rootkit found"
    fi
    ;;
  5)
    IMPLANTS=$(jq '.implant_detections | length' "$INPUT")
    [ "$IMPLANTS" -gt 0 ] && deduct "$(( IMPLANTS * 20 ))" "$IMPLANTS binary implant(s)"
    SUID=$(jq '.suid_sgid_binaries | length' "$INPUT")
    [ "$SUID" -gt 0 ] && deduct "$(( SUID * 3 < 15 ? SUID * 3 : 15 ))" "$SUID SUID/SGID binaries"
    HIDDEN=$(jq '.hidden_files_outside_home | length' "$INPUT")
    [ "$HIDDEN" -gt 0 ] && deduct "$(( HIDDEN * 5 < 20 ? HIDDEN * 5 : 20 ))" "$HIDDEN hidden dotfiles"
    if jq -r '.tamper_log_snippet' "$INPUT" | grep -iq 'failed\|unauthorized'; then
      deduct 10 "Suspicious auth log entries"
    fi
    ;;
esac

[ "$SCORE" -lt 10 ] && SCORE=10

OUTPUT="report-$(basename "$INPUT" .json).md"

{
echo "# Trust Report for $DISTRO"
echo "**Hostname:** $HOST"
echo "**Generated:** $DATE"
echo "**Audit Tier:** $TIER"
echo "**Trust Score:** $SCORE/100"
echo ""

echo "## Risk Summary"
if [ "${#PENALTIES[@]}" -eq 0 ]; then
  echo "_No major issues detected._"
else
  for p in "${PENALTIES[@]}"; do echo "- $p"; done
fi

echo ""

# Tier-specific sections...
case "$TIER" in
  1)
    echo "## Tier 1 Audit (Basic)"
    echo "**Enabled Services:**"
    jq -r '.services[]' "$INPUT" | sed 's/^/- /'
    echo ""
    echo "**SUID Files:**"
    jq -r '.suid_files[]' "$INPUT" | sed 's/^/- /'
    echo ""
    echo "**Cron Snippet:**"
    echo '```'
    jq -r '.cron_jobs_snippet' "$INPUT"
    echo '```'
    echo ""
    echo "**Listening Ports:**"
    echo '```'
    jq -r '.listening_ports' "$INPUT"
    echo '```'
    echo ""
    echo "**Hidden Files:**"
    jq -r '.hidden_files[]' "$INPUT" | sed 's/^/- /'
    ;;
  2)
    echo "## Tier 2 Audit (Integrity & Origin)"
    echo "**Third-Party Repositories:**"
    jq -r '.third_party_repos[]' "$INPUT" | sed 's/^/- /'
    echo ""
    echo "**Unsigned Packages:**"
    jq -r '.unsigned_packages[]' "$INPUT" | sed 's/^/- /'
    ;;
  3)
    echo "## Tier 3 Audit (Runtime Suspicion)"
    echo "**Unusual Processes:**"
    jq -r '.unusual_processes[]' "$INPUT" | sed 's/^/- /'
    ;;
  4)
    echo "## Tier 4 Audit (Rootkit/Tracing)"
    echo "**Rootkit Scan Result:**"
    echo '```'
    jq -r '.rootkit_scan' "$INPUT"
    echo '```'
    echo "**System Calls Snapshot:**"
    echo '```'
    jq -r '.syscall_trace_sample' "$INPUT"
    echo '```'
    ;;
  5)
    echo "## Tier 5 Audit (Offline Disk Scan)"
    echo "**SUID/SGID Binaries:**"
    jq -r '.suid_sgid_binaries[]' "$INPUT" | sed 's/^/- /'
    echo ""
    echo "**Hidden Dotfiles (outside /home):**"
    jq -r '.hidden_files_outside_home[]' "$INPUT" | sed 's/^/- /'
    echo ""
    echo "**Binary Implant Detections:**"
    jq -r '.implant_detections[]' "$INPUT" | sed 's/^/- /'
    ;;
esac

} > "$OUTPUT"

echo "Markdown report saved to: $OUTPUT"
