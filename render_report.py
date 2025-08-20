#!/usr/bin/env python3
"""
render_report.py
Convert a dtrust JSON report into Markdown and HTML (no external deps).

Usage:
  python3 render_report.py --in report.json --out report.md
  python3 render_report.py --in report.json --out report.html
"""
import json, argparse, html, sys
from pathlib import Path
from datetime import datetime

CSS = """\
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Helvetica Neue',Arial,sans-serif;line-height:1.5;margin:2rem;max-width:980px}
h1,h2,h3{line-height:1.2}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,'Liberation Mono','Courier New',monospace}
pre{background:#f6f8fa;padding:1rem;overflow:auto;border-radius:8px}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:.5rem}th{background:#fafafa;text-align:left}
.badge{display:inline-block;padding:.25rem .6rem;border-radius:999px;background:#eee;border:1px solid #ddd;font-weight:600;font-size:.85rem}
.small{color:#555}
"""

def md_escape(s: str) -> str:
    return s.replace("|", r"\|")

def render_markdown(report: dict) -> str:
    distro = report.get("distro", {}) or {}
    title = f"dtrust Report — Tier {report.get('tier')}"
    lines = [f"# {title}", ""]
    lines.append(f"- **Schema**: `{report.get('schema_version')}`")
    lines.append(f"- **Timestamp (UTC)**: `{report.get('timestamp_utc')}`")
    lines.append(f"- **Target rootfs**: `{report.get('target_rootfs')}`")
    if report.get("kernel"):
        lines.append(f"- **Kernel**: `{md_escape(report['kernel'])}`")
    lines.append(f"- **Distro**: `{md_escape(str(distro.get('pretty_name') or distro.get('name') or 'unknown'))}`")
    lines.append("")

    # Users
    users = report.get("users", [])
    if users:
        lines += ["## Users", "", "| name | uid | gid | home | shell |", "|---|---:|---:|---|---|"]
        for u in users[:200]:
            lines.append(f"| {md_escape(u.get('name',''))} | {u.get('uid','')} | {u.get('gid','')} | {md_escape(u.get('home',''))} | {md_escape(u.get('shell',''))} |")
        if len(users) > 200:
            lines.append(f"\n> _and {len(users)-200} more…_")
        lines.append("")

    # Groups
    groups = report.get("groups", [])
    if groups:
        lines += ["## Groups", "", "| name | gid | members |", "|---|---:|---|"]
        for g in groups[:200]:
            members = ", ".join(g.get("members", []))
            lines.append(f"| {md_escape(g.get('name',''))} | {g.get('gid','')} | {md_escape(members)} |")
        if len(groups) > 200:
            lines.append(f"\n> _and {len(groups)-200} more…_")
        lines.append("")

    # Cron
    cron = report.get("cron", {})
    lines += ["## Cron", ""]
    sys_cron = cron.get("system_crontab")
    lines.append("**/etc/crontab**:")
    lines.append("")
    lines.append("```")
    lines.append((sys_cron or "").strip())
    lines.append("```")
    lines.append("")
    lines.append("**/etc/cron.d files**: " + ", ".join(cron.get("cron_d_files", [])[:100]))
    lines.append("")
    if "cron_dirs" in cron:
        for dname, entries in cron["cron_dirs"].items():
            lines.append(f"**/etc/{dname}**: " + ", ".join(entries[:100]))
    lines.append("")

    # SUID/SGID
    suids = report.get("suid_sgid", [])
    lines += ["## SUID/SGID Binaries (sample)", "", "| path | mode | suid | sgid |", "|---|---|:--:|:--:|"]
    for s in suids[:200]:
        lines.append(f"| {md_escape(s.get('path',''))} | {md_escape(s.get('mode_octal',''))} | {str(s.get('suid'))} | {str(s.get('sgid'))} |")
    if len(suids) > 200:
        lines.append(f"\n> _and {len(suids)-200} more…_")
    lines.append("")

    # Services
    services = report.get("services", [])
    if services:
        lines += ["## Systemd Services (filenames)", ""]
        for svc in services[:400]:
            lines.append(f"- `{md_escape(svc)}`")
        if len(services) > 400:
            lines.append(f"\n> _and {len(services)-400} more…_")
        lines.append("")

    # Limits
    limits = report.get("limits", {})
    if limits:
        lines += ["## Scan Limits", ""]
        for k, v in limits.items():
            lines.append(f"- **{k}**: `{v}`")
        lines.append("")

    return "\n".join(lines)

def render_html(markdown_text: str, title: str = "dtrust Report"):
    # Extremely simple Markdown to HTML (subset) without external libs.
    # We rely on the fact that our generator is predictable.
    # For production, switch to a proper Markdown lib; this is fine for a preview.
    import re
    html_lines = []
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:].strip())}</h1>"); continue
        if line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:].strip())}</h2>"); continue
        if line.startswith("- "):
            # simple list
            if not html_lines or not html_lines[-1].startswith("<ul"):
                html_lines.append("<ul>")
            html_lines.append(f"<li>{html.escape(line[2:].strip())}</li>")
            # we'll close ul after block ends
            continue
        if line.startswith("|") and line.endswith("|"):
            # crude table accumulator
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not html_lines or not html_lines[-1].startswith("<table"):
                html_lines.append("<table>")
            row = "".join(f"<td>{html.escape(c)}</td>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
            continue
        if line.startswith("```"):
            if not html_lines or not html_lines[-1].startswith("<pre"):
                html_lines.append("<pre><code>")
            else:
                html_lines.append("</code></pre>")
            continue
        if line.strip().startswith("> _and "):
            html_lines.append(f"<p class='small'>{html.escape(line.strip()[2:].strip())}</p>")
            continue
        if line.strip() == "":
            # close lists/tables if previous lines opened them
            if html_lines and html_lines[-1].startswith("<ul"):
                html_lines.append("</ul>")
            if html_lines and html_lines[-1].startswith("<table"):
                html_lines.append("</table>")
            html_lines.append("<p></p>")
            continue
        # default paragraph or code content inside <pre><code>
        if html_lines and html_lines[-1].endswith("<code>"):
            html_lines.append(html.escape(line))
        else:
            html_lines.append(f"<p>{html.escape(line)}</p>")

    # Close any open tags
    if html_lines and html_lines[-1].startswith("<ul"):
        html_lines.append("</ul>")
    if html_lines and html_lines[-1].startswith("<table"):
        html_lines.append("</table>")

    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{CSS}</style></head><body>\n" + "\n".join(html_lines) + "\n</body></html>"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input dtrust JSON report")
    ap.add_argument("--out", dest="out", required=True, help="Output file (.md or .html)")
    args = ap.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    md = render_markdown(data)

    outp = Path(args.out)
    if outp.suffix.lower() == ".md":
        outp.write_text(md, encoding="utf-8")
        print(f"Wrote Markdown: {outp}")
    elif outp.suffix.lower() == ".html":
        html_doc = render_html(md, title=f"dtrust Report — Tier {data.get('tier')}")
        outp.write_text(html_doc, encoding="utf-8")
        print(f"Wrote HTML: {outp}")
    else:
        print("Output extension must be .md or .html", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
