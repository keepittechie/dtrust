#!/usr/bin/env bash
# dtrust_tier2_demo.sh
# Demo Tier-2 signals (PATH shadowing + manual areas) then clean up.

set -euo pipefail

ROOTFS="${1:-/}"                         # target rootfs (default "/")
OUTDIR="${2:-./reports/demo}"            # where to write tier2.json
PY="${PYTHON:-python3}"                  # override with PYTHON=...
CLI="${CLI:-./dtrust_cli.py}"            # path to your CLI
KEEP=${KEEP:-0}                          # set KEEP=1 to skip cleanup

cleanup() {
  if [ "$KEEP" -eq 1 ]; then
    echo "[*] KEEP=1, leaving demo artifacts in place."
    return
  fi
  echo "[*] Cleaning up demo files..."
  sudo rm -f "$ROOTFS/usr/local/bin/ls" \
             "$ROOTFS/usr/local/bin/cat" \
             "$ROOTFS/usr/local/bin/dtrust_demo_elf" \
             "$ROOTFS/usr/local/share/dtrust_demo_ww"*
}
trap cleanup EXIT

echo "[*] Preparing demo artifacts under: $ROOTFS"

# Ensure directories exist
sudo mkdir -p "$ROOTFS/usr/local/bin" "$ROOTFS/usr/local/share"

# 1) Create shadowed binaries earlier in PATH
for bin in ls cat; do
  target="$ROOTFS/usr/local/bin/$bin"
  echo "[*] Creating shadowed binary: $target"
  if command -v gcc >/dev/null 2>&1; then
    TMPDIR="$(mktemp -d)"
    cat >"$TMPDIR/demo_$bin.c" <<EOF
int main(){return 0;}
EOF
    gcc "$TMPDIR/demo_$bin.c" -s -o "$TMPDIR/$bin"
    sudo mv "$TMPDIR/$bin" "$target"
    sudo chmod 0755 "$target"
    rm -rf "$TMPDIR"
  else
    sudo cp /bin/echo "$target"
    sudo chmod 0755 "$target"
  fi
done

# 2) Create world-writable files in /usr/local/share
WW_FILE1="$ROOTFS/usr/local/share/dtrust_demo_ww1.txt"
WW_FILE2="$ROOTFS/usr/local/share/dtrust_demo_ww2.log"
echo "[*] Creating world-writable files: $WW_FILE1 $WW_FILE2"
echo "dtrust demo 1" | sudo tee "$WW_FILE1" >/dev/null
echo "dtrust demo 2" | sudo tee "$WW_FILE2" >/dev/null
sudo chmod 666 "$WW_FILE1" "$WW_FILE2"

# 3) Create a fake ELF binary in /usr/local/bin
FAKE_ELF="$ROOTFS/usr/local/bin/dtrust_demo_elf"
if command -v gcc >/dev/null 2>&1; then
  TMPDIR="$(mktemp -d)"
  cat >"$TMPDIR/fake.c" <<'EOF'
int main(){return 0;}
EOF
  gcc "$TMPDIR/fake.c" -s -o "$TMPDIR/demo_elf"
  sudo mv "$TMPDIR/demo_elf" "$FAKE_ELF"
  sudo chmod 0755 "$FAKE_ELF"
  rm -rf "$TMPDIR"
else
  sudo cp /bin/echo "$FAKE_ELF"
  sudo chmod 0755 "$FAKE_ELF"
fi

# 4) Run Tier-2 collection
echo "[*] Running Tier-2 scan..."
mkdir -p "$OUTDIR"
$PY "$CLI" --tier 2 --rootfs "$ROOTFS" --out "$OUTDIR/tier2.json"

# 5) Quick summary (jq may print nulls if a field isn’t present)
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

echo "[*] Demo complete."
