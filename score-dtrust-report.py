#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_yaml(path):
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_weights():
    return _load_yaml(ROOT / "templates" / "scoring.yaml")


def load_finding_policy():
    return _load_yaml(ROOT / "templates" / "findings.yaml")


def add_penalty(penalties, reason, value):
    if value <= 0:
        return
    penalties.append({"reason": reason, "value": -round(float(value), 2)})


def add_finding(findings, policy, finding_id, count, evidence=None, scored=False):
    if not count:
        return
    details = ((policy.get("findings") or {}).get(finding_id) or {})
    findings.append(
        {
            "id": finding_id,
            "severity": details.get("severity", "info"),
            "category": details.get("category", "uncategorized"),
            "title": details.get("title", finding_id),
            "count": int(count),
            "scored": bool(scored),
            "evidence": evidence or {},
        }
    )


def score_tier1(report, weights, policy):
    penalties = []
    signals = {}
    findings = []

    suids = report.get("suid_sgid", []) or []
    services = report.get("services", []) or []
    cron = report.get("cron", {}) or {}

    signals["suid_count"] = len(suids)
    signals["service_count"] = len(services)
    signals["cron_d_count"] = len(cron.get("cron_d_files", []) or [])

    w = ((weights.get("weights") or {}).get("tier1") or {})
    per = float(w.get("suid_per_file_penalty", 0.2))
    cap = int(w.get("suid_cap", 15))

    applied = min(len(suids), cap)
    add_penalty(penalties, f"{applied} suid/sgid binaries", per * applied)
    add_finding(
        findings,
        policy,
        "tier1.suid_sgid",
        len(suids),
        {"sample_paths": [item.get("path") for item in suids[:10]]},
        scored=applied > 0,
    )

    score = max(0.0, 100.0 + sum(p["value"] for p in penalties))
    return round(score, 1), penalties, signals, findings


def _count_shadow_bins(shadows):
    if isinstance(shadows, dict):
        total = 0
        for value in shadows.values():
            if isinstance(value, list):
                total += len(value)
        return total

    if isinstance(shadows, list):
        total = 0
        for item in shadows:
            if isinstance(item, str):
                total += 1
            elif isinstance(item, dict):
                shadowed = item.get("shadowed")
                if isinstance(shadowed, list):
                    total += len(shadowed)
                else:
                    total += 1
        return total

    return 0


def _iter_repos(report):
    repos = report.get("repos", {}) or {}
    for key in ("apt", "yum_dnf"):
        for repo in repos.get(key, []) or []:
            if isinstance(repo, dict):
                yield repo
    for repo in repos.get("pacman", []) or []:
        if isinstance(repo, dict) and "name" in repo:
            yield repo


def score_tier2_like(report, weights, policy, tier_name):
    penalties = []
    signals = {}
    findings = []

    unsigned = report.get("unsigned_packages", []) or []
    shadows = report.get("path_shadowing", []) or []
    manual = report.get("manual_areas", {}) or {}

    shadow_bins = _count_shadow_bins(shadows)
    manual_world_writable = sum(
        int((payload.get("stats", {}) or {}).get("world_writable", 0))
        for payload in manual.values()
        if isinstance(payload, dict)
    )

    signals["shadow_bin_paths"] = shadow_bins
    signals["unsigned_packages"] = len(unsigned)
    signals["manual_world_writable"] = manual_world_writable

    w = ((weights.get("weights") or {}).get(tier_name) or {})
    shadow_penalty = float(w.get("shadowing_per_bin_penalty", 0.1)) * shadow_bins
    shadow_cap = w.get("shadowing_cap")
    if shadow_cap is not None:
        try:
            shadow_penalty = min(shadow_penalty, float(shadow_cap))
        except Exception:
            pass
    add_penalty(penalties, f"{shadow_bins} PATH shadowed binaries", shadow_penalty)
    add_finding(
        findings,
        policy,
        f"{tier_name}.path_shadowing",
        shadow_bins,
        {"sample_binaries": [item.get("basename") for item in shadows[:10] if isinstance(item, dict)]},
        scored=shadow_bins > 0 and shadow_penalty > 0,
    )

    repo_http_penalty = float(w.get("repo_custom_source_penalty", 2))
    insecure_repos = []
    for repo in _iter_repos(report):
        baseurl = repo.get("baseurl") or ""
        if isinstance(baseurl, str) and baseurl.startswith("http://"):
            insecure_repos.append({"name": repo.get("name"), "reason": "http_baseurl"})
        if repo.get("gpgcheck") is False:
            insecure_repos.append({"name": repo.get("name"), "reason": "gpgcheck_disabled"})
    add_penalty(penalties, f"{len(insecure_repos)} insecure repository settings", repo_http_penalty * len(insecure_repos))
    signals["insecure_repo_settings"] = len(insecure_repos)
    add_finding(
        findings,
        policy,
        f"{tier_name}.repo_security",
        len(insecure_repos),
        {"sample_repos": insecure_repos[:10]},
        scored=bool(insecure_repos),
    )

    unsigned_penalty = float(w.get("unsigned_package_penalty", 3))
    add_penalty(penalties, f"{len(unsigned)} unsigned packages", unsigned_penalty * len(unsigned))
    add_finding(
        findings,
        policy,
        f"{tier_name}.unsigned_packages",
        len(unsigned),
        {"sample_packages": unsigned[:10]},
        scored=bool(unsigned),
    )

    manual_penalty = float(w.get("manual_area_entry_penalty", 0.1))
    add_penalty(
        penalties,
        f"{manual_world_writable} world-writable manual-area files",
        manual_penalty * manual_world_writable,
    )
    add_finding(
        findings,
        policy,
        f"{tier_name}.manual_area_world_writable",
        manual_world_writable,
        {"areas": {key: (value.get("stats") or {}).get("world_writable", 0) for key, value in manual.items()}},
        scored=manual_world_writable > 0,
    )

    score = max(0.0, 100.0 + sum(p["value"] for p in penalties))
    return round(score, 1), penalties, signals, findings


def score_tier3(report, weights, policy):
    score, penalties, signals, findings = score_tier2_like(report, weights, policy, "tier3")

    advanced = report.get("advanced_checks", {}) or {}
    process_audit = (advanced.get("process_audit") or {})
    process_summary = process_audit.get("summary") or {}
    network_checks = (advanced.get("network_listeners") or {})
    network_summary = network_checks.get("summary") or {}
    kernel_checks = (advanced.get("kernel_integrity") or {})
    kernel_summary = kernel_checks.get("summary") or {}

    deleted_execs = int(process_summary.get("deleted_executable_processes", 0) or 0)
    suspicious_execs = int(process_summary.get("suspicious_executable_processes", 0) or 0)
    orphan_like = int(process_summary.get("orphan_like_processes", 0) or 0)
    wildcard_binds = int(network_summary.get("wildcard_bind_count", 0) or 0)
    unattributed = int(network_summary.get("unattributed_listener_count", 0) or 0)
    suspicious_modules = int(kernel_summary.get("suspicious_modules", 0) or 0)
    missing_module_files = int(kernel_summary.get("missing_module_files", 0) or 0)
    tainted_modules = int(kernel_summary.get("tainted_modules", 0) or 0)

    signals["runtime_deleted_exec_processes"] = deleted_execs
    signals["runtime_suspicious_exec_processes"] = suspicious_execs
    signals["runtime_orphan_like_processes"] = orphan_like
    signals["runtime_wildcard_binds"] = wildcard_binds
    signals["runtime_unattributed_listeners"] = unattributed
    signals["kernel_suspicious_modules"] = suspicious_modules
    signals["kernel_missing_module_files"] = missing_module_files
    signals["kernel_tainted_modules"] = tainted_modules

    w = ((weights.get("weights") or {}).get("tier3") or {})
    deleted_exec_penalty = float(w.get("deleted_exec_penalty", 4)) * deleted_execs
    suspicious_exec_penalty = float(w.get("suspicious_exec_penalty", 1.5)) * suspicious_execs
    orphan_penalty = float(w.get("orphan_like_penalty", 0.5)) * orphan_like
    wildcard_penalty = float(w.get("wildcard_listener_penalty", 1.5)) * wildcard_binds
    unattributed_penalty = float(w.get("unattributed_listener_penalty", 2)) * unattributed
    suspicious_module_penalty = float(w.get("suspicious_module_penalty", 2)) * suspicious_modules
    missing_module_penalty = float(w.get("missing_module_file_penalty", 3)) * missing_module_files
    tainted_module_penalty = float(w.get("tainted_module_penalty", 2)) * tainted_modules

    add_penalty(penalties, f"{deleted_execs} processes running deleted executables", deleted_exec_penalty)
    add_penalty(penalties, f"{suspicious_execs} processes with suspicious executable paths", suspicious_exec_penalty)
    add_penalty(penalties, f"{orphan_like} orphan-like processes", orphan_penalty)
    add_penalty(penalties, f"{wildcard_binds} wildcard listeners", wildcard_penalty)
    add_penalty(penalties, f"{unattributed} unattributed listeners", unattributed_penalty)
    add_penalty(penalties, f"{suspicious_modules} suspicious kernel modules", suspicious_module_penalty)
    add_penalty(penalties, f"{missing_module_files} loaded modules missing on-disk files", missing_module_penalty)
    add_penalty(penalties, f"{tainted_modules} tainted modules", tainted_module_penalty)

    suspicious_processes = process_audit.get("suspicious_processes") or []
    listeners = network_checks.get("listeners") or []
    modules = kernel_checks.get("modules") or []

    add_finding(
        findings,
        policy,
        "tier3.deleted_exec_processes",
        deleted_execs,
        {"sample_processes": [item for item in suspicious_processes if item.get("reason") == "deleted_executable"][:10]},
        scored=deleted_exec_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.suspicious_exec_processes",
        suspicious_execs,
        {"sample_processes": suspicious_processes[:10]},
        scored=suspicious_exec_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.orphan_like_processes",
        orphan_like,
        {"summary": process_summary},
        scored=orphan_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.wildcard_listeners",
        wildcard_binds,
        {"sample_listeners": [item for item in listeners if item.get("local_address") in ("0.0.0.0", "::")][:10]},
        scored=wildcard_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.unattributed_listeners",
        unattributed,
        {"sample_listeners": [item for item in listeners if not item.get("pids")][:10]},
        scored=unattributed_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.kernel_path_anomalies",
        suspicious_modules,
        {"sample_modules": [item for item in modules if item.get("path_risk_reason")][:10]},
        scored=suspicious_module_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.kernel_missing_module_files",
        missing_module_files,
        {"sample_modules": [item for item in modules if item.get("path_risk_reason") == "missing_module_file"][:10]},
        scored=missing_module_penalty > 0,
    )
    add_finding(
        findings,
        policy,
        "tier3.kernel_tainted_modules",
        tainted_modules,
        {"sample_modules": [item for item in modules if item.get("risk_reason") == "tainted_module"][:10]},
        scored=tainted_module_penalty > 0,
    )
    categorized_only = [
        item for item in modules
        if item.get("module_path_category") not in (None, "", "in_tree")
        and item.get("path_risk_reason") in (None, "")
        and item.get("risk_reason") in (None, "")
    ]
    add_finding(
        findings,
        policy,
        "tier3.kernel_known_third_party_layouts",
        len(categorized_only),
        {"sample_modules": categorized_only[:10]},
        scored=False,
    )

    score = max(0.0, 100.0 + sum(p["value"] for p in penalties))
    return round(score, 1), penalties, signals, findings


def main():
    parser = argparse.ArgumentParser(description="Score a dtrust report and emit structured findings.")
    parser.add_argument("report_json", help="Path to a dtrust report JSON file")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--findings-only", action="store_true", help="Emit only the findings array as JSON")
    group.add_argument(
        "--json-summary",
        action="store_true",
        help="Emit a compact JSON summary with score, penalty count, finding count, and top findings",
    )
    args = parser.parse_args()

    report_path = Path(args.report_json)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    weights = load_weights()
    policy = load_finding_policy()

    tier = report.get("tier")
    if tier == 1:
        score, penalties, signals, findings = score_tier1(report, weights, policy)
    elif tier == 2:
        score, penalties, signals, findings = score_tier2_like(report, weights, policy, "tier2")
    elif tier == 3:
        score, penalties, signals, findings = score_tier3(report, weights, policy)
    else:
        print("Unsupported tier for scoring.", file=sys.stderr)
        sys.exit(3)

    full_output = {"score": score, "penalties": penalties, "signals": signals, "findings": findings}

    if args.findings_only:
        print(json.dumps(findings, indent=2))
        return

    if args.json_summary:
        summary = {
            "score": score,
            "penalty_count": len(penalties),
            "finding_count": len(findings),
            "top_findings": findings[:10],
        }
        print(json.dumps(summary, indent=2))
        return

    print(json.dumps(full_output, indent=2))


if __name__ == "__main__":
    main()
