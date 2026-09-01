#!/usr/bin/env python3
"""Report completeness of the isolated zero-temperature E0/D CADES batch."""

import csv
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(
    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
    "literature_benchmarks_20260819"
)


def complete(path):
    if not path.is_file() or path.stat().st_size == 0:
        return False
    text = path.read_text(errors="replace")
    return "status\tCOMPLETE" in text and "max_iterations\t10000" in text


def main():
    with (ROOT / "manifests/targets.tsv").open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    by_set = defaultdict(list)
    missing = []
    for row in rows:
        by_set[(row["U"], row["V"])].append(row)
        if not complete(ROOT / "results" / row["result_filename"]):
            missing.append(row)
    print("U\tV\tcomplete\ttotal")
    for key, group in by_set.items():
        count = sum(complete(ROOT / "results" / row["result_filename"]) for row in group)
        print(f"{key[0]}\t{key[1]}\t{count}\t{len(group)}")
    print(f"TOTAL\t\t{len(rows)-len(missing)}\t{len(rows)}")
    print(f"templates_remaining\t{len(list((ROOT/'templates').glob('job_e0d_*.sh')))}")
    queue = subprocess.run(
        ["squeue", "-h", "-u", "9pm", "-n", "E0DZT", "-o", "%a|%T"],
        check=False,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.splitlines()
    counts = Counter(queue)
    for key in sorted(counts):
        print(f"queue\t{key}\t{counts[key]}")
    missing_path = ROOT / "state/missing_targets.tsv"
    with missing_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(missing)
    print(f"missing_manifest\t{missing_path}")


if __name__ == "__main__":
    main()
