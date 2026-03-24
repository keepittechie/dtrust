#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
TMP = ROOT / "build" / "regression_examples"


def run(cmd):
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def main():
    TMP.mkdir(parents=True, exist_ok=True)

    example_files = [
        EXAMPLES / "tier1_golden.json",
        EXAMPLES / "tier2_golden.json",
        EXAMPLES / "tier3_golden.json",
    ]

    for example in example_files:
        if not example.exists():
            raise SystemExit(f"Missing example fixture: {example}")

        run([sys.executable, "scripts/validate.py", str(example)])

        score_out = run([sys.executable, "score-dtrust-report.py", str(example)])
        score = json.loads(score_out)
        if "score" not in score or "signals" not in score or "findings" not in score:
            raise SystemExit(f"Invalid score output for {example.name}")

        html_out = TMP / f"{example.stem}.html"
        pretty_out = TMP / f"{example.stem}_pretty.html"
        md_out = TMP / f"{example.stem}.md"

        run([sys.executable, "render_report.py", "--in", str(example), "--out", str(html_out)])
        run([sys.executable, "render_report.py", "--in", str(example), "--out", str(md_out)])
        run([sys.executable, "render_pretty.py", "--in", str(example), "--out", str(pretty_out)])

        if not html_out.exists() or not pretty_out.exists() or not md_out.exists():
            raise SystemExit(f"Renderer did not produce expected artifacts for {example.name}")

    print("OK: example regression suite passed.")


if __name__ == "__main__":
    main()
