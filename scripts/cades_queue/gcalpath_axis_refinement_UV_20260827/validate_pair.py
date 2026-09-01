#!/usr/bin/python3.11
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse(path: Path) -> dict:
    out = {"path": str(path), "exists": path.is_file(), "size": 0}
    if not path.is_file():
        return out
    out["size"] = path.stat().st_size
    metadata = {}
    a = b = None
    q = None
    nrm2 = None
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        key = parts[0]
        if key in {"Lx", "Ly", "tp", "U", "V", "E0", "Gap"} and len(parts) >= 2:
            metadata[key] = float(parts[1])
        elif key == "Q" and len(parts) >= 2:
            q = parts[1]
        elif key == "nrm2" and len(parts) >= 2:
            nrm2 = float(parts[1])
        elif key == "a":
            a = [float(x) for x in parts[1:]]
        elif key == "b":
            b = [float(x) for x in parts[1:]]
    out.update({"metadata": metadata, "Q": q, "nrm2": nrm2,
                "a_count": 0 if a is None else len(a),
                "b_count": 0 if b is None else len(b)})
    out["finite"] = bool(
        a is not None and b is not None
        and all(math.isfinite(x) for x in a)
        and all(math.isfinite(x) for x in b)
        and nrm2 is not None and math.isfinite(nrm2) and nrm2 > 0.0
    )
    return out


def validate_pair(gp: Path, gh: Path, U: float, V: float, tp: float) -> dict:
    files = [parse(gp), parse(gh)]
    reasons = []
    for item in files:
        if not item.get("exists"):
            reasons.append(f"missing:{item['path']}")
            continue
        md = item.get("metadata", {})
        for key, want in (("Lx", 4.0), ("Ly", 4.0), ("U", U), ("V", V), ("tp", tp)):
            got = md.get(key)
            if got is None or not math.isclose(got, want, rel_tol=0.0, abs_tol=5e-10):
                reasons.append(f"metadata:{item['path']}:{key}:{got}!={want}")
        if item.get("Q") != "0,0":
            reasons.append(f"Q:{item['path']}:{item.get('Q')}")
        if item.get("a_count") != 999 or item.get("b_count") != 999:
            reasons.append(
                f"continued_fraction:{item['path']}:a={item.get('a_count')}:b={item.get('b_count')}"
            )
        if not item.get("finite"):
            reasons.append(f"nonfinite_or_zero_norm:{item['path']}")
    return {"valid": not reasons, "reasons": reasons, "files": files,
            "expected": {"U": U, "V": V, "tp": tp, "Q": "0,0", "a": 999, "b": 999}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gp", type=Path, required=True)
    p.add_argument("--gh", type=Path, required=True)
    p.add_argument("--U", type=float, required=True)
    p.add_argument("--V", type=float, required=True)
    p.add_argument("--tp", type=float, required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = validate_pair(args.gp, args.gh, args.U, args.V, args.tp)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
