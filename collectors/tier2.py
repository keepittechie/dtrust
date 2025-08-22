# dtrust/collectors/tier2.py
from __future__ import annotations
import os, re, json, hashlib, time, stat
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------- utilities ----------
def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

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

def path_list_from_env(rootfs: Path) -> List[Path]:
    # Try /etc/environment PATH or fall back to a sane default
    default = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    paths = []
    etc_env = rootfs / "etc/environment"
    env_path = None
    if etc_env.exists():
        txt = etc_env.read_text(errors="ignore")
        m = re.search(r'PATH\s*=\s*"?([^"\n]+)"?', txt)
        if m: env_path = m.group(1)
    if not env_path:
        env_path = default
    for p in env_path.split(":"):
        pp = (rootfs / p.lstrip("/")).resolve()
        paths.append(pp)
    return [p for p in paths if p.is_dir()]

def detect_distro(rootfs: Path) -> Dict:
    osrel = rootfs / "etc/os-release"
    data = {}
    if osrel.exists():
        for line in osrel.read_text(errors="ignore").splitlines():
            if "=" in line:
                k,v = line.split("=",1)
                v = v.strip().strip('"')
                data[k] = v
    return {
        "id": data.get("ID") or "?",
        "version": data.get("VERSION_ID") or "?",
        "like": (data.get("ID_LIKE") or "").split()
    }

# ---------- repo collectors ----------
def collect_dnf_repos(rootfs: Path) -> List[Dict]:
    repos = []
    repodir = rootfs / "etc/yum.repos.d"
    for f in sorted(repodir.glob("*.repo")):
        txt = f.read_text(errors="ignore") if f.exists() else ""
        blocks = re.split(r"\n\[(.+?)\]\s*\n", "\n"+txt)
        # blocks like: ['', 'appstream', 'key=val\n...', 'baseos', 'key=val\n...']
        for i in range(1, len(blocks), 2):
            name = blocks[i].strip()
            body = blocks[i+1]
            def get(k, default=None):
                m = re.search(rf"^{k}\s*=\s*(.+)$", body, re.M|re.I)
                return (m.group(1).strip() if m else default)
            enabled = (get("enabled","1") == "1")
            gpgcheck = (get("gpgcheck","1") == "1")
            baseurl = get("baseurl")
            mirrorlist = get("mirrorlist")
            gpgkey = get("gpgkey")
            gpgkey_files = []
            if gpgkey:
                # gpgkey can be a list
                for part in re.split(r"\s*[,\s]\s*", gpgkey.strip()):
                    if part.startswith("file:"):
                        p = part.replace("file://","file:").replace("file:","")
                        if p: gpgkey_files.append(p)
            repos.append({
                "manager":"dnf","name":name,"enabled":enabled,
                "baseurl":baseurl,"mirrorlist":mirrorlist,
                "gpgcheck":gpgcheck,"gpgkey_files":gpgkey_files,"file":str(f)
            })
    return repos

def collect_apt_repos(rootfs: Path) -> List[Dict]:
    repos = []
    sources = [rootfs/"etc/apt/sources.list"]
    d = rootfs/"etc/apt/sources.list.d"
    if d.is_dir():
        sources += sorted(d.glob("*.list"))
    line_re = re.compile(r"^\s*deb(-src)?\s+(\[[^\]]+\]\s+)?(\S+)\s+(\S+)\s+(.*)$")
    for f in sources:
        if not f.exists(): continue
        for line in f.read_text(errors="ignore").splitlines():
            if line.strip().startswith("#") or not line.strip(): continue
            m = line_re.match(line)
            if not m: continue
            is_src = bool(m.group(1))
            opts = m.group(2) or ""
            url = m.group(3); suite = m.group(4)
            comps = (m.group(5) or "").split()
            enabled = not line.strip().startswith("#")
            gpgcheck = True  # apt always verifies by default if keyrings installed
            repos.append({
                "manager":"apt","name":f"{suite}{'-src' if is_src else ''}",
                "enabled":enabled,"baseurl":url,"mirrorlist":None,
                "gpgcheck":gpgcheck,"gpgkey_files":[], "file":str(f),
                "components": comps, "options": opts.strip()
            })
    return repos

def collect_pacman_repos(rootfs: Path) -> List[Dict]:
    conf = rootfs/"etc/pacman.conf"
    if not conf.exists(): return []
    txt = conf.read_text(errors="ignore")
    repos = []
    blocks = re.split(r"\n\[(.+?)\]\s*\n", "\n"+txt)
    for i in range(1, len(blocks), 2):
        name = blocks[i].strip()
        body = blocks[i+1]
        servers = re.findall(r"^Server\s*=\s*(.+)$", body, re.M)
        siglevel = re.search(r"^SigLevel\s*=\s*(.+)$", body, re.M)
        gpgcheck = True
        if siglevel and "Never" in siglevel.group(1):
            gpgcheck = False
        enabled = True  # sections present imply enabled unless Include toggles say otherwise
        repos.append({
            "manager":"pacman","name":name,"enabled":enabled,
            "baseurl": servers[0] if servers else None,
            "mirrorlist": None, "gpgcheck": gpgcheck,
            "gpgkey_files": [], "file": str(conf)
        })
    return repos

def collect_repos(rootfs: Path) -> List[Dict]:
    out = []
    out += collect_dnf_repos(rootfs)
    out += collect_apt_repos(rootfs)
    out += collect_pacman_repos(rootfs)
    return out

# ---------- unsigned packages (existing hook) ----------
def collect_unsigned_packages(rootfs: Path) -> List[Dict]:
    # Leave your existing implementation; keep this shim.
    # If not available, return [] to avoid breaking.
    try:
        from dtrust.collectors.pkg_unsigned import collect as _collect
        return _collect(rootfs)
    except Exception:
        return []

# ---------- PATH shadowing ----------
def collect_path_shadowing(rootfs: Path) -> List[Dict]:
    paths = path_list_from_env(rootfs)
    # Map basename -> list of full paths (in PATH order)
    seen: Dict[str, List[Path]] = {}
    for p in paths:
        try:
            for child in p.iterdir():
                if not child.is_file():
                    continue
                b = child.name
                seen.setdefault(b, [])
                # keep unique (avoid duplicates via symlinks pointing to same file)
                if child not in seen[b]:
                    seen[b].append(child)
        except Exception:
            continue
    result = []
    for basename, lst in seen.items():
        if len(lst) <= 1:
            continue
        first = lst[0]
        shadowed = lst[1:]
        entry = {
            "basename": basename,
            "first_hit": str(first),
            "shadowed": [str(x) for x in shadowed],
            "first_hit_sha256": sha256_file(first),
            "shadowed_sha256": [sha256_file(x) for x in shadowed]
        }
        result.append(entry)
    return result

# ---------- manual areas ----------
def scan_dir(root: Path, limit: int = 5000) -> Dict:
    entries = []
    files = dirs = ww = elf = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # guardrails
        if count > limit:
            break
        # dirs
        for d in dirnames:
            p = Path(dirpath) / d
            try:
                st = p.stat()
            except Exception:
                continue
            dirs += 1
        # files
        for f in filenames:
            p = Path(dirpath) / f
            count += 1
            if count > limit:
                break
            try:
                st = p.stat()
                mode_str, owner = file_mode_owner(p)
                ww_bit = bool(stat.S_IMODE(st.st_mode) & 0o002)
                if ww_bit: ww += 1
                elf_bit = is_elf(p)
                if elf_bit: elf += 1
                files += 1
                entries.append({
                    "path": str(p),
                    "type": "file",
                    "mode": mode_str,
                    "owner": owner,
                    "size": st.st_size,
                    "elf": elf_bit,
                    "w_world": ww_bit,
                    "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()
                })
            except Exception:
                continue
    return {
        "entries": entries,
        "stats": {"files": files, "dirs": dirs, "world_writable": ww, "elf_binaries": elf}
    }

def collect_manual_areas(rootfs: Path) -> Dict[str, Dict]:
    areas = {}
    for p in ("/usr/local", "/opt"):
        pp = (rootfs / p.lstrip("/"))
        if pp.exists() and pp.is_dir():
            areas[p] = scan_dir(pp, limit=6000)
        else:
            areas[p] = {"entries": [], "stats": {"files":0,"dirs":0,"world_writable":0,"elf_binaries":0}}
    return areas

# ---------- main entry ----------
def collect(rootfs_str: str = "/") -> Dict:
    rootfs = Path(rootfs_str)
    return {
        "schema_version": "2.0.0",
        "tier": 2,
        "timestamp_utc": utc_now(),
        "target_rootfs": rootfs_str,
        "distro": detect_distro(rootfs),
        "repos": collect_repos(rootfs),
        "unsigned_packages": collect_unsigned_packages(rootfs),
        "path_shadowing": collect_path_shadowing(rootfs),
        "manual_areas": collect_manual_areas(rootfs),
        "notes": []
    }

if __name__ == "__main__":
    print(json.dumps(collect("/"), indent=2))
