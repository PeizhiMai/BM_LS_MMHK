#!/usr/bin/env python3
"""Prepare 400-twist validation of every under-covered final U>=4 bracket.

Run on CADES.  The 400-point panel is a deterministic maximin extension of
the validated 100-point panel.  Every point is an exact member of the full
integer 0 <= kx <= ky <= 40 wedge containing 861 grid points.
"""

import csv
import math
import random
import re
import subprocess
from pathlib import Path


BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
SEARCH = BASE / "transition_search"
OLD = SEARCH / "hundred_twist_final_brackets_U16_U36_20260727"
BATCH = SEARCH / "four_hundred_twist_final_brackets_U16_U36_20260728"
PANEL100 = OLD / "twist_panel.tsv"
TARGETS = [
    (16, "4.025", "Mott"),
    (16, "4.03", "charge"),
    (20, "5.025", "charge"),
    (24, "6.02", "Mott"),
    (24, "6.025", "charge"),
    (28, "7.015", "Mott"),
    (28, "7.02", "charge"),
    (32, "8.015", "Mott"),
    (32, "8.02", "charge"),
    (36, "9.01", "Mott"),
    (36, "9.02", "charge"),
]
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")


def twist_distance(a, b):
    def periodic_delta(x, y):
        delta = abs(x - y)
        return min(delta, 40 - delta)

    values = []
    for bx, by in (b, (b[1], b[0])):
        values.append(
            math.hypot(
                periodic_delta(a[0], bx),
                periodic_delta(a[1], by),
            )
        )
    return min(values)


def read_panel100():
    with PANEL100.open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    panel = [(int(row["kx"]), int(row["ky"])) for row in rows]
    assert len(panel) == 100 and len(set(panel)) == 100
    assert all(0 <= kx <= ky < 40 for kx, ky in panel)
    return panel


def build_panel400(initial):
    candidates = [(kx, ky) for ky in range(41) for kx in range(ky + 1)]
    selected = list(initial)
    remaining = [candidate for candidate in candidates if candidate not in selected]
    nearest_distance = {
        candidate: min(twist_distance(candidate, chosen) for chosen in selected)
        for candidate in remaining
    }
    while len(selected) < 400:
        _, point = max((nearest_distance[candidate], candidate) for candidate in remaining)
        selected.append(point)
        remaining.remove(point)
        del nearest_distance[point]
        for candidate in remaining:
            nearest_distance[candidate] = min(
                nearest_distance[candidate],
                twist_distance(candidate, point),
            )
    return sorted(selected, key=lambda point: (point[1], point[0]))


def is_complete(path):
    return path.is_file() and COMPLETE_RE.search(
        path.read_text(errors="ignore")
    ) is not None


def decimal_tag(value):
    return value.replace("-", "m").replace(".", "p")


if BATCH.exists():
    raise SystemExit("Refusing to overwrite existing batch: {}".format(BATCH))
for name in ("templates", "submitted", "logs", "auto_repair", "analysis"):
    (BATCH / name).mkdir(parents=True, exist_ok=True)

panel100 = read_panel100()
panel400 = build_panel400(panel100)
assert len(panel400) == 400 and len(set(panel400)) == 400
assert set(panel100).issubset(set(panel400))
assert all(0 <= kx <= ky <= 40 for kx, ky in panel400)

# Reuse the tested capped submission and repair machinery.
for name in ("monitor_and_repair.py", "submit_fill.sh", "submit_next.sh"):
    text = (OLD / name).read_text()
    text = text.replace(OLD.name, BATCH.name)
    text = text.replace("job_obs100_", "job_obs400_")
    text = text.replace("OBS100", "OBS400")
    (BATCH / name).write_text(text)
    (BATCH / name).chmod(0o700)

rng = random.SystemRandom()
seeds = set()
while len(seeds) < len(TARGETS) * len(panel400):
    seeds.add(rng.randint(1, 4294967295))
seed_iter = iter(seeds)

manifest_rows = []
index = 0
template_index = 0
# Interleave target sets so both accounts receive all U,V families.
for twist_index, (kx, ky) in enumerate(panel400, 1):
    for U, V, expected_phase in TARGETS:
        index += 1
        seed = next(seed_iter)
        result = BASE / (
            "L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_obs.dat".format(
                u=U, v=V, kx=kx, ky=ky
            )
        )
        complete = is_complete(result)
        template = ""
        if not complete:
            template_index += 1
            template_path = BATCH / "templates" / (
                "job_obs400_{i:05d}_U{u}_V{v}_f{kx}x{ky}.sh".format(
                    i=template_index,
                    u=U,
                    v=decimal_tag(V),
                    kx=kx,
                    ky=ky,
                )
            )
            script = """#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS400
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -o {batch}/logs/%x-%j.out
#SBATCH -e {batch}/logs/%x-%j.err

set -uo pipefail
cd {base}
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED={seed}
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}
refilled=0
refill() {{
  if (( refilled == 0 )); then
    refilled=1
    bash '{batch}/submit_next.sh' "${{SLURM_JOB_ACCOUNT:-ccsd}}" || true
  fi
}}
trap refill EXIT
trap 'exit 143' TERM INT
result='{result}'
if [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${{result}}"; then
  echo 'OBS400_RESULT ALREADY_COMPLETE U={u} V={v} kx={kx} ky={ky}'
  exit 0
fi
rm -f "${{result}}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 {kx} {ky} 0 0 {u} {v} 0
job_rc=$?
set -e
if (( job_rc == 0 )) && [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${{result}}"; then
  echo 'OBS400_RESULT COMPLETE U={u} V={v} kx={kx} ky={ky} seed={seed}'
else
  echo 'OBS400_RESULT FAILED rc='"${{job_rc}}"' U={u} V={v} kx={kx} ky={ky} seed={seed}' >&2
  (( job_rc == 0 )) && job_rc=90
fi
exit "${{job_rc}}"
""".format(
                batch=BATCH,
                base=BASE,
                seed=seed,
                result=result,
                u=U,
                v=V,
                kx=kx,
                ky=ky,
            )
            template_path.write_text(script)
            template_path.chmod(0o700)
            subprocess.check_call(["bash", "-n", str(template_path)])
            template = str(template_path)
        manifest_rows.append(
            {
                "index": index,
                "U": U,
                "V": V,
                "expected_phase": expected_phase,
                "twist_index": twist_index,
                "kx": kx,
                "ky": ky,
                "in_861_wedge": True,
                "seed": seed,
                "result": str(result),
                "state": "complete" if complete else "template",
                "template": template,
            }
        )

fields = list(manifest_rows[0])
with (BATCH / "manifest.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(manifest_rows)
with (BATCH / "twist_panel.tsv").open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["twist_index", "kx", "ky", "in_original_100", "in_861_wedge"])
    for twist_index, (kx, ky) in enumerate(panel400, 1):
        writer.writerow(
            [twist_index, kx, ky, (kx, ky) in set(panel100), True]
        )

status = r'''#!/usr/bin/env python3
import csv
import re
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/four_hundred_twist_final_brackets_U16_U36_20260728")
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
rows = list(csv.DictReader((BATCH / "manifest.tsv").open(), delimiter="\t"))
counts = defaultdict(lambda: [0, 0])
for row in rows:
    path = Path(row["result"])
    complete = path.is_file() and COMPLETE_RE.search(path.read_text(errors="ignore"))
    counts[(int(row["U"]), float(row["V"]))][1] += 1
    if complete:
        counts[(int(row["U"]), float(row["V"]))][0] += 1
for (U, V), (complete, total) in sorted(counts.items()):
    print("U={} V={:g} COMPLETE={}/{}".format(U, V, complete, total))
'''
(BATCH / "status.py").write_text(status)
(BATCH / "status.py").chmod(0o700)

analysis = r'''#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/four_hundred_twist_final_brackets_U16_U36_20260728")
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
if len(parsed) != 4400:
    raise SystemExit("Expected 4400 outputs, found {}".format(len(parsed)))

OUT.mkdir(exist_ok=True)
with (OUT / "four_hundred_twist_final_bracket_observables.csv").open("w", newline="") as handle:
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
        "unanimous_expected_phase": len(group) == 400 and all(
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
with (OUT / "four_hundred_twist_final_bracket_validation.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

failed = [row for row in summary if not row["unanimous_expected_phase"]]
print("Validated groups: {}/{}".format(len(summary) - len(failed), len(summary)))
for row in summary:
    print(
        "U={U} V={V:g} expected={expected_phase} matching={matching_twists}/400 "
        "D=[{double_occupancy_min:.6g},{double_occupancy_max:.6g}]".format(**row)
    )
if failed:
    sys.exit(3)
'''
(BATCH / "analyze_brackets.py").write_text(analysis)
(BATCH / "analyze_brackets.py").chmod(0o700)

for path in BATCH.glob("*.sh"):
    subprocess.check_call(["bash", "-n", str(path)])
for path in BATCH.glob("*.py"):
    subprocess.check_call(["python3", "-m", "py_compile", str(path)])

complete_count = sum(row["state"] == "complete" for row in manifest_rows)
template_count = sum(row["state"] == "template" for row in manifest_rows)
(BATCH / "README.txt").write_text(
    """Four-hundred-twist validation of every under-covered final U>=4 bracket.
Targets: {targets}
Panel: deterministic maximin extension of the validated 100-point panel.
All 400 points satisfy 0 <= kx <= ky <= 40 and belong to the 861-point wedge.
Targets: {total}; existing COMPLETE outputs reused: {complete}; missing jobs: {missing}.
Resources: ccsd/cnms, 32 tasks, 100G, 8h; total-user cap 150 per account.
Solver: {solver}; locate_E0 maxit=10000.
""".format(
        targets=TARGETS,
        total=len(manifest_rows),
        complete=complete_count,
        missing=template_count,
        solver=BASE / "Hubbard_sym_testobs_UV.x",
    )
)
print(
    "Created {}: {} targets, {} complete, {} templates.".format(
        BATCH, len(manifest_rows), complete_count, template_count
    )
)
