#!/usr/bin/python3.11
"""Prepare the finite-(U,V) Fig. 4 C_NN fullobs campaign on CADES.

This generator is intentionally submission-free.  It creates 25 independent
full-observable templates (one parameter point x 25 validated twists), a
manifest, guarded queue-fill helpers, a read-only status command, and an
analysis command.  Run it on CADES from any directory; all generated paths are
absolute.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path


BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
BATCH_NAME = "fullobs_25twist_u20v5_fig4_cnn_20260821"
BATCH = BASE / "fig4_cnn" / BATCH_NAME
SOLVER = BASE / "Hubbard_sym_testobs_UV.x"
SOURCE = BASE / "Hubbard_sym_testobs_UV.cc"
QBASIS_LIBRARY = Path("/home/9pm/installs/lib/libqbasis.so")
JOB_NAME = "F4C20V5"

# User-requested additional U=20, V=5 point for the finite-(U,V) Fig. 4(a)
# line.  This is a fresh add-only campaign and does not alter the original
# 300-target F4CNN25 batch.
PAIRS = [(20, "5")]

# Validated deterministic maximin panel from the U=16--36 transition study.
TWISTS = [
    (3, 3),
    (7, 7),
    (2, 8),
    (10, 12),
    (1, 14),
    (6, 16),
    (17, 17),
    (9, 21),
    (1, 23),
    (15, 23),
    (20, 25),
    (25, 25),
    (6, 26),
    (12, 29),
    (17, 29),
    (22, 30),
    (27, 30),
    (4, 32),
    (19, 34),
    (34, 34),
    (28, 35),
    (10, 36),
    (4, 38),
    (38, 38),
    (33, 39),
]

COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def deterministic_seed(U: int, V: str, kx: int, ky: int) -> int:
    payload = f"{BATCH_NAME}|U={U}|V={V}|f={kx}x{ky}".encode()
    # qbasis accepts an unsigned 32-bit seed; exclude zero.
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % 4294967295 + 1


def decimal_tag(value: str) -> str:
    return value.replace("-", "m").replace(".", "p")


def is_complete(path: Path) -> bool:
    try:
        return path.is_file() and bool(COMPLETE_RE.search(path.read_text(errors="ignore")))
    except OSError:
        return False


def make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


if os.environ.get("HOSTNAME", "").startswith("or-login") is False:
    # Do not make hostname a hard requirement (CADES hostnames can change),
    # but make accidental local execution obvious before touching anything.
    print(f"NOTICE: HOSTNAME={os.environ.get('HOSTNAME', '')!r}; expected a CADES login host.")

if BATCH.exists():
    raise SystemExit(f"Refusing to overwrite existing batch: {BATCH}")
if not SOLVER.is_file() or not os.access(SOLVER, os.X_OK):
    raise SystemExit(f"Missing executable solver: {SOLVER}")
if not SOURCE.is_file():
    raise SystemExit(f"Missing solver source: {SOURCE}")
if not QBASIS_LIBRARY.is_file():
    raise SystemExit(f"Missing qbasis runtime library: {QBASIS_LIBRARY}")
if SOURCE.stat().st_mtime > SOLVER.stat().st_mtime:
    raise SystemExit("Solver source is newer than the executable; rebuild and revalidate first.")

solver_hash = sha256(SOLVER)
source_hash = sha256(SOURCE)
qbasis_hash = sha256(QBASIS_LIBRARY)
expected_solver_hash = "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
expected_source_hash = "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
expected_qbasis_hash = "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
if (
    solver_hash != expected_solver_hash
    or source_hash != expected_source_hash
    or qbasis_hash != expected_qbasis_hash
):
    raise SystemExit(
        "Solver/source hash changed since preflight; do not generate without a fresh review.\n"
        f"solver {solver_hash}\nsource {source_hash}\nlibqbasis {qbasis_hash}"
    )

for dirname in (
    "templates",
    "submitted",
    "logs",
    "analysis",
    "work",
    "locks",
    "failed_outputs",
    "pinned_solver",
):
    (BATCH / dirname).mkdir(parents=True, exist_ok=False)

PINNED_SOLVER = BATCH / "pinned_solver" / SOLVER.name
PINNED_SOURCE = BATCH / "pinned_solver" / SOURCE.name
PINNED_QBASIS = BATCH / "pinned_solver" / QBASIS_LIBRARY.name
shutil.copy2(SOLVER, PINNED_SOLVER)
shutil.copy2(SOURCE, PINNED_SOURCE)
shutil.copy2(QBASIS_LIBRARY, PINNED_QBASIS)
PINNED_SOLVER.chmod(0o700)
PINNED_SOURCE.chmod(0o600)
PINNED_QBASIS.chmod(0o700)
(BATCH / "PINNED_SHA256SUMS").write_text(
    f"{solver_hash}  pinned_solver/{PINNED_SOLVER.name}\n"
    f"{source_hash}  pinned_solver/{PINNED_SOURCE.name}\n"
    f"{qbasis_hash}  pinned_solver/{PINNED_QBASIS.name}\n"
)

manifest_rows: list[dict[str, object]] = []
seeds: set[int] = set()
results: set[str] = set()
index = 0

for U, V in PAIRS:
    for twist_index, (kx, ky) in enumerate(TWISTS, 1):
        index += 1
        seed = deterministic_seed(U, V, kx, ky)
        if seed in seeds:
            raise RuntimeError(f"Seed collision: {seed}")
        seeds.add(seed)
        result_name = f"L4x4Nup8Ndn8U{U}V{V}tp0f{kx}x{ky}Q0x0_obs.dat"
        result = BASE / result_name
        if str(result) in results:
            raise RuntimeError(f"Duplicate result: {result}")
        results.add(str(result))
        if result.exists() and not is_complete(result):
            raise SystemExit(f"Pre-existing incomplete/conflicting result: {result}")

        state = "complete" if is_complete(result) else "template"
        template = ""
        if state == "template":
            template_path = BATCH / "templates" / (
                f"job_f4c20v5_{index:04d}_U{U}_V{decimal_tag(V)}_f{kx}x{ky}.sh"
            )
            script = f"""#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J {JOB_NAME}
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -o {BATCH}/logs/%x-%j.out
#SBATCH -e {BATCH}/logs/%x-%j.err

set -Eeuo pipefail
umask 077
BATCH='{BATCH}'
BASE='{BASE}'
SOLVER='{PINNED_SOLVER}'
EXPECTED_SOLVER_SHA256='{solver_hash}'
PINNED_LIBQBASIS='{PINNED_QBASIS}'
EXPECTED_QBASIS_SHA256='{qbasis_hash}'
INDEX='{index}'
U='{U}'
V='{V}'
KX='{kx}'
KY='{ky}'
SEED='{seed}'
RESULT_NAME='{result_name}'
RESULT="${{BASE}}/${{RESULT_NAME}}"
WORK="${{BATCH}}/work/task_${{INDEX}}_${{SLURM_JOB_ID:-manual}}"
LOCK="${{BATCH}}/locks/${{RESULT_NAME}}.lock"

refilled=0
refill() {{
  if (( refilled == 0 )); then
    refilled=1
    bash "${{BATCH}}/submit_next.sh" "${{SLURM_JOB_ACCOUNT:-ccsd}}" || true
  fi
}}
trap refill EXIT
trap 'exit 143' TERM INT

mkdir -p "${{WORK}}"
exec 9>"${{LOCK}}"
flock -x 9

if [[ -s "${{RESULT}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{RESULT}}"; then
  echo '{JOB_NAME}_RESULT ALREADY_COMPLETE index={index} U={U} V={V} kx={kx} ky={ky}'
  exit 0
fi
if [[ -e "${{RESULT}}" ]]; then
  echo '{JOB_NAME}_RESULT CONFLICT_INCOMPLETE index={index} path='"${{RESULT}}" >&2
  exit 92
fi
actual_sha256="$(sha256sum "${{SOLVER}}" | awk '{{print $1}}')"
if [[ "${{actual_sha256}}" != "${{EXPECTED_SOLVER_SHA256}}" ]]; then
  echo '{JOB_NAME}_RESULT SOLVER_HASH_MISMATCH expected='"${{EXPECTED_SOLVER_SHA256}}"' actual='"${{actual_sha256}}" >&2
  exit 96
fi
actual_qbasis_sha256="$(sha256sum "${{PINNED_LIBQBASIS}}" | awk '{{print $1}}')"
if [[ "${{actual_qbasis_sha256}}" != "${{EXPECTED_QBASIS_SHA256}}" ]]; then
  echo '{JOB_NAME}_RESULT QBASIS_HASH_MISMATCH expected='"${{EXPECTED_QBASIS_SHA256}}"' actual='"${{actual_qbasis_sha256}}" >&2
  exit 97
fi

cd "${{WORK}}"
ln -sfn "${{SOLVER}}" ./Hubbard_sym_testobs_UV.x
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED="${{SEED}}"
export LD_LIBRARY_PATH={BATCH}/pinned_solver:/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}
resolved_qbasis="$(ldd "${{SOLVER}}" | awk '$1=="libqbasis.so" {{print $3}}')"
if [[ "$(readlink -f "${{resolved_qbasis}}")" != "$(readlink -f "${{PINNED_LIBQBASIS}}")" ]]; then
  echo '{JOB_NAME}_RESULT QBASIS_RESOLUTION_MISMATCH expected='"${{PINNED_LIBQBASIS}}"' actual='"${{resolved_qbasis}}" >&2
  exit 98
fi
cat > run_metadata.txt <<EOF
index ${{INDEX}}
U ${{U}}
V ${{V}}
kx ${{KX}}
ky ${{KY}}
seed ${{SEED}}
solver_sha256 ${{EXPECTED_SOLVER_SHA256}}
qbasis_sha256 ${{EXPECTED_QBASIS_SHA256}}
slurm_job_id ${{SLURM_JOB_ID:-manual}}
slurm_account ${{SLURM_JOB_ACCOUNT:-unknown}}
hostname $(hostname)
started_at $(date --iso-8601=seconds)
EOF

set +e
time ./Hubbard_sym_testobs_UV.x 8 8 "${{KX}}" "${{KY}}" 0 0 "${{U}}" "${{V}}" 0
job_rc=$?
set -e
LOCAL_RESULT="${{WORK}}/${{RESULT_NAME}}"
if (( job_rc != 0 )) || [[ ! -s "${{LOCAL_RESULT}}" ]] || ! grep -Eq '^status[[:space:]]+COMPLETE$' "${{LOCAL_RESULT}}"; then
  echo '{JOB_NAME}_RESULT FAILED rc='"${{job_rc}}"' index={index} U={U} V={V} kx={kx} ky={ky} seed={seed}' >&2
  (( job_rc == 0 )) && job_rc=90
  exit "${{job_rc}}"
fi

# Recheck under the per-result lock before an atomic installation.  Never
# overwrite an incomplete external file or a COMPLETE result from another run.
if [[ -s "${{RESULT}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{RESULT}}"; then
  echo '{JOB_NAME}_RESULT DUPLICATE_COMPLETE index={index} U={U} V={V} kx={kx} ky={ky}'
  exit 0
fi
if [[ -e "${{RESULT}}" ]]; then
  echo '{JOB_NAME}_RESULT INSTALL_CONFLICT_INCOMPLETE index={index} path='"${{RESULT}}" >&2
  exit 93
fi
INSTALL_TMP="${{RESULT}}.install.${{SLURM_JOB_ID:-manual}}.tmp"
cp -p "${{LOCAL_RESULT}}" "${{INSTALL_TMP}}"
grep -Eq '^status[[:space:]]+COMPLETE$' "${{INSTALL_TMP}}"
mv "${{INSTALL_TMP}}" "${{RESULT}}"
echo "finished_at $(date --iso-8601=seconds)" >> run_metadata.txt
echo '{JOB_NAME}_RESULT COMPLETE index={index} U={U} V={V} kx={kx} ky={ky} seed={seed}'
"""
            template_path.write_text(script)
            make_executable(template_path)
            template = str(template_path)

        manifest_rows.append(
            {
                "index": index,
                "U": U,
                "V": V,
                "V_over_U": float(V) / U,
                "expected_phase": "Mott",
                "twist_index": twist_index,
                "kx": kx,
                "ky": ky,
                "seed": seed,
                "job_name": JOB_NAME,
                "result": str(result),
                "state_at_generation": state,
                "template": template,
            }
        )

manifest_fields = list(manifest_rows[0])
with (BATCH / "manifest.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, delimiter="\t", fieldnames=manifest_fields)
    writer.writeheader()
    writer.writerows(manifest_rows)

with (BATCH / "twist_panel.tsv").open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["twist_index", "kx", "ky", "diagonal", "symmetry_multiplicity"])
    for twist_index, (kx, ky) in enumerate(TWISTS, 1):
        writer.writerow([twist_index, kx, ky, kx == ky, 1 if kx == ky else 2])

(BATCH / "submission.tsv").write_text(
    "submitted_at\taccount\tjob_id\tindex\tU\tV\tkx\tky\trun_script\tresult\n"
)

provenance = {
    "created_at": subprocess.run(
        ["date", "--iso-8601=seconds"], check=True, text=True, capture_output=True
    ).stdout.strip(),
    "batch": str(BATCH),
    "job_name": JOB_NAME,
    "original_solver": str(SOLVER),
    "pinned_solver": str(PINNED_SOLVER),
    "solver_sha256": solver_hash,
    "original_source": str(SOURCE),
    "pinned_source": str(PINNED_SOURCE),
    "source_sha256": source_hash,
    "original_qbasis_library": str(QBASIS_LIBRARY),
    "pinned_qbasis_library": str(PINNED_QBASIS),
    "qbasis_library_sha256": qbasis_hash,
    "locate_E0_lanczos_maxit": 10000,
    "physics": {"Lx": 4, "Ly": 4, "Nup": 8, "Ndn": 8, "Qm": 0, "Qn": 0, "tp": 0},
    "resources": {
        "partition": "burst",
        "nodes": 1,
        "tasks": 32,
        "cpus_per_task": 1,
        "memory": "100G",
        "time_limit": "08:00:00",
        "default_total_user_account_cap": 150,
    },
    "pairs": [{"U": U, "V": V, "V_over_U": float(V) / U} for U, V in PAIRS],
    "twists": [{"kx": kx, "ky": ky} for kx, ky in TWISTS],
    "target_count": len(manifest_rows),
    "complete_reused_at_generation": sum(r["state_at_generation"] == "complete" for r in manifest_rows),
    "templates_at_generation": sum(r["state_at_generation"] == "template" for r in manifest_rows),
    "aggregation": {
        "primary_C_NN_estimator": "unweighted arithmetic mean over deterministic 25-twist maximin panel",
        "diagnostic_estimator": "exchange-symmetry-multiplicity-weighted panel mean",
        "twist_spread_is_not_standard_error": True,
    },
}
(BATCH / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")

submit_next = f'''#!/bin/bash
# generated for {BATCH}
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
TEMPLATE_DIR="${{SCRIPT_DIR}}/templates"
SUBMITTED_DIR="${{SCRIPT_DIR}}/submitted"
RAW_LOG="${{SCRIPT_DIR}}/logs/submit.log"
TABLE_LOG="${{SCRIPT_DIR}}/submission.tsv"
LOCK_FILE="${{SCRIPT_DIR}}/.queue.lock"
MANIFEST="${{SCRIPT_DIR}}/manifest.tsv"
ACCOUNT="${{1:-ccsd}}"
case "${{ACCOUNT}}" in
  ccsd) CAP="${{F4C20V5_CCSD_USER_CAP:-150}}" ;;
  cnms) CAP="${{F4C20V5_CNMS_USER_CAP:-150}}" ;;
  *) echo "Unsupported account: ${{ACCOUNT}}" >&2; exit 1 ;;
esac
count_jobs_excluding_self() {{
  local self="${{SLURM_JOB_ID:-}}"
  squeue -h -r -u "${{USER}}" -o '%i|%a' |
    awk -F'|' -v account="${{ACCOUNT}}" -v self="${{self}}" '$1 != self && $2 == account {{n++}} END {{print n+0}}'
}}
submit_one() {{
  local template="$1" base run sbout job_id idx row
  base="$(basename "${{template}}")"
  run="${{SUBMITTED_DIR}}/${{base%.sh}}_${{ACCOUNT}}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${{ACCOUNT}}/" "${{template}}" > "${{run}}"
  chmod 700 "${{run}}"
  if sbout="$(sbatch "${{run}}" 2>&1)"; then
    job_id="$(awk '/Submitted batch job/ {{print $4}}' <<<"${{sbout}}")"
    [[ "${{job_id}}" =~ ^[0-9]+$ ]] || {{ echo "Could not parse sbatch output: ${{sbout}}" >&2; rm -f "${{run}}"; return 1; }}
    idx="$(sed -n 's/^INDEX='"'"'\\([0-9][0-9]*\\)'"'"'$/\\1/p' "${{run}}")"
    row="$(awk -F'\\t' -v i="${{idx}}" 'NR>1 && $1==i {{print $1"\\t"$2"\\t"$3"\\t"$7"\\t"$8; exit}}' "${{MANIFEST}}")"
    [[ -n "${{row}}" ]] || {{ echo "Manifest lookup failed for index ${{idx}}" >&2; return 1; }}
    mv "${{template}}" "${{SUBMITTED_DIR}}/${{base%.sh}}.template"
    printf '%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "${{ACCOUNT}}" "${{run}}" "${{sbout}}" >> "${{RAW_LOG}}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date --iso-8601=seconds)" "${{ACCOUNT}}" "${{job_id}}" "${{row}}" "${{run}}" "$(awk -F'\\t' -v i="${{idx}}" 'NR>1 && $1==i {{print $11; exit}}' "${{MANIFEST}}")" >> "${{TABLE_LOG}}"
    return 0
  fi
  rm -f "${{run}}"
  printf '%s\t%s\tFAILED\t%s\t%s\n' "$(date '+%F %T')" "${{ACCOUNT}}" "${{base}}" "${{sbout}}" >> "${{RAW_LOG}}"
  return 1
}}
exec 211>"${{LOCK_FILE}}"
flock -x 211
current="$(count_jobs_excluding_self)"
(( current < CAP )) || exit 0
next="$(find "${{TEMPLATE_DIR}}" -maxdepth 1 -type f -name 'job_f4c20v5_*.sh' | LC_ALL=C sort | head -n 1 || true)"
[[ -n "${{next}}" ]] || exit 0
submit_one "${{next}}"
'''
(BATCH / "submit_next.sh").write_text(submit_next)
make_executable(BATCH / "submit_next.sh")

submit_fill = f'''#!/bin/bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BASE='{BASE}'
PINNED_SOLVER='{PINNED_SOLVER}'
PINNED_SOURCE='{PINNED_SOURCE}'
PINNED_QBASIS='{PINNED_QBASIS}'
TEMPLATE_DIR="${{SCRIPT_DIR}}/templates"
SUBMITTED_DIR="${{SCRIPT_DIR}}/submitted"
RAW_LOG="${{SCRIPT_DIR}}/logs/submit.log"
TABLE_LOG="${{SCRIPT_DIR}}/submission.tsv"
LOCK_FILE="${{SCRIPT_DIR}}/.queue.lock"
MANIFEST="${{SCRIPT_DIR}}/manifest.tsv"
ACCOUNT="${{1:-ccsd}}"
case "${{ACCOUNT}}" in
  ccsd) CAP="${{F4C20V5_CCSD_USER_CAP:-150}}" ;;
  cnms) CAP="${{F4C20V5_CNMS_USER_CAP:-150}}" ;;
  *) echo "Unsupported account: ${{ACCOUNT}}" >&2; exit 1 ;;
esac
[[ "${{F4C20V5_CONFIRM_SUBMIT:-NO}}" == YES ]] || {{ echo 'Submission disarmed; set F4C20V5_CONFIRM_SUBMIT=YES.' >&2; exit 2; }}
[[ -x "${{PINNED_SOLVER}}" ]] || {{ echo 'Missing pinned observable executable.' >&2; exit 1; }}
[[ -f "${{PINNED_SOURCE}}" ]] || {{ echo 'Missing pinned observable source.' >&2; exit 1; }}
[[ "$(sha256sum "${{PINNED_SOLVER}}" | awk '{{print $1}}')" == '{solver_hash}' ]] || {{ echo 'Pinned solver hash mismatch.' >&2; exit 1; }}
[[ "$(sha256sum "${{PINNED_SOURCE}}" | awk '{{print $1}}')" == '{source_hash}' ]] || {{ echo 'Pinned source hash mismatch.' >&2; exit 1; }}
[[ "$(sha256sum "${{PINNED_QBASIS}}" | awk '{{print $1}}')" == '{qbasis_hash}' ]] || {{ echo 'Pinned qbasis library hash mismatch.' >&2; exit 1; }}
count_jobs() {{
  squeue -h -r -u "${{USER}}" -o '%a' | awk -v account="${{ACCOUNT}}" '$1 == account {{n++}} END {{print n+0}}'
}}
submit_one() {{
  local template="$1" base run sbout job_id idx row
  base="$(basename "${{template}}")"
  run="${{SUBMITTED_DIR}}/${{base%.sh}}_${{ACCOUNT}}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${{ACCOUNT}}/" "${{template}}" > "${{run}}"
  chmod 700 "${{run}}"
  if sbout="$(sbatch "${{run}}" 2>&1)"; then
    job_id="$(awk '/Submitted batch job/ {{print $4}}' <<<"${{sbout}}")"
    [[ "${{job_id}}" =~ ^[0-9]+$ ]] || {{ echo "Could not parse sbatch output: ${{sbout}}" >&2; rm -f "${{run}}"; return 1; }}
    idx="$(sed -n 's/^INDEX='"'"'\\([0-9][0-9]*\\)'"'"'$/\\1/p' "${{run}}")"
    row="$(awk -F'\\t' -v i="${{idx}}" 'NR>1 && $1==i {{print $1"\\t"$2"\\t"$3"\\t"$7"\\t"$8; exit}}' "${{MANIFEST}}")"
    [[ -n "${{row}}" ]] || {{ echo "Manifest lookup failed for index ${{idx}}" >&2; return 1; }}
    mv "${{template}}" "${{SUBMITTED_DIR}}/${{base%.sh}}.template"
    printf '%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "${{ACCOUNT}}" "${{run}}" "${{sbout}}" >> "${{RAW_LOG}}"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date --iso-8601=seconds)" "${{ACCOUNT}}" "${{job_id}}" "${{row}}" "${{run}}" "$(awk -F'\\t' -v i="${{idx}}" 'NR>1 && $1==i {{print $11; exit}}' "${{MANIFEST}}")" >> "${{TABLE_LOG}}"
    return 0
  fi
  rm -f "${{run}}"
  printf '%s\t%s\tFAILED\t%s\t%s\n' "$(date '+%F %T')" "${{ACCOUNT}}" "${{base}}" "${{sbout}}" >> "${{RAW_LOG}}"
  return 1
}}
exec 210>"${{LOCK_FILE}}"
flock -x 210
before="$(count_jobs)"
slots=$((CAP-before))
(( slots > 0 )) || {{ echo "${{ACCOUNT}}: user jobs=${{before}} already meet/exceed cap=${{CAP}}; submitted=0."; exit 0; }}
submitted=0
while (( submitted < slots )); do
  next="$(find "${{TEMPLATE_DIR}}" -maxdepth 1 -type f -name 'job_f4c20v5_*.sh' | LC_ALL=C sort | head -n 1 || true)"
  [[ -n "${{next}}" ]] || break
  submit_one "${{next}}" || break
  submitted=$((submitted+1))
done
echo "${{ACCOUNT}}: user jobs before=${{before}}; cap=${{CAP}}; newly submitted=${{submitted}}."
'''
(BATCH / "submit_fill.sh").write_text(submit_fill)
make_executable(BATCH / "submit_fill.sh")

status_script = f'''#!/usr/bin/python3.11
import csv, os, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path
BATCH=Path(r"{BATCH}")
COMPLETE_RE=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
def state(path):
    path=Path(path)
    try:
        if not path.exists(): return "missing"
        if path.is_file() and COMPLETE_RE.search(path.read_text(errors="ignore")): return "complete"
        return "incomplete"
    except OSError: return "unreadable"
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(), delimiter="\\t"))
counts=Counter(state(r["result"]) for r in rows)
print("TOTAL", len(rows), " ".join(f"{{k}}={{v}}" for k,v in sorted(counts.items())))
groups=defaultdict(Counter)
for row in rows: groups[(row["U"],row["V"])][state(row["result"])]+=1
for (U,V), c in groups.items():
    print(f"U={{U}} V={{V}}: complete={{c['complete']}}/25 incomplete={{c['incomplete']}} missing={{c['missing']}}")
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%i|%j|%a|%T|%M|%l|%R"], text=True, capture_output=True).stdout
active=[]
for line in out.splitlines():
    fields=[x.strip() for x in line.split("|")]
    if len(fields)==7 and fields[1] in {{"{JOB_NAME}","{JOB_NAME}R"}}: active.append(fields)
ac=Counter((r[1],r[2],r[3]) for r in active)
print("ACTIVE", " ".join(f"{{j}}:{{a}}:{{s}}={{n}}" for (j,a,s),n in sorted(ac.items())) or "none")
print("TEMPLATES", len(list((BATCH/"templates").glob("job_f4c20v5_*.sh"))))
print("SUBMITTED_SCRIPTS", len(list((BATCH/"submitted").glob("job_f4c20v5_*_ccsd.sh"))) + len(list((BATCH/"submitted").glob("job_f4c20v5_*_cnms.sh"))))
'''
(BATCH / "status.py").write_text(status_script)
make_executable(BATCH / "status.py")

analyze_script = f'''#!/usr/bin/python3.11
import csv, math, re, statistics, sys
from pathlib import Path
BATCH=Path(r"{BATCH}")
OUT=BATCH/"analysis"
COMPLETE_RE=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(), delimiter="\\t"))
required=["E0","<ni_upni_dn>","<mCDW2_pipi>","<C1_NN>","<nn_NN>","<Kinetic_per_site>"]
parsed=[]
for row in rows:
    path=Path(row["result"])
    text=path.read_text(errors="ignore") if path.is_file() else ""
    if not COMPLETE_RE.search(text):
        print(f"Not ready: {{path}}", file=sys.stderr); sys.exit(2)
    values={{}}
    for line in text.splitlines():
        parts=line.split(None,1)
        if len(parts)==2: values[parts[0]]=parts[1]
    missing=[key for key in required if key not in values]
    if missing: raise SystemExit(f"Missing {{missing}} in {{path}}")
    parsed.append({{
        "index":int(row["index"]), "U":int(row["U"]), "V":float(row["V"]),
        "V_over_U":float(row["V_over_U"]), "twist_index":int(row["twist_index"]),
        "kx":int(row["kx"]), "ky":int(row["ky"]), "seed":int(row["seed"]),
        "E0":float(values["E0"]), "D_site":float(values["<ni_upni_dn>"]),
        "mCDW2_pipi":float(values["<mCDW2_pipi>"]), "C1_NN":float(values["<C1_NN>"]),
        "nn_NN":float(values["<nn_NN>"]), "kinetic_per_site":float(values["<Kinetic_per_site>"]),
        "status":"COMPLETE", "result":row["result"],
    }})
OUT.mkdir(exist_ok=True)
with (OUT/"fig4_cnn_25twist_observables.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(parsed[0])); w.writeheader(); w.writerows(parsed)
groups=defaultdict(list)
for row in parsed: groups[(row["U"],row["V"])].append(row)
summary=[]
for (U,V), group in sorted(groups.items()):
    if len(group)!=25: raise SystemExit(f"Expected 25 twists at U={{U}} V={{V}}, found {{len(group)}}")
    C=[r["C1_NN"] for r in group]
    weights=[1 if r["kx"]==r["ky"] else 2 for r in group]
    Cmean=statistics.fmean(C)
    Csym=sum(w*x for w,x in zip(weights,C))/sum(weights)
    factor=(2*U-V)/(U-V)
    summary.append({{
        "U":U,"V":V,"V_over_U":V/U,"expected_phase":"Mott","complete_twists":25,
        "C1_NN_panel_mean":Cmean,"C1_NN_panel_min":min(C),"C1_NN_panel_max":max(C),
        "C1_NN_panel_spread":max(C)-min(C),"C1_NN_panel_population_std":statistics.pstdev(C),
        "C1_NN_symmetry_weighted_diagnostic":Csym,
        "C1_NN_estimator_difference":Csym-Cmean,
        "s_NN_prediction":1+factor*(2*Cmean-0.5),
        "s_NN_prediction_symmetry_weighted_diagnostic":1+factor*(2*Csym-0.5),
        "D_site_panel_mean":statistics.fmean(r["D_site"] for r in group),
        "mCDW2_pipi_panel_mean":statistics.fmean(r["mCDW2_pipi"] for r in group),
        "nn_NN_panel_mean":statistics.fmean(r["nn_NN"] for r in group),
        "kinetic_per_site_panel_mean":statistics.fmean(r["kinetic_per_site"] for r in group),
        "panel_method":"unweighted arithmetic mean of deterministic maximin 25-twist panel",
        "twist_spread_is_standard_error":False,
    }})
with (OUT/"fig4_cnn_25twist_summary.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
for row in summary:
    print("U={{U}} V={{V:g}} C_NN={{C1_NN_panel_mean:.12f}} spread={{C1_NN_panel_spread:.3e}} s_pred={{s_NN_prediction:.9f}}".format(**row))
'''
(BATCH / "analyze.py").write_text(analyze_script)
make_executable(BATCH / "analyze.py")

preflight_script = f'''#!/usr/bin/python3.11
import csv, hashlib, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path
BATCH=Path(r"{BATCH}")
BASE=Path(r"{BASE}")
PINNED_SOLVER=Path(r"{PINNED_SOLVER}")
PINNED_SOURCE=Path(r"{PINNED_SOURCE}")
PINNED_QBASIS=Path(r"{PINNED_QBASIS}")
EXPECTED_SOLVER="{solver_hash}"
EXPECTED_SOURCE="{source_hash}"
EXPECTED_QBASIS="{qbasis_hash}"
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\\t"))
assert len(rows)==25, len(rows)
assert len({{r["index"] for r in rows}})==25
assert len({{r["seed"] for r in rows}})==25
assert len({{r["result"] for r in rows}})==25
groups=Counter((r["U"],r["V"]) for r in rows)
assert groups == {{("20", "5"): 25}}, groups
assert sha(PINNED_SOLVER)==EXPECTED_SOLVER
assert sha(PINNED_SOURCE)==EXPECTED_SOURCE
assert sha(PINNED_QBASIS)==EXPECTED_QBASIS
assert (BATCH/"PINNED_SHA256SUMS").read_text()==f"{{EXPECTED_SOLVER}}  pinned_solver/Hubbard_sym_testobs_UV.x\\n{{EXPECTED_SOURCE}}  pinned_solver/Hubbard_sym_testobs_UV.cc\\n{{EXPECTED_QBASIS}}  pinned_solver/libqbasis.so\\n"
templates=list((BATCH/"templates").glob("job_f4c20v5_*.sh"))
for path in templates:
    text=path.read_text()
    assert "#SBATCH -A __ACCOUNT__" in text
    assert "#SBATCH -J {JOB_NAME}" in text
    assert "#SBATCH --mem=100G" in text and "#SBATCH -t 08:00:00" in text
    assert EXPECTED_SOLVER in text
    p=subprocess.run(["bash","-n",str(path)],capture_output=True,text=True)
    if p.returncode: raise SystemExit(f"bash -n failed for {{path}}: {{p.stderr}}")
for helper in ["submit_fill.sh","submit_next.sh"]:
    p=subprocess.run(["bash","-n",str(BATCH/helper)],capture_output=True,text=True)
    if p.returncode: raise SystemExit(f"bash -n failed for {{helper}}: {{p.stderr}}")
complete=0; incomplete=[]
rx=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
for row in rows:
    p=Path(row["result"])
    if not p.exists(): continue
    if p.is_file() and rx.search(p.read_text(errors="ignore")): complete+=1
    else: incomplete.append(str(p))
if incomplete: raise SystemExit("Conflicting incomplete target files:\\n"+"\\n".join(incomplete))
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%j|%a|%T"],capture_output=True,text=True).stdout
active=[line for line in out.splitlines() if line.split("|",1)[0].strip() in {{"{JOB_NAME}","{JOB_NAME}R"}}]
if active: raise SystemExit("This batch job name is already active:\\n"+"\\n".join(active))
acct=Counter()
for line in out.splitlines():
    f=[x.strip() for x in line.split("|")]
    if len(f)==3: acct[(f[1],f[2])]+=1
print("PREFLIGHT PASS")
print(f"manifest={{len(rows)}} templates={{len(templates)}} complete_reused={{complete}}")
print("active user jobs:", " ".join(f"{{a}}:{{s}}={{n}}" for (a,s),n in sorted(acct.items())) or "none")
print("submission remains DISARMED unless F4C20V5_CONFIRM_SUBMIT=YES")
'''
(BATCH / "preflight.py").write_text(preflight_script)
make_executable(BATCH / "preflight.py")

dry_run_script = f'''#!/usr/bin/python3.11
import os, subprocess, sys
from pathlib import Path
BATCH=Path(r"{BATCH}")
account=sys.argv[1] if len(sys.argv)>1 else "ccsd"
if account not in {{"ccsd","cnms"}}: raise SystemExit("account must be ccsd or cnms")
cap=int(os.environ.get("F4C20V5_"+account.upper()+"_USER_CAP","150"))
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%a"],text=True,capture_output=True,check=True).stdout
current=sum(line.strip()==account for line in out.splitlines())
templates=sorted((BATCH/"templates").glob("job_f4c20v5_*.sh"))
slots=max(0,cap-current)
n=min(slots,len(templates))
print(f"DRY RUN ONLY: account={{account}} current_user_jobs={{current}} cap={{cap}} open_slots={{slots}} templates={{len(templates)}} would_submit={{n}}")
for path in templates[:n]: print("WOULD_RENDER_AND_SBATCH", path)
'''
(BATCH / "dry_run_submit.py").write_text(dry_run_script)
make_executable(BATCH / "dry_run_submit.py")

readme = f'''# Fig. 4 finite-(U,V) C_NN fullobs campaign

Created on CADES: {provenance["created_at"]}

Batch root: `{BATCH}`

Targets: U=20, V=5 on 25 deterministic maximin twists = 25 independent
fullobs calculations.  No exact target result existed at generation.

Pair:
{os.linesep.join(f"- U={U}, V={V}" for U,V in PAIRS)}

Original solver: `{SOLVER}`
Pinned executable actually run by every job: `{PINNED_SOLVER}`
Pinned source: `{PINNED_SOURCE}`
Pinned qbasis runtime library: `{PINNED_QBASIS}`
Solver SHA-256: `{solver_hash}`
Source SHA-256: `{source_hash}`
qbasis library SHA-256: `{qbasis_hash}`
The reviewed source calls `locate_E0_lanczos(..., 10000)`.

Physics: 4x4, Nup=Ndn=8, Q=(0,0), t'=0.
Resources per job: account placeholder, burst, 1 node, 32 tasks,
1 CPU/task, 100 GB, 8 hours, TERM warning at 120 s.
Job name: `{JOB_NAME}`.

Safety:
- Generation is submission-free and refuses to overwrite an existing batch.
- `submit_fill.sh` is disarmed without `F4C20V5_CONFIRM_SUBMIT=YES`.
- Results are generated in isolated per-job work directories, validated for a
  standalone `status COMPLETE`, and then installed atomically.
- An incomplete root-level target is never deleted or overwritten.
- Each job runs the batch-local pinned executable and checks its reviewed
  SHA-256 before execution.  `PINNED_SHA256SUMS` pins the executable, source,
  and qbasis runtime library for monitor/audit use.  The pinned-library
  directory is first in `LD_LIBRARY_PATH`, and every job verifies that `ldd`
  resolves `libqbasis.so` to the pinned copy.
- Queue filling counts all of the user's jobs on the selected account and
  defaults to the established total-user cap of 150 per account.

Read-only validation:
```
/usr/bin/python3.11 preflight.py
/usr/bin/python3.11 dry_run_submit.py ccsd
/usr/bin/python3.11 status.py
```

Armed initial submission (not run by the generator):
```
F4C20V5_CONFIRM_SUBMIT=YES F4C20V5_CCSD_USER_CAP=150 ./submit_fill.sh ccsd
```
Each completed/skipped batch job calls `submit_next.sh`, keeping the campaign
moving without exceeding the selected total-user account cap.

Submission records:
- `logs/submit.log`: raw tab-separated timestamp, account, rendered script,
  and exact `sbatch` response.
- `submission.tsv`: header plus submitted_at, account, job_id, manifest index,
  U, V, kx, ky, rendered run script, and result path.

Final aggregation:
```
/usr/bin/python3.11 analyze.py
```
The primary C_NN estimator is the unweighted arithmetic mean over this exact
validated 25-twist panel.  The exchange-symmetry-weighted mean is emitted only
as a diagnostic.  Twist spread is explicitly not treated as a standard error.
At the existing U=40 all-twist controls (V=0,4,8,9), the primary panel-minus-
861-grid C_NN differences are -1.35e-7, -1.76e-7, -2.44e-7, and -2.69e-7.
'''
(BATCH / "README.md").write_text(readme)

# Freeze the generator used to create the remote batch beside its products.
try:
    shutil.copy2(Path(__file__).resolve(), BATCH / "setup_generator.py")
except shutil.SameFileError:
    pass

print(f"Prepared (not submitted): {BATCH}")
print(f"Targets: {len(manifest_rows)}; templates: {sum(r['state_at_generation']=='template' for r in manifest_rows)}")
print(f"Solver SHA-256: {solver_hash}")
print("Next read-only command: python3 {}/preflight.py".format(BATCH))
