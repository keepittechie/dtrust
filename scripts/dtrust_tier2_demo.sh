#!/usr/bin/env bash
# dtrust_tier2_demo.sh
# Demo Tier-2 signals (PATH shadowing + manual areas) then clean up.

set -euo pipefail

ROOTFS="${1:-/}"                         # target rootfs (default "/")
OUTDIR="${2:-./reports/demo}"            # where to write tier2.json
PY="${PYTHON:-python3}"                  # override with PYTHON=...
CLI="${CLI:-./dtrust_cli.py}"            # path to your CLI

# Files we create (under ROOTFS)
SHADOW_TARGET="$ROOTFS/usr/local/bin/ls"
WW_FILE="$ROOTFS/usr/local/share/dtrust_demo_ww.txt"

cleanup() {
  echo "[*] Cleaning up demo files..."
  sudo rm -f "$SHADOW_TARGET" || true
  sudo rm -f "$WW_FILE" || true
}
trap cleanup EXIT

echo "[*] Preparing demo artifacts under: $ROOTFS"

# Ensure directories exist
sudo mkdir -p "$ROOTFS/usr/local/bin" "$ROOTFS/usr/local/share"

# 1) Create a shadowed binary earlier in PATH (/usr/local/bin/ls)
# Prefer a tiny compiled ELF if gcc is present; otherwise copy a known ELF.
if command -v gcc >/dev/null 2>&1; then
  echo '[*] gcc found; building tiny ELF to shadow /usr/bin/ls'
  TMPDIR="$(mktemp -d)"
  cat >"$TMPDIR/a.c" <<'EOF'
int main(){return 0;}
EOF
  gcc "$TMPDIR/a.c" -s -o "$TMPDIR/ls"
  sudo mv "$TMPDIR/ls" "$SHADOW_TARGET"
  sudo chmod 0755 "$SHADOW_TARGET"
  rm -rf "$TMPDIR"
else
  echo '[*] gcc not found; copying /bin/echo (ELF on most distros) to shadow /usr/bin/ls'
  sudo cp /bin/echo "$SHADOW_TARGET"
  sudo chmod 0755 "$SHADOW_TARGET"
fi

# 2) Create a world-writable file in /usr/local (manual areas signal)
echo "[*] Creating world-writable file: $WW_FILE"
echo "dtrust demo" | sudo tee "$WW_FILE" >/dev/null
sudo chmod 666 "$WW_FILE"

# 3) Run Tier-2 collection
echo "[*] Running Tier-2 scan..."
mkdir -p "$OUTDIR"
$PY "$CLI" --tier 2 --rootfs "$ROOTFS" --out "$OUTDIR/tier2.json"

# 4) Quick summary (jq may print nulls if a field isn’t present)
echo "[*] Summary (first items for each bucket):"
if command -v jq >/dev/null 2>&1; then
  jq '{
    repo_yum_dnf_first: (.repos.yum_dnf[0] // null),
    repo_apt_first: (.repos.apt[0] // null),
    path_shadowing_first: (.path_shadowing[0] // null),
    manual_usr_local_stats: (.manual_areas["/usr/local"].stats // null),
    unsigned_pkg_first: (.unsigned_packages[0] // null)
  }' "$OUTDIR/tier2.json"
else
  echo "jq not installed; showing raw file path:"
  echo "  -> $OUTDIR/tier2.json"
fi

echo "[*] Demo complete. (Files will be cleaned automatically.)"
