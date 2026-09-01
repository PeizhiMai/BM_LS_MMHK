#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/hundred_twist_final_brackets_U16_U36_20260727")
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
    phase = "charge" if D > 0.25 else "Mott"
    parsed.append(
        {
            "U": int(row["U"]),
            "V": float(row["V"]),
            "expected_phase": row["expected_phase"],
            "kx": int(row["kx"]),
            "ky": int(row["ky"]),
            "double_occupancy": D,
            "mCDW2_pipi": float(values["<mCDW2_pipi>"]),
            "C1_NN": float(values["<C1_NN>"]),
            "nn_NN": float(values["<nn_NN>"]),
            "kinetic_per_site": float(values["<Kinetic_per_site>"]),
            "phase": phase,
            "phase_matches_expected": phase == row["expected_phase"],
            "status": "COMPLETE",
            "result": row["result"],
        }
    )
if len(parsed) != 1100:
    raise SystemExit("Expected 1100 outputs, found {}".format(len(parsed)))

OUT.mkdir(exist_ok=True)
with (OUT / "hundred_twist_final_bracket_observables.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
    writer.writeheader()
    writer.writerows(parsed)

groups = defaultdict(list)
for row in parsed:
    groups[(row["U"], row["V"], row["expected_phase"])].append(row)
summary = []
for (U, V, expected), group in sorted(groups.items()):
    phases = sorted(set(row["phase"] for row in group))
    record = {
        "U": U,
        "V": V,
        "expected_phase": expected,
        "complete_twists": len(group),
        "matching_twists": sum(row["phase_matches_expected"] for row in group),
        "observed_phases": "|".join(phases),
        "unanimous_expected_phase": len(group) == 100 and all(
            row["phase_matches_expected"] for row in group
        ),
    }
    for metric in ("double_occupancy", "mCDW2_pipi", "C1_NN", "nn_NN", "kinetic_per_site"):
        values = [row[metric] for row in group]
        record[metric + "_mean"] = sum(values) / len(values)
        record[metric + "_min"] = min(values)
        record[metric + "_max"] = max(values)
        record[metric + "_spread"] = max(values) - min(values)
    summary.append(record)
with (OUT / "hundred_twist_final_bracket_validation.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

failed = [row for row in summary if not row["unanimous_expected_phase"]]
print("Validated groups: {}/{}".format(len(summary) - len(failed), len(summary)))
for row in summary:
    print(
        "U={U} V={V:g} expected={expected_phase} matching={matching_twists}/100 "
        "D=[{double_occupancy_min:.6g},{double_occupancy_max:.6g}]".format(**row)
    )
if failed:
    sys.exit(3)
