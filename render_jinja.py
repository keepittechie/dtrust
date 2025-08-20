#!/usr/bin/env python3
import sys, json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

def main():
    if len(sys.argv) != 4:
        print("Usage: render_jinja.py <report.json> <format: html|md> <out>")
        sys.exit(2)
    report_path, fmt, out_path = sys.argv[1:]
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    # load score
    import subprocess
    scorer = Path(__file__).resolve().parent / "score-dtrust-report.py"
    proc = subprocess.run([sys.executable, str(scorer), report_path], capture_output=True, text=True)
    score = {}
    try:
        score = json.loads(proc.stdout)
    except Exception:
        pass

    env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent / "templates" / "jinja")), autoescape=select_autoescape())
    tplname = "report.html.j2" if fmt == "html" else "report.md.j2"
    tpl = env.get_template(tplname)
    out = tpl.render(report=report, score=score)
    Path(out_path).write_text(out, encoding="utf-8")

if __name__ == "__main__":
    main()