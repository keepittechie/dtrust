#!/usr/bin/env python3
"""
Tier-aware minimal schema validator for dtrust.
- Reads report JSON
- Selects schema by `tier`
- Performs basic structural validation (not full JSON Schema)
"""
import json, sys, re
from pathlib import Path

def type_matches(val, spec):
    types = spec if isinstance(spec, list) else [spec]
    for t in types:
        if t == "string" and isinstance(val, str): return True
        if t == "integer" and isinstance(val, int): return True
        if t == "boolean" and isinstance(val, bool): return True
        if t == "null" and val is None: return True
        if t == "object" and isinstance(val, dict): return True
        if t == "array" and isinstance(val, list): return True
    return False

def validate_object(obj, schema, path="$"):
    errors = []
    for key in schema.get("required", []):
        if key not in obj:
            errors.append(f"{path}: missing required key '{key}'")
    props = schema.get("properties", {})
    for key, subschema in props.items():
        if key not in obj: continue
        val = obj[key]
        typ = subschema.get("type")
        if typ and not type_matches(val, typ):
            errors.append(f"{path}.{key}: expected type {typ}, got {type(val).__name__}")
            continue
        if isinstance(val, dict) and (typ in (None, "object", ["object"])):
            errors += validate_object(val, subschema, f"{path}.{key}")
        if isinstance(val, list) and "items" in subschema:
            item_schema = subschema["items"]
            for i, item in enumerate(val):
                if isinstance(item, dict):
                    errors += validate_object(item, item_schema, f"{path}.{key}[{i}]")
                else:
                    it = item_schema.get("type")
                    if it and not type_matches(item, it):
                        errors.append(f"{path}.{key}[{i}]: expected type {it}, got {type(item).__name__}")
        if "const" in subschema and obj.get(key) != subschema["const"]:
            errors.append(f"{path}.{key}: expected const {subschema['const']}, got {obj.get(key)}")
        if "pattern" in subschema and isinstance(val, str):
            if not re.match(subschema["pattern"], val):
                errors.append(f"{path}.{key}: string does not match pattern {subschema['pattern']}")
    return errors

def main():
    if len(sys.argv) != 2:
        print("Usage: scripts/validate.py <report.json>")
        sys.exit(2)
    report_path = Path(sys.argv[1])
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading report: {e}", file=sys.stderr)
        sys.exit(2)
    root = Path(__file__).resolve().parents[1]
    tier = report.get("tier") if isinstance(report, dict) else None
    if tier == 2:
        schema_path = root / "templates" / "report.tier2.schema.json"
    else:
        schema_path = root / "templates" / "report.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading schema: {e}", file=sys.stderr)
        sys.exit(2)
    errs = validate_object(report, schema, "$")
    if errs:
        print("VALIDATION FAILED:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print("OK: report matches minimal schema.")
    sys.exit(0)

if __name__ == "__main__":
    main()
