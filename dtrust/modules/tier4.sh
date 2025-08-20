#!/bin/bash
# modules/tier4.sh

json_escape_block() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

run_tier4_audit() {
  local output_file="$1"

  echo "[DEBUG] Inside Tier 4"
  echo "[DEBUG] Output file: $output_file"
  echo "[DEBUG] Distro: $DISTRO_NAME"
  echo "[DEBUG] Hostname: $HOSTNAME"
  echo "[DEBUG] Timestamp: $TIMESTAMP"

  set +e

  # 🧪 Rootkit check and audit subsystem status
  rootkit_results=$(chkrootkit 2>/dev/null)
  auditd_status=$(auditctl -s 2>/dev/null)

  # 🧬 Syscall activity snapshot
  syscall_sample=$(timeout 5s strace -c -e trace=execve,connect,open,write,sendto,recvfrom sleep 2 2>&1)

  # 🧠 Collect kernel module hashes
  kmods=$(lsmod | awk 'NR>1 {print $1}')
  mod_hashes=()
  for mod in $kmods; do
    path=$(modinfo -n "$mod" 2>/dev/null)
    if [ -f "$path" ]; then
      sha=$(sha256sum "$path" | awk '{print $1}')
      mod_hashes+=("{\"module\": \"$mod\", \"path\": \"$path\", \"sha256\": \"$sha\"}")
    fi
  done
  mod_hashes_json=$(IFS=,; echo "[${mod_hashes[*]}]")

  # 📁 Audit log sample
  audit_log=""
  if [ -f /var/log/audit/audit.log ]; then
    audit_log=$(grep -iE 'execve|unauthorized|denied' /var/log/audit/audit.log | tail -n 50)
  fi

  # 📝 Bash history
  bash_hist=""
  if [ -f /root/.bash_history ]; then
    bash_hist=$(tail -n 50 /root/.bash_history)
  fi

  # ➕ JSON Output
  echo "[DEBUG] Writing JSON to $output_file"
  cat <<EOF > "$output_file"
{
  "distro": "$DISTRO_NAME",
  "hostname": "$HOSTNAME",
  "timestamp": "$TIMESTAMP",
  "tier": 4,
  "rootkit_scan": $(echo "$rootkit_results" | json_escape_block),
  "auditd_status": $(echo "$auditd_status" | json_escape_block),
  "syscall_trace_sample": $(echo "$syscall_sample" | json_escape_block),
  "kernel_modules": $mod_hashes_json,
  "auditd_log_snippet": $(echo "$audit_log" | json_escape_block),
  "bash_history_snippet": $(echo "$bash_hist" | json_escape_block)
}
EOF

  echo "✅ Tier 4 JSON written to: $output_file"
}
