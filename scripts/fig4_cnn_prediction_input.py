#!/usr/bin/env python3
"""Fail-closed input contract for the all-F861 Fig. 4 Eq. (10) bundle.

Publication use of Fig. 4 must not fall back to the deterministic 25-point
pilot, a common :math:`C_{NN}`, or a V=0 axis anchor. The only production
input accepted here is the exact 16-row product made from full 861-coordinate
wedge averages: twelve wedges assembled from the hash-pinned 300 pilot rows
plus the 10,032-point complement, and four independently existing U=40 F861
controls.

The old 25-point analyzer remains a decision-audit tool. Its schema-v1 mixed
P25/F861 bundle is intentionally incompatible with this publication gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_FULL861_ANALYZER = ROOT / "scripts/analyze_fig4_cnn_full861_campaign.py"
REVIEWED_SNAPSHOT_ROOT = (
    ROOT / "data/fullobs/fullobs_861twist_fig4_cnn_20260821"
)
REVIEWED_FINALIZER_SHA256 = (
    "997814a4f4cd69e45dbce7f6eb78c1102e863d13209e328998c1ad597bd2ed2c"
)
SNAPSHOT_LEDGER_RELATIVE = Path("metadata/snapshot_file_sha256.tsv")

FULL861_EXPANSION_SOURCE = "fullobs F861 expansion (25 reused + 836 complement)"
FULL861_CONTROL_SOURCE = "fullobs F861 existing U=40 control"
FULL861_SAMPLING = "full_861_wedge_exchange_trapezoidal_weight_1600"
FULL861_FIDELITY = "F861"
EQ10_CONVENTION = "signed s_NN in omega_GZ=s_NN epsilon_NN"
POINTWISE_BASENAME = "fig4_cnn_pointwise_eq10.csv"
PROVENANCE_BASENAME = "fig4_cnn_analysis_provenance.json"
SCHEMA_VERSION = 3
DATA_PRODUCT = "fig4_pointwise_full861_direct_fullobs_C_NN_eq10"
C_NN_OBSERVABLE = "<C1_NN>"
DECISION_GATE_ALGORITHM = "fig4_cnn_25_to_861_quadrature_v2"
FIXTURE_DATA_PRODUCT = "synthetic_fig4_pointwise_full861_contract_fixture"
MAX_REVIEWED_IDENTITY_TOLERANCE = 1.0e-8
REVIEWED_FULL861_ANALYZER_SHA256 = (
    "66323714273c8e8bd2940b8d901588689034a807af63e5b4bcf383759e94bf12"
)

# Every scientific and quadrature input that defines the reviewed F861
# product is pinned independently. The materialized manifest hash differs
# from its semantic-plan hash; both are required.
REVIEWED_FULL861_PINS = {
    "expansion_manifest_sha256": "53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31",
    "source_25_manifest_sha256": "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5",
    "expansion_plan_sha256": "368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e",
    "wedge_861_sha256": "9efc7f43498726d7d1b1119e85bf617b24370aa7b2ff9d5127a85859602ca93e",
    "solver_sha256": "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b",
    "source_sha256": "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73",
    "qbasis_library_sha256": "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85",
    "u40_summary_sha256": "81d45fe4ea75dee1e121dcb22963652c2253cf5e45a61094c3e153f98e4dd5e4",
    "u40_rows_sha256": "81f50b31cffa6581b27f52b9aced792b9d6cacbb64950471594693473194a5d9",
    "gz_points_sha256": "44755fe1c15efce59903044f31ffa0c794da8d9e85f330f89d3683e6ae609c0a",
    "expansion_generator_sha256": "4bf400ee8f9371f82a8f20712da3852055c79cd07135aa017e2d9c815ce17dc9",
}

ANALYZER_OUTPUT_BASENAMES = (
    "fig4_cnn_full861_campaign_raw_validation.csv",
    "fig4_cnn_full861_campaign_summary.csv",
    "fig4_cnn_full861_u40_control_summary.csv",
    POINTWISE_BASENAME,
    "fig4_cnn_pointwise_family_summary.csv",
)

SNAPSHOT_INPUT_RELATIVE_PATHS = {
    "expansion_manifest": Path("metadata/manifest.tsv"),
    "reused_25_manifest": Path("metadata/reused_25.tsv"),
    "source_25_manifest": Path("metadata/reviewed_inputs/source_25_manifest.tsv"),
    "remote_raw_ledger": Path("metadata/remote_results_sha256.tsv"),
    "campaign_provenance": Path("metadata/provenance.json"),
    "decision_certificate": Path("metadata/decision_certificate.json"),
    "decision_verifier": Path("metadata/tools/generate_batch.py"),
    "snapshot_provenance": Path("metadata/snapshot_provenance.json"),
    "local_summary": Path("analysis/fig4_cnn_full861_summary.csv"),
    "remote_summary": Path("metadata/analysis/fig4_cnn_full861_summary.csv"),
    "remote_provenance": Path(
        "metadata/analysis/fig4_cnn_full861_provenance.json"
    ),
    "local_raw": Path("analysis/fig4_cnn_full861_raw_validation.csv"),
}

# The reviewed finalizer installs this exact executable inventory as 0555 and
# every other file/all child directories as 0444/0555.  Its staging root stays
# 0700 only through the macOS-safe no-replace rename, then becomes 0555 before
# the installed tree can pass its full post-install hash/mode verification.
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

# Compatibility name used by the figure builder. It now denotes the all-F861
# release pins; it is not the former 25-point campaign pin set.
REVIEWED_CAMPAIGN_PINS = REVIEWED_FULL861_PINS

EXPECTED_EXPANSION_CASES = (
    (20.0, 0.0),
    (20.0, 2.0),
    (20.0, 3.0),
    (20.0, 4.0),
    (20.0, 4.5),
    (40.0, 6.0),
    (80.0, 0.0),
    (80.0, 4.0),
    (80.0, 8.0),
    (80.0, 12.0),
    (80.0, 16.0),
    (80.0, 18.0),
)
EXPECTED_CONTROL_CASES = (
    (40.0, 0.0),
    (40.0, 4.0),
    (40.0, 8.0),
    (40.0, 9.0),
)
EXPECTED_POINTWISE_CASES = tuple(
    sorted(set(EXPECTED_EXPANSION_CASES) | set(EXPECTED_CONTROL_CASES))
)

# Old public name retained only for import compatibility in staging helpers.
EXPECTED_CAMPAIGN_CASES = EXPECTED_EXPANSION_CASES

REQUIRED_COLUMNS = {
    "U",
    "V",
    "r",
    "branch",
    "C_NN",
    "C_NN_source",
    "C_NN_sampling",
    "C_NN_fidelity",
    "C_NN_full_wedge_rows",
    "C_NN_quadrature_weight",
    "C_NN_full_quadrature_weighted_population_std",
    "twist_spread_is_standard_error",
    "eq10_factor",
    "s_eq10_signed",
    "eq10_convention",
}


class PointwisePredictionError(RuntimeError):
    """Raised when an Eq. (10) bundle violates the all-F861 contract."""


@dataclass(frozen=True)
class FullobsEq10Bundle:
    """Validated pointwise rows and their inseparable provenance sidecar."""

    rows: pd.DataFrame
    provenance: dict
    source_dir: Path


def eq10_signed(
    U: np.ndarray | float,
    V: np.ndarray | float,
    C_NN: np.ndarray | float,
) -> np.ndarray:
    """Evaluate signed Eq. (10), ``s=1+(2U-V)/(U-V)*(2C_NN-1/2)``."""
    u = np.asarray(U, dtype=float)
    v = np.asarray(V, dtype=float)
    c = np.asarray(C_NN, dtype=float)
    if not (np.isfinite(u).all() and np.isfinite(v).all() and np.isfinite(c).all()):
        raise PointwisePredictionError("Eq. (10) inputs must all be finite")
    if np.any(np.isclose(u - v, 0.0, atol=1.0e-14, rtol=0.0)):
        raise PointwisePredictionError("Eq. (10) is singular at U=V")
    return 1.0 + ((2.0 * u - v) / (u - v)) * (2.0 * c - 0.5)


def _strict_bool(series: pd.Series, label: str) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    invalid = ~values.isin({"true", "false"})
    if invalid.any():
        bad = sorted(values[invalid].unique().tolist())
        raise PointwisePredictionError(
            f"{label} must contain only explicit True/False values; found {bad}"
        )
    return values.eq("true")


def _expected_source(case: tuple[float, float]) -> str:
    if case in set(EXPECTED_EXPANSION_CASES):
        return FULL861_EXPANSION_SOURCE
    return FULL861_CONTROL_SOURCE


def validate_pointwise_eq10_predictions(
    table: pd.DataFrame,
    *,
    allow_fixture: bool = False,
) -> pd.DataFrame:
    """Validate and canonicalize the exact 16-row all-F861 table."""
    missing_columns = REQUIRED_COLUMNS - set(table.columns)
    if missing_columns:
        raise PointwisePredictionError(
            "Pointwise C_NN table is missing required all-F861 columns: "
            f"{sorted(missing_columns)}"
        )

    frame = table.copy()
    if len(frame) != len(EXPECTED_POINTWISE_CASES):
        raise PointwisePredictionError(
            f"Pointwise C_NN table must contain exactly 16 rows; found {len(frame)}"
        )
    numeric_columns = (
        "U",
        "V",
        "r",
        "C_NN",
        "C_NN_full_wedge_rows",
        "C_NN_quadrature_weight",
        "C_NN_full_quadrature_weighted_population_std",
        "eq10_factor",
        "s_eq10_signed",
    )
    for column in numeric_columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise PointwisePredictionError(
                f"Pointwise column {column} must be numeric"
            ) from exc
    if not np.isfinite(frame[list(numeric_columns)].to_numpy(dtype=float)).all():
        raise PointwisePredictionError("Pointwise numeric inputs must all be finite")

    if frame.duplicated(["U", "V"]).any():
        duplicates = frame.loc[
            frame.duplicated(["U", "V"], keep=False), ["U", "V"]
        ].drop_duplicates()
        raise PointwisePredictionError(
            "Duplicate pointwise C_NN cases: "
            f"{[tuple(row) for row in duplicates.to_numpy()]}"
        )
    cases = {(float(row.U), float(row.V)) for row in frame[["U", "V"]].itertuples()}
    expected = set(EXPECTED_POINTWISE_CASES)
    if cases != expected:
        raise PointwisePredictionError(
            "Pointwise C_NN inventory mismatch; "
            f"missing={sorted(expected - cases)}, unexpected={sorted(cases - expected)}"
        )

    expected_r = frame["V"].to_numpy(dtype=float) / frame["U"].to_numpy(dtype=float)
    if not np.allclose(
        frame["r"].to_numpy(dtype=float), expected_r, atol=1.0e-13, rtol=0.0
    ):
        raise PointwisePredictionError("Pointwise r values are inconsistent with V/U")
    if np.any(frame["U"].to_numpy(dtype=float) <= frame["V"].to_numpy(dtype=float)):
        raise PointwisePredictionError("Eq. (10) pointwise inputs require U>V")
    expected_branch = np.where(frame["V"].eq(0.0), "U-only", "Mott/spin")
    if not np.array_equal(frame["branch"].astype(str).to_numpy(), expected_branch):
        raise PointwisePredictionError(
            "Pointwise branch must be U-only at V=0 and Mott/spin at finite V"
        )

    c_values = frame["C_NN"].to_numpy(dtype=float)
    if np.any((c_values < -0.75) | (c_values >= 0.0)):
        raise PointwisePredictionError(
            "Mott-side fullobs C_NN values must satisfy -0.75 <= C_NN < 0"
        )
    if np.any(
        frame["C_NN_full_quadrature_weighted_population_std"].to_numpy(dtype=float)
        < 0.0
    ):
        raise PointwisePredictionError("F861 population-spread diagnostics cannot be negative")
    if not frame["C_NN_full_wedge_rows"].eq(861).all():
        raise PointwisePredictionError("Every pointwise C_NN input must contain 861 wedge rows")
    if not np.allclose(
        frame["C_NN_quadrature_weight"], 1600.0, atol=1.0e-12, rtol=0.0
    ):
        raise PointwisePredictionError(
            "Every pointwise C_NN input must have quadrature weight 1600"
        )
    if not frame["C_NN_sampling"].astype(str).eq(FULL861_SAMPLING).all():
        raise PointwisePredictionError(
            "Publication C_NN sampling must be F861 for all 16 rows; P25 inputs are rejected"
        )
    if not frame["C_NN_fidelity"].astype(str).eq(FULL861_FIDELITY).all():
        raise PointwisePredictionError("Every pointwise C_NN source must be labeled F861")
    for row in frame.itertuples(index=False):
        case = (float(row.U), float(row.V))
        if str(row.C_NN_source) != _expected_source(case):
            raise PointwisePredictionError(
                f"Wrong F861 source label for (U,V)={case}: {row.C_NN_source!r}"
            )

    if _strict_bool(
        frame["twist_spread_is_standard_error"],
        "twist_spread_is_standard_error",
    ).any():
        raise PointwisePredictionError(
            "Deterministic quadrature-grid spread must not be labeled a standard error"
        )
    if not frame["eq10_convention"].astype(str).eq(EQ10_CONVENTION).all():
        raise PointwisePredictionError(
            "Eq. (10) convention mismatch: predictions must be signed s_NN"
        )

    recomputed_factor = (
        2.0 * frame["U"].to_numpy(dtype=float) - frame["V"].to_numpy(dtype=float)
    ) / (frame["U"].to_numpy(dtype=float) - frame["V"].to_numpy(dtype=float))
    if not np.allclose(
        frame["eq10_factor"].to_numpy(dtype=float),
        recomputed_factor,
        atol=5.0e-13,
        rtol=5.0e-13,
    ):
        raise PointwisePredictionError(
            "Stored eq10_factor does not reproduce (2U-V)/(U-V)"
        )
    recomputed = eq10_signed(
        frame["U"].to_numpy(dtype=float),
        frame["V"].to_numpy(dtype=float),
        c_values,
    )
    supplied = frame["s_eq10_signed"].to_numpy(dtype=float)
    if not np.allclose(supplied, recomputed, atol=5.0e-13, rtol=5.0e-13):
        raise PointwisePredictionError(
            "Stored s_eq10_signed does not reproduce signed Eq. (10); "
            f"max_abs_error={float(np.max(np.abs(supplied - recomputed))):.3e}"
        )
    if np.any(recomputed >= 0.0):
        raise PointwisePredictionError(
            "Expected negative signed Mott-side Eq. (10) predictions"
        )
    frame["eq10_factor"] = recomputed_factor
    frame["s_eq10_signed"] = recomputed

    if "fixture_only" in frame.columns:
        flags = _strict_bool(frame["fixture_only"], "fixture_only")
        if flags.any() and not flags.all():
            raise PointwisePredictionError("Mixed production and fixture rows are not allowed")
        if flags.any():
            if not allow_fixture:
                raise PointwisePredictionError(
                    "Synthetic fixture table rejected; pass allow_fixture=True only for staging"
                )
            if (
                "fixture_label" not in frame.columns
                or frame["fixture_label"].isna().any()
                or frame["fixture_label"].astype(str).str.strip().eq("").any()
            ):
                raise PointwisePredictionError("Fixture rows require a nonempty fixture_label")

    return frame.sort_values(["U", "V"]).reset_index(drop=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_mapping(payload: object, label: str) -> dict:
    if not isinstance(payload, dict):
        raise PointwisePredictionError(f"Analysis provenance {label} must be an object")
    return payload


def _load_json_mapping(path: Path, label: str) -> dict:
    try:
        return _require_mapping(json.loads(path.read_text()), label)
    except (OSError, json.JSONDecodeError) as exc:
        raise PointwisePredictionError(f"Could not parse {label}: {path}") from exc


def validate_immutable_snapshot_tree(snapshot_root: Path) -> None:
    """Verify finalizer modes, no-link policy, and the complete file ledger."""
    supplied = Path(snapshot_root).expanduser()
    if supplied.is_symlink():
        raise PointwisePredictionError(
            f"Reviewed immutable snapshot root must not be a symlink: {supplied}"
        )
    snapshot_root = supplied.resolve()
    if not snapshot_root.is_dir():
        raise PointwisePredictionError(
            f"Reviewed immutable snapshot root is missing: {snapshot_root}"
        )

    for current, directory_names, file_names in os.walk(
        snapshot_root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        if current_path.is_symlink():
            raise PointwisePredictionError(
                f"Immutable snapshot contains a linked directory: {current_path}"
            )
        if stat.S_IMODE(current_path.stat().st_mode) != 0o555:
            relative = (
                "."
                if current_path == snapshot_root
                else current_path.relative_to(snapshot_root).as_posix()
            )
            raise PointwisePredictionError(
                f"Immutable snapshot directory mode must be exactly 0555: {relative}"
            )

        for name in (*directory_names, *file_names):
            path = current_path / name
            path_stat = path.lstat()
            if stat.S_ISLNK(path_stat.st_mode):
                raise PointwisePredictionError(
                    "Immutable snapshot contains a symlink: "
                    + path.relative_to(snapshot_root).as_posix()
                )
            if stat.S_ISDIR(path_stat.st_mode):
                continue
            if not stat.S_ISREG(path_stat.st_mode):
                raise PointwisePredictionError(
                    "Immutable snapshot contains a non-regular filesystem entry: "
                    + path.relative_to(snapshot_root).as_posix()
                )
            relative = path.relative_to(snapshot_root).as_posix()
            expected_mode = (
                0o555 if relative in SNAPSHOT_EXECUTABLE_RELATIVE_PATHS else 0o444
            )
            if stat.S_IMODE(path_stat.st_mode) != expected_mode:
                raise PointwisePredictionError(
                    "Immutable snapshot file mode differs from the reviewed finalizer: "
                    f"{relative} must be {expected_mode:04o}"
                )

    ledger_path = snapshot_root / SNAPSHOT_LEDGER_RELATIVE
    if not ledger_path.is_file():
        raise PointwisePredictionError(
            f"Reviewed immutable snapshot hash ledger is missing: {ledger_path}"
        )
    try:
        ledger = pd.read_csv(ledger_path, sep="\t", dtype=str)
    except Exception as exc:
        raise PointwisePredictionError(
            f"Could not read immutable snapshot hash ledger: {ledger_path}"
        ) from exc
    required = {"sha256", "size_bytes", "relative_path"}
    if set(ledger.columns) != required or ledger.empty:
        raise PointwisePredictionError(
            "Immutable snapshot hash ledger has the wrong schema or is empty"
        )
    if ledger["relative_path"].duplicated().any():
        raise PointwisePredictionError(
            "Immutable snapshot hash ledger contains duplicate relative paths"
        )

    recorded: dict[str, tuple[str, int]] = {}
    for row in ledger.itertuples(index=False):
        relative = Path(str(row.relative_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise PointwisePredictionError(
                f"Unsafe path in immutable snapshot hash ledger: {relative}"
            )
        digest = str(row.sha256)
        try:
            size = int(row.size_bytes)
        except (TypeError, ValueError) as exc:
            raise PointwisePredictionError(
                f"Noninteger size in immutable snapshot hash ledger: {relative}"
            ) from exc
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise PointwisePredictionError(
                f"Invalid SHA-256 in immutable snapshot hash ledger: {relative}"
            )
        if size < 0:
            raise PointwisePredictionError(
                f"Negative size in immutable snapshot hash ledger: {relative}"
            )
        recorded[relative.as_posix()] = (digest, size)

    actual_paths = sorted(
        path
        for path in snapshot_root.rglob("*")
        if path.is_file() and path != ledger_path
    )
    actual_relative = {path.relative_to(snapshot_root).as_posix() for path in actual_paths}
    if actual_relative != set(recorded):
        missing = sorted(set(recorded) - actual_relative)
        unexpected = sorted(actual_relative - set(recorded))
        raise PointwisePredictionError(
            "Immutable snapshot file inventory differs from the finalizer ledger; "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )
    if sum(path.parts[0] == "raw" for path in map(Path, actual_relative)) != 10_332:
        raise PointwisePredictionError(
            "Immutable snapshot ledger does not contain exactly 10,332 raw outputs"
        )
    for path in actual_paths:
        relative = path.relative_to(snapshot_root).as_posix()
        digest, size = recorded[relative]
        if path.stat().st_size != size or _sha256(path) != digest:
            raise PointwisePredictionError(
                f"Immutable snapshot file fails its finalizer ledger: {relative}"
            )


def _bind_and_replay_reviewed_analyzer(
    provenance: dict,
    *,
    pointwise_path: Path,
    scale_points_path: Path,
) -> None:
    """Bind claims to real immutable bytes and replay the reviewed analyzer."""
    analyzer_claim = provenance.get("analyzer")
    if not isinstance(analyzer_claim, str):
        raise PointwisePredictionError(
            "Analysis provenance lacks the reviewed analyzer path"
        )
    analyzer_path = Path(analyzer_claim).expanduser().resolve()
    reviewed_analyzer = REVIEWED_FULL861_ANALYZER.resolve()
    if analyzer_path != reviewed_analyzer or not analyzer_path.is_file():
        raise PointwisePredictionError(
            "Analysis provenance is not bound to the canonical reviewed all-F861 analyzer"
        )
    if (
        _sha256(analyzer_path) != REVIEWED_FULL861_ANALYZER_SHA256
        or provenance.get("analyzer_sha256") != REVIEWED_FULL861_ANALYZER_SHA256
    ):
        raise PointwisePredictionError(
            "Reviewed all-F861 analyzer bytes do not match the release pin"
        )

    snapshot_claim = provenance.get("snapshot_root")
    if not isinstance(snapshot_claim, str):
        raise PointwisePredictionError(
            "Analysis provenance lacks the immutable snapshot root"
        )
    claimed_snapshot_root = Path(snapshot_claim).expanduser()
    reviewed_snapshot_root = REVIEWED_SNAPSHOT_ROOT.expanduser()
    if claimed_snapshot_root.is_symlink() or reviewed_snapshot_root.is_symlink():
        raise PointwisePredictionError(
            "The canonical immutable F861 snapshot root must not be a symlink"
        )
    snapshot_root = claimed_snapshot_root.resolve()
    if snapshot_root != reviewed_snapshot_root.resolve() or not snapshot_root.is_dir():
        raise PointwisePredictionError(
            "Analysis provenance is not bound to the canonical immutable F861 snapshot"
        )
    validate_immutable_snapshot_tree(claimed_snapshot_root)

    inputs = _require_mapping(provenance.get("input_files"), "input_files")
    expected_paths = {
        label: (snapshot_root / relative).resolve()
        for label, relative in SNAPSHOT_INPUT_RELATIVE_PATHS.items()
    }
    expected_paths.update(
        {
            "u40_summary": (
                ROOT
                / "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv"
            ).resolve(),
            "u40_rows": (
                ROOT / "results/fullobs_U40_observable_rows_20260723_091307.csv.gz"
            ).resolve(),
            "gz_points": scale_points_path.resolve(),
        }
    )
    if set(inputs) != set(expected_paths):
        raise PointwisePredictionError(
            "Analysis provenance input_files is not the exact immutable-snapshot/U40/GZ inventory"
        )
    for label, expected_path in expected_paths.items():
        record = _require_mapping(inputs.get(label), f"input_files.{label}")
        claimed_path = record.get("path")
        claimed_hash = record.get("sha256")
        if not isinstance(claimed_path, str):
            raise PointwisePredictionError(
                f"Analysis provenance input {label} lacks a path"
            )
        actual_path = Path(claimed_path).expanduser().resolve()
        if actual_path != expected_path or not actual_path.is_file():
            raise PointwisePredictionError(
                f"Analysis provenance input {label} is not the canonical reviewed file"
            )
        if not isinstance(claimed_hash, str) or _sha256(actual_path) != claimed_hash:
            raise PointwisePredictionError(
                f"Analysis provenance input {label} SHA-256 is stale or forged"
            )

    campaign_provenance = _load_json_mapping(
        expected_paths["campaign_provenance"], "expansion campaign provenance"
    )
    campaign_source_revalidation = _require_mapping(
        campaign_provenance.get("source_decision_revalidation"),
        "campaign source_decision_revalidation",
    )
    expansion_decision = _require_mapping(
        provenance.get("expansion_decision"), "expansion_decision"
    )
    if campaign_source_revalidation != {
        "case_count": expansion_decision.get("case_count"),
        "source_decision_inputs_sha256": expansion_decision.get(
            "source_decision_inputs_sha256"
        ),
        "all_decision_driving_target_metrics_match_source_bytes": (
            expansion_decision.get(
                "all_decision_driving_target_metrics_match_source_bytes"
            )
        ),
    }:
        raise PointwisePredictionError(
            "Analysis decision revalidation differs from campaign provenance"
        )

    snapshot_provenance = _load_json_mapping(
        expected_paths["snapshot_provenance"], "immutable snapshot provenance"
    )
    pinned_finalizer = (
        snapshot_root
        / "metadata/local_tools/finalize_fullobs_861expand_fig4_cnn.py"
    )
    if (
        snapshot_provenance.get("finalizer_sha256") != REVIEWED_FINALIZER_SHA256
        or not pinned_finalizer.is_file()
        or _sha256(pinned_finalizer) != REVIEWED_FINALIZER_SHA256
    ):
        raise PointwisePredictionError(
            "Immutable snapshot is not bound to the reviewed full-861 finalizer bytes"
        )

    outputs = _require_mapping(provenance.get("output_files"), "output_files")
    if set(outputs) != set(ANALYZER_OUTPUT_BASENAMES):
        raise PointwisePredictionError(
            "Analysis provenance does not pin the exact five analyzer CSV outputs"
        )
    source_dir = pointwise_path.parent
    for basename in ANALYZER_OUTPUT_BASENAMES:
        path = source_dir / basename
        if not path.is_file() or outputs.get(basename) != _sha256(path):
            raise PointwisePredictionError(
                f"Analyzer output is missing or hash-stale: {basename}"
            )

    staging_parent = ROOT / "tmp"
    staging_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="fig4_cnn_full861_replay_", dir=staging_parent
    ) as temporary:
        replay_dir = Path(temporary) / "analysis"
        command = [
            sys.executable,
            str(analyzer_path),
            "--snapshot-root",
            str(snapshot_root),
            "--u40-summary",
            str(expected_paths["u40_summary"]),
            "--u40-rows",
            str(expected_paths["u40_rows"]),
            "--gz-points",
            str(expected_paths["gz_points"]),
            "--output-dir",
            str(replay_dir),
        ]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip().splitlines()
            tail = detail[-1] if detail else "no diagnostic output"
            raise PointwisePredictionError(
                "Reviewed all-F861 analyzer replay failed against the immutable snapshot: "
                + tail
            )
        for basename in ANALYZER_OUTPUT_BASENAMES:
            replay_path = replay_dir / basename
            if not replay_path.is_file() or _sha256(replay_path) != outputs[basename]:
                raise PointwisePredictionError(
                    f"Publication bundle is not byte-identical to analyzer replay: {basename}"
                )


def validate_analysis_provenance(
    provenance: dict,
    *,
    pointwise_path: Path,
    scale_points_path: Path,
) -> None:
    """Validate the all-F861 analyzer sidecar before publication use."""
    if provenance.get("schema_version") != SCHEMA_VERSION:
        raise PointwisePredictionError(
            f"Analysis provenance schema_version must be {SCHEMA_VERSION}; mixed P25/F861 schema-v1 bundles are not publishable"
        )
    if provenance.get("data_product") != DATA_PRODUCT:
        raise PointwisePredictionError(
            f"Analysis provenance data_product must be {DATA_PRODUCT!r}"
        )
    if provenance.get("C_NN_observable") != C_NN_OBSERVABLE:
        raise PointwisePredictionError(
            f"Analysis provenance C_NN_observable must be {C_NN_OBSERVABLE!r}"
        )
    if provenance.get("C_NN_fidelity") != FULL861_FIDELITY:
        raise PointwisePredictionError("Analysis provenance must certify C_NN_fidelity=F861")
    if provenance.get("analyzer_sha256") != REVIEWED_FULL861_ANALYZER_SHA256:
        raise PointwisePredictionError(
            "Analysis provenance was not emitted by the reviewed all-F861 analyzer"
        )

    reviewed = _require_mapping(provenance.get("reviewed_inputs"), "reviewed_inputs")
    if reviewed != REVIEWED_FULL861_PINS:
        raise PointwisePredictionError(
            "Analysis provenance reviewed_inputs is not the exact all-F861 pin set"
        )

    outputs = _require_mapping(provenance.get("output_files"), "output_files")
    if outputs.get(POINTWISE_BASENAME) != _sha256(pointwise_path):
        raise PointwisePredictionError(
            "Pointwise CSV SHA-256 does not match analysis provenance"
        )

    inputs = _require_mapping(provenance.get("input_files"), "input_files")
    for label, pin_key in (
        ("expansion_manifest", "expansion_manifest_sha256"),
        ("source_25_manifest", "source_25_manifest_sha256"),
        ("decision_verifier", "expansion_generator_sha256"),
        ("u40_summary", "u40_summary_sha256"),
        ("u40_rows", "u40_rows_sha256"),
        ("gz_points", "gz_points_sha256"),
    ):
        record = _require_mapping(inputs.get(label), f"input_files.{label}")
        if record.get("sha256") != REVIEWED_FULL861_PINS[pin_key]:
            raise PointwisePredictionError(
                f"Analysis provenance input {label} is not hash-pinned to the reviewed file"
            )
    decision_certificate = _require_mapping(
        inputs.get("decision_certificate"), "input_files.decision_certificate"
    )
    decision_certificate_sha256 = provenance.get("decision_certificate_sha256")
    if (
        not isinstance(decision_certificate_sha256, str)
        or len(decision_certificate_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in decision_certificate_sha256
        )
        or decision_certificate.get("sha256") != decision_certificate_sha256
        or provenance.get("decision_gate_algorithm") != DECISION_GATE_ALGORITHM
    ):
        raise PointwisePredictionError(
            "Analysis provenance is not bound to the approved v2 expansion decision certificate"
        )
    expansion_decision = _require_mapping(
        provenance.get("expansion_decision"), "expansion_decision"
    )
    expected_expansion_decision_keys = {
        "decision",
        "approved",
        "gate_algorithm",
        "decision_certificate_sha256",
        "decision_verifier_sha256",
        "case_count",
        "source_decision_inputs_sha256",
        "all_decision_driving_target_metrics_match_source_bytes",
    }
    source_decision_inputs_sha256 = expansion_decision.get(
        "source_decision_inputs_sha256"
    )
    if (
        set(expansion_decision) != expected_expansion_decision_keys
        or expansion_decision.get("decision") != "APPROVE_EXPANSION"
        or expansion_decision.get("approved") is not True
        or expansion_decision.get("gate_algorithm") != DECISION_GATE_ALGORITHM
        or expansion_decision.get("decision_certificate_sha256")
        != decision_certificate_sha256
        or expansion_decision.get("decision_verifier_sha256")
        != REVIEWED_FULL861_PINS["expansion_generator_sha256"]
        or expansion_decision.get("case_count") != 12
        or not isinstance(source_decision_inputs_sha256, str)
        or len(source_decision_inputs_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in source_decision_inputs_sha256
        )
        or expansion_decision.get(
            "all_decision_driving_target_metrics_match_source_bytes"
        )
        is not True
    ):
        raise PointwisePredictionError(
            "Analysis provenance does not certify the exact approved expansion decision"
        )
    actual_gz_hash = _sha256(scale_points_path)
    if actual_gz_hash != REVIEWED_FULL861_PINS["gz_points_sha256"]:
        raise PointwisePredictionError(
            "Current GZ scale table is not the reviewed all-F861 analysis input"
        )

    pins = _require_mapping(
        provenance.get("campaign_pinned_solver"), "campaign_pinned_solver"
    )
    for key in ("solver_sha256", "source_sha256", "qbasis_library_sha256"):
        if pins.get(key) != REVIEWED_FULL861_PINS[key]:
            raise PointwisePredictionError(f"Analysis provenance has an unreviewed {key}")

    raw = _require_mapping(
        provenance.get("raw_output_inventory"), "raw_output_inventory"
    )
    if (
        raw.get("count") != 10_332
        or raw.get("expansion_count") != 10_032
        or raw.get("reused_25_count") != 300
        or raw.get("all_status_complete") is not True
        or raw.get("all_sha256_match") is not True
    ):
        raise PointwisePredictionError(
            "Analysis provenance does not certify the exact 10,332-row F861 raw inventory"
        )
    try:
        residual = float(raw["max_abs_identity_residual"])
        tolerance = float(raw["identity_tolerance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PointwisePredictionError(
            "Analysis provenance lacks numeric observable-identity bounds"
        ) from exc
    if not (
        np.isfinite(residual)
        and np.isfinite(tolerance)
        and residual >= 0.0
        and tolerance == MAX_REVIEWED_IDENTITY_TOLERANCE
        and residual <= tolerance
    ):
        raise PointwisePredictionError(
            "Analysis provenance must use and pass the exact reviewed 1e-8 observable-identity tolerance"
        )

    snapshot = _require_mapping(provenance.get("snapshot"), "snapshot")
    if (
        snapshot.get("immutable_add_only") is not True
        or snapshot.get("combined_targets") != 10_332
        or snapshot.get("full_wedges_verified") is not True
        or snapshot.get("remote_local_analysis_agreement") is not True
    ):
        raise PointwisePredictionError(
            "Analysis provenance does not certify the immutable validated F861 snapshot"
        )

    aggregation = _require_mapping(provenance.get("aggregation"), "aggregation")
    if (
        aggregation.get("campaign_case_count") != 12
        or aggregation.get("full_wedge_coordinates_per_case") != 861
        or aggregation.get("quadrature_weight_per_case") != 1600.0
        or aggregation.get("pointwise_full861_count") != 16
        or aggregation.get("twist_spread_is_standard_error") is not False
        or aggregation.get("C_NN_estimator")
        != "861-point wedge with exchange and trapezoidal endpoint weights (weight 1600)"
    ):
        raise PointwisePredictionError(
            "Analysis provenance has an invalid all-F861 aggregation contract"
        )

    controls = _require_mapping(provenance.get("u40_controls"), "u40_controls")
    try:
        control_residual = float(controls["max_abs_identity_residual"])
        control_tolerance = float(controls["identity_tolerance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PointwisePredictionError(
            "Analysis provenance lacks numeric U=40 F861 identity bounds"
        ) from exc
    if (
        controls.get("count") != 4
        or controls.get("raw_wedge_rows") != 3_444
        or controls.get("coordinates_per_case") != 861
        or controls.get("quadrature_weight_per_case") != 1600.0
        or controls.get("all_status_complete") is not True
        or controls.get("summary_sha256")
        != REVIEWED_FULL861_PINS["u40_summary_sha256"]
        or controls.get("rows_sha256") != REVIEWED_FULL861_PINS["u40_rows_sha256"]
        or not (
            np.isfinite(control_residual)
            and np.isfinite(control_tolerance)
            and control_residual >= 0.0
            and control_tolerance == MAX_REVIEWED_IDENTITY_TOLERANCE
            and control_residual <= control_tolerance
        )
    ):
        raise PointwisePredictionError(
            "Analysis provenance does not certify four complete hash-pinned U=40 F861 controls"
        )

    pointwise = _require_mapping(provenance.get("pointwise"), "pointwise")
    if (
        pointwise.get("count") != 16
        or pointwise.get("expansion_full861_C_NN_points") != 12
        or pointwise.get("existing_u40_full861_C_NN_points") != 4
        or pointwise.get("full861_C_NN_points") != 16
        or pointwise.get("all_rows_labeled_F861") is not True
        or pointwise.get("all_C_NN_inputs_independent_of_GZ_slope") is not True
    ):
        raise PointwisePredictionError(
            "Analysis provenance does not certify 16 independent all-F861 C_NN inputs"
        )

    equations = _require_mapping(provenance.get("equations"), "equations")
    if equations.get("signed_convention") != "omega_GZ(k)=s_NN epsilon_NN(k)":
        raise PointwisePredictionError(
            "Analysis provenance does not certify the signed s_NN convention"
        )
    if equations.get("eq10") != "s_NN=1+[(2U-V)/(U-V)](2C_NN-1/2)":
        raise PointwisePredictionError(
            "Analysis provenance Eq. (10) declaration is missing or changed"
        )
    if provenance.get("publication_artifacts_modified") is not False:
        raise PointwisePredictionError(
            "Analysis provenance must certify no publication artifact modification"
        )
    _bind_and_replay_reviewed_analyzer(
        provenance,
        pointwise_path=pointwise_path,
        scale_points_path=scale_points_path,
    )


def load_validated_fullobs_eq10_bundle(
    analysis_dir: Path,
    *,
    allow_fixture: bool = False,
    scale_points_path: Path | None = None,
) -> FullobsEq10Bundle:
    """Load the inseparable all-F861 CSV/provenance bundle."""
    source_dir = Path(analysis_dir).expanduser().resolve()
    if not source_dir.is_dir():
        raise PointwisePredictionError(
            f"Pointwise fullobs analysis directory not found: {source_dir}"
        )
    source = source_dir / POINTWISE_BASENAME
    provenance_path = source_dir / PROVENANCE_BASENAME
    if not source.is_file():
        raise PointwisePredictionError(f"Pointwise C_NN table not found: {source}")
    if not provenance_path.is_file():
        raise PointwisePredictionError(
            f"Analysis provenance not found: {provenance_path}"
        )
    try:
        table = pd.read_csv(source)
    except Exception as exc:
        raise PointwisePredictionError(
            f"Could not read pointwise C_NN table: {source}"
        ) from exc
    validated = validate_pointwise_eq10_predictions(table, allow_fixture=allow_fixture)
    try:
        provenance = _require_mapping(json.loads(provenance_path.read_text()), "root")
    except (OSError, json.JSONDecodeError) as exc:
        raise PointwisePredictionError(
            f"Could not parse analysis provenance: {provenance_path}"
        ) from exc

    fixture = (
        "fixture_only" in validated.columns
        and _strict_bool(validated["fixture_only"], "fixture_only").all()
    )
    if fixture:
        outputs = _require_mapping(provenance.get("output_files"), "output_files")
        labels = set(validated["fixture_label"].astype(str))
        if (
            provenance.get("fixture_only") is not True
            or provenance.get("data_product") != FIXTURE_DATA_PRODUCT
            or provenance.get("fixture_label") not in labels
            or outputs.get(POINTWISE_BASENAME) != _sha256(source)
            or provenance.get("publication_artifacts_modified") is not False
        ):
            raise PointwisePredictionError(
                "Synthetic fixture provenance is missing, inconsistent, or hash-stale"
            )
        return FullobsEq10Bundle(validated, provenance, source_dir)

    if scale_points_path is None:
        raise PointwisePredictionError(
            "Production pointwise validation requires the current scale_points_path"
        )
    scale_path = Path(scale_points_path).expanduser().resolve()
    if not scale_path.is_file():
        raise PointwisePredictionError(
            f"Current GZ scale table not found: {scale_path}"
        )
    validate_analysis_provenance(
        provenance,
        pointwise_path=source,
        scale_points_path=scale_path,
    )
    return FullobsEq10Bundle(validated, provenance, source_dir)


def load_pointwise_eq10_predictions(
    path: Path,
    *,
    allow_fixture: bool = False,
    scale_points_path: Path | None = None,
) -> pd.DataFrame:
    """Compatibility wrapper that still enforces the complete sibling bundle."""
    source = Path(path).expanduser().resolve()
    if source.name != POINTWISE_BASENAME:
        raise PointwisePredictionError(
            f"Pointwise table must use the analyzer basename {POINTWISE_BASENAME}"
        )
    return load_validated_fullobs_eq10_bundle(
        source.parent,
        allow_fixture=allow_fixture,
        scale_points_path=scale_points_path,
    ).rows
