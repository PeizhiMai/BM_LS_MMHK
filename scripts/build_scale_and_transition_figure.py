#!/usr/bin/env python3
"""Combine the analytic finite-(U,V) scale laws with the Mott--CDW boundary.

Panel (a) compares the measured signed GZ coefficients with the leading
strong-coupling Mott and CDW laws.  Before pointwise promotion, the default
Mott curves retain the published axis-anchor construction.  A strictly gated
staging mode can instead draw the sixteen pointwise Eq. (10) predictions made
from independent fullobs C_NN inputs.  A successful production promotion
writes an active-bundle pointer, after which default rebuilds are fail-closed
to that validated pointwise bundle rather than reverting to the anchor.
Panel (b) plots the independently measured critical ratio (V/U)_c versus U/t,
retaining only U/t >= 4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

import fcntl
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter

from fig4_cnn_prediction_input import (
    DATA_PRODUCT as FULL861_DATA_PRODUCT,
    FULL861_FIDELITY,
    PROVENANCE_BASENAME,
    REVIEWED_FULL861_PINS,
    SCHEMA_VERSION as FULL861_SCHEMA_VERSION,
    load_validated_fullobs_eq10_bundle,
)
from freeze_fig4_cnn_full861_release import (
    RELEASE_MANIFEST_BASENAME,
    validate_frozen_full861_release,
)
from manuscript_figure_style import outside_panel_label


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "figures" / "pnas_main"

SCALE_POINTS = RESULTS / "pnas_scale_rule_points_eta0p05.csv"
BOUNDARY_SOURCE = RESULTS / "transition_brackets_combined_U2_U40.csv"
BOUNDARY_FILTERED = RESULTS / "transition_brackets_Uge4_for_combined_figure.csv"
ANALYTIC_POINTS = RESULTS / "finite_uv_strong_coupling_validation_eta0p05.csv"
ANALYTIC_SUMMARY = RESULTS / "finite_uv_strong_coupling_validation_eta0p05.json"

OUT_PDF = OUT / "pnas_fig3_scale_and_transition_boundary.pdf"
OUT_PNG = OUT / "pnas_fig3_scale_and_transition_boundary.png"
PRL_VERTICAL_OUT_PDF = (
    ROOT / "figures" / "prl_main" / "fig4_scale_and_transition_boundary.pdf"
)
PRL_VERTICAL_OUT_PNG = (
    ROOT / "figures" / "prl_main" / "fig4_scale_and_transition_boundary.png"
)
# The scale/boundary panel is Fig. 5 in the current six-figure manuscript.
# Keep the historical constant name because the frozen Fig. 4 campaign tools
# import and patch it as part of their staging contract.
MANUSCRIPT_FIG4_OUT_PDF = (
    ROOT / "manuscript" / "figures" / "fig5_scale_and_transition_boundary.pdf"
)
STAGING_ROOT = ROOT / "tmp"
ACTIVE_BUNDLE_POINTER = RESULTS / "fig4_cnn_active_bundle.json"
LEGACY_ANALYTIC_ARCHIVE_DIR = (
    RESULTS / "archive" / "fig4_axis_anchor_validation_pre_pointwise_20260821"
)
REVIEWED_LEGACY_ANALYTIC_SHA256 = {
    "analytic_csv": "dd3ad76001021a300a54b03b25505b8d7d1b3be6315734d3c697d462ee039cd0",
    "analytic_json": "8cf1bc6564b17ae09e52c54b98361e9e69c01b05a7f31284b79bcb6b0b669fdb",
}

COLORS = {20.0: "#e68613", 40.0: "#c63b32", 80.0: "#7556a5"}
MARKERS = {20.0: "s", 40.0: "^", 80.0: "D"}
S_U_RESOLUTION = -1.4035604012
S_V = -8.0 / 7.0
R_BOUNDARY = 0.25

STYLE = {
    "font.family": "Arial",
    "font.size": 11,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10.5,
    "axes.linewidth": 1.1,
    "lines.linewidth": 2.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def _transactional_promote(
    promotion_pairs: list[tuple[Path, Path]],
) -> None:
    """Promote a complete artifact set, restoring every old byte on failure.

    A rename is atomic only for one file.  Fig. 4 promotion replaces nine
    coupled files, so copying and replacing them one at a time without a
    rollback can expose a mixed old/new release.  This routine first prepares
    every candidate and byte-for-byte backup adjacent to its destination.  It
    then commits the set; if any commit raises, every already replaced path is
    restored (or removed when it did not exist before the transaction).
    """
    pairs = [
        (Path(staged), Path(destination)) for staged, destination in promotion_pairs
    ]
    if not pairs:
        raise RuntimeError("Transactional promotion requires at least one artifact")
    destinations = [destination.resolve() for _, destination in pairs]
    if len(set(destinations)) != len(destinations):
        raise RuntimeError("Transactional promotion destinations must be distinct")
    for staged, _ in pairs:
        if not staged.is_file() or staged.stat().st_size <= 0:
            raise RuntimeError(
                f"Staged promotion artifact is missing or empty: {staged}"
            )

    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    records: list[dict[str, object]] = []
    preserve_backups = False
    try:
        # Preflight/copy the whole set before replacing any destination.
        for staged, destination in pairs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not destination.is_file():
                raise RuntimeError(
                    f"Promotion destination exists but is not a file: {destination}"
                )
            candidate = destination.with_name(
                f".{destination.name}.fullobs-candidate-{token}.tmp"
            )
            backup = destination.with_name(
                f".{destination.name}.fullobs-backup-{token}.tmp"
            )
            existed = destination.is_file()
            record: dict[str, object] = {
                "destination": destination,
                "candidate": candidate,
                "backup": backup,
                "existed": existed,
            }
            records.append(record)
            shutil.copy2(staged, candidate)
            if existed:
                shutil.copy2(destination, backup)

        try:
            for record in records:
                os.replace(
                    Path(record["candidate"]),
                    Path(record["destination"]),
                )
        except BaseException as commit_error:
            rollback_errors: list[str] = []
            # Restore the complete recorded prestate, not only entries marked
            # committed.  This closes the interruption window after a
            # successful os.replace but before Python executes the next line.
            for record in reversed(records):
                destination = Path(record["destination"])
                backup = Path(record["backup"])
                try:
                    if record["existed"]:
                        if not backup.is_file():
                            raise RuntimeError(f"backup vanished: {backup}")
                        os.replace(backup, destination)
                    elif destination.exists():
                        destination.unlink()
                except (
                    BaseException
                ) as rollback_error:  # pragma: no cover - catastrophic I/O
                    rollback_errors.append(
                        f"{destination}: {type(rollback_error).__name__}: {rollback_error}"
                    )
            if rollback_errors:
                preserve_backups = True
                raise RuntimeError(
                    "Fig. 4 artifact-set commit failed and rollback was incomplete; "
                    "adjacent fullobs-backup files were retained for manual recovery: "
                    + "; ".join(rollback_errors)
                ) from commit_error
            raise RuntimeError(
                "Fig. 4 artifact-set commit failed; all active destinations were restored"
            ) from commit_error
    finally:
        for record in records:
            candidate = Path(record["candidate"])
            backup = Path(record["backup"])
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass
            if backup.exists() and not preserve_backups:
                try:
                    backup.unlink()
                except OSError:
                    pass


@contextmanager
def _promotion_lock(pointer_path: Path):
    """Serialize archive preparation and coupled active-set commits."""
    lock_path = pointer_path.with_name(".fig4_fullobs_promotion.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_active_bundle_pointer(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not read active Fig. 4 bundle pointer: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Active Fig. 4 bundle pointer must be a JSON object")
    required = {
        "schema_version",
        "data_product",
        "analysis_dir",
        "pointwise_csv_sha256",
        "analysis_provenance_sha256",
        "analysis_release_manifest_sha256",
        "analysis_bundle_sha256",
        "decision_certificate_sha256",
        "decision_gate_algorithm",
        "C_NN_fidelity",
        "reviewed_inputs",
        "legacy_analytic_archive",
        "release_artifacts_sha256",
    }
    if set(payload) != required:
        raise RuntimeError(
            "Active Fig. 4 bundle pointer has the wrong exact schema: "
            f"missing={sorted(required - set(payload))}, "
            f"unexpected={sorted(set(payload) - required)}"
        )
    if payload["schema_version"] != FULL861_SCHEMA_VERSION:
        raise RuntimeError("Unsupported active Fig. 4 bundle-pointer schema")
    if payload["data_product"] != FULL861_DATA_PRODUCT:
        raise RuntimeError("Active Fig. 4 bundle pointer has the wrong data product")
    if payload["C_NN_fidelity"] != FULL861_FIDELITY:
        raise RuntimeError("Active Fig. 4 pointer is not an all-F861 release")
    if payload["reviewed_inputs"] != REVIEWED_FULL861_PINS:
        raise RuntimeError("Active Fig. 4 pointer has the wrong reviewed F861 pins")
    if payload["legacy_analytic_archive"] != str(LEGACY_ANALYTIC_ARCHIVE_DIR.resolve()):
        raise RuntimeError("Active Fig. 4 pointer names the wrong legacy archive")

    analysis_dir = Path(str(payload["analysis_dir"])).expanduser().resolve()
    try:
        release_manifest = validate_frozen_full861_release(
            analysis_dir,
            results_root=RESULTS,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            "Active Fig. 4 pointer does not name a valid frozen all-F861 release"
        ) from exc
    release_manifest_path = analysis_dir / RELEASE_MANIFEST_BASENAME
    if (
        payload["analysis_dir"] != str(analysis_dir)
        or payload["analysis_release_manifest_sha256"]
        != _sha256(release_manifest_path)
        or payload["analysis_bundle_sha256"]
        != release_manifest["analysis_bundle_sha256"]
        or payload["pointwise_csv_sha256"]
        != release_manifest["pointwise_csv_sha256"]
        or payload["analysis_provenance_sha256"]
        != release_manifest["analysis_provenance_sha256"]
        or payload["decision_certificate_sha256"]
        != release_manifest["decision_certificate_sha256"]
        or payload["decision_gate_algorithm"]
        != release_manifest["decision_gate_algorithm"]
    ):
        raise RuntimeError(
            "Active Fig. 4 pointer is stale against its frozen release manifest"
        )

    artifact_paths = {
        "pnas_pdf": OUT_PDF,
        "pnas_png": OUT_PNG,
        "prl_pdf": PRL_VERTICAL_OUT_PDF,
        "prl_png": PRL_VERTICAL_OUT_PNG,
        "manuscript_pdf": MANUSCRIPT_FIG4_OUT_PDF,
        "analytic_csv": ANALYTIC_POINTS,
        "analytic_json": ANALYTIC_SUMMARY,
        "boundary_csv": BOUNDARY_FILTERED,
    }
    release_hashes = payload["release_artifacts_sha256"]
    if not isinstance(release_hashes, dict) or set(release_hashes) != set(
        artifact_paths
    ):
        raise RuntimeError("Active Fig. 4 pointer has an incomplete artifact hash set")
    for role, artifact in artifact_paths.items():
        if not artifact.is_file() or release_hashes[role] != _sha256(artifact):
            raise RuntimeError(
                f"Active Fig. 4 artifact is missing or hash-stale: {role}"
            )
    if release_hashes["manuscript_pdf"] != release_hashes["prl_pdf"]:
        raise RuntimeError(
            "Active manuscript Fig. 4 is not byte-identical to the PRL vertical PDF"
        )

    provenance_path = analysis_dir / PROVENANCE_BASENAME
    if not provenance_path.is_file() or payload[
        "analysis_provenance_sha256"
    ] != _sha256(provenance_path):
        raise RuntimeError("Active Fig. 4 analysis provenance is missing or hash-stale")
    return payload


def _read_pointer_state(path: Path) -> dict[str, object] | None:
    """Return an absent/valid pointer state and reject every ambiguous state."""
    if not os.path.lexists(path):
        return None
    if not path.is_file():
        raise RuntimeError(
            f"Active Fig. 4 bundle pointer exists but is not a regular file: {path}"
        )
    return _load_active_bundle_pointer(path)


def _validate_reviewed_legacy_archive(
    *,
    archive_dir: Path,
    analytic_csv: Path,
    analytic_json: Path,
    expected_sha256: dict[str, str],
) -> None:
    """Verify the installed immutable archive without consulting active tables."""
    manifest_name = "archive_manifest.json"
    if not archive_dir.is_dir():
        raise RuntimeError(f"Reviewed legacy archive is missing: {archive_dir}")
    sources = {
        "analytic_csv": analytic_csv,
        "analytic_json": analytic_json,
    }
    expected_names = {source.name for source in sources.values()} | {manifest_name}
    actual_names = {path.name for path in archive_dir.iterdir()}
    if actual_names != expected_names:
        raise RuntimeError(
            "Reviewed legacy archive is incomplete or has unexpected files: "
            f"expected={sorted(expected_names)}, found={sorted(actual_names)}"
        )
    try:
        manifest = json.loads((archive_dir / manifest_name).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Reviewed legacy archive manifest is unreadable") from exc
    if manifest.get("purpose") != (
        "pre-pointwise archive of legacy V=0-axis-anchor validation"
    ):
        raise RuntimeError("Reviewed legacy archive has the wrong purpose")
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise RuntimeError("Reviewed legacy archive manifest lacks file records")
    for role, source in sources.items():
        archived = archive_dir / source.name
        expected_hash = expected_sha256[role]
        record = records.get(source.name)
        if (
            not isinstance(record, dict)
            or record.get("sha256") != expected_hash
            or record.get("source") != str(source.resolve())
            or _sha256(archived) != expected_hash
        ):
            raise RuntimeError(
                f"Reviewed legacy archive identity mismatch for {source.name}"
            )


def _archive_legacy_analytic_outputs(
    *,
    analytic_csv: Path,
    analytic_json: Path,
    archive_dir: Path,
    expected_sha256: dict[str, str] | None = None,
) -> bool:
    """Install or validate one complete immutable legacy archive directory."""
    sources = (analytic_csv, analytic_json)
    if not all(path.is_file() for path in sources):
        raise RuntimeError(
            "Cannot promote pointwise Fig. 4 without both legacy analytic outputs to archive"
        )
    if expected_sha256 is not None:
        actual = {
            "analytic_csv": _sha256(analytic_csv),
            "analytic_json": _sha256(analytic_json),
        }
        if actual != expected_sha256:
            raise RuntimeError(
                "Refusing to archive unreviewed legacy analytic outputs: "
                f"expected={expected_sha256}, found={actual}"
            )
    manifest: dict[str, object] = {
        "purpose": "pre-pointwise archive of legacy V=0-axis-anchor validation",
        "files": {},
    }
    file_records = manifest["files"]
    assert isinstance(file_records, dict)
    for source in sources:
        file_records[source.name] = {
            "sha256": _sha256(source),
            "source": str(source.resolve()),
        }

    manifest_name = "archive_manifest.json"
    if os.path.lexists(archive_dir):
        if not archive_dir.is_dir():
            raise RuntimeError(f"Legacy archive path is not a directory: {archive_dir}")
        expected_names = {source.name for source in sources} | {manifest_name}
        actual_names = {path.name for path in archive_dir.iterdir()}
        if actual_names != expected_names:
            raise RuntimeError(
                "Existing legacy archive is incomplete or has unexpected files: "
                f"expected={sorted(expected_names)}, found={sorted(actual_names)}"
            )
        try:
            archived_manifest = json.loads((archive_dir / manifest_name).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Existing legacy archive manifest is unreadable"
            ) from exc
        if archived_manifest != manifest:
            raise RuntimeError(
                "Existing legacy archive manifest disagrees with active sources"
            )
        for source in sources:
            archived = archive_dir / source.name
            if archived.read_bytes() != source.read_bytes():
                raise RuntimeError(
                    f"Existing legacy archive disagrees with active source: {archived}"
                )
        return False

    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    staged_archive = Path(
        tempfile.mkdtemp(
            prefix=f".{archive_dir.name}.staging-",
            dir=archive_dir.parent,
        )
    )
    try:
        for source in sources:
            shutil.copy2(source, staged_archive / source.name)
        (staged_archive / manifest_name).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        expected_names = {source.name for source in sources} | {manifest_name}
        if {path.name for path in staged_archive.iterdir()} != expected_names:
            raise RuntimeError(
                "Legacy archive staging did not create the complete file set"
            )
        for source in sources:
            archived = staged_archive / source.name
            if _sha256(archived) != file_records[source.name]["sha256"]:
                raise RuntimeError(
                    f"Legacy archive staging hash mismatch for {source.name}"
                )
        # The manifest exists inside the staged directory before the directory
        # becomes visible at its final name, so a failed copy cannot leave a
        # manifest-less partial archive at ``archive_dir``.
        os.rename(staged_archive, archive_dir)
        return True
    finally:
        if staged_archive.exists():
            shutil.rmtree(staged_archive, ignore_errors=True)


def panel_label(
    ax: plt.Axes,
    label: str,
    x: float,
    *,
    fontsize: float = 12.5,
) -> None:
    """Place a panel label just left of the topmost y tick."""
    outside_panel_label(ax, label, x=x, fontsize=fontsize)


def mott_scale_law_from_axis_anchor(
    r: np.ndarray | float,
    s0_signed: np.ndarray | float,
) -> np.ndarray:
    """Leading Mott law with C_NN replaced by s(U,0)/4 at the same order."""
    r_array = np.asarray(r, dtype=float)
    s0_array = np.asarray(s0_signed, dtype=float)
    return (s0_array - 0.5 * (s0_array + 1.0) * r_array) / (1.0 - r_array)


def cdw_scale_law(r: np.ndarray | float) -> np.ndarray:
    """Parameter-free checkerboard law -(8V-U)/(7V-U), with r=V/U."""
    r_array = np.asarray(r, dtype=float)
    return -(8.0 * r_array - 1.0) / (7.0 * r_array - 1.0)


def load_scale_data() -> pd.DataFrame:
    points = pd.read_csv(SCALE_POINTS)
    expected_u = {20.0, 40.0, 80.0}
    if set(points["U"].astype(float)) != expected_u:
        raise RuntimeError(
            f"Expected scale families {sorted(expected_u)}, "
            f"found {sorted(set(points['U'].astype(float)))}"
        )
    return points


def assemble_analytic_validation(
    points: pd.DataFrame,
    *,
    cnn_predictions: pd.DataFrame | None = None,
    cnn_provenance: dict[str, object] | None = None,
    cnn_source_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Assemble analytic rows/summary without touching the filesystem."""
    validation = points.drop(
        columns=["s_selected_fit", "fit_residual"], errors="ignore"
    ).copy()
    validation["s_signed_observed"] = -validation["s"].astype(float)
    validation["s_strong_coupling"] = np.nan
    cnn_is_fixture = False

    mott = validation["branch"].eq("Mott/spin")
    if cnn_predictions is None:
        validation.loc[mott, "s_strong_coupling"] = mott_scale_law_from_axis_anchor(
            validation.loc[mott, "r"].to_numpy(dtype=float),
            -validation.loc[mott, "s_u0"].to_numpy(dtype=float),
        )
    else:
        cnn_is_fixture = bool(
            "fixture_only" in cnn_predictions.columns
            and cnn_predictions["fixture_only"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("true")
            .all()
        )
        prediction_values = cnn_predictions.set_index(["U", "V"])
        pointwise_keys = pd.MultiIndex.from_frame(validation[["U", "V"]])
        aligned_predictions = prediction_values.reindex(pointwise_keys)
        copied_columns = {
            "C_NN": "C_NN_pointwise",
            "eq10_factor": "eq10_factor_pointwise",
            "s_eq10_signed": "s_pointwise_eq10_signed",
            "C_NN_source": "C_NN_source",
            "C_NN_sampling": "C_NN_sampling",
            "C_NN_fidelity": "C_NN_fidelity",
            "C_NN_full_wedge_rows": "C_NN_full_wedge_rows",
            "C_NN_quadrature_weight": "C_NN_quadrature_weight",
            "C_NN_full_quadrature_weighted_population_std": (
                "C_NN_full_quadrature_weighted_population_std"
            ),
            "twist_spread_is_standard_error": ("twist_spread_is_standard_error"),
            "eq10_convention": "eq10_convention",
        }
        for input_column, output_column in copied_columns.items():
            validation[output_column] = aligned_predictions[input_column].to_numpy()
        for fixture_column in ("fixture_only", "fixture_label"):
            if fixture_column in aligned_predictions.columns:
                validation[fixture_column] = aligned_predictions[
                    fixture_column
                ].to_numpy()
        expected_pointwise = validation["branch"].isin(["U-only", "Mott/spin"])
        if validation.loc[expected_pointwise, "s_pointwise_eq10_signed"].isna().any():
            raise RuntimeError(
                "Validated C_NN bundle does not cover every plotted Mott-side point"
            )
        validation.loc[expected_pointwise, "s_strong_coupling"] = validation.loc[
            expected_pointwise, "s_pointwise_eq10_signed"
        ]
        validation["diagnostic_s_axis_anchor_signed"] = np.nan
        validation.loc[expected_pointwise, "diagnostic_s_axis_anchor_signed"] = (
            mott_scale_law_from_axis_anchor(
                validation.loc[expected_pointwise, "r"].to_numpy(dtype=float),
                -validation.loc[expected_pointwise, "s_u0"].to_numpy(dtype=float),
            )
        )
        validation["diagnostic_axis_anchor_residual_observed_minus_prediction"] = (
            validation["s_signed_observed"]
            - validation["diagnostic_s_axis_anchor_signed"]
        )
    charge = validation["branch"].eq("charge")
    validation.loc[charge, "s_strong_coupling"] = cdw_scale_law(
        validation.loc[charge, "r"].to_numpy(dtype=float)
    )
    validation["strong_coupling_residual"] = (
        validation["s_signed_observed"] - validation["s_strong_coupling"]
    )
    if cnn_predictions is not None:
        validation["strong_coupling_model"] = np.select(
            [expected_pointwise, charge],
            [
                (
                    "Mott Eq. (10), synthetic C_NN fixture"
                    if cnn_is_fixture
                    else "Mott Eq. (10), pointwise fullobs F861 C_NN"
                ),
                "CDW Eq. (11), checkerboard law",
            ],
            default="not evaluated",
        )

    summary: dict[str, object] = {
        "convention": "omega_GZ(k)=s_NN epsilon_NN(k), signed s_NN",
        "mott_rule": (
            "s_M=1+[(2U-V)/(U-V)](2C_NN-1/2); plotted curves use "
            + (
                "s0=s_NN(U,0)=4C_NN at leading order"
                if cnn_predictions is None
                else (
                    "sixteen synthetic fixture C_NN inputs (not production)"
                    if cnn_is_fixture
                    else "sixteen independent fullobs F861 C_NN inputs"
                )
            )
        ),
        "cdw_rule": "s_C=-(8V-U)/(7V-U)",
        "finite_V_fit_parameters": 0,
        "validation_exclusions": (
            ["U-only anchors", "boundary points"]
            if cnn_predictions is None
            else ["V=0 points", "boundary points"]
        ),
        "families": [],
    }
    if cnn_predictions is not None:
        summary["mott_curve_source"] = (
            "synthetic pointwise C_NN fixture; not production"
            if cnn_is_fixture
            else "pointwise independent fullobs F861 C_NN"
        )
        summary["mott_metrics_scope"] = "finite-V Mott/spin rows; V=0 excluded"
        summary["axis_anchor_role"] = "diagnostic comparison only; not plotted"
        if cnn_provenance is None or cnn_source_dir is None:
            raise RuntimeError(
                "Pointwise analytic output requires validated bundle provenance"
            )
        output_files = cnn_provenance.get("output_files")
        if not isinstance(output_files, dict):
            raise RuntimeError("Validated bundle provenance lacks output_files")
        summary["pointwise_bundle"] = {
            "source_dir": str(Path(cnn_source_dir).resolve()),
            "schema_version": cnn_provenance.get("schema_version"),
            "data_product": cnn_provenance.get("data_product"),
            "C_NN_observable": cnn_provenance.get("C_NN_observable"),
            "C_NN_fidelity": cnn_provenance.get("C_NN_fidelity"),
            "reviewed_inputs": cnn_provenance.get("reviewed_inputs"),
            "pointwise_csv_sha256": output_files.get("fig4_cnn_pointwise_eq10.csv"),
            "fixture_only": cnn_is_fixture,
            "fixture_label": cnn_provenance.get("fixture_label"),
        }
    families: list[dict[str, object]] = []
    for branch in ("Mott/spin", "charge"):
        branch_rows = validation[validation["branch"].eq(branch)]
        for U, group in branch_rows.groupby("U", sort=True):
            residual = group["strong_coupling_residual"].to_numpy(dtype=float)
            families.append(
                {
                    "branch": branch,
                    "U": float(U),
                    "point_count": int(len(group)),
                    "rmse": float(np.sqrt(np.mean(residual**2))),
                    "mae": float(np.mean(np.abs(residual))),
                    "max_abs_residual": float(np.max(np.abs(residual))),
                }
            )
        residual = branch_rows["strong_coupling_residual"].to_numpy(dtype=float)
        summary[f"{branch}_all_points_rmse"] = float(np.sqrt(np.mean(residual**2)))
        complete = branch_rows[branch_rows["missing_raw_rows"].eq(0)]
        complete_residual = complete["strong_coupling_residual"].to_numpy(dtype=float)
        summary[f"{branch}_complete_paths_rmse"] = float(
            np.sqrt(np.mean(complete_residual**2))
        )
    summary["families"] = families
    return validation, summary


def write_analytic_validation(
    points: pd.DataFrame,
    *,
    cnn_predictions: pd.DataFrame | None = None,
    cnn_provenance: dict[str, object] | None = None,
    cnn_source_dir: Path | None = None,
    analytic_points_path: Path = ANALYTIC_POINTS,
    analytic_summary_path: Path = ANALYTIC_SUMMARY,
) -> dict[str, object]:
    """Write analytic outputs only after their complete in-memory assembly."""
    validation, summary = assemble_analytic_validation(
        points,
        cnn_predictions=cnn_predictions,
        cnn_provenance=cnn_provenance,
        cnn_source_dir=cnn_source_dir,
    )
    validation.to_csv(analytic_points_path, index=False)
    analytic_summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def load_boundary_data(
    *,
    write_filtered: bool = True,
    filtered_path: Path = BOUNDARY_FILTERED,
) -> pd.DataFrame:
    source = pd.read_csv(BOUNDARY_SOURCE)
    boundary = source[source["U"].astype(float) >= 4.0].copy()
    boundary = boundary.sort_values("U").reset_index(drop=True)
    expected_u = {4, 8, 12, 16, 20, 24, 28, 32, 36, 40}
    if set(boundary["U"].astype(int)) != expected_u:
        raise RuntimeError(
            f"Expected U>=4 boundary grid {sorted(expected_u)}, "
            f"found {sorted(set(boundary['U'].astype(int)))}"
        )
    if not np.all(boundary["V_c_over_U_halfwidth"].to_numpy() > 0):
        raise RuntimeError("Every transition point must carry a finite bracket")
    if write_filtered:
        boundary.to_csv(filtered_path, index=False)
    return boundary


def draw_scale_panel(
    ax: plt.Axes,
    points: pd.DataFrame,
    *,
    cnn_predictions: pd.DataFrame | None = None,
    panel_label_fontsize: float = 12.5,
    panel_label_x: float = -0.115,
) -> None:
    """Draw data and the leading analytic laws on an existing axis."""
    ax.axvspan(0.0, R_BOUNDARY, color="#3b78a8", alpha=0.055, zorder=0)
    ax.axvspan(R_BOUNDARY, 0.53, color="#b64a42", alpha=0.05, zorder=0)
    for U in [20.0, 40.0, 80.0]:
        group = points[points["U"].eq(U)].sort_values("r")
        signed_s = -group["s"].to_numpy(dtype=float)
        ax.plot(
            group["r"],
            signed_s,
            marker=MARKERS[U],
            color=COLORS[U],
            lw=0,
            ms=6.5,
            label=rf"$U={U:g}$",
            zorder=4,
        )
        if cnn_predictions is None:
            s0 = -float(group.loc[group["V"].eq(0), "s_u0"].iloc[0])
            r = np.linspace(0.0, 0.245, 220)
            ax.plot(
                r,
                mott_scale_law_from_axis_anchor(r, s0),
                color=COLORS[U],
                lw=1.55,
                alpha=0.8,
            )
        else:
            prediction = cnn_predictions[cnn_predictions["U"].eq(U)].sort_values("r")
            ax.plot(
                prediction["r"],
                prediction["s_eq10_signed"],
                marker=MARKERS[U],
                markerfacecolor="white",
                markeredgecolor=COLORS[U],
                markeredgewidth=1.1,
                color=COLORS[U],
                lw=1.55,
                ms=5.2,
                alpha=0.9,
                zorder=3,
            )

    r = np.linspace(0.255, 0.52, 240)
    ax.plot(
        r,
        cdw_scale_law(r),
        color="black",
        ls="-.",
        lw=2.0,
    )
    ax.axvline(R_BOUNDARY, color="0.35", lw=1.0, ls=":")
    ax.hlines(
        S_U_RESOLUTION,
        0.0,
        R_BOUNDARY,
        color="0.45",
        ls="--",
        lw=1.0,
    )
    ax.hlines(S_V, R_BOUNDARY, 0.53, color="0.15", ls=":", lw=1.35)
    ax.text(
        0.155,
        S_U_RESOLUTION - 0.018,
        r"$U\to\infty,\ 4C_{\mathrm{NN}}$",
        ha="center",
        va="top",
        color="0.38",
    )
    ax.text(
        0.515,
        S_V - 0.008,
        r"$V$-only $-8/7$",
        ha="right",
        va="top",
        color="0.1",
    )
    ax.text(
        0.105,
        -1.075,
        "Mott side",
        color="#1f5278",
        ha="center",
        va="top",
    )
    ax.text(
        0.39,
        -1.075,
        "CDW side",
        color="#8d2d28",
        ha="center",
        va="top",
    )
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel(r"$s_{\mathrm{NN}}(U,V)$")
    ax.set_xlim(-0.01, 0.53)
    ax.set_ylim(-1.84, -1.06)
    ax.grid(alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    if cnn_predictions is not None:
        fixture = (
            "fixture_only" in cnn_predictions.columns
            and cnn_predictions["fixture_only"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("true")
            .all()
        )
        handles.append(
            Line2D(
                [],
                [],
                color="0.25",
                marker="o",
                markerfacecolor="white",
                markeredgecolor="0.25",
                lw=1.55,
                ms=5.2,
            )
        )
        labels.append(
            r"Eq. (10), pointwise $C_{\mathrm{NN}}$"
            + (" (fixture)" if fixture else " (fullobs F861)")
        )
    ax.legend(
        handles,
        labels,
        frameon=False,
        ncol=1,
        loc="upper left",
        bbox_to_anchor=(0.005, 0.88),
        borderaxespad=0.0,
    )
    panel_label(ax, "(a)", panel_label_x, fontsize=panel_label_fontsize)


def draw_boundary_panel(
    ax: plt.Axes,
    boundary: pd.DataFrame,
    *,
    mixed_momentum_terms: bool = False,
    panel_label_fontsize: float = 12.5,
    panel_label_x: float = -0.1435,
) -> None:
    """Plot the critical interaction ratio for U/t >= 4."""
    # Sampling density remains available in the source table, but the main
    # figure presents all independently bracketed transition points uniformly.
    _ = mixed_momentum_terms

    ax.plot(
        boundary["U"],
        boundary["V_c_over_U"],
        color="0.65",
        lw=1.1,
        zorder=1,
    )
    ax.errorbar(
        boundary["U"],
        boundary["V_c_over_U"],
        yerr=boundary["V_c_over_U_halfwidth"],
        fmt="o",
        markersize=6.0,
        markerfacecolor="white",
        markeredgecolor="#335f8d",
        markeredgewidth=1.05,
        ecolor="#335f8d",
        elinewidth=1.1,
        capsize=2.6,
        color="#335f8d",
        linestyle="none",
        zorder=3,
    )

    ax.axhline(R_BOUNDARY, color="0.18", ls="--", lw=1.25, zorder=0)
    ax.set_xlabel(r"$U/t$")
    ax.set_ylabel(r"$(V/U)_c$")
    ax.set_xlim(2.7, 41.3)
    ax.set_ylim(0.2497, 0.2581)
    ax.set_xticks(np.arange(4, 41, 4))
    ax.set_yticks([0.250, 0.252, 0.254, 0.256, 0.258])
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.3f"))
    ax.grid(axis="y", alpha=0.22)
    panel_label(ax, "(b)", panel_label_x, fontsize=panel_label_fontsize)


def _render_combined_figure(
    *,
    points: pd.DataFrame,
    boundary: pd.DataFrame,
    cnn_predictions: pd.DataFrame | None,
    out_pdf: Path,
    out_png: Path,
    mixed_momentum_terms: bool,
    vertical: bool,
    axis_text_scale: float,
    staging_preview: bool,
) -> None:
    """Render an already validated figure payload to the supplied paths."""
    render_style = dict(STYLE)
    if vertical:
        # This layout is included below full column width in the manuscript;
        # enlarge every textual element, not only the axes labels and ticks.
        for key in (
            "font.size",
            "axes.labelsize",
            "axes.titlesize",
            "xtick.labelsize",
            "ytick.labelsize",
            "legend.fontsize",
        ):
            if key in render_style:
                render_style[key] *= 1.2

    with plt.rc_context(render_style):
        if vertical:
            fig, axes = plt.subplots(
                2,
                1,
                figsize=(5.55, 7.8),
                gridspec_kw={"height_ratios": [1.0, 1.0]},
            )
        else:
            fig, axes = plt.subplots(
                1,
                2,
                figsize=(12.1, 4.8),
                gridspec_kw={"width_ratios": [1.62, 1.0]},
            )

        panel_fontsize = 20.4 if vertical else 12.5
        draw_scale_panel(
            axes[0],
            points,
            cnn_predictions=cnn_predictions,
            panel_label_fontsize=panel_fontsize,
            panel_label_x=-0.13 if vertical else -0.115,
        )
        draw_boundary_panel(
            axes[1],
            boundary,
            mixed_momentum_terms=mixed_momentum_terms,
            panel_label_fontsize=panel_fontsize,
            panel_label_x=-0.19 if vertical else -0.1435,
        )

        for ax in axes:
            ax.xaxis.label.set_fontsize(
                render_style["axes.labelsize"] * axis_text_scale
            )
            ax.yaxis.label.set_fontsize(
                render_style["axes.labelsize"] * axis_text_scale
            )
            ax.tick_params(
                axis="x",
                labelsize=render_style["xtick.labelsize"] * axis_text_scale,
            )
            ax.tick_params(
                axis="y",
                labelsize=render_style["ytick.labelsize"] * axis_text_scale,
            )

        if vertical:
            fig.subplots_adjust(
                left=0.200,
                right=0.995,
                top=0.992,
                bottom=0.082,
                hspace=0.20,
            )
        else:
            fig.subplots_adjust(
                left=0.070,
                right=0.985,
                top=0.975,
                bottom=0.155,
                wspace=0.265,
            )
        if staging_preview:
            fixture = (
                cnn_predictions is not None
                and "fixture_only" in cnn_predictions.columns
                and cnn_predictions["fixture_only"]
                .astype(str)
                .str.strip()
                .str.lower()
                .eq("true")
                .all()
            )
            preview_kind = "SYNTHETIC C_NN FIXTURE" if fixture else "POINTWISE C_NN"
            fig.text(
                0.5,
                0.998,
                f"STAGING PREVIEW — {preview_kind} — NOT FOR PUBLICATION",
                ha="center",
                va="top",
                color="#9b1c1c",
                fontsize=9.0,
                fontweight="bold",
            )
        fig.savefig(out_pdf, bbox_inches="tight")
        fig.savefig(out_png, dpi=280, bbox_inches="tight")
        plt.close(fig)


def _validate_pointwise_case_alignment(
    points: pd.DataFrame,
    cnn_predictions: pd.DataFrame,
) -> None:
    plotted = points[
        points["branch"].isin(["U-only", "Mott/spin"])
        & points["U"].isin([20.0, 40.0, 80.0])
    ]
    plotted_cases = {
        (float(row.U), float(row.V)) for row in plotted.itertuples(index=False)
    }
    prediction_cases = {
        (float(row.U), float(row.V)) for row in cnn_predictions.itertuples(index=False)
    }
    if (
        len(plotted) != 16
        or plotted.duplicated(["U", "V"]).any()
        or plotted_cases != prediction_cases
    ):
        raise RuntimeError(
            "Current GZ figure input and validated C_NN bundle do not share the exact 16 cases"
        )


def promote_pointwise_publication_release(
    *,
    fullobs_analysis_dir: Path,
) -> dict[str, Path]:
    """Atomically promote the complete horizontal+vertical Fig. 4 release.

    The eight publication artifacts and active-bundle pointer are rendered and
    validated together.  Under one interprocess lock, the reviewed legacy
    archive is installed (or revalidated) and all nine files are committed as
    one all-or-restore transaction, with the pointer deliberately last.
    Synthetic fixtures and transient analysis directories are never accepted.
    """
    source_dir = Path(fullobs_analysis_dir).expanduser().resolve()
    for transient_root in (STAGING_ROOT.resolve(), (ROOT / ".codex_tmp").resolve()):
        try:
            source_dir.relative_to(transient_root)
        except ValueError:
            continue
        raise RuntimeError(
            "Publication promotion requires a durable analysis bundle outside "
            f"{transient_root}"
        )

    # A publication source must be the exact immutable seven-file release made
    # by the reviewed freezer, not an analyzer candidate copied to an arbitrary
    # durable directory.  The strict scientific loader below remains a second,
    # independent gate over the bytes named by this manifest.
    try:
        frozen_release_manifest = validate_frozen_full861_release(
            source_dir,
            results_root=RESULTS,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            "Publication promotion requires a validated frozen full-861 release"
        ) from exc
    frozen_release_manifest_path = source_dir / RELEASE_MANIFEST_BASENAME
    frozen_release_manifest_sha256 = _sha256(frozen_release_manifest_path)

    # Complete bundle, formula, current-GZ, inventory, and analytic-payload
    # validation precedes every staging or active-path write.
    bundle = load_validated_fullobs_eq10_bundle(
        source_dir,
        allow_fixture=False,
        scale_points_path=SCALE_POINTS,
    )
    points = load_scale_data()
    boundary = load_boundary_data(write_filtered=False)
    _validate_pointwise_case_alignment(points, bundle.rows)
    validation, summary = assemble_analytic_validation(
        points,
        cnn_predictions=bundle.rows,
        cnn_provenance=bundle.provenance,
        cnn_source_dir=bundle.source_dir,
    )

    # Pointer/archive state is then classified before any staging write.  If a
    # previous pointwise release exists, its immutable legacy archive must
    # already be complete.  Otherwise the currently active analytic files must
    # be the exact reviewed legacy bytes that will be archived on commit.
    initial_pointer = _read_pointer_state(ACTIVE_BUNDLE_POINTER)
    if initial_pointer is None:
        if not (ANALYTIC_POINTS.is_file() and ANALYTIC_SUMMARY.is_file()):
            raise RuntimeError(
                "First pointwise release requires both reviewed legacy analytic outputs"
            )
        active_legacy_hashes = {
            "analytic_csv": _sha256(ANALYTIC_POINTS),
            "analytic_json": _sha256(ANALYTIC_SUMMARY),
        }
        if active_legacy_hashes != REVIEWED_LEGACY_ANALYTIC_SHA256:
            raise RuntimeError(
                "First pointwise release found unreviewed active legacy analytic outputs"
            )
        if os.path.lexists(LEGACY_ANALYTIC_ARCHIVE_DIR):
            _archive_legacy_analytic_outputs(
                analytic_csv=ANALYTIC_POINTS,
                analytic_json=ANALYTIC_SUMMARY,
                archive_dir=LEGACY_ANALYTIC_ARCHIVE_DIR,
                expected_sha256=REVIEWED_LEGACY_ANALYTIC_SHA256,
            )
    else:
        _validate_reviewed_legacy_archive(
            archive_dir=LEGACY_ANALYTIC_ARCHIVE_DIR,
            analytic_csv=ANALYTIC_POINTS,
            analytic_json=ANALYTIC_SUMMARY,
            expected_sha256=REVIEWED_LEGACY_ANALYTIC_SHA256,
        )

    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    release_stage = Path(
        tempfile.mkdtemp(prefix="fig4_fullobs_release_", dir=STAGING_ROOT)
    )
    stage_paths = {
        "pnas_pdf": release_stage / "pnas_horizontal.pdf",
        "pnas_png": release_stage / "pnas_horizontal.png",
        "prl_pdf": release_stage / "prl_vertical.pdf",
        "prl_png": release_stage / "prl_vertical.png",
        "manuscript_pdf": release_stage / "manuscript_fig4.pdf",
        "analytic_csv": release_stage / "analytic.csv",
        "analytic_json": release_stage / "analytic.json",
        "boundary_csv": release_stage / "boundary.csv",
        "pointer": release_stage / "active_bundle_pointer.json",
    }
    destinations = {
        "pnas_pdf": OUT_PDF,
        "pnas_png": OUT_PNG,
        "prl_pdf": PRL_VERTICAL_OUT_PDF,
        "prl_png": PRL_VERTICAL_OUT_PNG,
        "manuscript_pdf": MANUSCRIPT_FIG4_OUT_PDF,
        "analytic_csv": ANALYTIC_POINTS,
        "analytic_json": ANALYTIC_SUMMARY,
        "boundary_csv": BOUNDARY_FILTERED,
        "pointer": ACTIVE_BUNDLE_POINTER,
    }
    try:
        validation.to_csv(stage_paths["analytic_csv"], index=False)
        stage_paths["analytic_json"].write_text(json.dumps(summary, indent=2) + "\n")
        boundary.to_csv(stage_paths["boundary_csv"], index=False)
        _render_combined_figure(
            points=points,
            boundary=boundary,
            cnn_predictions=bundle.rows,
            out_pdf=stage_paths["pnas_pdf"],
            out_png=stage_paths["pnas_png"],
            mixed_momentum_terms=False,
            vertical=False,
            axis_text_scale=1.0,
            staging_preview=False,
        )
        _render_combined_figure(
            points=points,
            boundary=boundary,
            cnn_predictions=bundle.rows,
            out_pdf=stage_paths["prl_pdf"],
            out_png=stage_paths["prl_png"],
            mixed_momentum_terms=True,
            vertical=True,
            axis_text_scale=1.4,
            staging_preview=False,
        )
        # The active manuscript consumes the vertical PRL layout.  Copy the
        # already-rendered staged bytes rather than rendering a third time, so
        # the manuscript figure is provably the same release artifact.
        shutil.copy2(stage_paths["prl_pdf"], stage_paths["manuscript_pdf"])
        if stage_paths["manuscript_pdf"].read_bytes() != stage_paths[
            "prl_pdf"
        ].read_bytes():
            raise RuntimeError(
                "Staged manuscript Fig. 4 is not byte-identical to the PRL PDF"
            )
        release_hashes = {
            role: _sha256(stage_paths[role])
            for role in (
                "pnas_pdf",
                "pnas_png",
                "prl_pdf",
                "prl_png",
                "manuscript_pdf",
                "analytic_csv",
                "analytic_json",
                "boundary_csv",
            )
        }
        stage_paths["pointer"].write_text(
            json.dumps(
                {
                    "schema_version": FULL861_SCHEMA_VERSION,
                    "data_product": bundle.provenance.get("data_product"),
                    "C_NN_fidelity": bundle.provenance.get("C_NN_fidelity"),
                    "analysis_dir": str(bundle.source_dir.resolve()),
                    "pointwise_csv_sha256": bundle.provenance["output_files"][
                        "fig4_cnn_pointwise_eq10.csv"
                    ],
                    "analysis_provenance_sha256": _sha256(
                        bundle.source_dir / PROVENANCE_BASENAME
                    ),
                    "analysis_release_manifest_sha256": (
                        frozen_release_manifest_sha256
                    ),
                    "analysis_bundle_sha256": frozen_release_manifest[
                        "analysis_bundle_sha256"
                    ],
                    "decision_certificate_sha256": frozen_release_manifest[
                        "decision_certificate_sha256"
                    ],
                    "decision_gate_algorithm": frozen_release_manifest[
                        "decision_gate_algorithm"
                    ],
                    "reviewed_inputs": bundle.provenance.get("reviewed_inputs"),
                    "legacy_analytic_archive": str(
                        LEGACY_ANALYTIC_ARCHIVE_DIR.resolve()
                    ),
                    "release_artifacts_sha256": release_hashes,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if not all(
            path.is_file() and path.stat().st_size > 0 for path in stage_paths.values()
        ):
            raise RuntimeError("Unified Fig. 4 release staging is incomplete")

        # Pointer is last by construction.  A failure at any earlier or final
        # replacement restores both layouts, all derived tables, and pointer.
        ordered_roles = (
            "pnas_pdf",
            "pnas_png",
            "prl_pdf",
            "prl_png",
            "manuscript_pdf",
            "analytic_csv",
            "analytic_json",
            "boundary_csv",
            "pointer",
        )
        promotion_pairs = [
            (stage_paths[role], destinations[role]) for role in ordered_roles
        ]

        with _promotion_lock(ACTIVE_BUNDLE_POINTER):
            # Close the validation-to-commit window.  Even owner chmod/tampering
            # of the nominally read-only release must be detected before any
            # active artifact is replaced.
            current_release_manifest = validate_frozen_full861_release(
                source_dir,
                results_root=RESULTS,
            )
            if (
                current_release_manifest != frozen_release_manifest
                or _sha256(frozen_release_manifest_path)
                != frozen_release_manifest_sha256
            ):
                raise RuntimeError(
                    "Frozen full-861 release changed during publication staging"
                )
            current_pointer = _read_pointer_state(ACTIVE_BUNDLE_POINTER)
            archive_created = False
            if current_pointer is None:
                archive_created = _archive_legacy_analytic_outputs(
                    analytic_csv=ANALYTIC_POINTS,
                    analytic_json=ANALYTIC_SUMMARY,
                    archive_dir=LEGACY_ANALYTIC_ARCHIVE_DIR,
                    expected_sha256=REVIEWED_LEGACY_ANALYTIC_SHA256,
                )
            else:
                _validate_reviewed_legacy_archive(
                    archive_dir=LEGACY_ANALYTIC_ARCHIVE_DIR,
                    analytic_csv=ANALYTIC_POINTS,
                    analytic_json=ANALYTIC_SUMMARY,
                    expected_sha256=REVIEWED_LEGACY_ANALYTIC_SHA256,
                )
            try:
                _transactional_promote(promotion_pairs)
            except BaseException:
                if archive_created:
                    shutil.rmtree(LEGACY_ANALYTIC_ARCHIVE_DIR)
                raise
    finally:
        shutil.rmtree(release_stage, ignore_errors=True)

    return {role: Path(path) for role, path in destinations.items()}


def build_figure(
    *,
    out_pdf: Path = OUT_PDF,
    out_png: Path = OUT_PNG,
    mixed_momentum_terms: bool = False,
    vertical: bool = False,
    axis_text_scale: float = 1.0,
    fullobs_analysis_dir: Path | None = None,
    staging_preview: bool = False,
    production_promotion: bool = False,
    allow_fixture: bool = False,
    write_derived_tables: bool = True,
    analytic_points_path: Path = ANALYTIC_POINTS,
    analytic_summary_path: Path = ANALYTIC_SUMMARY,
    boundary_filtered_path: Path = BOUNDARY_FILTERED,
) -> None:
    """Build the combined figure with explicit staging/production gates.

    The no-argument/default path is intentionally unchanged.  Pointwise input
    always requires the analyzer's CSV+provenance bundle.  Staging confines
    every written artifact to ``ROOT/tmp``.  Production promotion is a
    separate, fixture-forbidden opt-in.  Either canonical PNAS or PRL
    production invocation delegates to one unified horizontal+vertical release
    transaction; a publication generation can never promote only one layout.
    """
    active_pointer: dict[str, object] | None = None
    active_pointer_rebuild = False
    pointer_lexists = os.path.lexists(ACTIVE_BUNDLE_POINTER)
    if fullobs_analysis_dir is None and pointer_lexists:
        if not ACTIVE_BUNDLE_POINTER.is_file():
            raise RuntimeError(
                "Active Fig. 4 bundle pointer exists but is not a regular file: "
                f"{ACTIVE_BUNDLE_POINTER}"
            )
        active_pointer = _load_active_bundle_pointer(ACTIVE_BUNDLE_POINTER)
        fullobs_analysis_dir = Path(str(active_pointer["analysis_dir"]))
        active_pointer_rebuild = True
    if production_promotion and pointer_lexists:
        if not ACTIVE_BUNDLE_POINTER.is_file():
            raise RuntimeError(
                "Refusing production promotion over a non-file active Fig. 4 pointer: "
                f"{ACTIVE_BUNDLE_POINTER}"
            )
        # A malformed pointer signals an already inconsistent active state.  It
        # must be repaired explicitly rather than silently overwritten.
        _load_active_bundle_pointer(ACTIVE_BUNDLE_POINTER)

    if staging_preview and production_promotion:
        raise RuntimeError(
            "staging_preview and production_promotion are mutually exclusive"
        )
    if fullobs_analysis_dir is not None and not (
        staging_preview or production_promotion or active_pointer_rebuild
    ):
        raise RuntimeError(
            "Pointwise C_NN requires explicit staging_preview or production_promotion"
        )
    if production_promotion and fullobs_analysis_dir is None:
        raise RuntimeError("Production promotion requires fullobs_analysis_dir")
    if allow_fixture and not staging_preview:
        raise RuntimeError(
            "Synthetic fixtures are allowed only in staging preview mode"
        )
    if production_promotion and allow_fixture:
        raise RuntimeError("Synthetic fixtures can never be promoted")

    figure_destinations = (("PDF", out_pdf), ("PNG", out_png))
    derived_destinations = (
        ("analytic CSV", analytic_points_path),
        ("analytic JSON", analytic_summary_path),
        ("filtered boundary CSV", boundary_filtered_path),
    )
    destinations = figure_destinations + (
        derived_destinations if write_derived_tables else ()
    )
    if staging_preview:
        if fullobs_analysis_dir is None:
            raise RuntimeError(
                "A staging pointwise preview requires fullobs_analysis_dir"
            )
        staging_root = STAGING_ROOT.resolve()
        resolved_destinations: list[Path] = []
        for label, destination in destinations:
            resolved = Path(destination).expanduser().resolve()
            resolved_destinations.append(resolved)
            try:
                resolved.relative_to(staging_root)
            except ValueError as exc:
                raise RuntimeError(
                    f"Staging {label} output must remain below {staging_root}: {resolved}"
                ) from exc
        if len(set(resolved_destinations)) != len(resolved_destinations):
            raise RuntimeError("Every staging artifact requires a distinct output path")
        active_destinations = {
            OUT_PDF.resolve(),
            OUT_PNG.resolve(),
            ANALYTIC_POINTS.resolve(),
            ANALYTIC_SUMMARY.resolve(),
            BOUNDARY_FILTERED.resolve(),
        }
        if any(path in active_destinations for path in resolved_destinations):
            raise RuntimeError("Staging preview cannot target an active artifact path")

    if production_promotion:
        resolved = {
            label: Path(path).expanduser().resolve() for label, path in destinations
        }
        if write_derived_tables:
            expected = {
                "PDF": OUT_PDF.resolve(),
                "PNG": OUT_PNG.resolve(),
                "analytic CSV": ANALYTIC_POINTS.resolve(),
                "analytic JSON": ANALYTIC_SUMMARY.resolve(),
                "filtered boundary CSV": BOUNDARY_FILTERED.resolve(),
            }
            if vertical or resolved != expected:
                raise RuntimeError(
                    "Derived-table production promotion requires the canonical horizontal PNAS artifact set"
                )
        else:
            expected = {
                "PDF": PRL_VERTICAL_OUT_PDF.resolve(),
                "PNG": PRL_VERTICAL_OUT_PNG.resolve(),
            }
            if not vertical or resolved != expected:
                raise RuntimeError(
                    "Figure-only production promotion requires the canonical PRL vertical pair"
                )

        assert fullobs_analysis_dir is not None
        promote_pointwise_publication_release(
            fullobs_analysis_dir=Path(fullobs_analysis_dir)
        )
        return

    if active_pointer_rebuild:
        resolved = {
            label: Path(path).expanduser().resolve() for label, path in destinations
        }
        if write_derived_tables:
            expected = {
                "PDF": OUT_PDF.resolve(),
                "PNG": OUT_PNG.resolve(),
                "analytic CSV": ANALYTIC_POINTS.resolve(),
                "analytic JSON": ANALYTIC_SUMMARY.resolve(),
                "filtered boundary CSV": BOUNDARY_FILTERED.resolve(),
            }
            if vertical or resolved != expected:
                raise RuntimeError(
                    "Active pointwise default rebuild requires the canonical horizontal PNAS artifact set"
                )
        else:
            expected = {
                "PDF": PRL_VERTICAL_OUT_PDF.resolve(),
                "PNG": PRL_VERTICAL_OUT_PNG.resolve(),
            }
            if not vertical or resolved != expected:
                raise RuntimeError(
                    "Active pointwise figure-only rebuild requires the canonical PRL vertical pair"
                )

        assert fullobs_analysis_dir is not None
        promote_pointwise_publication_release(
            fullobs_analysis_dir=Path(fullobs_analysis_dir)
        )
        return

    bundle = None
    cnn_predictions = None
    if fullobs_analysis_dir is not None:
        # This complete row/provenance/hash gate runs before directory creation
        # or any derived-table/figure write.
        bundle = load_validated_fullobs_eq10_bundle(
            fullobs_analysis_dir,
            allow_fixture=allow_fixture,
            scale_points_path=SCALE_POINTS,
        )
        cnn_predictions = bundle.rows

    points = load_scale_data()
    boundary = load_boundary_data(write_filtered=False)
    if cnn_predictions is not None:
        _validate_pointwise_case_alignment(points, cnn_predictions)

    analytic_payload: tuple[pd.DataFrame, dict[str, object]] | None = None
    if write_derived_tables:
        analytic_payload = assemble_analytic_validation(
            points,
            cnn_predictions=cnn_predictions,
            cnn_provenance=(bundle.provenance if bundle is not None else None),
            cnn_source_dir=(bundle.source_dir if bundle is not None else None),
        )

    # Initial/new production generations and all later active pointwise
    # rebuilds returned above through the unified orchestrator.  The remaining
    # direct-write paths are either an explicitly confined staging preview or
    # the deliberately unchanged pre-promotion legacy default.
    write_pdf = Path(out_pdf)
    write_png = Path(out_png)
    write_analytic_csv = Path(analytic_points_path)
    write_analytic_json = Path(analytic_summary_path)
    write_boundary_csv = Path(boundary_filtered_path)

    write_paths = [write_pdf, write_png]
    if write_derived_tables:
        write_paths.extend(
            [write_analytic_csv, write_analytic_json, write_boundary_csv]
        )

    for destination in write_paths:
        destination.parent.mkdir(parents=True, exist_ok=True)
    if analytic_payload is not None:
        validation, summary = analytic_payload
        validation.to_csv(write_analytic_csv, index=False)
        write_analytic_json.write_text(json.dumps(summary, indent=2) + "\n")
        boundary.to_csv(write_boundary_csv, index=False)

    _render_combined_figure(
        points=points,
        boundary=boundary,
        cnn_predictions=cnn_predictions,
        out_pdf=write_pdf,
        out_png=write_png,
        mixed_momentum_terms=mixed_momentum_terms,
        vertical=vertical,
        axis_text_scale=axis_text_scale,
        staging_preview=staging_preview,
    )


def main() -> None:
    """Refuse ambiguous direct execution.

    Publication promotion is a multi-artifact transaction and legacy previews
    must be explicitly staged by a caller.  Historically, even ``--help``
    reached ``build_figure()`` and overwrote the active horizontal artifacts.
    Keep the module importable, but make its command-line entry point
    deliberately read-only.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.epilog = (
        "Direct figure writes are disabled. Import build_figure() for an "
        "explicit staging build, or promote_pointwise_publication_release() "
        "for the reviewed atomic publication release."
    )
    parser.parse_args()
    parser.error(parser.epilog)


if __name__ == "__main__":
    main()
