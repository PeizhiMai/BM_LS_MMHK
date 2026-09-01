#!/usr/bin/env python3
"""Independent deep audit for the frozen Fig. 4 U80,V20 P25 add-on."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def refuse(message: str) -> None:
    raise SystemExit(f"REFUSAL: {message}")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} SNAPSHOT OUTPUT_JSON")
    root = Path(sys.argv[1]).expanduser().resolve()
    output = Path(sys.argv[2]).expanduser().resolve()
    ledger = root / "SNAPSHOT_SHA256SUMS"
    if output.exists():
        refuse("output already exists")
    if not root.is_dir() or root.is_symlink() or not ledger.is_file():
        refuse("snapshot/ledger missing or linked")

    expected: dict[str, str] = {}
    for line in ledger.read_text().splitlines():
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            refuse("malformed ledger")
        if len(digest) != 64 or relative in expected or relative == ledger.name:
            refuse("unsafe/duplicate ledger row")
        expected[relative] = digest
    actual: set[str] = set()
    immutable = True
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            info = (Path(current) / name).lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                refuse("linked/special directory")
            if info.st_mode & 0o222:
                immutable = False
        for name in files:
            path = Path(current) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                refuse("linked/special file")
            if info.st_nlink != 1 or info.st_mode & 0o222:
                immutable = False
            relative = path.relative_to(root).as_posix()
            if relative != ledger.name:
                actual.add(relative)
    if actual != set(expected):
        refuse("ledger inventory mismatch")
    for relative, digest in expected.items():
        if sha256(root / relative) != digest:
            refuse(f"hash mismatch: {relative}")
    if not immutable:
        refuse("snapshot is not read-only/nlink-one")

    provenance = json.loads((root / "metadata/provenance.json").read_text())
    canonical_audit = json.loads(
        (root / "metadata/canonical__analysis__latest_monitor.json").read_text()
    )
    replica_audit = json.loads((root / "metadata/replica_monitor.json").read_text())
    if provenance.get("schema") != "fig4_cnn_u80v20_p25_replica_resolved_v1":
        refuse("wrong provenance schema")
    inventory = provenance.get("inventory", {})
    if inventory != {
        "logical_rows": 25,
        "cases": 1,
        "twists_per_case": 25,
        "canonical_rows": 24,
        "selected_replica_rows": 1,
        "replica_crosscheck_rows": 5,
    }:
        refuse("wrong provenance inventory")
    selection = provenance.get("selection_policy", {})
    required_selection = {
        "same_target_duplicates_averaged": False,
        "selected_job_id": 5621087,
        "selected_seed": 436887014,
        "selected_replica_index": 1,
        "selected_replica_ordinal": 4,
        "canonical_result_still_absent": True,
    }
    if any(selection.get(key) != value for key, value in required_selection.items()):
        refuse("wrong provenance selection")
    if canonical_audit.get("counts") != {"COMPLETE": 24, "FAILED": 1}:
        refuse("wrong canonical audit counts")
    if canonical_audit.get("batch_active_queue_counts") != {}:
        refuse("canonical activity remains")
    if any(canonical_audit.get("anomalies", {}).values()):
        refuse("canonical audit anomaly")
    if not all(row.get("match") for row in canonical_audit.get("pin_audit", [])):
        refuse("canonical pin failure")
    failed = [row for row in canonical_audit["targets"] if row["status"] == "FAILED"]
    if len(failed) != 1 or (failed[0]["kx"], failed[0]["ky"]) != ("17", "17"):
        refuse("wrong canonical missing target")
    if failed[0]["result_exists"] or failed[0]["active_job_ids"]:
        refuse("canonical result/activity unexpectedly exists")
    if replica_audit.get("counts") != {"COMPLETE": 5}:
        refuse("wrong replica counts")
    if replica_audit.get("anomalies") or replica_audit.get("unmapped_terminal_activity"):
        refuse("replica audit anomaly")
    if not all(row.get("match") for row in replica_audit.get("pins", [])):
        refuse("replica pin failure")
    if not all(
        row.get("effective_seed_proof")
        and not row.get("validation_errors")
        and row.get("status") == "COMPLETE"
        for row in replica_audit.get("details", [])
    ):
        refuse("replica validation/effective-seed proof failed")

    with (root / "analysis/u80v20_raw_validation.csv").open(newline="") as handle:
        raw = list(csv.DictReader(handle))
    with (root / "analysis/u80v20_summary.csv").open(newline="") as handle:
        summary_rows = list(csv.DictReader(handle))
    with (root / "analysis/u80v20_replica_seed_crosscheck.csv").open(
        newline=""
    ) as handle:
        cross = list(csv.DictReader(handle))
    if len(raw) != 25 or len(summary_rows) != 1 or len(cross) != 5:
        refuse("analysis cardinality mismatch")
    if len({(int(row["kx"]), int(row["ky"])) for row in raw}) != 25:
        refuse("duplicate/missing twist")
    selected = [row for row in raw if row["source_role"].startswith("selected_")]
    if (
        len(selected) != 1
        or (int(selected[0]["kx"]), int(selected[0]["ky"])) != (17, 17)
        or int(selected[0]["source_job_id"]) != 5621087
        or int(selected[0]["seed"]) != 436887014
    ):
        refuse("raw selection mismatch")
    values = [float(row["C1_NN"]) for row in raw]
    if not all(math.isfinite(value) and -0.75000001 <= value <= 0.25000001 for value in values):
        refuse("C_NN bounds/finite check failed")
    max_identity = max(float(row["max_abs_identity_residual"]) for row in raw)
    if max_identity > 1.0e-8:
        refuse("identity bound failed")
    mean = sum(values) / len(values)
    summary = summary_rows[0]
    checks = {
        "C_NN": mean,
        "C_NN_min": min(values),
        "C_NN_max": max(values),
        "C_NN_spread": max(values) - min(values),
    }
    for key, expected_value in checks.items():
        if not math.isclose(float(summary[key]), expected_value, abs_tol=5e-13):
            refuse(f"summary mismatch: {key}")
    replica_values = [float(row["C1_NN"]) for row in cross]
    if max(replica_values) - min(replica_values) > 1.0e-10:
        refuse("replica agreement failed")

    report = {
        "schema": "fig4_cnn_u80v20_p25_replica_resolved_deep_audit_v1",
        "status": "PASS",
        "snapshot": str(root),
        "snapshot_ledger_sha256": sha256(ledger),
        "logical_rows": 25,
        "cases": 1,
        "twists_per_case": 25,
        "canonical_rows": 24,
        "selected_replica_rows": 1,
        "selected_job_id": 5621087,
        "selected_seed": 436887014,
        "selected_replica_ordinal": 4,
        "canonical_result_still_absent": True,
        "all_files_read_only_regular_nonlink_nlink1": True,
        "max_abs_identity_residual": max_identity,
        "identity_tolerance": 1.0e-8,
        "C_NN": mean,
        "C_NN_min": min(values),
        "C_NN_max": max(values),
        "C_NN_spread": max(values) - min(values),
        "five_replica_C_NN_spread": max(replica_values) - min(replica_values),
        "duplicate_replicas_averaged": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    output.chmod(0o444)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
