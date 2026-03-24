#!/usr/bin/env python3
import argparse
import html
import json
import sys
from pathlib import Path

CSS = """\
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Arial,sans-serif;line-height:1.5;margin:2rem;max-width:1000px}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}
pre{background:#f6f8fa;padding:1rem;overflow:auto;border-radius:8px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}
th{background:#fafafa}
"""


def render_markdown(report):
    distro = report.get("distro", {}) or {}
    lines = [
        f"# dtrust Report - Tier {report.get('tier')}",
        "",
        f"- **Schema**: `{report.get('schema_version')}`",
        f"- **Timestamp (UTC)**: `{report.get('timestamp_utc')}`",
        f"- **Target rootfs**: `{report.get('target_rootfs')}`",
        f"- **Kernel**: `{report.get('kernel')}`",
        f"- **Distro**: `{distro.get('pretty_name') or distro.get('name')}`",
        "",
        "## Summary",
        "",
        f"- **Users**: `{len(report.get('users', []) or [])}`",
        f"- **Groups**: `{len(report.get('groups', []) or [])}`",
        f"- **SUID/SGID entries**: `{len(report.get('suid_sgid', []) or [])}`",
        f"- **Services**: `{len(report.get('services', []) or [])}`",
    ]

    if report.get("tier") in (2, 3):
        lines.extend(
            [
                f"- **Unsigned packages**: `{len(report.get('unsigned_packages', []) or [])}`",
                f"- **PATH shadowing entries**: `{len(report.get('path_shadowing', []) or [])}`",
                f"- **Manual areas**: `{len((report.get('manual_areas') or {}).keys())}`",
            ]
        )
    if report.get("tier") == 3:
        advanced = report.get("advanced_checks", {}) or {}
        process_summary = ((advanced.get("process_audit") or {}).get("summary") or {})
        network_summary = ((advanced.get("network_listeners") or {}).get("summary") or {})
        kernel_summary = ((advanced.get("kernel_integrity") or {}).get("summary") or {})
        lines.extend(
            [
                f"- **Runtime processes**: `{process_summary.get('total_processes', 0)}`",
                f"- **Deleted executable processes**: `{process_summary.get('deleted_executable_processes', 0)}`",
                f"- **Suspicious executable processes**: `{process_summary.get('suspicious_executable_processes', 0)}`",
                f"- **Orphan-like processes**: `{process_summary.get('orphan_like_processes', 0)}`",
                f"- **Network listeners**: `{network_summary.get('total_listeners', 0)}`",
                f"- **Wildcard binds**: `{network_summary.get('wildcard_bind_count', 0)}`",
                f"- **Loaded kernel modules**: `{kernel_summary.get('loaded_modules', 0)}`",
                f"- **Suspicious kernel modules**: `{kernel_summary.get('suspicious_modules', 0)}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Report JSON",
            "```json",
            json.dumps(report, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)


def render_html(markdown_text, title):
    body = ""
    in_code = False
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            body += f"<h1>{html.escape(line[2:])}</h1>\n"
        elif line.startswith("## "):
            body += f"<h2>{html.escape(line[3:])}</h2>\n"
        elif line.startswith("- "):
            if not body.endswith("</ul>\n"):
                body += "<ul>\n"
            body += f"<li>{html.escape(line[2:])}</li>\n"
        elif line.startswith("```"):
            if in_code:
                body += "</code></pre>\n"
            else:
                body += "<pre><code>"
            in_code = not in_code
        elif line.strip() == "":
            if body.endswith("</li>\n"):
                body += "</ul>\n"
            body += "\n"
        else:
            if in_code:
                body += html.escape(line) + "\n"
            else:
                body += f"<p>{html.escape(line)}</p>\n"
    if in_code:
        body += "</code></pre>\n"
    if body.endswith("</li>\n"):
        body += "</ul>\n"
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True)
    parser.add_argument("--out", dest="out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    markdown = render_markdown(report)
    out_path = Path(args.out)

    if out_path.suffix.lower() == ".md":
        out_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote Markdown: {out_path}")
    elif out_path.suffix.lower() == ".html":
        html_doc = render_html(markdown, f"dtrust Report - Tier {report.get('tier')}")
        out_path.write_text(html_doc, encoding="utf-8")
        print(f"Wrote HTML: {out_path}")
    else:
        print("Output extension must be .md or .html", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
