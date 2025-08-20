#!/bin/bash
# modules/tier5.sh

run_tier5_audit() {
  local rootfs="$1"
  local output_file="$2"
  local baseline_file="./baselines/core_binary_hashes.sha256"

  if [ ! -d "$rootfs/etc" ]; then
    echo "ERROR: '$rootfs' does not appear to be a valid Linux root filesystem."
    exit 1
  fi

  # Hidden dotfiles outside of user home
  hidden_files=$(find "$rootfs" -type f -name ".*" -not -path "$rootfs/home/*" 2>/dev/null | sort)

  # Unlinked binaries or suspicious setuid/setgid files
  suid_files=$(find "$rootfs" -xdev -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | sort)

  # Check for unauthorized user accounts
  passwd_entries=$(cat "$rootfs/etc/passwd" | awk -F: '$3 >= 1000 { print $1 ":" $3 ":" $7 }' | sort)

  # Compare against known binary hashes (if baseline exists)
  bin_hashes=""
  implant_warnings=""
  for bin in "$rootfs/bin/"* "$rootfs/sbin/"* "$rootfs/usr/bin/"*; do
    [ -f "$bin" ] || continue
    sha=$(sha256sum "$bin" | awk '{print $1}')
    relpath="${bin#$rootfs}"
    bin_hashes+="{\"path\": \"$relpath\", \"sha256\": \"$sha\"},"

    # Check against baseline
    if [ -f "$baseline_file" ]; then
      baseline_sha=$(grep " $relpath\$" "$baseline_file" | awk '{print $1}')
      if [ -n "$baseline_sha" ] && [ "$baseline_sha" != "$sha" ]; then
        implant_warnings+="$relpath (modified);"
      fi
    fi
  done
  bin_hashes="[${bin_hashes%,}]"
  implant_warnings="[\"$(echo "$implant_warnings" | tr ';' '\n' | sed '/^$/d' | sed 's/.*/&"/' | paste -sd,)]"

  # Log analysis (tampering signs)
  tamper_logs=""
  if [ -f "$rootfs/var/log/auth.log" ]; then
    tamper_logs=$(grep -iE 'failed|invalid|unauthorized|root login' "$rootfs/var/log/auth.log" | tail -n 50)
  elif [ -f "$rootfs/var/log/secure" ]; then
    tamper_logs=$(grep -iE 'failed|invalid|unauthorized|root login' "$rootfs/var/log/secure" | tail -n 50)
  fi

  cat <<EOF > "$output_file"
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "tier": 5,
  "scanned_root": "$rootfs",
  "hidden_files_outside_home": [$(echo "$hidden_files" | sed 's/'"$rootfs"'\///' | sed 's/.*/"&"/' | paste -sd,)],
  "suid_sgid_binaries": [$(echo "$suid_files" | sed 's/'"$rootfs"'\///' | sed 's/.*/"&"/' | paste -sd,)],
  "user_accounts": [$(echo "$passwd_entries" | sed 's/.*/"&"/' | paste -sd,)],
  "core_binary_hashes": $bin_hashes,
  "implant_detections": $implant_warnings,
  "tamper_log_snippet": "$(echo "$tamper_logs" | sed 's/"/\\"/g')"
}
EOF
}
