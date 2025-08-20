#!/usr/bin/env python3
import json
import sys
import os

if len(sys.argv) < 2:
    print("Usage: score-dtrust-report.py <report.json>")
    sys.exit(1)

with open(sys.argv[1], "r") as f:
    data = json.load(f)

score = 100
penalty_log = []

def deduct(points, reason):
    global score
    score -= points
    penalty_log.append(f"-{points}: {reason}")

tier = data.get("tier")

# --- Tier 1
if tier == 1:
    hidden = data.get("hidden_files", [])
    if hidden:
        deduct(min(len(hidden)*5, 20), f"{len(hidden)} hidden files found")
    suids = data.get("suid_files", [])
    if suids:
        deduct(min(len(suids)*3, 15), f"{len(suids)} SUID/SGID files found")

# --- Tier 2
elif tier == 2:
    unsigned = data.get("unsigned_packages", [])
    if unsigned:
        deduct(len(unsigned)*10, f"{len(unsigned)} unsigned packages")
    repos = data.get("third_party_repos", [])
    if repos:
        deduct(len(repos)*15, f"{len(repos)} third-party repos")

# --- Tier 3
elif tier == 3:
    procs = data.get("unusual_processes", [])
    if procs:
        deduct(len(procs)*15, f"{len(procs)} suspicious processes")

# --- Tier 4
elif tier == 4:
    rootkit = data.get("rootkit_scan", "")
    if "INFECTED" in rootkit.upper() or "FOUND" in rootkit.upper():
        deduct(30, "Possible rootkit found")
    modules = data.get("kernel_modules", [])
    if modules:
        for mod in modules:
            if "modified" in mod.get("sha256", ""):  # placeholder
                deduct(25, f"Modified kernel module: {mod['path']}")

# --- Tier 5
elif tier == 5:
    implants = data.get("implant_detections", [])
    if implants and implants[0] != "":
        deduct(len(implants)*20, f"{len(implants)} binary implant warnings")
    suid = data.get("suid_sgid_binaries", [])
    if suid:
        deduct(min(len(suid)*3, 15), f"{len(suid)} SUID/SGID files")
    hidden = data.get("hidden_files_outside_home", [])
    if hidden:
        deduct(min(len(hidden)*5, 20), f"{len(hidden)} hidden dotfiles")
    log = data.get("tamper_log_snippet", "")
    if "failed" in log.lower() or "unauthorized" in log.lower():
        deduct(10, "Suspicious auth log entries")

# Score floor
score = max(score, 10)

print(f"\nTrust Score: {score}/100")
print("Reasons:")
for line in penalty_log:
    print("  ", line)