#!/bin/bash
# modules/tier2.sh

run_tier2_audit() {
  local output_file="$1"

  # 🧠 Capture metadata
  DISTRO_NAME=$(grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '"')
  HOSTNAME=$(hostname)
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  unsigned_packages=""
  third_party_repos=""

  if command -v apt >/dev/null; then
    # 🐧 Debian/Ubuntu
    third_party_repos=$(grep -h -v '^#' /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null \
      | grep -vE "ubuntu|debian|canonical|security.ubuntu" | sort | uniq)

    unsigned_packages=$(apt-mark showmanual 2>/dev/null | while read -r pkg; do
      apt-cache policy "$pkg" | grep -q '***' || echo "$pkg"
    done)

  elif command -v rpm >/dev/null; then
    # 🐧 RHEL/CentOS/Rocky/Fedora
    third_party_repos=$(grep -h -v '^#' /etc/yum.repos.d/*.repo 2>/dev/null \
      | grep -Ei 'baseurl|mirrorlist' | grep -vE "redhat|rocky|centos|fedora" | sort | uniq)

    unsigned_packages=$(rpm -Va --noscripts 2>/dev/null | grep '^..5' | awk '{print $NF}' | sort | uniq)

  elif command -v pacman >/dev/null; then
    # 🐧 Arch
    third_party_repos=$(grep -E '^\[.*\]' /etc/pacman.conf | grep -vE 'core|extra|community|multilib')

    unsigned_packages=$(pacman -Qm 2>/dev/null | awk '{print $1}')

  else
    echo "❌ Unsupported package manager." >&2
    return 1
  fi

  # 🧼 JSON-safe encoding
  up_formatted=$(echo "$unsigned_packages" | sed 's/"/\\"/g' | sed 's/.*/"&"/' | paste -sd,)
  repos_formatted=$(echo "$third_party_repos" | sed 's/"/\\"/g' | sed 's/.*/"&"/' | paste -sd,)

  cat <<EOF > "$output_file"
{
  "distro": "$DISTRO_NAME",
  "hostname": "$HOSTNAME",
  "timestamp": "$TIMESTAMP",
  "tier": 2,
  "unsigned_packages": [${up_formatted}],
  "third_party_repos": [${repos_formatted}]
}
EOF
}
