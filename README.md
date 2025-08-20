# DistroTrust (dtrust)

DistroTrust is a tool for scanning a Linux root filesystem and collecting *trust signals*.  
It generates structured JSON reports which can then be scored and rendered into readable Markdown or HTML.  
These reports help assess how much trust you can place in a given Linux distribution or installation.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/keepittechie/dtrust.git
cd dtrust

# 2. Run a Tier-2 scan on your root filesystem
python3 dtrust_cli.py --tier 2 --rootfs / --out build/tier2.json

# 3. Score + render the results
python3 score-dtrust-report.py build/tier2.json > build/tier2.score.json
python3 render_pretty.py --in build/tier2.json --out build/tier2_pretty.html --score build/tier2.score.json

# 4. Open the final report
xdg-open build/tier2_pretty.html

---

## What it does

* **Tier 1** – Collects base information such as distribution metadata.
* **Tier 2** – Adds repository definitions (`apt`, `yum/dnf`, `pacman`), path shadowing (duplicate binaries across directories), and manual areas of interest (`/usr/local`, `/opt`).
* Higher tiers (planned) will include even more checks.

The output can be scored for consistency and rendered into a clean HTML report for inspection.

---

## Installation

Clone the repo and install the minimal dependencies:

```bash
git clone https://github.com/keepittechie/dtrust.git
cd dtrust
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

Run directly with Python:

```bash
# Tier 1
python3 dtrust_cli.py --tier 1 --rootfs / --out build/report.json

# Tier 2
python3 dtrust_cli.py --tier 2 --rootfs / --out build/tier2.json
```

Score and render the reports:

```bash
python3 score-dtrust-report.py build/tier2.json > build/tier2.score.json
python3 render_pretty.py --in build/tier2.json --out build/tier2_pretty.html --score build/tier2.score.json
```

Open `build/tier2_pretty.html` in your browser to view the results.

---

## Using `make`

This project ships with a **Makefile** so you don’t need to type long commands manually.
`make` is a build automation tool: each **target** is a named recipe that runs shell commands.

Common targets:

* `make tier1` – Collect Tier-1 signals → `build/report.json`
* `make tier2` – Collect Tier-2 signals → `build/tier2.json`
* `make score-json1` / `make score-json2` – Score the Tier-1 or Tier-2 reports
* `make render_pretty1` / `make render_pretty2` – Render polished HTML reports

For example:

```bash
make tier2
make score-json2
make render_pretty2
```

Then open:

```bash
xdg-open build/tier2_pretty.html
```

---

## Example Reports

Sample Tier-2 reports are included under [`dtrust/examples`](./dtrust/examples) for Ubuntu, Rocky Linux, and AnduinOS.
You can compare them with your own distribution scans.

---

## License

Licensed under the [Apache License, Version 2.0](./LICENSE).

```

---

Would you like me to also add **badges** (build passing, license, etc.) at the top, so it looks more polished on GitHub?
```
