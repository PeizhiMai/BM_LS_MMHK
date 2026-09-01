#!/usr/bin/env python3
"""Create the CADES batch for the requested finite-tprime U/V grid.

This setup is intentionally self-contained and refuses to overwrite an
existing batch.  It generates eleven 120-momentum parameter sets, validated
raw-pair installation, account-capped self-refill scripts, and a two-copy seeded repair monitor (overwritten with the audited final monitor before submission).
"""

from __future__ import annotations

import csv
import json
import os
import random
import shutil
import subprocess
from pathlib import Path


SOURCE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath")
BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827")
PARAMETERS = [
    (9.0, 0.0, 0.0, "mott_U9_tp0"),
    (10.0, 0.0, 0.0, "mott_U10_tp0"),
    (11.0, 0.0, 0.0, "mott_U11_tp0"),
    (14.0, 0.0, 0.0, "mott_U14_tp0"),
    (16.0, 0.0, 0.0, "mott_U16_tp0"),
    (27.0, 0.0, 0.0, "mott_U27_tp0"),
    (0.0, 2.25, 0.0, "charge_V2p25_tp0"),
    (0.0, 2.5, 0.0, "charge_V2p5_tp0"),
    (0.0, 2.75, 0.0, "charge_V2p75_tp0"),
    (0.0, 3.25, 0.0, "charge_V3p25_tp0"),
    (0.0, 6.25, 0.0, "charge_V6p25_tp0"),
]


def label(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def slug(value: float) -> str:
    return label(value).replace("-", "m").replace(".", "p")


def raw_name(U: float, V: float, tp: float, kx: int, ky: int, kind: str) -> str:
    return (
        f"L4x4Nup8Ndn8U{label(U)}V{label(V)}tp{label(tp)}"
        f"f{kx}x{ky}Q0x0_{kind}.dat"
    )


def path120() -> list[tuple[int, int]]:
    # Strict Gamma-X-M-Gamma order with no repeated terminal Gamma.
    path = (
        [(kx, 0) for kx in range(41)]
        + [(40, ky) for ky in range(1, 41)]
        + [(k, k) for k in range(39, 0, -1)]
    )
    assert len(path) == 120 and len(set(path)) == 120
    assert path[0] == (0, 0) and path[40] == (40, 0)
    assert path[80] == (40, 40) and path[-1] == (1, 1)
    return path


VALIDATOR = r'''#!/sw/cades-open/python/3.10.14/bin/python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse(path: Path) -> dict:
    out = {"path": str(path), "exists": path.is_file(), "size": 0}
    if not path.is_file():
        return out
    out["size"] = path.stat().st_size
    metadata = {}
    a = b = None
    q = None
    nrm2 = None
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        key = parts[0]
        if key in {"Lx", "Ly", "tp", "U", "V", "E0", "Gap"} and len(parts) >= 2:
            metadata[key] = float(parts[1])
        elif key == "Q" and len(parts) >= 2:
            q = parts[1]
        elif key == "nrm2" and len(parts) >= 2:
            nrm2 = float(parts[1])
        elif key == "a":
            a = [float(x) for x in parts[1:]]
        elif key == "b":
            b = [float(x) for x in parts[1:]]
    out.update({"metadata": metadata, "Q": q, "nrm2": nrm2,
                "a_count": 0 if a is None else len(a),
                "b_count": 0 if b is None else len(b)})
    out["finite"] = bool(
        a is not None and b is not None
        and all(math.isfinite(x) for x in a)
        and all(math.isfinite(x) for x in b)
        and nrm2 is not None and math.isfinite(nrm2) and nrm2 > 0.0
    )
    return out


def validate_pair(gp: Path, gh: Path, U: float, V: float, tp: float) -> dict:
    files = [parse(gp), parse(gh)]
    reasons = []
    for item in files:
        if not item.get("exists"):
            reasons.append(f"missing:{item['path']}")
            continue
        md = item.get("metadata", {})
        for key, want in (("Lx", 4.0), ("Ly", 4.0), ("U", U), ("V", V), ("tp", tp)):
            got = md.get(key)
            if got is None or not math.isclose(got, want, rel_tol=0.0, abs_tol=5e-10):
                reasons.append(f"metadata:{item['path']}:{key}:{got}!={want}")
        if item.get("Q") != "0,0":
            reasons.append(f"Q:{item['path']}:{item.get('Q')}")
        if item.get("a_count") != 999 or item.get("b_count") != 999:
            reasons.append(
                f"continued_fraction:{item['path']}:a={item.get('a_count')}:b={item.get('b_count')}"
            )
        if not item.get("finite"):
            reasons.append(f"nonfinite_or_zero_norm:{item['path']}")
    return {"valid": not reasons, "reasons": reasons, "files": files,
            "expected": {"U": U, "V": V, "tp": tp, "Q": "0,0", "a": 999, "b": 999}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gp", type=Path, required=True)
    p.add_argument("--gh", type=Path, required=True)
    p.add_argument("--U", type=float, required=True)
    p.add_argument("--V", type=float, required=True)
    p.add_argument("--tp", type=float, required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = validate_pair(args.gp, args.gh, args.U, args.V, args.tp)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
'''


INSTALLER = r'''#!/sw/cades-open/python/3.10.14/bin/python3
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
'''


SUBMIT_COMMON = r'''#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
REPAIR_TEMPLATE_DIR="${SCRIPT_DIR}/repair_templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
REPAIR_SUBMITTED_DIR="${SCRIPT_DIR}/repair_submitted"
LOG_DIR="${SCRIPT_DIR}/logs"
LEDGER="${SCRIPT_DIR}/submission_ledger.tsv"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"
CCSD_CAP=${GAXR_CCSD_CAP:-990}
CNMS_CAP=${GAXR_CNMS_CAP:-330}
mkdir -p "${TEMPLATE_DIR}" "${REPAIR_TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${REPAIR_SUBMITTED_DIR}" "${LOG_DIR}"

count_jobs() {
  local account="$1" self="${SLURM_JOB_ID:-}"
  squeue -h -u "${USER}" -o '%i|%j|%a|%Z' \
    | awk -F'|' -v account="${account}" -v target="${SCRIPT_DIR}" -v self="${self}" \
      '$1 != self && ($2 == "GAXR" || $2 == "GAXRR") && $3 == account && $4 == target {n++} END {print n+0}'
}

next_template() {
  local account="$1" item
  item="$(find "${REPAIR_TEMPLATE_DIR}" -maxdepth 1 -type f -name "repair_*_A${account}.sh" | LC_ALL=C sort | head -n1 || true)"
  if [[ -n "${item}" ]]; then printf 'repair|%s\n' "${item}"; return 0; fi
  item="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_gaxr_*.sh' | LC_ALL=C sort | head -n1 || true)"
  [[ -n "${item}" ]] && printf 'normal|%s\n' "${item}"
}

submit_one() {
  local template="$1" account="$2" kind="$3" base run out job_id task_index destination
  base="$(basename "${template}")"
  if [[ "${kind}" == repair ]]; then
    destination="${REPAIR_SUBMITTED_DIR}"
  else
    destination="${SUBMITTED_DIR}"
  fi
  run="${destination}/${base%.sh}_${account}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${account}/" "${template}" > "${run}"
  chmod +x "${run}"
  out="$(cd "${SCRIPT_DIR}" && sbatch "${run}" 2>&1)" || { rm -f "${run}"; return 1; }
  job_id="$(awk '/Submitted batch job/{print $4}' <<<"${out}")"
  [[ "${job_id}" =~ ^[0-9]+$ ]] || { rm -f "${run}"; return 1; }
  task_index="$(grep -E '^export GAXR_TASK_INDEX=' "${run}" | head -n1 | cut -d= -f2)"
  mv "${template}" "${destination}/${base%.sh}.template"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "${job_id}" "${account}" "${task_index}" "${kind}" "${run}" >> "${LEDGER}"
  echo "${out}"
}
'''


MONITOR = r'''#!/sw/cades-open/python/3.10.14/bin/python3
from __future__ import annotations

import csv
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827")
MANIFEST = BATCH / "manifest.tsv"
LEDGER = BATCH / "submission_ledger.tsv"
STATE_FILE = BATCH / "repair_state.json"
REPORT = BATCH / "latest_report.json"
LOCK = BATCH / ".monitor.lock"
FAILURE = {"FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED", "BOOT_FAIL", "DEADLINE", "CANCELLED", "REVOKED"}
ACTIVE = {"PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED"}
sys.path.insert(0, str(BATCH))
from validate_pair import validate_pair


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def normalize(value):
    return value.strip().split("+", 1)[0].split()[0] if value.strip() else ""


def valid(row):
    return validate_pair(Path(row["gp"]), Path(row["gh"]), float(row["U"]), float(row["V"]), float(row["tp"]))["valid"]


def load_state():
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text())
    return {"version": 2, "used_repair_seeds": [], "targets": {}, "events": []}


def save_json(path, value):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def queue():
    p = run(["squeue", "-u", os.environ["USER"], "-h", "-o", "%i|%j|%a|%T|%Z"])
    out = {}
    for line in p.stdout.splitlines():
        cols = [x.strip() for x in line.split("|")]
        if len(cols) == 5 and cols[4] == str(BATCH) and cols[1] in {"GAXR", "GAXRR"}:
            out[cols[0]] = {"name": cols[1], "account": cols[2], "state": cols[3]}
    return out


def accounting(name):
    p = run(["sacct", "-S", "2026-07-31", "-n", "-X", "--name", name,
             "-o", "JobIDRaw,Account,State%30,ExitCode", "-P"])
    out = {}
    for line in p.stdout.splitlines():
        cols = line.split("|")
        if len(cols) >= 4 and cols[0].strip().isdigit():
            out[cols[0].strip()] = {"account": cols[1].strip(), "state": normalize(cols[2]), "exit": cols[3].strip()}
    return out


def ledger():
    out = defaultdict(list)
    if not LEDGER.is_file():
        return out
    with LEDGER.open() as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out[int(row["task_index"])].append(row)
    return out


def make_repair(row, account, generation, seed):
    idx = int(row["index"])
    work = BATCH / "repairs" / f"task_{idx:04d}" / f"gen_{generation:04d}"
    work.mkdir(parents=True, exist_ok=True)
    template = BATCH / "repair_templates" / f"repair_{idx:04d}_g{generation:04d}_A{account}.sh"
    text = (BATCH / "job_template_body.sh").read_text()
    values = {
        "__JOB_NAME__": "GAXRR", "__TASK_INDEX__": str(idx), "__WORK__": str(work),
        "__U__": row["U"], "__V__": row["V"], "__TP__": row["tp"],
        "__KX__": row["kx"], "__KY__": row["ky"], "__SEED__": str(seed),
        "__GP__": Path(row["gp"]).name, "__GH__": Path(row["gh"]).name,
    }
    for key, value in values.items():
        text = text.replace(key, value)
    template.write_text(text)
    template.chmod(0o700)
    subprocess.check_call(["bash", "-n", str(template)])
    return template


lock_handle = LOCK.open("w")
try:
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print("Another GAXR monitor is active; no action taken.")
    raise SystemExit(0)

rows = list(csv.DictReader(MANIFEST.open(), delimiter="\t"))
rows_by_index = {int(row["index"]): row for row in rows}
state = load_state()
used = {int(row["seed"]) for row in rows} | {int(x) for x in state.get("used_repair_seeds", [])}
q = queue()
sacct = {**accounting("GAXR"), **accounting("GAXRR")}
jobs = ledger()
prepared = []

for idx, row in rows_by_index.items():
    if valid(row):
        continue
    entries = jobs.get(idx, [])
    active_entries = [entry for entry in entries if entry["job_id"] in q]
    if active_entries:
        continue
    repair_templates = list((BATCH / "repair_templates").glob(f"repair_{idx:04d}_*.sh"))
    if repair_templates:
        continue
    ordinary_template = BATCH / "templates" / f"job_gaxr_{idx:04d}.sh"
    if ordinary_template.exists() and not entries:
        continue
    if not entries:
        # A missing template with no ledger is unexpected but repairable.
        account = "ccsd"
    else:
        last = entries[-1]
        terminal = sacct.get(last["job_id"])
        if terminal is None or terminal["state"] in ACTIVE:
            continue
        account = last["account"]
    target = state["targets"].setdefault(str(idx), {"generations": [], "row": row})
    generation = len(target["generations"]) + 1
    while True:
        seed = random.SystemRandom().randint(1, 4294967295)
        if seed not in used:
            break
    used.add(seed)
    template = make_repair(row, account, generation, seed)
    record = {"generation": generation, "seed": seed, "account": account,
              "template": str(template), "prepared_at": time.strftime("%F %T")}
    target["generations"].append(record)
    prepared.append({"task_index": idx, **record})

state["used_repair_seeds"] = sorted(used - {int(row["seed"]) for row in rows})
if prepared:
    state["events"].append({"time": time.strftime("%F %T"), "action": "prepare_repairs", "items": prepared})
save_json(STATE_FILE, state)

if not (BATCH / ".priority_pause").exists():
    env = os.environ.copy()
    env["GAXR_CONFIRM_SUBMIT"] = "YES"
    subprocess.run(["bash", str(BATCH / "submit_fill.sh"), "all"], env=env, check=False)

q = queue()
jobs = ledger()
case = defaultdict(lambda: {"total": 0, "complete": 0, "running": 0, "pending": 0, "waiting": 0, "repair_waiting": 0})
for idx, row in rows_by_index.items():
    key = (row["U"], row["V"], row["tp"], row["set_name"])
    stat = case[key]
    stat["total"] += 1
    if valid(row):
        stat["complete"] += 1
        continue
    entries = jobs.get(idx, [])
    active_entries = [entry for entry in entries if entry["job_id"] in q]
    if active_entries:
        states = [q[entry["job_id"]]["state"] for entry in active_entries]
        if any(value == "RUNNING" for value in states):
            stat["running"] += 1
        else:
            stat["pending"] += 1
    elif (BATCH / "templates" / f"job_gaxr_{idx:04d}.sh").exists():
        stat["waiting"] += 1
    elif list((BATCH / "repair_templates").glob(f"repair_{idx:04d}_*.sh")):
        stat["repair_waiting"] += 1

cases = []
for (U, V, tp, set_name), stat in sorted(case.items(), key=lambda item: item[0][3]):
    cases.append({"U": U, "V": V, "tp": tp, "set_name": set_name, **stat})
report = {
    "time": time.strftime("%F %T"), "total": len(rows),
    "complete": sum(item["complete"] for item in cases),
    "cases": cases, "repairs_prepared": prepared,
    "queue": {
        account: {
            state_name: sum(1 for item in q.values() if item["account"] == account and item["state"] == state_name)
            for state_name in ("RUNNING", "PENDING")
        }
        for account in ("ccsd", "cnms")
    },
}
save_json(REPORT, report)
print(f"GAXR progress at {report['time']}")
print(f"COMPLETE {report['complete']}/{report['total']} ({100.0*report['complete']/report['total']:.2f}%)")
for item in cases:
    print("U={U} V={V} tp={tp}: {complete}/{total} | R={running} PD={pending} waiting={waiting} repair_waiting={repair_waiting}".format(**item))
print("QUEUE ccsd R={RUNNING} PD={PENDING}".format(**report["queue"]["ccsd"]))
print("QUEUE cnms R={RUNNING} PD={PENDING}".format(**report["queue"]["cnms"]))
print(f"REPAIRS_PREPARED {len(prepared)}")
if report["complete"] == report["total"] and not q and not prepared:
    print("ALL_COMPLETE")
'''


def job_body() -> str:
    return r'''#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J __JOB_NAME__
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -D /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827
#SBATCH -o /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827/logs/%x-%j.out
#SBATCH -e /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827/logs/%x-%j.err

set -uo pipefail
BATCH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827
RAW="${BATCH}/raw"
export GAXR_TASK_INDEX=__TASK_INDEX__
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED=__SEED__
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}
refilled=0
refill() {
  if (( refilled == 0 )); then
    refilled=1
    bash "${BATCH}/submit_next.sh" "${SLURM_JOB_ACCOUNT:-ccsd}" || true
  fi
}
trap refill EXIT
trap 'exit 143' TERM INT

gp="${RAW}/__GP__"
gh="${RAW}/__GH__"
if /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/validate_pair.py" --gp "${gp}" --gh "${gh}" --U __U__ --V __V__ --tp __TP__; then
  echo "GAXR_RESULT ALREADY_VALID task=${GAXR_TASK_INDEX}"
  exit 0
fi

work='__WORK__'
rm -rf "${work}"
mkdir -p "${work}"
cd "${work}"
set +e
time "${BATCH}/Square_Hubbard_tbc_G_calculation_UV.x" 8 8 __KX__ __KY__ 0 0 __U__ __V__ __TP__
rc=$?
set -e
if (( rc == 0 )); then
  /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/install_pair.py" --gp "${work}/__GP__" --gh "${work}/__GH__" \
    --dest "${RAW}" --U __U__ --V __V__ --tp __TP__ || rc=$?
fi
if (( rc == 0 )) && /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/validate_pair.py" --gp "${gp}" --gh "${gh}" --U __U__ --V __V__ --tp __TP__; then
  echo "GAXR_RESULT COMPLETE task=${GAXR_TASK_INDEX} U=__U__ V=__V__ tp=__TP__ kx=__KX__ ky=__KY__ seed=__SEED__"
else
  echo "GAXR_RESULT FAILED rc=${rc} task=${GAXR_TASK_INDEX} U=__U__ V=__V__ tp=__TP__ kx=__KX__ ky=__KY__ seed=__SEED__" >&2
  (( rc == 0 )) && rc=90
fi
exit "${rc}"
'''


def render_job(row: dict[str, object], work: Path, seed: int, name: str = "GAXR") -> str:
    text = job_body()
    replacements = {
        "__JOB_NAME__": name,
        "__TASK_INDEX__": str(row["index"]),
        "__WORK__": str(work),
        "__U__": str(row["U"]),
        "__V__": str(row["V"]),
        "__TP__": str(row["tp"]),
        "__KX__": str(row["kx"]),
        "__KY__": str(row["ky"]),
        "__SEED__": str(seed),
        "__GP__": Path(str(row["gp"])).name,
        "__GH__": Path(str(row["gh"])).name,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def main() -> None:
    if BATCH.exists():
        raise SystemExit(f"Refusing to overwrite existing batch: {BATCH}")
    if not (SOURCE / "Square_Hubbard_tbc_G_calculation_UV.cc").is_file():
        raise SystemExit("Missing source UV Green-function solver")
    for name in (
        "raw", "templates", "submitted", "repair_templates", "repair_submitted",
        "logs", "work", "repairs", "analysis",
    ):
        (BATCH / name).mkdir(parents=True, exist_ok=True)

    shutil.copy2(SOURCE / "Square_Hubbard_tbc_G_calculation_UV.cc", BATCH)
    build = BATCH / "build.sh"
    build.write_text(
        """#!/bin/bash
set -euo pipefail
cd \"$(dirname \"$0\")\"
mkdir -p .tmp_build
export TMPDIR=\"$PWD/.tmp_build\"
/sw/cades-open/gcc/12.2.0/bin/g++ -std=c++17 -Wall -O3 -funroll-loops -m64 -DMKL_ILP64 -march=native \\
  -I/home/9pm/installs/include -I/home/9pm/intel/oneapi/mkl/2024.2/include \\
  Square_Hubbard_tbc_G_calculation_UV.cc \\
  -L/home/9pm/installs/lib -L/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64 \\
  -L/home/9pm/intel/oneapi/tbb/latest/lib \\
  -lqbasis -larpackILP64 -Wl,--no-as-needed -lmkl_intel_ilp64 -lmkl_tbb_thread \\
  -Wl,-rpath-link,/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64 \\
  -lmkl_core -lpthread -ltbb -lm -ldl -o Square_Hubbard_tbc_G_calculation_UV.x
"""
    )
    build.chmod(0o700)
    (BATCH / "validate_pair.py").write_text(VALIDATOR)
    (BATCH / "install_pair.py").write_text(INSTALLER)
    final_monitor = Path(__file__).with_name("monitor_and_repair_final.py")
    if not final_monitor.is_file():
        raise SystemExit(f"Missing audited final monitor: {final_monitor}")
    (BATCH / "monitor_and_repair.py").write_text(final_monitor.read_text())
    for name in ("validate_pair.py", "install_pair.py", "monitor_and_repair.py"):
        (BATCH / name).chmod(0o700)
    (BATCH / "job_template_body.sh").write_text(job_body())

    submit_next = BATCH / "submit_next.sh"
    submit_next.write_text(
        SUBMIT_COMMON
        + r'''
ACCOUNT="${1:-ccsd}"
case "${ACCOUNT}" in ccsd) CAP="${CCSD_CAP}" ;; cnms) CAP="${CNMS_CAP}" ;; *) exit 0 ;; esac
[[ ! -e "${SCRIPT_DIR}/.priority_pause" ]] || exit 0
exec 211>"${LOCK_FILE}"
flock -x 211
current="$(count_jobs "${ACCOUNT}")"
(( current < CAP )) || exit 0
record="$(next_template "${ACCOUNT}" || true)"
[[ -n "${record}" ]] || exit 0
kind="${record%%|*}"; template="${record#*|}"
submit_one "${template}" "${ACCOUNT}" "${kind}"
'''
    )
    submit_next.chmod(0o700)

    submit_fill = BATCH / "submit_fill.sh"
    submit_fill.write_text(
        SUBMIT_COMMON
        + r'''
[[ "${GAXR_CONFIRM_SUBMIT:-NO}" == YES ]] || { echo 'Submission disarmed; set GAXR_CONFIRM_SUBMIT=YES.' >&2; exit 2; }
[[ ! -e "${SCRIPT_DIR}/.priority_pause" ]] || { echo 'Batch is priority-paused.'; exit 0; }
ONLY="${1:-all}"
fill() {
  local account="$1" cap="$2" current slots submitted repairs normal record kind template
  repairs=0
  while true; do
    record="$(next_template "${account}" || true)"
    [[ -n "${record}" ]] || break
    kind="${record%%|*}"; template="${record#*|}"
    [[ "${kind}" == repair ]] || break
    submit_one "${template}" "${account}" "${kind}" || break
    repairs=$((repairs+1))
  done
  current="$(count_jobs "${account}")"; slots=$((cap-current)); normal=0
  (( slots < 0 )) && slots=0
  while (( normal < slots )); do
    record="$(next_template "${account}" || true)"
    [[ -n "${record}" ]] || break
    kind="${record%%|*}"; template="${record#*|}"
    submit_one "${template}" "${account}" "${kind}" || break
    normal=$((normal+1))
  done
  submitted=$((repairs+normal))
  echo "${account}: active after repair submission=${current}; ordinary quota=${cap}; repairs=${repairs}; ordinary=${normal}; total newly submitted=${submitted}."
}
exec 210>"${LOCK_FILE}"
flock -x 210
case "${ONLY}" in
  all) fill ccsd "${CCSD_CAP}"; fill cnms "${CNMS_CAP}" ;;
  ccsd) fill ccsd "${CCSD_CAP}" ;;
  cnms) fill cnms "${CNMS_CAP}" ;;
  *) exit 1 ;;
esac
'''
    )
    submit_fill.chmod(0o700)

    path = path120()
    seeds: set[int] = set()
    rng = random.SystemRandom()
    while len(seeds) < len(path) * len(PARAMETERS):
        seeds.add(rng.randint(1, 4294967295))
    seed_iter = iter(seeds)
    rows = []
    index = 0
    preflight = []
    for path_index, (kx, ky) in enumerate(path, 1):
        for U, V, tp, set_name in PARAMETERS:
            index += 1
            gp_name = raw_name(U, V, tp, kx, ky, "Gp")
            gh_name = raw_name(U, V, tp, kx, ky, "Gh")
            gp = BATCH / "raw" / gp_name
            gh = BATCH / "raw" / gh_name
            source_gp = SOURCE / gp_name
            source_gh = SOURCE / gh_name
            preflight.append(
                {
                    "index": index,
                    "gp_name": gp_name,
                    "gh_name": gh_name,
                    "source_gp_exists": source_gp.is_file(),
                    "source_gh_exists": source_gh.is_file(),
                }
            )
            if source_gp.exists() or source_gh.exists():
                raise SystemExit(f"Pre-existing CADES source file conflicts with planned target: {gp_name} / {gh_name}")
            seed = next(seed_iter)
            row = {
                "index": index,
                "set_name": set_name,
                "path_index": path_index,
                "U": label(U),
                "V": label(V),
                "tp": label(tp),
                "kx": kx,
                "ky": ky,
                "seed": seed,
                "gp": str(gp),
                "gh": str(gh),
                "template": str(BATCH / "templates" / f"job_gaxr_{index:04d}.sh"),
            }
            rows.append(row)
            template = Path(row["template"])
            template.write_text(render_job(row, BATCH / "work" / f"task_{index:04d}", seed))
            template.chmod(0o700)
            subprocess.check_call(["bash", "-n", str(template)])

    with (BATCH / "manifest.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    with (BATCH / "path120.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["path_index", "kx", "ky"])
        for i, (kx, ky) in enumerate(path, 1):
            writer.writerow([i, kx, ky])
    with (BATCH / "preflight_existing.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(preflight[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(preflight)
    (BATCH / "submission_ledger.tsv").write_text("time\tjob_id\taccount\ttask_index\tkind\tscript\n")
    (BATCH / "repair_state.json").write_text(json.dumps({"version": 2, "used_repair_seeds": [], "targets": {}, "events": []}, indent=2) + "\n")
    (BATCH / "README.md").write_text(
        "# U-only and V-only axis-refinement Green-function scan\n\n"
        "Eleven t-prime-zero axis-refinement sets for live Fig. 3d and Fig. 4d.\n\n"
        "- 120 unique Gamma-X-M-Gamma points per set\n"
        "- 32 tasks, 100 GB, 8 h\n"
        "- immutable ordinary allocation: 990 ccsd, 330 cnms (90/30 per set); all ordinary jobs submitted at once\n"
        "- valid pairs require matching metadata and 999 `a` plus 999 `b` coefficients in both Gh/Gp files\n"
    )
    provenance = {
        "created_at": "2026-08-27",
        "purpose": "Refine live Fig. 3d and Fig. 4d sampling at tprime=0",
        "parameters": [
            {"U": U, "V": V, "tp": tp, "set_name": name}
            for U, V, tp, name in PARAMETERS
        ],
        "sets": len(PARAMETERS),
        "pairs_per_set": len(path),
        "ordinary_jobs": len(rows),
        "expected_raw_files": 2 * len(rows),
        "account_assignment": {
            "per_set": {"ccsd": 90, "cnms": 30},
            "total": {"ccsd": 990, "cnms": 330},
            "policy": "immutable_ordinary_assignment_all_submitted_immediately",
        },
        "resources": {"partition": "burst", "tasks": 32, "memory": "100G", "walltime": "08:00:00"},
        "validity": "matching U,V,tp,Q=0,0; positive finite nrm2; finite 999 a and 999 b coefficients in each Gh/Gp file",
        "repair_policy": "exactly_two_concurrent_distinct_globally_unused_seeds_isolated_workdirs_latest_account_first_valid_wins",
    }
    (BATCH / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (BATCH / "TWO_COPY_REPAIR_POLICY.md").write_text(
        "# Two-copy repair policy\n\n"
        "For each terminal ordinary failure or invalid completed pair, create exactly two "
        "concurrent isolated GAXRR copies on the target's latest assigned account. Use distinct "
        "globally unused QBASIS_LANCZOS_SEED values. Never launch a third copy while a round is "
        "active. The first strictly valid installer wins and cancels only its active sibling. "
        "If both fail, the next monitor pass starts one fresh two-copy round.\n"
    )
    for script in (build, submit_next, submit_fill, BATCH / "job_template_body.sh"):
        subprocess.check_call(["bash", "-n", str(script)])
    print(f"Created {BATCH}")
    print(f"Targets: {len(rows)}; raw files expected: {2 * len(rows)}")
    print("Existing CADES conflicts: 0")


if __name__ == "__main__":
    main()
