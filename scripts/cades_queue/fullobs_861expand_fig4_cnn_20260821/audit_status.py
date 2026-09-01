#!/usr/bin/env python3
"""Read-only status audit for a manifest-driven CADES fullobs batch.

The monitor deliberately never calls ``sbatch``, ``scancel``, or changes a
result, template, or submission ledger.  It combines three independent views:

1. the target manifest and each target's canonical result file;
2. the batch submission ledger(s), which associate Slurm job IDs with targets;
3. live ``squeue`` and historical ``sacct`` records.

By default the report is printed only.  ``--write-report`` is the sole option
that writes a file, and it writes only the requested JSON report path.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import hashlib
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


COMPLETE_RE = re.compile(r"(?m)^status[\t ]+COMPLETE[\t ]*$")
JOB_ID_RE = re.compile(r"(?<![0-9])([0-9]{4,}(?:_[0-9]+)?)(?![0-9])")
SUBMITTED_JOB_RE = re.compile(r"Submitted batch job[\t ]+([0-9]+(?:_[0-9]+)?)")
RESULT_ASSIGN_RE = re.compile(
    r"(?m)^[\t ]*(?:result|RESULT|output|OUTPUT)[\t ]*=[\t ]*(['\"])(.*?)\1[\t ]*$"
)
ACTIVE_STATES = {
    "PENDING",
    "RUNNING",
    "CONFIGURING",
    "COMPLETING",
    "RESIZING",
    "SUSPENDED",
}
RUNNING_STATES = {"RUNNING", "CONFIGURING", "COMPLETING", "RESIZING"}
FAILURE_STATES = {
    "BOOT_FAIL",
    "CANCELLED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "REVOKED",
    "SPECIAL_EXIT",
    "TIMEOUT",
}


@dataclass(frozen=True)
class Submission:
    job_id: str
    account: str
    script: str
    result: str
    source: str


def command(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def normalize_state(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value.split("+", 1)[0].split()[0].upper()


def canonical(path: str | Path, base: Path) -> str:
    candidate = Path(str(path))
    if not candidate.is_absolute():
        candidate = base / candidate
    return str(candidate.resolve(strict=False))


def locate_manifest(batch: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else batch / path
    candidates = (
        batch / "manifest.tsv",
        batch / "manifests" / "targets.tsv",
        batch / "targets.tsv",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "No manifest found (tried {}).".format(
            ", ".join(str(path) for path in candidates)
        )
    )


def load_manifest(batch: Path, manifest: Path) -> list[dict[str, str]]:
    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError(f"Manifest has no targets: {manifest}")

    result_fields = ("result", "result_path", "output", "output_path", "result_filename")
    for index, row in enumerate(rows, 1):
        result_field = next((key for key in result_fields if row.get(key)), None)
        if result_field is None:
            raise ValueError(
                f"Manifest row {index} has none of these result fields: {result_fields}"
            )
        raw_result = row[result_field]
        if result_field == "result_filename":
            result = batch / "results" / raw_result
        else:
            result = Path(raw_result)
            if not result.is_absolute():
                result = batch / result
        row["_result"] = str(result.resolve(strict=False))
        row["_row_number"] = str(index)

        template = ""
        for field in ("template", "template_path", "script", "submission_script"):
            if row.get(field):
                template = canonical(row[field], batch)
                break
        row["_template"] = template
        row["_key"] = target_key(row)
    return rows


def target_key(row: dict[str, str]) -> str:
    explicit = row.get("target_id") or row.get("target_key")
    if explicit:
        return explicit
    parts = []
    for field in ("U", "V", "kx", "ky"):
        if row.get(field, "") != "":
            parts.append(f"{field}={row[field]}")
    return ",".join(parts) if parts else Path(row.get("_result", "target")).name


def numeric_close(actual: float, expected: float, tolerance: float = 1.0e-10) -> bool:
    return abs(actual - expected) <= tolerance * max(1.0, abs(expected))


def result_health(path_string: str, row: dict[str, str]) -> dict[str, object]:
    path = Path(path_string)
    health: dict[str, object] = {
        "exists": False,
        "size_bytes": 0,
        "complete": False,
        "complete_marker": False,
        "mtime": None,
        "validation_errors": [],
        "identity_residuals": {},
    }
    try:
        if not path.is_file():
            return health
        stat = path.stat()
        text = path.read_text(errors="replace")
        complete_marker = bool(COMPLETE_RE.search(text))
        validation_errors: list[str] = []
        identity_residuals: dict[str, float] = {}
        values: dict[str, str] = {}
        for line in text.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                values[parts[0]] = parts[1].strip()

        if complete_marker:
            required = (
                "Lx",
                "Ly",
                "tp",
                "U",
                "V",
                "E0",
                "<nn_NN>",
                "<delta_n_delta_n_NN>",
                "<Kinetic_NN_per_site>",
                "<Kinetic_NNN_per_site>",
                "<Kinetic_per_site>",
                "<C1_NN>",
                "Q",
                "<ni_upni_dn>",
                "<Sc_pipi>",
                "<mCDW2_pipi>",
            )
            missing = [key for key in required if key not in values]
            if missing:
                validation_errors.append("missing_keys=" + ",".join(missing))
            else:
                try:
                    numeric_keys = [key for key in required if key != "Q"]
                    observed = {key: float(values[key]) for key in numeric_keys}
                    nonfinite = [key for key, value in observed.items() if not math.isfinite(value)]
                    if nonfinite:
                        validation_errors.append("nonfinite=" + ",".join(nonfinite))
                    expected_u = float(row.get("U", observed["U"]))
                    expected_v = float(row.get("V", observed["V"]))
                    metadata_checks = {
                        "Lx": (observed["Lx"], 4.0),
                        "Ly": (observed["Ly"], 4.0),
                        "tp": (observed["tp"], 0.0),
                        "U": (observed["U"], expected_u),
                        "V": (observed["V"], expected_v),
                    }
                    for key, (actual, expected) in metadata_checks.items():
                        if not numeric_close(actual, expected):
                            validation_errors.append(
                                f"metadata_{key}={actual:.17g}_expected={expected:.17g}"
                            )
                    if values["Q"].replace(" ", "") != "0,0":
                        validation_errors.append(f"metadata_Q={values['Q']!r}_expected='0,0'")

                    energy_reconstructed = (
                        observed["<Kinetic_per_site>"]
                        + observed["U"] * observed["<ni_upni_dn>"]
                        + 2.0 * observed["V"] * observed["<nn_NN>"]
                    )
                    identity_residuals = {
                        "energy_per_site": observed["E0"] / 16.0 - energy_reconstructed,
                        "connected_density": observed["<delta_n_delta_n_NN>"]
                        - (observed["<nn_NN>"] - 1.0),
                        "kinetic_sum": observed["<Kinetic_per_site>"]
                        - (
                            observed["<Kinetic_NN_per_site>"]
                            + observed["<Kinetic_NNN_per_site>"]
                        ),
                        "charge_Sc_over_N": observed["<mCDW2_pipi>"]
                        - observed["<Sc_pipi>"] / 16.0,
                    }
                    for key, residual in identity_residuals.items():
                        if not math.isfinite(residual) or abs(residual) > 1.0e-8:
                            validation_errors.append(f"identity_{key}={residual:.6e}")

                    c_nn = observed["<C1_NN>"]
                    if not (-0.75000001 <= c_nn <= 0.25000001):
                        validation_errors.append(f"C1_NN_out_of_bounds={c_nn:.17g}")
                    d_site = observed["<ni_upni_dn>"]
                    if row.get("expected_phase") == "Mott" and not d_site < 0.25:
                        validation_errors.append(f"phase_not_Mott_D_site={d_site:.17g}")
                except (TypeError, ValueError, OverflowError) as exc:
                    validation_errors.append(f"numeric_parse={exc}")
        health.update(
            {
                "exists": True,
                "size_bytes": stat.st_size,
                "complete_marker": complete_marker,
                "complete": bool(complete_marker and not validation_errors),
                "mtime": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                "validation_errors": validation_errors,
                "identity_residuals": identity_residuals,
            }
        )
    except OSError as exc:
        health["read_error"] = str(exc)
    return health


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_pin_files(batch: Path, explicit: Iterable[str]) -> list[Path]:
    candidates = [Path(item) if Path(item).is_absolute() else batch / item for item in explicit]
    candidates.extend(
        [
            batch / "PINNED_SHA256SUMS",
            batch / "provenance" / "PINNED_SHA256SUMS",
            batch / "provenance" / "pinned_sha256sums.txt",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve(strict=False))
        if key not in seen and path.is_file():
            seen.add(key)
            unique.append(path)
    return unique


def audit_pins(pin_files: Iterable[Path]) -> tuple[list[dict[str, object]], list[str]]:
    """Validate conventional sha256sum files without invoking mutable tooling."""
    audits: list[dict[str, object]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    line_re = re.compile(r"^([0-9a-fA-F]{64})[\t ]+[* ]?(.*?)\s*$")
    for pin_file in pin_files:
        for line_number, line in enumerate(pin_file.read_text(errors="replace").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = line_re.match(line)
            if not match:
                warnings.append(f"Unparsed pin line {pin_file}:{line_number}")
                continue
            expected = match.group(1).lower()
            raw_path = match.group(2)
            path = Path(raw_path)
            if not path.is_absolute():
                path = pin_file.parent / path
            path = path.resolve(strict=False)
            key = (expected, str(path))
            if key in seen:
                continue
            seen.add(key)
            exists = path.is_file()
            actual = sha256(path) if exists else ""
            audits.append(
                {
                    "pin_file": str(pin_file),
                    "path": str(path),
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "exists": exists,
                    "match": bool(exists and actual == expected),
                }
            )
    return audits, warnings


def script_result(script: Path, batch: Path) -> str:
    try:
        text = script.read_text(errors="replace")
    except OSError:
        return ""
    match = RESULT_ASSIGN_RE.search(text)
    if not match:
        return ""
    value = match.group(2)
    # Submission scripts in this project normally carry an absolute path.  Do
    # not attempt shell expansion: an unresolved '$' path is not trustworthy.
    if "$" in value or "`" in value:
        return ""
    return canonical(value, batch)


def candidate_submission_files(batch: Path, explicit: Iterable[str]) -> list[Path]:
    candidates = [Path(item) if Path(item).is_absolute() else batch / item for item in explicit]
    candidates.extend(
        [
            batch / "submission.tsv",
            batch / "submissions.tsv",
            batch / "logs" / "submissions.tsv",
            batch / "state" / "submissions.tsv",
            # Keep the legacy free-form log last.  A headered ledger is the
            # authoritative association when both contain the same job.
            batch / "logs" / "submit.log",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve(strict=False))
        if key not in seen and path.is_file():
            seen.add(key)
            unique.append(path)
    return unique


def parse_submission_files(batch: Path, paths: Iterable[Path]) -> tuple[list[Submission], list[str]]:
    submissions: list[Submission] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        text = path.read_text(errors="replace")
        lines = text.splitlines()

        # New production batches use a headered TSV.  Parse the named columns
        # first: guessing a job ID from digits in a dated path is unsafe.
        header = lines[0].split("\t") if lines else []
        job_id_fields = ("job_id", "slurm_job_id", "submission_job_id")
        has_named_job_id = any(field in header for field in job_id_fields)
        if has_named_job_id:
            reader = csv.DictReader(lines, delimiter="\t")
            for row_number, row in enumerate(reader, 2):
                job_id = next(
                    (str(row.get(field, "")).strip() for field in job_id_fields if row.get(field)),
                    "",
                )
                if not job_id:
                    continue
                if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", job_id):
                    warnings.append(f"Invalid job_id {job_id!r} at {path}:{row_number}")
                    continue
                account = next(
                    (
                        str(row.get(field, "")).strip()
                        for field in ("account", "slurm_account")
                        if row.get(field)
                    ),
                    "",
                )
                script_text = next(
                    (
                        str(row.get(field, "")).strip()
                        for field in ("run_script", "submitted_script", "script", "sbatch_script")
                        if row.get(field)
                    ),
                    "",
                )
                script = Path(script_text) if script_text else None
                if script is not None and not script.is_absolute():
                    script = batch / script
                result_field = next(
                    (
                        field
                        for field in ("result", "result_path", "output", "output_path", "result_filename")
                        if row.get(field)
                    ),
                    "",
                )
                result = ""
                if result_field:
                    raw_result = str(row[result_field]).strip()
                    if result_field == "result_filename" and row.get("result_root"):
                        root = Path(str(row["result_root"]).strip())
                        result = canonical(root / raw_result, batch)
                    else:
                        result = canonical(raw_result, batch)
                if not result and script is not None:
                    result = script_result(script, batch)
                if not result:
                    warnings.append(
                        f"Could not associate job {job_id} with a target from {path}:{row_number}"
                    )
                    continue
                pair = (job_id, result)
                if pair in seen:
                    continue
                seen.add(pair)
                submissions.append(
                    Submission(
                        job_id=job_id,
                        account=account,
                        script=str(script) if script is not None else "",
                        result=result,
                        source=f"{path}:{row_number}",
                    )
                )
            continue

        # Backward-compatible parser for the older free-form submit.log files.
        for line_number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            submitted_match = SUBMITTED_JOB_RE.search(line)
            generic_matches = JOB_ID_RE.findall(line)
            job_id = submitted_match.group(1) if submitted_match else (generic_matches[-1] if generic_matches else "")
            if not job_id:
                # Permit a header line without warning.
                if line_number == 1 and "job" in line.lower():
                    continue
                continue
            fields = [field.strip() for field in line.split("\t")]
            account = next((field for field in fields if field in {"ccsd", "cnms"}), "")
            script_text = next((field for field in fields if field.endswith((".sh", ".sbatch"))), "")
            result_text = next(
                (
                    field
                    for field in fields
                    if field.endswith((".dat", ".txt", ".out")) and not field.endswith((".sh", ".sbatch"))
                ),
                "",
            )
            script = Path(script_text) if script_text else None
            if script is not None and not script.is_absolute():
                script = batch / script
            result = canonical(result_text, batch) if result_text else ""
            if not result and script is not None:
                result = script_result(script, batch)
            if not result:
                if not any(item.job_id == job_id for item in submissions):
                    warnings.append(
                        f"Could not associate job {job_id} with a target from {path}:{line_number}"
                    )
                continue
            pair = (job_id, result)
            if pair in seen:
                continue
            seen.add(pair)
            submissions.append(
                Submission(
                    job_id=job_id,
                    account=account,
                    script=str(script) if script is not None else "",
                    result=result,
                    source=f"{path}:{line_number}",
                )
            )
    return submissions, warnings


def manifest_submissions(rows: Iterable[dict[str, str]], batch: Path) -> list[Submission]:
    found: list[Submission] = []
    for row in rows:
        job_id = row.get("job_id") or row.get("slurm_job_id") or row.get("submission_job_id")
        if not job_id:
            continue
        task_id = row.get("array_task_id") or row.get("task_id")
        if task_id and "_" not in job_id:
            job_id = f"{job_id}_{task_id}"
        found.append(
            Submission(
                job_id=job_id,
                account=row.get("account", ""),
                script=row.get("_template", ""),
                result=row["_result"],
                source=f"manifest:{row['_row_number']}",
            )
        )
    return found


def parse_pipe_records(text: str, fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        columns = [item.strip() for item in line.split("|")]
        if len(columns) < len(fields):
            continue
        record = dict(zip(fields, columns))
        job_id = record.pop("job_id", "")
        if job_id:
            record["state"] = normalize_state(record.get("state", ""))
            records[job_id] = record
    return records


def slurm_views(
    user: str,
    since: str,
    squeue_file: str | None,
    sacct_file: str | None,
    no_slurm: bool,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[str]]:
    errors: list[str] = []
    if no_slurm:
        return {}, {}, errors

    if squeue_file:
        queue_text = Path(squeue_file).read_text(errors="replace")
    else:
        rc, queue_text, stderr = command(
            [
                "squeue",
                "-h",
                "-r",
                "-u",
                user,
                "-o",
                "%i|%j|%a|%T|%P|%C|%D|%m|%M|%l|%R",
            ]
        )
        if rc:
            errors.append(f"squeue failed ({rc}): {stderr.strip()}")
    queue = parse_pipe_records(
        queue_text,
        (
            "job_id",
            "job_name",
            "account",
            "state",
            "partition",
            "cpus",
            "nodes",
            "memory",
            "elapsed",
            "time_limit",
            "reason",
        ),
    )

    if sacct_file:
        accounting_text = Path(sacct_file).read_text(errors="replace")
    else:
        rc, accounting_text, stderr = command(
            [
                "sacct",
                "-X",
                "-n",
                "-P",
                "-u",
                user,
                "-S",
                since,
                "-o",
                "JobIDRaw,JobName%40,Account%20,State%30,Elapsed,ExitCode",
            ]
        )
        if rc:
            errors.append(f"sacct failed ({rc}): {stderr.strip()}")
    accounting = parse_pipe_records(
        accounting_text,
        ("job_id", "job_name", "account", "state", "elapsed", "exit_code"),
    )
    return queue, accounting, errors


def matching_job_records(
    job_id: str,
    records: dict[str, dict[str, str]],
) -> list[tuple[str, dict[str, str]]]:
    if job_id in records:
        return [(job_id, records[job_id])]
    # If a ledger contains an array parent, include its materialized elements.
    prefix = job_id + "_"
    return [(key, value) for key, value in records.items() if key.startswith(prefix)]


def latest_job_id(job_ids: Iterable[str]) -> str:
    def order(value: str) -> tuple[int, int]:
        base, _, task = value.partition("_")
        return (int(base) if base.isdigit() else -1, int(task) if task.isdigit() else -1)

    return max(job_ids, key=order, default="")


def build_report(
    batch: Path,
    manifest: Path,
    rows: list[dict[str, str]],
    submissions: list[Submission],
    queue: dict[str, dict[str, str]],
    accounting: dict[str, dict[str, str]],
    scheduler_errors: list[str],
    warnings: list[str],
    job_names: set[str],
    pin_audits: list[dict[str, object]],
    pins_required: bool,
    expected_targets: int | None,
    expected_per_case: int | None,
    expected_accounts: set[str],
    expected_partition: str | None,
    expected_cpus: int | None,
    expected_nodes: int | None,
    expected_memory: str | None,
    expected_time_limit: str | None,
) -> dict[str, object]:
    by_result_submissions: dict[str, list[Submission]] = defaultdict(list)
    for submission in submissions:
        by_result_submissions[submission.result].append(submission)

    duplicate_manifest_results = [
        result for result, count in Counter(row["_result"] for row in rows).items() if count > 1
    ]
    duplicate_manifest_seeds = [
        seed
        for seed, count in Counter(row.get("seed", "") for row in rows).items()
        if seed and count > 1
    ]
    manifest_job_name_mismatches = [
        row["_key"]
        for row in rows
        if job_names and row.get("job_name") and row.get("job_name") not in job_names
    ]
    result_name_re = re.compile(
        r"^L4x4Nup8Ndn8U([^/]+?)V([^/]+?)tp0f([0-9]+)x([0-9]+)Q0x0_obs\.dat$"
    )
    manifest_result_name_mismatches = []
    for row in rows:
        match = result_name_re.match(Path(row["_result"]).name)
        if not match:
            manifest_result_name_mismatches.append(row["_key"])
            continue
        try:
            matches = (
                numeric_close(float(match.group(1)), float(row.get("U", match.group(1))))
                and numeric_close(float(match.group(2)), float(row.get("V", match.group(2))))
                and int(match.group(3)) == int(row.get("kx", match.group(3)))
                and int(match.group(4)) == int(row.get("ky", match.group(4)))
            )
        except ValueError:
            matches = False
        if not matches:
            manifest_result_name_mismatches.append(row["_key"])
    targets: list[dict[str, object]] = []
    active_to_results: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        result = row["_result"]
        health = result_health(result, row)
        target_submissions = by_result_submissions.get(result, [])

        active_records: dict[str, dict[str, str]] = {}
        accounting_records: dict[str, dict[str, str]] = {}
        for submission in target_submissions:
            for job_id, record in matching_job_records(submission.job_id, queue):
                if record.get("state") in ACTIVE_STATES:
                    active_records[job_id] = record
                    active_to_results[job_id].add(result)
            for job_id, record in matching_job_records(submission.job_id, accounting):
                accounting_records[job_id] = record

        if health["complete"]:
            status = "COMPLETE"
        elif health["complete_marker"]:
            status = "INVALID"
        elif active_records:
            status = (
                "RUNNING"
                if any(record.get("state") in RUNNING_STATES for record in active_records.values())
                else "PENDING"
            )
        elif accounting_records:
            latest = latest_job_id(accounting_records)
            terminal_state = accounting_records[latest].get("state", "")
            if terminal_state in FAILURE_STATES or terminal_state == "COMPLETED":
                status = "FAILED"
            else:
                status = "UNKNOWN"
        elif health["exists"]:
            status = "INCOMPLETE"
        elif row.get("_template") and Path(row["_template"]).is_file():
            status = "UNSUBMITTED"
        elif target_submissions:
            status = "UNKNOWN"
        else:
            status = "MISSING"

        active_ids = sorted(active_records, key=lambda item: tuple(int(x) for x in item.split("_")))
        latest_terminal_id = latest_job_id(accounting_records)
        latest_terminal = accounting_records.get(latest_terminal_id, {})
        duplicate_active = len(active_ids) > 1
        complete_with_active = bool(health["complete"] and active_ids)
        repair_eligible = bool(
            status in {"FAILED", "INCOMPLETE"}
            and not scheduler_errors
            and not active_ids
            and not health["complete"]
        )
        targets.append(
            {
                "key": row["_key"],
                "U": row.get("U", ""),
                "V": row.get("V", ""),
                "kx": row.get("kx", ""),
                "ky": row.get("ky", ""),
                "result": result,
                "status": status,
                "result_exists": health["exists"],
                "result_complete": health["complete"],
                "result_complete_marker": health["complete_marker"],
                "result_size_bytes": health["size_bytes"],
                "result_mtime": health["mtime"],
                "validation_errors": health["validation_errors"],
                "identity_residuals": health["identity_residuals"],
                "active_job_ids": active_ids,
                "active_states": {job_id: active_records[job_id].get("state", "") for job_id in active_ids},
                "submission_job_ids": sorted({item.job_id for item in target_submissions}),
                "latest_terminal_job_id": latest_terminal_id,
                "latest_terminal_state": latest_terminal.get("state", ""),
                "latest_exit_code": latest_terminal.get("exit_code", ""),
                "template": row.get("_template", ""),
                "duplicate_active": duplicate_active,
                "complete_with_active": complete_with_active,
                "repair_eligible": repair_eligible,
            }
        )

    status_counts = Counter(str(item["status"]) for item in targets)
    by_case: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for target in targets:
        by_case[(str(target["U"]), str(target["V"]))][str(target["status"])] += 1

    known_active_ids = {job_id for target in targets for job_id in target["active_job_ids"]}
    matching_queue_ids = {
        job_id
        for job_id, record in queue.items()
        if not job_names or record.get("job_name") in job_names
    }
    unmapped_active = sorted(matching_queue_ids - known_active_ids)
    ambiguous_active = {
        job_id: sorted(results)
        for job_id, results in active_to_results.items()
        if len(results) > 1
    }
    anomalies = {
        "duplicate_manifest_results": sorted(duplicate_manifest_results),
        "duplicate_manifest_seeds": sorted(duplicate_manifest_seeds),
        "manifest_job_name_mismatches": manifest_job_name_mismatches,
        "manifest_result_name_mismatches": manifest_result_name_mismatches,
        "targets_with_multiple_active_jobs": [
            target["key"] for target in targets if target["duplicate_active"]
        ],
        "complete_targets_with_active_jobs": [
            target["key"] for target in targets if target["complete_with_active"]
        ],
        "active_jobs_mapped_to_multiple_targets": ambiguous_active,
        "unmapped_active_matching_jobs": unmapped_active,
        "pin_hash_failures": [
            audit["path"] for audit in pin_audits if not audit["match"]
        ],
        "required_pins_missing": bool(pins_required and not pin_audits),
        "invalid_complete_outputs": [
            target["key"] for target in targets if target["status"] == "INVALID"
        ],
        "expected_target_count_mismatch": bool(
            expected_targets is not None and len(rows) != expected_targets
        ),
        "expected_per_case_mismatches": [
            f"U={case[0]},V={case[1]}:{sum(counts.values())}"
            for case, counts in sorted(by_case.items())
            if expected_per_case is not None and sum(counts.values()) != expected_per_case
        ],
    }

    batch_queue = {
        job_id: record
        for job_id, record in queue.items()
        if not job_names or record.get("job_name") in job_names
    }
    resource_mismatches: list[str] = []
    for job_id, record in sorted(batch_queue.items()):
        checks: list[tuple[str, str, object | None]] = [
            ("partition", record.get("partition", ""), expected_partition),
            ("cpus", record.get("cpus", ""), expected_cpus),
            ("nodes", record.get("nodes", ""), expected_nodes),
            ("memory", record.get("memory", ""), expected_memory),
            ("time_limit", record.get("time_limit", ""), expected_time_limit),
        ]
        if expected_accounts and record.get("account") not in expected_accounts:
            resource_mismatches.append(
                f"{job_id}:account={record.get('account','')}:expected={','.join(sorted(expected_accounts))}"
            )
        for field, actual, expected in checks:
            if expected is None:
                continue
            if field in {"cpus", "nodes"}:
                matches = str(actual).isdigit() and int(str(actual)) == int(expected)
            elif field == "time_limit":
                matches = str(actual).lstrip("0") == str(expected).lstrip("0")
            else:
                matches = str(actual) == str(expected)
            if not matches:
                resource_mismatches.append(f"{job_id}:{field}={actual}:expected={expected}")
    anomalies["active_resource_mismatches"] = resource_mismatches

    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "read_only": True,
        "batch": str(batch),
        "manifest": str(manifest),
        "total_targets": len(targets),
        "counts": dict(sorted(status_counts.items())),
        "batch_active_queue_counts": dict(
            sorted(Counter(record.get("state", "") for record in batch_queue.values()).items())
        ),
        "cases": [
            {
                "U": case[0],
                "V": case[1],
                "total": sum(counts.values()),
                "counts": dict(sorted(counts.items())),
            }
            for case, counts in sorted(by_case.items(), key=lambda item: item[0])
        ],
        "repair_candidates": [target["key"] for target in targets if target["repair_eligible"]],
        "anomalies": anomalies,
        "scheduler_errors": scheduler_errors,
        "warnings": warnings,
        "pin_audit": pin_audits,
        "targets": targets,
    }


def print_human(report: dict[str, object]) -> None:
    counts = report["counts"]
    count_text = " ".join(f"{key}={value}" for key, value in counts.items()) or "none"
    print(f"FULLobs audit {report['generated_at']}")
    print(f"BATCH {report['batch']}")
    print(f"TARGETS {report['total_targets']} | {count_text}")
    for case in report["cases"]:
        case_counts = " ".join(f"{key}={value}" for key, value in case["counts"].items())
        print(f"U={case['U']} V={case['V']}: {case_counts}")

    anomalies = report["anomalies"]
    anomaly_count = sum(
        len(value) if isinstance(value, (list, dict)) else int(bool(value))
        for value in anomalies.values()
    )
    print(f"ANOMALIES {anomaly_count}")
    for key, value in anomalies.items():
        if value:
            print(f"  {key}: {json.dumps(value, sort_keys=True)}")
    print(f"REPAIR_CANDIDATES {len(report['repair_candidates'])}")
    if report["repair_candidates"]:
        print("  " + "; ".join(report["repair_candidates"]))
    if report["pin_audit"]:
        print(
            "PINS {}/{} MATCH".format(
                sum(bool(item["match"]) for item in report["pin_audit"]),
                len(report["pin_audit"]),
            )
        )
    for error in report["scheduler_errors"]:
        print(f"SCHEDULER_ERROR {error}", file=sys.stderr)
    for warning in report["warnings"]:
        print(f"WARNING {warning}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="Remote batch root")
    parser.add_argument("--manifest", help="Manifest path, absolute or relative to --batch")
    parser.add_argument(
        "--submission-log",
        action="append",
        default=[],
        help="Additional submission ledger, absolute or relative to --batch (repeatable)",
    )
    parser.add_argument(
        "--job-name",
        action="append",
        default=[],
        help="Exact Slurm job name used to flag active jobs missing from the ledger",
    )
    parser.add_argument(
        "--pin-file",
        action="append",
        default=[],
        help="sha256sum-format pin file, absolute or relative to --batch (repeatable)",
    )
    parser.add_argument(
        "--require-pins",
        action="store_true",
        help="Flag an anomaly if no readable checksum entries are found",
    )
    parser.add_argument("--expect-targets", type=int, help="Expected manifest row count")
    parser.add_argument("--expect-per-case", type=int, help="Expected target count for each (U,V)")
    parser.add_argument("--expect-account", action="append", default=[], help="Allowed active-job account")
    parser.add_argument("--expect-partition", help="Expected active-job partition")
    parser.add_argument("--expect-cpus", type=int, help="Expected total CPUs per active job")
    parser.add_argument("--expect-nodes", type=int, help="Expected nodes per active job")
    parser.add_argument("--expect-memory", help="Expected squeue minimum-memory field, e.g. 100G")
    parser.add_argument("--expect-time-limit", help="Expected squeue time-limit field")
    parser.add_argument("--user", default=os.environ.get("USER", "9pm"))
    parser.add_argument(
        "--since",
        default=(dt.date.today() - dt.timedelta(days=7)).isoformat(),
        help="sacct start date (YYYY-MM-DD; default: seven days ago)",
    )
    parser.add_argument("--no-slurm", action="store_true", help="Inspect files only")
    parser.add_argument("--squeue-file", help="Use captured pipe-delimited squeue output")
    parser.add_argument("--sacct-file", help="Use captured pipe-delimited sacct output")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the concise report")
    parser.add_argument(
        "--write-report",
        help="Explicitly write the full JSON report here (the only write operation)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 for anomalies/failures/missing targets; 3 for scheduler errors",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = Path(args.batch).resolve(strict=False)
    try:
        manifest = locate_manifest(batch, args.manifest).resolve(strict=False)
        rows = load_manifest(batch, manifest)
        ledger_paths = candidate_submission_files(batch, args.submission_log)
        ledger_submissions, warnings = parse_submission_files(batch, ledger_paths)
        submissions = manifest_submissions(rows, batch) + ledger_submissions
        # Deduplicate identical associations assembled from more than one ledger.
        submissions = list(
            {
                (item.job_id, item.result): item
                for item in submissions
            }.values()
        )
        queue, accounting, scheduler_errors = slurm_views(
            args.user,
            args.since,
            args.squeue_file,
            args.sacct_file,
            args.no_slurm,
        )
        pin_files = locate_pin_files(batch, args.pin_file)
        pin_audits, pin_warnings = audit_pins(pin_files)
        warnings.extend(pin_warnings)
        report = build_report(
            batch,
            manifest,
            rows,
            submissions,
            queue,
            accounting,
            scheduler_errors,
            warnings,
            set(args.job_name),
            pin_audits,
            args.require_pins,
            args.expect_targets,
            args.expect_per_case,
            set(args.expect_account),
            args.expect_partition,
            args.expect_cpus,
            args.expect_nodes,
            args.expect_memory,
            args.expect_time_limit,
        )
    except Exception as exc:  # concise fatal error for unattended heartbeat use
        print(f"FATAL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        destination = Path(args.write_report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(str(destination) + ".tmp")
        temporary.write_text(rendered)
        os.replace(temporary, destination)
    if args.json:
        print(rendered, end="")
    else:
        print_human(report)

    if report["scheduler_errors"]:
        return 3 if args.strict else 0
    if args.strict:
        anomaly_count = sum(
            len(value) if isinstance(value, (list, dict)) else int(bool(value))
            for value in report["anomalies"].values()
        )
        bad = sum(
            int(report["counts"].get(status, 0))
            for status in ("FAILED", "INCOMPLETE", "INVALID", "MISSING", "UNKNOWN")
        )
        if anomaly_count or bad:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
