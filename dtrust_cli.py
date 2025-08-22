#!/usr/bin/env python3
import sys, os, json, time, glob, platform, datetime
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

def collect_system_info(rootfs="/"):
    """Collect distro, kernel, timestamp for metadata envelope."""
    distro = None
    osrel = os.path.join(rootfs, "etc/os-release")
    if os.path.exists(osrel):
        with open(osrel) as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    distro = line.split("=", 1)[1].strip().strip('"')
                    break
    if not distro:
        distro = platform.system()

    kernel = platform.release()
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "timestamp": ts,
        "system": {
            "distro": distro,
            "kernel": kernel
        }
    }

def read_text(p: Path) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""

def gather_pkg_repos(root: Path):
    """Collect APT and YUM/DNF repo info. (Pacman handled separately.)"""
    repos = {"apt": [], "yum_dnf": []}

    # APT
    sources_list = root / "etc" / "apt" / "sources.list"
    sources_d = root / "etc" / "apt" / "sources.list.d"
    t = read_text(sources_list)
    if t:
        lines = [ln for ln in t.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        repos["apt"].append({"file": str(sources_list), "lines": lines})
    if sources_d.exists() and sources_d.is_dir():
        for f in sorted(sources_d.iterdir()):
            if f.is_file():
                tt = read_text(f) or ""
                lines = [ln for ln in tt.splitlines() if ln.strip() and not ln.strip().startswith("#")]
                repos["apt"].append({"file": str(f), "lines": lines})

    # YUM/DNF
    yumdir = root / "etc" / "yum.repos.d"
    if yumdir.exists() and yumdir.is_dir():
        for f in sorted(yumdir.iterdir()):
            if f.is_file() and f.suffix == ".repo":
                tt = read_text(f) or ""
                repos["yum_dnf"].append({"file": str(f), "content": tt})

    return repos

# --- Arch/Manjaro ---
def gather_pacman_repos(root: Path):
    """
    Collect pacman repo signals:
      - /etc/pacman.conf (raw content + Include targets)
      - /etc/pacman.d/mirrorlist and any included files
        Extract both 'Server = ...' and commented '#Server = ...' lines.
    """
    out = []

    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    includes = []
    conf = root / "etc" / "pacman.conf"
    if conf.exists():
        txt = _read(conf)
        out.append({"file": str(conf), "content": txt})
        for ln in txt.splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if s.lower().startswith("include"):
                parts = s.split("=", 1)
                if len(parts) == 2:
                    pattern = parts[1].strip()
                    pat = str(root / pattern.lstrip("/"))
                    for g in glob.glob(pat):
                        includes.append(Path(g))

    def _extract_servers(text: str):
        servers = []
        for ln in text.splitlines():
            # Accept commented servers too
            t = ln.lstrip().lstrip("#").strip()
            if t.lower().startswith("server"):
                parts = t.split("=", 1)
                if len(parts) == 2:
                    servers.append(parts[1].strip())
        return servers

    for inc in includes:
        itxt = _read(inc)
        out.append({"file": str(inc), "content": itxt})
        sv = _extract_servers(itxt)
        if sv:
            out.append({"file": str(inc), "servers": sv})

    mirror = root / "etc" / "pacman.d" / "mirrorlist"
    if mirror.exists():
        mtxt = _read(mirror)
        sv = _extract_servers(mtxt)
        out.append({"file": str(mirror), "servers": sv})

    return out

def list_path_shadowing(root: Path):
    """Count only meaningful collisions:
       - Different real (st_dev, st_ino), AND
       - At least one path is outside /usr/bin|/usr/sbin, OR
         the files differ by size.
    """
    paths = [
        root/"bin", root/"sbin",
        root/"usr"/"bin", root/"usr"/"sbin",
        root/"usr"/"local"/"bin", root/"usr"/"local"/"sbin",
    ]
    by_name = {}
    for base in paths:
        if not base.exists():
            continue
        try:
            for p in base.iterdir():
                if p.is_file():
                    by_name.setdefault(p.name, []).append(p)
        except Exception:
            continue

    def real_stat(p: Path):
        try:
            rp = Path(os.path.realpath(p)); st = rp.stat()
            return rp, int(st.st_dev), int(st.st_ino), int(st.st_size)
        except Exception:
            return p, None, None, None

    shadows = {}
    for name, plist in by_name.items():
        info = [real_stat(p) for p in plist]
        buckets = {}
        for rp, dev, ino, sz in info:
            buckets.setdefault((dev, ino), []).append((rp, sz))
        buckets.pop((None, None), None)
        if len(buckets) <= 1:
            continue

        # If all under /usr/bin or /usr/sbin and sizes match, ignore (normal dupes)
        all_usr = True
        sizes = set()
        for arr in buckets.values():
            for rp, sz in arr:
                sizes.add(sz)
                s = str(rp)
                if not (s.startswith("/usr/bin/") or s.startswith("/usr/sbin/")):
                    all_usr = False
        if all_usr and len(sizes) == 1:
            continue

        flat = []
        for arr in buckets.values():
            for rp, _ in arr:
                flat.append(str(rp))
        shadows[name] = sorted(set(flat))
    return shadows

def collect_tier2(root: Path, overall_deadline: float):
    now = datetime.now(timezone.utc).isoformat()
    repos = gather_pkg_repos(root)
    pacman_out = gather_pacman_repos(root)
    repos.setdefault('apt', [])
    repos.setdefault('yum_dnf', [])
    repos['pacman'] = pacman_out

    shadows = list_path_shadowing(root)

    manual_dirs = []
    for p in [root / "usr" / "local", root / "opt"]:
        if p.exists() and p.is_dir():
            try:
                entries = [str(x) for x in sorted(p.iterdir())[:200]]
            except Exception:
                entries = []
            manual_dirs.append({"dir": str(p), "entries": entries})

    return {
        "schema_version": SCHEMA_VERSION,
        "tier": 2,
        "timestamp_utc": now,
        "target_rootfs": str(root.resolve()),
        "repos": repos,
        "path_shadowing": shadows,
        "manual_areas": manual_dirs,
    }

def run_tier(rootfs: str, tier: int, max_seconds: int = 15):
    root = Path(rootfs)
    deadline = time.time() + max_seconds
    sysinfo = collect_system_info(rootfs)   # already returns {timestamp, system}

    # base envelope
    base = {
        "schema": SCHEMA_VERSION,   # normalized
        "tier": tier,
        "timestamp": sysinfo.get("timestamp"),
        "system": sysinfo.get("system", {}),
        "target": str(root.resolve())
    }

    if tier == 2:
        tier_data = collect_tier2(root, deadline)
    elif tier == 1:
        repos = gather_pkg_repos(root)
        repos["pacman"] = gather_pacman_repos(root)
        tier_data = {
            "repos": repos
        }
    else:
        raise SystemExit(f"Tiers >2 not implemented yet. Asked: {tier}")

    base.update(tier_data)
    return base

def _main_with_argparse():
    import argparse
    p = argparse.ArgumentParser(description="dtrust CLI (Python)")
    p.add_argument("--tier", type=int, default=1, help="Tier number")
    p.add_argument("--rootfs", default="/", help="Target rootfs to scan")
    p.add_argument("--out", default="-", help="Output file (or '-' for stdout)")
    p.add_argument("--max-seconds", type=int, default=15, help="Overall time budget")
    args = p.parse_args()

    report = run_tier(args.rootfs, args.tier, args.max_seconds)
    data = json.dumps(report, indent=2)
    if args.out == "-" or args.out.strip() == "":
        print(data)
    else:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(data, encoding="utf-8")
        print(f"Wrote report: {outp}")

def main():
    _main_with_argparse()

if __name__ == "__main__":
    main()
