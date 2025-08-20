#!/bin/bash
# modules/tier3.sh

run_tier3_audit() {
  local output_file="$1"
  local distro="$2"
  local host="$3"
  local time="$4"

  echo "[DEBUG] Inside Tier 3"
  echo "[DEBUG] Output: $output_file"
  echo "[DEBUG] Distro: $distro"
  echo "[DEBUG] Hostname: $host"
  echo "[DEBUG] Timestamp: $time"

  set +e

  # 🧠 Capture unusual processes
  unusual_procs=$(ps axo pid,ppid,user,command | awk '$4 ~ /^\// && $4 !~ /^\/(usr|bin|sbin|lib|opt|snap)/')

  # 🐚 Executables found in temp directories
  tmp_binaries=$(find /tmp /dev/shm /home -type f -executable 2>/dev/null)

  # 🌳 Process tree (first 100 lines for readability)
  pstree_snapshot=$(pstree -panU 2>/dev/null | head -n 100)

  # 🌐 Active established network connections
  net_connections=$(ss -tunap 2>/dev/null | grep ESTAB)

  # 📦 JSON list formatter
  json_escape_list() {
    local input="$1"
    if [[ -z "$input" || "$input" =~ ^[[:space:]]*$ ]]; then
      echo ""
      return
    fi

    local result=""
    while IFS= read -r line; do
      line=$(echo "$line" | sed 's/"/\\"/g')
      [[ -n "$line" ]] && result+="\"$line\","
    done <<< "$input"
    echo "${result%,}"
  }

  # Write output
  cat <<EOF > "$output_file"
{
  "distro": "$distro",
  "hostname": "$host",
  "timestamp": "$time",
  "tier": 3,
  "unusual_processes": [$(json_escape_list "$unusual_procs")],
  "executables_in_tmp": [$(json_escape_list "$tmp_binaries")],
  "pstree": $(echo "$pstree_snapshot" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
  "network_established": $(echo "$net_connections" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
}
EOF

  echo "✅ Tier 3 JSON written to: $output_file"
}
