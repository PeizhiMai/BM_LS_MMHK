#!/usr/bin/env python3
"""Expand every refined endpoint with fewer than 25 twists to the 25 panel.

Run on CADES.  The selected panel is read verbatim from the validated
25-twist U=16--36 batch and is therefore a subset of the 861-point
0 <= kx <= ky <= 40 symmetry wedge.
"""

import csv
import random
import re
import subprocess
from pathlib import Path


BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
SEARCH = BASE / "transition_search"
BATCH = SEARCH / "twentyfive_twist_refined_endpoints_U20_U32_20260727"
PANEL_SOURCE = SEARCH / "twentyfive_twist_brackets_U16_U36_20260727" / "twist_panel.tsv"
TARGETS = [
    (20, "5.025", "charge"),
    (24, "6.025", "charge"),
    (28, "7.015", "Mott"),
    (32, "8.015", "midpoint"),
]
EXTERNAL_JOB = {(32, "8.015", 2, 8): "5513726"}
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")


def is_complete(path):
    return path.is_file() and COMPLETE_RE.search(
        path.read_text(errors="ignore")
    ) is not None


def job_is_active(job_id):
    output = subprocess.check_output(
        ["squeue", "-h", "-j", str(job_id), "-o", "%T"],
        universal_newlines=True,
    ).strip()
    return output in {"PENDING", "RUNNING", "COMPLETING", "CONFIGURING"}


def decimal_tag(value):
    return value.replace("-", "m").replace(".", "p")


if BATCH.exists():
    raise SystemExit("Refusing to overwrite existing batch: {}".format(BATCH))
for name in ("templates", "submitted", "logs", "analysis"):
    (BATCH / name).mkdir(parents=True, exist_ok=True)

with PANEL_SOURCE.open() as handle:
    panel_rows = list(csv.DictReader(handle, delimiter="\t"))
twists = [(int(row["kx"]), int(row["ky"])) for row in panel_rows]
assert len(twists) == 25
assert len(set(twists)) == 25
assert all(0 <= kx <= ky <= 40 for kx, ky in twists)

rng = random.SystemRandom()
seeds = set()
while len(seeds) < 100:
    seeds.add(rng.randint(1, 4294967295))
seed_iter = iter(seeds)

rows = []
template_number = 0
for U, V, expected_phase in TARGETS:
    for twist_index, (kx, ky) in enumerate(twists, 1):
        seed = next(seed_iter)
        result = BASE / (
            "L4x4Nup8Ndn8U{u}V{v}tp0f{kx}x{ky}Q0x0_obs.dat".format(
                u=U, v=V, kx=kx, ky=ky
            )
        )
        state = "complete" if is_complete(result) else "missing"
        external_job_id = ""
        key = (U, V, kx, ky)
        if state == "missing" and key in EXTERNAL_JOB:
            candidate = EXTERNAL_JOB[key]
            if job_is_active(candidate):
                state = "external_running"
                external_job_id = candidate

        template = ""
        account = ""
        if state == "missing":
            template_number += 1
            account = "ccsd" if template_number % 2 else "cnms"
            template_path = BATCH / "templates" / (
                "job_obs25r_{i:04d}_U{u}_V{v}_f{kx}x{ky}_{account}.sh".format(
                    i=template_number,
                    u=U,
                    v=decimal_tag(V),
                    kx=kx,
                    ky=ky,
                    account=account,
                )
            )
            script = """#!/bin/bash
#SBATCH -A {account}
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS25R
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
trap 'exit 143' TERM INT
result='{result}'
if [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${{result}}"; then
  echo 'OBS25R_RESULT ALREADY_COMPLETE U={u} V={v} kx={kx} ky={ky}'
  exit 0
fi
rm -f "${{result}}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 {kx} {ky} 0 0 {u} {v} 0
job_rc=$?
set -e
if (( job_rc == 0 )) && [[ -s "${{result}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${{result}}"; then
  echo 'OBS25R_RESULT COMPLETE U={u} V={v} kx={kx} ky={ky} seed={seed}'
else
  echo 'OBS25R_RESULT FAILED rc='"${{job_rc}}"' U={u} V={v} kx={kx} ky={ky} seed={seed}' >&2
  (( job_rc == 0 )) && job_rc=90
fi
exit "${{job_rc}}"
""".format(
                account=account,
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

        rows.append(
            {
                "U": U,
                "V": V,
                "expected_phase": expected_phase,
                "twist_index": twist_index,
                "kx": kx,
                "ky": ky,
                "in_861_wedge": True,
                "seed": seed,
                "result": str(result),
                "state": state,
                "external_job_id": external_job_id,
                "account": account,
                "template": template,
            }
        )

fields = list(rows[0])
with (BATCH / "manifest.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
with (BATCH / "twist_panel.tsv").open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["twist_index", "kx", "ky", "in_861_wedge"])
    for index, (kx, ky) in enumerate(twists, 1):
        writer.writerow([index, kx, ky, True])

submit = """#!/bin/bash
set -euo pipefail
BATCH='{batch}'
LOG="$BATCH/submission.tsv"
if [[ ! -s "$LOG" ]]; then
  printf 'job_id\\taccount\\tscript\\n' > "$LOG"
fi
shopt -s nullglob
for script in "$BATCH"/templates/*.sh; do
  account=$(awk '$1==\"#SBATCH\" && $2==\"-A\" {{print $3; exit}}' "$script")
  output=$(sbatch "$script")
  job_id=${{output##* }}
  printf '%s\\t%s\\t%s\\n' "$job_id" "$account" "$script" >> "$LOG"
  mv "$script" "$BATCH/submitted/"
done
""".format(batch=BATCH)
(BATCH / "submit_all.sh").write_text(submit)
(BATCH / "submit_all.sh").chmod(0o700)
subprocess.check_call(["bash", "-n", str(BATCH / "submit_all.sh")])

status = r'''#!/usr/bin/env python3
import csv
import re
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/twentyfive_twist_refined_endpoints_U20_U32_20260727")
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
rows = list(csv.DictReader((BATCH / "manifest.tsv").open(), delimiter="\t"))
counts = defaultdict(lambda: [0, 0])
for row in rows:
    path = Path(row["result"])
    complete = path.is_file() and COMPLETE_RE.search(path.read_text(errors="ignore"))
    counts[(row["U"], row["V"])][1] += 1
    if complete:
        counts[(row["U"], row["V"])][0] += 1
for key in sorted(counts, key=lambda x: (int(x[0]), float(x[1]))):
    complete, total = counts[key]
    print("U={} V={} COMPLETE={}/{}".format(key[0], key[1], complete, total))
'''
(BATCH / "status.py").write_text(status)
(BATCH / "status.py").chmod(0o700)

analysis = r'''#!/usr/bin/env python3
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
'''
(BATCH / "analyze_panel.py").write_text(analysis)
(BATCH / "analyze_panel.py").chmod(0o700)
subprocess.check_call(["python3", "-m", "py_compile", str(BATCH / "status.py")])
subprocess.check_call(["python3", "-m", "py_compile", str(BATCH / "analyze_panel.py")])

state_counts = {}
account_counts = {}
for row in rows:
    state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
    if row["account"]:
        account_counts[row["account"]] = account_counts.get(row["account"], 0) + 1
(BATCH / "README.txt").write_text(
    """Expand refined transition endpoints to the validated 25-twist panel.
Targets: {targets}
Panel source: {panel}
All panel points satisfy 0 <= kx <= ky <= 40 and belong to the 861-point wedge.
State counts at setup: {states}
New-job account split: {accounts}
Resources: 32 tasks, 100G, 8h; solver locate_E0 maxit=10000.
Existing COMPLETE outputs are reused and never resubmitted.
""".format(
        targets=TARGETS,
        panel=PANEL_SOURCE,
        states=state_counts,
        accounts=account_counts,
    )
)

print("Created {}".format(BATCH))
print("State counts: {}".format(state_counts))
print("New-job account split: {}".format(account_counts))
