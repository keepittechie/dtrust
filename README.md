# DistroTrust (dtrust)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Make](https://img.shields.io/badge/build-make-lightgrey)

DistroTrust scans a Linux root filesystem and produces structured trust-audit reports. It collects baseline system signals, supply-chain signals, and Tier 3 runtime signals, then scores and renders them for human review or automation.

## What it does

- **Tier 1**: distro metadata, users, groups, cron, SUID/SGID binaries, services, repo inventory
- **Tier 2**: normalized repo config, unsigned packages, PATH shadowing, `/usr/local` and `/opt` inspection
- **Tier 3**: live process audit, network listeners, runtime heuristics, kernel module inventory

The report format is JSON-first. Scoring weights live in [`templates/scoring.yaml`](./templates/scoring.yaml), and finding metadata lives in [`templates/findings.yaml`](./templates/findings.yaml).

## Quick start

```bash
git clone https://github.com/keepittechie/dtrust.git
cd dtrust

# Generate a Tier 3 report
python3 dtrust_cli.py --tier 3 --rootfs / --out build/tier3.json

# Score it
python3 score-dtrust-report.py build/tier3.json > build/tier3.score.json

# Render the main HTML report
python3 render_pretty.py --in build/tier3.json --out build/tier3_pretty.html --score build/tier3.score.json
```

Open the report with:

```bash
xdg-open build/tier3_pretty.html
```

## Common commands

Generate reports:

```bash
python3 dtrust_cli.py --tier 1 --rootfs / --out build/tier1.json
python3 dtrust_cli.py --tier 2 --rootfs / --out build/tier2.json
python3 dtrust_cli.py --tier 3 --rootfs / --out build/tier3.json
```

Score reports:

```bash
# Full score output
python3 score-dtrust-report.py build/tier3.json

# Findings only
python3 score-dtrust-report.py --findings-only build/tier3.json

# Compact CI-friendly summary
python3 score-dtrust-report.py --json-summary build/tier3.json
```

Render reports:

```bash
# Main HTML renderer
python3 render_pretty.py --in build/tier3.json --out build/tier3_pretty.html --score build/tier3.score.json

# Lightweight Markdown/HTML fallback
python3 render_report.py --in build/tier3.json --out build/tier3.md
python3 render_report.py --in build/tier3.json --out build/tier3.html
```

## Which renderer should I use?

- Use [`render_pretty.py`](./render_pretty.py) for the main HTML report.
- Use [`render_report.py`](./render_report.py) only if you want a simpler Markdown or HTML export.

## Make targets

```bash
make tier1
make tier2
make tier3
make score-json3
make render_pretty3
make regression
```

`make regression` validates, scores, and renders the golden example reports under [`examples/`](./examples).

## Project layout

```text
.
├── dtrust_cli.py           # Report generator
├── score-dtrust-report.py  # Scoring and findings
├── render_pretty.py        # Main HTML renderer
├── render_report.py        # Minimal fallback renderer
├── examples/               # Golden reports for regression testing
├── scripts/                # Validation and helper scripts
├── templates/              # Schemas, scoring policy, finding policy
└── Makefile                # Common tasks
```

## Notes

- Tier 3 runtime inspection depends on live `/proc` and `/sys` data.
- Known third-party kernel module layouts such as Arch `extramodules` and DKMS paths are categorized separately from true path anomalies.
- This tool helps investigate trust signals; it does not prove that a distro is safe.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Before opening a PR, run:

```bash
make regression
```

## License

Licensed under the [Apache License, Version 2.0](./LICENSE).
