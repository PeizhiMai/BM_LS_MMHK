#!/usr/bin/env python3
"""Report completeness of the isolated spinless t-V benchmark batch."""

import csv
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(
    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
    "spinless_tV_benchmark_20260820"
)


def complete(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    text = path.read_text(errors="replace")
    return (
        "status\tCOMPLETE" in text
        and "max_iterations\t10000" in text
        and "N\t8" in text
    )


def main():
    with (ROOT / "manifests/targets.tsv").open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    by_v = defaultdict(list)
    missing = []
    for row in rows:
        by_v[row["V"]].append(row)
        if not complete(ROOT / "results" / row["result_filename"]):
            missing.append(row)

    print("V\tcomplete\ttotal")
    for V, group in by_v.items():
        count = sum(
            complete(ROOT / "results" / row["result_filename"]) for row in group
        )
        print(f"{V}\t{count}\t{len(group)}")
    print(f"TOTAL\t{len(rows)-len(missing)}\t{len(rows)}")
    print(
        "templates_remaining\t"
        f"{len(list((ROOT / 'templates').glob('job_sltv_*.sh')))}"
    )

    queue = subprocess.run(
        ["squeue", "-h", "-u", "9pm", "-n", "SLTVE0", "-o", "%a|%T"],
        check=False,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.splitlines()
    for key, count in sorted(Counter(queue).items()):
        print(f"queue\t{key}\t{count}")

    missing_path = ROOT / "state/missing_targets.tsv"
    with missing_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(missing)
    print(f"missing_manifest\t{missing_path}")


if __name__ == "__main__":
    main()
