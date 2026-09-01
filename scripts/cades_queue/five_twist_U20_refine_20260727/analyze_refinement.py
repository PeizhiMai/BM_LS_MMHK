#!/usr/bin/env python3
import csv
import re
import sys
from pathlib import Path

BATCH = Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/five_twist_U20_refine_20260727")
OUT = BATCH / "analysis"
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
phases = {row["phase"] for row in parsed}
if len(parsed) != 5 or len(phases) != 1:
    print("Five twists do not give a unanimous midpoint phase: {}".format(phases), file=sys.stderr)
    sys.exit(3)
midpoint_phase = next(iter(phases))
if midpoint_phase == "Mott":
    v_mott, v_charge = 5.025, 5.030
else:
    v_mott, v_charge = 5.020, 5.025
summary = {
    "U": 20,
    "V_Mott": v_mott,
    "V_charge": v_charge,
    "V_c_midpoint": (v_mott + v_charge) / 2.0,
    "V_c_halfwidth": (v_charge - v_mott) / 2.0,
    "V_c_over_U": (v_mott + v_charge) / 40.0,
    "V_c_over_U_halfwidth": (v_charge - v_mott) / 40.0,
    "bracket_width": v_charge - v_mott,
    "midpoint_phase": midpoint_phase,
    "all_five_twists_agree": True,
    "status": "bracketed",
}
OUT.mkdir(exist_ok=True)
with (OUT / "five_twist_U20_refinement_observables.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
    writer.writeheader()
    writer.writerows(parsed)
with (OUT / "five_twist_U20_refined_bracket.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary))
    writer.writeheader()
    writer.writerow(summary)
print(summary)
