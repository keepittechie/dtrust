#!/usr/bin/env python3
import sys, os, json, time, glob, platform
import re
from datetime import datetime, timezone
from pathlib import Path
import hashlib, stat
from typing import Optional, Tuple

def sha256_file(p: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def is_elf(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:
        return False

def file_mode_owner(p: Path) -> Tuple[str, str]:
    try:
        st = p.stat()
        mode = stat.S_IMODE(st.st_mode)
        mode_str = f"{mode:04o}"
        try:
            import pwd, grp
            owner = f"{pwd.getpwuid(st.st_uid).pw_name}:{grp.getgrgid(st.st_gid).gr_name}"
        except Exception:
            owner = f"{st.st_uid}:{st.st_gid}"
        return mode_str, owner
    except Exception:
        return "0000", "?:?"

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
    ts = datetime.now(timezone.utc).isoformat()

    return {
        "timestamp": ts,
        "system": {
            "distro": distro,
            "kernel": kernel
        }
    }

def collect_unsigned_packages(root: Path):
    """
    Tries to call your existing unsigned-package collector if present,
    otherwise returns [] safely so reports still render.
    """
    try:
        # if you have a module, e.g., dtrust/pkg_unsigned.py with collect(root: Path)
        from dtrust import pkg_unsigned  # adapt if your module path differs
        return pkg_unsigned.collect(root)
    except Exception:
        return []


def read_text(p: Path) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""

def gather_pkg_repos(root: Path):
    """Collect normalized repo data for APT and YUM/DNF. (Pacman handled separately.)"""
    repos = {"apt": [], "yum_dnf": []}

    # --- APT ---
    sources_list = root / "etc" / "apt" / "sources.list"
    sources_d = root / "etc" / "apt" / "sources.list.d"
    line_re = re.compile(r"^\s*deb(-src)?\s+(\[[^\]]+\]\s+)?(\S+)\s+(\S+)\s+(.*)$")

    def _parse_apt_file(f: Path):
        t = read_text(f) or ""
        for line in t.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            m = line_re.match(line)
            if not m:
                continue
            is_src = bool(m.group(1))
            opts = (m.group(2) or "").strip()
            url = m.group(3); suite = m.group(4)
            comps = (m.group(5) or "").split()
            repos["apt"].append({
                "file": str(f),
                "name": f"{suite}{'-src' if is_src else ''}",
                "enabled": True,            # non-commented line
                "baseurl": url,
                "mirrorlist": None,
                "gpgcheck": True,           # apt verifies by default w/ keyrings
                "gpgkey_files": [],         # apt keyrings are system-managed
                "components": comps,
                "options": opts,
            })

    if sources_list.exists():
        _parse_apt_file(sources_list)
    if sources_d.exists() and sources_d.is_dir():
        for f in sorted(sources_d.glob("*.list")):
            _parse_apt_file(f)

    # --- YUM/DNF ---
    yumdir = root / "etc" / "yum.repos.d"
    if yumdir.exists() and yumdir.is_dir():
        for f in sorted(yumdir.glob("*.repo")):
            body = read_text(f) or ""
            # split on [section]
            parts = re.split(r"\n\[(.+?)\]\s*\n", "\n"+body)
            for i in range(1, len(parts), 2):
                name = parts[i].strip()
                section = parts[i+1]
                def get(k, default=None):
                    m = re.search(rf"^{k}\s*=\s*(.+)$", section, re.M|re.I)
                    return (m.group(1).strip() if m else default)
                enabled = (get("enabled","1") == "1")
                gpgcheck = (get("gpgcheck","1") == "1")
                baseurl = get("baseurl")
                mirrorlist = get("mirrorlist")
                gpgkey = get("gpgkey") or ""
                gpgkey_files = []
                if gpgkey:
                    for part in re.split(r"[\s,]+", gpgkey.strip()):
                        if part.startswith("file:"):
                            p = part.replace("file://","file:").replace("file:","")
                            if p:
                                gpgkey_files.append(p)
                repos["yum_dnf"].append({
                    "file": str(f),
                    "name": name,
                    "enabled": enabled,
                    "baseurl": baseurl,
                    "mirrorlist": mirrorlist,
                    "gpgcheck": gpgcheck,
                    "gpgkey_files": gpgkey_files
                })

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
    """Return entries with first_hit vs shadowed + sha256 for each."""
    path_dirs = [
        root/"usr"/"local"/"sbin", root/"usr"/"local"/"bin",
        root/"usr"/"sbin", root/"usr"/"bin",
        root/"sbin", root/"bin",
    ]
    by_name = {}
    for base in path_dirs:
        if not base.exists():
            continue
        try:
            for p in base.iterdir():
                if p.is_file():
                    by_name.setdefault(p.name, []).append(p)
        except Exception:
            continue

    results = []
    for name, plist in by_name.items():
        # remove exact same real file duplicates
        uniq = []
        seen = set()
        for p in plist:
            rp = Path(os.path.realpath(p))
            try:
                st = rp.stat()
                key = (int(st.st_dev), int(st.st_ino))
            except Exception:
                key = (str(rp), None)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(rp)
        if len(uniq) <= 1:
            continue
        first = uniq[0]
        shadowed = uniq[1:]
        results.append({
            "basename": name,
            "first_hit": str(first),
            "shadowed": [str(x) for x in shadowed],
            "first_hit_sha256": sha256_file(first),
            "shadowed_sha256": [sha256_file(x) for x in shadowed],
        })
    return results

def scan_dir_dtrust(root: Path, limit: int = 6000):
    entries = []
    files = dirs = ww = elf = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for d in dirnames:
            p = Path(dirpath) / d
            try:
                _ = p.stat()
                dirs += 1
            except Exception:
                continue
        for f in filenames:
            if count >= limit:
                break
            p = Path(dirpath) / f
            try:
                st = p.stat()
                mode_str, owner = file_mode_owner(p)
                ww_bit = bool(stat.S_IMODE(st.st_mode) & 0o002)
                if ww_bit: ww += 1
                elf_bit = is_elf(p)
                if elf_bit: elf += 1
                files += 1
                count += 1
                entries.append({
                    "path": str(p),
                    "type": "file",
                    "mode": mode_str,
                    "owner": owner,
                    "size": st.st_size,
                    "elf": elf_bit,
                    "w_world": ww_bit,
                    "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat(),
                })
            except Exception:
                continue
        if count >= limit:
            break
    return {
        "entries": entries,
        "stats": {"files": files, "dirs": dirs, "world_writable": ww, "elf_binaries": elf}
    }

def collect_manual_areas(root: Path):
    out = {}
    for p in (root / "usr" / "local", root / "opt"):
        key = "/" + str(p.relative_to(root))
        if p.exists() and p.is_dir():
            out[key] = scan_dir_dtrust(p, limit=6000)
        else:
            out[key] = {"entries": [], "stats": {"files":0,"dirs":0,"world_writable":0,"elf_binaries":0}}
    return out

def collect_tier2(root: Path, overall_deadline: float):
    # Repos
    repos = gather_pkg_repos(root)
    repos["pacman"] = gather_pacman_repos(root)  # keep your existing pacman routine

    # Unsigned packages (safe no-op if module missing)
    unsigned = collect_unsigned_packages(root)

    # PATH shadowing (rich)
    shadowing = list_path_shadowing(root)

    # Manual areas (/usr/local, /opt)
    manual = collect_manual_areas(root)

    return {
        "repos": repos,
        "unsigned_packages": unsigned,
        "path_shadowing": shadowing,
        "manual_areas": manual,
    }

def run_tier(rootfs: str, tier: int, max_seconds: int = 15):
    root = Path(rootfs)
    deadline = time.time() + max_seconds
    sysinfo = collect_system_info(rootfs)

    base = {
        "schema": SCHEMA_VERSION,
        "tier": tier,
        "timestamp": sysinfo.get("timestamp"),
        "system": sysinfo.get("system", {}),
        "target": str(root.resolve()),
    }

    if tier == 2:
        tier_data = collect_tier2(root, deadline)
    elif tier == 1:
        # keep Tier-1 functional so --tier 1 doesn’t crash
        repos = gather_pkg_repos(root)
        repos["pacman"] = gather_pacman_repos(root)
        tier_data = {"repos": repos}
    else:
        raise SystemExit(f"Tiers > 2 not implemented yet. Asked: {tier}")

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
