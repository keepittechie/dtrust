# dtrust

**dtrust** is a Linux Trust Profiling tool that scans any Linux distribution for potential risks, suspicious behavior, and trust issues. It's designed for security-minded users, distro testers, and system auditors.

## Features

- Modular audit system with tiers (basic to forensic)
- Generates JSON trust reports
- Transparent, reproducible audit output
- Fully offline-compatible

## Usage

```bash
chmod +x dtrust.sh
./dtrust.sh --tier1
./dtrust.sh --tier2
```

## Markdown Reports

Convert your JSON reports to readable `.md` files for sharing or publishing:

```bash
./json-to-md.sh profiles/<your-report>.json
```

## Tier System

| Tier | Description |
|------|-------------|
| 1    | **Basic Audit** – Startup services, SUID files, hidden dotfiles, cron jobs, and open ports |
| 2    | **Integrity & Origin Audit** – Scans for unsigned or manually installed packages and flags non-official repo mirrors |
| 3+   | **Advanced & Forensic** – Coming soon: runtime tracing, memory analysis, external mount audits |
