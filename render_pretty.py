#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path

CSS = """\
:root{--bg:#0b0c0f;--panel:#13151a;--ink:#f6f7fb;--muted:#9aa0aa;--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,Helvetica,Arial,sans-serif;line-height:1.5}
.wrap{max-width:1100px;margin:40px auto;padding:0 20px}
.card{background:var(--panel);border:1px solid #1f2229;border-radius:16px;padding:16px 18px;box-shadow:0 12px 40px rgba(0,0,0,.3)}
.grid{display:grid;gap:16px}
.grid.cols-2{grid-template-columns:repeat(2,1fr)}
.grid.cols-3{grid-template-columns:repeat(3,1fr)}
.section{margin-top:20px}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border-bottom:1px solid #1f2229;padding:8px 6px;text-align:left;font-size:.95rem;vertical-align:top}
.small{color:var(--muted);font-size:.9rem}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}
.score{font-size:1.4rem;font-weight:800}
.score.good{color:var(--ok)}
.score.warn{color:var(--warn)}
.score.bad{color:var(--bad)}
pre{background:#0f1116;border:1px solid #2a2f3a;border-radius:12px;padding:12px;overflow:auto;max-height:60vh;white-space:pre-wrap;word-break:break-word}
@media (max-width: 900px){.grid.cols-2,.grid.cols-3{grid-template-columns:1fr}}
"""


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def score_class(score):
    try:
        value = float(score)
    except Exception:
        return ""
    if value < 60:
        return "bad"
    if value < 75:
        return "warn"
    return "good"


def table(headers, rows):
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table class='table'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_summary(report, score):
    distro = report.get("distro", {}) or {}
    cards = [
        (
            "<div class='card'><div class='grid cols-3'>"
            f"<div><div class='small'>Schema</div><div class='mono'>{esc(report.get('schema_version'))}</div></div>"
            f"<div><div class='small'>Tier</div><div class='mono'>{esc(report.get('tier'))}</div></div>"
            f"<div><div class='small'>Target</div><div class='mono'>{esc(report.get('target_rootfs'))}</div></div>"
            "</div></div>"
        ),
        (
            "<div class='card'>"
            f"<div class='small'>Timestamp (UTC)</div><div class='mono'>{esc(report.get('timestamp_utc'))}</div>"
            f"<div class='small' style='margin-top:12px'>Kernel</div><div class='mono'>{esc(report.get('kernel'))}</div>"
            f"<div class='small' style='margin-top:12px'>Distro</div><div class='mono'>{esc(distro.get('pretty_name') or distro.get('name'))}</div>"
            "</div>"
        ),
    ]
    if score:
        cards.append(
            "<div class='card'>"
            f"<div class='score {score_class(score.get('score'))}'>Score: {esc(score.get('score'))}</div>"
            f"<div class='small'>{esc(len(score.get('penalties', [])))} penalties</div>"
            "</div>"
        )
    return "<div class='grid cols-3'>" + "".join(cards) + "</div>"


def render_score_explanation(report, score):
    if not score:
        return ""

    penalties = score.get("penalties", []) or []
    signals = score.get("signals", {}) or {}
    findings = score.get("findings", []) or []
    penalty_rows = [
        [esc(item.get("reason")), esc(item.get("value"))]
        for item in penalties
    ]
    signal_rows = [[esc(key), esc(value)] for key, value in sorted(signals.items())]
    finding_rows = [
        [
            esc(item.get("severity")),
            esc(item.get("category")),
            esc(item.get("title")),
            esc(item.get("count")),
            esc("yes" if item.get("scored") else "no"),
        ]
        for item in findings
    ]

    notes = []
    if report.get("tier") == 3:
        kernel_modules = ((report.get("advanced_checks") or {}).get("kernel_integrity") or {}).get("modules") or []
        categorized_only = sum(
            1
            for item in kernel_modules
            if item.get("module_path_category") not in (None, "", "in_tree")
            and item.get("path_risk_reason") in (None, "")
            and item.get("risk_reason") in (None, "")
        )
        if categorized_only:
            notes.append(
                f"{categorized_only} kernel modules were categorized as known third-party layouts without adding a penalty."
            )

    content = "<div class='section card'><h2>Score Explanation</h2>"
    content += "<div class='small'>Applied penalties affect the score. Signals provide context even when they do not trigger a penalty.</div>"
    content += "<h3 style='margin-top:16px'>Applied Penalties</h3>"
    content += table(["reason", "value"], penalty_rows) if penalty_rows else "<p><em>No penalties applied.</em></p>"
    content += "<h3 style='margin-top:16px'>Signals</h3>"
    content += table(["signal", "value"], signal_rows) if signal_rows else "<p><em>No score signals recorded.</em></p>"
    content += "<h3 style='margin-top:16px'>Findings</h3>"
    content += table(["severity", "category", "title", "count", "scored"], finding_rows) if finding_rows else "<p><em>No findings recorded.</em></p>"
    if notes:
        note_html = "".join(f"<p class='small'>{esc(note)}</p>" for note in notes)
        content += f"<h3 style='margin-top:16px'>Notes</h3>{note_html}"
    content += "</div>"
    return content


def render_tier1(report):
    sections = []

    users = report.get("users") or []
    if users:
        rows = [
            [esc(u.get("name")), esc(u.get("uid")), esc(u.get("gid")), esc(u.get("home")), esc(u.get("shell"))]
            for u in users[:200]
        ]
        sections.append("<div class='section card'><h2>Users</h2>" + table(["name", "uid", "gid", "home", "shell"], rows) + "</div>")

    groups = report.get("groups") or []
    if groups:
        rows = [[esc(g.get("name")), esc(g.get("gid")), esc(", ".join(g.get("members") or []))] for g in groups[:200]]
        sections.append("<div class='section card'><h2>Groups</h2>" + table(["name", "gid", "members"], rows) + "</div>")

    cron = report.get("cron") or {}
    cron_dirs = "".join(
        f"<div class='small'>{esc(name)}</div><div class='mono'>{esc(', '.join(entries[:100]))}</div>"
        for name, entries in (cron.get("cron_dirs") or {}).items()
    )
    sections.append(
        "<div class='section card'><h2>Cron</h2>"
        f"<div class='small'>/etc/crontab</div><pre>{esc((cron.get('system_crontab') or '').strip())}</pre>"
        f"<div class='small'>/etc/cron.d</div><div class='mono'>{esc(', '.join((cron.get('cron_d_files') or [])[:100]))}</div>"
        f"{cron_dirs}</div>"
    )

    suids = report.get("suid_sgid") or []
    if suids:
        rows = [
            [esc(item.get("path")), esc(item.get("mode_octal")), "yes" if item.get("suid") else "", "yes" if item.get("sgid") else ""]
            for item in suids[:200]
        ]
        sections.append("<div class='section card'><h2>SUID/SGID</h2>" + table(["path", "mode", "suid", "sgid"], rows) + "</div>")

    services = report.get("services") or []
    if services:
        rows = [[esc(name)] for name in services[:300]]
        sections.append("<div class='section card'><h2>Services</h2>" + table(["unit"], rows) + "</div>")

    return "".join(sections)


def render_repos(report):
    repos = report.get("repos", {}) or {}
    parts = []

    apt = repos.get("apt") or []
    if apt:
        rows = [
            [
                esc(repo.get("name")),
                esc(repo.get("enabled")),
                esc(repo.get("baseurl")),
                esc(" ".join(repo.get("components") or [])),
                esc(repo.get("options")),
                esc(repo.get("file")),
            ]
            for repo in apt[:100]
        ]
        parts.append("<div class='section card'><h2>APT Repos</h2>" + table(["name", "enabled", "baseurl", "components", "options", "file"], rows) + "</div>")

    yum = repos.get("yum_dnf") or []
    if yum:
        rows = [
            [
                esc(repo.get("name")),
                esc(repo.get("enabled")),
                esc(repo.get("gpgcheck")),
                esc(repo.get("baseurl") or repo.get("mirrorlist")),
                esc(", ".join(repo.get("gpgkey_files") or [])),
                esc(repo.get("file")),
            ]
            for repo in yum[:100]
        ]
        parts.append("<div class='section card'><h2>YUM/DNF Repos</h2>" + table(["name", "enabled", "gpgcheck", "source", "gpgkeys", "file"], rows) + "</div>")

    pacman = repos.get("pacman") or []
    if pacman:
        rows = [[esc(repo.get("file")), esc("\n".join(repo.get("servers") or []) or repo.get("content") or "")] for repo in pacman[:20]]
        parts.append("<div class='section card'><h2>Pacman Repos</h2>" + table(["file", "servers/content"], rows) + "</div>")

    return "".join(parts)


def render_tier2_plus(report):
    parts = [render_repos(report)]

    unsigned = report.get("unsigned_packages") or []
    rows = [[esc(item.get("name")), esc(item.get("version")), esc(item.get("manager")), esc(item.get("reason"))] for item in unsigned[:100]]
    parts.append("<div class='section card'><h2>Unsigned Packages</h2>" + (table(["name", "version", "manager", "reason"], rows) if rows else "<p><em>None detected.</em></p>") + "</div>")

    shadows = report.get("path_shadowing") or []
    shadow_rows = [
        [esc(item.get("basename")), esc(item.get("first_hit")), esc(", ".join(item.get("shadowed") or []))]
        for item in shadows[:200]
    ]
    parts.append("<div class='section card'><h2>PATH Shadowing</h2>" + (table(["binary", "first hit", "shadowed"], shadow_rows) if shadow_rows else "<p><em>No shadowing detected.</em></p>") + "</div>")

    manual = report.get("manual_areas") or {}
    manual_blocks = []
    for area, payload in manual.items():
        stats = payload.get("stats", {}) or {}
        entries = payload.get("entries", []) or []
        rows = [
            [
                esc(entry.get("path")),
                esc(entry.get("mode")),
                esc(entry.get("owner")),
                esc(entry.get("size")),
                "yes" if entry.get("elf") else "no",
                "yes" if entry.get("w_world") else "no",
            ]
            for entry in entries[:50]
        ]
        manual_blocks.append(
            "<div style='margin-top:16px'>"
            f"<h3>{esc(area)}</h3>"
            f"<div class='small'>files={esc(stats.get('files', 0))} dirs={esc(stats.get('dirs', 0))} world-writable={esc(stats.get('world_writable', 0))} elf={esc(stats.get('elf_binaries', 0))}</div>"
            + (table(["path", "mode", "owner", "size", "elf", "world-writable"], rows) if rows else "<p><em>Empty.</em></p>")
            + "</div>"
        )
    parts.append("<div class='section card'><h2>Manual Areas</h2>" + "".join(manual_blocks) + "</div>")

    if report.get("tier") == 3:
        checks = report.get("advanced_checks") or {}
        process_audit = checks.get("process_audit") or {}
        process_summary = process_audit.get("summary") or {}
        process_rows = [
            [
                esc(item.get("pid")),
                esc(item.get("ppid")),
                esc(item.get("name")),
                esc(item.get("uid")),
                esc(item.get("threads")),
                esc(item.get("exe")),
            ]
            for item in (process_audit.get("processes") or [])[:50]
        ]
        parts.append(
            "<div class='section card'><h2>Runtime Process Audit</h2>"
            f"<div class='small'>processes={esc(process_summary.get('total_processes', 0))} "
            f"threads={esc(process_summary.get('total_threads', 0))} "
            f"root-owned={esc(process_summary.get('root_owned_processes', 0))} "
            f"deleted-exe={esc(process_summary.get('deleted_executable_processes', 0))} "
            f"suspicious-exe={esc(process_summary.get('suspicious_executable_processes', 0))} "
            f"orphan-like={esc(process_summary.get('orphan_like_processes', 0))}</div>"
            + (table(["pid", "ppid", "name", "uid", "threads", "exe"], process_rows) if process_rows else "<p><em>No runtime process data available.</em></p>")
            + "</div>"
        )

        suspicious_rows = [
            [
                esc(item.get("pid")),
                esc(item.get("name")),
                esc(item.get("reason")),
                esc(item.get("exe")),
                esc(" <- ".join(f"{ancestor.get('name')}({ancestor.get('pid')})" for ancestor in (item.get("ancestry") or []))),
            ]
            for item in (process_audit.get("suspicious_processes") or [])[:50]
        ]
        parts.append(
            "<div class='section card'><h2>Suspicious Runtime Processes</h2>"
            + (table(["pid", "name", "reason", "exe", "ancestry"], suspicious_rows) if suspicious_rows else "<p><em>No suspicious executable heuristics matched.</em></p>")
            + "</div>"
        )

        network_checks = checks.get("network_listeners") or {}
        network_summary = network_checks.get("summary") or {}
        network_rows = [
            [
                esc(item.get("proto")),
                esc(item.get("local_address") or item.get("path")),
                esc(item.get("local_port")),
                esc(", ".join(item.get("process_names") or [])),
                esc(item.get("state")),
            ]
            for item in (network_checks.get("listeners") or [])[:100]
        ]
        parts.append(
            "<div class='section card'><h2>Network Listeners</h2>"
            f"<div class='small'>listeners={esc(network_summary.get('total_listeners', 0))} "
            f"wildcard-binds={esc(network_summary.get('wildcard_bind_count', 0))} "
            f"unattributed={esc(network_summary.get('unattributed_listener_count', 0))}</div>"
            + (table(["proto", "bind", "port", "processes", "state"], network_rows) if network_rows else "<p><em>No listener data available.</em></p>")
            + "</div>"
        )

        kernel_check = checks.get("kernel_integrity") or {}
        kernel_summary = kernel_check.get("summary") or {}
        kernel_rows = [
            [
                esc(item.get("name")),
                esc(item.get("state")),
                esc(item.get("use_count")),
                esc(item.get("module_path_category")),
                esc(item.get("module_path")),
                esc(item.get("path_risk_reason")),
                esc(item.get("risk_reason")),
            ]
            for item in (kernel_check.get("modules") or [])[:100]
        ]
        parts.append(
            "<div class='section card'><h2>Kernel Integrity</h2>"
            f"<div class='small'>loaded={esc(kernel_summary.get('loaded_modules', 0))} "
            f"suspicious={esc(kernel_summary.get('suspicious_modules', 0))} "
            f"missing-files={esc(kernel_summary.get('missing_module_files', 0))} "
            f"tainted={esc(kernel_summary.get('tainted_modules', 0))}</div>"
            + (table(["name", "state", "use_count", "path_category", "module_path", "path_risk", "risk_reason"], kernel_rows) if kernel_rows else "<p><em>No kernel module data available.</em></p>")
            + "</div>"
        )

    return "".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True)
    parser.add_argument("--out", dest="out", required=True)
    parser.add_argument("--score", dest="score", default=None)
    args = parser.parse_args()

    report = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    score = None
    if args.score and Path(args.score).exists():
        try:
            score = json.loads(Path(args.score).read_text(encoding="utf-8"))
        except Exception:
            score = None

    title = f"dtrust Report - Tier {report.get('tier')}"
    content = [f"<h1>{esc(title)}</h1>", render_summary(report, score), render_score_explanation(report, score), render_tier1(report)]
    if report.get("tier") in (2, 3):
        content.append(render_tier2_plus(report))

    html_doc = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body><div class='wrap'>"
        + "".join(content)
        + "</div></body></html>"
    )
    Path(args.out).write_text(html_doc, encoding="utf-8")
    print(f"Wrote pretty HTML: {args.out}")


if __name__ == "__main__":
    main()
