#!/bin/bash
# modules/tier1.sh

escape_json_string() {
  echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

run_tier1_audit() {
  local output_file="$1"

  # 🧠 Capture distro, hostname, timestamp, kernel
  DISTRO_NAME=$(awk -F= '/^PRETTY_NAME=/{print $2}' /etc/os-release | tr -d '"')
  HOSTNAME=$(hostname)
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  KERNEL=$(uname -r)

  # 🔍 Tier 1 data
  services=$(systemctl list-unit-files | grep enabled | awk '{print $1}' | sort)
  suid_files=$(find / -type f -perm -4000 2>/dev/null | sort)
  cron_jobs=$(find /etc/cron* /var/spool/cron /etc/anacrontab /etc/crontab 2>/dev/null -type f | xargs cat 2>/dev/null)
  net_listeners=$(ss -tulnp 2>/dev/null)
  hidden_files=$(find /root /home /etc /tmp -name ".*" -type f 2>/dev/null | sort)

cat <<EOF > "$output_file"
{
  "distro": "$DISTRO_NAME",
  "hostname": "$HOSTNAME",
  "timestamp": "$TIMESTAMP",
  "kernel": "$KERNEL",
  "tier": 1,
  "services": [$(echo "$services" | sed 's/.*/"&"/' | paste -sd,)],
  "suid_files": [$(echo "$suid_files" | sed 's/.*/"&"/' | paste -sd,)],
  "cron_jobs_snippet": "$(escape_json_string "$(echo "$cron_jobs" | head -c 500)")",
  "listening_ports": "$(escape_json_string "$net_listeners")",
  "hidden_files": [$(echo "$hidden_files" | sed 's/.*/"&"/' | paste -sd,)]
}
EOF
}
