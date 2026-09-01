#!/usr/bin/env python3
"""Emit the available cluster-convergence status for the benchmark manuscript.

The current checkout contains 4x4-MMHK benchmark tables and one 2x2-MMHK data set
(U=2), but not the requested U=4,8,12 1x1/2x2/ED data.  This script records that
status in machine-readable form so manuscript caveats are reproducible.
"""
from __future__ import annotations
import csv, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"
rows=[]
# Available 4x4 benchmark values from the generated methods table.
methods=RESULTS/"half_filling_methods.csv"
if methods.exists():
    with methods.open(newline="",encoding="utf-8") as h:
        for r in csv.DictReader(h):
            if r["method"]=="MMHK" and r["property"] in {"Ground State Energy","Double Occupancy"}:
                rows.append({"cluster":"4x4-MMHK","U":r["U"],"property":r["property"],"value":r["value"],"source":str(methods),"status":"available"})
# Available 2x2 folder status.
rows.append({"cluster":"2x2-MMHK","U":"2","property":"Ground State Energy/Double Occupancy","value":"see 2x2test/tp0U2 observable files","source":"2x2test/tp0U2","status":"available_only_for_U2_not_requested_grid"})
for U in [4,8,12]:
    for cluster in ["1x1-HK","2x2-MMHK","4x4-Hubbard-ED-PBC"]:
        rows.append({"cluster":cluster,"U":str(U),"property":"Ground State Energy/Double Occupancy","value":"","source":"","status":"not_available_in_current_checkout"})
RESULTS.mkdir(exist_ok=True)
out=RESULTS/"cluster_convergence.csv"
with out.open("w",newline="",encoding="utf-8") as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(json.dumps({"cluster_convergence":str(out)},indent=2))
