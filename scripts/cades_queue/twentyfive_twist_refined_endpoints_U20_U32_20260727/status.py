#!/usr/bin/env python3
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
