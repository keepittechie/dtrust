# dtrust/scorers/tier2.py
def score_tier2(data: dict) -> dict:
    score = 100
    reasons = []

    # Repos: penalize disabled GPG, unknown mirror sources
    for r in data.get("repos", []):
        if not r.get("gpgcheck", True):
            score -= 5
            reasons.append(f"Repo {r.get('name')} has gpgcheck=0")
        if (r.get("baseurl") or "") .startswith("http://"):
            score -= 2
            reasons.append(f"Repo {r.get('name')} uses http baseurl")

    # Unsigned packages
    unsigned = data.get("unsigned_packages", [])
    if unsigned:
        score -= min(30, 3 * len(unsigned))
        reasons.append(f"{len(unsigned)} unsigned packages")

    # Path shadowing
    shadows = data.get("path_shadowing", [])
    if shadows:
        score -= min(15, 1 * len(shadows))
        reasons.append(f"{len(shadows)} shadowed binaries in PATH")

    # Manual areas
    mans = data.get("manual_areas", {})
    for area, payload in mans.items():
        ww = payload.get("stats", {}).get("world_writable", 0)
        elf = payload.get("stats", {}).get("elf_binaries", 0)
        if ww:
            score -= min(10, ww)
            reasons.append(f"{area} contains {ww} world-writable files")
        if elf > 50:
            score -= 5
            reasons.append(f"{area} contains unusually many ELF binaries ({elf})")

    score = max(0, score)
    return {"score": score, "reasons": reasons}
