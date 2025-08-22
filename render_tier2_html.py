#!/usr/bin/env python3
# render_tier2_html.py
import json, html, sys
from pathlib import Path
from datetime import datetime, timezone

def esc(s): return html.escape(str(s if s is not None else ""))

def tr(cells): return "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>"
def th(headers): return "<tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"

def table(headers, rows):
    return (
        '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;margin:10px 0;">'
        + th(headers)
        + "".join(tr(r) for r in rows)
        + "</table>"
    )

def section(title, body_html):
    return f"<h2>{esc(title)}</h2>\n{body_html}"

def render_repos(data):
    repos = data.get("repos", {})
    parts = []

    # YUM/DNF normalized
    yum = repos.get("yum_dnf") or []
    if yum:
        rows = [[r.get("name"), r.get("enabled"), r.get("gpgcheck"),
                 r.get("baseurl") or r.get("mirrorlist") or "",
                 ", ".join(r.get("gpgkey_files") or []),
                 r.get("file")] for r in yum]
        parts.append("<h3>YUM/DNF</h3>" + table(
            ["name", "enabled", "gpgcheck", "source", "gpgkeys", "file"], rows
        ))

    # APT normalized
    apt = repos.get("apt") or []
    if apt:
        rows = [[r.get("name"), r.get("enabled"),
                 r.get("baseurl"), " ".join(r.get("components") or []),
                 r.get("options") or "", r.get("file")] for r in apt]
        parts.append("<h3>APT</h3>" + table(
            ["name", "enabled", "baseurl", "components", "options", "file"], rows
        ))

    # Pacman signals (not normalized, just useful context)
    pac = repos.get("pacman") or []
    if pac:
        rows = [[p.get("file"), (", ".join(p.get("servers")) if p.get("servers") else "(content)")] for p in pac]
        parts.append("<h3>Pacman</h3>" + table(["file", "servers/content"], rows))

    if not parts:
        return "<p><em>No repositories found.</em></p>"
    return "".join(parts)

def render_unsigned(data):
    ups = data.get("unsigned_packages") or []
    if not ups:
        return "<p><em>None detected.</em></p>"
    rows = [[u.get("name"), u.get("version"), u.get("manager"), u.get("reason")] for u in ups]
    return table(["name", "version", "manager", "reason"], rows)

def render_shadowing(data):
    sh = data.get("path_shadowing") or []
    if not sh:
        return "<p><em>No shadowed binaries detected.</em></p>"
    rows = [[x.get("basename"), x.get("first_hit"), len(x.get("shadowed") or []),
             x.get("first_hit_sha256", "")] for x in sh]
    return table(["basename", "first_hit", "shadowed_count", "first_hit_sha256"], rows)

def render_manual(data):
    mans = data.get("manual_areas") or {}
    if not mans:
        return "<p><em>No manual areas scanned.</em></p>"
    parts = []
    for area, payload in mans.items():
        st = payload.get("stats", {})
        parts.append(
            f"<h3>{esc(area)}</h3>"
            f"<p><strong>files</strong> {esc(st.get('files',0))} • "
            f"<strong>dirs</strong> {esc(st.get('dirs',0))} • "
            f"<strong>world-writable</strong> {esc(st.get('world_writable',0))} • "
            f"<strong>ELF</strong> {esc(st.get('elf_binaries',0))}</p>"
        )
        ents = (payload.get("entries") or [])[:100]  # show first 100 for brevity
        if ents:
            rows = [[e.get("path"), e.get("mode"), e.get("owner"), e.get("size"),
                     "yes" if e.get("elf") else "no",
                     "yes" if e.get("w_world") else "no",
                     e.get("mtime_utc")] for e in ents]
            parts.append(table(["path","mode","owner","size","ELF","world-writable","mtime"], rows))
        else:
            parts.append("<p><em>Empty.</em></p>")
    return "".join(parts)

def render_html(data):
    head = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>DTrust Tier-2 Report</title>"
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:24px;max-width:1100px;margin:auto}"
        "h1{margin:10px 0 4px} h2{margin-top:28px}"
        "table th{background:#f5f5f5;text-align:left}</style>"
    )
    meta = (
        f"<p><strong>schema</strong> {esc(data.get('schema',''))} &nbsp; "
        f"<strong>tier</strong> {esc(data.get('tier',''))} &nbsp; "
        f"<strong>timestamp</strong> {esc(data.get('timestamp',''))} &nbsp; "
        f"<strong>target</strong> {esc(data.get('target',''))}</p>"
    )
    body = (
        f"<h1>DTrust Tier-2 Report</h1>{meta}"
        + section("Repository Configuration", render_repos(data))
        + section("Unsigned / Unverified Packages", render_unsigned(data))
        + section("PATH Shadowing", render_shadowing(data))
        + section("Manual Areas (/usr/local, /opt)", render_manual(data))
        + f"<p style='margin-top:28px;color:#666;font-size:12px'>Generated {esc(datetime.now(timezone.utc).isoformat())}</p>"
    )
    return head + body

def main():
    if len(sys.argv) < 3:
        print("Usage: render_tier2_html.py <tier2.json> <out.html>")
        sys.exit(1)
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(render_html(data), encoding="utf-8")
    print(f"Wrote HTML: {sys.argv[2]}")

if __name__ == "__main__":
    main()
