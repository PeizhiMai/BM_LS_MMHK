#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

BATCH = Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/five_twist_refine_U24_U28_20260727")
OUT = BATCH / "analysis"
CASES = {
    24: {"lower": 6.020, "midpoint": 6.025, "upper": 6.030},
    28: {"lower": 7.010, "midpoint": 7.015, "upper": 7.020},
}
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
rows = list(csv.DictReader((BATCH / "manifest.tsv").open(), delimiter="\t"))
parsed = []
for row in rows:
    path = Path(row["result"])
    text = path.read_text(errors="ignore") if path.is_file() else ""
    if not COMPLETE_RE.search(text):
        print("Not ready: {}".format(path), file=sys.stderr)
        sys.exit(2)
    values = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values[parts[0]] = parts[1]
    D = float(values["<ni_upni_dn>"])
    parsed.append(
        {
            "U": int(row["U"]),
            "V": float(row["V"]),
            "kx": int(row["kx"]),
            "ky": int(row["ky"]),
            "E0": float(values["E0"]),
            "double_occupancy": D,
            "mCDW2_pipi": float(values["<mCDW2_pipi>"]),
            "C1_NN": float(values["<C1_NN>"]),
            "nn_NN": float(values["<nn_NN>"]),
            "kinetic_per_site": float(values["<Kinetic_per_site>"]),
            "phase": "charge" if D > 0.25 else "Mott",
            "status": "COMPLETE",
            "result": row["result"],
        }
    )
if len(parsed) != 10:
    raise SystemExit("Expected 10 outputs, found {}".format(len(parsed)))

groups = defaultdict(list)
for row in parsed:
    groups[row["U"]].append(row)
summary = []
for U in sorted(CASES):
    group = groups[U]
    phases = {row["phase"] for row in group}
    if len(group) != 5 or len(phases) != 1:
        print("U={} midpoint is not unanimous: {}".format(U, phases), file=sys.stderr)
        sys.exit(3)
    phase = next(iter(phases))
    case = CASES[U]
    if phase == "Mott":
        v_mott, v_charge = case["midpoint"], case["upper"]
    else:
        v_mott, v_charge = case["lower"], case["midpoint"]
    summary.append(
        {
            "U": U,
            "V_Mott": v_mott,
            "V_charge": v_charge,
            "V_c_midpoint": (v_mott + v_charge) / 2.0,
            "V_c_halfwidth": (v_charge - v_mott) / 2.0,
            "V_c_over_U": (v_mott + v_charge) / (2.0 * U),
            "V_c_over_U_halfwidth": (v_charge - v_mott) / (2.0 * U),
            "bracket_width": v_charge - v_mott,
            "midpoint_phase": phase,
            "all_five_twists_agree": True,
            "status": "bracketed",
        }
    )

OUT.mkdir(exist_ok=True)
with (OUT / "five_twist_U24_U28_refinement_observables.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
    writer.writeheader()
    writer.writerows(parsed)
with (OUT / "five_twist_U24_U28_refined_brackets.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)
for row in summary:
    print(row)
