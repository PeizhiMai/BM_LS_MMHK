#!/Users/cosdis/.venvs/myenv/bin/python
"""Finalize a conditionally approved Fig. 4 861-wedge C_NN campaign.

This add-only finalizer is intentionally unusable until the expansion batch
exists and all 10,032 complement jobs are valid COMPLETE.  It also rechecks
the hash-pinned 300 reused results, giving a standalone immutable snapshot of
all 10,332 raw outputs.  There is no overwrite or force option.
"""

from __future__ import annotations

import argparse
import ctypes
import csv
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[2]
CORE_PATH = SCRIPT.with_name("finalize_fullobs_25twist_fig4_cnn.py")
MONITOR = SCRIPT.with_name("monitor_fullobs_batch.py")

REMOTE_HOST_DEFAULT = "cades"
REMOTE_BASE = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
REMOTE_BATCH = REMOTE_BASE / "fig4_cnn" / "fullobs_861expand_fig4_cnn_20260821"
SNAPSHOT_NAME = "fullobs_861twist_fig4_cnn_20260821"
SNAPSHOT_ROOT_DEFAULT = REPO / "data" / "fullobs"

EXPECTED_EXPANSION = 10_032
EXPECTED_REUSED = 300
EXPECTED_COMBINED = 10_332
EXPECTED_EXPANSION_PER_CASE = 836
EXPECTED_FULL_PER_CASE = 861
EXPECTED_MANIFEST_SHA256 = (
    "53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31"
)
EXPECTED_PLAN_SHA256 = (
    "368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e"
)
EXPECTED_JOB_NAMES = ("F4CNN861X", "F4CNN861R", "F4CNN25", "F4CNN25R")
EXPECTED_ACCOUNTS = ("ccsd", "cnms")
EXPECTED_SOLVER_SHA256 = (
    "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
)
EXPECTED_SOURCE_SHA256 = (
    "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
)
EXPECTED_QBASIS_SHA256 = (
    "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
)
EXPECTED_CORE_FINALIZER_SHA256 = (
    "9180998b4733ee1c36d756b02c57e064a854ef45a312e7d4f8ea35c1dd1ab7e1"
)
EXPECTED_MONITOR_SHA256 = (
    "bc2df46d66ca8bb6ef7df4b366cedfbb1d177585b6bc64fd51e8f2cba84f887a"
)
SACCT_SINCE = "2026-08-21"
COMPLETE_RE = re.compile(r"(?m)^status[\t ]+COMPLETE[\t ]*$")
SNAPSHOT_INSTALL_LOCK = ".fullobs_861twist_fig4_cnn_20260821.install.lock"

# The remote materializer fixes these executable paths.  Every other snapshot
# file is data or reviewed source and must be installed 0444.  Keep this exact
# inventory synchronized with the publication loader's independent contract.
SNAPSHOT_EXECUTABLE_RELATIVE_PATHS = frozenset(
    {
        "metadata/preflight.py",
        "metadata/submit_fill.py",
        "metadata/status.py",
        "metadata/analyze.py",
        "metadata/audit_status.py",
        "metadata/pinned_solver/Hubbard_sym_testobs_UV.x",
        "metadata/pinned_solver/libqbasis.so",
        "metadata/tools/audit_status.py",
        "metadata/local_tools/monitor_fullobs_batch.py",
        "metadata/local_tools/finalize_fullobs_861expand_fig4_cnn.py",
        "metadata/local_tools/finalize_fullobs_25twist_fig4_cnn.py",
    }
)


REMOTE_QUIESCENCE_PROGRAM = r"""
import json, os, subprocess, sys
from pathlib import Path

batch=Path(sys.argv[1]).resolve()
names=set(sys.argv[2:])
submitted=batch/"submitted"
if not submitted.is_dir():
    raise SystemExit("missing submitted directory: "+str(submitted))
claims=sorted(path.name for path in submitted.glob("*.claim"))
user=os.environ.get("USER")
if not user:
    raise SystemExit("USER is unset")
proc=subprocess.run(
    ["squeue","-h","-r","-u",user,"-o","%i|%j|%a|%T"],
    text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
)
if proc.returncode:
    raise SystemExit("squeue failed: "+proc.stderr.strip())
active=[]
for line in proc.stdout.splitlines():
    fields=line.split("|",3)
    if len(fields)==4 and fields[1] in names:
        active.append({"job_id":fields[0],"job_name":fields[1],"account":fields[2],"state":fields[3]})
print(json.dumps({"claims":claims,"exact_name_activity":active},indent=2,sort_keys=True))
"""


REMOTE_INVENTORY_PROGRAM = r"""
import csv, hashlib, json, re, sys
from collections import Counter
from pathlib import Path

batch=Path(sys.argv[1]).resolve(); base=Path(sys.argv[2]).resolve()
require_analysis=sys.argv[3]=="1"
rx=re.compile(r"(?m)^status[\t ]+COMPLETE[\t ]*$")
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def need(condition,message):
    if not condition: raise SystemExit(message)

manifest=batch/"manifest.tsv"; reused_path=batch/"reused_25.tsv"
exp=list(csv.DictReader(manifest.open(),delimiter="\t"))
reused=list(csv.DictReader(reused_path.open(),delimiter="\t"))
need(len(exp)==10032,"expansion manifest count mismatch")
need(len(reused)==300,"reused count mismatch")
need(sha(manifest)=="53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31","manifest hash mismatch")
need(len({r["index"] for r in exp})==10032,"expansion index collision")
need(len({r["seed"] for r in exp})==10032,"expansion seed collision")
need(len({r["seed"] for r in reused})==300,"reused seed collision")
need(not ({r["seed"] for r in exp}&{r["seed"] for r in reused}),"cross-campaign seed collision")
rows=[]
for r in exp:
    rows.append({"global_index":int(r["index"]),"source":"expansion",**r})
for n,r in enumerate(reused,1):
    rows.append({"global_index":10032+n,"source":"reused_25",**r})
keys={(r["U"],r["V"],r["kx"],r["ky"]) for r in rows}
need(len(keys)==10332,"combined coordinate collision")
counts=Counter((r["U"],r["V"]) for r in rows)
need(len(counts)==12 and set(counts.values())=={861},"combined per-case count mismatch")
wedge={(str(x),str(y)) for y in range(41) for x in range(y+1)}
for case in counts:
    observed={(r["kx"],r["ky"]) for r in rows if (r["U"],r["V"])==case}
    need(observed==wedge,"combined wedge mismatch at U={},V={}".format(*case))
results=[]; seen=set()
for r in rows:
    path=Path(r["result"]).resolve()
    need(path.parent==base,"result escapes canonical base: "+str(path))
    need(path.name not in seen,"duplicate result filename: "+path.name); seen.add(path.name)
    need(path.is_file(),"missing result: "+str(path))
    text=path.read_text(errors="replace")
    need(bool(rx.search(text)),"result lacks COMPLETE: "+str(path))
    st=path.stat()
    results.append({
      "index":int(r["global_index"]),"source":r["source"],"U":r["U"],"V":r["V"],
      "kx":int(r["kx"]),"ky":int(r["ky"]),"filename":path.name,"path":str(path),
      "size_bytes":st.st_size,"mtime_ns":st.st_mtime_ns,"sha256":sha(path)})

submitted=list(csv.DictReader((batch/"submission.tsv").open(),delimiter="\t"))
need(len(submitted)==10032,"original submission ledger must have exactly 10032 rows")
need(len({r["job_id"] for r in submitted})==10032,"submission job-id collision")
need({r["index"] for r in submitted}=={r["index"] for r in exp},"submission coverage mismatch")

fixed=[
 "manifest.tsv","reused_25.tsv","decision_certificate.json","provenance.json",
 "PINNED_SHA256SUMS","TEMPLATE_SHA256SUMS","README.md","submission.tsv",
 "repair_submission.tsv","preflight.py","submit_fill.py","status.py","analyze.py",
 "audit_status.py","pinned_solver/Hubbard_sym_testobs_UV.x",
 "pinned_solver/Hubbard_sym_testobs_UV.cc","pinned_solver/libqbasis.so",
]
for directory in ("reviewed_inputs","tools"):
    root=batch/directory
    need(root.is_dir(),"missing metadata directory: "+str(root))
    fixed.extend(p.relative_to(batch).as_posix() for p in sorted(root.rglob("*")) if p.is_file())
for rel in ("analysis/fig4_cnn_full861_summary.csv","analysis/fig4_cnn_full861_provenance.json"):
    if require_analysis: fixed.append(rel)
    elif (batch/rel).is_file(): fixed.append(rel)
metadata=[]; seen_rel=set()
for rel in fixed:
    need(rel not in seen_rel,"duplicate metadata path: "+rel); seen_rel.add(rel)
    path=batch/rel; need(path.is_file(),"missing metadata: "+str(path)); st=path.stat()
    metadata.append({"relative_path":rel,"size_bytes":st.st_size,"mtime_ns":st.st_mtime_ns,"sha256":sha(path)})
payload={
 "schema_version":1,"batch":str(batch),"base":str(base),
 "manifest_sha256":sha(manifest),"reused_25_sha256":sha(reused_path),
 "expansion_count":len(exp),"reused_count":len(reused),"target_count":len(results),
 "submission_count":len(submitted),"results":sorted(results,key=lambda x:x["index"]),
 "metadata":sorted(metadata,key=lambda x:x["relative_path"])}
print(json.dumps(payload,indent=2,sort_keys=True))
"""


def load_core():
    if (
        hashlib.sha256(CORE_PATH.read_bytes()).hexdigest()
        != EXPECTED_CORE_FINALIZER_SHA256
    ):
        raise RuntimeError("Pinned 25-panel finalizer core hash mismatch")
    spec = importlib.util.spec_from_file_location(
        "fig4_cnn_25_finalizer_core", CORE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import finalizer core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_core()
Refusal = CORE.Refusal


def sha256(path: Path) -> str:
    return CORE.sha256(path)


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise Refusal(f"owned snapshot path is not a real directory: {path}")
    return info.st_dev, info.st_ino


def _scan_snapshot_tree(root: Path) -> tuple[set[str], dict[str, Path]]:
    """Return the exact real-directory/regular-file inventory without links."""
    if root.is_symlink() or not root.is_dir():
        raise Refusal(f"snapshot staging root is not a real directory: {root}")
    directories: set[str] = set()
    files: dict[str, Path] = {}
    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        current_info = current_path.lstat()
        if stat.S_ISLNK(current_info.st_mode) or not stat.S_ISDIR(
            current_info.st_mode
        ):
            raise Refusal(f"snapshot contains a linked/non-directory path: {current_path}")
        relative_current = (
            "."
            if current_path == root
            else current_path.relative_to(root).as_posix()
        )
        directories.add(relative_current)
        for name in directory_names:
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise Refusal(f"snapshot contains a linked/non-directory path: {path}")
        for name in file_names:
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise Refusal(f"snapshot contains a linked/non-regular file: {path}")
            relative = path.relative_to(root).as_posix()
            if relative in files:
                raise Refusal(f"snapshot file inventory collision: {relative}")
            files[relative] = path
    return directories, files


def _capture_snapshot_install_contract(
    root: Path,
    *,
    expected_raw_count: int = EXPECTED_COMBINED,
    executable_paths: frozenset[str] = SNAPSHOT_EXECUTABLE_RELATIVE_PATHS,
) -> dict[str, Any]:
    """Bind the complete staged inventory to its ledger and exact final modes."""
    directories, files = _scan_snapshot_tree(root)
    ledger_relative = "metadata/snapshot_file_sha256.tsv"
    ledger_path = files.get(ledger_relative)
    if ledger_path is None:
        raise Refusal("snapshot hash ledger is missing before installation")
    with ledger_path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["sha256", "size_bytes", "relative_path"]:
            raise Refusal("snapshot hash ledger has the wrong exact schema")
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
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise Refusal(f"invalid snapshot hash-ledger row: {row}")
        try:
            size = int(row["size_bytes"])
        except (TypeError, ValueError) as exc:
            raise Refusal(f"invalid snapshot ledger size: {row}") from exc
        if size < 0:
            raise Refusal(f"negative snapshot ledger size: {row}")
        recorded[relative_text] = (digest, size)

    data_files = set(files) - {ledger_relative}
    if set(recorded) != data_files:
        raise Refusal(
            "snapshot hash ledger does not cover the exact staged inventory; "
            f"missing={sorted(data_files - set(recorded))[:5]}, "
            f"unexpected={sorted(set(recorded) - data_files)[:5]}"
        )
    raw_count = sum(Path(relative).parts[0] == "raw" for relative in data_files)
    if raw_count != expected_raw_count:
        raise Refusal(
            f"snapshot staging has {raw_count} raw files, expected {expected_raw_count}"
        )
    missing_executables = set(executable_paths) - set(files)
    if missing_executables:
        raise Refusal(
            "snapshot staging lacks reviewed executable paths: "
            + ", ".join(sorted(missing_executables))
        )

    file_contract: dict[str, dict[str, Any]] = {}
    for relative, path in files.items():
        expected_digest, expected_size = (
            (sha256(path), path.stat().st_size)
            if relative == ledger_relative
            else recorded[relative]
        )
        if path.stat().st_size != expected_size or sha256(path) != expected_digest:
            raise Refusal(f"snapshot staging file fails its hash ledger: {relative}")
        file_contract[relative] = {
            "sha256": expected_digest,
            "size_bytes": expected_size,
            "mode": 0o555 if relative in executable_paths else 0o444,
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
        raise Refusal("snapshot inventory changed during installation")
    if stat.S_IMODE(root.stat().st_mode) != root_mode:
        raise Refusal(f"snapshot root mode is not {root_mode:04o}: {root}")
    for relative in directories - {"."}:
        if stat.S_IMODE((root / relative).stat().st_mode) != 0o555:
            raise Refusal(f"snapshot directory mode is not 0555: {relative}")
    for relative, path in files.items():
        record = contract["files"][relative]
        if (
            stat.S_IMODE(path.stat().st_mode) != record["mode"]
            or path.stat().st_size != record["size_bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise Refusal(f"snapshot installed file hash/mode mismatch: {relative}")


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
        raise Refusal("platform lacks reviewed atomic no-replace directory rename")
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
        raise Refusal(f"refusing to remove a snapshot path no longer owned: {path}")
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
        raise Refusal(f"owned snapshot cleanup did not remove: {path}")


def install_read_only_snapshot(
    staging: Path,
    destination: Path,
    *,
    expected_raw_count: int = EXPECTED_COMBINED,
    executable_paths: frozenset[str] = SNAPSHOT_EXECUTABLE_RELATIVE_PATHS,
) -> None:
    """Validate, atomically install, and verify one immutable snapshot tree."""
    staging_identity = _directory_identity(staging)
    installed = False
    try:
        contract = _capture_snapshot_install_contract(
            staging,
            expected_raw_count=expected_raw_count,
            executable_paths=executable_paths,
        )
        _apply_snapshot_install_modes(staging, contract)
        _verify_snapshot_install_contract(staging, contract, root_mode=0o700)
        lock_path = destination.parent / SNAPSHOT_INSTALL_LOCK
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            if os.path.lexists(destination):
                raise Refusal(f"destination appeared: {destination}")
            _rename_directory_no_replace(staging, destination)
            installed = True
            try:
                if _directory_identity(destination) != staging_identity:
                    raise Refusal("installed snapshot directory identity changed")
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


def monitor_arguments(*, no_slurm: bool = False, combined: bool = False) -> list[str]:
    total = EXPECTED_COMBINED if combined else EXPECTED_EXPANSION
    per_case = EXPECTED_FULL_PER_CASE if combined else EXPECTED_EXPANSION_PER_CASE
    args = [
        "--batch",
        str(REMOTE_BATCH),
        "--job-name",
        EXPECTED_JOB_NAMES[0],
        "--job-name",
        EXPECTED_JOB_NAMES[1],
        "--job-name",
        EXPECTED_JOB_NAMES[2],
        "--job-name",
        EXPECTED_JOB_NAMES[3],
        "--pin-file",
        "PINNED_SHA256SUMS",
        "--require-pins",
        "--submission-log",
        "repair_submission.tsv",
        "--since",
        SACCT_SINCE,
        "--expect-targets",
        str(total),
        "--expect-per-case",
        str(per_case),
        "--expect-account",
        "ccsd",
        "--expect-account",
        "cnms",
        "--expect-partition",
        "burst",
        "--expect-cpus",
        "32",
        "--expect-nodes",
        "1",
        "--expect-memory",
        "100G",
        "--expect-time-limit",
        "08:00:00",
        "--json",
    ]
    if no_slurm:
        args.append("--no-slurm")
    return args


def gate_report(report: dict[str, Any], *, combined: bool, label: str) -> None:
    expected = EXPECTED_COMBINED if combined else EXPECTED_EXPANSION
    reasons = []
    if report.get("total_targets") != expected:
        reasons.append(f"targets={report.get('total_targets')}")
    if report.get("counts") != {"COMPLETE": expected}:
        reasons.append(f"counts={report.get('counts')}")
    if report.get("batch_active_queue_counts"):
        reasons.append(f"active={report['batch_active_queue_counts']}")
    if report.get("scheduler_errors"):
        reasons.append("scheduler_errors")
    if report.get("warnings"):
        reasons.append(f"warnings={report['warnings']}")
    if report.get("repair_candidates"):
        reasons.append("repair_candidates")
    for key, value in report.get("anomalies", {}).items():
        if value:
            reasons.append(
                f"{key}={len(value) if isinstance(value, (list, dict)) else value}"
            )
    pins = report.get("pin_audit", [])
    if len(pins) != 3 or not all(item.get("match") for item in pins):
        reasons.append("runtime_pins")
    if reasons:
        raise Refusal(label + " gate refused: " + "; ".join(reasons))


def remote_audit(host: str, monitor_source: str) -> dict[str, Any]:
    output = CORE.remote_python(host, monitor_source, monitor_arguments(), timeout=900)
    report = json.loads(output)
    gate_report(report, combined=False, label="remote")
    return report


def remote_quiescence(host: str, *, label: str) -> dict[str, Any]:
    output = CORE.remote_python(
        host,
        REMOTE_QUIESCENCE_PROGRAM,
        (str(REMOTE_BATCH), *EXPECTED_JOB_NAMES),
        timeout=300,
    )
    payload = json.loads(output)
    claims = payload.get("claims")
    activity = payload.get("exact_name_activity")
    if not isinstance(claims, list) or not isinstance(activity, list):
        raise Refusal(f"{label} quiescence response is malformed")
    reasons = []
    if claims:
        reasons.append(f"claims={claims}")
    if activity:
        reasons.append(f"exact_name_activity={activity}")
    if reasons:
        raise Refusal(f"{label} quiescence gate refused: " + "; ".join(reasons))
    return payload


def run_remote_preflight(host: str) -> str:
    command = f"/usr/bin/python3.11 {REMOTE_BATCH}/preflight.py"
    return CORE.run(["ssh", host, command], timeout=1800).stdout


def run_remote_analysis(host: str) -> str:
    command = f"/usr/bin/python3.11 {REMOTE_BATCH}/analyze.py"
    return CORE.run(["ssh", host, command], timeout=1800).stdout


def remote_inventory(host: str, *, require_analysis: bool) -> dict[str, Any]:
    output = CORE.remote_python(
        host,
        REMOTE_INVENTORY_PROGRAM,
        (str(REMOTE_BATCH), str(REMOTE_BASE), "1" if require_analysis else "0"),
        timeout=3600,
    )
    payload = json.loads(output)
    if payload.get("target_count") != EXPECTED_COMBINED:
        raise Refusal("combined inventory count mismatch")
    if payload.get("expansion_count") != EXPECTED_EXPANSION:
        raise Refusal("expansion inventory count mismatch")
    if payload.get("reused_count") != EXPECTED_REUSED:
        raise Refusal("reused inventory count mismatch")
    if payload.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise Refusal("manifest hash mismatch")
    if len(payload.get("results", [])) != EXPECTED_COMBINED:
        raise Refusal("inventory result list mismatch")
    return payload


def make_local_manifest(metadata: Path) -> None:
    with (metadata / "manifest.tsv").open(newline="") as f:
        exp = list(csv.DictReader(f, delimiter="\t"))
    with (metadata / "reused_25.tsv").open(newline="") as f:
        reused = list(csv.DictReader(f, delimiter="\t"))
    rows = []
    for source, group in (("expansion", exp), ("reused_25", reused)):
        for row in group:
            remote = row["result"]
            filename = Path(remote).name
            rows.append(
                {
                    "index": len(rows) + 1,
                    "source_campaign": source,
                    "U": row["U"],
                    "V": row["V"],
                    "expected_phase": "Mott",
                    "kx": row["kx"],
                    "ky": row["ky"],
                    "seed": row["seed"],
                    "job_name": "",
                    "result": str((metadata.parent / "raw" / filename).resolve()),
                    "remote_result": remote,
                    "snapshot_result": "../raw/" + filename,
                    "template": "",
                }
            )
    if len(rows) != EXPECTED_COMBINED:
        raise RuntimeError("local combined manifest count mismatch")
    fields = list(rows[0])
    with (metadata / "manifest_local.tsv").open("x", newline="") as f:
        w = csv.DictWriter(f, delimiter="\t", fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def local_audit(metadata: Path, monitor_path: Path) -> dict[str, Any]:
    args = monitor_arguments(no_slurm=True, combined=True)
    batch_index = args.index("--batch")
    args[batch_index + 1] = str(metadata)
    args.extend(("--manifest", "manifest_local.tsv"))
    proc = CORE.run(
        [str(Path.home() / ".venvs/myenv/bin/python"), str(monitor_path), *args],
        timeout=3600,
    )
    report = json.loads(proc.stdout)
    gate_report(report, combined=True, label="local downloaded-data")
    return report


def parse_values(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2:
            out[fields[0]] = fields[1]
    return out


def generate_analysis(metadata: Path, raw: Path, analysis: Path) -> None:
    analysis.mkdir(exist_ok=False)
    with (metadata / "manifest_local.tsv").open(newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    parsed = []
    groups = defaultdict(list)
    for row in rows:
        path = raw / Path(row["snapshot_result"]).name
        values = parse_values(path)
        C = float(values["<C1_NN>"])
        item = {
            "index": int(row["index"]),
            "source_campaign": row["source_campaign"],
            "U": int(row["U"]),
            "V": float(row["V"]),
            "kx": int(row["kx"]),
            "ky": int(row["ky"]),
            "seed": int(row["seed"]),
            "C_NN": C,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "snapshot_result": row["snapshot_result"],
            "remote_result": row["remote_result"],
        }
        parsed.append(item)
        groups[(item["U"], item["V"])].append(item)
    with (analysis / "fig4_cnn_full861_raw_validation.csv").open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(parsed[0]))
        w.writeheader()
        w.writerows(parsed)
    summary = []
    expected_wedge = {(x, y) for y in range(41) for x in range(y + 1)}
    for (U, V), group in sorted(groups.items()):
        if len(group) != 861 or {(r["kx"], r["ky"]) for r in group} != expected_wedge:
            raise RuntimeError(f"bad full wedge U={U},V={V}")
        weighted = []
        for row in group:
            kx, ky = row["kx"], row["ky"]
            weight = (
                (1 if kx == ky else 2)
                * (0.5 if kx in (0, 40) else 1)
                * (0.5 if ky in (0, 40) else 1)
            )
            weighted.append((weight, row["C_NN"]))
        total = sum(w for w, _ in weighted)
        if not math.isclose(total, 1600.0):
            raise RuntimeError("quadrature weight mismatch")
        mean = sum(w * C for w, C in weighted) / total
        spread = math.sqrt(sum(w * (C - mean) ** 2 for w, C in weighted) / total)
        factor = (2 * U - V) / (U - V)
        summary.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "complete_wedge": 861,
                "quadrature_weight": total,
                "C_NN_full_861": mean,
                "C_NN_full_quadrature_weighted_population_std": spread,
                "s_eq10_signed": 1 + factor * (2 * mean - 0.5),
                "twist_spread_is_standard_error": False,
            }
        )
    if len(summary) != 12:
        raise RuntimeError("full861 analysis case count mismatch")
    with (analysis / "fig4_cnn_full861_summary.csv").open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    remote_summary = metadata / "analysis/fig4_cnn_full861_summary.csv"
    with remote_summary.open(newline="") as f:
        remote_rows = list(csv.DictReader(f))
    if len(remote_rows) != 12:
        raise RuntimeError("remote full861 summary count mismatch")
    for local, remote in zip(summary, remote_rows):
        for key in (
            "U",
            "V",
            "C_NN_full_861",
            "C_NN_full_quadrature_weighted_population_std",
            "s_eq10_signed",
        ):
            if not math.isclose(
                float(local[key]), float(remote[key]), rel_tol=1e-13, abs_tol=1e-14
            ):
                raise RuntimeError(
                    f"remote/local analysis mismatch {key} U={local['U']} V={local['V']}"
                )


def snapshot_readme(destination: Path) -> str:
    return f"""# Immutable full-861 Fig. 4 C_NN snapshot

This standalone add-only snapshot contains 10,332 hash-verified raw outputs:
10,032 conditionally approved complement calculations plus the exact 300
source-panel outputs bound into the approval certificate.  Every case contains
the exact 861-coordinate wedge and total quadrature weight 1600.

- Remote batch: `{REMOTE_BATCH}`
- Local snapshot: `{destination}`
- Expansion manifest SHA-256: `{EXPECTED_MANIFEST_SHA256}`
- Semantic plan SHA-256: `{EXPECTED_PLAN_SHA256}`

`metadata/manifest.tsv` and `metadata/reused_25.tsv` are untouched remote
records. `metadata/manifest_local.tsv` is their combined local 10,332-row map.
Twist spread is a quadrature-weighted population diagnostic, not a standard
error. The finalizer has no overwrite or force mode.
"""


def finalize(host: str, snapshot_root: Path, check_only: bool) -> Path:
    destination = snapshot_root / SNAPSHOT_NAME
    staging = snapshot_root / ("." + SNAPSHOT_NAME + ".staging")
    if os.path.lexists(destination):
        raise Refusal(f"snapshot exists: {destination}")
    if os.path.lexists(staging):
        raise Refusal(f"staging exists: {staging}")
    if sha256(MONITOR) != EXPECTED_MONITOR_SHA256:
        raise RuntimeError("Pinned monitor hash mismatch")
    monitor_source = MONITOR.read_text()
    quiescence_before = remote_quiescence(host, label="pre-download")
    audit_before = remote_audit(host, monitor_source)
    run_remote_preflight(host)
    inventory_before = remote_inventory(host, require_analysis=False)
    if check_only:
        print("ELIGIBLE: expansion=10032 COMPLETE, reused=300 hash-pinned, no writes")
        return destination
    run_remote_analysis(host)
    inventory_before = remote_inventory(host, require_analysis=True)
    # Recheck immediately before any transfer.  The earlier checks make
    # --check-only meaningful; these bind the actual download window after the
    # add-only remote analysis has been materialized.
    quiescence_before = remote_quiescence(host, label="pre-download")
    audit_before = remote_audit(host, monitor_source)
    run_remote_preflight(host)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    staging_identity = _directory_identity(staging)
    metadata = staging / "metadata"
    raw = staging / "raw"
    tools = metadata / "local_tools"
    metadata.mkdir()
    tools.mkdir()
    try:
        CORE.atomic_text(
            metadata / "remote_quiescence_pre_download.json",
            json.dumps(quiescence_before, indent=2, sort_keys=True) + "\n",
        )
        CORE.atomic_text(
            metadata / "remote_audit_pre_download.json",
            json.dumps(audit_before, indent=2, sort_keys=True) + "\n",
        )
        CORE.atomic_text(
            metadata / "remote_inventory_pre_download.json",
            json.dumps(inventory_before, indent=2, sort_keys=True) + "\n",
        )
        results_list = metadata / "result_files_from_remote.txt"
        meta_list = metadata / "metadata_files_from_remote.txt"
        CORE.write_lines(
            results_list, (r["filename"] for r in inventory_before["results"])
        )
        CORE.write_lines(
            meta_list, (r["relative_path"] for r in inventory_before["metadata"])
        )
        CORE.rsync_files_from(host, REMOTE_BASE, results_list, raw)
        remote_metadata = staging / ".remote_metadata"
        CORE.rsync_files_from(host, REMOTE_BATCH, meta_list, remote_metadata)
        for source in sorted(remote_metadata.iterdir()):
            target = metadata / source.name
            if target.exists():
                raise RuntimeError(f"metadata collision: {target}")
            os.rename(source, target)
        remote_metadata.rmdir()
        CORE.verify_inventory_files(inventory_before, metadata, raw)
        quiescence_after = remote_quiescence(host, label="post-download")
        audit_after = remote_audit(host, monitor_source)
        run_remote_preflight(host)
        inventory_after = remote_inventory(host, require_analysis=True)
        if inventory_after != inventory_before:
            raise Refusal("remote inventory changed during transfer")
        CORE.atomic_text(
            metadata / "remote_quiescence_post_download.json",
            json.dumps(quiescence_after, indent=2, sort_keys=True) + "\n",
        )
        CORE.atomic_text(
            metadata / "remote_audit_post_download.json",
            json.dumps(audit_after, indent=2, sort_keys=True) + "\n",
        )
        CORE.atomic_text(
            metadata / "remote_inventory_post_download.json",
            json.dumps(inventory_after, indent=2, sort_keys=True) + "\n",
        )
        CORE.inventory_to_tsv(inventory_after, metadata / "remote_results_sha256.tsv")
        pinned_monitor = tools / MONITOR.name
        pinned_finalizer = tools / SCRIPT.name
        pinned_core = tools / CORE_PATH.name
        pinned_monitor.write_text(monitor_source)
        pinned_finalizer.write_bytes(SCRIPT.read_bytes())
        pinned_core.write_bytes(CORE_PATH.read_bytes())
        pinned_monitor.chmod(0o555)
        pinned_finalizer.chmod(0o555)
        pinned_core.chmod(0o555)
        make_local_manifest(metadata)
        local_report = local_audit(metadata, pinned_monitor)
        CORE.atomic_text(
            metadata / "local_download_audit.json",
            json.dumps(local_report, indent=2, sort_keys=True) + "\n",
        )
        generate_analysis(metadata, raw, staging / "analysis")
        provenance = {
            "schema_version": 1,
            "snapshot_created_at": dt.datetime.now().astimezone().isoformat(),
            "immutable_add_only": True,
            "destination": str(destination),
            "remote_host": host,
            "remote_batch": str(REMOTE_BATCH),
            "expansion_targets": EXPECTED_EXPANSION,
            "reused_targets": EXPECTED_REUSED,
            "combined_targets": EXPECTED_COMBINED,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "plan_sha256": EXPECTED_PLAN_SHA256,
            "solver_sha256": EXPECTED_SOLVER_SHA256,
            "source_sha256": EXPECTED_SOURCE_SHA256,
            "qbasis_library_sha256": EXPECTED_QBASIS_SHA256,
            "remote_inventory_sha256": CORE.json_bytes_sha256(inventory_after),
            "remote_quiescence_pre_download_sha256": CORE.json_bytes_sha256(
                quiescence_before
            ),
            "remote_quiescence_post_download_sha256": CORE.json_bytes_sha256(
                quiescence_after
            ),
            "local_monitor_sha256": sha256(pinned_monitor),
            "finalizer_sha256": sha256(pinned_finalizer),
            "core_finalizer_sha256": sha256(pinned_core),
            "validation": {
                "remote_counts": audit_after["counts"],
                "local_counts": local_report["counts"],
                "remote_activity": audit_after["batch_active_queue_counts"],
                "remote_claims_pre_download": quiescence_before["claims"],
                "remote_claims_post_download": quiescence_after["claims"],
                "remote_exact_name_activity_pre_download": quiescence_before[
                    "exact_name_activity"
                ],
                "remote_exact_name_activity_post_download": quiescence_after[
                    "exact_name_activity"
                ],
            },
        }
        CORE.atomic_text(
            metadata / "snapshot_provenance.json",
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        )
        CORE.atomic_text(staging / "README.md", snapshot_readme(destination))
        CORE.write_snapshot_hashes(staging, metadata / "snapshot_file_sha256.tsv")
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
            f"FINALIZATION ABORTED; owned staging/release removed: {staging}",
            file=sys.stderr,
        )
        raise
    print(f"FINALIZED READ-ONLY SNAPSHOT: {destination}")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote-host", default=REMOTE_HOST_DEFAULT)
    parser.add_argument("--snapshot-root", type=Path, default=SNAPSHOT_ROOT_DEFAULT)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        finalize(
            args.remote_host, args.snapshot_root.expanduser().resolve(), args.check_only
        )
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
