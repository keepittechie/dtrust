# dtrust – Revive & Complete Plan

This checklist captures concrete, high‑impact steps to finish and modernize **dtrust**. It’s organized by milestone so we can work through it quickly and get to a shippable 0.1.0.

## Milestone 0: Baseline & Smoke Tests
- [ ] Add `--tier` and `--out` flags to `dtrust.sh` (keep current defaults).
- [ ] Support `--rootfs <path>` to scan mounted images/containers (no host writes).
- [ ] Normalize environment: `LC_ALL=C`, `PATH` safety, `set -Eeuo pipefail`.
- [ ] Create a tiny sample report in `examples/` for each tier (Tier1–Tier2 now).
- [ ] Write a **JSON Schema** for reports: `templates/report.schema.json` (semver: `"schema_version": "1.0.0"`).
- [ ] Add a validator step: `scripts/validate.py <report.json>` using `jsonschema`.

## Milestone 1: Tier 1 & 2 Feature-Complete
- [ ] Finish `modules/tier1.sh` outputs: hidden files, suid/sgid, cron, open ports, users, services, kernel, distro, timestamp.
- [ ] Finish `modules/tier2.sh` outputs: unsigned/manual packages, repo remotes, untracked files in `/usr/local`, PATH shadowing.
- [ ] Define **stable keys** and example payloads in `templates/examples.tier{1,2}.json`.
- [ ] Ensure **no absolute host paths** leak when `--rootfs` is used (prefix with `/` intentionally).

## Milestone 2: Scoring & Policy
- [ ] Complete `score-dtrust-report.py` with documented rationale for each deduction.
- [ ] Externalize weights to `templates/scoring.yaml` and load in the scorer.
- [ ] Include output format: `{"score": 0-100, "penalties": [...], "signals": {...}}`.
- [ ] Add `dtrust score <report.json>` subcommand wrapper around the Python scorer.

## Milestone 3: Output UX
- [ ] Replace `json-to-md.sh` with Python/Jinja2: `render_report.py` (Markdown + HTML).
- [ ] Create a minimal **static site** generator: `md-to-html.sh` (keep) or `render_site.py` that builds `/site` from `/profiles`.
- [ ] Add print-friendly CSS + dark mode, and a summary badge (`score.svg`).

## Milestone 4: Packaging & CI
- [ ] Provide `Makefile` with targets: `lint`, `test`, `build`, `package`.
- [ ] Lint: `shellcheck` + `shfmt` for bash, `black` + `ruff` for Python.
- [ ] Unit tests with `bats` for shell modules; GitHub Actions workflow.
- [ ] Build artifacts: `.deb` and `.rpm` (fpm), and a Docker image `ghcr.io/<org>/dtrust`.

## Milestone 5: Safety & Performance
- [ ] Drop all `sudo` from scripts; clearly document required capabilities.
- [ ] Rate-limit expensive `find`/`sha256sum`; skip known heavy dirs (configurable allow/deny).
- [ ] Add timeouts per probe and overall `--max-seconds` CLI cap.
- [ ] Respect offline mode (no network calls).

## Milestone 6: Docs
- [ ] Expand `README.md` with **quick start**, **threat model**, **what dtrust is/is not**, and **example reports**.
- [ ] Add an **FAQ** and a `CONTRIBUTING.md` with style, testing, and release flow.
- [ ] Add `SECURITY.md` to report issues privately.

---

### Nice-to-haves
- [ ] Container image scanner mode (mount rootfs of `docker save` tar).
- [ ] Live system delta mode (baseline vs current, alert on drift).
- [ ] Export to SARIF for CI code scanning UIs.

