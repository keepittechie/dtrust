#!/usr/bin/env python3
# Score a dtrust report using templates/scoring.yaml weights.
# Outputs JSON:
# {
#   "score": <0..100>,
#   "penalties": [{"reason": "...", "value": -X}, ...],
#   "signals": {...}
# }

import sys, json
from pathlib import Path

def load_weights():
    # Try PyYAML first; if not available, naive fallback parser
    path = Path(__file__).resolve().parents[0] / "templates" / "scoring.yaml"
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
        cur = data
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line:
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if not v:
                    cur[k] = {}
                    cur = cur[k]
                else:
                    try:
                        cur[k] = float(v) if "." in v else int(v)
                    except Exception:
                        cur[k] = v
        return data

def score_tier1(report, weights):
    penalties = []
    signals = {}

    suids = report.get("suid_sgid", []) or []
    count = len(suids)
    signals["suid_count"] = count

    # FIX: use tier1 weights (was mistakenly looking up "tier2")
    w = (weights.get("weights", {}) or {}).get("tier1", {}) or {}
    per = float(w.get("suid_per_file_penalty", 0.2))
    cap = int(w.get("suid_cap", 15))

    applied = min(count, cap)
    if applied > 0:
        penalties.append({"reason": f"{applied} suid/sgid binaries", "value": -per * applied})

    score = 100.0 + sum(p["value"] for p in penalties)
    if score < 0:
        score = 0.0
    return round(score, 1), penalties, signals


def _count_shadow_bins(shadows):
    """Robustly count shadowed binaries across multiple possible shapes."""
    if isinstance(shadows, dict):
        # expected original shape: {"/usr/bin": ["foo","bar"], ...}
        total = 0
        for v in shadows.values():
            if isinstance(v, list):
                total += len(v)
            elif isinstance(v, (int, float)):
                total += int(v)
            elif v is None:
                continue
            else:
                # fallback: count as 1 if it’s some other type
                total += 1
        return total

    if isinstance(shadows, list):
        # Anduin shape: list of strings or objects
        total = 0
        for item in shadows:
            if isinstance(item, str):
                total += 1
            elif isinstance(item, dict):
                # Try common keys that might contain the actual list
                for k in ("bins", "binaries", "paths", "files"):
                    v = item.get(k)
                    if isinstance(v, list):
                        total += len(v)
                        break
                else:
                    # No recognizable list field -> count the item itself
                    total += 1
            elif isinstance(item, (int, float)):
                total += int(item)
            else:
                total += 1
        return total

    # anything else
    return 0


def score_tier2(report, weights):
    penalties = []
    signals = {}

    shadows = report.get("path_shadowing", {})  # may be dict OR list
    shadow_bins = _count_shadow_bins(shadows)
    signals["shadow_bin_paths"] = shadow_bins

    w = (weights.get("weights", {}) or {}).get("tier2", {}) or {}
    per = float(w.get("shadowing_per_bin_penalty", 0.1))
    cap = w.get("shadowing_cap")

    total_pen = per * shadow_bins
    if cap is not None:
        try:
            total_pen = min(total_pen, float(cap))
        except Exception:
            pass

    if shadow_bins:
        penalties.append({
            "reason": f"{shadow_bins} PATH shadowed binaries",
            "value": -float(total_pen)
        })

    score = 100.0 + sum(p["value"] for p in penalties)
    if score < 0:
        score = 0.0
    return round(score, 1), penalties, signals


def main():
    if len(sys.argv) != 2:
        print("Usage: score-dtrust-report.py <report.json>", file=sys.stderr)
        sys.exit(2)
    report_path = Path(sys.argv[1])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    weights = load_weights()
    if report.get("tier") == 1:
        score, penalties, signals = score_tier1(report, weights)
    elif report.get("tier") == 2:
        score, penalties, signals = score_tier2(report, weights)
    else:
        print("Unsupported tier for scoring.", file=sys.stderr); sys.exit(3)
    out = {"score": score, "penalties": penalties, "signals": signals}
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
