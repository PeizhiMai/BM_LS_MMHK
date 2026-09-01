#!/usr/bin/env python3
"""Validate and analyze the finite-(U,V) Fig. 4 C_NN fullobs campaign.

This is deliberately a downstream, staging-only analyzer.  It does not edit
the manuscript, a figure, or any of the result tables currently consumed by
the figure builders.  A caller supplies a fresh output directory.

The primary finite-(U,V) estimator is the *unweighted* arithmetic mean over
the exact deterministic 25-twist maximin panel.  Exchange-multiplicity
weighting and the twist-to-twist spread are retained only as diagnostics; the
latter is not divided by sqrt(25) and is not called a statistical error.

The analyzer combines the twelve new campaign cases with four existing
full-861 U=40 controls, then evaluates the signed Eq. (10) prediction

    s_NN = 1 + (2U-V)/(U-V) * (2 C_NN - 1/2)

at the sixteen Mott-side points in the GZ scale table.  It also evaluates the
old V=0-axis-anchor baseline for an explicit, pointwise comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NSITES = 16.0
SCHEMA_VERSION = 1
DATA_PRODUCT = "fig4_pointwise_direct_fullobs_C_NN_eq10"
C_NN_OBSERVABLE = "<C1_NN>"
REVIEWED_MANIFEST_SHA256 = (
    "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
)

EXPECTED_CAMPAIGN_CASES = (
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

EXPECTED_U40_CONTROLS = ((40.0, 0.0), (40.0, 4.0), (40.0, 8.0), (40.0, 9.0))

EXPECTED_POINTWISE_CASES = tuple(
    sorted(set(EXPECTED_CAMPAIGN_CASES) | set(EXPECTED_U40_CONTROLS))
)

EXPECTED_TWISTS = (
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

COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
FILENAME_RE = re.compile(
    r"^L4x4Nup8Ndn8U(?P<U>[^V]+)V(?P<V>[^t]+)tp(?P<tp>[^f]+)"
    r"f(?P<kx>\d+)x(?P<ky>\d+)Q(?P<Qm>-?\d+)x(?P<Qn>-?\d+)_obs\.dat$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_MANIFEST_COLUMNS = {
    "index",
    "U",
    "V",
    "V_over_U",
    "expected_phase",
    "twist_index",
    "kx",
    "ky",
    "seed",
    "result",
}

REQUIRED_RAW_KEYS = {
    "Lx",
    "Ly",
    "tp",
    "U",
    "V",
    "E0",
    "Gap",
    "<nn_NN>",
    "<delta_n_delta_n_NN>",
    "<Kinetic_NN_per_site>",
    "<Kinetic_NNN_per_site>",
    "<Kinetic_per_site>",
    "<C1_NN>",
    "Q",
    "<nq>",
    "<nq_upnq_dn>",
    "<ni_upni_dn>",
    "<Spipi>",
    "<Sc_pipi>",
    "<mCDW2_pipi>",
    "status",
}

OUTPUT_BASENAMES = {
    "raw": "fig4_cnn_campaign_raw_validation.csv",
    "panel": "fig4_cnn_campaign_panel_summary.csv",
    "controls": "fig4_cnn_u40_panel_calibration.csv",
    "pointwise": "fig4_cnn_pointwise_eq10.csv",
    "families": "fig4_cnn_pointwise_family_summary.csv",
    "provenance": "fig4_cnn_analysis_provenance.json",
}


class ValidationError(RuntimeError):
    """Raised when a campaign or an input table violates its data contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-root",
        type=Path,
        required=True,
        help="Downloaded campaign directory containing manifest/provenance files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Override campaign manifest (default: CAMPAIGN_ROOT/manifest.tsv).",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Directory containing the 300 downloaded *_obs.dat files (default: CAMPAIGN_ROOT/raw).",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        help="Override campaign provenance JSON (default: CAMPAIGN_ROOT/provenance.json).",
    )
    parser.add_argument(
        "--twist-panel",
        type=Path,
        help="Override twist-panel table (default: CAMPAIGN_ROOT/twist_panel.tsv).",
    )
    parser.add_argument(
        "--u40-summary",
        type=Path,
        default=ROOT
        / "results"
        / "fullobs_U40_observable_summary_by_V_20260723_091307.csv",
    )
    parser.add_argument(
        "--u40-rows",
        type=Path,
        default=ROOT / "results" / "fullobs_U40_observable_rows_20260723_091307.csv.gz",
    )
    parser.add_argument(
        "--gz-points",
        type=Path,
        default=ROOT / "results" / "pnas_scale_rule_points_eta0p05.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Fresh staging directory. Existing analyzer outputs are never overwritten.",
    )
    parser.add_argument(
        "--identity-tolerance",
        type=float,
        default=1.0e-8,
        help="Maximum allowed absolute per-output observable-identity residual.",
    )
    parser.add_argument(
        "--u40-panel-bias-tolerance",
        type=float,
        default=1.0e-6,
        help="Maximum allowed |25-panel mean - full-861 mean| on each U=40 control.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_case(U: object, V: object) -> tuple[float, float]:
    return (round(float(U), 10), round(float(V), 10))


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValidationError(f"Missing {label}: {path}")
    return path


def validate_output_destination(output_dir: Path) -> None:
    resolved = output_dir.expanduser().resolve()
    for protected in (ROOT / "manuscript", ROOT / "figures"):
        try:
            resolved.relative_to(protected.resolve())
        except ValueError:
            continue
        raise ValidationError(
            f"Refusing to write analyzer staging files inside protected tree: {protected}"
        )
    if resolved == (ROOT / "results").resolve():
        raise ValidationError(
            "Refusing to write directly into the published results root"
        )
    collisions = [
        resolved / name
        for name in OUTPUT_BASENAMES.values()
        if (resolved / name).exists()
    ]
    if collisions:
        raise ValidationError(
            "Analyzer output already exists; choose a fresh staging directory: "
            + ", ".join(str(path) for path in collisions)
        )


def load_and_validate_manifest(manifest_path: Path) -> pd.DataFrame:
    manifest_path = require_file(manifest_path, "manifest")
    observed_hash = sha256(manifest_path)
    if observed_hash != REVIEWED_MANIFEST_SHA256:
        raise ValidationError(
            "Manifest SHA-256 does not match the reviewed campaign manifest: "
            f"expected {REVIEWED_MANIFEST_SHA256}, got {observed_hash}"
        )
    manifest = pd.read_csv(manifest_path, sep="\t")
    missing = sorted(REQUIRED_MANIFEST_COLUMNS - set(manifest.columns))
    if missing:
        raise ValidationError(f"Manifest is missing columns: {missing}")
    if len(manifest) != 300:
        raise ValidationError(
            f"Expected exactly 300 manifest rows, found {len(manifest)}"
        )

    for column in ("index", "twist_index", "kx", "ky", "seed"):
        manifest[column] = pd.to_numeric(manifest[column], errors="raise").astype(
            np.int64
        )
    for column in ("U", "V", "V_over_U"):
        manifest[column] = pd.to_numeric(manifest[column], errors="raise").astype(float)

    if (
        set(manifest["index"]) != set(range(1, 301))
        or manifest["index"].duplicated().any()
    ):
        raise ValidationError("Manifest indices must be the unique integers 1..300")
    if manifest["result"].duplicated().any():
        raise ValidationError("Manifest contains duplicate result paths")
    if (
        manifest["seed"].duplicated().any()
        or not manifest["seed"].between(1, 2**32 - 1).all()
    ):
        raise ValidationError("Manifest seeds must be unique nonzero uint32 values")
    if set(manifest["expected_phase"].astype(str)) != {"Mott"}:
        raise ValidationError(
            "Every campaign target must be labeled expected_phase=Mott"
        )
    if not np.allclose(
        manifest["V_over_U"], manifest["V"] / manifest["U"], atol=1e-13, rtol=0
    ):
        raise ValidationError("Manifest V_over_U values are inconsistent with U and V")

    observed_cases = {canonical_case(row.U, row.V) for row in manifest.itertuples()}
    expected_cases = set(EXPECTED_CAMPAIGN_CASES)
    if observed_cases != expected_cases:
        raise ValidationError(
            f"Campaign case set mismatch; missing={sorted(expected_cases - observed_cases)}, "
            f"extra={sorted(observed_cases - expected_cases)}"
        )

    expected_twists = set(EXPECTED_TWISTS)
    for (U, V), group in manifest.groupby(["U", "V"], sort=True):
        if len(group) != 25:
            raise ValidationError(
                f"Expected 25 manifest rows at U={U:g}, V={V:g}; found {len(group)}"
            )
        twists = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if twists != expected_twists:
            raise ValidationError(f"Twist panel mismatch at U={U:g}, V={V:g}")
        if set(group["twist_index"]) != set(range(1, 26)):
            raise ValidationError(f"twist_index must be 1..25 at U={U:g}, V={V:g}")
        by_index = group.set_index("twist_index")[["kx", "ky"]]
        for index, twist in enumerate(EXPECTED_TWISTS, 1):
            if tuple(map(int, by_index.loc[index])) != twist:
                raise ValidationError(
                    f"twist_index mapping mismatch at U={U:g}, V={V:g}, index={index}"
                )

    for row in manifest.itertuples(index=False):
        name = Path(str(row.result)).name
        match = FILENAME_RE.fullmatch(name)
        if not match:
            raise ValidationError(f"Unexpected result filename: {name}")
        values = match.groupdict()
        if (
            canonical_case(values["U"], values["V"]) != canonical_case(row.U, row.V)
            or float(values["tp"]) != 0.0
            or int(values["kx"]) != int(row.kx)
            or int(values["ky"]) != int(row.ky)
            or int(values["Qm"]) != 0
            or int(values["Qn"]) != 0
        ):
            raise ValidationError(
                f"Manifest parameters do not match result filename: {name}"
            )

    return manifest.sort_values("index").reset_index(drop=True)


def validate_twist_panel(path: Path) -> None:
    panel = pd.read_csv(require_file(path, "twist panel"), sep="\t")
    if not {"twist_index", "kx", "ky"}.issubset(panel.columns):
        raise ValidationError("Twist-panel table must contain twist_index, kx, and ky")
    observed = [
        (int(row.kx), int(row.ky))
        for row in panel.sort_values("twist_index").itertuples(index=False)
    ]
    if observed != list(EXPECTED_TWISTS):
        raise ValidationError(
            "Downloaded twist-panel table is not the reviewed 25-point panel"
        )


def load_and_validate_campaign_provenance(path: Path) -> dict:
    provenance = json.loads(require_file(path, "campaign provenance").read_text())
    if int(provenance.get("target_count", -1)) != 300:
        raise ValidationError("Campaign provenance target_count is not 300")
    pairs = {
        canonical_case(row.get("U"), row.get("V"))
        for row in provenance.get("pairs", [])
    }
    if pairs != set(EXPECTED_CAMPAIGN_CASES):
        raise ValidationError(
            "Campaign provenance pair list does not match the reviewed target set"
        )
    twists = [(int(row["kx"]), int(row["ky"])) for row in provenance.get("twists", [])]
    if twists != list(EXPECTED_TWISTS):
        raise ValidationError(
            "Campaign provenance twist list does not match the reviewed panel"
        )
    aggregation = provenance.get("aggregation", {})
    primary = str(aggregation.get("primary_C_NN_estimator", "")).lower()
    if "unweighted arithmetic mean" not in primary:
        raise ValidationError(
            "Campaign provenance does not declare the reviewed unweighted estimator"
        )
    if not bool(aggregation.get("twist_spread_is_not_standard_error", False)):
        raise ValidationError(
            "Campaign provenance must state that twist spread is not a standard error"
        )
    for key in ("solver_sha256", "source_sha256", "qbasis_library_sha256"):
        if not HEX64_RE.fullmatch(str(provenance.get(key, ""))):
            raise ValidationError(f"Campaign provenance lacks a valid {key}")
    if int(provenance.get("locate_E0_lanczos_maxit", -1)) != 10000:
        raise ValidationError("Campaign provenance does not pin locate_E0 maxit=10000")
    return provenance


def index_raw_files(raw_dir: Path, expected_names: Iterable[str]) -> dict[str, Path]:
    if not raw_dir.is_dir():
        raise ValidationError(f"Missing raw-output directory: {raw_dir}")
    expected = set(expected_names)
    found: dict[str, Path] = {}
    unexpected: list[str] = []
    for path in raw_dir.rglob("*_obs.dat"):
        if path.name not in expected:
            unexpected.append(str(path.relative_to(raw_dir)))
            continue
        if path.name in found:
            raise ValidationError(f"Duplicate downloaded raw basename: {path.name}")
        found[path.name] = path
    if unexpected:
        preview = ", ".join(sorted(unexpected)[:5])
        raise ValidationError(
            f"Raw directory contains {len(unexpected)} unexpected *_obs.dat files; first: {preview}"
        )
    missing = sorted(expected - set(found))
    if missing:
        preview = ", ".join(missing[:5])
        raise ValidationError(
            f"Missing {len(missing)} of 300 raw outputs; first: {preview}"
        )
    return found


def parse_raw_file(path: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")
    if not COMPLETE_RE.search(text):
        raise ValidationError(f"Raw output is not COMPLETE: {path}")
    values: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1].strip()
    missing = sorted(REQUIRED_RAW_KEYS - set(values))
    if missing:
        raise ValidationError(f"Raw output {path.name} is missing fields: {missing}")
    return values


def numeric(values: dict[str, str], key: str, path: Path) -> float:
    try:
        value = float(values[key])
    except (KeyError, ValueError) as exc:
        raise ValidationError(f"Non-numeric {key} in {path}") from exc
    if not math.isfinite(value):
        raise ValidationError(f"Non-finite {key} in {path}")
    return value


def parse_and_validate_outputs(
    manifest: pd.DataFrame,
    raw_dir: Path,
    identity_tolerance: float,
) -> pd.DataFrame:
    names = [Path(path).name for path in manifest["result"].astype(str)]
    indexed = index_raw_files(raw_dir, names)
    parsed: list[dict[str, object]] = []

    for row in manifest.itertuples(index=False):
        name = Path(str(row.result)).name
        path = indexed[name]
        values = parse_raw_file(path)
        U, V = float(row.U), float(row.V)
        if (
            numeric(values, "Lx", path) != 4.0
            or numeric(values, "Ly", path) != 4.0
            or numeric(values, "tp", path) != 0.0
            or not math.isclose(numeric(values, "U", path), U, abs_tol=1e-12, rel_tol=0)
            or not math.isclose(numeric(values, "V", path), V, abs_tol=1e-12, rel_tol=0)
            or values["Q"].replace(" ", "") != "0,0"
            or values["status"].strip() != "COMPLETE"
        ):
            raise ValidationError(f"Body metadata mismatch in {path.name}")

        E0 = numeric(values, "E0", path)
        gap = numeric(values, "Gap", path)
        nn = numeric(values, "<nn_NN>", path)
        delta_nn = numeric(values, "<delta_n_delta_n_NN>", path)
        kinetic_nn = numeric(values, "<Kinetic_NN_per_site>", path)
        kinetic_nnn = numeric(values, "<Kinetic_NNN_per_site>", path)
        kinetic = numeric(values, "<Kinetic_per_site>", path)
        C = numeric(values, "<C1_NN>", path)
        nq = numeric(values, "<nq>", path)
        nq_updn = numeric(values, "<nq_upnq_dn>", path)
        D = numeric(values, "<ni_upni_dn>", path)
        Spipi = numeric(values, "<Spipi>", path)
        Sc = numeric(values, "<Sc_pipi>", path)
        mcdw = numeric(values, "<mCDW2_pipi>", path)

        energy_residual = E0 / NSITES - (kinetic + U * D + 2.0 * V * nn)
        connected_residual = delta_nn - (nn - 1.0)
        kinetic_residual = kinetic - (kinetic_nn + kinetic_nnn)
        charge_residual = mcdw - Sc / NSITES
        identity_residuals = {
            "energy_identity_residual": energy_residual,
            "connected_density_identity_residual": connected_residual,
            "kinetic_identity_residual": kinetic_residual,
            "charge_identity_residual": charge_residual,
        }
        if (
            max(abs(value) for value in identity_residuals.values())
            > identity_tolerance
        ):
            raise ValidationError(
                f"Observable identity residual exceeds {identity_tolerance:g} in {path.name}: "
                + repr(identity_residuals)
            )
        if not (0.0 <= D < 0.25):
            raise ValidationError(
                f"Expected a Mott-side D_site<0.25 in {path.name}; found {D:g}"
            )
        if not (-0.75 - 1e-10 <= C <= 0.25 + 1e-10) or C >= 0.0:
            raise ValidationError(f"Unphysical/non-Mott C1_NN in {path.name}: {C:g}")
        if not (0.0 <= nn <= 4.0 and 0.0 <= mcdw <= 1.0 + 1e-10):
            raise ValidationError(f"Physical-range check failed in {path.name}")

        parsed.append(
            {
                "index": int(row.index),
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "twist_index": int(row.twist_index),
                "kx": int(row.kx),
                "ky": int(row.ky),
                "seed": int(row.seed),
                "filename": name,
                "raw_path": str(path.resolve()),
                "raw_sha256": sha256(path),
                "E0": E0,
                "Gap": gap,
                "D_site": D,
                "mCDW2_pipi": mcdw,
                "C1_NN": C,
                "nn_NN": nn,
                "kinetic_NN_per_site": kinetic_nn,
                "kinetic_NNN_per_site": kinetic_nnn,
                "kinetic_per_site": kinetic,
                "nq": nq,
                "nq_upnq_dn": nq_updn,
                "Spipi": Spipi,
                "Sc_pipi": Sc,
                **identity_residuals,
                "status": "COMPLETE",
            }
        )

    output = pd.DataFrame(parsed).sort_values("index").reset_index(drop=True)
    if len(output) != 300 or output["filename"].duplicated().any():
        raise ValidationError("Parsed-output inventory is not exactly 300 unique rows")
    return output


def population_std(values: pd.Series) -> float:
    return float(np.std(values.to_numpy(dtype=float), ddof=0))


def aggregate_campaign(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (U, V), group in raw.groupby(["U", "V"], sort=True):
        if len(group) != 25:
            raise ValidationError(f"Cannot aggregate incomplete case U={U:g}, V={V:g}")
        C = group["C1_NN"].to_numpy(dtype=float)
        weights = np.where(group["kx"].to_numpy() == group["ky"].to_numpy(), 1.0, 2.0)
        mean = float(np.mean(C))
        weighted_diagnostic = float(np.average(C, weights=weights))
        factor = (2.0 * U - V) / (U - V)
        rows.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "expected_phase": "Mott",
                "complete_twists": 25,
                "C_NN": mean,
                "C_NN_min": float(np.min(C)),
                "C_NN_max": float(np.max(C)),
                "C_NN_spread": float(np.ptp(C)),
                "C_NN_population_std_diagnostic": float(np.std(C, ddof=0)),
                "C_NN_symmetry_weighted_diagnostic": weighted_diagnostic,
                "C_NN_symmetry_weighted_minus_primary": weighted_diagnostic - mean,
                "s_eq10_signed": 1.0 + factor * (2.0 * mean - 0.5),
                "s_eq10_twist_spread_equivalent_diagnostic": 2.0
                * factor
                * float(np.ptp(C)),
                "D_site_panel_mean": float(group["D_site"].mean()),
                "mCDW2_pipi_panel_mean": float(group["mCDW2_pipi"].mean()),
                "nn_NN_panel_mean": float(group["nn_NN"].mean()),
                "kinetic_per_site_panel_mean": float(group["kinetic_per_site"].mean()),
                "max_abs_identity_residual": float(
                    group[
                        [
                            "energy_identity_residual",
                            "connected_density_identity_residual",
                            "kinetic_identity_residual",
                            "charge_identity_residual",
                        ]
                    ]
                    .abs()
                    .to_numpy()
                    .max()
                ),
                "C_NN_source": "new fullobs campaign",
                "C_NN_sampling": "deterministic_25_panel_unweighted_arithmetic_mean",
                "twist_spread_is_standard_error": False,
            }
        )
    summary = pd.DataFrame(rows)
    if {canonical_case(r.U, r.V) for r in summary.itertuples()} != set(
        EXPECTED_CAMPAIGN_CASES
    ):
        raise ValidationError("Aggregated campaign case inventory is not exact")
    return summary


def trapezoidal_weights(rows: pd.DataFrame) -> np.ndarray:
    kx = rows["kx"].to_numpy(dtype=int)
    ky = rows["ky"].to_numpy(dtype=int)
    symmetry = np.where(kx == ky, 1.0, 2.0)
    endpoint = np.where(np.isin(kx, [0, 40]), 0.5, 1.0) * np.where(
        np.isin(ky, [0, 40]), 0.5, 1.0
    )
    return symmetry * endpoint


def validate_and_load_u40_controls(
    summary_path: Path,
    rows_path: Path,
    panel_bias_tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(require_file(summary_path, "U=40 full-861 summary"))
    rows = pd.read_csv(require_file(rows_path, "U=40 full-861 rows"))
    needed_summary = {
        "U",
        "V",
        "wedge_rows",
        "wedge_completion_fraction",
        "quadrature_weight_observed",
        "quadrature_completion_fraction",
        "C1_NN_mean",
        "C1_NN_std",
        "branch",
    }
    needed_rows = {"U", "V", "kx", "ky", "C1_NN"}
    if not needed_summary.issubset(summary.columns) or not needed_rows.issubset(
        rows.columns
    ):
        raise ValidationError("U=40 control tables lack required columns")

    selected_summary = summary[
        summary.apply(
            lambda row: (
                canonical_case(row["U"], row["V"]) in set(EXPECTED_U40_CONTROLS)
            ),
            axis=1,
        )
    ].copy()
    if {canonical_case(r.U, r.V) for r in selected_summary.itertuples()} != set(
        EXPECTED_U40_CONTROLS
    ):
        raise ValidationError(
            "U=40 summary does not contain the four required controls exactly once"
        )
    if selected_summary.duplicated(["U", "V"]).any():
        raise ValidationError("Duplicate U=40 control rows")
    if not (
        selected_summary["wedge_rows"].eq(861).all()
        and np.allclose(selected_summary["wedge_completion_fraction"], 1.0)
        and np.allclose(selected_summary["quadrature_weight_observed"], 1600.0)
        and np.allclose(selected_summary["quadrature_completion_fraction"], 1.0)
        and selected_summary["branch"].astype(str).str.lower().eq("mott").all()
    ):
        raise ValidationError(
            "Required U=40 controls are not complete 861-row Mott grids"
        )

    panel_set = set(EXPECTED_TWISTS)
    calibration: list[dict[str, object]] = []
    controls: list[dict[str, object]] = []
    for control in selected_summary.sort_values("V").itertuples(index=False):
        group = rows[
            (rows["U"].astype(float) == 40.0)
            & np.isclose(rows["V"].astype(float), float(control.V))
        ].copy()
        if len(group) != 861 or group.duplicated(["kx", "ky"]).any():
            raise ValidationError(
                f"U=40,V={control.V:g} rows are not a unique 861-point wedge"
            )
        observed_wedge = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        expected_wedge = {(kx, ky) for ky in range(41) for kx in range(ky + 1)}
        if observed_wedge != expected_wedge:
            raise ValidationError(
                f"U=40,V={control.V:g} wedge coordinates are incomplete"
            )
        weights = trapezoidal_weights(group)
        if not math.isclose(float(weights.sum()), 1600.0, abs_tol=1e-12, rel_tol=0):
            raise ValidationError("U=40 quadrature weights do not sum to 1600")
        recomputed_full = float(
            np.average(group["C1_NN"].to_numpy(dtype=float), weights=weights)
        )
        full = float(control.C1_NN_mean)
        if not math.isclose(recomputed_full, full, abs_tol=5e-13, rel_tol=0):
            raise ValidationError(
                f"U=40,V={control.V:g} stored mean differs from recomputed quadrature: "
                f"{full:.15g} vs {recomputed_full:.15g}"
            )
        panel = group[
            group.apply(
                lambda row: (int(row["kx"]), int(row["ky"])) in panel_set, axis=1
            )
        ]
        if len(panel) != 25:
            raise ValidationError(
                f"U=40,V={control.V:g} control lacks the reviewed panel"
            )
        panel_mean = float(panel["C1_NN"].mean())
        bias = panel_mean - full
        if abs(bias) > panel_bias_tolerance:
            raise ValidationError(
                f"25-panel calibration bias exceeds {panel_bias_tolerance:g} at "
                f"U=40,V={control.V:g}: {bias:+.6g}"
            )
        calibration.append(
            {
                "U": 40.0,
                "V": float(control.V),
                "V_over_U": float(control.V) / 40.0,
                "C_NN_full_861": full,
                "C_NN_panel_25": panel_mean,
                "panel_minus_full": bias,
                "abs_panel_minus_full": abs(bias),
                "C_NN_panel_spread": float(panel["C1_NN"].max() - panel["C1_NN"].min()),
                "C_NN_full_grid_population_std_diagnostic": float(control.C1_NN_std),
                "panel_bias_tolerance": panel_bias_tolerance,
                "passes_panel_bias_gate": True,
                "panel_estimator": "unweighted arithmetic mean over reviewed 25 twists",
                "full_estimator": "861-point wedge with exchange and trapezoidal endpoint weights (weight 1600)",
            }
        )
        controls.append(
            {
                "U": 40.0,
                "V": float(control.V),
                "V_over_U": float(control.V) / 40.0,
                "C_NN": full,
                "C_NN_spread": np.nan,
                "C_NN_population_std_diagnostic": float(control.C1_NN_std),
                "C_NN_source": "existing U=40 all-twist fullobs control",
                "C_NN_sampling": "full_861_wedge_trapezoidal_weight_1600",
                "twist_spread_is_standard_error": False,
            }
        )
    return pd.DataFrame(controls), pd.DataFrame(calibration)


def axis_anchor_law(r: np.ndarray | float, s0_signed: np.ndarray | float) -> np.ndarray:
    r_array = np.asarray(r, dtype=float)
    s0_array = np.asarray(s0_signed, dtype=float)
    return (s0_array - 0.5 * (s0_array + 1.0) * r_array) / (1.0 - r_array)


def build_pointwise_table(
    campaign: pd.DataFrame,
    controls: pd.DataFrame,
    gz_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    gz = pd.read_csv(require_file(gz_path, "GZ scale-point table"))
    required = {"U", "V", "r", "branch", "s", "s_u0", "source_csv"}
    if not required.issubset(gz.columns):
        raise ValidationError(
            f"GZ point table is missing columns: {sorted(required - set(gz.columns))}"
        )
    selected = gz[
        gz["branch"].astype(str).isin(["U-only", "Mott/spin"])
        & gz["U"].astype(float).isin([20.0, 40.0, 80.0])
    ].copy()
    observed_cases = {canonical_case(r.U, r.V) for r in selected.itertuples()}
    if observed_cases != set(EXPECTED_POINTWISE_CASES) or len(selected) != 16:
        raise ValidationError(
            f"GZ Mott-side point inventory mismatch; expected 16 exact points, found {len(selected)}"
        )
    if selected.duplicated(["U", "V"]).any():
        raise ValidationError("Duplicate GZ Mott-side (U,V) points")
    if not np.allclose(
        selected["r"], selected["V"] / selected["U"], atol=1e-13, rtol=0
    ):
        raise ValidationError("GZ r values are inconsistent with U and V")
    if not (
        np.isfinite(selected[["s", "s_u0"]].to_numpy(dtype=float)).all()
        and (selected[["s", "s_u0"]].to_numpy(dtype=float) > 0.0).all()
    ):
        raise ValidationError(
            "GZ s and s_u0 must be finite positive magnitudes before signing"
        )
    anchors = selected[selected["V"].astype(float).eq(0.0)]
    if len(anchors) != 3 or set(anchors["branch"].astype(str)) != {"U-only"}:
        raise ValidationError(
            "Expected exactly one U-only V=0 anchor for each U family"
        )
    for U, group in selected.groupby("U", sort=True):
        if not np.allclose(group["s_u0"], group["s_u0"].iloc[0], atol=1e-13, rtol=0):
            raise ValidationError(f"GZ s_u0 is not constant within U={U:g}")
        anchor = group[group["V"].astype(float).eq(0.0)].iloc[0]
        if not math.isclose(
            float(anchor["s"]), float(anchor["s_u0"]), abs_tol=1e-13, rel_tol=0
        ):
            raise ValidationError(
                f"GZ U={U:g} V=0 slope does not equal its s_u0 anchor"
            )

    campaign_for_merge = campaign[
        [
            "U",
            "V",
            "C_NN",
            "C_NN_spread",
            "C_NN_population_std_diagnostic",
            "C_NN_source",
            "C_NN_sampling",
            "twist_spread_is_standard_error",
        ]
    ]
    c_inputs = pd.concat([campaign_for_merge, controls], ignore_index=True)
    if len(c_inputs) != 16 or c_inputs.duplicated(["U", "V"]).any():
        raise ValidationError(
            "C_NN source merge is not one-to-one over the 16 pointwise cases"
        )
    pointwise = selected.merge(
        c_inputs, on=["U", "V"], how="left", validate="one_to_one"
    )
    if pointwise["C_NN"].isna().any():
        raise ValidationError("At least one GZ point lacks an independent C_NN input")

    pointwise["s_signed_observed"] = -pointwise["s"].astype(float)
    pointwise["s_u0_signed"] = -pointwise["s_u0"].astype(float)
    pointwise["eq10_factor"] = (2.0 * pointwise["U"] - pointwise["V"]) / (
        pointwise["U"] - pointwise["V"]
    )
    pointwise["s_eq10_signed"] = 1.0 + pointwise["eq10_factor"] * (
        2.0 * pointwise["C_NN"] - 0.5
    )
    pointwise["s_axis_anchor_signed"] = axis_anchor_law(
        pointwise["r"].to_numpy(dtype=float),
        pointwise["s_u0_signed"].to_numpy(dtype=float),
    )
    pointwise["eq10_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_eq10_signed"]
    )
    pointwise["axis_anchor_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_axis_anchor_signed"]
    )
    pointwise["abs_residual_reduction_eq10_vs_anchor"] = (
        pointwise["axis_anchor_residual_observed_minus_prediction"].abs()
        - pointwise["eq10_residual_observed_minus_prediction"].abs()
    )
    pointwise["s_eq10_twist_spread_equivalent_diagnostic"] = (
        2.0 * pointwise["eq10_factor"] * pointwise["C_NN_spread"]
    )
    pointwise["finite_V"] = pointwise["V"].astype(float) > 0.0
    pointwise["eq10_convention"] = "signed s_NN in omega_GZ=s_NN epsilon_NN"
    pointwise["residual_convention"] = "observed minus prediction"

    summaries: list[dict[str, object]] = []
    for U, group in pointwise.groupby("U", sort=True):
        for scope, scoped in (
            ("all_points", group),
            ("finite_V_only", group[group["finite_V"]]),
        ):
            eq = scoped["eq10_residual_observed_minus_prediction"].to_numpy(dtype=float)
            anchor = scoped["axis_anchor_residual_observed_minus_prediction"].to_numpy(
                dtype=float
            )
            summaries.append(
                {
                    "U": float(U),
                    "scope": scope,
                    "point_count": len(scoped),
                    "eq10_rmse": float(np.sqrt(np.mean(eq**2))),
                    "eq10_mae": float(np.mean(np.abs(eq))),
                    "eq10_max_abs_residual": float(np.max(np.abs(eq))),
                    "axis_anchor_rmse": float(np.sqrt(np.mean(anchor**2))),
                    "axis_anchor_mae": float(np.mean(np.abs(anchor))),
                    "axis_anchor_max_abs_residual": float(np.max(np.abs(anchor))),
                    "rmse_reduction_eq10_vs_anchor": float(
                        np.sqrt(np.mean(anchor**2)) - np.sqrt(np.mean(eq**2))
                    ),
                }
            )
    finite = pointwise[pointwise["finite_V"]]
    for scope, scoped in (("all_points", pointwise), ("finite_V_only", finite)):
        eq = scoped["eq10_residual_observed_minus_prediction"].to_numpy(dtype=float)
        anchor = scoped["axis_anchor_residual_observed_minus_prediction"].to_numpy(
            dtype=float
        )
        summaries.append(
            {
                "U": "all",
                "scope": scope,
                "point_count": len(scoped),
                "eq10_rmse": float(np.sqrt(np.mean(eq**2))),
                "eq10_mae": float(np.mean(np.abs(eq))),
                "eq10_max_abs_residual": float(np.max(np.abs(eq))),
                "axis_anchor_rmse": float(np.sqrt(np.mean(anchor**2))),
                "axis_anchor_mae": float(np.mean(np.abs(anchor))),
                "axis_anchor_max_abs_residual": float(np.max(np.abs(anchor))),
                "rmse_reduction_eq10_vs_anchor": float(
                    np.sqrt(np.mean(anchor**2)) - np.sqrt(np.mean(eq**2))
                ),
            }
        )
    return pointwise.sort_values(["U", "V"]).reset_index(drop=True), pd.DataFrame(
        summaries
    )


def git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def atomic_write_json(payload: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def main() -> None:
    args = parse_args()
    campaign_root = args.campaign_root.expanduser().resolve()
    manifest_path = (
        (args.manifest or campaign_root / "manifest.tsv").expanduser().resolve()
    )
    raw_dir = (args.raw_dir or campaign_root / "raw").expanduser().resolve()
    provenance_path = (
        (args.provenance or campaign_root / "provenance.json").expanduser().resolve()
    )
    twist_path = (
        (args.twist_panel or campaign_root / "twist_panel.tsv").expanduser().resolve()
    )
    output_dir = args.output_dir.expanduser().resolve()

    if args.identity_tolerance <= 0 or args.u40_panel_bias_tolerance <= 0:
        raise ValidationError("Validation tolerances must be positive")
    validate_output_destination(output_dir)
    manifest = load_and_validate_manifest(manifest_path)
    validate_twist_panel(twist_path)
    campaign_provenance = load_and_validate_campaign_provenance(provenance_path)
    raw = parse_and_validate_outputs(manifest, raw_dir, args.identity_tolerance)
    panel = aggregate_campaign(raw)
    controls, calibration = validate_and_load_u40_controls(
        args.u40_summary.expanduser().resolve(),
        args.u40_rows.expanduser().resolve(),
        args.u40_panel_bias_tolerance,
    )
    pointwise, families = build_pointwise_table(
        panel,
        controls,
        args.gz_points.expanduser().resolve(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {key: output_dir / name for key, name in OUTPUT_BASENAMES.items()}
    atomic_write_csv(raw, output_paths["raw"])
    atomic_write_csv(panel, output_paths["panel"])
    atomic_write_csv(calibration, output_paths["controls"])
    atomic_write_csv(pointwise, output_paths["pointwise"])
    atomic_write_csv(families, output_paths["families"])

    input_paths = {
        "manifest": manifest_path,
        "twist_panel": twist_path,
        "campaign_provenance": provenance_path,
        "u40_summary": args.u40_summary.expanduser().resolve(),
        "u40_rows": args.u40_rows.expanduser().resolve(),
        "gz_points": args.gz_points.expanduser().resolve(),
    }
    output_hashes = {
        output_paths[key].name: sha256(output_paths[key])
        for key in ("raw", "panel", "controls", "pointwise", "families")
    }
    raw_hash_digest = hashlib.sha256(
        "".join(
            f"{row.filename}\t{row.raw_sha256}\n"
            for row in raw.sort_values("filename").itertuples(index=False)
        ).encode()
    ).hexdigest()
    finite_summary = families[
        (families["U"].astype(str) == "all") & (families["scope"] == "finite_V_only")
    ].iloc[0]
    analysis_provenance = {
        "schema_version": SCHEMA_VERSION,
        "data_product": DATA_PRODUCT,
        "C_NN_observable": C_NN_OBSERVABLE,
        "reviewed_manifest_sha256": REVIEWED_MANIFEST_SHA256,
        "created_at": datetime.now().astimezone().isoformat(),
        "purpose": "staging-only downstream analysis; does not update manuscript or figure inputs",
        "analyzer": str(Path(__file__).resolve()),
        "analyzer_sha256": sha256(Path(__file__).resolve()),
        "git_head": git_head(),
        "campaign_root": str(campaign_root),
        "input_files": {
            label: {"path": str(path), "sha256": sha256(path)}
            for label, path in input_paths.items()
        },
        "campaign_pinned_solver": {
            key: campaign_provenance[key]
            for key in ("solver_sha256", "source_sha256", "qbasis_library_sha256")
        },
        "raw_output_inventory": {
            "count": len(raw),
            "ordered_filename_sha256_digest": raw_hash_digest,
            "all_status_complete": bool(raw["status"].eq("COMPLETE").all()),
            "max_abs_identity_residual": float(
                raw[
                    [
                        "energy_identity_residual",
                        "connected_density_identity_residual",
                        "kinetic_identity_residual",
                        "charge_identity_residual",
                    ]
                ]
                .abs()
                .to_numpy()
                .max()
            ),
            "identity_tolerance": args.identity_tolerance,
        },
        "aggregation": {
            "primary_C_NN_estimator": "unweighted arithmetic mean over exact deterministic 25-twist maximin panel",
            "diagnostic_estimator": "exchange-multiplicity-weighted panel mean",
            "twist_spread_is_standard_error": False,
            "campaign_case_count": len(panel),
            "campaign_twists_per_case": 25,
            "u40_control_estimator": "full 861-point wedge, exchange symmetry and trapezoidal endpoints, weight 1600",
            "max_abs_u40_panel_minus_full": float(
                calibration["abs_panel_minus_full"].max()
            ),
            "u40_panel_bias_tolerance": args.u40_panel_bias_tolerance,
        },
        "equations": {
            "signed_convention": "omega_GZ(k)=s_NN epsilon_NN(k)",
            "eq10": "s_NN=1+[(2U-V)/(U-V)](2C_NN-1/2)",
            "axis_anchor_baseline": "s_anchor=[s0-(s0+1)r/2]/(1-r), r=V/U",
            "residual": "signed observed minus signed prediction",
        },
        "pointwise": {
            "count": len(pointwise),
            "campaign_C_NN_points": len(panel),
            "existing_u40_full861_C_NN_points": len(controls),
            "all_C_NN_inputs_independent_of_GZ_slope": True,
            "finite_V_eq10_rmse": float(finite_summary["eq10_rmse"]),
            "finite_V_axis_anchor_rmse": float(finite_summary["axis_anchor_rmse"]),
        },
        "output_files": output_hashes,
        "publication_artifacts_modified": False,
        "methodological_caveat": (
            "The 25 twists form a deterministic quadrature surrogate, not independent random samples. "
            "Their spread and population standard deviation quantify momentum variation, not a sampling "
            "standard error. The U=40 full-861 comparison is an empirical bias calibration, not a proof "
            "of the same bound at every U and V."
        ),
    }
    atomic_write_json(analysis_provenance, output_paths["provenance"])

    print(f"Validated campaign outputs: {len(raw)}/300 COMPLETE")
    print(f"Aggregated campaign cases: {len(panel)}/12")
    print(
        "U=40 panel calibration max |panel-full|: "
        f"{calibration['abs_panel_minus_full'].max():.3e}"
    )
    print(
        "Finite-V RMSE: "
        f"Eq.10={finite_summary['eq10_rmse']:.9g}, "
        f"axis-anchor={finite_summary['axis_anchor_rmse']:.9g}"
    )
    print(f"Staging outputs: {output_dir}")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        raise SystemExit(f"VALIDATION FAILED: {exc}") from exc
