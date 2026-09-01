#!/usr/bin/python3.11
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import os
import subprocess

BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
BATCH_NAME = "fullobs_25twist_u80v20_fig4_cnn_20260822_213314"
BATCH = BASE / "fig4_cnn" / BATCH_NAME
JOB = {"F4C80V20", "F4C80V20R"}
TW = [
    (3, 3), (7, 7), (2, 8), (10, 12), (1, 14),
    (6, 16), (17, 17), (9, 21), (1, 23), (15, 23),
    (20, 25), (25, 25), (6, 26), (12, 29), (17, 29),
    (22, 30), (27, 30), (4, 32), (19, 34), (34, 34),
    (28, 35), (10, 36), (4, 38), (38, 38), (33, 39),
]
SEEDS = {
    1481495364, 4240726229, 1633247478, 2304763714, 3877106370,
    2186540020, 4064600374, 3510575585, 231736040, 1463730226,
    2971012082, 1657316320, 2475833735, 2085068886, 2869733746,
    1859494341, 377139798, 720272907, 2895380408, 3733044548,
    699240660, 3706483231, 2872312446, 1469605930, 1367453518,
}
NAMES = {
    f"L4x4Nup8Ndn8U80V20tp0f{kx}x{ky}Q0x0_obs.dat" for kx, ky in TW
}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


solver = BASE / "Hubbard_sym_testobs_UV.x"
source = BASE / "Hubbard_sym_testobs_UV.cc"
lib = Path("/home/9pm/installs/lib/libqbasis.so")
pins = {
    str(path): {"sha256": sha(path), "mtime_ns": path.stat().st_mtime_ns}
    for path in (solver, source, lib)
}

paths = (
    set(BASE.glob("*.tsv"))
    | set(BASE.glob("*/*.tsv"))
    | set(BASE.glob("*/*/*.tsv"))
)
seed_files = []
seed_rows = 0
seed_hits = []
needle_hits = []
parse_errors = []
needles = sorted(NAMES | JOB | {BATCH_NAME})
for path in sorted(paths):
    try:
        text = path.read_text(errors="replace")
        for needle in needles:
            if needle in text:
                needle_hits.append({"path": str(path), "needle": needle})
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not reader.fieldnames or "seed" not in reader.fieldnames:
                continue
            count = 0
            for line, row in enumerate(reader, 2):
                value = (row.get("seed") or "").strip()
                if not value:
                    continue
                try:
                    value = int(value)
                except ValueError:
                    parse_errors.append(
                        {"path": str(path), "line": line, "value": value}
                    )
                    continue
                count += 1
                seed_rows += 1
                if value in SEEDS:
                    seed_hits.append(
                        {"path": str(path), "line": line, "seed": value}
                    )
            seed_files.append({"path": str(path), "rows": count})
    except Exception as exc:
        parse_errors.append({"path": str(path), "error": repr(exc)})

outputs = []
for name in sorted(NAMES):
    path = BASE / name
    outputs.append(
        {
            "name": name,
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else None,
            "install_tmps": [str(item) for item in BASE.glob(name + ".install.*")],
            "fig4_locks": [
                str(item)
                for item in (BASE / "fig4_cnn").glob("*/locks/" + name + ".lock")
            ],
        }
    )

user = os.environ.get("USER", "9pm")
squeue = subprocess.run(
    ["squeue", "-h", "-u", user, "-o", "%i|%j|%T|%a|%P|%M|%R"],
    capture_output=True,
    text=True,
    check=True,
)
active = []
for line in squeue.stdout.splitlines():
    fields = line.split("|")
    if len(fields) == 7:
        active.append(
            dict(
                zip(
                    [
                        "job_id", "job_name", "state", "account",
                        "partition", "elapsed", "reason",
                    ],
                    fields,
                )
            )
        )
counts = {}
for row in active:
    key = row["account"] + "|" + row["state"]
    counts[key] = counts.get(key, 0) + 1
related = [
    row
    for row in active
    if row["job_name"] in JOB or "U80V20" in row["job_name"]
]

sacct = subprocess.run(
    [
        "sacct", "-n", "-X", "-S", "2026-01-01", "-u", user,
        "--name=F4C80V20,F4C80V20R",
        "-o", "JobIDRaw,JobName,State,Account,Partition,Elapsed,Submit", "-P",
    ],
    capture_output=True,
    text=True,
)
history = [line for line in sacct.stdout.splitlines() if line.strip()]

collision_free = (
    not BATCH.exists()
    and all(
        not item["exists"]
        and not item["install_tmps"]
        and not item["fig4_locks"]
        for item in outputs
    )
    and not seed_hits
    and not needle_hits
    and not parse_errors
    and not related
    and not history
)

result = {
    "schema": "fig4_cnn_u80v20_p25_readonly_preflight_v1",
    "audited_at": datetime.now().astimezone().isoformat(),
    "hostname": os.uname().nodename,
    "proposal": {
        "batch": str(BATCH),
        "batch_exists": BATCH.exists(),
        "job_names": sorted(JOB),
        "target_count": 25,
        "expected_phase": "boundary",
        "seeds": len(SEEDS),
    },
    "pins": pins,
    "source_not_newer_than_solver": (
        source.stat().st_mtime_ns <= solver.stat().st_mtime_ns
    ),
    "target_paths": {
        "all_absent": all(not item["exists"] for item in outputs),
        "existing": [item for item in outputs if item["exists"]],
        "install_tmps": [item for item in outputs if item["install_tmps"]],
        "locks": [item for item in outputs if item["fig4_locks"]],
    },
    "global_tsv_audit": {
        "tsv_files_considered": len(paths),
        "seed_files": len(seed_files),
        "seed_rows": seed_rows,
        "proposed_unique_seeds": len(SEEDS),
        "seed_hits": seed_hits,
        "needle_hits": needle_hits,
        "parse_errors": parse_errors,
    },
    "scheduler": {
        "squeue_rc": squeue.returncode,
        "active_elements": len(active),
        "account_state_counts": counts,
        "related_active": related,
        "sacct_rc": sacct.returncode,
        "sacct_stderr": sacct.stderr.strip(),
        "exact_name_history_since_2026_01_01": history,
    },
    "collision_free": collision_free,
    "remote_mutations": 0,
    "sbatch_calls": 0,
}
print(json.dumps(result, indent=2, sort_keys=True))
