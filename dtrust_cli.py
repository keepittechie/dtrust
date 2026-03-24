#!/usr/bin/env python3
import argparse
import glob
import hashlib
import json
import os
import platform
import re
import socket
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCHEMA_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except Exception:
        return False


def file_mode_owner(path: Path) -> Tuple[str, str]:
    try:
        st = path.stat()
        mode_str = f"{stat.S_IMODE(st.st_mode):04o}"
        try:
            import grp
            import pwd

            owner = f"{pwd.getpwuid(st.st_uid).pw_name}:{grp.getgrgid(st.st_gid).gr_name}"
        except Exception:
            owner = f"{st.st_uid}:{st.st_gid}"
        return mode_str, owner
    except Exception:
        return "0000", "?:?"


def collect_distro(root: Path) -> Dict[str, Optional[str]]:
    os_release = root / "etc" / "os-release"
    values: Dict[str, str] = {}
    if os_release.exists():
        for line in read_text(os_release).splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return {
        "id": values.get("ID"),
        "name": values.get("NAME"),
        "version_id": values.get("VERSION_ID"),
        "pretty_name": values.get("PRETTY_NAME") or platform.system(),
    }


def collect_kernel(root: Path) -> Optional[str]:
    proc_version = root / "proc" / "version"
    version_text = read_text(proc_version).strip()
    if version_text:
        return version_text
    try:
        return platform.release()
    except Exception:
        return None


def collect_users(root: Path) -> List[Dict[str, object]]:
    passwd_path = root / "etc" / "passwd"
    users: List[Dict[str, object]] = []
    for line in read_text(passwd_path).splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 7:
            continue
        name, _, uid, gid, _, home, shell = parts[:7]
        try:
            uid_val: Optional[int] = int(uid)
        except Exception:
            uid_val = None
        try:
            gid_val: Optional[int] = int(gid)
        except Exception:
            gid_val = None
        users.append(
            {
                "name": name,
                "uid": uid_val,
                "gid": gid_val,
                "home": home,
                "shell": shell,
            }
        )
    return users


def collect_groups(root: Path) -> List[Dict[str, object]]:
    group_path = root / "etc" / "group"
    groups: List[Dict[str, object]] = []
    for line in read_text(group_path).splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        name, _, gid, members = parts[:4]
        try:
            gid_val: Optional[int] = int(gid)
        except Exception:
            gid_val = None
        groups.append(
            {
                "name": name,
                "gid": gid_val,
                "members": [m for m in members.split(",") if m],
            }
        )
    return groups


def collect_cron(root: Path) -> Dict[str, object]:
    etc = root / "etc"
    cron_dirs = {}
    for name in ("cron.hourly", "cron.daily", "cron.weekly", "cron.monthly"):
        base = etc / name
        entries: List[str] = []
        if base.exists() and base.is_dir():
            try:
                entries = [child.name for child in sorted(base.iterdir())]
            except Exception:
                entries = []
        cron_dirs[name] = entries

    cron_d_dir = etc / "cron.d"
    cron_d_files: List[str] = []
    if cron_d_dir.exists() and cron_d_dir.is_dir():
        try:
            cron_d_files = [child.name for child in sorted(cron_d_dir.iterdir())]
        except Exception:
            cron_d_files = []

    return {
        "system_crontab": read_text(etc / "crontab") or None,
        "cron_d_files": cron_d_files,
        "cron_dirs": cron_dirs,
    }


def collect_suid_sgid(root: Path, max_entries: int = 2000) -> List[Dict[str, object]]:
    scan_roots = [
        root / "bin",
        root / "sbin",
        root / "usr" / "bin",
        root / "usr" / "sbin",
        root / "usr" / "local" / "bin",
        root / "usr" / "local" / "sbin",
        root / "opt",
    ]
    results: List[Dict[str, object]] = []
    seen = set()
    for base in scan_roots:
        if not base.exists():
            continue
        for dirpath, _, filenames in os.walk(base, followlinks=False):
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    st = path.stat()
                except Exception:
                    continue
                key = (int(st.st_dev), int(st.st_ino))
                if key in seen:
                    continue
                seen.add(key)
                suid = bool(st.st_mode & stat.S_ISUID)
                sgid = bool(st.st_mode & stat.S_ISGID)
                if not suid and not sgid:
                    continue
                results.append(
                    {
                        "path": str(path),
                        "mode_octal": f"{stat.S_IMODE(st.st_mode):04o}",
                        "suid": suid,
                        "sgid": sgid,
                    }
                )
                if len(results) >= max_entries:
                    return results
    return results


def collect_services(root: Path, limit: int = 4000) -> List[str]:
    bases = [
        root / "etc" / "systemd" / "system",
        root / "usr" / "lib" / "systemd" / "system",
        root / "lib" / "systemd" / "system",
    ]
    names = set()
    for base in bases:
        if not base.exists():
            continue
        for dirpath, _, filenames in os.walk(base, followlinks=False):
            for filename in filenames:
                if not filename.endswith(".service"):
                    continue
                names.add(filename)
                if len(names) >= limit:
                    return sorted(names)
    return sorted(names)


def collect_limits(max_seconds: int) -> Dict[str, object]:
    return {
        "max_seconds": max_seconds,
        "manual_area_entry_limit": 6000,
        "suid_scan_roots": [
            "/bin",
            "/sbin",
            "/usr/bin",
            "/usr/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/opt",
        ],
    }


def gather_pkg_repos(root: Path) -> Dict[str, List[Dict[str, object]]]:
    repos: Dict[str, List[Dict[str, object]]] = {"apt": [], "yum_dnf": [], "pacman": []}

    sources_list = root / "etc" / "apt" / "sources.list"
    sources_d = root / "etc" / "apt" / "sources.list.d"
    line_re = re.compile(r"^\s*deb(-src)?\s+(\[[^\]]+\]\s+)?(\S+)\s+(\S+)\s+(.*)$")

    def parse_apt_file(path: Path) -> None:
        for line in read_text(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = line_re.match(line)
            if not match:
                continue
            is_src = bool(match.group(1))
            opts = (match.group(2) or "").strip()
            url = match.group(3)
            suite = match.group(4)
            components = (match.group(5) or "").split()
            repos["apt"].append(
                {
                    "file": str(path),
                    "name": f"{suite}{'-src' if is_src else ''}",
                    "enabled": True,
                    "baseurl": url,
                    "mirrorlist": None,
                    "gpgcheck": True,
                    "gpgkey_files": [],
                    "components": components,
                    "options": opts,
                }
            )

    if sources_list.exists():
        parse_apt_file(sources_list)
    if sources_d.exists() and sources_d.is_dir():
        for repo_file in sorted(sources_d.glob("*.list")):
            parse_apt_file(repo_file)

    yum_dir = root / "etc" / "yum.repos.d"
    if yum_dir.exists() and yum_dir.is_dir():
        for repo_file in sorted(yum_dir.glob("*.repo")):
            body = read_text(repo_file)
            parts = re.split(r"\n\[(.+?)\]\s*\n", "\n" + body)
            for idx in range(1, len(parts), 2):
                name = parts[idx].strip()
                section = parts[idx + 1]

                def get_value(key: str, default=None):
                    match = re.search(rf"^{key}\s*=\s*(.+)$", section, re.M | re.I)
                    return match.group(1).strip() if match else default

                enabled = get_value("enabled", "1") == "1"
                gpgcheck = get_value("gpgcheck", "1") == "1"
                baseurl = get_value("baseurl")
                mirrorlist = get_value("mirrorlist")
                gpgkey = get_value("gpgkey") or ""
                gpgkey_files: List[str] = []
                for part in re.split(r"[\s,]+", gpgkey.strip()):
                    if part.startswith("file:"):
                        normalized = part.replace("file://", "file:").replace("file:", "")
                        if normalized:
                            gpgkey_files.append(normalized)
                repos["yum_dnf"].append(
                    {
                        "file": str(repo_file),
                        "name": name,
                        "enabled": enabled,
                        "baseurl": baseurl,
                        "mirrorlist": mirrorlist,
                        "gpgcheck": gpgcheck,
                        "gpgkey_files": gpgkey_files,
                    }
                )

    includes: List[Path] = []
    pacman_conf = root / "etc" / "pacman.conf"
    if pacman_conf.exists():
        conf_text = read_text(pacman_conf)
        repos["pacman"].append({"file": str(pacman_conf), "content": conf_text})
        for line in conf_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith("include"):
                parts = stripped.split("=", 1)
                if len(parts) != 2:
                    continue
                pattern = str(root / parts[1].strip().lstrip("/"))
                includes.extend(Path(match) for match in glob.glob(pattern))

    def extract_servers(text: str) -> List[str]:
        servers: List[str] = []
        for line in text.splitlines():
            candidate = line.lstrip().lstrip("#").strip()
            if not candidate.lower().startswith("server"):
                continue
            parts = candidate.split("=", 1)
            if len(parts) == 2:
                servers.append(parts[1].strip())
        return servers

    for include_path in includes:
        include_text = read_text(include_path)
        repos["pacman"].append(
            {
                "file": str(include_path),
                "content": include_text,
                "servers": extract_servers(include_text),
            }
        )

    mirrorlist = root / "etc" / "pacman.d" / "mirrorlist"
    if mirrorlist.exists():
        mirror_text = read_text(mirrorlist)
        repos["pacman"].append(
            {"file": str(mirrorlist), "content": mirror_text, "servers": extract_servers(mirror_text)}
        )

    return repos


def collect_unsigned_packages(root: Path) -> List[Dict[str, object]]:
    try:
        from dtrust import pkg_unsigned

        return pkg_unsigned.collect(root)
    except Exception:
        return []


def list_path_shadowing(root: Path) -> List[Dict[str, object]]:
    path_dirs = [
        root / "usr" / "local" / "sbin",
        root / "usr" / "local" / "bin",
        root / "usr" / "sbin",
        root / "usr" / "bin",
        root / "sbin",
        root / "bin",
    ]
    by_name: Dict[str, List[Path]] = {}
    for base in path_dirs:
        if not base.exists():
            continue
        try:
            for path in base.iterdir():
                if path.is_file():
                    by_name.setdefault(path.name, []).append(path)
        except Exception:
            continue

    results: List[Dict[str, object]] = []
    for name, paths in by_name.items():
        uniq: List[Path] = []
        seen = set()
        for path in paths:
            real_path = Path(os.path.realpath(path))
            try:
                st = real_path.stat()
                key = (int(st.st_dev), int(st.st_ino))
            except Exception:
                key = (str(real_path), None)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(real_path)
        if len(uniq) <= 1:
            continue
        first = uniq[0]
        shadowed = uniq[1:]
        results.append(
            {
                "basename": name,
                "first_hit": str(first),
                "shadowed": [str(item) for item in shadowed],
                "first_hit_sha256": sha256_file(first),
                "shadowed_sha256": [sha256_file(item) for item in shadowed],
            }
        )
    return results


def scan_dir(root: Path, limit: int = 6000) -> Dict[str, object]:
    entries: List[Dict[str, object]] = []
    files = 0
    dirs = 0
    world_writable = 0
    elf_binaries = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for dirname in dirnames:
            path = Path(dirpath) / dirname
            try:
                path.stat()
                dirs += 1
            except Exception:
                continue
        for filename in filenames:
            if count >= limit:
                break
            path = Path(dirpath) / filename
            try:
                st = path.stat()
                mode_str, owner = file_mode_owner(path)
                ww_bit = bool(stat.S_IMODE(st.st_mode) & 0o002)
                elf_bit = is_elf(path)
                if ww_bit:
                    world_writable += 1
                if elf_bit:
                    elf_binaries += 1
                files += 1
                count += 1
                entries.append(
                    {
                        "path": str(path),
                        "type": "file",
                        "mode": mode_str,
                        "owner": owner,
                        "size": st.st_size,
                        "elf": elf_bit,
                        "w_world": ww_bit,
                        "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                        .replace(microsecond=0)
                        .isoformat(),
                    }
                )
            except Exception:
                continue
        if count >= limit:
            break
    return {
        "entries": entries,
        "stats": {
            "files": files,
            "dirs": dirs,
            "world_writable": world_writable,
            "elf_binaries": elf_binaries,
        },
    }


def collect_manual_areas(root: Path) -> Dict[str, Dict[str, object]]:
    areas: Dict[str, Dict[str, object]] = {}
    for path in (root / "usr" / "local", root / "opt"):
        key = "/" + str(path.relative_to(root))
        if path.exists() and path.is_dir():
            areas[key] = scan_dir(path, limit=6000)
        else:
            areas[key] = {
                "entries": [],
                "stats": {"files": 0, "dirs": 0, "world_writable": 0, "elf_binaries": 0},
            }
    return areas


def _readlink_text(path: Path) -> Optional[str]:
    try:
        return os.readlink(path)
    except Exception:
        return None


def _decode_cmdline(raw: bytes) -> str:
    parts = [part.decode("utf-8", errors="ignore") for part in raw.split(b"\x00") if part]
    return " ".join(parts)


def _safe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _format_ip(hex_ip: str, family: int) -> str:
    try:
        data = bytes.fromhex(hex_ip)
        if family == socket.AF_INET:
            return socket.inet_ntop(socket.AF_INET, data[::-1])
        if family == socket.AF_INET6:
            words = [data[idx : idx + 4][::-1] for idx in range(0, len(data), 4)]
            return socket.inet_ntop(socket.AF_INET6, b"".join(words))
    except Exception:
        pass
    return hex_ip


def _parse_proc_net(path: Path, proto: str, family: int, kind: str) -> List[Dict[str, object]]:
    rows = []
    text = read_text(path)
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 10:
            continue
        local_hex, local_port_hex = fields[1].split(":", 1)
        state = fields[3]
        inode = fields[9]
        rows.append(
            {
                "proto": proto,
                "family": "ipv6" if family == socket.AF_INET6 else "ipv4",
                "kind": kind,
                "local_address": _format_ip(local_hex, family),
                "local_port": int(local_port_hex, 16),
                "state": state,
                "inode": inode,
            }
        )
    return rows


def _parse_proc_unix(path: Path) -> List[Dict[str, object]]:
    rows = []
    text = read_text(path)
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 7:
            continue
        inode = fields[6]
        unix_path = fields[7] if len(fields) > 7 else ""
        rows.append(
            {
                "proto": "unix",
                "family": "unix",
                "kind": "stream",
                "path": unix_path,
                "state": fields[5],
                "inode": inode,
            }
        )
    return rows


def _normalize_module_name(name: str) -> str:
    return name.replace("-", "_")


def _distro_families(root: Path) -> set[str]:
    distro = collect_distro(root)
    families = set()
    for value in (distro.get("id"), distro.get("name"), distro.get("pretty_name")):
        if isinstance(value, str) and value:
            families.add(value.lower())
    os_release = read_text(root / "etc" / "os-release")
    for line in os_release.splitlines():
        if not line.startswith("ID_LIKE="):
            continue
        families.update(item.strip().strip('"').lower() for item in line.split("=", 1)[1].split() if item.strip())
    return families


def _build_module_file_index(root: Path) -> Dict[str, str]:
    modules_root = root / "lib" / "modules"
    index: Dict[str, str] = {}
    if not modules_root.exists() or not modules_root.is_dir():
        return index
    for path in modules_root.rglob("*"):
        if not path.is_file():
            continue
        suffixes = "".join(path.suffixes)
        if ".ko" not in suffixes:
            continue
        module_name = path.name
        for suffix in (".ko.xz", ".ko.zst", ".ko.gz", ".ko"):
            if module_name.endswith(suffix):
                module_name = module_name[: -len(suffix)]
                break
        index.setdefault(_normalize_module_name(module_name), str(path))
    return index


def _module_path_category(module_path: Optional[str], distro_families: set[str]) -> str:
    if not module_path:
        return "missing"
    normalized = module_path.lower()
    if "/kernel/" in normalized:
        return "in_tree"
    if "/updates/dkms/" in normalized or normalized.endswith("/dkms"):
        return "dkms"
    if "/extramodules/" in normalized and ("arch" in distro_families or "manjaro" in distro_families):
        return "arch_extramodules"
    if "/extra/" in normalized and ({"rhel", "fedora", "centos", "rocky", "alma", "suse"} & distro_families):
        return "vendor_extra"
    if "/weak-updates/" in normalized and ({"rhel", "fedora", "centos", "rocky", "alma"} & distro_families):
        return "weak_updates"
    if "/updates/" in normalized:
        return "updates"
    return "nonstandard"


def _module_risk_reason(module_path: Optional[str], taint: str, path_category: str) -> Optional[str]:
    if not module_path:
        return "missing_module_file"
    if taint and taint not in ("0", ""):
        return "tainted_module"
    if path_category == "nonstandard":
        return "nonstandard_module_path"
    if path_category == "updates":
        return "out_of_tree_module_path"
    return None


def _ancestry_chain(pid: int, indexed_processes: Dict[int, Dict[str, object]], max_depth: int = 6) -> List[Dict[str, object]]:
    chain = []
    current_pid = pid
    seen = set()
    for _ in range(max_depth):
        proc = indexed_processes.get(current_pid)
        if not proc or current_pid in seen:
            break
        seen.add(current_pid)
        chain.append({"pid": proc.get("pid"), "name": proc.get("name"), "exe": proc.get("exe")})
        parent_pid = proc.get("ppid")
        if not isinstance(parent_pid, int) or parent_pid <= 0 or parent_pid == current_pid:
            break
        current_pid = parent_pid
    return chain


def _suspicious_exec_reason(exe_path: Optional[str]) -> Optional[str]:
    if not exe_path:
        return "missing_executable_path"
    normalized = exe_path.replace(" (deleted)", "")
    if exe_path.endswith(" (deleted)"):
        return "deleted_executable"
    suspicious_prefixes = ("/tmp/", "/var/tmp/", "/dev/shm/", "/run/")
    if normalized.startswith(suspicious_prefixes):
        return "ephemeral_executable_path"
    if normalized.startswith("/usr/local/") or normalized.startswith("/opt/"):
        return "locally_installed_executable"
    return None


def collect_runtime_activity(root: Path) -> Dict[str, object]:
    proc_root = root / "proc"
    distro_families = _distro_families(root)
    if not proc_root.exists() or not proc_root.is_dir():
        return {
            "status": "unavailable",
            "reason": "Runtime inspection requires a mounted /proc tree in the target rootfs.",
            "process_audit": {"summary": {"total_processes": 0}, "processes": []},
            "network_listeners": {"summary": {"total_listeners": 0}, "listeners": []},
            "kernel_integrity": {"status": "unavailable", "summary": {"loaded_modules": 0}, "modules": []},
        }

    processes: List[Dict[str, object]] = []
    fd_inode_to_pids: Dict[str, List[int]] = {}
    total_threads = 0
    root_owned = 0
    deleted_execs = 0

    for entry in sorted(proc_root.iterdir(), key=lambda p: p.name):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        status_text = read_text(entry / "status")
        if not status_text:
            continue
        status = {}
        for line in status_text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            status[key.strip()] = value.strip()

        uid_fields = (status.get("Uid") or "").split()
        uid = _safe_int(uid_fields[0]) if uid_fields else None
        threads = _safe_int(status.get("Threads", ""))
        if uid == 0:
            root_owned += 1
        if threads:
            total_threads += threads

        exe_path = _readlink_text(entry / "exe")
        if exe_path and exe_path.endswith(" (deleted)"):
            deleted_execs += 1

        cmdline = ""
        try:
            cmdline = _decode_cmdline((entry / "cmdline").read_bytes())
        except Exception:
            cmdline = ""
        if not cmdline:
            cmdline = read_text(entry / "comm").strip()

        process_info = {
            "pid": pid,
            "ppid": _safe_int(status.get("PPid", "")),
            "name": status.get("Name") or "",
            "uid": uid,
            "threads": threads or 0,
            "exe": exe_path,
            "cmdline": cmdline,
        }
        processes.append(process_info)

        fd_dir = entry / "fd"
        if not fd_dir.exists() or not fd_dir.is_dir():
            continue
        # Map socket inode -> pid so listeners can be attributed back to processes.
        for fd_entry in fd_dir.iterdir():
            target = _readlink_text(fd_entry)
            if not target or not target.startswith("socket:["):
                continue
            inode = target.removeprefix("socket:[").removesuffix("]")
            fd_inode_to_pids.setdefault(inode, []).append(pid)

    listeners = []
    for item in _parse_proc_net(proc_root / "net" / "tcp", "tcp", socket.AF_INET, "stream"):
        if item["state"] == "0A":
            listeners.append(item)
    for item in _parse_proc_net(proc_root / "net" / "tcp6", "tcp6", socket.AF_INET6, "stream"):
        if item["state"] == "0A":
            listeners.append(item)
    listeners.extend(_parse_proc_net(proc_root / "net" / "udp", "udp", socket.AF_INET, "datagram"))
    listeners.extend(_parse_proc_net(proc_root / "net" / "udp6", "udp6", socket.AF_INET6, "datagram"))
    listeners.extend(_parse_proc_unix(proc_root / "net" / "unix"))

    indexed_processes = {item["pid"]: item for item in processes}
    suspicious_processes = []
    orphan_like = 0
    for proc in processes:
        reason = _suspicious_exec_reason(proc.get("exe"))
        if proc.get("ppid") == 1 and proc.get("pid") not in (1,):
            orphan_like += 1
        if not reason:
            continue
        suspicious_processes.append(
            {
                "pid": proc.get("pid"),
                "name": proc.get("name"),
                "uid": proc.get("uid"),
                "exe": proc.get("exe"),
                "cmdline": proc.get("cmdline"),
                "reason": reason,
                "ancestry": _ancestry_chain(int(proc["pid"]), indexed_processes),
            }
        )
    listener_rows: List[Dict[str, object]] = []
    wildcard_count = 0
    for item in listeners:
        inode = item.get("inode")
        pids = sorted(set(fd_inode_to_pids.get(str(inode), [])))
        proc_names = []
        for pid in pids[:5]:
            proc = indexed_processes.get(pid) or {}
            proc_names.append(proc.get("name") or str(pid))
        local_address = item.get("local_address") or ""
        if local_address in ("0.0.0.0", "::"):
            wildcard_count += 1
        listener_rows.append(
            {
                "proto": item.get("proto"),
                "family": item.get("family"),
                "kind": item.get("kind"),
                "local_address": local_address or None,
                "local_port": item.get("local_port"),
                "path": item.get("path"),
                "state": item.get("state"),
                "inode": inode,
                "pids": pids,
                "process_names": proc_names,
            }
        )

    processes.sort(key=lambda item: (item.get("name") or "", item["pid"]))
    top_processes = sorted(processes, key=lambda item: (-int(item.get("threads") or 0), item["pid"]))[:50]
    listener_rows.sort(key=lambda item: (str(item.get("proto")), int(item.get("local_port") or 0), str(item.get("path") or "")))

    modules_index = _build_module_file_index(root)
    loaded_modules = []
    suspicious_modules = 0
    missing_module_files = 0
    tainted_modules = 0
    modules_text = read_text(proc_root / "modules")
    for line in modules_text.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        name, size, use_count, deps, state, address = parts[:6]
        taint_text = read_text(root / "sys" / "module" / name / "taint").strip()
        module_path = modules_index.get(_normalize_module_name(name))
        path_category = _module_path_category(module_path, distro_families)
        reason = _module_risk_reason(module_path, taint_text, path_category)
        path_risk_reason = None
        if module_path is None:
            path_risk_reason = "missing_module_file"
        elif path_category == "nonstandard":
            path_risk_reason = "nonstandard_module_path"
        elif path_category == "updates":
            path_risk_reason = "out_of_tree_module_path"
        if module_path is None:
            missing_module_files += 1
        if taint_text and taint_text not in ("0", ""):
            tainted_modules += 1
        if path_risk_reason:
            suspicious_modules += 1
        loaded_modules.append(
            {
                "name": name,
                "size": _safe_int(size) or 0,
                "use_count": _safe_int(use_count) or 0,
                "dependencies": [] if deps == "-" else [item for item in deps.split(",") if item],
                "state": state,
                "address": address,
                "module_path": module_path,
                "module_path_category": path_category,
                "path_risk_reason": path_risk_reason,
                "risk_reason": reason,
            }
        )
    loaded_modules.sort(key=lambda item: (item.get("risk_reason") is None, str(item.get("name"))))

    return {
        "status": "ok",
        "process_audit": {
            "summary": {
                "total_processes": len(processes),
                "total_threads": total_threads,
                "root_owned_processes": root_owned,
                "deleted_executable_processes": deleted_execs,
                "orphan_like_processes": orphan_like,
                "suspicious_executable_processes": len(suspicious_processes),
            },
            "processes": top_processes,
            "suspicious_processes": suspicious_processes[:100],
        },
        "network_listeners": {
            "summary": {
                "total_listeners": len(listener_rows),
                "wildcard_bind_count": wildcard_count,
                "unattributed_listener_count": sum(1 for item in listener_rows if not item["pids"]),
            },
            "listeners": listener_rows[:200],
        },
        "kernel_integrity": {
            "status": "ok",
            "summary": {
                "loaded_modules": len(loaded_modules),
                "suspicious_modules": suspicious_modules,
                "missing_module_files": missing_module_files,
                "tainted_modules": tainted_modules,
            },
            "modules": loaded_modules[:200],
        },
    }


def collect_tier1(root: Path, max_seconds: int) -> Dict[str, object]:
    return {
        "kernel": collect_kernel(root),
        "distro": collect_distro(root),
        "users": collect_users(root),
        "groups": collect_groups(root),
        "cron": collect_cron(root),
        "suid_sgid": collect_suid_sgid(root),
        "services": collect_services(root),
        "limits": collect_limits(max_seconds),
        "repos": gather_pkg_repos(root),
    }


def collect_tier2(root: Path, max_seconds: int) -> Dict[str, object]:
    tier1 = collect_tier1(root, max_seconds)
    tier1.update(
        {
            "unsigned_packages": collect_unsigned_packages(root),
            "path_shadowing": list_path_shadowing(root),
            "manual_areas": collect_manual_areas(root),
        }
    )
    return tier1


def collect_tier3(root: Path, max_seconds: int) -> Dict[str, object]:
    tier2 = collect_tier2(root, max_seconds)
    tier2["advanced_checks"] = collect_runtime_activity(root)
    return tier2


def build_report(rootfs: str, tier: int, max_seconds: int) -> Dict[str, object]:
    root = Path(rootfs)
    base = {
        "schema_version": SCHEMA_VERSION,
        "tier": tier,
        "timestamp_utc": utc_now(),
        "target_rootfs": str(root.resolve()),
    }

    if tier == 1:
        payload = collect_tier1(root, max_seconds)
    elif tier == 2:
        payload = collect_tier2(root, max_seconds)
    elif tier == 3:
        payload = collect_tier3(root, max_seconds)
    else:
        raise SystemExit(f"Tiers > 3 not implemented yet. Asked: {tier}")

    base.update(payload)
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="dtrust CLI (Python)")
    parser.add_argument("--tier", type=int, default=1, help="Tier number")
    parser.add_argument("--rootfs", default="/", help="Target rootfs to scan")
    parser.add_argument("--out", default="-", help="Output file (or '-' for stdout)")
    parser.add_argument("--max-seconds", type=int, default=15, help="Overall time budget")
    args = parser.parse_args()

    start = time.time()
    report = build_report(args.rootfs, args.tier, args.max_seconds)
    report.setdefault("limits", {})
    report["limits"]["elapsed_seconds"] = round(time.time() - start, 3)

    data = json.dumps(report, indent=2)
    if args.out == "-" or args.out.strip() == "":
        print(data)
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(data, encoding="utf-8")
    print(f"Wrote report: {out_path}")


if __name__ == "__main__":
    main()
