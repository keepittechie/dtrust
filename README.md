# DistroTrust (dtrust)

`dtrust` is a prototype toolkit to collect, score, and render distribution trust signals from a Linux rootfs.  

## Updates
- **Tier-2 schema locked** (repos, path shadowing, manual areas).  
- **Tier-1 & Tier-2 validators** (JSON Schema, with golden examples).  
- **Pretty HTML Renderer** (`render_pretty.py`)  
  - Dark theme, responsive cards, score badge.  
  - Renders both Tier-1 (users, groups, cron, suid/sgid, services) and Tier-2 (repos, shadowing, manual areas).  
- **Makefile Targets**
  - `tier1` / `tier2` → collect reports  
  - `score1` / `score2` → score reports  
  - `score-json1` / `score-json2` → save scores as JSON  
  - `render_pretty1` / `render_pretty2` → produce polished HTML reports  
- **CI Workflow** uploads artifacts for Tier-1 pretty reports.

## Usage

Collect a Tier-1 report:
```bash
make tier1
make score-json1
make render_pretty1
```

Collect a Tier-2 report:
```bash
make tier2
make score-json2
make render_pretty2
```

Open `build/report_pretty.html` or `build/tier2_pretty.html` in a browser to view.

## Layout
- `dtrust_cli.py` — CLI (argparse-based, stable)  
- `scripts/validate.py` — schema validation  
- `render_pretty.py` — HTML renderer (no external deps)  
- `templates/*.schema.json` — JSON Schemas  
- `templates/examples.*.json` — canonical examples  
- `examples/*_golden.json` — generated goldens  
- `docs/SCHEMA_TIER1.md`, `docs/SCHEMA_TIER2.md` — schema docs  
