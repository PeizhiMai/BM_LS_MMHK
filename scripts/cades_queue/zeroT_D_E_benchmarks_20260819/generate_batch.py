#!/usr/bin/env python3
"""Generate the isolated CADES E0/D production manifest and job templates."""

import argparse
import csv
from pathlib import Path


SETS = [(2, 0.5), (4, 1), (6, 1.5), (0, 0.45), (0, 1), (0, 2)]
PILOT_SEEDS = {
    (2, 0.5): 2026081901,
    (4, 1): 2026081902,
    (6, 1.5): 2026081903,
    (0, 0.45): 2026081905,
    (0, 1): 2026081906,
    (0, 2): 2026081907,
}


def label(value):
    return f"{value:g}"


def slug(value):
    return label(value).replace("-", "m").replace(".", "p")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(
            "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
            "literature_benchmarks_20260819"
        ),
    )
    return parser.parse_args()


def template_text(root, task):
    return f"""#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J E0DZT
#SBATCH --mem=100G
#SBATCH -t 8:00:00
#SBATCH -o {root}/logs/%x-%j.out
#SBATCH -e {root}/logs/%x-%j.err

set -uo pipefail
ROOT={root}
cd "$ROOT/results"
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}

result="$ROOT/results/{task['result_filename']}"
if [[ -s "$result" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "$result"; then
    echo "E0DZT_RESULT ALREADY_COMPLETE task={task['task_id']} U={task['U']} V={task['V']} kx={task['kx']} ky={task['ky']}"
    bash "$ROOT/scripts/submit_next_E0D.sh" "${{SLURM_JOB_ACCOUNT:-ccsd}}" || true
    exit 0
fi

rm -f "$result"
set +e
time "$ROOT/bin/Hubbard_sym_E0_D_UV.x" 8 8 {task['kx']} {task['ky']} 0 0 {task['U']} {task['V']} 0 {task['seed']}
job_rc=$?
set -e

if (( job_rc == 0 )) && [[ -s "$result" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "$result"; then
    echo "E0DZT_RESULT COMPLETE task={task['task_id']} U={task['U']} V={task['V']} kx={task['kx']} ky={task['ky']} seed={task['seed']}"
else
    echo "E0DZT_RESULT FAILED rc=${{job_rc}} task={task['task_id']} U={task['U']} V={task['V']} kx={task['kx']} ky={task['ky']} seed={task['seed']}" >&2
    (( job_rc == 0 )) && job_rc=90
fi

# Refill the account even after a failed target; the retained script and Slurm
# log remain available for diagnosis and targeted repair.
bash "$ROOT/scripts/submit_next_E0D.sh" "${{SLURM_JOB_ACCOUNT:-ccsd}}" || true
exit "$job_rc"
"""


def main():
    args = parse_args()
    root = args.root
    manifest_dir = root / "manifests"
    template_dir = root / "templates"
    submitted_dir = root / "submitted"
    for directory in [manifest_dir, template_dir, submitted_dir, root / "logs", root / "results", root / "state"]:
        directory.mkdir(parents=True, exist_ok=True)

    # Refuse to mix an old template population with a freshly numbered one.
    for old in template_dir.glob("job_e0d_*.sh"):
        old.unlink()

    rows = []
    task_id = 0
    used_seeds = set()
    for kx in range(41):
        for ky in range(kx, 41):
            for U_value, V_value in SETS:
                task_id += 1
                if kx == 0 and ky == 0:
                    seed = PILOT_SEEDS[(U_value, V_value)]
                else:
                    seed = 230_000_000 + task_id
                if seed in used_seeds:
                    raise RuntimeError(f"Duplicate seed: {seed}")
                used_seeds.add(seed)
                U = label(U_value)
                V = label(V_value)
                filename = f"L4x4Nup8Ndn8U{U}V{V}tp0f{kx}x{ky}Q0x0_E0D.dat"
                template_name = (
                    f"job_e0d_{task_id:06d}_U{slug(U_value)}_V{slug(V_value)}_"
                    f"f{kx}x{ky}.sh"
                )
                row = {
                    "task_id": task_id,
                    "U": U,
                    "V": V,
                    "kx": kx,
                    "ky": ky,
                    "Qx": 0,
                    "Qy": 0,
                    "tp": 0,
                    "seed": seed,
                    "result_filename": filename,
                    "template_filename": template_name,
                }
                rows.append(row)
                path = template_dir / template_name
                path.write_text(template_text(root, row))
                path.chmod(0o755)

    if task_id != 6 * 861:
        raise RuntimeError(f"Expected 5166 tasks, generated {task_id}")
    manifest = manifest_dir / "targets.tsv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} targets and templates under {root}")
    print(f"Unique Lanczos seed records: {len(used_seeds)}")


if __name__ == "__main__":
    main()
