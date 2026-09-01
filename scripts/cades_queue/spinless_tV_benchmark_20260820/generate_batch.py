#!/usr/bin/env python3
"""Generate the isolated spinless 16-MMHK t-V benchmark batch."""

import argparse
import csv
from pathlib import Path


V_VALUES = [0.45, 1.0, 2.0]
ROOT_DEFAULT = Path(
    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
    "spinless_tV_benchmark_20260820"
)


def label(value):
    return f"{value:g}"


def slug(value):
    return label(value).replace("-", "m").replace(".", "p")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    return parser.parse_args()


def template_text(root: Path, bundle: dict) -> str:
    return f"""#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -J SLTVE0
#SBATCH --mem=8G
#SBATCH -t 2:00:00
#SBATCH -o {root}/logs/%x-%j.out
#SBATCH -e {root}/logs/%x-%j.err

set -uo pipefail
ROOT={root}
TARGETS="$ROOT/{bundle['target_list']}"
cd "$ROOT/results"
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}

failed=0
while IFS=$'\t' read -r task_id V kx ky seed result_filename; do
    [[ "$task_id" == "task_id" ]] && continue
    result="$ROOT/results/$result_filename"
    if [[ -s "$result" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "$result" && grep -Eq '^max_iterations[[:space:]]+10000$' "$result"; then
        echo "SLTVE0_RESULT ALREADY_COMPLETE task=$task_id V=$V kx=$kx ky=$ky"
        continue
    fi

    rm -f "$result"
    set +e
    time "$ROOT/bin/Spinless_tV_sym_E0.x" 8 "$kx" "$ky" 0 0 "$V" 0 "$seed"
    job_rc=$?
    set -e
    if (( job_rc == 0 )) && [[ -s "$result" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "$result" && grep -Eq '^max_iterations[[:space:]]+10000$' "$result"; then
        echo "SLTVE0_RESULT COMPLETE task=$task_id V=$V kx=$kx ky=$ky seed=$seed"
    else
        echo "SLTVE0_RESULT FAILED rc=$job_rc task=$task_id V=$V kx=$kx ky=$ky seed=$seed" >&2
        failed=1
    fi
done < "$TARGETS"

bash "$ROOT/scripts/submit_next_spinless.sh" "${{SLURM_JOB_ACCOUNT:-ccsd}}" || true
exit "$failed"
"""


def main():
    args = parse_args()
    root = args.root
    manifest_dir = root / "manifests"
    bundle_list_dir = manifest_dir / "bundle_targets"
    template_dir = root / "templates"
    submitted_dir = root / "submitted"
    for directory in [
        manifest_dir,
        bundle_list_dir,
        template_dir,
        submitted_dir,
        root / "logs",
        root / "results",
        root / "state",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    for old in template_dir.glob("job_sltv_*.sh"):
        old.unlink()
    for old in bundle_list_dir.glob("bundle_sltv_*.tsv"):
        old.unlink()

    targets = []
    bundles = []
    used_seeds = set()
    task_id = 0
    bundle_id = 0
    for V_value in V_VALUES:
        for kx in range(41):
            bundle_id += 1
            bundle_targets = []
            for ky in range(kx, 41):
                task_id += 1
                seed = 250_000_000 + task_id
                if seed in used_seeds:
                    raise RuntimeError(f"Duplicate seed: {seed}")
                used_seeds.add(seed)
                V = label(V_value)
                result_filename = (
                    f"L4x4N8V{V}tp0f{kx}x{ky}Q0x0_E0_spinless.dat"
                )
                row = {
                    "task_id": task_id,
                    "V": V,
                    "kx": kx,
                    "ky": ky,
                    "seed": seed,
                    "result_filename": result_filename,
                }
                targets.append(row)
                bundle_targets.append(row)

            target_list = (
                Path("manifests/bundle_targets")
                / f"bundle_sltv_{bundle_id:03d}_V{slug(V_value)}_kx{kx}.tsv"
            )
            target_path = root / target_list
            with target_path.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=list(bundle_targets[0]), delimiter="\t"
                )
                writer.writeheader()
                writer.writerows(bundle_targets)

            template_filename = (
                f"job_sltv_{bundle_id:03d}_V{slug(V_value)}_kx{kx}.sh"
            )
            bundle = {
                "bundle_id": bundle_id,
                "V": label(V_value),
                "kx": kx,
                "target_count": len(bundle_targets),
                "target_list": str(target_list),
                "template_filename": template_filename,
            }
            bundles.append(bundle)
            template_path = template_dir / template_filename
            template_path.write_text(template_text(root, bundle))
            template_path.chmod(0o755)

    if task_id != 3 * 861:
        raise RuntimeError(f"Expected 2583 targets, generated {task_id}")
    if bundle_id != 3 * 41:
        raise RuntimeError(f"Expected 123 bundles, generated {bundle_id}")

    for filename, rows in [("targets.tsv", targets), ("bundles.tsv", bundles)]:
        with (manifest_dir / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    print(f"Generated {len(targets)} targets in {len(bundles)} bundle templates under {root}")
    print(f"Unique Lanczos seeds: {len(used_seeds)}")


if __name__ == "__main__":
    main()
