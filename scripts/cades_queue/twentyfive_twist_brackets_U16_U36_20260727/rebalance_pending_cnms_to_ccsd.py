#!/usr/bin/env python3
"""Move half of pending OBS25T cnms jobs to ccsd without touching running jobs."""

from __future__ import print_function

import argparse
import csv
import fcntl
import os
from pathlib import Path
import re
import subprocess
import time


BATCH = Path(
    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/"
    "twentyfive_twist_brackets_U16_U36_20260727"
)
SUBMIT_LOG = BATCH / "logs" / "submit.log"
IGNORE_FILE = BATCH / "auto_repair" / "ignored_normal_job_ids.txt"
LOCK_FILE = BATCH / ".queue.lock"
MANIFEST = BATCH / "manifest.tsv"
JOB_ID_RE = re.compile(r"Submitted batch job\s+(\d+)")
RESULT_RE = re.compile(r"^result='([^']+)'$", re.M)
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")


def run(command, check=False):
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            "{} failed ({}): {}".format(
                " ".join(command), process.returncode, process.stderr.strip()
            )
        )
    return process


def complete(path):
    path = Path(path)
    return path.is_file() and bool(
        COMPLETE_RE.search(path.read_text(errors="ignore"))
    )


def queue():
    process = run(
        ["squeue", "-u", os.environ["USER"], "-h", "-o", "%i|%j|%a|%T"],
        check=True,
    )
    records = {}
    for line in process.stdout.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 4:
            records[parts[0]] = {
                "job_name": parts[1],
                "account": parts[2],
                "state": parts[3],
            }
    return records


def submissions():
    records = {}
    if not SUBMIT_LOG.is_file():
        return records
    for line in SUBMIT_LOG.read_text().splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        timestamp, account, script, message = parts
        match = JOB_ID_RE.search(message)
        if not match:
            continue
        script_path = Path(script)
        if not script_path.is_file():
            continue
        script_text = script_path.read_text()
        result_match = RESULT_RE.search(script_text)
        if not result_match:
            continue
        records[match.group(1)] = {
            "timestamp": timestamp,
            "account": account,
            "script": script_path,
            "result": result_match.group(1),
        }
    return records


def append_submission(account, script, message):
    with SUBMIT_LOG.open("a") as handle:
        handle.write(
            "{}\t{}\t{}\t{}\n".format(
                time.strftime("%Y-%m-%d %H:%M:%S"),
                account,
                script,
                message,
            )
        )


parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()

with MANIFEST.open() as handle:
    manifest_rows = list(csv.DictReader(handle, delimiter="\t"))
row_by_result = {row["result"]: row for row in manifest_rows}

with LOCK_FILE.open("w") as lock_handle:
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    active = queue()
    submitted = submissions()
    candidates = []
    for job_id, state in active.items():
        if (
            state["job_name"] != "OBS25T"
            or state["account"] != "cnms"
            or state["state"] != "PENDING"
            or job_id not in submitted
        ):
            continue
        submission = submitted[job_id]
        row = row_by_result.get(submission["result"])
        if row is None or complete(submission["result"]):
            continue
        candidates.append(
            {
                "old_job_id": job_id,
                "submission": submission,
                "row": row,
            }
        )

    groups = {}
    for candidate in candidates:
        row = candidate["row"]
        groups.setdefault((int(row["U"]), float(row["V"])), []).append(candidate)

    selected = []
    for key in sorted(groups):
        group = sorted(
            groups[key],
            key=lambda item: (
                int(item["row"]["ky"]),
                int(item["row"]["kx"]),
                int(item["old_job_id"]),
            ),
        )
        # Alternating entries gives ceil(n/2), spread across each endpoint.
        selected.extend(group[::2])

    print(
        "Pending OBS25T on cnms: {}; selected for ccsd: {}".format(
            len(candidates), len(selected)
        )
    )
    for item in selected:
        row = item["row"]
        print(
            "{old_job_id} U={U} V={V} f{kx}x{ky}".format(
                old_job_id=item["old_job_id"], **row
            )
        )

    if not args.apply:
        raise SystemExit(0)

    ignored = set()
    if IGNORE_FILE.is_file():
        ignored.update(
            line.strip()
            for line in IGNORE_FILE.read_text().splitlines()
            if line.strip()
        )
    ignored.update(item["old_job_id"] for item in selected)
    temporary_ignore = Path(str(IGNORE_FILE) + ".tmp")
    temporary_ignore.write_text("\n".join(sorted(ignored, key=int)) + "\n")
    os.replace(str(temporary_ignore), str(IGNORE_FILE))

    timestamp_tag = time.strftime("%Y%m%dT%H%M%S")
    audit_path = BATCH / "logs" / (
        "rebalance_cnms_to_ccsd_{}.tsv".format(timestamp_tag)
    )
    audit_fields = [
        "time",
        "U",
        "V",
        "kx",
        "ky",
        "result",
        "source_account",
        "destination_account",
        "old_job_id",
        "new_job_id",
        "old_script",
        "new_script",
        "status",
    ]
    audit_rows = []

    for item in selected:
        old_job_id = item["old_job_id"]
        row = item["row"]
        old_script = item["submission"]["script"]

        current = queue().get(old_job_id)
        if not current or current != {
            "job_name": "OBS25T",
            "account": "cnms",
            "state": "PENDING",
        }:
            audit_rows.append(
                {
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "U": row["U"],
                    "V": row["V"],
                    "kx": row["kx"],
                    "ky": row["ky"],
                    "result": row["result"],
                    "source_account": "cnms",
                    "destination_account": "ccsd",
                    "old_job_id": old_job_id,
                    "new_job_id": "",
                    "old_script": old_script,
                    "new_script": "",
                    "status": "skipped_not_pending",
                }
            )
            continue

        run(["scancel", old_job_id], check=True)
        new_script = old_script.with_name(
            old_script.stem.replace("_cnms", "")
            + "_ccsd_rebalance_{}.sh".format(timestamp_tag)
        )
        text = old_script.read_text()
        text, replacements = re.subn(
            r"(?m)^#SBATCH -A cnms$", "#SBATCH -A ccsd", text
        )
        if replacements != 1:
            raise RuntimeError(
                "Expected one account directive in {}".format(old_script)
            )
        new_script.write_text(text)
        new_script.chmod(0o755)
        submission = run(["sbatch", str(new_script)])
        match = JOB_ID_RE.search(submission.stdout)
        if submission.returncode == 0 and match:
            new_job_id = match.group(1)
            append_submission("ccsd", new_script, submission.stdout.strip())
            status = "moved"
        else:
            # Restore the target to cnms if the requested ccsd submission fails.
            fallback = run(["sbatch", str(old_script)], check=True)
            fallback_match = JOB_ID_RE.search(fallback.stdout)
            if not fallback_match:
                raise RuntimeError("Fallback submission returned no job id.")
            new_job_id = fallback_match.group(1)
            append_submission("cnms", old_script, fallback.stdout.strip())
            status = "ccsd_failed_restored_cnms"

        audit_rows.append(
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "U": row["U"],
                "V": row["V"],
                "kx": row["kx"],
                "ky": row["ky"],
                "result": row["result"],
                "source_account": "cnms",
                "destination_account": "ccsd",
                "old_job_id": old_job_id,
                "new_job_id": new_job_id,
                "old_script": old_script,
                "new_script": new_script,
                "status": status,
            }
        )

    with audit_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=audit_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(audit_rows)

    moved = sum(row["status"] == "moved" for row in audit_rows)
    skipped = sum(row["status"] == "skipped_not_pending" for row in audit_rows)
    restored = sum(
        row["status"] == "ccsd_failed_restored_cnms" for row in audit_rows
    )
    print(
        "Moved {}; skipped {}; restored to cnms {}; audit={}".format(
            moved, skipped, restored, audit_path
        )
    )
