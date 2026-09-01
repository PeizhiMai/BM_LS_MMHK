#!/Users/cosdis/.venvs/myenv/bin/python
"""Capture and verify the immutable, policy-bound 25→861 handoff record.

The tool never mutates CADES.  Before each launch/rebalance action it captures
an exclusive local policy-state artifact from a fresh remote audit.  After the
action it writes an exclusive receipt that binds the exact append-only
submission-ledger delta, selected manifest indices/job IDs, and the recomputed
campaign-specific add-only policy.  Every artifact is fsynced, mode 0444, and
never replaced.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent
GENERATOR = PACKAGE / "generate_batch.py"
REMOTE_ROOT = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn")
REMOTE_BATCH = REMOTE_ROOT / "fullobs_861expand_fig4_cnn_20260821"
EXPECTED_MANIFEST_SHA256 = (
    "53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31"
)
EXPECTED_PLAN_SHA256 = (
    "368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e"
)
EXPECTED_TARGETS = 10_032
EXPECTED_PINS = 3
JOB_NAMES = ("F4CNN861X", "F4CNN861R")
PHASES = ("initial_launch", "rebalance_10m", "rebalance_20m")
PREDECESSOR = {
    "rebalance_10m": "initial_launch",
    "rebalance_20m": "rebalance_10m",
}
MIN_CHECKPOINT_SECONDS = 600
RECEIPT_SCHEMA_VERSION = 2
POLICY_STATE_SCHEMA_VERSION = 1
POLICY_ALGORITHM = "fig4_cnn_861_add_only_interleaved_v1"
ACCOUNTS = ("ccsd", "cnms")
EXPECTED_CASES = (
    ("20", "0"),
    ("20", "2"),
    ("20", "3"),
    ("20", "4"),
    ("20", "4.5"),
    ("40", "6"),
    ("80", "0"),
    ("80", "4"),
    ("80", "8"),
    ("80", "12"),
    ("80", "16"),
    ("80", "18"),
)
DECISION_COUNT_KEYS = (
    "pending_ccsd",
    "pending_cnms",
    "running_or_completing_ccsd",
    "running_or_completing_cnms",
)
HANDOFF_SUBMISSION_KINDS = set(PHASES)


class Refusal(RuntimeError):
    """A safety or integrity gate did not pass."""


# This program is sent over stdin and is deliberately read-only.  It repeats
# package/certificate/preflight/audit gates and returns the exact semantic
# submission ledger plus a deterministic interleaving of still-unsubmitted
# manifest indices.  No scheduler mutation command appears here.
REMOTE_STATE_PROGRAM = r"""
import csv, hashlib, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

batch=Path(sys.argv[1]).resolve()
remote_package=Path(sys.argv[2]).resolve()
remote_certificate=Path(sys.argv[3]).resolve()
expected_manifest=sys.argv[4]
expected_certificate=sys.argv[5]
expected_receipt_tool=sys.argv[6]
job_names={"F4CNN861X","F4CNN861R"}
expected_cases=(
 ("20","0"),("20","2"),("20","3"),("20","4"),("20","4.5"),("40","6"),
 ("80","0"),("80","4"),("80","8"),("80","12"),("80","16"),("80","18"),
)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def need(condition,message):
    if not condition: raise SystemExit(message)
def canonical_rows_digest(rows):
    encoded=json.dumps(rows,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(encoded).hexdigest()
def index_from_template(path):
    match=re.match(r"^job_f4cnn861x_(\d{5})_",path.name)
    need(bool(match),"malformed template/archive basename: "+path.name)
    return int(match.group(1))

def interleave(indices,manifest):
    groups=defaultdict(list)
    for index_text,row in manifest.items():
        index=int(index_text)
        case=(row["U"],row["V"])
        need(case in expected_cases,"manifest has unexpected physics case")
        groups[case].append(index)
    for values in groups.values(): values.sort()
    full_order=[]
    depth=max((len(values) for values in groups.values()),default=0)
    for position in range(depth):
        for case in expected_cases:
            values=groups.get(case,())
            if position<len(values): full_order.append(values[position])
    available=set(indices)
    need(len(available)==len(indices),"available template index collision")
    ordered=[index for index in full_order if index in available]
    need(len(ordered)==len(indices) and len(set(ordered))==len(indices),"interleave cardinality mismatch")
    return ordered

need(batch.is_dir(),"missing expansion batch")
need(remote_package.is_dir(),"missing reviewed holding package")
need(remote_certificate.is_file(),"missing external decision certificate")
need(sha(remote_certificate)==expected_certificate,"external certificate hash mismatch")
need(not (batch/"MATERIALIZATION_INCOMPLETE").exists(),"materialization marker exists")
need(sha(batch/"manifest.tsv")==expected_manifest,"manifest hash mismatch")
need(sha(batch/"decision_certificate.json")==expected_certificate,"certificate hash mismatch")
need(sha(batch/"tools/handoff_receipt.py")==expected_receipt_tool,"receipt-tool hash mismatch")
provenance=json.loads((batch/"provenance.json").read_text())
need(provenance.get("manifest_sha256")==expected_manifest,"provenance manifest mismatch")
need(provenance.get("decision_certificate_sha256")==expected_certificate,"provenance certificate mismatch")
need(provenance.get("package_tools_sha256",{}).get("handoff_receipt.py")==expected_receipt_tool,"provenance receipt-tool mismatch")
package_verify=subprocess.run(
    ["/usr/bin/python3.11",str(remote_package/"generate_batch.py"),
     "--verify-certificate","--decision-certificate",str(remote_certificate)],
    text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
)
need(package_verify.returncode==0,"holding-package/certificate revalidation failed: "+package_verify.stdout+package_verify.stderr)
package_verify_payload=json.loads(package_verify.stdout)
need(package_verify_payload.get("mode")=="VERIFY_CERTIFICATE_ONLY","holding package did not enter certificate-only mode")
preflight=subprocess.run(
    ["/usr/bin/python3.11",str(batch/"preflight.py")],
    text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
)
need(preflight.returncode==0,"preflight failed: "+preflight.stdout+preflight.stderr)
audit_args=[
    "/usr/bin/python3.11",str(batch/"audit_status.py"),"--batch",str(batch),
    "--job-name","F4CNN861X","--job-name","F4CNN861R",
    "--pin-file","PINNED_SHA256SUMS","--require-pins",
    "--submission-log","repair_submission.tsv","--since","2026-08-21",
    "--expect-targets","10032","--expect-per-case","836",
    "--expect-account","ccsd","--expect-account","cnms",
    "--expect-partition","burst","--expect-cpus","32","--expect-nodes","1",
    "--expect-memory","100G","--expect-time-limit","08:00:00","--json",
]
audit_proc=subprocess.run(
    audit_args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
)
need(audit_proc.returncode==0,"scheduler audit failed: "+audit_proc.stdout+audit_proc.stderr)
audit=json.loads(audit_proc.stdout)
claims=sorted(path.name for path in (batch/"submitted").glob("*.claim"))
template_paths=sorted((batch/"templates").glob("job_f4cnn861x_*.sh"))
archive_paths=sorted((batch/"submitted").glob("job_f4cnn861x_*.template"))
template_indices=[index_from_template(path) for path in template_paths]
archive_indices=[index_from_template(path) for path in archive_paths]
need(len(set(template_indices))==len(template_indices),"pending-template index collision")
need(len(set(archive_indices))==len(archive_indices),"archive index collision")
need(not (set(template_indices)&set(archive_indices)),"template/archive index overlap")
with (batch/"manifest.tsv").open(newline="") as handle:
    manifest_rows=list(csv.DictReader(handle,delimiter="\t"))
manifest={row["index"]:row for row in manifest_rows}
need(len(manifest)==10032 and len(manifest_rows)==10032,"manifest index cardinality mismatch")
need(set(template_indices)|set(archive_indices)=={int(index) for index in manifest},"template/archive manifest coverage mismatch")
with (batch/"submission.tsv").open(newline="") as handle:
    submission_reader=csv.DictReader(handle,delimiter="\t")
    required=["submitted_at","account","job_id","index","U","V","kx","ky","run_script","result","submission_kind","action_id","selection_rank"]
    need(submission_reader.fieldnames==required,"submission ledger schema mismatch")
    submissions=list(submission_reader)
with (batch/"repair_submission.tsv").open(newline="") as handle:
    repairs=list(csv.DictReader(handle,delimiter="\t"))
need(not claims,"ambiguous claims exist")
need(len(template_paths)+len(archive_paths)==10032,"template/archive inventory mismatch")
need(len(submissions)==len(archive_paths),"submission/archive count mismatch")
need(len({row["index"] for row in submissions})==len(submissions),"submission index collision")
need(len({row["job_id"] for row in submissions})==len(submissions),"submission job-id collision")
need({int(row["index"]) for row in submissions}==set(archive_indices),"submission/archive index-set mismatch")
need(all(row["account"] in {"ccsd","cnms"} for row in submissions),"submission account mismatch")
need(all(row["submission_kind"] in {"initial_launch","rebalance_10m","rebalance_20m","chain_refill","heartbeat_refill"} for row in submissions),"submission-kind mismatch")
need(all(row["action_id"] for row in submissions),"empty action id")
need(all(row["selection_rank"].isdigit() and int(row["selection_rank"])>=1 for row in submissions),"invalid selection rank")
need(not repairs,"repairs exist during initial handoff")
user=os.environ.get("USER")
need(bool(user),"USER is unset")
queue_proc=subprocess.run(
    ["squeue","-h","-r","-u",user,"-o","%i|%j|%a|%T"],
    text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
)
need(queue_proc.returncode==0,"squeue failed: "+queue_proc.stderr.strip())
exact=[]; all_account_state=Counter()
for line in queue_proc.stdout.splitlines():
    fields=line.split("|",3)
    if len(fields)!=4: continue
    job_id,job_name,account,state=(field.strip() for field in fields)
    all_account_state[(account,state)]+=1
    if job_name in job_names:
        exact.append({"job_id":job_id,"job_name":job_name,"account":account,"state":state})
pending_order=interleave(template_indices,manifest)
pending_order_text="".join(str(index)+"\n" for index in pending_order)
payload={
    "batch":str(batch),
    "reviewed_holding_package":str(remote_package),
    "external_decision_certificate":str(remote_certificate),
    "holding_package_certificate_revalidated":True,
    "manifest_sha256":sha(batch/"manifest.tsv"),
    "plan_sha256":provenance.get("plan_sha256"),
    "decision_certificate_sha256":sha(batch/"decision_certificate.json"),
    "preflight_stdout":preflight.stdout.strip(),
    "template_count":len(template_paths),
    "archive_count":len(archive_paths),
    "claim_count":len(claims),
    "submission_count":len(submissions),
    "submission_accounts":dict(sorted(Counter(row["account"] for row in submissions).items())),
    "submission_ledger_sha256":sha(batch/"submission.tsv"),
    "submission_rows_digest":canonical_rows_digest(submissions),
    "submission_rows":submissions,
    "pending_template_indices_interleaved":pending_order,
    "pending_template_order_sha256":hashlib.sha256(pending_order_text.encode()).hexdigest(),
    "repair_submission_count":len(repairs),
    "exact_name_activity":exact,
    "exact_name_account_state_counts":{
        account+"|"+state:count
        for (account,state),count in sorted(Counter((row["account"],row["state"]) for row in exact).items())
    },
    "all_user_account_state_counts":{
        account+"|"+state:count
        for (account,state),count in sorted(all_account_state.items())
    },
    "all_user_active_by_account":dict(sorted(Counter(account for (account,_),count in all_account_state.items() for _unused in range(count)).items())),
    "audit":audit,
}
print(json.dumps(payload,indent=2,sort_keys=True))
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_rows_digest(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def state_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("state_digest", None)
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def immutable_file_gate(path: Path, *, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise Refusal(f"missing {label}: {path}") from exc
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise Refusal(f"{label} is not a regular non-symlink file: {path}")
    if stat.S_IMODE(info.st_mode) != 0o444:
        raise Refusal(
            f"{label} mode is not 0444: {path} mode={stat.S_IMODE(info.st_mode):04o}"
        )
    if info.st_nlink != 1:
        raise Refusal(f"{label} link count is not one: {path} links={info.st_nlink}")
    return info


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def exclusive_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Create one durable 0444 JSON artifact without any replace window."""

    path = path.expanduser().resolve()
    if not path.parent.is_dir():
        raise Refusal(f"artifact parent does not exist: {path.parent}")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise Refusal(f"artifact output exists: {path}") from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write while creating immutable artifact")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    fsync_directory(path.parent)
    immutable_file_gate(path, label="new immutable artifact")


def run(
    command: list[str], *, input_text: str | None = None, timeout: int = 1800
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
        rendered = " ".join(shlex.quote(item) for item in command)
        raise Refusal(
            f"command failed ({proc.returncode}): {rendered}\n"
            f"stdout:\n{proc.stdout[-6000:]}\nstderr:\n{proc.stderr[-6000:]}"
        )
    return proc


def remote_python(host: str, program: str, arguments: tuple[str, ...]) -> str:
    remote_command = " ".join(
        shlex.quote(item) for item in ("/usr/bin/python3.11", "-", *arguments)
    )
    return run(["ssh", host, remote_command], input_text=program, timeout=1800).stdout


def verify_certificate(certificate: Path) -> dict[str, Any]:
    proc = run(
        [
            sys.executable,
            str(GENERATOR),
            "--verify-certificate",
            "--decision-certificate",
            str(certificate),
        ]
    )
    payload = json.loads(proc.stdout)
    if payload.get("mode") != "VERIFY_CERTIFICATE_ONLY":
        raise Refusal("generator did not enter certificate-only mode")
    if payload.get("decision") != "APPROVE_EXPANSION":
        raise Refusal("certificate does not approve expansion")
    return payload


def query_remote_state(
    *, remote_host: str, certificate_sha: str, receipt_tool_sha: str
) -> dict[str, Any]:
    remote_package = (
        REMOTE_ROOT
        / "reviewed_packages"
        / f"fullobs_861expand_fig4_cnn_20260821_{certificate_sha}"
    )
    remote_certificate = (
        REMOTE_ROOT
        / "decision_certificates"
        / f"fig4_cnn_861_{certificate_sha}.json"
    )
    payload = json.loads(
        remote_python(
            remote_host,
            REMOTE_STATE_PROGRAM,
            (
                str(REMOTE_BATCH),
                str(remote_package),
                str(remote_certificate),
                EXPECTED_MANIFEST_SHA256,
                certificate_sha,
                receipt_tool_sha,
            ),
        )
    )
    payload["remote_reviewed_holding_package"] = str(remote_package)
    payload["remote_external_decision_certificate"] = str(remote_certificate)
    return payload


def gate_remote_state(remote: dict[str, Any]) -> None:
    if remote.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise Refusal("remote manifest mismatch")
    if remote.get("plan_sha256") != EXPECTED_PLAN_SHA256:
        raise Refusal("remote semantic plan mismatch")
    if remote.get("holding_package_certificate_revalidated") is not True:
        raise Refusal("remote holding package/certificate was not revalidated")
    if remote.get("claim_count") != 0:
        raise Refusal("remote claim count is nonzero")
    if remote.get("repair_submission_count") != 0:
        raise Refusal("unexpected repair exists during handoff")
    if remote.get("template_count", -1) + remote.get("archive_count", -1) != EXPECTED_TARGETS:
        raise Refusal("remote template/archive total mismatch")
    if remote.get("submission_count") != remote.get("archive_count"):
        raise Refusal("remote submission/archive mismatch")
    rows = remote.get("submission_rows")
    if not isinstance(rows, list) or len(rows) != remote.get("submission_count"):
        raise Refusal("remote semantic submission-ledger cardinality mismatch")
    if canonical_rows_digest(rows) != remote.get("submission_rows_digest"):
        raise Refusal("remote semantic submission-ledger digest mismatch")
    pending_order = remote.get("pending_template_indices_interleaved")
    if not isinstance(pending_order, list) or len(pending_order) != remote.get("template_count"):
        raise Refusal("remote interleaved pending-template order mismatch")
    if len(set(pending_order)) != len(pending_order):
        raise Refusal("remote interleaved pending-template order collides")
    pending_text = "".join(f"{int(index)}\n" for index in pending_order)
    if hashlib.sha256(pending_text.encode()).hexdigest() != remote.get(
        "pending_template_order_sha256"
    ):
        raise Refusal("remote interleaved pending-template digest mismatch")
    audit = remote.get("audit")
    if not isinstance(audit, dict) or audit.get("total_targets") != EXPECTED_TARGETS:
        raise Refusal("remote audit target count mismatch")
    if audit.get("scheduler_errors"):
        raise Refusal("remote scheduler audit failed")
    if audit.get("warnings"):
        raise Refusal(f"remote audit warnings: {audit['warnings']}")
    for key, value in audit.get("anomalies", {}).items():
        if value:
            raise Refusal(f"remote audit anomaly {key}")
    bad = sum(
        int(audit.get("counts", {}).get(name, 0))
        for name in ("FAILED", "INCOMPLETE", "INVALID", "MISSING", "UNKNOWN")
    )
    if bad:
        raise Refusal("remote audit has invalid or failed targets")
    if int(audit.get("counts", {}).get("UNSUBMITTED", 0)) != remote.get(
        "template_count"
    ):
        raise Refusal("remote audit/template UNSUBMITTED count mismatch")
    pins = audit.get("pin_audit", [])
    if len(pins) != EXPECTED_PINS or not all(item.get("match") for item in pins):
        raise Refusal("remote runtime pin audit mismatch")


def observation_from_remote(remote: dict[str, Any]) -> dict[str, Any]:
    exact_counts = remote.get("exact_name_account_state_counts", {})
    pending_by_account = {
        account: int(exact_counts.get(f"{account}|PENDING", 0)) for account in ACCOUNTS
    }
    running_by_account = {
        account: int(exact_counts.get(f"{account}|RUNNING", 0))
        + int(exact_counts.get(f"{account}|COMPLETING", 0))
        for account in ACCOUNTS
    }
    Q = int(remote["audit"]["counts"].get("UNSUBMITTED", 0))
    P = sum(pending_by_account.values())
    observation = {
        "P": P,
        "Q": Q,
        "B": P + Q,
        "Rc": running_by_account["ccsd"],
        "Rn": running_by_account["cnms"],
        "pending_by_account": pending_by_account,
        "running_or_completing_by_account": running_by_account,
        "all_user_active_by_account": {
            account: int(remote.get("all_user_active_by_account", {}).get(account, 0))
            for account in ACCOUNTS
        },
        "exact_name_account_state_counts": remote.get(
            "exact_name_account_state_counts", {}
        ),
    }
    if observation["Q"] != remote.get("template_count"):
        raise Refusal("policy observation Q differs from pending-template count")
    return observation


def decision_counts(observation: dict[str, Any]) -> dict[str, int]:
    return {
        "pending_ccsd": int(observation["pending_by_account"]["ccsd"]),
        "pending_cnms": int(observation["pending_by_account"]["cnms"]),
        "running_or_completing_ccsd": int(
            observation["running_or_completing_by_account"]["ccsd"]
        ),
        "running_or_completing_cnms": int(
            observation["running_or_completing_by_account"]["cnms"]
        ),
    }


def compute_policy(
    *,
    phase: str,
    observation: dict[str, Any],
    previous_observation: dict[str, Any] | None,
    account_cap: int,
    interleaved_unsubmitted_indices: list[int],
) -> dict[str, Any]:
    """Pure campaign-specific add-only policy, replayed during verification."""

    if phase not in PHASES:
        raise Refusal("policy phase mismatch")
    if account_cap < 1:
        raise Refusal("account cap must be positive")
    for key in ("P", "Q", "B", "Rc", "Rn"):
        if not isinstance(observation.get(key), int) or observation[key] < 0:
            raise Refusal(f"invalid policy input {key}")
    if observation["B"] != observation["P"] + observation["Q"]:
        raise Refusal("policy backlog B is not P+Q")
    if len(interleaved_unsubmitted_indices) != observation["Q"]:
        raise Refusal("interleaved selection cardinality does not equal Q")
    if len(set(interleaved_unsubmitted_indices)) != len(
        interleaved_unsubmitted_indices
    ):
        raise Refusal("interleaved selection contains duplicate indices")

    if phase == "initial_launch":
        counts_changed = False
        if previous_observation is not None:
            raise Refusal("initial policy unexpectedly has a previous observation")
        if observation["P"] != 0 or observation["Rc"] + observation["Rn"] != 0:
            raise Refusal("initial policy requires zero exact-name queue activity")
        if observation["Q"] != EXPECTED_TARGETS:
            raise Refusal("initial policy requires all 10,032 templates unsubmitted")
        target_account: str | None = "ccsd"
        requested_n = observation["Q"]
        branch = "initial_primary_ccsd_fill"
    else:
        if previous_observation is None:
            raise Refusal("rebalance policy lacks previous observation")
        current_counts = decision_counts(observation)
        previous_counts = decision_counts(previous_observation)
        counts_changed = any(
            current_counts[key] != previous_counts[key] for key in DECISION_COUNT_KEYS
        )
        target_account = "cnms"
        if observation["B"] <= 10:
            requested_n = 0
            branch = "backlog_at_most_10"
        elif observation["Q"] == 0:
            requested_n = 0
            branch = "no_unsubmitted_templates"
        elif phase == "rebalance_20m" and not counts_changed:
            requested_n = 0
            branch = "no_pending_or_running_count_change"
        elif phase == "rebalance_10m" and observation["Rc"] + observation["Rn"] == 0:
            requested_n = 0
            branch = "zero_running_keep_primary"
        elif observation["Rn"] == 0:
            if phase == "rebalance_10m" and observation["Rc"] > 0:
                requested_n = min(10, observation["Q"])
                branch = "seed_cnms_probe"
            else:
                requested_n = 0
                branch = "cnms_probe_not_running"
        else:
            denominator = observation["Rc"] + observation["Rn"]
            if denominator <= 0:
                raise Refusal("positive Rn with nonpositive running denominator")
            requested_n = int(observation["Q"] * observation["Rn"] / denominator + 0.5)
            branch = "running_ratio_cnms_fill"
        if requested_n == 0:
            target_account = None

    capacity_account = target_account or ("ccsd" if phase == "initial_launch" else "cnms")
    current_for_account = int(
        observation["all_user_active_by_account"].get(capacity_account, 0)
    )
    capacity = max(0, account_cap - current_for_account)
    effective_n = min(requested_n, observation["Q"], capacity)
    selected = [int(index) for index in interleaved_unsubmitted_indices[:effective_n]]
    return {
        "algorithm": POLICY_ALGORITHM,
        "inputs": {
            "P": observation["P"],
            "Q": observation["Q"],
            "B": observation["B"],
            "Rc": observation["Rc"],
            "Rn": observation["Rn"],
            "pending_by_account": observation["pending_by_account"],
            "running_or_completing_by_account": observation[
                "running_or_completing_by_account"
            ],
            "all_user_active_by_account": observation["all_user_active_by_account"],
            "account_cap": account_cap,
            "capacity_account": capacity_account,
            "capacity": capacity,
        },
        "counts_changed": counts_changed,
        "rule_branch": branch,
        "target_account": target_account,
        "requested_n": requested_n,
        "effective_n": effective_n,
        "selected_manifest_indices": selected,
    }


def expected_allowed_refill_accounts(submission_accounts: dict[str, Any]) -> list[str]:
    unknown = set(submission_accounts) - set(ACCOUNTS)
    if unknown:
        raise Refusal(f"unknown submission accounts in receipt: {sorted(unknown)}")
    allowed = ["ccsd"]
    if int(submission_accounts.get("cnms", 0)) > 0:
        allowed.append("cnms")
    return allowed


def validate_policy_state_payload(payload: dict[str, Any]) -> None:
    if payload.get("artifact_type") != "fig4_cnn_861_handoff_policy_state":
        raise Refusal("policy-state artifact type mismatch")
    if payload.get("schema_version") != POLICY_STATE_SCHEMA_VERSION:
        raise Refusal("policy-state schema mismatch")
    observed_digest = payload.get("state_digest")
    if not isinstance(observed_digest, str) or observed_digest != state_digest(payload):
        raise Refusal("policy-state digest mismatch")
    phase = payload.get("phase")
    if phase not in PHASES:
        raise Refusal("policy-state phase mismatch")
    if payload.get("certificate_decision") != "APPROVE_EXPANSION":
        raise Refusal("policy state does not bind APPROVE_EXPANSION")
    if payload.get("standing_user_authorization") is not True:
        raise Refusal("policy-state standing-authorization flag mismatch")
    if payload.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise Refusal("policy-state manifest mismatch")
    if payload.get("plan_sha256") != EXPECTED_PLAN_SHA256:
        raise Refusal("policy-state plan mismatch")
    if payload.get("holding_package_certificate_revalidated") is not True:
        raise Refusal("policy-state holding-package/certificate flag mismatch")
    if payload.get("runtime_pins_matching") != EXPECTED_PINS:
        raise Refusal("policy-state runtime-pin count mismatch")
    if payload.get("handoff_receipt_tool_sha256") != sha256(SCRIPT):
        raise Refusal("policy-state receipt-tool hash mismatch")
    if payload.get("claim_count") != 0 or payload.get("repair_submission_count") != 0:
        raise Refusal("policy state records a claim or repair")
    observation = payload.get("observation")
    order = payload.get("interleaved_unsubmitted_indices")
    if not isinstance(observation, dict) or not isinstance(order, list):
        raise Refusal("policy state lacks observation or interleaved order")
    order_text = "".join(f"{int(index)}\n" for index in order)
    if hashlib.sha256(order_text.encode()).hexdigest() != payload.get(
        "interleaved_unsubmitted_indices_sha256"
    ):
        raise Refusal("policy-state interleaved-order hash mismatch")
    previous_observation = payload.get("previous_observation")
    recomputed = compute_policy(
        phase=phase,
        observation=observation,
        previous_observation=previous_observation,
        account_cap=int(payload.get("account_cap", 0)),
        interleaved_unsubmitted_indices=[int(index) for index in order],
    )
    if payload.get("policy") != recomputed:
        raise Refusal("policy-state decision does not recompute exactly")
    ledger = payload.get("submission_ledger_before")
    if not isinstance(ledger, dict):
        raise Refusal("policy-state pre-action ledger binding is missing")
    if not isinstance(ledger.get("row_count"), int) or ledger["row_count"] < 0:
        raise Refusal("policy-state pre-action ledger count is invalid")
    for key in ("file_sha256", "semantic_rows_sha256"):
        value = ledger.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise Refusal(f"policy-state pre-action ledger {key} is invalid")


def validate_receipt(payload: dict[str, Any]) -> None:
    if payload.get("artifact_type") != "fig4_cnn_861_handoff_receipt":
        raise Refusal("receipt artifact type mismatch")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise Refusal("receipt schema mismatch")
    observed = payload.get("state_digest")
    if not isinstance(observed, str) or observed != state_digest(payload):
        raise Refusal("receipt state digest mismatch")
    if payload.get("phase") not in PHASES:
        raise Refusal("receipt phase mismatch")
    if payload.get("certificate_decision") != "APPROVE_EXPANSION":
        raise Refusal("receipt does not bind APPROVE_EXPANSION")
    if payload.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise Refusal("receipt manifest hash mismatch")
    if payload.get("plan_sha256") != EXPECTED_PLAN_SHA256:
        raise Refusal("receipt plan hash mismatch")
    if payload.get("standing_user_authorization") is not True:
        raise Refusal("receipt standing-authorization flag mismatch")
    if payload.get("holding_package_certificate_revalidated") is not True:
        raise Refusal("receipt holding-package/certificate flag mismatch")
    if payload.get("claim_count") != 0 or payload.get("repair_submission_count") != 0:
        raise Refusal("receipt records a claim or repair")
    if payload.get("runtime_pins_matching") != EXPECTED_PINS:
        raise Refusal("receipt runtime-pin count mismatch")
    if payload.get("handoff_receipt_tool_sha256") != sha256(SCRIPT):
        raise Refusal("receipt receipt-tool hash mismatch")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or policy.get("algorithm") != POLICY_ALGORITHM:
        raise Refusal("receipt policy record mismatch")
    if not isinstance(policy.get("counts_changed"), bool):
        raise Refusal("receipt lacks Boolean counts_changed")
    requested = policy.get("requested_n")
    effective = policy.get("effective_n")
    if not isinstance(requested, int) or not isinstance(effective, int):
        raise Refusal("receipt requested/effective N is invalid")
    if not (0 <= effective <= requested):
        raise Refusal("receipt effective N exceeds requested N")
    action = payload.get("handoff_action")
    if not isinstance(action, dict):
        raise Refusal("receipt handoff action is missing")
    if action.get("submission_kind") != payload["phase"]:
        raise Refusal("receipt action phase mismatch")
    if action.get("action_id") != payload.get("policy_state_digest"):
        raise Refusal("receipt action ID differs from policy-state digest")
    if action.get("target_account") != policy.get("target_account"):
        raise Refusal("receipt action target account differs from policy")
    if action.get("selection_is_interleaved") is not True:
        raise Refusal("receipt action lacks interleaved-selection proof")
    indices = action.get("selected_manifest_indices")
    jobs = action.get("selected_job_ids")
    if not isinstance(indices, list) or not isinstance(jobs, list):
        raise Refusal("receipt selected indices/job IDs are invalid")
    if len(indices) != effective or len(jobs) != effective:
        raise Refusal("receipt selected action cardinality mismatch")
    if indices != policy.get("selected_manifest_indices"):
        raise Refusal("receipt selected indices differ from recomputed policy")
    if len(set(indices)) != len(indices) or len(set(jobs)) != len(jobs):
        raise Refusal("receipt action index/job-id collision")
    if not all(str(job).isdigit() for job in jobs):
        raise Refusal("receipt action contains a nonnumeric Slurm job ID")
    delta = payload.get("bound_submission_ledger_delta")
    if not isinstance(delta, dict):
        raise Refusal("receipt ledger delta is missing")
    if delta.get("action_id") != action.get("action_id"):
        raise Refusal("receipt ledger-delta action ID mismatch")
    if delta.get("action_row_count") != effective:
        raise Refusal("receipt action-row count differs from effective N")
    before_count = delta.get("before_row_count")
    after_count = delta.get("after_row_count")
    if (
        not isinstance(before_count, int)
        or not isinstance(after_count, int)
        or before_count < 0
        or after_count < before_count
    ):
        raise Refusal("receipt ledger row counts are invalid")
    if delta.get("rows_appended") != after_count - before_count:
        raise Refusal("receipt ledger appended-row arithmetic mismatch")
    if delta["rows_appended"] < effective:
        raise Refusal("receipt ledger delta is smaller than its action")
    expected_accounts = expected_allowed_refill_accounts(
        payload.get("submission_accounts", {})
    )
    if payload.get("allowed_refill_accounts") != expected_accounts:
        raise Refusal("receipt allowed-refill-account set mismatch")
    terminal = payload["phase"] == "rebalance_20m"
    if payload.get("rebalance_cycle_complete") is not terminal:
        raise Refusal("receipt rebalance-completion flag mismatch")
    if payload.get("eligible_for_two_hour_expansion_heartbeat") is not terminal:
        raise Refusal("receipt heartbeat-eligibility flag mismatch")


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Refusal(f"{label} is not a JSON object: {path}")
    return payload


def validate_policy_state(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    immutable_file_gate(path, label="policy-state artifact")
    payload = load_json(path, label="policy-state artifact")
    validate_policy_state_payload(payload)
    previous_path_text = payload.get("previous_receipt_path")
    predecessor = PREDECESSOR.get(payload["phase"])
    if predecessor is None:
        if previous_path_text is not None or payload.get("previous_receipt_sha256") is not None:
            raise Refusal("initial policy state unexpectedly has a predecessor")
        if payload.get("previous_observation") is not None:
            raise Refusal("initial policy state unexpectedly has a prior observation")
    else:
        if not isinstance(previous_path_text, str):
            raise Refusal("policy-state predecessor path is missing")
        previous_path = Path(previous_path_text).expanduser().resolve()
        previous = validate_receipt_chain(previous_path)
        if previous.get("phase") != predecessor:
            raise Refusal("policy-state predecessor phase mismatch")
        if sha256(previous_path) != payload.get("previous_receipt_sha256"):
            raise Refusal("policy-state predecessor file hash mismatch")
        if previous.get("state_digest") != payload.get("previous_state_digest"):
            raise Refusal("policy-state predecessor digest mismatch")
        if previous.get("certificate_sha256") != payload.get("certificate_sha256"):
            raise Refusal("policy-state predecessor certificate mismatch")
        if previous.get("observation") != payload.get("previous_observation"):
            raise Refusal("policy-state prior observation mismatch")
        elapsed = (
            dt.datetime.fromisoformat(payload["created_at"])
            - dt.datetime.fromisoformat(previous["created_at"])
        ).total_seconds()
        if elapsed < MIN_CHECKPOINT_SECONDS:
            raise Refusal(
                f"policy-state checkpoint is early: elapsed_seconds={elapsed:.1f}"
            )
    return payload


def validate_receipt_chain(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    immutable_file_gate(path, label="handoff receipt")
    payload = load_json(path, label="handoff receipt")
    validate_receipt(payload)

    policy_path_text = payload.get("policy_state_path")
    if not isinstance(policy_path_text, str):
        raise Refusal("receipt policy-state path is missing")
    policy_path = Path(policy_path_text).expanduser().resolve()
    policy = validate_policy_state(policy_path)
    if sha256(policy_path) != payload.get("policy_state_sha256"):
        raise Refusal("receipt policy-state file hash mismatch")
    if policy.get("state_digest") != payload.get("policy_state_digest"):
        raise Refusal("receipt policy-state digest mismatch")
    if policy.get("phase") != payload.get("phase"):
        raise Refusal("receipt/policy-state phase mismatch")
    if policy.get("certificate_sha256") != payload.get("certificate_sha256"):
        raise Refusal("receipt/policy-state certificate mismatch")
    if policy.get("policy") != payload.get("policy"):
        raise Refusal("receipt policy differs from its policy-state artifact")
    if policy.get("observation") != payload.get("policy_observation"):
        raise Refusal("receipt policy observation mismatch")
    if dt.datetime.fromisoformat(policy["created_at"]) > dt.datetime.fromisoformat(
        payload["created_at"]
    ):
        raise Refusal("receipt predates its policy-state capture")

    predecessor = PREDECESSOR.get(payload["phase"])
    previous_path_text = payload.get("previous_receipt_path")
    if predecessor is None:
        if previous_path_text is not None or payload.get("previous_receipt_sha256") is not None:
            raise Refusal("initial receipt unexpectedly has a predecessor")
        return payload
    if not isinstance(previous_path_text, str):
        raise Refusal("receipt predecessor path is missing")
    previous_path = Path(previous_path_text).expanduser().resolve()
    previous = validate_receipt_chain(previous_path)
    if sha256(previous_path) != payload.get("previous_receipt_sha256"):
        raise Refusal("receipt predecessor file hash mismatch")
    if previous["phase"] != predecessor:
        raise Refusal("receipt predecessor phase mismatch")
    if previous["state_digest"] != payload.get("previous_state_digest"):
        raise Refusal("receipt predecessor state digest mismatch")
    if previous["certificate_sha256"] != payload.get("certificate_sha256"):
        raise Refusal("receipt-chain certificate mismatch")
    elapsed = (
        dt.datetime.fromisoformat(payload["created_at"])
        - dt.datetime.fromisoformat(previous["created_at"])
    ).total_seconds()
    if elapsed < MIN_CHECKPOINT_SECONDS:
        raise Refusal(f"receipt-chain checkpoint is early: elapsed_seconds={elapsed:.1f}")
    return payload


def load_predecessor(
    path: Path | None, phase: str, certificate_sha: str
) -> dict[str, Any]:
    if phase not in PREDECESSOR:
        if path:
            raise Refusal("initial launch must not specify a predecessor receipt")
        return {}
    if not path:
        raise Refusal(f"{phase} requires --previous-receipt")
    previous_path = path.expanduser().resolve()
    previous = validate_receipt_chain(previous_path)
    if previous["phase"] != PREDECESSOR[phase]:
        raise Refusal("receipt predecessor phase mismatch")
    if previous.get("certificate_sha256") != certificate_sha:
        raise Refusal("receipt predecessor certificate mismatch")
    created = dt.datetime.fromisoformat(previous["created_at"])
    elapsed = (dt.datetime.now().astimezone() - created).total_seconds()
    if elapsed < MIN_CHECKPOINT_SECONDS:
        raise Refusal(f"checkpoint is early: elapsed_seconds={elapsed:.1f}")
    return previous


def certificate_context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], str, str]:
    certificate = args.certificate.expanduser().resolve()
    if not certificate.is_file():
        raise Refusal(f"missing certificate: {certificate}")
    certificate_payload = verify_certificate(certificate)
    certificate_sha = sha256(certificate)
    receipt_tool_sha = sha256(SCRIPT)
    return certificate, certificate_payload, certificate_sha, receipt_tool_sha


def capture_policy_state(args: argparse.Namespace) -> dict[str, Any]:
    certificate, certificate_payload, certificate_sha, receipt_tool_sha = (
        certificate_context(args)
    )
    previous_path = (
        args.previous_receipt.expanduser().resolve() if args.previous_receipt else None
    )
    previous = load_predecessor(previous_path, args.phase, certificate_sha)
    remote = query_remote_state(
        remote_host=args.remote_host,
        certificate_sha=certificate_sha,
        receipt_tool_sha=receipt_tool_sha,
    )
    gate_remote_state(remote)
    if remote.get("decision_certificate_sha256") != certificate_sha:
        raise Refusal("remote batch certificate differs from local certificate")
    if args.phase == "initial_launch" and remote.get("submission_count") != 0:
        raise Refusal("initial policy capture requires an empty submission ledger")
    observation = observation_from_remote(remote)
    order = [int(index) for index in remote["pending_template_indices_interleaved"]]
    previous_observation = previous.get("observation") if previous else None
    policy = compute_policy(
        phase=args.phase,
        observation=observation,
        previous_observation=previous_observation,
        account_cap=args.account_cap,
        interleaved_unsubmitted_indices=order,
    )
    if args.phase == "initial_launch" and policy["effective_n"] < 1:
        raise Refusal("initial primary fill has zero effective capacity")
    order_text = "".join(f"{index}\n" for index in order)
    payload: dict[str, Any] = {
        "artifact_type": "fig4_cnn_861_handoff_policy_state",
        "schema_version": POLICY_STATE_SCHEMA_VERSION,
        "phase": args.phase,
        "created_at": dt.datetime.now().astimezone().isoformat(),
        "standing_user_authorization": True,
        "certificate_decision": certificate_payload["decision"],
        "certificate_sha256": certificate_sha,
        "certificate_path": str(certificate),
        "remote_host": args.remote_host,
        "remote_batch": str(REMOTE_BATCH),
        "remote_reviewed_holding_package": remote[
            "remote_reviewed_holding_package"
        ],
        "remote_external_decision_certificate": remote[
            "remote_external_decision_certificate"
        ],
        "holding_package_certificate_revalidated": remote[
            "holding_package_certificate_revalidated"
        ],
        "manifest_sha256": remote["manifest_sha256"],
        "plan_sha256": remote["plan_sha256"],
        "handoff_receipt_tool_sha256": receipt_tool_sha,
        "previous_receipt_path": str(previous_path) if previous_path else None,
        "previous_receipt_sha256": sha256(previous_path) if previous_path else None,
        "previous_state_digest": previous.get("state_digest") if previous else None,
        "previous_observation": previous_observation,
        "account_cap": args.account_cap,
        "observation": observation,
        "policy": policy,
        "interleaved_unsubmitted_indices": order,
        "interleaved_unsubmitted_indices_sha256": hashlib.sha256(
            order_text.encode()
        ).hexdigest(),
        "submission_ledger_before": {
            "file_sha256": remote["submission_ledger_sha256"],
            "semantic_rows_sha256": remote["submission_rows_digest"],
            "row_count": remote["submission_count"],
        },
        "submission_accounts_before": remote["submission_accounts"],
        "template_count": remote["template_count"],
        "archive_count": remote["archive_count"],
        "claim_count": remote["claim_count"],
        "repair_submission_count": remote["repair_submission_count"],
        "runtime_pins_matching": EXPECTED_PINS,
    }
    payload["state_digest"] = state_digest(payload)
    validate_policy_state_payload(payload)
    exclusive_write_json(args.output, payload)
    return payload


def validate_ledger_action(
    *, policy_state: dict[str, Any], remote: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = policy_state["submission_ledger_before"]
    before_count = int(before["row_count"])
    rows = remote["submission_rows"]
    if len(rows) < before_count:
        raise Refusal("submission ledger shrank after policy capture")
    if canonical_rows_digest(rows[:before_count]) != before["semantic_rows_sha256"]:
        raise Refusal("pre-action submission ledger is not an unchanged prefix")
    delta_rows = rows[before_count:]
    action_id = policy_state["state_digest"]
    action_rows = [row for row in delta_rows if row.get("action_id") == action_id]
    effective = int(policy_state["policy"]["effective_n"])
    if len(action_rows) != effective:
        raise Refusal(
            "policy action ledger cardinality mismatch: "
            f"observed={len(action_rows)} expected={effective}"
        )
    if any(row.get("submission_kind") != policy_state["phase"] for row in action_rows):
        raise Refusal("policy action ledger kind mismatch")
    target = policy_state["policy"]["target_account"]
    if any(row.get("account") != target for row in action_rows):
        raise Refusal("policy action ledger account mismatch")
    try:
        ranked = sorted(action_rows, key=lambda row: int(row["selection_rank"]))
    except (KeyError, ValueError) as exc:
        raise Refusal("policy action has invalid selection rank") from exc
    if [int(row["selection_rank"]) for row in ranked] != list(range(1, effective + 1)):
        raise Refusal("policy action selection ranks are not contiguous")
    indices = [int(row["index"]) for row in ranked]
    expected_indices = policy_state["policy"]["selected_manifest_indices"]
    if indices != expected_indices:
        raise Refusal("policy action did not use the deterministic interleaved selection")
    job_ids = [row["job_id"] for row in ranked]
    if len(set(job_ids)) != len(job_ids) or not all(job.isdigit() for job in job_ids):
        raise Refusal("policy action job IDs are invalid")
    delta = {
        "before_file_sha256": before["file_sha256"],
        "before_semantic_rows_sha256": before["semantic_rows_sha256"],
        "before_row_count": before_count,
        "after_file_sha256": remote["submission_ledger_sha256"],
        "after_semantic_rows_sha256": remote["submission_rows_digest"],
        "after_row_count": len(rows),
        "rows_appended": len(delta_rows),
        "appended_rows_semantic_sha256": canonical_rows_digest(delta_rows),
        "action_id": action_id,
        "action_row_count": len(action_rows),
        "action_rows_semantic_sha256": canonical_rows_digest(ranked),
    }
    action = {
        "submission_kind": policy_state["phase"],
        "action_id": action_id,
        "target_account": target,
        "selected_manifest_indices": indices,
        "selected_job_ids": job_ids,
        "selection_is_interleaved": True,
    }
    return delta, action


def write_receipt(args: argparse.Namespace) -> dict[str, Any]:
    certificate, certificate_payload, certificate_sha, receipt_tool_sha = (
        certificate_context(args)
    )
    policy_path = args.policy_state.expanduser().resolve()
    policy_state = validate_policy_state(policy_path)
    if policy_state["phase"] != args.phase:
        raise Refusal("policy-state phase differs from requested receipt phase")
    if policy_state["certificate_sha256"] != certificate_sha:
        raise Refusal("policy-state certificate differs from requested certificate")
    previous_path = (
        args.previous_receipt.expanduser().resolve() if args.previous_receipt else None
    )
    previous = load_predecessor(previous_path, args.phase, certificate_sha)
    expected_policy_previous = policy_state.get("previous_receipt_path")
    if expected_policy_previous != (str(previous_path) if previous_path else None):
        raise Refusal("receipt predecessor differs from policy-state predecessor")
    remote = query_remote_state(
        remote_host=args.remote_host,
        certificate_sha=certificate_sha,
        receipt_tool_sha=receipt_tool_sha,
    )
    gate_remote_state(remote)
    if remote.get("decision_certificate_sha256") != certificate_sha:
        raise Refusal("remote batch certificate differs from local certificate")
    delta, action = validate_ledger_action(policy_state=policy_state, remote=remote)
    if remote.get("submission_count", 0) < 1:
        raise Refusal("authorized initial fill has not recorded a submission")
    observation = observation_from_remote(remote)
    allowed_accounts = expected_allowed_refill_accounts(remote["submission_accounts"])
    payload: dict[str, Any] = {
        "artifact_type": "fig4_cnn_861_handoff_receipt",
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "phase": args.phase,
        "created_at": dt.datetime.now().astimezone().isoformat(),
        "standing_user_authorization": True,
        "certificate_decision": certificate_payload["decision"],
        "certificate_sha256": certificate_sha,
        "certificate_path": str(certificate),
        "remote_host": args.remote_host,
        "remote_batch": str(REMOTE_BATCH),
        "remote_reviewed_holding_package": remote[
            "remote_reviewed_holding_package"
        ],
        "remote_external_decision_certificate": remote[
            "remote_external_decision_certificate"
        ],
        "holding_package_certificate_revalidated": remote[
            "holding_package_certificate_revalidated"
        ],
        "manifest_sha256": remote["manifest_sha256"],
        "plan_sha256": remote["plan_sha256"],
        "handoff_receipt_tool_sha256": receipt_tool_sha,
        "policy_state_path": str(policy_path),
        "policy_state_sha256": sha256(policy_path),
        "policy_state_digest": policy_state["state_digest"],
        "policy_observation": policy_state["observation"],
        "policy": policy_state["policy"],
        "handoff_action": action,
        "bound_submission_ledger_delta": delta,
        "previous_receipt_path": str(previous_path) if previous_path else None,
        "previous_receipt_sha256": sha256(previous_path) if previous_path else None,
        "previous_state_digest": previous.get("state_digest") if previous else None,
        "observation": observation,
        "template_count": remote["template_count"],
        "archive_count": remote["archive_count"],
        "claim_count": remote["claim_count"],
        "submission_count": remote["submission_count"],
        "submission_accounts": remote["submission_accounts"],
        "repair_submission_count": remote["repair_submission_count"],
        "exact_name_account_state_counts": remote[
            "exact_name_account_state_counts"
        ],
        "all_user_account_state_counts": remote["all_user_account_state_counts"],
        "audit_counts": remote["audit"]["counts"],
        "runtime_pins_matching": EXPECTED_PINS,
        "allowed_refill_accounts": allowed_accounts,
        "rebalance_cycle_complete": args.phase == "rebalance_20m",
        "eligible_for_two_hour_expansion_heartbeat": args.phase == "rebalance_20m",
    }
    payload["state_digest"] = state_digest(payload)
    validate_receipt(payload)
    exclusive_write_json(args.output, payload)
    # Re-read the durable bytes and the entire recursive chain before reporting
    # success.  Terminal heartbeat eligibility is therefore never asserted from
    # an in-memory payload alone.
    return validate_receipt_chain(args.output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--verify-receipt", type=Path)
    modes.add_argument("--verify-policy-state", type=Path)
    modes.add_argument("--capture-policy-state", action="store_true")
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--previous-receipt", type=Path)
    parser.add_argument("--policy-state", type=Path)
    parser.add_argument("--account-cap", type=int, default=150)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remote-host", default="cades")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.verify_receipt:
            payload = validate_receipt_chain(args.verify_receipt)
            print(
                json.dumps(
                    {
                        "mode": "VERIFY_HANDOFF_RECEIPT_ONLY",
                        "phase": payload["phase"],
                        "state_digest": payload["state_digest"],
                        "eligible_for_two_hour_expansion_heartbeat": payload[
                            "eligible_for_two_hour_expansion_heartbeat"
                        ],
                        "allowed_refill_accounts": payload[
                            "allowed_refill_accounts"
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.verify_policy_state:
            payload = validate_policy_state(args.verify_policy_state)
            print(
                json.dumps(
                    {
                        "mode": "VERIFY_HANDOFF_POLICY_STATE_ONLY",
                        "phase": payload["phase"],
                        "state_digest": payload["state_digest"],
                        "policy": payload["policy"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if not args.certificate or not args.phase or not args.output:
            raise Refusal(
                "artifact creation requires --certificate, --phase, and --output"
            )
        if args.capture_policy_state:
            if args.policy_state:
                raise Refusal("policy capture does not accept --policy-state")
            payload = capture_policy_state(args)
        else:
            if not args.policy_state:
                raise Refusal("receipt creation requires --policy-state")
            payload = write_receipt(args)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
