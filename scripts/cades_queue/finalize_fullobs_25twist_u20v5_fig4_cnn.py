#!/Users/cosdis/.venvs/myenv/bin/python
"""Safely finalize the exact Fig. 4 C_NN fullobs campaign.

The script is deliberately add-only.  It will not create a staging directory,
download a byte, or run the analysis unless two conditions are both true:

1. the deep remote audit reports exactly 25/25 valid COMPLETE targets with
   no matching Slurm activity, anomalies, scheduler errors, or repair cases;
2. the fixed, dated local snapshot path and its staging path do not exist.

After the gate passes, it downloads only a hash-pinned list of canonical
COMPLETE results and provenance files into a new staging directory, repeats
the remote audit and inventory, validates all hashes and observables locally,
generates the C_NN analysis tables, writes a snapshot-wide checksum ledger,
makes the tree read-only, and atomically renames it into place.

There is intentionally no overwrite or force option.
"""

from __future__ import annotations

import argparse
import ctypes
import csv
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import stat
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[2]
MONITOR = SCRIPT.with_name("monitor_fullobs_batch.py")

REMOTE_HOST_DEFAULT = "cades"
REMOTE_USER = "9pm"
REMOTE_BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
REMOTE_BATCH = REMOTE_BASE / "fig4_cnn" / "fullobs_25twist_u20v5_fig4_cnn_20260821"
SNAPSHOT_NAME = "fullobs_25twist_u20v5_fig4_cnn_20260821"
SNAPSHOT_ROOT_DEFAULT = REPO / "data" / "fullobs"

EXPECTED_TARGETS = 25
EXPECTED_PER_CASE = 25
EXPECTED_MANIFEST_SHA256 = (
    "05d8ee7c0aef76beb1b86b82b4780a9e85fcce9df0c4b8da023d3b84f545943e"
)
EXPECTED_PROVENANCE_SHA256 = (
    "ccf109a50ad2bf6d4f0abd2b1c0c2c0723354971c71b6fcdfd8815488484a51e"
)
EXPECTED_TWIST_PANEL_SHA256 = (
    "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
)
EXPECTED_PIN_SHA256 = {
    "Hubbard_sym_testobs_UV.x": (
        "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
    ),
    "Hubbard_sym_testobs_UV.cc": (
        "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
    ),
    "libqbasis.so": (
        "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
    ),
}
EXPECTED_JOB_NAMES = ("F4C20V5", "F4C20V5R")
EXPECTED_ACCOUNTS = ("ccsd",)
EXPECTED_PARTITION = "burst"
EXPECTED_CPUS = 32
EXPECTED_NODES = 1
EXPECTED_MEMORY = "100G"
EXPECTED_TIME_LIMIT = "08:00:00"
SACCT_SINCE = "2026-08-21"
IDENTITY_TOLERANCE = 1.0e-8

TWISTS = (
    (3, 3),
    (7, 7),
    (2, 8),
    (10, 12),
    (1, 14),
    (6, 16),
    (17, 17),
    (9, 21),
    (1, 23),
    (15, 23),
    (20, 25),
    (25, 25),
    (6, 26),
    (12, 29),
    (17, 29),
    (22, 30),
    (27, 30),
    (4, 32),
    (19, 34),
    (34, 34),
    (28, 35),
    (10, 36),
    (4, 38),
    (38, 38),
    (33, 39),
)

COMPLETE_RE = re.compile(r"(?m)^status[\t ]+COMPLETE[\t ]*$")
SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SNAPSHOT_INSTALL_LOCK = ".fullobs_25twist_u20v5_fig4_cnn_20260821.install.lock"

REMOTE_INVENTORY_PROGRAM = r"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

batch = Path(sys.argv[1]).resolve()
base = Path(sys.argv[2]).resolve()
complete_re = re.compile(r"(?m)^status[\t ]+COMPLETE[\t ]*$")

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

manifest = batch / "manifest.tsv"
with manifest.open(newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))
if len(rows) != 25:
    raise SystemExit("manifest target count is {}, expected 25".format(len(rows)))
if len({row["index"] for row in rows}) != 25:
    raise SystemExit("manifest indices are not unique")
if len({row["seed"] for row in rows}) != 25:
    raise SystemExit("manifest seeds are not unique")

results = []
seen_names = set()
for row in rows:
    path = Path(row["result"]).resolve()
    if path.parent != base:
        raise SystemExit("result escapes canonical base: {}".format(path))
    if path.name in seen_names:
        raise SystemExit("duplicate result name: {}".format(path.name))
    seen_names.add(path.name)
    if not path.is_file():
        raise SystemExit("missing result: {}".format(path))
    text = path.read_text(errors="replace")
    if not complete_re.search(text):
        raise SystemExit("result lacks standalone COMPLETE: {}".format(path))
    st = path.stat()
    results.append({
        "index": int(row["index"]),
        "U": row["U"],
        "V": row["V"],
        "kx": int(row["kx"]),
        "ky": int(row["ky"]),
        "filename": path.name,
        "path": str(path),
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": sha256(path),
    })

submission = batch / "submission.tsv"
with submission.open(newline="") as f:
    submitted = list(csv.DictReader(f, delimiter="\t"))
if len(submitted) < 25:
    raise SystemExit("submission ledger has {} rows, expected at least 25".format(len(submitted)))
manifest_indices = {row["index"] for row in rows}
submitted_indices = {row["index"] for row in submitted}
if submitted_indices != manifest_indices:
    raise SystemExit("submission ledger does not cover exactly the 25 manifest indices")
if len({row["job_id"] for row in submitted}) != len(submitted):
    raise SystemExit("submission ledger job IDs are not unique")
manifest_by_index = {row["index"]: row for row in rows}
for record in submitted:
    expected = manifest_by_index[record["index"]]
    if record["account"] not in {"ccsd"}:
        raise SystemExit("unsupported submission account: {}".format(record["account"]))
    if not record["job_id"].isdigit():
        raise SystemExit("nonnumeric submission job ID: {}".format(record["job_id"]))
    for field in ("U", "V", "kx", "ky", "result"):
        if record[field] != expected[field]:
            raise SystemExit(
                "submission/manifest mismatch index={} field={}: {} != {}".format(
                    record["index"], field, record[field], expected[field]
                )
            )

fixed_metadata = [
    "manifest.tsv",
    "twist_panel.tsv",
    "provenance.json",
    "PINNED_SHA256SUMS",
    "README.md",
    "submission.tsv",
    "setup_generator.py",
    "analyze.py",
    "audit_status.py",
    "preflight.py",
    "dry_run_submit.py",
    "status.py",
    "submit_fill.sh",
    "submit_next.sh",
    "pinned_solver/Hubbard_sym_testobs_UV.x",
    "pinned_solver/Hubbard_sym_testobs_UV.cc",
    "pinned_solver/libqbasis.so",
]
optional_metadata = [
    "repair_submission.tsv",
    "logs/submit.log",
    "analysis/fig4_cnn_25twist_observables.csv",
    "analysis/fig4_cnn_25twist_summary.csv",
]
metadata_paths = []
for rel in fixed_metadata:
    path = batch / rel
    if not path.is_file():
        raise SystemExit("missing required metadata: {}".format(path))
    metadata_paths.append(path)
for rel in optional_metadata:
    path = batch / rel
    if path.is_file():
        metadata_paths.append(path)
submitted_dir = batch / "submitted"
if submitted_dir.is_dir():
    metadata_paths.extend(sorted(p for p in submitted_dir.iterdir() if p.is_file()))

metadata = []
seen_rel = set()
for path in metadata_paths:
    path = path.resolve()
    try:
        rel = path.relative_to(batch).as_posix()
    except ValueError:
        raise SystemExit("metadata escapes batch: {}".format(path))
    if rel in seen_rel:
        continue
    seen_rel.add(rel)
    st = path.stat()
    metadata.append({
        "relative_path": rel,
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": sha256(path),
    })

payload = {
    "schema_version": 1,
    "batch": str(batch),
    "base": str(base),
    "manifest_sha256": sha256(manifest),
    "provenance_sha256": sha256(batch / "provenance.json"),
    "twist_panel_sha256": sha256(batch / "twist_panel.tsv"),
    "pin_file_sha256": sha256(batch / "PINNED_SHA256SUMS"),
    "target_count": len(results),
    "submission_count": len(submitted),
    "results": sorted(results, key=lambda item: item["index"]),
    "metadata": sorted(metadata, key=lambda item: item["relative_path"]),
}
print(json.dumps(payload, indent=2, sort_keys=True))
"""


class Refusal(RuntimeError):
    """Expected safe refusal; reported with exit status 2."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes_sha256(payload: Any) -> str:
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary):
        raise Refusal(f"Refusing to replace pre-existing temporary file: {temporary}")
    temporary.write_text(text)
    os.replace(temporary, path)


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(
            "Command failed ({}): {}\nstdout:\n{}\nstderr:\n{}".format(
                proc.returncode,
                " ".join(shlex.quote(item) for item in command),
                proc.stdout[-6000:],
                proc.stderr[-6000:],
            )
        )
    return proc


def remote_python(
    host: str, program: str, arguments: Iterable[str], timeout: int
) -> str:
    remote_command = " ".join(
        shlex.quote(item) for item in ("/usr/bin/python3.11", "-", *tuple(arguments))
    )
    return run(
        ["ssh", host, remote_command], input_text=program, timeout=timeout
    ).stdout


def monitor_arguments(
    batch: Path, *, json_output: bool = True, no_slurm: bool = False
) -> list[str]:
    args = [
        "--batch",
        str(batch),
        "--job-name",
        EXPECTED_JOB_NAMES[0],
        "--job-name",
        EXPECTED_JOB_NAMES[1],
        "--pin-file",
        "PINNED_SHA256SUMS",
        "--require-pins",
        "--submission-log",
        "repair_submission.tsv",
        "--since",
        SACCT_SINCE,
        "--expect-targets",
        str(EXPECTED_TARGETS),
        "--expect-per-case",
        str(EXPECTED_PER_CASE),
        "--expect-partition",
        EXPECTED_PARTITION,
        "--expect-cpus",
        str(EXPECTED_CPUS),
        "--expect-nodes",
        str(EXPECTED_NODES),
        "--expect-memory",
        EXPECTED_MEMORY,
        "--expect-time-limit",
        EXPECTED_TIME_LIMIT,
    ]
    for account in EXPECTED_ACCOUNTS:
        args.extend(("--expect-account", account))
    if json_output:
        args.append("--json")
    if no_slurm:
        args.append("--no-slurm")
    return args


def remote_audit(host: str, monitor_source: str) -> dict[str, Any]:
    output = remote_python(
        host,
        monitor_source,
        monitor_arguments(REMOTE_BATCH),
        timeout=180,
    )
    try:
        report = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Remote monitor returned invalid JSON: {exc}\n{output[-4000:]}"
        ) from exc
    if Path(str(report.get("batch", ""))) != REMOTE_BATCH:
        raise Refusal(f"Remote audit reported the wrong batch: {report.get('batch')!r}")
    return report


def anomaly_items(report: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for key, value in report.get("anomalies", {}).items():
        if isinstance(value, (list, dict)):
            if value:
                bad.append(f"{key}={len(value)}")
        elif value:
            bad.append(f"{key}={value!r}")
    return bad


def gate_report(report: dict[str, Any], label: str) -> None:
    reasons: list[str] = []
    if report.get("total_targets") != EXPECTED_TARGETS:
        reasons.append(f"total_targets={report.get('total_targets')!r}")
    counts = report.get("counts", {})
    if counts != {"COMPLETE": EXPECTED_TARGETS}:
        reasons.append(f"counts={json.dumps(counts, sort_keys=True)}")
    active = report.get("batch_active_queue_counts", {})
    if active:
        reasons.append(f"active={json.dumps(active, sort_keys=True)}")
    anomalies = anomaly_items(report)
    if anomalies:
        reasons.append("anomalies=" + ",".join(anomalies))
    if report.get("scheduler_errors"):
        reasons.append(f"scheduler_errors={len(report['scheduler_errors'])}")
    if report.get("warnings"):
        reasons.append(f"warnings={len(report['warnings'])}")
    if report.get("repair_candidates"):
        reasons.append(f"repair_candidates={len(report['repair_candidates'])}")
    if report.get("read_only") is not True:
        reasons.append("audit_not_marked_read_only")
    pin_audit = report.get("pin_audit", [])
    if len(pin_audit) != 3 or not all(item.get("match") for item in pin_audit):
        reasons.append(
            "pins={}/{}".format(
                sum(bool(item.get("match")) for item in pin_audit), len(pin_audit)
            )
        )
    if reasons:
        raise Refusal(f"{label} gate refused finalization: " + "; ".join(reasons))


def remote_inventory(host: str) -> dict[str, Any]:
    output = remote_python(
        host,
        REMOTE_INVENTORY_PROGRAM,
        (str(REMOTE_BATCH), str(REMOTE_BASE)),
        timeout=300,
    )
    try:
        inventory = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Remote inventory returned invalid JSON: {exc}") from exc
    if inventory.get("target_count") != EXPECTED_TARGETS:
        raise Refusal(
            f"Remote inventory target count is {inventory.get('target_count')!r}"
        )
    if int(inventory.get("submission_count", 0)) < EXPECTED_TARGETS:
        raise Refusal(
            f"Remote submission count is {inventory.get('submission_count')!r}, expected at least 25"
        )
    if len(inventory.get("results", [])) != EXPECTED_TARGETS:
        raise Refusal("Remote inventory does not contain exactly 25 results")
    require_source_hashes(inventory, "remote inventory")
    validate_inventory_contract(inventory)
    return inventory


def require_manifest_hash(actual: str, label: str) -> None:
    if actual != EXPECTED_MANIFEST_SHA256:
        raise Refusal(
            f"{label} manifest SHA-256 mismatch: "
            f"actual={actual!r}, expected={EXPECTED_MANIFEST_SHA256}"
        )


def expected_pin_file_text() -> str:
    return "".join(
        f"{digest}  pinned_solver/{name}\n"
        for name, digest in EXPECTED_PIN_SHA256.items()
    )


def require_source_hashes(source: dict[str, Any], label: str) -> None:
    require_manifest_hash(str(source.get("manifest_sha256", "")), label)
    expected = {
        "provenance_sha256": EXPECTED_PROVENANCE_SHA256,
        "twist_panel_sha256": EXPECTED_TWIST_PANEL_SHA256,
        "pin_file_sha256": hashlib.sha256(
            expected_pin_file_text().encode()
        ).hexdigest(),
    }
    for field, digest in expected.items():
        actual = str(source.get(field, ""))
        if actual != digest:
            raise Refusal(
                f"{label} {field.replace('_', ' ')} mismatch: "
                f"actual={actual!r}, expected={digest}"
            )


def expected_raw_name(kx: int, ky: int) -> str:
    return f"L4x4Nup8Ndn8U20V5tp0f{kx}x{ky}Q0x0_obs.dat"


def validate_inventory_contract(inventory: dict[str, Any]) -> None:
    """Independently bind remote inventory JSON to the reviewed 25 targets."""
    if Path(str(inventory.get("batch", ""))) != REMOTE_BATCH:
        raise Refusal(
            f"Remote inventory reported the wrong batch: {inventory.get('batch')!r}"
        )
    if Path(str(inventory.get("base", ""))) != REMOTE_BASE:
        raise Refusal(
            f"Remote inventory reported the wrong base: {inventory.get('base')!r}"
        )

    results = inventory.get("results")
    if not isinstance(results, list) or len(results) != EXPECTED_TARGETS:
        raise Refusal("Remote inventory must contain exactly 25 result records")
    expected_names: set[str] = set()
    for expected_index, (item, (kx, ky)) in enumerate(zip(results, TWISTS), 1):
        if not isinstance(item, dict):
            raise Refusal("Remote inventory result record is not an object")
        filename = expected_raw_name(kx, ky)
        expected_names.add(filename)
        try:
            valid = (
                int(item["index"]) == expected_index
                and float(item["U"]) == 20.0
                and float(item["V"]) == 5.0
                and int(item["kx"]) == kx
                and int(item["ky"]) == ky
                and item["filename"] == filename
                and Path(str(item["path"])).parent == REMOTE_BASE
                and Path(str(item["path"])).name == filename
                and int(item["size_bytes"]) > 0
                and int(item["mtime_ns"]) > 0
                and bool(SHA256_RE.fullmatch(str(item["sha256"])))
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise Refusal(
                f"Malformed remote inventory result at index {expected_index}: {exc}"
            ) from exc
        if not valid:
            raise Refusal(
                f"Remote inventory result {expected_index} violates the exact U20,V5 panel"
            )
    if len(expected_names) != EXPECTED_TARGETS:
        raise AssertionError("Reviewed twist panel produced duplicate raw names")

    metadata = inventory.get("metadata")
    if not isinstance(metadata, list):
        raise Refusal("Remote inventory metadata is not a list")
    metadata_by_name: dict[str, dict[str, Any]] = {}
    for item in metadata:
        if not isinstance(item, dict):
            raise Refusal("Remote inventory metadata record is not an object")
        relative = Path(str(item.get("relative_path", "")))
        relative_text = relative.as_posix()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative_text in ("", ".")
            or relative_text in metadata_by_name
            or not SHA256_RE.fullmatch(str(item.get("sha256", "")))
        ):
            raise Refusal(f"Unsafe or duplicate remote metadata record: {item!r}")
        try:
            if int(item["size_bytes"]) < 0 or int(item["mtime_ns"]) <= 0:
                raise ValueError("invalid size/mtime")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise Refusal(f"Malformed remote metadata record: {item!r}") from exc
        metadata_by_name[relative_text] = item

    required_hashes = {
        "manifest.tsv": EXPECTED_MANIFEST_SHA256,
        "provenance.json": EXPECTED_PROVENANCE_SHA256,
        "twist_panel.tsv": EXPECTED_TWIST_PANEL_SHA256,
        "PINNED_SHA256SUMS": hashlib.sha256(
            expected_pin_file_text().encode()
        ).hexdigest(),
        **{
            f"pinned_solver/{name}": digest
            for name, digest in EXPECTED_PIN_SHA256.items()
        },
    }
    for relative, digest in required_hashes.items():
        record = metadata_by_name.get(relative)
        if record is None or record.get("sha256") != digest:
            raise Refusal(
                f"Remote inventory lacks exact reviewed metadata hash for {relative}"
            )


def write_lines(path: Path, values: Iterable[str]) -> None:
    values = list(values)
    for value in values:
        candidate = Path(value)
        if (
            "\n" in value
            or "\r" in value
            or candidate.is_absolute()
            or ".." in candidate.parts
        ):
            raise RuntimeError(f"Unsafe file-list entry: {value!r}")
    path.write_text("".join(value + "\n" for value in values))


def rsync_files_from(
    host: str, remote_root: Path, file_list: Path, destination: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    run(
        [
            "rsync",
            "-a",
            "--files-from=" + str(file_list),
            f"{host}:{remote_root.as_posix().rstrip('/')}/",
            str(destination) + "/",
        ],
        timeout=3600,
    )


def verify_inventory_files(
    inventory: dict[str, Any], metadata: Path, raw: Path
) -> None:
    errors: list[str] = []
    for item in inventory["results"]:
        path = raw / item["filename"]
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing result {path.name}")
            continue
        if path.stat().st_size != int(item["size_bytes"]):
            errors.append(f"size mismatch {path.name}")
        if sha256(path) != item["sha256"]:
            errors.append(f"hash mismatch {path.name}")
    for item in inventory["metadata"]:
        path = metadata / item["relative_path"]
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing metadata {item['relative_path']}")
            continue
        if path.stat().st_size != int(item["size_bytes"]):
            errors.append(f"metadata size mismatch {item['relative_path']}")
        if sha256(path) != item["sha256"]:
            errors.append(f"metadata hash mismatch {item['relative_path']}")
    if errors:
        raise RuntimeError(
            "Downloaded inventory verification failed:\n" + "\n".join(errors[:30])
        )


def validate_downloaded_campaign_metadata(metadata: Path) -> None:
    """Validate the original campaign files byte-for-byte and semantically."""
    paths = {
        "manifest_sha256": metadata / "manifest.tsv",
        "provenance_sha256": metadata / "provenance.json",
        "twist_panel_sha256": metadata / "twist_panel.tsv",
        "pin_file_sha256": metadata / "PINNED_SHA256SUMS",
    }
    for label, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise Refusal(f"Downloaded {label} is not a regular file: {path}")
    require_source_hashes(
        {label: sha256(path) for label, path in paths.items()},
        "downloaded metadata",
    )
    if paths["pin_file_sha256"].read_text() != expected_pin_file_text():
        raise Refusal(
            "Downloaded PINNED_SHA256SUMS is not the exact reviewed declaration"
        )
    for name, digest in EXPECTED_PIN_SHA256.items():
        path = metadata / "pinned_solver" / name
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise Refusal(f"Downloaded pinned artifact fails exact hash: {name}")

    expected_manifest_fields = (
        "index",
        "U",
        "V",
        "V_over_U",
        "expected_phase",
        "twist_index",
        "kx",
        "ky",
        "seed",
        "job_name",
        "result",
        "state_at_generation",
        "template",
    )
    with paths["manifest_sha256"].open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != expected_manifest_fields:
            raise Refusal("Downloaded manifest has the wrong exact schema")
        manifest_rows = list(reader)
    if len(manifest_rows) != EXPECTED_TARGETS:
        raise Refusal(f"Downloaded manifest has {len(manifest_rows)} rows, expected 25")
    seeds: set[int] = set()
    for expected_index, (row, (kx, ky)) in enumerate(zip(manifest_rows, TWISTS), 1):
        try:
            seed = int(row["seed"])
            result = Path(row["result"])
            valid = (
                int(row["index"]) == expected_index
                and float(row["U"]) == 20.0
                and float(row["V"]) == 5.0
                and float(row["V_over_U"]) == 0.25
                and row["expected_phase"] == "Mott"
                and int(row["twist_index"]) == expected_index
                and int(row["kx"]) == kx
                and int(row["ky"]) == ky
                and row["job_name"] == EXPECTED_JOB_NAMES[0]
                and result.parent == REMOTE_BASE
                and result.name == expected_raw_name(kx, ky)
                and row["state_at_generation"] in {"template", "complete"}
                and 1 <= seed <= 0xFFFFFFFF
                and seed not in seeds
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise Refusal(
                f"Malformed downloaded manifest row {expected_index}: {exc}"
            ) from exc
        if not valid:
            raise Refusal(
                f"Downloaded manifest row {expected_index} violates the reviewed contract"
            )
        seeds.add(seed)

    with paths["twist_panel_sha256"].open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != (
            "twist_index",
            "kx",
            "ky",
            "diagonal",
            "symmetry_multiplicity",
        ):
            raise Refusal("Downloaded twist panel has the wrong exact schema")
        twist_rows = list(reader)
    if len(twist_rows) != EXPECTED_PER_CASE:
        raise Refusal("Downloaded twist panel does not contain exactly 25 rows")
    for expected_index, (row, (kx, ky)) in enumerate(zip(twist_rows, TWISTS), 1):
        expected = {
            "twist_index": str(expected_index),
            "kx": str(kx),
            "ky": str(ky),
            "diagonal": str(kx == ky),
            "symmetry_multiplicity": str(1 if kx == ky else 2),
        }
        if row != expected:
            raise Refusal(
                f"Downloaded twist-panel row {expected_index} is not reviewed"
            )

    try:
        provenance = json.loads(paths["provenance_sha256"].read_text())
    except json.JSONDecodeError as exc:
        raise Refusal("Downloaded provenance is not valid JSON") from exc
    expected_physics = {
        "Lx": 4,
        "Ly": 4,
        "Ndn": 8,
        "Nup": 8,
        "Qm": 0,
        "Qn": 0,
        "tp": 0,
    }
    expected_provenance_pins = {
        "solver_sha256": EXPECTED_PIN_SHA256["Hubbard_sym_testobs_UV.x"],
        "source_sha256": EXPECTED_PIN_SHA256["Hubbard_sym_testobs_UV.cc"],
        "qbasis_library_sha256": EXPECTED_PIN_SHA256["libqbasis.so"],
    }
    if not isinstance(provenance, dict):
        raise Refusal("Downloaded provenance is not a JSON object")
    if (
        provenance.get("batch") != str(REMOTE_BATCH)
        or provenance.get("job_name") != EXPECTED_JOB_NAMES[0]
        or provenance.get("target_count") != EXPECTED_TARGETS
        or provenance.get("physics") != expected_physics
        or provenance.get("twists") != [{"kx": kx, "ky": ky} for kx, ky in TWISTS]
        or provenance.get("pairs") != [{"U": 20, "V": "5", "V_over_U": 0.25}]
        or any(
            provenance.get(key) != digest
            for key, digest in expected_provenance_pins.items()
        )
    ):
        raise Refusal(
            "Downloaded provenance violates the exact U20,V5 campaign contract"
        )
    aggregation = provenance.get("aggregation")
    if not isinstance(aggregation, dict) or (
        aggregation.get("primary_C_NN_estimator")
        != "unweighted arithmetic mean over deterministic 25-twist maximin panel"
        or aggregation.get("twist_spread_is_not_standard_error") is not True
    ):
        raise Refusal("Downloaded provenance has the wrong aggregation contract")


def make_local_manifest(remote_manifest: Path, local_manifest: Path) -> None:
    with remote_manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != EXPECTED_TARGETS:
        raise RuntimeError(f"Downloaded manifest has {len(rows)} rows")
    fields = list(rows[0])
    if "remote_result" not in fields:
        fields.append("remote_result")
    if "snapshot_result" not in fields:
        fields.append("snapshot_result")
    for row in rows:
        filename = Path(row["result"]).name
        row["remote_result"] = row["result"]
        row["snapshot_result"] = f"../raw/{filename}"
        row["result"] = row["snapshot_result"]
        # The original template path is preserved by the remote manifest; the
        # local audit should never mistake a remote absolute path for a local
        # resubmission mechanism.
        row["template"] = ""
    with local_manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def local_audit(metadata: Path, monitor_path: Path) -> dict[str, Any]:
    command = [
        str(Path.home() / ".venvs" / "myenv" / "bin" / "python"),
        str(monitor_path),
        *monitor_arguments(metadata, no_slurm=True),
        "--manifest",
        "manifest_local.tsv",
    ]
    proc = run(command, timeout=300)
    report = json.loads(proc.stdout)
    gate_report(report, "local downloaded-data")
    return report


def parse_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"Could not read raw output as strict text: {path}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise RuntimeError(f"Malformed raw line {path}:{line_number}")
        key, value = parts
        if key in values:
            raise RuntimeError(f"Duplicate raw key {key!r} in {path}")
        values[key] = value.strip()
    return values


def generate_analysis(metadata: Path, raw: Path, analysis: Path) -> None:
    analysis.mkdir(parents=True, exist_ok=False)
    with (metadata / "manifest_local.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
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
        "status",
    )
    if len(rows) != EXPECTED_TARGETS:
        raise RuntimeError(f"Analysis manifest has {len(rows)} rows, expected 25")
    expected_names = {expected_raw_name(kx, ky) for kx, ky in TWISTS}
    raw_entries = list(raw.iterdir())
    if (
        len(raw_entries) != EXPECTED_TARGETS
        or any(path.is_symlink() or not path.is_file() for path in raw_entries)
        or {path.name for path in raw_entries} != expected_names
    ):
        raise RuntimeError("Raw directory is not the exact 25-file reviewed inventory")

    parsed: list[dict[str, Any]] = []
    seeds: set[int] = set()
    for expected_index, (row, (expected_kx, expected_ky)) in enumerate(
        zip(rows, TWISTS), 1
    ):
        seed = int(row["seed"])
        expected_name = expected_raw_name(expected_kx, expected_ky)
        if not (
            int(row["index"]) == expected_index
            and float(row["U"]) == 20.0
            and float(row["V"]) == 5.0
            and float(row["V_over_U"]) == 0.25
            and row["expected_phase"] == "Mott"
            and int(row["twist_index"]) == expected_index
            and int(row["kx"]) == expected_kx
            and int(row["ky"]) == expected_ky
            and row["job_name"] == EXPECTED_JOB_NAMES[0]
            and Path(row["snapshot_result"]).name == expected_name
            and Path(row["remote_result"]).parent == REMOTE_BASE
            and Path(row["remote_result"]).name == expected_name
            and 1 <= seed <= 0xFFFFFFFF
            and seed not in seeds
        ):
            raise RuntimeError(
                f"Analysis manifest row {expected_index} violates the reviewed contract"
            )
        seeds.add(seed)
        path = raw / Path(row["snapshot_result"]).name
        text = path.read_text(errors="replace")
        if not COMPLETE_RE.search(text):
            raise RuntimeError(f"Local analysis saw incomplete output: {path}")
        values = parse_values(path)
        missing = [key for key in required if key not in values]
        if missing:
            raise RuntimeError(f"Missing {missing} in {path}")
        if values["status"] != "COMPLETE":
            raise RuntimeError(f"Raw status is not exactly COMPLETE: {path}")
        numeric_keys = tuple(key for key in required if key not in {"Q", "status"})
        try:
            observed = {key: float(values[key]) for key in numeric_keys}
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError(f"Numeric parse failed in {path}: {exc}") from exc
        if not all(math.isfinite(value) for value in observed.values()):
            raise RuntimeError(f"Non-finite raw observable in {path}")
        if not (
            math.isclose(observed["Lx"], 4.0, rel_tol=0.0, abs_tol=1.0e-13)
            and math.isclose(observed["Ly"], 4.0, rel_tol=0.0, abs_tol=1.0e-13)
            and math.isclose(observed["tp"], 0.0, rel_tol=0.0, abs_tol=1.0e-13)
            and math.isclose(observed["U"], 20.0, rel_tol=0.0, abs_tol=1.0e-12)
            and math.isclose(observed["V"], 5.0, rel_tol=0.0, abs_tol=1.0e-12)
            and values["Q"] == "0,0"
        ):
            raise RuntimeError(f"Raw physics metadata mismatch: {path}")

        c_nn = observed["<C1_NN>"]
        d_site = observed["<ni_upni_dn>"]
        if not (-0.75 <= c_nn < 0.0):
            raise RuntimeError(f"Mott-side C_NN is outside [-0.75,0): {path}")
        if not (0.0 <= d_site < 0.25):
            raise RuntimeError(f"Mott-side D must be in [0,0.25): {path}")
        residuals = {
            "identity_energy_per_site_residual": observed["E0"] / 16.0
            - (
                observed["<Kinetic_per_site>"]
                + 20.0 * d_site
                + 2.0 * 5.0 * observed["<nn_NN>"]
            ),
            "identity_connected_density_residual": observed["<delta_n_delta_n_NN>"]
            - (observed["<nn_NN>"] - 1.0),
            "identity_kinetic_sum_residual": observed["<Kinetic_per_site>"]
            - (observed["<Kinetic_NN_per_site>"] + observed["<Kinetic_NNN_per_site>"]),
            "identity_charge_Sc_over_N_residual": observed["<mCDW2_pipi>"]
            - observed["<Sc_pipi>"] / 16.0,
        }
        max_identity = max(abs(value) for value in residuals.values())
        if not math.isfinite(max_identity) or max_identity > IDENTITY_TOLERANCE:
            raise RuntimeError(
                f"Four-identity tolerance exceeded in {path}: {max_identity:.3e}"
            )
        parsed.append(
            {
                "index": int(row["index"]),
                "U": int(row["U"]),
                "V": float(row["V"]),
                "V_over_U": float(row["V_over_U"]),
                "twist_index": int(row["twist_index"]),
                "kx": int(row["kx"]),
                "ky": int(row["ky"]),
                "seed": int(row["seed"]),
                "analytic_phase": "Mott",
                "E0": observed["E0"],
                "D_site": d_site,
                "mCDW2_pipi": observed["<mCDW2_pipi>"],
                "Sc_pipi": observed["<Sc_pipi>"],
                "C1_NN": c_nn,
                "nn_NN": observed["<nn_NN>"],
                "delta_n_delta_n_NN": observed["<delta_n_delta_n_NN>"],
                "kinetic_NN_per_site": observed["<Kinetic_NN_per_site>"],
                "kinetic_NNN_per_site": observed["<Kinetic_NNN_per_site>"],
                "kinetic_per_site": observed["<Kinetic_per_site>"],
                **residuals,
                "max_abs_identity_residual": max_identity,
                "status": "COMPLETE",
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "snapshot_result": f"../raw/{path.name}",
                "remote_result": row["remote_result"],
            }
        )
    if len(parsed) != EXPECTED_TARGETS:
        raise RuntimeError(f"Analysis parsed {len(parsed)} rows, expected 25")

    observables = analysis / "fig4_cnn_25twist_observables.csv"
    with observables.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(parsed[0]))
        writer.writeheader()
        writer.writerows(parsed)

    groups: dict[tuple[int, float], list[dict[str, Any]]] = defaultdict(list)
    for row in parsed:
        groups[(row["U"], row["V"])].append(row)
    if len(groups) != 1:
        raise RuntimeError(f"Analysis found {len(groups)} parameter groups, expected 1")

    summary: list[dict[str, Any]] = []
    for (U, V), group in sorted(groups.items()):
        if len(group) != EXPECTED_PER_CASE:
            raise RuntimeError(f"U={U},V={V}: {len(group)} twists, expected 25")
        c_values = [float(row["C1_NN"]) for row in group]
        weights = [1 if row["kx"] == row["ky"] else 2 for row in group]
        c_mean = statistics.fmean(c_values)
        c_sym = sum(w * value for w, value in zip(weights, c_values)) / sum(weights)
        factor = (2 * U - V) / (U - V)
        summary.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "expected_phase": "Mott",
                "complete_twists": len(group),
                "C1_NN_panel_mean": c_mean,
                "C1_NN_panel_min": min(c_values),
                "C1_NN_panel_max": max(c_values),
                "C1_NN_panel_spread": max(c_values) - min(c_values),
                "C1_NN_panel_population_std": statistics.pstdev(c_values),
                "C1_NN_symmetry_weighted_diagnostic": c_sym,
                "C1_NN_estimator_difference": c_sym - c_mean,
                "s_NN_prediction": 1 + factor * (2 * c_mean - 0.5),
                "s_NN_prediction_symmetry_weighted_diagnostic": 1
                + factor * (2 * c_sym - 0.5),
                "D_site_panel_mean": statistics.fmean(row["D_site"] for row in group),
                "mCDW2_pipi_panel_mean": statistics.fmean(
                    row["mCDW2_pipi"] for row in group
                ),
                "nn_NN_panel_mean": statistics.fmean(row["nn_NN"] for row in group),
                "kinetic_per_site_panel_mean": statistics.fmean(
                    row["kinetic_per_site"] for row in group
                ),
                "panel_method": (
                    "unweighted arithmetic mean of deterministic maximin 25-twist panel"
                ),
                "twist_spread_is_standard_error": False,
            }
        )
    with (analysis / "fig4_cnn_25twist_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def inventory_to_tsv(inventory: dict[str, Any], path: Path) -> None:
    fields = (
        "index",
        "U",
        "V",
        "kx",
        "ky",
        "filename",
        "size_bytes",
        "mtime_ns",
        "sha256",
    )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for item in inventory["results"]:
            writer.writerow({key: item[key] for key in fields})


def write_snapshot_hashes(snapshot: Path, ledger: Path) -> None:
    files = sorted(
        path for path in snapshot.rglob("*") if path.is_file() and path != ledger
    )
    with ledger.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sha256", "size_bytes", "relative_path"])
        for path in files:
            writer.writerow(
                [
                    sha256(path),
                    path.stat().st_size,
                    path.relative_to(snapshot).as_posix(),
                ]
            )


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise Refusal(f"Owned snapshot path is not a real directory: {path}")
    return info.st_dev, info.st_ino


def _scan_snapshot_tree(root: Path) -> tuple[set[str], dict[str, Path]]:
    """Return an exact real-directory/regular-file inventory without links."""
    if root.is_symlink() or not root.is_dir():
        raise Refusal(f"Snapshot staging root is not a real directory: {root}")
    directories: set[str] = set()
    files: dict[str, Path] = {}
    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        current_info = current_path.lstat()
        if stat.S_ISLNK(current_info.st_mode) or not stat.S_ISDIR(current_info.st_mode):
            raise Refusal(
                f"Snapshot contains a linked/non-directory path: {current_path}"
            )
        relative_current = (
            "." if current_path == root else current_path.relative_to(root).as_posix()
        )
        directories.add(relative_current)
        for name in directory_names:
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise Refusal(f"Snapshot contains a linked/non-directory path: {path}")
        for name in file_names:
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise Refusal(f"Snapshot contains a linked/non-regular file: {path}")
            relative = path.relative_to(root).as_posix()
            if relative in files:
                raise Refusal(f"Snapshot file inventory collision: {relative}")
            files[relative] = path
    return directories, files


def _capture_snapshot_install_contract(
    root: Path,
    *,
    expected_raw_count: int = EXPECTED_TARGETS,
) -> dict[str, Any]:
    """Bind the complete staged inventory to its ledger and final file modes."""
    directories, files = _scan_snapshot_tree(root)
    ledger_relative = "metadata/snapshot_file_sha256.tsv"
    ledger_path = files.get(ledger_relative)
    if ledger_path is None:
        raise Refusal("Snapshot hash ledger is missing before installation")
    with ledger_path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["sha256", "size_bytes", "relative_path"]:
            raise Refusal("Snapshot hash ledger has the wrong exact schema")
        rows = list(reader)
    recorded: dict[str, tuple[str, int]] = {}
    for row in rows:
        relative = Path(row["relative_path"])
        relative_text = relative.as_posix()
        digest = row["sha256"]
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative_text in ("", ".", ledger_relative)
            or relative_text in recorded
            or not SHA256_RE.fullmatch(digest)
        ):
            raise Refusal(f"Invalid snapshot hash-ledger row: {row}")
        try:
            size = int(row["size_bytes"])
        except (TypeError, ValueError) as exc:
            raise Refusal(f"Invalid snapshot ledger size: {row}") from exc
        if size < 0:
            raise Refusal(f"Negative snapshot ledger size: {row}")
        recorded[relative_text] = (digest, size)

    data_files = set(files) - {ledger_relative}
    if set(recorded) != data_files:
        raise Refusal(
            "Snapshot hash ledger does not cover the exact staged inventory; "
            f"missing={sorted(data_files - set(recorded))[:5]}, "
            f"unexpected={sorted(set(recorded) - data_files)[:5]}"
        )
    raw_count = sum(Path(relative).parts[0] == "raw" for relative in data_files)
    if raw_count != expected_raw_count:
        raise Refusal(
            f"Snapshot staging has {raw_count} raw files, expected {expected_raw_count}"
        )

    file_contract: dict[str, dict[str, Any]] = {}
    for relative, path in files.items():
        expected_digest, expected_size = (
            (sha256(path), path.stat().st_size)
            if relative == ledger_relative
            else recorded[relative]
        )
        if path.stat().st_size != expected_size or sha256(path) != expected_digest:
            raise Refusal(f"Snapshot staging file fails its hash ledger: {relative}")
        file_contract[relative] = {
            "sha256": expected_digest,
            "size_bytes": expected_size,
            "mode": 0o444,
        }
    return {"directories": directories, "files": file_contract}


def _apply_snapshot_install_modes(root: Path, contract: dict[str, Any]) -> None:
    """Freeze all contents while retaining a renameable 0700 staging root."""
    for relative, record in contract["files"].items():
        (root / relative).chmod(record["mode"])
    child_directories = sorted(
        (relative for relative in contract["directories"] if relative != "."),
        key=lambda value: (len(Path(value).parts), value),
        reverse=True,
    )
    for relative in child_directories:
        (root / relative).chmod(0o555)
    root.chmod(0o700)


def _verify_snapshot_install_contract(
    root: Path,
    contract: dict[str, Any],
    *,
    root_mode: int,
) -> None:
    """Rehash and remode-check the complete owned tree after each install phase."""
    directories, files = _scan_snapshot_tree(root)
    if directories != contract["directories"] or set(files) != set(contract["files"]):
        raise Refusal("Snapshot inventory changed during installation")
    if stat.S_IMODE(root.stat().st_mode) != root_mode:
        raise Refusal(f"Snapshot root mode is not {root_mode:04o}: {root}")
    for relative in directories - {"."}:
        if stat.S_IMODE((root / relative).stat().st_mode) != 0o555:
            raise Refusal(f"Snapshot directory mode is not 0555: {relative}")
    for relative, path in files.items():
        record = contract["files"][relative]
        if (
            stat.S_IMODE(path.stat().st_mode) != record["mode"]
            or path.stat().st_size != record["size_bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise Refusal(f"Snapshot installed file hash/mode mismatch: {relative}")


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically install one directory without replacing any existing path."""
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            -100, source_bytes, -100, destination_bytes, 0x00000001
        )  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise Refusal("Platform lacks reviewed atomic no-replace directory rename")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(source),
            str(destination),
        )


def _remove_owned_snapshot_tree(
    path: Path,
    expected_identity: tuple[int, int],
) -> None:
    """Remove only the exact directory inode created by this finalizer."""
    if not os.path.lexists(path):
        return
    if _directory_identity(path) != expected_identity:
        raise Refusal(f"Refusing to remove a snapshot path no longer owned: {path}")
    path.chmod(0o700)
    for current, directory_names, file_names in os.walk(
        path, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        if not current_path.is_symlink():
            current_path.chmod(0o700)
        for name in directory_names:
            child = current_path / name
            if not child.is_symlink():
                child.chmod(0o700)
        for name in file_names:
            child = current_path / name
            if not child.is_symlink():
                child.chmod(0o600)
    shutil.rmtree(path)
    if os.path.lexists(path):
        raise Refusal(f"Owned snapshot cleanup did not remove: {path}")


def install_read_only_snapshot(
    staging: Path,
    destination: Path,
    *,
    expected_raw_count: int = EXPECTED_TARGETS,
) -> None:
    """Validate, atomically install, and verify one immutable snapshot tree."""
    staging_identity = _directory_identity(staging)
    installed = False
    try:
        contract = _capture_snapshot_install_contract(
            staging, expected_raw_count=expected_raw_count
        )
        _apply_snapshot_install_modes(staging, contract)
        _verify_snapshot_install_contract(staging, contract, root_mode=0o700)
        lock_path = destination.parent / SNAPSHOT_INSTALL_LOCK
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            if os.path.lexists(destination):
                raise Refusal(
                    f"Destination appeared during finalization: {destination}"
                )
            _rename_directory_no_replace(staging, destination)
            installed = True
            try:
                if _directory_identity(destination) != staging_identity:
                    raise Refusal("Installed snapshot directory identity changed")
                destination.chmod(0o555)
                _verify_snapshot_install_contract(
                    destination, contract, root_mode=0o555
                )
            except BaseException:
                _remove_owned_snapshot_tree(destination, staging_identity)
                installed = False
                raise
    except BaseException:
        if not installed and os.path.lexists(staging):
            _remove_owned_snapshot_tree(staging, staging_identity)
        raise


def snapshot_readme(destination: Path) -> str:
    return f"""# Immutable Fig. 4 C_NN fullobs snapshot

This add-only snapshot was finalized only after the remote deep audit reported
exactly 25/25 valid `status COMPLETE` results, zero matching Slurm activity,
zero anomalies, zero scheduler errors, and 3/3 matching pinned hashes.

- Remote host: `{REMOTE_HOST_DEFAULT}`
- Remote batch: `{REMOTE_BATCH}`
- Local snapshot: `{destination}`
- Campaign date: 2026-08-21
- Targets: U=20,V=5 x 25 twists = 25

`metadata/manifest.tsv` is the untouched remote manifest.
`metadata/manifest_local.tsv` maps the same rows to `raw/` without changing the
remote record.  `metadata/remote_results_sha256.tsv` pins every downloaded
canonical output.  `metadata/snapshot_file_sha256.tsv` pins every other file
in this snapshot.  Analysis products are under `analysis/`.

The tree is made read-only after hashing.  The finalizer has no overwrite or
force mode; rerunning it refuses because this dated destination exists.
"""


def finalize(host: str, snapshot_root: Path, check_only: bool) -> Path:
    if not SAFE_HOST_RE.fullmatch(host):
        raise Refusal(f"Unsafe SSH host name: {host!r}")
    destination = snapshot_root / SNAPSHOT_NAME
    staging = snapshot_root / ("." + SNAPSHOT_NAME + ".staging")
    if os.path.lexists(destination):
        raise Refusal(
            f"Immutable snapshot already exists; refusing overwrite: {destination}"
        )
    if os.path.lexists(staging):
        raise Refusal(f"Staging path already exists; inspect it manually: {staging}")
    if not MONITOR.is_file():
        raise RuntimeError(f"Missing required deep-audit implementation: {MONITOR}")
    monitor_source = MONITOR.read_text()
    finalizer_bytes = SCRIPT.read_bytes()

    print("Running read-only remote completion/activity/anomaly gate...", flush=True)
    audit_before = remote_audit(host, monitor_source)
    gate_report(audit_before, "remote pre-download")
    print("Inventorying and pinning the completed remote campaign...", flush=True)
    inventory_before = remote_inventory(host)
    if check_only:
        print(
            "ELIGIBLE: all finalization gates pass; --check-only performed no writes."
        )
        return destination

    snapshot_root.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    staging_identity = _directory_identity(staging)
    metadata = staging / "metadata"
    raw = staging / "raw"
    tools_dir = metadata / "tools"

    try:
        metadata.mkdir()
        tools_dir.mkdir()
        atomic_text(
            metadata / "remote_audit_pre_download.json",
            json.dumps(audit_before, indent=2, sort_keys=True) + "\n",
        )
        atomic_text(
            metadata / "remote_inventory_pre_download.json",
            json.dumps(inventory_before, indent=2, sort_keys=True) + "\n",
        )

        result_file_list = metadata / "result_files_from_remote.txt"
        metadata_file_list = metadata / "metadata_files_from_remote.txt"
        write_lines(
            result_file_list, (item["filename"] for item in inventory_before["results"])
        )
        write_lines(
            metadata_file_list,
            (item["relative_path"] for item in inventory_before["metadata"]),
        )
        print("Downloading hash-pinned canonical COMPLETE outputs...", flush=True)
        rsync_files_from(host, REMOTE_BASE, result_file_list, raw)
        print("Downloading hash-pinned batch provenance...", flush=True)
        # metadata already exists, so download into a fresh child and move its
        # contents add-only into metadata after verification.
        remote_metadata = staging / ".remote_metadata"
        rsync_files_from(host, REMOTE_BATCH, metadata_file_list, remote_metadata)
        for source in sorted(remote_metadata.iterdir()):
            target = metadata / source.name
            if target.exists():
                raise RuntimeError(f"Metadata destination collision: {target}")
            os.rename(source, target)
        remote_metadata.rmdir()

        verify_inventory_files(inventory_before, metadata, raw)
        validate_downloaded_campaign_metadata(metadata)

        print("Repeating remote audit and inventory after transfer...", flush=True)
        audit_after = remote_audit(host, monitor_source)
        gate_report(audit_after, "remote post-download")
        inventory_after = remote_inventory(host)
        if inventory_after != inventory_before:
            raise Refusal(
                "Remote inventory changed during download; refusing snapshot installation"
            )
        atomic_text(
            metadata / "remote_audit_post_download.json",
            json.dumps(audit_after, indent=2, sort_keys=True) + "\n",
        )
        atomic_text(
            metadata / "remote_inventory_post_download.json",
            json.dumps(inventory_after, indent=2, sort_keys=True) + "\n",
        )
        inventory_to_tsv(inventory_after, metadata / "remote_results_sha256.tsv")

        pinned_monitor = tools_dir / MONITOR.name
        pinned_finalizer = tools_dir / SCRIPT.name
        pinned_monitor.write_text(monitor_source)
        pinned_finalizer.write_bytes(finalizer_bytes)
        pinned_monitor.chmod(0o555)
        pinned_finalizer.chmod(0o555)
        make_local_manifest(metadata / "manifest.tsv", metadata / "manifest_local.tsv")

        print("Running identical deep validation on downloaded files...", flush=True)
        local_report = local_audit(metadata, pinned_monitor)
        atomic_text(
            metadata / "local_download_audit.json",
            json.dumps(local_report, indent=2, sort_keys=True) + "\n",
        )

        print("Generating independent local C_NN analysis tables...", flush=True)
        generate_analysis(metadata, raw, staging / "analysis")

        snapshot_provenance = {
            "schema_version": 1,
            "snapshot_created_at": dt.datetime.now().astimezone().isoformat(),
            "immutable_add_only": True,
            "snapshot_name": SNAPSHOT_NAME,
            "destination": str(destination),
            "remote_host": host,
            "remote_user": REMOTE_USER,
            "remote_base": str(REMOTE_BASE),
            "remote_batch": str(REMOTE_BATCH),
            "expected_targets": EXPECTED_TARGETS,
            "expected_per_case": EXPECTED_PER_CASE,
            "remote_manifest_sha256": inventory_after["manifest_sha256"],
            "expected_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "remote_provenance_sha256": inventory_after["provenance_sha256"],
            "expected_provenance_sha256": EXPECTED_PROVENANCE_SHA256,
            "remote_twist_panel_sha256": inventory_after["twist_panel_sha256"],
            "expected_twist_panel_sha256": EXPECTED_TWIST_PANEL_SHA256,
            "expected_pinned_artifact_sha256": EXPECTED_PIN_SHA256,
            "identity_tolerance": IDENTITY_TOLERANCE,
            "remote_audit_pre_sha256": json_bytes_sha256(audit_before),
            "remote_audit_post_sha256": json_bytes_sha256(audit_after),
            "remote_inventory_sha256": json_bytes_sha256(inventory_after),
            "local_monitor_sha256": sha256(pinned_monitor),
            "finalizer_sha256": sha256(pinned_finalizer),
            "validation": {
                "remote_pre_counts": audit_before["counts"],
                "remote_post_counts": audit_after["counts"],
                "local_counts": local_report["counts"],
                "remote_activity": audit_after["batch_active_queue_counts"],
                "remote_anomalies": anomaly_items(audit_after),
                "local_anomalies": anomaly_items(local_report),
                "pin_matches": sum(
                    bool(item["match"]) for item in audit_after["pin_audit"]
                ),
            },
        }
        atomic_text(
            metadata / "snapshot_provenance.json",
            json.dumps(snapshot_provenance, indent=2, sort_keys=True) + "\n",
        )
        atomic_text(staging / "README.md", snapshot_readme(destination))
        write_snapshot_hashes(staging, metadata / "snapshot_file_sha256.tsv")

        # The installer changes only modes after the ledger is written. It
        # retains root 0700 through the macOS-safe no-replace rename, then
        # freezes the installed root and revalidates every hash/mode.
        install_read_only_snapshot(staging, destination)
    except BaseException as finalization_error:
        try:
            if os.path.lexists(staging):
                _remove_owned_snapshot_tree(staging, staging_identity)
        except BaseException as cleanup_error:
            raise RuntimeError(
                "FINALIZATION ABORTED and owned staging cleanup failed: "
                f"{staging}: {cleanup_error}"
            ) from finalization_error
        print(
            "FINALIZATION ABORTED. Owned staging/release was removed; "
            f"no destination was installed: {staging}",
            file=sys.stderr,
        )
        raise

    print(f"FINALIZED READ-ONLY SNAPSHOT: {destination}")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote-host", default=REMOTE_HOST_DEFAULT)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run the remote finalization gate only; never create or download anything",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        finalize(args.remote_host, SNAPSHOT_ROOT_DEFAULT.resolve(), args.check_only)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except (
        RuntimeError,
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
