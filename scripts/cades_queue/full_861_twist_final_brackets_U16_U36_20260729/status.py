#!/usr/bin/env python3
import csv
import re
from collections import defaultdict
from pathlib import Path

BATCH = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/full_861_twist_final_brackets_U16_U36_20260729")
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
