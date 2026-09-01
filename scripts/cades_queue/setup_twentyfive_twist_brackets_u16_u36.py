#!/usr/bin/env python3
"""Prepare 25-twist validation jobs at five Mott/charge brackets on CADES.

The 25-point panel is a deterministic maximin extension of the five twists
already calculated.  Distances are measured on the periodic 40-step twist
torus and minimized over x/y exchange.  Index 40 is omitted from candidate
selection because it is periodically identical to index 0.

Run this script on CADES.  It prepares, but does not submit, the missing jobs.
"""

import csv
import math
import random
import re
import subprocess
from pathlib import Path


BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
OLD = BASE / "transition_search" / "five_twist_U16_U36_20260726"
BATCH = BASE / "transition_search" / "twentyfive_twist_brackets_U16_U36_20260727"
BRACKETS = {
    16: ("4.025", "4.03"),
    24: ("6.02", "6.03"),
    28: ("7.01", "7.02"),
    32: ("8.01", "8.02"),
    36: ("9.01", "9.02"),
}
INITIAL_TWISTS = [(2, 8), (1, 14), (1, 23), (27, 30), (28, 35)]
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")


def twist_distance(a, b):
    def periodic_delta(x, y):
        delta = abs(x - y)
        return min(delta, 40 - delta)

    distances = []
    for bx, by in (b, (b[1], b[0])):
        distances.append(
            math.hypot(
                periodic_delta(a[0], bx),
                periodic_delta(a[1], by),
            )
        )
    return min(distances)


def build_twist_panel():
    candidates = [(x, y) for y in range(40) for x in range(y + 1)]
    selected = list(INITIAL_TWISTS)
    while len(selected) < 25:
        _, point = max(
            (
                min(twist_distance(candidate, chosen) for chosen in selected),
                candidate,
            )
            for candidate in candidates
            if candidate not in selected
        )
        selected.append(point)
    return sorted(selected, key=lambda point: (point[1], point[0]))


def is_complete(path):
    if not path.is_file():
        return False
    return COMPLETE_RE.search(path.read_text(errors="ignore")) is not None


def decimal_tag(value):
    return str(value).replace("-", "m").replace(".", "p")


if BATCH.exists():
    raise SystemExit("Refusing to overwrite existing batch: {}".format(BATCH))
for directory in ("templates", "submitted", "logs", "auto_repair", "analysis"):
    (BATCH / directory).mkdir(parents=True, exist_ok=True)

twists = build_twist_panel()
assert len(twists) == 25
assert set(INITIAL_TWISTS).issubset(set(twists))
assert min(
    twist_distance(a, b)
    for index, a in enumerate(twists)
    for b in twists[index + 1 :]
) >= 5.0

# Reuse the tested submission and stateful repair monitor with unique names.
for name in ("monitor_and_repair.py", "status.py", "submit_fill.sh", "submit_next.sh"):
    text = (OLD / name).read_text()
    text = text.replace("five_twist_U16_U36_20260726", BATCH.name)
    text = text.replace("job_obs5t_", "job_obs25t_")
    text = text.replace("OBS5T", "OBS25T")
    text = text.replace(
        '[[ "${ACCOUNT}" == ccsd ]] || { echo \'This batch is ccsd-only.\' >&2; exit 1; }\n'
        'CAP="${OBS25T_CCSD_USER_CAP:-150}"',
        'case "${ACCOUNT}" in\n'
        '  ccsd) CAP="${OBS25T_CCSD_USER_CAP:-150}" ;;\n'
        '  cnms) CAP="${OBS25T_CNMS_USER_CAP:-150}" ;;\n'
        '  *) echo "Unsupported account: ${ACCOUNT}" >&2; exit 1 ;;\n'
        'esac',
    )
    text = text.replace(
        '[[ "${ACCOUNT}" == ccsd ]] || exit 0\n'
        'CAP="${OBS25T_CCSD_USER_CAP:-150}"',
        'case "${ACCOUNT}" in\n'
        '  ccsd) CAP="${OBS25T_CCSD_USER_CAP:-150}" ;;\n'
        '  cnms) CAP="${OBS25T_CNMS_USER_CAP:-150}" ;;\n'
        '  *) exit 0 ;;\n'
        'esac',
    )
    (BATCH / name).write_text(text)
    (BATCH / name).chmod(0o755)

rng = random.SystemRandom()
seeds = set()
while len(seeds) < 250:
    seeds.add(rng.randint(1, 4294967295))
seed_iter = iter(seeds)

manifest_rows = []
index = 0
for U, endpoints in sorted(BRACKETS.items()):
    for endpoint_index, V in enumerate(endpoints):
        expected_phase = "Mott" if endpoint_index == 0 else "charge"
        for kx, ky in twists:
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
                template_path = BATCH / "templates" / (
                    "job_obs25t_{i:04d}_U{u}_V{v}_f{kx}x{ky}.sh".format(
                        i=index, u=U, v=decimal_tag(V), kx=kx, ky=ky
                    )
                )
                script = """#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS25T
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
if [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{result}}"; then
  echo 'OBS25T_RESULT ALREADY_COMPLETE U={u} V={v} kx={kx} ky={ky}'
  exit 0
fi
rm -f "${{result}}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 {kx} {ky} 0 0 {u} {v} 0
job_rc=$?
set -e
if (( job_rc == 0 )) && [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{result}}"; then
  echo 'OBS25T_RESULT COMPLETE U={u} V={v} kx={kx} ky={ky} seed={seed}'
else
  echo 'OBS25T_RESULT FAILED rc='"${{job_rc}}"' U={u} V={v} kx={kx} ky={ky} seed={seed}' >&2
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
                template_path.chmod(0o755)
                template = str(template_path)
            manifest_rows.append(
                {
                    "index": index,
                    "U": U,
                    "V": V,
                    "expected_phase": expected_phase,
                    "kx": kx,
                    "ky": ky,
                    "seed": seed,
                    "result": str(result),
                    "state": "complete" if complete else "template",
                    "template": template,
                }
            )

manifest_fields = [
    "index",
    "U",
    "V",
    "expected_phase",
    "kx",
    "ky",
    "seed",
    "result",
    "state",
    "template",
]
with (BATCH / "manifest.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=manifest_fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(manifest_rows)
with (BATCH / "twist_panel.tsv").open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["twist_index", "kx", "ky", "in_original_five"])
    for twist_index, (kx, ky) in enumerate(twists, 1):
        writer.writerow([twist_index, kx, ky, (kx, ky) in INITIAL_TWISTS])

analysis = r'''#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

BATCH = Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/twentyfive_twist_brackets_U16_U36_20260727")
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
            "E0": float(values["E0"]),
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
if len(parsed) != 250:
    raise SystemExit("Expected 250 parsed outputs, found {}".format(len(parsed)))

OUT.mkdir(exist_ok=True)
with (OUT / "twentyfive_twist_bracket_observables_U16_U36.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
    writer.writeheader()
    writer.writerows(parsed)

groups = defaultdict(list)
for row in parsed:
    groups[(row["U"], row["V"], row["expected_phase"])].append(row)
summary = []
metrics = ["double_occupancy", "mCDW2_pipi", "C1_NN", "nn_NN", "kinetic_per_site"]
for key in sorted(groups):
    U, V, expected = key
    group = groups[key]
    phases = sorted({row["phase"] for row in group})
    record = {
        "U": U,
        "V": V,
        "expected_phase": expected,
        "complete_twists": len(group),
        "matching_twists": sum(row["phase_matches_expected"] for row in group),
        "observed_phases": "|".join(phases),
        "unanimous_expected_phase": len(group) == 25 and all(
            row["phase_matches_expected"] for row in group
        ),
    }
    for metric in metrics:
        values = [row[metric] for row in group]
        record[metric + "_mean"] = sum(values) / len(values)
        record[metric + "_min"] = min(values)
        record[metric + "_max"] = max(values)
        record[metric + "_spread"] = max(values) - min(values)
    summary.append(record)
with (OUT / "twentyfive_twist_bracket_validation_U16_U36.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

failed = [row for row in summary if not row["unanimous_expected_phase"]]
print("Validated groups: {}/{}".format(len(summary) - len(failed), len(summary)))
for row in summary:
    print(
        "U={U} V={V:g} expected={expected_phase} matching={matching_twists}/25 "
        "D=[{double_occupancy_min:.6g},{double_occupancy_max:.6g}]".format(**row)
    )
if failed:
    sys.exit(3)
'''
(BATCH / "analyze_brackets.py").write_text(analysis)
(BATCH / "analyze_brackets.py").chmod(0o755)

complete_count = sum(row["state"] == "complete" for row in manifest_rows)
template_count = sum(row["state"] == "template" for row in manifest_rows)
(BATCH / "README.txt").write_text(
    """Twenty-five-twist validation at the five U=16--36 transition brackets.
Created: 2026-07-27
Brackets: {brackets}
Twists: {twists}
Selection: deterministic maximin extension of the original five points using
periodic 40-step torus distance minimized over x/y exchange; index 40 is
excluded as the periodic duplicate of 0. Minimum pair separation: 5 indices.
Targets: 250 total; {complete} existing COMPLETE outputs reused; {missing}
missing outputs prepared for submission.
Solver: {solver}
Physics: Nup=Ndn=8, Q=(0,0), tp=0; locate_E0 maxit=10000.
Resources: ccsd, 32 tasks, 100G, 8h; total-user ccsd cap 150.
Success: expected output contains a standalone status COMPLETE line.
""".format(
        brackets=BRACKETS,
        twists=twists,
        complete=complete_count,
        missing=template_count,
        solver=BASE / "Hubbard_sym_testobs_UV.x",
    )
)

for path in BATCH.glob("*.sh"):
    subprocess.check_call(["bash", "-n", str(path)])
for path in BATCH.glob("*.py"):
    subprocess.check_call(["python3", "-m", "py_compile", str(path)])

print(
    "Created {}: {} total, {} complete, {} templates.".format(
        BATCH, len(manifest_rows), complete_count, template_count
    )
)
