#!/usr/bin/env python3
"""Build a staging-only Fig. 4 from every completed pointwise C_NN input.

The input contract is deliberately narrow.  It accepts one immutable,
replica-resolved 13-case P25 bundle (325 selected rows, exactly one result per
twist) and joins it to the four reviewed U=40 full-F861 controls.  To remain
compatible with the current manuscript text and caption, each Mott curve keeps
the observed Green-function-zero coefficient at V=0 as its sole anchor and
uses the independently measured fullobs drift,

    C_eff(U,V) = s_obs(U,0)/4 + C_NN(U,V) - C_NN(U,0),

inside the signed Eq. (10) law

    s_NN = 1 + (2U-V)/(U-V) (2 C_NN - 1/2)

at 17 nodes: six U=20, five U=40, and six U=80 points.  Every drift uses a
matched estimator: P25 minus P25, or F861 minus F861.  In particular U=40,V=6
uses the reviewed P25 projection of the U=40,V=0 full wedge, while U=40 at
V=4,8,9 uses the F861 V=0 control.  The old constant-C axis-anchor law is
retained only as a diagnostic baseline.

This program has no promotion path.  It writes only to a fresh directory
below ``tmp/`` and never edits ``figures/``, ``manuscript/``, ``results/``, or
Overleaf.  ``--publication-candidate`` removes the staging watermark but does
not relax that confinement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_fig4_cnn_campaign as legacy_analysis
import build_scale_and_transition_figure as legacy_fig4


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]
TMP = ROOT / "tmp"

P25_SUMMARY_BASENAME = "fig4_cnn_p25_13case_summary.csv"
P25_RAW_BASENAME = "fig4_cnn_p25_13case_raw_validation.csv"
P25_17NODE_BASENAME = "fig4_cnn_17node_CNN_inputs.csv"
P25_CONTROL_BASENAME = "fig4_cnn_u40_controls_p25_vs_full861.csv"
P25_MATCHED_DRIFT_BASENAME = "fig4_cnn_u40_sampling_matched_drift.csv"
P25_PROVENANCE_BASENAME = "provenance.json"
P25_LEDGER_BASENAME = "SNAPSHOT_SHA256SUMS"

U40_SUMMARY = ROOT / "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv"
U40_ROWS = ROOT / "results/fullobs_U40_observable_rows_20260723_091307.csv.gz"
GZ_POINTS = ROOT / "results/pnas_scale_rule_points_eta0p05.csv"
BOUNDARY_SOURCE = ROOT / "results/transition_brackets_combined_U2_U40.csv"

REVIEWED_INPUT_SHA256 = {
    U40_SUMMARY: "81d45fe4ea75dee1e121dcb22963652c2253cf5e45a61094c3e153f98e4dd5e4",
    U40_ROWS: "81f50b31cffa6581b27f52b9aced792b9d6cacbb64950471594693473194a5d9",
    GZ_POINTS: "44755fe1c15efce59903044f31ffa0c794da8d9e85f330f89d3683e6ae609c0a",
    BOUNDARY_SOURCE: "22931d887dba76a4b523d3dadeb60378650f75f66dfb4c646a921b57e9aebd27",
}

P25_CASES = (
    (20.0, 0.0),
    (20.0, 2.0),
    (20.0, 3.0),
    (20.0, 4.0),
    (20.0, 4.5),
    (20.0, 5.0),
    (40.0, 6.0),
    (80.0, 0.0),
    (80.0, 4.0),
    (80.0, 8.0),
    (80.0, 12.0),
    (80.0, 16.0),
    (80.0, 18.0),
)
U40_CONTROL_CASES = ((40.0, 0.0), (40.0, 4.0), (40.0, 8.0), (40.0, 9.0))
POINTWISE_CASES = tuple(sorted(P25_CASES + U40_CONTROL_CASES))
REPAIRED_TWISTS = {
    (80.0, 12.0, 3, 3),
    (80.0, 12.0, 17, 17),
    (80.0, 16.0, 27, 30),
    (80.0, 18.0, 15, 23),
    (80.0, 18.0, 4, 38),
}
EXPECTED_TWISTS = tuple(legacy_analysis.EXPECTED_TWISTS)

HEX64 = re.compile(r"^[0-9a-f]{64}$")
P25_SUMMARY_REQUIRED = {
    "U",
    "V",
    "r",
    "complete_twists",
    "C_NN",
    "C_NN_min",
    "C_NN_max",
    "C_NN_spread",
    "C_NN_population_std_diagnostic",
    "eq10_factor",
    "s_eq10_signed",
}
P25_RAW_REQUIRED = {
    "U",
    "V",
    "kx",
    "ky",
    "C1_NN",
    "source_role",
    "source_job_id",
    "replica_index",
    "replica_ordinal",
    "selection_rule_applied",
}

POINTWISE_BASENAME = "fig4_all_complete_pointwise_eq10.csv"
METRICS_BASENAME = "fig4_all_complete_family_metrics.csv"
CALIBRATION_BASENAME = "fig4_u40_p25_f861_calibration.csv"
FIGURE_PDF_BASENAME = "fig4_scale_and_transition_boundary_STAGING.pdf"
FIGURE_PNG_BASENAME = "fig4_scale_and_transition_boundary_STAGING.png"
CANDIDATE_FIGURE_PDF_BASENAME = "fig4_scale_and_transition_boundary.pdf"
CANDIDATE_FIGURE_PNG_BASENAME = "fig4_scale_and_transition_boundary.png"
PROVENANCE_BASENAME = "fig4_all_complete_figure_provenance.json"
TABULAR_OUTPUTS = (
    POINTWISE_BASENAME,
    METRICS_BASENAME,
    CALIBRATION_BASENAME,
)


class CandidateError(RuntimeError):
    """Raised when a frozen input or staging output violates the contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_case(U: object, V: object) -> tuple[float, float]:
    return (round(float(U), 10), round(float(V), 10))


def require_regular(path: Path, label: str, *, immutable: bool = False) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CandidateError(f"Missing {label}: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CandidateError(f"{label} must be a regular non-link file: {path}")
    if immutable:
        if info.st_nlink != 1:
            raise CandidateError(f"{label} must have link count one: {path}")
        if info.st_mode & 0o222:
            raise CandidateError(f"{label} must be read-only: {path}")
    return path


def require_exact_hash(path: Path, expected: str, label: str) -> None:
    if not HEX64.fullmatch(expected):
        raise CandidateError(f"Expected SHA-256 for {label} is not 64 lowercase hex")
    actual = sha256(path)
    if actual != expected:
        raise CandidateError(
            f"{label} SHA-256 mismatch: actual={actual}, expected={expected}"
        )


def validate_output_dir(path: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(TMP.resolve())
    except ValueError as exc:
        raise CandidateError(f"Staging output must be below {TMP}") from exc
    if len(relative.parts) != 1:
        raise CandidateError("Staging output must be one fresh top-level child of tmp/")
    if candidate.exists():
        raise CandidateError(f"Staging output already exists: {candidate}")
    return candidate


def _read_csv(path: Path, label: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pandas emits several parser exception classes
        raise CandidateError(f"Could not parse {label}: {path}") from exc


def validate_snapshot_ledger(root: Path, expected_sha256: str) -> dict[str, str]:
    """Bind and rehash every regular file in the immutable frozen snapshot."""
    ledger = require_regular(
        root / P25_LEDGER_BASENAME, "P25 snapshot ledger", immutable=True
    )
    require_exact_hash(ledger, expected_sha256, "P25 snapshot ledger")
    entries: dict[str, str] = {}
    for line_number, line in enumerate(ledger.read_text().splitlines(), start=1):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise CandidateError(
                f"Malformed snapshot-ledger line {line_number}"
            ) from exc
        relative_path = Path(relative)
        if (
            not HEX64.fullmatch(digest)
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative in entries
            or relative == P25_LEDGER_BASENAME
        ):
            raise CandidateError(
                f"Unsafe/duplicate snapshot-ledger line {line_number}: {line!r}"
            )
        entries[relative] = digest
    actual: set[str] = set()
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory_name in directory_names:
            directory = current_path / directory_name
            info = directory.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CandidateError(
                    f"Frozen snapshot has a linked/special directory: {directory}"
                )
            if info.st_mode & 0o222:
                raise CandidateError(
                    f"Frozen snapshot directory is writable: {directory}"
                )
        for file_name in file_names:
            path = current_path / file_name
            require_regular(path, "frozen snapshot file", immutable=True)
            relative = path.relative_to(root).as_posix()
            if relative != P25_LEDGER_BASENAME:
                actual.add(relative)
    if actual != set(entries):
        raise CandidateError(
            "Snapshot ledger inventory mismatch: "
            f"missing={sorted(set(entries) - actual)}, extra={sorted(actual - set(entries))}"
        )
    for relative, expected in entries.items():
        require_exact_hash(root / relative, expected, f"snapshot file {relative}")
    return entries


def validate_p25_bundle(
    bundle: Path,
    *,
    snapshot_ledger_sha256: str,
    deep_audit: Path,
    deep_audit_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, str]]:
    """Validate the exact immutable 325-row, replica-resolved P25 bundle."""
    root = bundle.expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    try:
        root_info = root.lstat()
    except OSError as exc:
        raise CandidateError(f"Missing P25 bundle: {root}") from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise CandidateError(f"P25 bundle must be a real directory: {root}")
    if root_info.st_mode & 0o222:
        raise CandidateError(f"P25 bundle must be read-only: {root}")
    root = root.resolve()
    ledger_entries = validate_snapshot_ledger(root, snapshot_ledger_sha256)
    analysis = root / "analysis"
    if not analysis.is_dir() or analysis.is_symlink():
        raise CandidateError(f"P25 bundle lacks a real analysis directory: {analysis}")

    summary_path = require_regular(
        analysis / P25_SUMMARY_BASENAME, "P25 case summary", immutable=True
    )
    raw_path = require_regular(
        analysis / P25_RAW_BASENAME, "P25 raw validation", immutable=True
    )
    provenance_path = require_regular(
        root / "metadata" / P25_PROVENANCE_BASENAME,
        "P25 provenance",
        immutable=True,
    )
    consumer17_path = require_regular(
        analysis / P25_17NODE_BASENAME, "frozen 17-node consumer table", immutable=True
    )
    control_path = require_regular(
        analysis / P25_CONTROL_BASENAME, "frozen U40 control table", immutable=True
    )
    require_regular(
        analysis / P25_MATCHED_DRIFT_BASENAME,
        "frozen U40 sampling-matched drift table",
        immutable=True,
    )

    audit_path = require_regular(
        deep_audit.expanduser().resolve(), "independent deep audit", immutable=True
    )
    require_exact_hash(audit_path, deep_audit_sha256, "independent deep audit")
    try:
        audit = json.loads(audit_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateError("Could not parse independent deep audit") from exc
    required_audit = {
        "status": "PASS",
        "schema": "fig4_cnn_p25_13case_replica_resolved_deep_audit_v1",
        "snapshot": str(root),
        "snapshot_ledger_sha256": snapshot_ledger_sha256,
        "logical_rows": 325,
        "cases": 13,
        "twists_per_case": 25,
        "consumer17_rows": 17,
        "remote_missing_canonical_results_still_absent": True,
        "canonical_overwrite_detected": False,
        "all_files_read_only_regular_nonlink_nlink1": True,
    }
    for key, expected in required_audit.items():
        if audit.get(key) != expected:
            raise CandidateError(
                f"Independent deep audit has wrong {key}: {audit.get(key)!r}"
            )
    if audit.get("selected_D_job_ids") != [5618538, 5618539, 5618540, 5618541, 5618547]:
        raise CandidateError("Independent deep audit selected the wrong D job IDs")

    summary = _read_csv(summary_path, "P25 case summary")
    raw = _read_csv(raw_path, "P25 raw validation")
    consumer17 = _read_csv(consumer17_path, "frozen 17-node consumer table")
    frozen_controls = _read_csv(control_path, "frozen U40 control table")
    try:
        provenance = json.loads(provenance_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateError("Could not parse P25 provenance JSON") from exc
    if not isinstance(provenance, dict):
        raise CandidateError("P25 provenance must be a JSON object")

    missing_summary = sorted(P25_SUMMARY_REQUIRED - set(summary.columns))
    missing_raw = sorted(P25_RAW_REQUIRED - set(raw.columns))
    if missing_summary:
        raise CandidateError(f"P25 summary missing columns: {missing_summary}")
    if missing_raw:
        raise CandidateError(f"P25 raw validation missing columns: {missing_raw}")
    if len(summary) != 13 or summary.duplicated(["U", "V"]).any():
        raise CandidateError("P25 summary must contain 13 unique (U,V) rows")
    if {canonical_case(r.U, r.V) for r in summary.itertuples()} != set(P25_CASES):
        raise CandidateError("P25 summary has the wrong exact 13-case inventory")
    if len(raw) != 325:
        raise CandidateError(
            f"P25 raw validation must contain 325 rows, found {len(raw)}"
        )
    if raw.duplicated(["U", "V", "kx", "ky"]).any():
        raise CandidateError("P25 raw validation contains duplicate target coordinates")

    numeric_summary = sorted(P25_SUMMARY_REQUIRED - {"complete_twists"})
    for column in numeric_summary + ["complete_twists"]:
        summary[column] = pd.to_numeric(summary[column], errors="raise")
    raw = raw.rename(columns={"C1_NN": "C_NN"})
    for column in ["U", "V", "kx", "ky", "C_NN"]:
        raw[column] = pd.to_numeric(raw[column], errors="raise")
    if not np.isfinite(summary[numeric_summary].to_numpy(dtype=float)).all():
        raise CandidateError("P25 summary contains non-finite numeric values")
    if not np.isfinite(raw[["U", "V", "C_NN"]].to_numpy(dtype=float)).all():
        raise CandidateError("P25 raw validation contains non-finite values")
    if not summary["complete_twists"].eq(25).all():
        raise CandidateError("Each P25 summary case must use exactly 25 twists")
    if not np.allclose(summary["r"], summary["V"] / summary["U"], atol=1e-13, rtol=0):
        raise CandidateError("P25 summary r is inconsistent with V/U")
    if not ((raw["C_NN"] >= -0.75) & (raw["C_NN"] < 0.0)).all():
        raise CandidateError("P25 raw C_NN values lie outside [-0.75,0)")

    expected_twists = set(EXPECTED_TWISTS)
    recomputed: list[dict[str, float]] = []
    for U, V in P25_CASES:
        group = raw[
            np.isclose(raw["U"].astype(float), U)
            & np.isclose(raw["V"].astype(float), V)
        ]
        if len(group) != 25:
            raise CandidateError(f"P25 U={U:g},V={V:g} does not contain 25 rows")
        twists = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if twists != expected_twists:
            raise CandidateError(f"P25 U={U:g},V={V:g} has the wrong twist panel")
        values = group["C_NN"].to_numpy(dtype=float)
        recomputed.append(
            {
                "U": U,
                "V": V,
                "C_NN_recomputed": float(values.mean()),
                "C_NN_min_recomputed": float(values.min()),
                "C_NN_max_recomputed": float(values.max()),
                "C_NN_spread_recomputed": float(np.ptp(values)),
                "C_NN_population_std_recomputed": float(values.std(ddof=0)),
            }
        )
    check = summary.merge(
        pd.DataFrame(recomputed), on=["U", "V"], validate="one_to_one"
    )
    comparisons = {
        "C_NN": "C_NN_recomputed",
        "C_NN_min": "C_NN_min_recomputed",
        "C_NN_max": "C_NN_max_recomputed",
        "C_NN_spread": "C_NN_spread_recomputed",
        "C_NN_population_std_diagnostic": "C_NN_population_std_recomputed",
    }
    for stored, computed in comparisons.items():
        if not np.allclose(check[stored], check[computed], atol=5e-13, rtol=0):
            raise CandidateError(
                f"P25 stored {stored} disagrees with the 325 selected rows"
            )
    U = summary["U"].to_numpy(dtype=float)
    V = summary["V"].to_numpy(dtype=float)
    C = summary["C_NN"].to_numpy(dtype=float)
    factor = (2.0 * U - V) / (U - V)
    prediction = 1.0 + factor * (2.0 * C - 0.5)
    if not np.allclose(summary["eq10_factor"], factor, atol=5e-13, rtol=0):
        raise CandidateError("P25 stored Eq. (10) factor is inconsistent")
    if not np.allclose(summary["s_eq10_signed"], prediction, atol=5e-13, rtol=0):
        raise CandidateError("P25 stored signed Eq. (10) prediction is inconsistent")

    # The deep freezer owns provenance of replica choice.  At this plotting
    # boundary we require its exact invariant to be present, while the 325-row
    # uniqueness check above independently proves that no selected target was
    # averaged twice.
    if provenance.get("schema") != "fig4_cnn_p25_13case_replica_resolved_v1":
        raise CandidateError("P25 provenance has the wrong schema")
    inventory = provenance.get("inventory")
    selection = provenance.get("selection_policy")
    if not isinstance(inventory, dict) or not isinstance(selection, dict):
        raise CandidateError("P25 provenance lacks inventory/selection objects")
    if not (
        inventory.get("logical_rows") == 325
        and inventory.get("cases") == 13
        and inventory.get("twists_per_case") == 25
        and inventory.get("D_selected_rows") == 5
        and selection.get("same_target_duplicates_averaged") is False
        and selection.get("sort_key")
        == ["replica_ordinal", "numeric_slurm_job_id", "replica_index"]
        and selection.get("selected_job_ids")
        == {
            "226": 5618538,
            "232": 5618539,
            "267": 5618540,
            "285": 5618541,
            "298": 5618547,
        }
    ):
        raise CandidateError(
            "P25 provenance has the wrong one-replica selection contract"
        )
    repaired_rows = raw[
        raw["source_role"].eq("D_selected_replica_for_missing_A")
    ].copy()
    if (
        len(repaired_rows) != 5
        or not repaired_rows["selection_rule_applied"].astype(bool).all()
    ):
        raise CandidateError("P25 raw validation does not contain five selected D rows")
    repaired_observed = {
        (float(row.U), float(row.V), int(row.kx), int(row.ky))
        for row in repaired_rows.itertuples()
    }
    if repaired_observed != REPAIRED_TWISTS:
        raise CandidateError(
            "P25 raw validation does not cover all five repaired targets"
        )
    if repaired_rows["source_job_id"].astype(int).tolist() != [
        5618538,
        5618539,
        5618540,
        5618541,
        5618547,
    ]:
        raise CandidateError("P25 raw validation selected unexpected replica job IDs")

    # Bind the frozen 17-node consumer and U40 control products now; the final
    # assembly below will independently reconstruct and compare every C_NN.
    if len(consumer17) != 17 or consumer17.duplicated(["U", "V"]).any():
        raise CandidateError("Frozen consumer table must contain 17 unique nodes")
    if {canonical_case(r.U, r.V) for r in consumer17.itertuples()} != set(
        POINTWISE_CASES
    ):
        raise CandidateError("Frozen consumer table has the wrong 17-node inventory")
    if len(frozen_controls) != 4 or frozen_controls.duplicated(["U", "V"]).any():
        raise CandidateError("Frozen U40 control table must contain four unique rows")
    consumer_p25 = consumer17[
        consumer17.apply(
            lambda row: canonical_case(row["U"], row["V"]) in set(P25_CASES),
            axis=1,
        )
    ][["U", "V", "C_NN"]]
    p25_crosscheck = summary[["U", "V", "C_NN"]].merge(
        consumer_p25,
        on=["U", "V"],
        suffixes=("_summary", "_consumer"),
        validate="one_to_one",
    )
    if len(p25_crosscheck) != 13 or not np.allclose(
        p25_crosscheck["C_NN_summary"],
        p25_crosscheck["C_NN_consumer"],
        atol=5e-13,
        rtol=0,
    ):
        raise CandidateError(
            "Frozen 17-node P25 values disagree with the 13-case summary"
        )
    consumer_controls = consumer17[
        consumer17.apply(
            lambda row: canonical_case(row["U"], row["V"]) in set(U40_CONTROL_CASES),
            axis=1,
        )
    ][["U", "V", "C_NN"]]
    control_crosscheck = frozen_controls[["U", "V", "C_NN_full861"]].merge(
        consumer_controls, on=["U", "V"], validate="one_to_one"
    )
    if len(control_crosscheck) != 4 or not np.allclose(
        control_crosscheck["C_NN_full861"],
        control_crosscheck["C_NN"],
        atol=5e-13,
        rtol=0,
    ):
        raise CandidateError(
            "Frozen 17-node F861 controls disagree with the control table"
        )
    consumer_U = consumer17["U"].to_numpy(dtype=float)
    consumer_V = consumer17["V"].to_numpy(dtype=float)
    consumer_C = consumer17["C_NN"].to_numpy(dtype=float)
    consumer_eq10 = 1.0 + (2.0 * consumer_U - consumer_V) / (
        consumer_U - consumer_V
    ) * (2.0 * consumer_C - 0.5)
    if not np.allclose(consumer17["s_eq10_signed"], consumer_eq10, atol=5e-13, rtol=0):
        raise CandidateError("Frozen 17-node direct Eq. (10) values are inconsistent")

    input_hashes = {
        P25_LEDGER_BASENAME: snapshot_ledger_sha256,
        "independent_deep_audit": deep_audit_sha256,
        f"analysis/{P25_SUMMARY_BASENAME}": ledger_entries[
            f"analysis/{P25_SUMMARY_BASENAME}"
        ],
        f"analysis/{P25_RAW_BASENAME}": ledger_entries[f"analysis/{P25_RAW_BASENAME}"],
        f"analysis/{P25_17NODE_BASENAME}": ledger_entries[
            f"analysis/{P25_17NODE_BASENAME}"
        ],
        f"analysis/{P25_CONTROL_BASENAME}": ledger_entries[
            f"analysis/{P25_CONTROL_BASENAME}"
        ],
        f"analysis/{P25_MATCHED_DRIFT_BASENAME}": ledger_entries[
            f"analysis/{P25_MATCHED_DRIFT_BASENAME}"
        ],
        f"metadata/{P25_PROVENANCE_BASENAME}": ledger_entries[
            f"metadata/{P25_PROVENANCE_BASENAME}"
        ],
    }

    return (
        summary.sort_values(["U", "V"]).reset_index(drop=True),
        raw.sort_values(["U", "V", "kx", "ky"]).reset_index(drop=True),
        provenance,
        input_hashes,
    )


def load_reviewed_u40_controls() -> tuple[pd.DataFrame, pd.DataFrame]:
    for path, expected in REVIEWED_INPUT_SHA256.items():
        require_regular(path, f"reviewed input {path.name}")
        require_exact_hash(path, expected, f"reviewed input {path.name}")
    try:
        controls, calibration = legacy_analysis.validate_and_load_u40_controls(
            U40_SUMMARY,
            U40_ROWS,
            panel_bias_tolerance=1.0e-6,
        )
    except Exception as exc:
        raise CandidateError(f"U=40 F861 control validation failed: {exc}") from exc
    if len(controls) != 4 or len(calibration) != 4:
        raise CandidateError("U=40 control loader did not return four controls")
    return controls, calibration


def assemble_pointwise(
    p25: pd.DataFrame,
    controls: pd.DataFrame,
    calibration: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join 17 nodes and evaluate matched-sampling, axis-anchored C drifts."""
    p25_nodes = p25.copy()
    p25_nodes["C_NN_source"] = "replica-resolved fullobs P25"
    p25_nodes["C_NN_sampling"] = "25-twist unweighted arithmetic mean"
    p25_nodes["C_NN_fidelity"] = "P25"
    p25_nodes["twist_spread_is_standard_error"] = False
    keep = [
        "U",
        "V",
        "r",
        "C_NN",
        "C_NN_min",
        "C_NN_max",
        "C_NN_spread",
        "C_NN_population_std_diagnostic",
        "complete_twists",
        "C_NN_source",
        "C_NN_sampling",
        "C_NN_fidelity",
        "twist_spread_is_standard_error",
    ]
    p25_nodes = p25_nodes[keep]

    control_nodes = controls.rename(columns={"V_over_U": "r"}).copy()
    control_nodes["C_NN_min"] = np.nan
    control_nodes["C_NN_max"] = np.nan
    control_nodes["complete_twists"] = 861
    control_nodes["C_NN_fidelity"] = "F861"
    control_nodes = control_nodes[keep]
    merged_C = pd.concat([p25_nodes, control_nodes], ignore_index=True)
    if len(merged_C) != 17 or merged_C.duplicated(["U", "V"]).any():
        raise CandidateError("Joined C_NN table must contain 17 unique nodes")
    if {canonical_case(r.U, r.V) for r in merged_C.itertuples()} != set(
        POINTWISE_CASES
    ):
        raise CandidateError("Joined C_NN table has the wrong 17-node inventory")

    gz = _read_csv(GZ_POINTS, "reviewed GZ points")
    selected = gz[
        gz.apply(
            lambda row: canonical_case(row["U"], row["V"]) in set(POINTWISE_CASES),
            axis=1,
        )
    ].copy()
    if len(selected) != 17 or selected.duplicated(["U", "V"]).any():
        raise CandidateError("Reviewed GZ table does not contain the exact 17 nodes")
    pointwise = merged_C.merge(
        selected[["U", "V", "branch", "s", "s_u0", "source_csv"]],
        on=["U", "V"],
        validate="one_to_one",
    )
    pointwise["analytic_phase"] = "Mott"
    pointwise["analytic_phase_basis"] = np.where(
        (pointwise["U"].eq(20.0) & pointwise["V"].eq(5.0)),
        "V=5 is below independently bracketed V_Mott=5.02",
        "Mott-side reviewed target",
    )
    pointwise["s_signed_observed"] = -pointwise["s"].astype(float)
    pointwise["s_u0_signed"] = -pointwise["s_u0"].astype(float)
    U = pointwise["U"].to_numpy(dtype=float)
    V = pointwise["V"].to_numpy(dtype=float)
    pointwise["eq10_factor"] = (2.0 * U - V) / (U - V)
    p25_c0 = {
        float(U_value): float(group.loc[group["V"].eq(0.0), "C_NN"].iloc[0])
        for U_value, group in p25.groupby("U", sort=True)
        if group["V"].eq(0.0).any()
    }
    if set(p25_c0) != {20.0, 80.0}:
        raise CandidateError("P25 bundle must provide V=0 references for U=20 and 80")
    u40_cal = calibration.set_index("V")
    if set(u40_cal.index.astype(float)) != {0.0, 4.0, 8.0, 9.0}:
        raise CandidateError("U=40 calibration has the wrong exact control inventory")
    u40_full_c0 = float(u40_cal.loc[0.0, "C_NN_full_861"])
    u40_p25_c0 = float(u40_cal.loc[0.0, "C_NN_panel_25"])

    references: list[dict[str, object]] = []
    for row in pointwise.itertuples(index=False):
        U_value = float(row.U)
        V_value = float(row.V)
        if U_value == 20.0:
            reference = p25_c0[20.0]
            sampling = "P25 minus P25 at U=20,V=0"
        elif U_value == 80.0:
            reference = p25_c0[80.0]
            sampling = "P25 minus P25 at U=80,V=0"
        elif U_value == 40.0 and V_value == 6.0:
            reference = u40_p25_c0
            sampling = "P25 minus matched P25 projection at U=40,V=0"
        elif U_value == 40.0:
            reference = u40_full_c0
            sampling = "F861 minus F861 at U=40,V=0"
        else:  # pragma: no cover - inventory gate above makes this unreachable
            raise CandidateError(
                f"No matched C_NN reference for U={U_value},V={V_value}"
            )
        anchor_C = float(row.s_u0_signed) / 4.0
        drift = float(row.C_NN) - reference
        effective_C = anchor_C + drift
        anchored_prediction = 1.0 + float(row.eq10_factor) * (2.0 * effective_C - 0.5)
        references.append(
            {
                "U": U_value,
                "V": V_value,
                "C_NN_matched_V0_reference": reference,
                "C_NN_reference_sampling": sampling,
                "C_NN_axis_anchor_from_s_observed_V0": anchor_C,
                "C_NN_measured_drift_from_matched_V0": drift,
                "C_NN_effective_axis_anchored_drift": effective_C,
                "s_eq10_axis_anchored_C_NN_drift": anchored_prediction,
            }
        )
    pointwise = pointwise.merge(
        pd.DataFrame(references), on=["U", "V"], validate="one_to_one"
    )
    pointwise["s_axis_anchor_signed"] = legacy_fig4.mott_scale_law_from_axis_anchor(
        pointwise["r"].to_numpy(dtype=float),
        pointwise["s_u0_signed"].to_numpy(dtype=float),
    )
    pointwise["drift_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_eq10_axis_anchored_C_NN_drift"]
    )
    pointwise["axis_anchor_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_axis_anchor_signed"]
    )
    pointwise["eq10_convention"] = "signed s_NN in omega_GZ=s_NN epsilon_NN"
    pointwise["residual_convention"] = "observed minus prediction"
    pointwise = pointwise.sort_values(["U", "V"]).reset_index(drop=True)

    metrics: list[dict[str, object]] = []
    for U_value, group in pointwise.groupby("U", sort=True):
        for scope, scoped in (
            ("all pointwise nodes", group),
            ("finite-V nodes", group[group["V"] > 0.0]),
        ):
            for model, column in (
                (
                    "axis-anchored Eq. (10) + measured matched-sampling C_NN drift",
                    "drift_residual_observed_minus_prediction",
                ),
                (
                    "V=0-axis anchor without measured C_NN drift",
                    "axis_anchor_residual_observed_minus_prediction",
                ),
            ):
                residual = scoped[column].to_numpy(dtype=float)
                metrics.append(
                    {
                        "U": float(U_value),
                        "scope": scope,
                        "model": model,
                        "point_count": len(scoped),
                        "rmse": float(np.sqrt(np.mean(residual**2))),
                        "mae": float(np.mean(np.abs(residual))),
                        "max_abs_residual": float(np.max(np.abs(residual))),
                    }
                )
    return pointwise, pd.DataFrame(metrics)


def draw_scale_panel(
    ax: plt.Axes, points: pd.DataFrame, prediction: pd.DataFrame
) -> None:
    """Draw GZ symbols and axis-anchored, measured-C-drift Mott lines."""
    ax.axvspan(0.0, legacy_fig4.R_BOUNDARY, color="#3b78a8", alpha=0.055, zorder=0)
    ax.axvspan(legacy_fig4.R_BOUNDARY, 0.53, color="#b64a42", alpha=0.05, zorder=0)
    for U in (20.0, 40.0, 80.0):
        observed = points[points["U"].eq(U)].sort_values("r")
        predicted = prediction[prediction["U"].eq(U)].sort_values("r")
        ax.plot(
            observed["r"],
            -observed["s"].to_numpy(dtype=float),
            marker=legacy_fig4.MARKERS[U],
            color=legacy_fig4.COLORS[U],
            lw=0,
            ms=6.5,
            label=rf"$U={U:g}$",
            zorder=5,
        )
        ax.plot(
            predicted["r"],
            predicted["s_eq10_axis_anchored_C_NN_drift"],
            color=legacy_fig4.COLORS[U],
            lw=1.6,
            alpha=0.92,
            zorder=3,
        )

    r_cdw = np.linspace(0.255, 0.52, 240)
    ax.plot(r_cdw, legacy_fig4.cdw_scale_law(r_cdw), color="black", ls="-.", lw=2.0)
    ax.axvline(legacy_fig4.R_BOUNDARY, color="0.35", lw=1.0, ls=":")
    ax.hlines(
        legacy_fig4.S_U_RESOLUTION,
        0.0,
        legacy_fig4.R_BOUNDARY,
        color="0.45",
        ls="--",
        lw=1.0,
    )
    ax.hlines(
        legacy_fig4.S_V,
        legacy_fig4.R_BOUNDARY,
        0.53,
        color="0.15",
        ls=":",
        lw=1.35,
    )
    ax.text(
        0.125,
        legacy_fig4.S_U_RESOLUTION - 0.018,
        r"$U\to\infty,\ 4C_{\mathrm{NN}}$",
        ha="center",
        va="top",
        color="0.38",
    )
    ax.text(
        0.515,
        legacy_fig4.S_V - 0.008,
        r"$V$-only $-8/7$",
        ha="right",
        va="top",
        color="0.1",
    )
    ax.text(0.105, -1.075, "Mott side", color="#1f5278", ha="center", va="top")
    ax.text(0.39, -1.075, "CDW side", color="#8d2d28", ha="center", va="top")
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(U,V)$")
    ax.set_xlim(-0.01, 0.53)
    ax.set_ylim(-1.84, -1.06)
    ax.grid(alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles,
        labels,
        frameon=False,
        ncol=1,
        loc="upper left",
        bbox_to_anchor=(0.005, 0.88),
        borderaxespad=0.0,
        fontsize=9.84,
    )
    legacy_fig4.panel_label(ax, "(a)", -0.13, fontsize=17.0)


def render(
    pointwise: pd.DataFrame,
    out_pdf: Path,
    out_png: Path,
    *,
    watermark: bool,
) -> None:
    points = legacy_fig4.load_scale_data()
    boundary = legacy_fig4.load_boundary_data(write_filtered=False)
    with plt.rc_context(legacy_fig4.STYLE):
        fig, axes = plt.subplots(
            2,
            1,
            figsize=(5.55, 7.8),
            gridspec_kw={"height_ratios": [1.0, 1.0]},
        )
        draw_scale_panel(axes[0], points, pointwise)
        legacy_fig4.draw_boundary_panel(
            axes[1],
            boundary,
            mixed_momentum_terms=True,
            panel_label_fontsize=17.0,
            panel_label_x=-0.19,
        )
        for axis in axes:
            axis.xaxis.label.set_fontsize(legacy_fig4.STYLE["axes.labelsize"] * 1.4)
            axis.yaxis.label.set_fontsize(legacy_fig4.STYLE["axes.labelsize"] * 1.4)
            axis.tick_params(
                axis="x", labelsize=legacy_fig4.STYLE["xtick.labelsize"] * 1.4
            )
            axis.tick_params(
                axis="y", labelsize=legacy_fig4.STYLE["ytick.labelsize"] * 1.4
            )
        fig.subplots_adjust(
            left=0.200,
            right=0.995,
            top=0.982 if watermark else 0.992,
            bottom=0.082,
            hspace=0.20,
        )
        if watermark:
            fig.text(
                0.5,
                0.998,
                "STAGING PREVIEW — ALL COMPLETED FULL-OBS C_NN — NOT FOR PUBLICATION",
                ha="center",
                va="top",
                color="#9b1c1c",
                fontsize=7.8,
                fontweight="bold",
            )
        fig.savefig(out_pdf, bbox_inches="tight")
        fig.savefig(out_png, dpi=280, bbox_inches="tight")
        plt.close(fig)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p25-bundle", type=Path, required=True)
    parser.add_argument("--snapshot-ledger-sha256", required=True)
    parser.add_argument("--deep-audit", type=Path, required=True)
    parser.add_argument("--deep-audit-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--publication-candidate",
        action="store_true",
        help="Remove watermark while remaining staging-only below tmp/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out = validate_output_dir(args.output_dir)
    p25, raw, p25_provenance, p25_hashes = validate_p25_bundle(
        args.p25_bundle,
        snapshot_ledger_sha256=args.snapshot_ledger_sha256,
        deep_audit=args.deep_audit,
        deep_audit_sha256=args.deep_audit_sha256,
    )
    controls, calibration = load_reviewed_u40_controls()
    pointwise, metrics = assemble_pointwise(p25, controls, calibration)
    figure_pdf_name = (
        CANDIDATE_FIGURE_PDF_BASENAME
        if args.publication_candidate
        else FIGURE_PDF_BASENAME
    )
    figure_png_name = (
        CANDIDATE_FIGURE_PNG_BASENAME
        if args.publication_candidate
        else FIGURE_PNG_BASENAME
    )

    out.mkdir(mode=0o755)
    pointwise.to_csv(out / POINTWISE_BASENAME, index=False)
    metrics.to_csv(out / METRICS_BASENAME, index=False)
    calibration.to_csv(out / CALIBRATION_BASENAME, index=False)
    render(
        pointwise,
        out / figure_pdf_name,
        out / figure_png_name,
        watermark=not args.publication_candidate,
    )
    output_hashes = {
        name: sha256(out / name)
        for name in TABULAR_OUTPUTS + (figure_pdf_name, figure_png_name)
    }
    provenance = {
        "schema_version": 1,
        "data_product": "fig4_17node_axis_anchored_eq10_completed_fullobs_C_NN_drift",
        "created_at": datetime.now().astimezone().isoformat(),
        "publication_artifacts_modified": False,
        "plot_model": (
            "C_eff=s_obs(U,0)/4 + C_NN(U,V)-C_NN(U,0), with matched "
            "P25/P25 or F861/F861 sampling, then Eq. (10); no finite-V fit"
        ),
        "pointwise_inventory": {
            "rows": 17,
            "P25_rows": 13,
            "F861_control_rows": 4,
            "P25_selected_raw_rows": len(raw),
            "one_replica_per_missing_target": True,
            "repaired_targets": sorted([list(case) for case in REPAIRED_TWISTS]),
        },
        "p25_bundle": {
            "path": str(Path(args.p25_bundle).expanduser().resolve()),
            "input_hashes": p25_hashes,
            "provenance_schema": p25_provenance.get("schema"),
        },
        "reviewed_inputs_sha256": {
            str(path.relative_to(ROOT)): digest
            for path, digest in REVIEWED_INPUT_SHA256.items()
        },
        "twist_spread_role": "systematic diagnostic, not SEM; not plotted as an error bar",
        "output_files": output_hashes,
        "caption_compatibility": {
            "current_axis_anchor_wording_remains_true": True,
            "filled_symbols_remain_GZ_data_only": True,
            "caption_or_main_text_update_required_if_promoted": False,
        },
    }
    (out / PROVENANCE_BASENAME).write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "output_dir": str(out),
                "pointwise_rows": len(pointwise),
                "P25_selected_rows": len(raw),
                "max_U40_panel_bias": float(calibration["abs_panel_minus_full"].max()),
                "figure_pdf_sha256": output_hashes[figure_pdf_name],
                "figure_png_sha256": output_hashes[figure_png_name],
                "publication_artifacts_modified": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
