# dtrust/renderers/markdown.py
def render_tier2(md, data):
    md.h1("Tier 2 Report")
    hdr = f"**Schema** {data.get('schema_version')}  •  **Target** `{data.get('target_rootfs')}`  •  **When** {data.get('timestamp_utc')}"
    md.p(hdr)

    # Repos
    md.h2("Repository Configuration")
    if data.get("repos"):
        md.table(
            headers=["manager","name","enabled","gpgcheck","baseurl/mirrorlist","file"],
            rows=[[
                r.get("manager"), r.get("name"),
                "yes" if r.get("enabled") else "no",
                "yes" if r.get("gpgcheck") else "no",
                (r.get("baseurl") or r.get("mirrorlist") or ""),
                r.get("file") or ""
            ] for r in data["repos"]]
        )
    else:
        md.p("_No repositories found._")

    # Unsigned packages
    md.h2("Unsigned / Unverified Packages")
    ups = data.get("unsigned_packages") or []
    if ups:
        md.table(
            headers=["name","version","manager","reason"],
            rows=[[u.get("name"), u.get("version"), u.get("manager"), u.get("reason")] for u in ups]
        )
    else:
        md.p("_None detected._")

    # Path shadowing
    md.h2("PATH Shadowing")
    sh = data.get("path_shadowing") or []
    if sh:
        md.table(
            headers=["basename","first_hit","shadowed_count"],
            rows=[[x["basename"], x["first_hit"], len(x["shadowed"])] for x in sh]
        )
        md.p("> Tip: binaries earlier in PATH take precedence; review unexpected first_hits.")
    else:
        md.p("_No shadowed binaries detected._")

    # Manual areas
    md.h2("Manual Areas (/usr/local, /opt)")
    mans = data.get("manual_areas") or {}
    for area, payload in mans.items():
        md.h3(area)
        st = payload.get("stats", {})
        md.p(f"**files** {st.get('files',0)} • **dirs** {st.get('dirs',0)} • **world-writable** {st.get('world_writable',0)} • **ELF** {st.get('elf_binaries',0)}")
        ents = payload.get("entries", [])[:100]  # show first 100 for brevity
        if ents:
            md.table(
                headers=["path","mode","owner","size","ELF","world-writable","mtime"],
                rows=[[e["path"], e["mode"], e["owner"], e["size"], "yes" if e["elf"] else "no", "yes" if e["w_world"] else "no", e["mtime_utc"]] for e in ents]
            )
        else:
            md.p("_Empty._")
