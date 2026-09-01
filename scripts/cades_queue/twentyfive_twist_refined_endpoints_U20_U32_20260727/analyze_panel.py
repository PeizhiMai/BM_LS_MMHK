#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/twentyfive_twist_refined_endpoints_U20_U32_20260727")
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

OUT.mkdir(exist_ok=True)
with (OUT / "twentyfive_twist_refined_endpoint_observables.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
    writer.writeheader()
    writer.writerows(parsed)

groups = defaultdict(list)
for row in parsed:
    groups[(row["U"], row["V"])].append(row)
summary = []
for (U, V), group in sorted(groups.items()):
    phases = sorted(set(row["phase"] for row in group))
    record = {
        "U": U,
        "V": V,
        "complete_twists": len(group),
        "observed_phases": "|".join(phases),
        "unanimous_phase": len(group) == 25 and len(phases) == 1,
    }
    for metric in ("double_occupancy", "mCDW2_pipi", "C1_NN", "nn_NN", "kinetic_per_site"):
        values = [row[metric] for row in group]
        record[metric + "_mean"] = sum(values) / len(values)
        record[metric + "_min"] = min(values)
        record[metric + "_max"] = max(values)
    summary.append(record)
with (OUT / "twentyfive_twist_refined_endpoint_validation.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

u32 = [row for row in summary if row["U"] == 32][0]
if not u32["unanimous_phase"]:
    print("U=32 midpoint is not unanimous: {}".format(u32["observed_phases"]), file=sys.stderr)
    sys.exit(3)
if u32["observed_phases"] == "Mott":
    v_mott, v_charge = 8.015, 8.020
else:
    v_mott, v_charge = 8.010, 8.015
midpoint = 0.5 * (v_mott + v_charge)
halfwidth = 0.5 * (v_charge - v_mott)
bracket = {
    "U": 32,
    "V_Mott": v_mott,
    "V_charge": v_charge,
    "V_c_midpoint": midpoint,
    "V_c_halfwidth": halfwidth,
    "V_c_over_U": midpoint / 32.0,
    "V_c_over_U_halfwidth": halfwidth / 32.0,
    "bracket_width": v_charge - v_mott,
    "midpoint_phase": u32["observed_phases"],
    "twists_at_midpoint": 25,
    "status": "bracketed",
}
with (OUT / "twentyfive_twist_U32_refined_bracket.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(bracket))
    writer.writeheader()
    writer.writerow(bracket)
print("Validated 25/25 twists for all four targets.")
print("U=32 midpoint phase={}; refined bracket [{:.3f},{:.3f}]".format(
    u32["observed_phases"], v_mott, v_charge
))
