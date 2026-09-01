#!/usr/bin/env python3
"""Build a staging-only Fig. 4 with both measured ``V/U=1/4`` endpoints.

This is an additive wrapper around
``build_fig4_all_completed_cnn_candidate.py``.  It deliberately leaves that
builder's immutable 13-case/325-row/17-node contract unchanged, validates a
separate immutable 25-row ``U=80,V=20`` add-on, and adds the already reviewed
full-861 ``U=40,V=10`` control.  The final pointwise inventory is therefore

* fourteen P25 cases (350 logical rows),
* five independent U=40 F861 controls, and
* nineteen plotted C_NN nodes.

For consistency with the currently installed figure, the Mott curves use the
axis-anchored, matched-sampling C_NN drift

    C_eff(U,V) = s_obs(U,0)/4 + C_NN(U,V) - C_NN(U,0)

inside Eq. (10).  The direct unanchored Eq. (10) value is retained in the
pointwise table as a diagnostic.  The two new endpoint values are independent
inputs, not fitted coefficients.

There is intentionally no promotion path.  Outputs are confined to one fresh
top-level child of ``tmp/``.  The script never writes below ``figures/``,
``manuscript/``, or ``results/`` and never accesses Overleaf.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import build_fig4_all_completed_cnn_candidate as base


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]

BASE_BUILDER_SHA256 = (
    "a1744685419bf0c8dc8c0634d6cba4be99f828d729c6cd64f32c16b35c9ae130"
)

ADDON_SUMMARY_RELATIVE = Path("analysis/u80v20_summary.csv")
ADDON_RAW_RELATIVE = Path("analysis/u80v20_raw_validation.csv")
ADDON_PROVENANCE_RELATIVE = Path("metadata/provenance.json")
ADDON_LEDGER_BASENAME = "SNAPSHOT_SHA256SUMS"
ADDON_LEDGER_INVENTORY = frozenset(
    {
        ADDON_SUMMARY_RELATIVE.as_posix(),
        ADDON_RAW_RELATIVE.as_posix(),
        ADDON_PROVENANCE_RELATIVE.as_posix(),
    }
)

ADDON_PROVENANCE_SCHEMA = "fig4_cnn_u80v20_p25_replica_resolved_v1"
ADDON_DEEP_AUDIT_SCHEMA = (
    "fig4_cnn_u80v20_p25_replica_resolved_deep_audit_v1"
)

SELECTED_REPLICA_JOB_ID = 5621087
SELECTED_REPLICA_SEED = 436887014
SELECTED_REPLICA_ORDINAL = 4
SELECTED_REPLICA_TARGET = (80.0, 20.0, 17, 17)
SELECTED_REPLICA_C_NN = -0.3494608622230716555
EXPECTED_U80V20_C_NN_MEAN = -0.3494588373529676

FROZEN_P25_CASES_13 = tuple(base.P25_CASES)
FROZEN_U40_CONTROLS_4 = tuple(base.U40_CONTROL_CASES)
FROZEN_POINTWISE_CASES_17 = tuple(base.POINTWISE_CASES)
U80V20_CASE = (80.0, 20.0)
U40V10_CASE = (40.0, 10.0)
FINAL_P25_CASES_14 = FROZEN_P25_CASES_13 + (U80V20_CASE,)
FINAL_U40_CONTROLS_5 = FROZEN_U40_CONTROLS_4 + (U40V10_CASE,)
FINAL_POINTWISE_CASES_19 = tuple(
    sorted(set(FINAL_P25_CASES_14) | set(FINAL_U40_CONTROLS_5))
)

POINTWISE_BASENAME = "fig4_boundary_complete_pointwise_eq10.csv"
METRICS_BASENAME = "fig4_boundary_complete_family_metrics.csv"
CALIBRATION_BASENAME = "fig4_u40_p25_f861_calibration_5node.csv"
STAGING_FIGURE_PDF_BASENAME = "fig4_scale_and_transition_boundary_STAGING.pdf"
STAGING_FIGURE_PNG_BASENAME = "fig4_scale_and_transition_boundary_STAGING.png"
CANDIDATE_FIGURE_PDF_BASENAME = "fig4_scale_and_transition_boundary.pdf"
CANDIDATE_FIGURE_PNG_BASENAME = "fig4_scale_and_transition_boundary.png"
PROVENANCE_BASENAME = "fig4_boundary_complete_figure_provenance.json"

HEX64 = re.compile(r"^[0-9a-f]{64}$")

ADDON_SUMMARY_REQUIRED = {
    "U",
    "V",
    "r",
    "complete_twists",
    "C_NN",
    "C_NN_min",
    "C_NN_max",
    "C_NN_spread",
    "C_NN_population_std_diagnostic",
    "C_NN_symmetry_weighted_diagnostic",
    "C_NN_symmetry_weighted_minus_primary",
    "s_eq10_signed",
    "D_site_panel_mean",
    "mCDW2_pipi_panel_mean",
    "nn_NN_panel_mean",
    "kinetic_per_site_panel_mean",
    "max_abs_identity_residual",
    "C_NN_source",
    "C_NN_sampling",
    "twist_spread_is_standard_error",
}

ADDON_RAW_REQUIRED = {
    "U",
    "V",
    "kx",
    "ky",
    "C1_NN",
    "source_role",
    "source_job_id",
    "seed",
    "replica_index",
    "replica_ordinal",
    "selection_rule_applied",
    "E0",
    "D_site",
    "mCDW2_pipi",
    "nn_NN",
    "kinetic_per_site",
    "max_abs_identity_residual",
}


class BoundaryCandidateError(RuntimeError):
    """Raised when a boundary input or staging output violates the contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str, label: str) -> None:
    if not HEX64.fullmatch(str(expected)):
        raise BoundaryCandidateError(f"{label} expected SHA-256 is not lowercase hex")
    actual = sha256(path)
    if actual != expected:
        raise BoundaryCandidateError(
            f"{label} SHA-256 mismatch: actual={actual}, expected={expected}"
        )


def _require_immutable_regular(path: Path, label: str) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise BoundaryCandidateError(f"Missing {label}: {path}") from exc
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_mode & 0o222
    ):
        raise BoundaryCandidateError(
            f"{label} must be read-only, regular, non-link, and link-count one: {path}"
        )
    return path


def _strict_bool(series: pd.Series, label: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        bad = sorted(values[~values.isin({"true", "false"})].unique().tolist())
        raise BoundaryCandidateError(f"{label} is not strict Boolean: {bad}")
    return values.eq("true")


def _canonical_case(U: object, V: object) -> tuple[float, float]:
    return (round(float(U), 10), round(float(V), 10))


def _load_json(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundaryCandidateError(f"Could not parse {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise BoundaryCandidateError(f"{label} must be a JSON object")
    return payload


def _load_csv(path: Path, label: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pandas exposes several parser exception types
        raise BoundaryCandidateError(f"Could not parse {label}: {path}") from exc


def _validate_base_builder_identity() -> None:
    if tuple(base.P25_CASES) != FROZEN_P25_CASES_13:
        raise BoundaryCandidateError("Base builder P25 constants changed unexpectedly")
    if tuple(base.U40_CONTROL_CASES) != FROZEN_U40_CONTROLS_4:
        raise BoundaryCandidateError("Base builder U40-control constants changed unexpectedly")
    if tuple(base.POINTWISE_CASES) != FROZEN_POINTWISE_CASES_17:
        raise BoundaryCandidateError("Base builder pointwise constants changed unexpectedly")
    _require_hash(Path(base.__file__).resolve(), BASE_BUILDER_SHA256, "base builder")


def validate_addon_bundle(
    bundle: Path,
    *,
    snapshot_ledger_sha256: str,
    deep_audit: Path,
    deep_audit_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, str]]:
    """Validate the immutable U80,V20 24-canonical-plus-one-replica add-on."""
    root = bundle.expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    try:
        info = root.lstat()
    except OSError as exc:
        raise BoundaryCandidateError(f"Missing U80,V20 add-on snapshot: {root}") from exc
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISDIR(info.st_mode)
        or info.st_mode & 0o222
    ):
        raise BoundaryCandidateError(
            f"U80,V20 add-on must be a read-only real directory: {root}"
        )
    root = root.resolve()
    try:
        ledger_entries = base.validate_snapshot_ledger(root, snapshot_ledger_sha256)
    except base.CandidateError as exc:
        raise BoundaryCandidateError(str(exc)) from exc
    if set(ledger_entries) != ADDON_LEDGER_INVENTORY:
        raise BoundaryCandidateError(
            "U80,V20 add-on has the wrong exact file inventory: "
            f"expected={sorted(ADDON_LEDGER_INVENTORY)}, "
            f"found={sorted(ledger_entries)}"
        )

    summary_path = _require_immutable_regular(
        root / ADDON_SUMMARY_RELATIVE, "U80,V20 summary"
    )
    raw_path = _require_immutable_regular(
        root / ADDON_RAW_RELATIVE, "U80,V20 raw-validation table"
    )
    provenance_path = _require_immutable_regular(
        root / ADDON_PROVENANCE_RELATIVE, "U80,V20 provenance"
    )
    audit_path = _require_immutable_regular(
        deep_audit.expanduser().resolve(), "U80,V20 independent deep audit"
    )
    _require_hash(audit_path, deep_audit_sha256, "U80,V20 independent deep audit")

    audit = _load_json(audit_path, "U80,V20 independent deep audit")
    required_audit = {
        "status": "PASS",
        "schema": ADDON_DEEP_AUDIT_SCHEMA,
        "snapshot": str(root),
        "snapshot_ledger_sha256": snapshot_ledger_sha256,
        "logical_rows": 25,
        "cases": 1,
        "twists_per_case": 25,
        "canonical_rows": 24,
        "selected_replica_rows": 1,
        "selected_job_id": SELECTED_REPLICA_JOB_ID,
        "selected_seed": SELECTED_REPLICA_SEED,
        "selected_replica_ordinal": SELECTED_REPLICA_ORDINAL,
        "canonical_result_still_absent": True,
        "same_target_duplicates_averaged": False,
        "all_files_read_only_regular_nonlink_nlink1": True,
    }
    for key, expected in required_audit.items():
        if audit.get(key) != expected:
            raise BoundaryCandidateError(
                f"U80,V20 independent deep audit has wrong {key}: {audit.get(key)!r}"
            )
    try:
        audit_identity = float(audit["max_abs_identity_residual"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BoundaryCandidateError(
            "U80,V20 independent deep audit lacks max_abs_identity_residual"
        ) from exc
    if not math.isfinite(audit_identity) or audit_identity > 1.0e-8:
        raise BoundaryCandidateError(
            f"U80,V20 independent deep-audit identity residual is {audit_identity:g}"
        )

    provenance = _load_json(provenance_path, "U80,V20 provenance")
    if provenance.get("schema") != ADDON_PROVENANCE_SCHEMA:
        raise BoundaryCandidateError("U80,V20 provenance has the wrong schema")
    inventory = provenance.get("inventory")
    selection = provenance.get("selection_policy")
    if not isinstance(inventory, dict) or not isinstance(selection, dict):
        raise BoundaryCandidateError(
            "U80,V20 provenance lacks inventory/selection-policy objects"
        )
    required_inventory = {
        "logical_rows": 25,
        "cases": 1,
        "twists_per_case": 25,
        "canonical_rows": 24,
        "selected_replica_rows": 1,
    }
    for key, expected in required_inventory.items():
        if inventory.get(key) != expected:
            raise BoundaryCandidateError(
                f"U80,V20 provenance inventory has wrong {key}: {inventory.get(key)!r}"
            )
    selected_target = selection.get("selected_target")
    if not isinstance(selected_target, dict):
        raise BoundaryCandidateError("U80,V20 selection lacks selected_target")
    if not (
        selection.get("same_target_duplicates_averaged") is False
        and selection.get("selected_job_id") == SELECTED_REPLICA_JOB_ID
        and selection.get("selected_seed") == SELECTED_REPLICA_SEED
        and selection.get("selected_replica_ordinal") == SELECTED_REPLICA_ORDINAL
        and _canonical_case(selected_target.get("U"), selected_target.get("V"))
        == U80V20_CASE
        and int(selected_target.get("kx")) == 17
        and int(selected_target.get("ky")) == 17
    ):
        raise BoundaryCandidateError("U80,V20 provenance selected the wrong replica")

    summary = _load_csv(summary_path, "U80,V20 summary")
    raw = _load_csv(raw_path, "U80,V20 raw-validation table")
    missing_summary = sorted(ADDON_SUMMARY_REQUIRED - set(summary.columns))
    missing_raw = sorted(ADDON_RAW_REQUIRED - set(raw.columns))
    if missing_summary:
        raise BoundaryCandidateError(
            f"U80,V20 summary lacks required columns: {missing_summary}"
        )
    if missing_raw:
        raise BoundaryCandidateError(
            f"U80,V20 raw validation lacks required columns: {missing_raw}"
        )
    if len(summary) != 1 or len(raw) != 25:
        raise BoundaryCandidateError(
            f"U80,V20 add-on must contain one summary and 25 raw rows; "
            f"found {len(summary)} and {len(raw)}"
        )

    summary_numeric = sorted(
        ADDON_SUMMARY_REQUIRED
        - {"C_NN_source", "C_NN_sampling", "twist_spread_is_standard_error"}
    )
    raw_numeric = sorted(
        ADDON_RAW_REQUIRED - {"source_role", "selection_rule_applied"}
    )
    for column in summary_numeric:
        summary[column] = pd.to_numeric(summary[column], errors="raise")
    for column in raw_numeric:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    finite_summary_columns = [
        column for column in summary_numeric if column not in {"replica_index", "replica_ordinal"}
    ]
    if not np.isfinite(summary[finite_summary_columns].to_numpy(dtype=float)).all():
        raise BoundaryCandidateError("U80,V20 summary contains non-finite values")
    finite_raw_columns = [
        "U",
        "V",
        "kx",
        "ky",
        "C1_NN",
        "source_job_id",
        "seed",
        "E0",
        "D_site",
        "mCDW2_pipi",
        "nn_NN",
        "kinetic_per_site",
        "max_abs_identity_residual",
    ]
    if not np.isfinite(raw[finite_raw_columns].to_numpy(dtype=float)).all():
        raise BoundaryCandidateError("U80,V20 raw validation contains non-finite values")

    summary_bool = _strict_bool(
        summary["twist_spread_is_standard_error"],
        "U80,V20 twist_spread_is_standard_error",
    )
    selected_bool = _strict_bool(
        raw["selection_rule_applied"], "U80,V20 selection_rule_applied"
    )
    if summary_bool.any():
        raise BoundaryCandidateError("U80,V20 twist spread is incorrectly labeled SEM")

    if (
        _canonical_case(summary.iloc[0]["U"], summary.iloc[0]["V"])
        != U80V20_CASE
        or not math.isclose(float(summary.iloc[0]["r"]), 0.25, abs_tol=1e-13)
        or int(summary.iloc[0]["complete_twists"]) != 25
    ):
        raise BoundaryCandidateError("U80,V20 summary has wrong parameters/cardinality")
    if {
        _canonical_case(row.U, row.V) for row in raw.itertuples(index=False)
    } != {U80V20_CASE}:
        raise BoundaryCandidateError("U80,V20 raw table contains another parameter set")
    if raw.duplicated(["kx", "ky"]).any():
        raise BoundaryCandidateError("U80,V20 raw table contains duplicate twists")
    observed_twists = set(zip(raw["kx"].astype(int), raw["ky"].astype(int)))
    if observed_twists != set(base.EXPECTED_TWISTS):
        raise BoundaryCandidateError("U80,V20 raw table has the wrong 25-twist panel")

    selected_rows = raw[selected_bool].copy()
    canonical_rows = raw[~selected_bool].copy()
    if len(selected_rows) != 1 or len(canonical_rows) != 24:
        raise BoundaryCandidateError("U80,V20 must select exactly one replica and 24 canonicals")
    selected = selected_rows.iloc[0]
    if not (
        (float(selected["U"]), float(selected["V"]), int(selected["kx"]), int(selected["ky"]))
        == SELECTED_REPLICA_TARGET
        and int(selected["source_job_id"]) == SELECTED_REPLICA_JOB_ID
        and int(selected["seed"]) == SELECTED_REPLICA_SEED
        and int(selected["replica_ordinal"]) == SELECTED_REPLICA_ORDINAL
        and math.isfinite(float(selected["replica_index"]))
        and "replica" in str(selected["source_role"]).lower()
        and math.isclose(
            float(selected["C1_NN"]), SELECTED_REPLICA_C_NN, abs_tol=5e-13, rel_tol=0
        )
    ):
        raise BoundaryCandidateError("U80,V20 raw table selected the wrong replica row")
    if not canonical_rows["source_role"].astype(str).str.lower().str.contains("canonical").all():
        raise BoundaryCandidateError("U80,V20 non-selected rows are not all canonical")

    C = raw["C1_NN"].to_numpy(dtype=float)
    if not ((C >= -0.75) & (C < 0.0)).all():
        raise BoundaryCandidateError("U80,V20 C_NN lies outside [-0.75,0)")
    if not (
        raw["D_site"].between(0.0, 1.0).all()
        and raw["mCDW2_pipi"].between(0.0, 1.0 + 1e-10).all()
        and raw["nn_NN"].between(0.0, 4.0).all()
    ):
        raise BoundaryCandidateError("U80,V20 common physical bounds failed")
    if (raw["max_abs_identity_residual"].abs() > 1.0e-8).any():
        raise BoundaryCandidateError("U80,V20 raw identity tolerance failed")

    row = summary.iloc[0]
    recomputed = {
        "C_NN": float(np.mean(C)),
        "C_NN_min": float(np.min(C)),
        "C_NN_max": float(np.max(C)),
        "C_NN_spread": float(np.ptp(C)),
        "C_NN_population_std_diagnostic": float(np.std(C, ddof=0)),
        "D_site_panel_mean": float(raw["D_site"].mean()),
        "mCDW2_pipi_panel_mean": float(raw["mCDW2_pipi"].mean()),
        "nn_NN_panel_mean": float(raw["nn_NN"].mean()),
        "kinetic_per_site_panel_mean": float(raw["kinetic_per_site"].mean()),
        "max_abs_identity_residual": float(
            raw["max_abs_identity_residual"].abs().max()
        ),
    }
    for column, value in recomputed.items():
        if not math.isclose(float(row[column]), value, abs_tol=5e-13, rel_tol=0):
            raise BoundaryCandidateError(
                f"U80,V20 stored {column} disagrees with the 25 raw rows"
            )
    weights = np.where(raw["kx"].astype(int).eq(raw["ky"].astype(int)), 1.0, 2.0)
    weighted = float(np.average(C, weights=weights))
    if not (
        math.isclose(
            float(row["C_NN_symmetry_weighted_diagnostic"]),
            weighted,
            abs_tol=5e-13,
            rel_tol=0,
        )
        and math.isclose(
            float(row["C_NN_symmetry_weighted_minus_primary"]),
            weighted - recomputed["C_NN"],
            abs_tol=5e-13,
            rel_tol=0,
        )
    ):
        raise BoundaryCandidateError("U80,V20 symmetry-weighted diagnostic is inconsistent")
    direct = 1.0 + ((160.0 - 20.0) / (80.0 - 20.0)) * (
        2.0 * recomputed["C_NN"] - 0.5
    )
    if not math.isclose(float(row["s_eq10_signed"]), direct, abs_tol=5e-13, rel_tol=0):
        raise BoundaryCandidateError("U80,V20 stored direct Eq. (10) value is inconsistent")
    if not math.isclose(
        recomputed["C_NN"], EXPECTED_U80V20_C_NN_MEAN, abs_tol=5e-13, rel_tol=0
    ):
        raise BoundaryCandidateError("U80,V20 C_NN mean differs from reviewed result")
    if not (
        str(row["C_NN_source"]).strip()
        and "25" in str(row["C_NN_sampling"])
        and "unweighted" in str(row["C_NN_sampling"]).lower()
    ):
        raise BoundaryCandidateError("U80,V20 summary lacks explicit source/sampling labels")

    normalized = summary.copy()
    normalized["C_NN_fidelity"] = "P25"
    input_hashes = {
        ADDON_LEDGER_BASENAME: snapshot_ledger_sha256,
        "independent_deep_audit": deep_audit_sha256,
        ADDON_SUMMARY_RELATIVE.as_posix(): ledger_entries[
            ADDON_SUMMARY_RELATIVE.as_posix()
        ],
        ADDON_RAW_RELATIVE.as_posix(): ledger_entries[ADDON_RAW_RELATIVE.as_posix()],
        ADDON_PROVENANCE_RELATIVE.as_posix(): ledger_entries[
            ADDON_PROVENANCE_RELATIVE.as_posix()
        ],
    }
    return normalized, raw, provenance, input_hashes


def load_u40_v10_endpoint() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate U40,V10 as an independent complete F861 Mott-side endpoint."""
    summary = _load_csv(base.U40_SUMMARY, "reviewed U40 full-861 summary")
    rows = _load_csv(base.U40_ROWS, "reviewed U40 full-861 rows")
    selected = summary[
        summary.apply(
            lambda row: _canonical_case(row["U"], row["V"]) == U40V10_CASE,
            axis=1,
        )
    ].copy()
    if len(selected) != 1:
        raise BoundaryCandidateError("Reviewed U40 summary must contain U40,V10 exactly once")
    control = selected.iloc[0]
    if not (
        int(control["wedge_rows"]) == 861
        and math.isclose(float(control["wedge_completion_fraction"]), 1.0)
        and math.isclose(float(control["quadrature_weight_observed"]), 1600.0)
        and math.isclose(float(control["quadrature_completion_fraction"]), 1.0)
        and str(control["branch"]).strip().lower() == "mott"
    ):
        raise BoundaryCandidateError("U40,V10 is not a complete full-861 Mott row")

    group = rows[
        (rows["U"].astype(float) == 40.0)
        & np.isclose(rows["V"].astype(float), 10.0)
    ].copy()
    if len(group) != 861 or group.duplicated(["kx", "ky"]).any():
        raise BoundaryCandidateError("U40,V10 raw wedge is not 861 unique rows")
    expected_wedge = {(kx, ky) for ky in range(41) for kx in range(ky + 1)}
    observed_wedge = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
    if observed_wedge != expected_wedge:
        raise BoundaryCandidateError("U40,V10 raw wedge has the wrong coordinates")
    identity_columns = [
        "energy_identity_residual",
        "connected_density_identity_residual",
        "kinetic_identity_residual",
        "charge_identity_residual",
    ]
    if not set(identity_columns).issubset(group.columns):
        raise BoundaryCandidateError("U40,V10 raw wedge lacks identity residuals")
    if group[identity_columns].abs().to_numpy(dtype=float).max() > 1.0e-8:
        raise BoundaryCandidateError("U40,V10 raw wedge fails identity tolerance")

    weights = base.legacy_analysis.trapezoidal_weights(group)
    if not math.isclose(float(weights.sum()), 1600.0, abs_tol=1e-12, rel_tol=0):
        raise BoundaryCandidateError("U40,V10 quadrature weights do not sum to 1600")
    C = group["C1_NN"].to_numpy(dtype=float)
    full = float(np.average(C, weights=weights))
    full_std = float(np.sqrt(np.average((C - full) ** 2, weights=weights)))
    if not (
        math.isclose(full, float(control["C1_NN_mean"]), abs_tol=5e-13, rel_tol=0)
        and math.isclose(
            full_std, float(control["C1_NN_std"]), abs_tol=5e-13, rel_tol=0
        )
    ):
        raise BoundaryCandidateError("U40,V10 stored C_NN mean/spread is inconsistent")
    panel_set = set(base.EXPECTED_TWISTS)
    panel = group[
        group.apply(
            lambda row: (int(row["kx"]), int(row["ky"])) in panel_set,
            axis=1,
        )
    ]
    if len(panel) != 25:
        raise BoundaryCandidateError("U40,V10 lacks the reviewed 25-point panel")
    panel_mean = float(panel["C1_NN"].mean())
    bias = panel_mean - full
    if abs(bias) > 1.0e-6:
        raise BoundaryCandidateError(
            f"U40,V10 P25/F861 calibration bias exceeds 1e-6: {bias:+.6g}"
        )

    node = pd.DataFrame(
        [
            {
                "U": 40.0,
                "V": 10.0,
                "r": 0.25,
                "C_NN": full,
                "C_NN_min": np.nan,
                "C_NN_max": np.nan,
                "C_NN_spread": np.nan,
                "C_NN_population_std_diagnostic": full_std,
                "complete_twists": 861,
                "C_NN_source": "existing U=40 all-twist fullobs control",
                "C_NN_sampling": "full_861_wedge_trapezoidal_weight_1600",
                "C_NN_fidelity": "F861",
                "twist_spread_is_standard_error": False,
            }
        ]
    )
    calibration = pd.DataFrame(
        [
            {
                "U": 40.0,
                "V": 10.0,
                "V_over_U": 0.25,
                "C_NN_full_861": full,
                "C_NN_panel_25": panel_mean,
                "panel_minus_full": bias,
                "abs_panel_minus_full": abs(bias),
                "C_NN_panel_spread": float(
                    panel["C1_NN"].max() - panel["C1_NN"].min()
                ),
                "C_NN_full_grid_population_std_diagnostic": full_std,
                "panel_bias_tolerance": 1.0e-6,
                "passes_panel_bias_gate": True,
                "panel_estimator": "unweighted arithmetic mean over reviewed 25 twists",
                "full_estimator": (
                    "861-point wedge with exchange and trapezoidal endpoint weights "
                    "(weight 1600)"
                ),
            }
        ]
    )
    return node, calibration


def _endpoint_pointwise_row(
    node: pd.Series,
    base_pointwise: pd.DataFrame,
    gz_points: pd.DataFrame,
    *,
    analytic_phase_basis: str,
) -> dict[str, object]:
    U = float(node["U"])
    V = float(node["V"])
    gz = gz_points[
        (gz_points["U"].astype(float) == U)
        & np.isclose(gz_points["V"].astype(float), V)
    ]
    if len(gz) != 1:
        raise BoundaryCandidateError(f"Reviewed GZ input lacks U={U:g},V={V:g}")
    gz_row = gz.iloc[0]
    anchor = base_pointwise[
        (base_pointwise["U"].astype(float) == U)
        & np.isclose(base_pointwise["V"].astype(float), 0.0)
    ]
    if len(anchor) != 1:
        raise BoundaryCandidateError(f"Base pointwise table lacks U={U:g},V=0 anchor")
    anchor = anchor.iloc[0]
    factor = (2.0 * U - V) / (U - V)
    C = float(node["C_NN"])
    reference = float(anchor["C_NN"])
    anchor_C = -float(gz_row["s_u0"]) / 4.0
    drift = C - reference
    effective_C = anchor_C + drift
    anchored_prediction = 1.0 + factor * (2.0 * effective_C - 0.5)
    direct_prediction = 1.0 + factor * (2.0 * C - 0.5)
    observed = -float(gz_row["s"])
    axis_prediction = float(
        base.legacy_fig4.mott_scale_law_from_axis_anchor(
            np.asarray([V / U]), np.asarray([-float(gz_row["s_u0"])])
        )[0]
    )
    if U == 40.0:
        reference_sampling = "F861 minus F861 at U=40,V=0"
    elif U == 80.0:
        reference_sampling = "P25 minus P25 at U=80,V=0"
    else:  # pragma: no cover - fixed endpoint inventory makes this unreachable
        raise BoundaryCandidateError(f"Unsupported endpoint family U={U:g}")
    return {
        "U": U,
        "V": V,
        "r": V / U,
        "C_NN": C,
        "C_NN_min": node.get("C_NN_min", np.nan),
        "C_NN_max": node.get("C_NN_max", np.nan),
        "C_NN_spread": node.get("C_NN_spread", np.nan),
        "C_NN_population_std_diagnostic": node[
            "C_NN_population_std_diagnostic"
        ],
        "complete_twists": int(node["complete_twists"]),
        "C_NN_source": node["C_NN_source"],
        "C_NN_sampling": node["C_NN_sampling"],
        "C_NN_fidelity": node["C_NN_fidelity"],
        "twist_spread_is_standard_error": False,
        "branch": gz_row["branch"],
        "s": float(gz_row["s"]),
        "s_u0": float(gz_row["s_u0"]),
        "source_csv": gz_row["source_csv"],
        "analytic_phase": "Mott",
        "analytic_phase_basis": analytic_phase_basis,
        "s_signed_observed": observed,
        "s_u0_signed": -float(gz_row["s_u0"]),
        "eq10_factor": factor,
        "C_NN_matched_V0_reference": reference,
        "C_NN_reference_sampling": reference_sampling,
        "C_NN_axis_anchor_from_s_observed_V0": anchor_C,
        "C_NN_measured_drift_from_matched_V0": drift,
        "C_NN_effective_axis_anchored_drift": effective_C,
        "s_eq10_axis_anchored_C_NN_drift": anchored_prediction,
        "s_eq10_direct_fullobs_C_NN": direct_prediction,
        "s_axis_anchor_signed": axis_prediction,
        "drift_residual_observed_minus_prediction": observed - anchored_prediction,
        "axis_anchor_residual_observed_minus_prediction": observed - axis_prediction,
        "eq10_convention": "signed s_NN in omega_GZ=s_NN epsilon_NN",
        "residual_convention": "observed minus prediction",
    }


def _recompute_metrics(pointwise: pd.DataFrame) -> pd.DataFrame:
    metrics: list[dict[str, object]] = []
    for U, group in pointwise.groupby("U", sort=True):
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
                        "U": float(U),
                        "scope": scope,
                        "model": model,
                        "point_count": int(len(scoped)),
                        "rmse": float(np.sqrt(np.mean(residual**2))),
                        "mae": float(np.mean(np.abs(residual))),
                        "max_abs_residual": float(np.max(np.abs(residual))),
                    }
                )
    return pd.DataFrame(metrics)


def assemble_final_pointwise(
    base_p25: pd.DataFrame,
    base_controls: pd.DataFrame,
    base_calibration: pd.DataFrame,
    addon_summary: pd.DataFrame,
    u40v10_node: pd.DataFrame,
    u40v10_calibration: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Assemble and independently validate the exact 19-node final table."""
    base_pointwise, _ = base.assemble_pointwise(
        base_p25, base_controls, base_calibration
    )
    base_pointwise["s_eq10_direct_fullobs_C_NN"] = 1.0 + base_pointwise[
        "eq10_factor"
    ].astype(float) * (2.0 * base_pointwise["C_NN"].astype(float) - 0.5)

    addon = addon_summary.iloc[0].copy()
    addon_node = pd.Series(
        {
            "U": 80.0,
            "V": 20.0,
            "r": 0.25,
            "C_NN": float(addon["C_NN"]),
            "C_NN_min": float(addon["C_NN_min"]),
            "C_NN_max": float(addon["C_NN_max"]),
            "C_NN_spread": float(addon["C_NN_spread"]),
            "C_NN_population_std_diagnostic": float(
                addon["C_NN_population_std_diagnostic"]
            ),
            "complete_twists": 25,
            "C_NN_source": "replica-resolved fullobs P25",
            "C_NN_sampling": "25-twist unweighted arithmetic mean",
            "C_NN_fidelity": "P25",
        }
    )

    gz_points = base._read_csv(base.GZ_POINTS, "reviewed GZ points")
    endpoint_rows = [
        _endpoint_pointwise_row(
            u40v10_node.iloc[0],
            base_pointwise,
            gz_points,
            analytic_phase_basis=(
                "V=10 is below the independently bracketed U=40 Mott endpoint "
                "V_Mott=10.01"
            ),
        ),
        _endpoint_pointwise_row(
            addon_node,
            base_pointwise,
            gz_points,
            analytic_phase_basis=(
                "V/U=1/4 boundary endpoint; fullobs charge/spin diagnostics "
                "support the Mott/spin side"
            ),
        ),
    ]
    pointwise = pd.concat(
        [base_pointwise, pd.DataFrame(endpoint_rows)], ignore_index=True, sort=False
    ).sort_values(["U", "V"]).reset_index(drop=True)
    observed_cases = {
        _canonical_case(row.U, row.V) for row in pointwise.itertuples(index=False)
    }
    if (
        len(pointwise) != 19
        or pointwise.duplicated(["U", "V"]).any()
        or observed_cases != set(FINAL_POINTWISE_CASES_19)
    ):
        raise BoundaryCandidateError("Final pointwise table is not the exact 19-node inventory")
    counts = pointwise.groupby("U").size().to_dict()
    if counts != {20.0: 6, 40.0: 6, 80.0: 7}:
        raise BoundaryCandidateError(f"Final pointwise family counts are wrong: {counts}")
    if _strict_bool(
        pointwise["twist_spread_is_standard_error"],
        "final twist_spread_is_standard_error",
    ).any():
        raise BoundaryCandidateError("Final pointwise table labels a spread as SEM")
    required_numeric = [
        "U",
        "V",
        "r",
        "C_NN",
        "s_signed_observed",
        "eq10_factor",
        "s_eq10_axis_anchored_C_NN_drift",
        "s_eq10_direct_fullobs_C_NN",
        "s_axis_anchor_signed",
        "drift_residual_observed_minus_prediction",
    ]
    if not np.isfinite(pointwise[required_numeric].to_numpy(dtype=float)).all():
        raise BoundaryCandidateError("Final pointwise table contains non-finite required data")
    if not np.allclose(
        pointwise["r"], pointwise["V"] / pointwise["U"], atol=1e-13, rtol=0
    ):
        raise BoundaryCandidateError("Final pointwise r is inconsistent with V/U")

    calibration = pd.concat(
        [base_calibration, u40v10_calibration], ignore_index=True, sort=False
    ).sort_values("V").reset_index(drop=True)
    if (
        len(calibration) != 5
        or calibration.duplicated(["U", "V"]).any()
        or set(calibration["V"].astype(float)) != {0.0, 4.0, 8.0, 9.0, 10.0}
        or not calibration["passes_panel_bias_gate"].astype(bool).all()
        or float(calibration["abs_panel_minus_full"].max()) > 1.0e-6
    ):
        raise BoundaryCandidateError("Final U40 P25/F861 calibration is invalid")
    return pointwise, _recompute_metrics(pointwise), calibration


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-p25-bundle", type=Path, required=True)
    parser.add_argument("--base-snapshot-ledger-sha256", required=True)
    parser.add_argument("--base-deep-audit", type=Path, required=True)
    parser.add_argument("--base-deep-audit-sha256", required=True)
    parser.add_argument("--u80v20-addon", type=Path, required=True)
    parser.add_argument("--u80v20-snapshot-ledger-sha256", required=True)
    parser.add_argument("--u80v20-deep-audit", type=Path, required=True)
    parser.add_argument("--u80v20-deep-audit-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--publication-candidate",
        action="store_true",
        help="Remove the watermark while retaining strict tmp/-only confinement.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _validate_base_builder_identity()
    try:
        out = base.validate_output_dir(args.output_dir)
        base_p25, base_raw, base_provenance, base_hashes = base.validate_p25_bundle(
            args.base_p25_bundle,
            snapshot_ledger_sha256=args.base_snapshot_ledger_sha256,
            deep_audit=args.base_deep_audit,
            deep_audit_sha256=args.base_deep_audit_sha256,
        )
        base_controls, base_calibration = base.load_reviewed_u40_controls()
    except base.CandidateError as exc:
        raise BoundaryCandidateError(str(exc)) from exc

    addon_summary, addon_raw, addon_provenance, addon_hashes = validate_addon_bundle(
        args.u80v20_addon,
        snapshot_ledger_sha256=args.u80v20_snapshot_ledger_sha256,
        deep_audit=args.u80v20_deep_audit,
        deep_audit_sha256=args.u80v20_deep_audit_sha256,
    )
    u40v10_node, u40v10_calibration = load_u40_v10_endpoint()
    pointwise, metrics, calibration = assemble_final_pointwise(
        base_p25,
        base_controls,
        base_calibration,
        addon_summary,
        u40v10_node,
        u40v10_calibration,
    )

    figure_pdf_name = (
        CANDIDATE_FIGURE_PDF_BASENAME
        if args.publication_candidate
        else STAGING_FIGURE_PDF_BASENAME
    )
    figure_png_name = (
        CANDIDATE_FIGURE_PNG_BASENAME
        if args.publication_candidate
        else STAGING_FIGURE_PNG_BASENAME
    )
    out.mkdir(mode=0o755)
    pointwise.to_csv(out / POINTWISE_BASENAME, index=False)
    metrics.to_csv(out / METRICS_BASENAME, index=False)
    calibration.to_csv(out / CALIBRATION_BASENAME, index=False)
    base.render(
        pointwise,
        out / figure_pdf_name,
        out / figure_png_name,
        watermark=not args.publication_candidate,
    )
    output_names = (
        POINTWISE_BASENAME,
        METRICS_BASENAME,
        CALIBRATION_BASENAME,
        figure_pdf_name,
        figure_png_name,
    )
    output_hashes = {name: sha256(out / name) for name in output_names}
    endpoint_report: dict[str, dict[str, float]] = {}
    for U, V in (U40V10_CASE, U80V20_CASE):
        row = pointwise[
            pointwise["U"].eq(U) & np.isclose(pointwise["V"], V)
        ].iloc[0]
        endpoint_report[f"U{U:g}_V{V:g}"] = {
            "C_NN": float(row["C_NN"]),
            "s_observed_signed": float(row["s_signed_observed"]),
            "s_eq10_axis_anchored_C_NN_drift": float(
                row["s_eq10_axis_anchored_C_NN_drift"]
            ),
            "s_eq10_direct_fullobs_C_NN": float(
                row["s_eq10_direct_fullobs_C_NN"]
            ),
            "observed_minus_anchored_drift_prediction": float(
                row["drift_residual_observed_minus_prediction"]
            ),
        }
    provenance = {
        "schema_version": 1,
        "data_product": "fig4_19node_axis_anchored_eq10_completed_fullobs_C_NN_drift",
        "created_at": datetime.now().astimezone().isoformat(),
        "publication_artifacts_modified": False,
        "builder": {
            "path": str(SCRIPT),
            "sha256": sha256(SCRIPT),
            "base_builder": str(Path(base.__file__).resolve()),
            "base_builder_sha256": BASE_BUILDER_SHA256,
        },
        "plot_model": (
            "C_eff=s_obs(U,0)/4 + C_NN(U,V)-C_NN(U,0), with matched "
            "P25/P25 or F861/F861 sampling, then Eq. (10); no finite-V fit"
        ),
        "pointwise_inventory": {
            "rows": 19,
            "family_counts": {"U20": 6, "U40": 6, "U80": 7},
            "P25_cases": 14,
            "P25_logical_rows": 350,
            "F861_control_cases": 5,
            "old_frozen_P25_cases": 13,
            "old_frozen_P25_rows": len(base_raw),
            "U80V20_addon_rows": len(addon_raw),
            "same_target_duplicates_averaged": False,
        },
        "base_P25_bundle": {
            "path": str(Path(args.base_p25_bundle).expanduser().resolve()),
            "input_hashes": base_hashes,
            "provenance_schema": base_provenance.get("schema"),
        },
        "U80V20_addon_bundle": {
            "path": str(Path(args.u80v20_addon).expanduser().resolve()),
            "input_hashes": addon_hashes,
            "provenance_schema": addon_provenance.get("schema"),
            "selected_job_id": SELECTED_REPLICA_JOB_ID,
            "selected_seed": SELECTED_REPLICA_SEED,
            "selected_replica_ordinal": SELECTED_REPLICA_ORDINAL,
        },
        "reviewed_inputs_sha256": {
            str(path.relative_to(ROOT)): digest
            for path, digest in base.REVIEWED_INPUT_SHA256.items()
        },
        "endpoint_values": endpoint_report,
        "U40_calibration": {
            "rows": len(calibration),
            "max_abs_panel_minus_full": float(
                calibration["abs_panel_minus_full"].max()
            ),
            "tolerance": 1.0e-6,
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
                "P25_logical_rows": len(base_raw) + len(addon_raw),
                "U40_calibration_rows": len(calibration),
                "max_U40_panel_bias": float(
                    calibration["abs_panel_minus_full"].max()
                ),
                "endpoints": endpoint_report,
                "figure_pdf_sha256": output_hashes[figure_pdf_name],
                "figure_png_sha256": output_hashes[figure_png_name],
                "publication_artifacts_modified": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
