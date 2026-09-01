#!/usr/bin/env python3
"""Create the CADES five-twist midpoint refinement for U=20.

Run this script on CADES.  It prepares, but does not submit, five jobs at
V=5.025.  The established unanimous full-grid endpoints are V=5.020 (Mott)
and V=5.030 (charge), so the midpoint classification halves the bracket.
"""

import csv
import random
import shutil
import subprocess
from pathlib import Path


BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
OLD = BASE / "transition_search" / "five_twist_U16_U36_20260726"
BATCH = BASE / "transition_search" / "five_twist_U20_refine_20260727"
U = 20
V = "5.025"
TWISTS = [(2, 8), (1, 14), (1, 23), (27, 30), (28, 35)]


def decimal_tag(value):
    return str(value).replace("-", "m").replace(".", "p")


if BATCH.exists():
    raise SystemExit("Refusing to overwrite existing batch: {}".format(BATCH))
for directory in ("templates", "submitted", "logs", "auto_repair", "analysis"):
    (BATCH / directory).mkdir(parents=True, exist_ok=True)

# Reuse the already-tested stateful monitor/submission implementation while
# giving this batch unique paths, job names, and template patterns.
for name in ("monitor_and_repair.py", "status.py", "submit_fill.sh", "submit_next.sh"):
    text = (OLD / name).read_text()
    text = text.replace("five_twist_U16_U36_20260726", BATCH.name)
    text = text.replace("job_obs5t_", "job_obs5t20_")
    text = text.replace("OBS5T", "OBS5T20")
    (BATCH / name).write_text(text)
    (BATCH / name).chmod(0o755)

rng = random.SystemRandom()
seeds = set()
while len(seeds) < len(TWISTS):
    seeds.add(rng.randint(1, 4294967295))
seeds = list(seeds)

manifest_rows = []
for index, ((kx, ky), seed) in enumerate(zip(TWISTS, seeds), 1):
    result = BASE / (
        "L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_obs.dat".format(
            u=U, v=V, kx=kx, ky=ky
        )
    )
    template = BATCH / "templates" / (
        "job_obs5t20_{i:04d}_U{u}_V{v}_f{kx}x{ky}.sh".format(
            i=index, u=U, v=decimal_tag(V), kx=kx, ky=ky
        )
    )
    script = """#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS5T20
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
  echo 'OBS5T20_RESULT ALREADY_COMPLETE U={u} V={v} kx={kx} ky={ky}'
  exit 0
fi
rm -f "${{result}}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 {kx} {ky} 0 0 {u} {v} 0
job_rc=$?
set -e
if (( job_rc == 0 )) && [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{result}}"; then
  echo 'OBS5T20_RESULT COMPLETE U={u} V={v} kx={kx} ky={ky} seed={seed}'
else
  echo 'OBS5T20_RESULT FAILED rc='"${{job_rc}}"' U={u} V={v} kx={kx} ky={ky} seed={seed}' >&2
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
    template.write_text(script)
    template.chmod(0o755)
    manifest_rows.append(
        {
            "index": index,
            "U": U,
            "V": V,
            "kx": kx,
            "ky": ky,
            "seed": seed,
            "result": str(result),
            "state": "template",
            "template": str(template),
        }
    )

with (BATCH / "manifest.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "index",
            "U",
            "V",
            "kx",
            "ky",
            "seed",
            "result",
            "state",
            "template",
        ],
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(manifest_rows)

analysis = r'''#!/usr/bin/env python3
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
'''
(BATCH / "analyze_refinement.py").write_text(analysis)
(BATCH / "analyze_refinement.py").chmod(0o755)

(BATCH / "README.txt").write_text(
    """Five-twist midpoint refinement for the established U=20 bracket.
Created: 2026-07-27
Existing full-grid bracket: V=5.020 (Mott), V=5.030 (charge).
New midpoint: V=5.025.
Twists: {twists}
Targets: 5 unique jobs.
Solver: {solver}
Physics: Nup=Ndn=8, Q=(0,0), tp=0; locate_E0 maxit=10000.
Resources: ccsd, 32 tasks, 100G, 8h.
Success: expected output contains a standalone status COMPLETE line.
""".format(
        twists=TWISTS, solver=BASE / "Hubbard_sym_testobs_UV.x"
    )
)

for path in BATCH.glob("*.sh"):
    subprocess.check_call(["bash", "-n", str(path)])
for path in BATCH.glob("*.py"):
    subprocess.check_call(["python3", "-m", "py_compile", str(path)])

print("Created {} with {} targets.".format(BATCH, len(manifest_rows)))
