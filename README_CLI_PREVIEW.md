
# dtrust Python CLI Preview

This is a minimal Python-first CLI for dtrust to stabilize the data model and support `--rootfs` scanning.

## Usage

```bash
python3 dtrust_cli.py --tier 1 --rootfs / --out /tmp/report.json --max-seconds 15
```

- `--tier`       : audit tier (currently 1)
- `--rootfs`     : target root filesystem to scan (default `/`)
- `--out`        : where to write the JSON report (`-` for stdout)
- `--max-seconds`: overall time budget

## Validate a report

```bash
python3 scripts/validate.py examples/tier1_golden.json
```

Validator exit code: 0 means OK.

## Notes
- If `typer` is installed, the CLI uses it; otherwise it falls back to `argparse` automatically.
- Tier 1 probes rely on file inspection and avoid executing inside the target rootfs.
- Kernel version is only reported when scanning `/` (live host).
