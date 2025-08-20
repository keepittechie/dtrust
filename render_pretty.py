#!/usr/bin/env python3
"""
render_pretty.py
Sleek HTML renderer for dtrust reports without external deps.
- Renders summary cards, score badge, and tier-specific sections
- Accepts optional --score to include computed score JSON

Usage:
  python3 render_pretty.py --in build/report.json --out build/report_pretty.html [--score build/report.score.json]
"""
import json, argparse, html
from pathlib import Path
from datetime import datetime

CSS = """\
:root{--bg:#0b0c0f;--panel:#13151a;--ink:#f6f7fb;--muted:#9aa0aa;--accent:#6aa7ff;--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c}
*{box-sizing:border-box} html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,Helvetica,Arial,sans-serif;line-height:1.5}
.wrap{max-width:1100px;margin:40px auto;padding:0 20px}
h1,h2,h3{line-height:1.2;margin:0 0 12px}
p{margin:8px 0}
.card{background:var(--panel);border:1px solid #1f2229;border-radius:16px;padding:16px;box-shadow:0 1px 0 rgba(255,255,255,.02), 0 12px 40px rgba(0,0,0,.3)}
.grid{display:grid;gap:16px}
.grid.cols-3{grid-template-columns:repeat(3,1fr)}
.grid.cols-2{grid-template-columns:repeat(2,1fr)}
.kv{display:grid;grid-template-columns:220px 1fr;gap:8px 12px}
.badge{display:inline-flex;align-items:center;gap:10px;background:#0f1116;border:1px solid #2a2f3a;border-radius:999px;padding:10px 14px;font-weight:600}
.tag{display:inline-block;padding:4px 10px;border:1px solid #2a2f3a;border-radius:999px;background:#0f1116;color:var(--muted);font-size:.85rem}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border-bottom:1px solid #1f2229;padding:8px 6px;text-align:left;font-size:.95rem}
.small{color:var(--muted);font-size:.9rem}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}
hr{border:none;border-top:1px solid #1f2229;margin:24px 0}
.score{font-size:1.4rem;font-weight:800}
.score.good{color:var(--ok)} .score.warn{color:var(--warn)} .score.bad{color:var(--bad)}
.section{margin-top:20px}
"""

HTML_SHELL = """<!doctype html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
  {content}
</div>
</body></html>
"""

def esc(x): return html.escape(str(x)) if x is not None else ""

def score_class(v):
    try:
        v = float(v)
    except Exception:
        return ""
    if v >= 90: return "good"
    if v >= 70: return "warn"
    return "bad"

def render_summary(report, score):
    distro = report.get("distro", {}) or {}
    items = []
    items.append("<div class='card'><div class='grid cols-3'>"                 f"<div><div class='small'>Schema</div><div class='mono'>{esc(report.get('schema_version'))}</div></div>"                 f"<div><div class='small'>Tier</div><div class='mono'>{esc(report.get('tier'))}</div></div>"                 f"<div><div class='small'>Target</div><div class='mono'>{esc(report.get('target_rootfs'))}</div></div>"                 "</div></div>")
    badge = ""
    if score:
        cls = score_class(score.get("score"))
        badge = f"<div class='card'><div class='score {cls}'>Score: {esc(score.get('score'))}</div><div class='small'>{esc(len(score.get('penalties',[])))} penalties • signals captured: {esc(len(score.get('signals',{})))}</div></div>"
    sys_card = "<div class='card'><h2>System</h2><div class='kv'>" \
               f"<div class='small'>Timestamp (UTC)</div><div class='mono'>{esc(report.get('timestamp_utc'))}</div>" \
               f"<div class='small'>Kernel</div><div class='mono'>{esc(report.get('kernel'))}</div>" \
               f"<div class='small'>Distro</div><div class='mono'>{esc(distro.get('pretty_name') or distro.get('name'))}</div>" \
               "</div></div>"
    return "<div class='grid cols-2'>" + items[0] + (badge or "") + sys_card + "</div>"

def render_users(report):
    users = report.get("users") or []
    if not users: return ""
    rows = "".join(f"<tr><td>{esc(u.get('name'))}</td><td class='mono'>{esc(u.get('uid'))}</td><td class='mono'>{esc(u.get('gid'))}</td><td class='mono'>{esc(u.get('home'))}</td><td class='mono'>{esc(u.get('shell'))}</td></tr>" for u in users[:200])
    extra = f"<div class='small'>and {len(users)-200} more…</div>" if len(users)>200 else ""
    return f"<div class='section card'><h2>Users</h2><table class='table'><thead><tr><th>name</th><th>uid</th><th>gid</th><th>home</th><th>shell</th></tr></thead><tbody>{rows}</tbody></table>{extra}</div>"

def render_groups(report):
    groups = report.get("groups") or []
    if not groups: return ""
    rows = "".join(f"<tr><td>{esc(g.get('name'))}</td><td class='mono'>{esc(g.get('gid'))}</td><td class='mono'>{esc(', '.join(g.get('members') or []))}</td></tr>" for g in groups[:200])
    extra = f"<div class='small'>and {len(groups)-200} more…</div>" if len(groups)>200 else ""
    return f"<div class='section card'><h2>Groups</h2><table class='table'><thead><tr><th>name</th><th>gid</th><th>members</th></tr></thead><tbody>{rows}</tbody></table>{extra}</div>"

def render_cron(report):
    cron = report.get("cron") or {}
    sys_cron = (cron.get("system_crontab") or "").strip()
    cron_d = cron.get("cron_d_files") or []
    dirs = cron.get("cron_dirs") or {}
    parts = ["<div class='section card'><h2>Cron</h2>"]
    parts.append("<div class='small'>/etc/crontab</div>")
    parts.append(f"<pre class='mono'>{esc(sys_cron)}</pre>")
    if cron_d:
        parts.append("<div class='small'>/etc/cron.d</div>")
        parts.append("<p>" + ", ".join(esc(x) for x in cron_d[:100]) + ("…" if len(cron_d)>100 else "") + "</p>")
    for k, v in dirs.items():
        parts.append(f"<div class='small'>/etc/{esc(k)}</div>")
        parts.append("<p>" + ", ".join(esc(x) for x in v[:100]) + ("…" if len(v)>100 else "") + "</p>")
    parts.append("</div>")
    return "".join(parts)

def render_suids(report):
    arr = report.get("suid_sgid") or []
    if not arr: return ""
    rows = "".join(f"<tr><td class='mono'>{esc(x.get('path'))}</td><td class='mono'>{esc(x.get('mode_octal'))}</td><td>{'✓' if x.get('suid') else ''}</td><td>{'✓' if x.get('sgid') else ''}</td></tr>" for x in arr[:200])
    extra = f"<div class='small'>and {len(arr)-200} more…</div>" if len(arr)>200 else ""
    return f"<div class='section card'><h2>SUID/SGID Binaries</h2><table class='table'><thead><tr><th>path</th><th>mode</th><th>suid</th><th>sgid</th></tr></thead><tbody>{rows}</tbody></table>{extra}</div>"

def render_services(report):
    svc = report.get("services") or []
    if not svc: return ""
    items = "".join(f"<li class='mono'>{esc(x)}</li>" for x in svc[:400])
    extra = f"<div class='small'>and {len(svc)-400} more…</div>" if len(svc)>400 else ""
    return f"<div class='section card'><h2>Systemd Services (filenames)</h2><ul>{items}</ul>{extra}</div>"

def render_tier2(report):
    repos = report.get("repos") or {}
    apt = repos.get("apt") or []
    yum = repos.get("yum_dnf") or []
    shadows = report.get("path_shadowing") or {}
    manual = report.get("manual_areas") or []

    parts = ["<div class='grid cols-2'>"]
    # APT
    apt_blocks = []
    for x in apt[:6]:
        filep = esc(x.get('file'))
        lines_text = "\n".join(x.get('lines') or [])
        apt_blocks.append(f"<div class='small'>{filep}</div><pre class='mono'>{esc(lines_text)}</pre>")
    apthtml = "<div class='card'><h2>APT Sources</h2>" + "".join(apt_blocks) + "</div>"
    # YUM/DNF
    yum_blocks = []
    for x in yum[:6]:
        filep = esc(x.get('file'))
        content_text = x.get('content') or ""
        yum_blocks.append(f"<div class='small'>{filep}</div><pre class='mono'>{esc(content_text)}</pre>")
    yumhtml = "<div class='card'><h2>YUM/DNF Repos</h2>" + "".join(yum_blocks) + "</div>"
    parts += [apthtml, yumhtml]
    parts.append("</div>")
    # PACMAN
    pac = repos.get("pacman") or []
    pac_blocks = []
    for x in pac[:6]:
        filep = esc(x.get("file"))
        content_text = x.get("content") or ""
        servers = x.get("servers") or []
        body = esc(content_text) if content_text else esc("\n".join(servers))
        pac_blocks.append(f"<div class='small'>{filep}</div><pre class='mono'>{body}</pre>")
    pachtml = "<div class='card'><h2>Pacman Repos</h2>" + "".join(pac_blocks) + "</div>"
    parts += [pachtml]

    if shadows:
        rows = "".join(f"<tr><td>{esc(k)}</td><td class='mono'>{esc(', '.join(v))}</td></tr>" for k, v in list(shadows.items())[:200])
        parts.append(f"<div class='section card'><h2>PATH Shadowing</h2><table class='table'><thead><tr><th>binary</th><th>paths</th></tr></thead><tbody>{rows}</tbody></table></div>")

    if manual:
        parts.append("<div class='section card'><h2>Manual Areas</h2>")
        for m in manual[:6]:
            entries = ", ".join(esc(x) for x in (m.get('entries') or [])[:20])
            parts.append(f"<div class='small'>{esc(m.get('dir'))}</div><p class='mono'>{entries}</p>")
        parts.append("</div>")
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--score", dest="score", default=None, help="Optional JSON with score/penalties/signals")    
    args = ap.parse_args()

    report = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    score = None
    if args.score and Path(args.score).exists():
        try:
            score = json.loads(Path(args.score).read_text(encoding="utf-8"))
        except Exception:
            score = None

    title = f"dtrust Report — Tier {report.get('tier')}"
    content = [f"<h1>{html.escape(title)}</h1>"]
    content.append(render_summary(report, score))

    tier = report.get("tier")
    if tier == 1:
        content.append(render_users(report))
        content.append(render_groups(report))
        content.append(render_cron(report))
        content.append(render_suids(report))
        content.append(render_services(report))
    elif tier == 2:
        content.append(render_tier2(report))

    html_doc = HTML_SHELL.format(title=html.escape(title), css=CSS, content="\n".join(c for c in content if c))
    Path(args.out).write_text(html_doc, encoding="utf-8")
    print(f"Wrote pretty HTML: {args.out}")

if __name__ == "__main__":
    main()