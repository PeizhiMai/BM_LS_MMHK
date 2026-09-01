#!/usr/bin/python3.11
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_pair import validate_pair


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gp", type=Path, required=True)
    p.add_argument("--gh", type=Path, required=True)
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--U", type=float, required=True)
    p.add_argument("--V", type=float, required=True)
    p.add_argument("--tp", type=float, required=True)
    args = p.parse_args()
    result = validate_pair(args.gp, args.gh, args.U, args.V, args.tp)
    if not result["valid"]:
        raise SystemExit("Refusing to install invalid pair: " + "; ".join(result["reasons"]))
    args.dest.mkdir(parents=True, exist_ok=True)
    token = str(os.getpid())
    staged = []
    try:
        for src in (args.gp, args.gh):
            tmp = args.dest / (src.name + f".install.{token}.tmp")
            shutil.copy2(src, tmp)
            staged.append(tmp)
        staged_result = validate_pair(staged[0], staged[1], args.U, args.V, args.tp)
        if not staged_result["valid"]:
            raise RuntimeError("Staged pair failed validation")
        os.replace(staged[0], args.dest / args.gp.name)
        os.replace(staged[1], args.dest / args.gh.name)
    finally:
        for path in staged:
            if path.exists():
                path.unlink()
    final = validate_pair(args.dest / args.gp.name, args.dest / args.gh.name,
                          args.U, args.V, args.tp)
    if not final["valid"]:
        raise SystemExit("Installed pair failed final validation")


if __name__ == "__main__":
    main()
