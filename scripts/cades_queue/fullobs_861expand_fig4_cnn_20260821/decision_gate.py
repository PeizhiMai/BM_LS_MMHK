#!/Users/cosdis/.venvs/myenv/bin/python
"""Issue a quantitative decision certificate for the Fig. 4 25→861 expansion.

The gate first runs the frozen, reviewed 25-panel analyzer.  Consequently it
cannot issue any certificate until all 300 source outputs are COMPLETE and the
source manifest, solver provenance, observable identities, U=40 calibration
tables, and GZ-scale table pass their existing strict checks.

An expansion is approved only when the U=40 calibration, conservatively
propagated to the twelve new panels, reaches a fixed absolute tolerance in the
dimensionless Eq. (10) slope or a target quadrature diagnostic leaves the
predeclared calibration envelope.  Eq. (10) residuals are reported separately
as secondary, dimensionally consistent diagnostics.  The energy-unit GZ
curve-fit RMSE is never used in the decision.  The output is advisory and
submission-free; it never invokes Slurm or creates a CADES batch.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent
REPO = SCRIPT.parents[3]
ANALYZER = PACKAGE / "reviewed_analyze_fig4_cnn_campaign.py"

EXPECTED_ANALYZER_SHA256 = (
    "cd6658b8cdd70aed2a597d24ff2b2c1e16fe9b4807dc204e7e8cf1d6a5ba7132"
)
EXPECTED_MANIFEST_SHA256 = (
    "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
)
EXPECTED_PROVENANCE_SHA256 = (
    "844658183e18445ea49a01e71303782307474072c32b3937a5ebb31058bad322"
)
EXPECTED_TWIST_PANEL_SHA256 = (
    "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
)
EXPECTED_U40_ROWS_SHA256 = (
    "81f50b31cffa6581b27f52b9aced792b9d6cacbb64950471594693473194a5d9"
)
EXPECTED_U40_SUMMARY_SHA256 = (
    "81d45fe4ea75dee1e121dcb22963652c2253cf5e45a61094c3e153f98e4dd5e4"
)
EXPECTED_GZ_POINTS_SHA256 = (
    "44755fe1c15efce59903044f31ffa0c794da8d9e85f330f89d3683e6ae609c0a"
)
EXPECTED_WEDGE_SHA256 = (
    "9efc7f43498726d7d1b1119e85bf617b24370aa7b2ff9d5127a85859602ca93e"
)
EXPECTED_COMPLEMENT_SHA256 = (
    "15026c80b25c00db6cc530b8ec03319ddbf0e831887e277764e07f752c3ab572"
)
EXPECTED_CONTRACT_SHA256 = (
    "2f7b898a7670ac96e2f49447e879a2424ce2871c6f4436dcf38c2b4991bbc2c2"
)

EXPECTED_SOLVER_SHA256 = (
    "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
)
EXPECTED_SOURCE_SHA256 = (
    "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
)
EXPECTED_QBASIS_SHA256 = (
    "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
)

EXPECTED_CASES = (
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

# Calibration transfer is deliberately conservative: inflate the largest
# absolute U=40 bias and both empirical diagnostic-to-bias transfers by five.
CALIBRATION_SAFETY_FACTOR = 5.0
# This is half of a 0.001 dimensionless slope reporting/figure increment.  It
# is an operational materiality tolerance, not a statistical confidence bound.
ABS_PROPAGATED_S_TOLERANCE = 5.0e-4
# A target diagnostic is operationally outside the U=40 calibrated domain only
# after it exceeds four times the largest corresponding control diagnostic.
ROUGHNESS_EXIT_MULTIPLIER = 4.0
SYMMETRY_DIAGNOSTIC_EXIT_MULTIPLIER = 4.0

# Deterministic output contract for the hash-pinned U=40 full-861 tables and
# frozen analyzer.  This makes an unexpected calibration drift a refusal
# rather than silently changing the operational expansion decision.
EXPECTED_U40_CALIBRATION = {
    "max_abs_C_NN_panel_minus_full861": 2.6920934537155716e-7,
    "max_abs_bias_to_panel_spread_ratio": 0.008825660518580818,
    "max_abs_bias_to_symmetry_diagnostic_ratio": 0.2683572051938072,
    "max_U40_panel_spread": 5.229141656709624e-5,
    "max_abs_U40_symmetry_weighted_minus_primary": 1.450012748316354e-6,
}
FLOAT_REL_TOL = 1.0e-12
FLOAT_ABS_TOL = 1.0e-15


class GateError(RuntimeError):
    """A hard provenance, validation, or completeness gate failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise GateError(f"Missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise GateError(
            f"{label} SHA-256 mismatch: actual={actual}, expected={expected}"
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_case(U: Any, V: Any) -> tuple[float, float]:
    return round(float(U), 10), round(float(V), 10)


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise GateError("Pearson correlation needs paired samples")
    xmean = sum(xs) / len(xs)
    ymean = sum(ys) / len(ys)
    dx = [value - xmean for value in xs]
    dy = [value - ymean for value in ys]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denominator == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(dx, dy)) / denominator


def campaign_layout(root: Path) -> tuple[Path, Path, Path, Path]:
    root = root.expanduser().resolve()
    metadata = root / "metadata"
    if (metadata / "manifest.tsv").is_file():
        return (
            metadata / "manifest.tsv",
            metadata / "provenance.json",
            metadata / "twist_panel.tsv",
            root / "raw",
        )
    return (
        root / "manifest.tsv",
        root / "provenance.json",
        root / "twist_panel.tsv",
        root / "raw",
    )


def validate_frozen_inputs(
    manifest: Path,
    provenance: Path,
    twist_panel: Path,
    u40_summary: Path,
    u40_rows: Path,
    gz_points: Path,
) -> None:
    checks = (
        (ANALYZER, EXPECTED_ANALYZER_SHA256, "reviewed analyzer"),
        (manifest, EXPECTED_MANIFEST_SHA256, "source 25 manifest"),
        (provenance, EXPECTED_PROVENANCE_SHA256, "source 25 provenance"),
        (twist_panel, EXPECTED_TWIST_PANEL_SHA256, "source 25 twist panel"),
        (u40_summary, EXPECTED_U40_SUMMARY_SHA256, "U40 full-861 summary"),
        (u40_rows, EXPECTED_U40_ROWS_SHA256, "U40 full-861 rows"),
        (gz_points, EXPECTED_GZ_POINTS_SHA256, "GZ scale points"),
        (PACKAGE / "wedge_861.tsv", EXPECTED_WEDGE_SHA256, "861 wedge contract"),
        (
            PACKAGE / "complement_836.tsv",
            EXPECTED_COMPLEMENT_SHA256,
            "836-coordinate complement contract",
        ),
        (PACKAGE / "contract.json", EXPECTED_CONTRACT_SHA256, "package contract"),
    )
    for path, expected, label in checks:
        require_hash(path, expected, label)


def run_analyzer(
    campaign_root: Path,
    manifest: Path,
    provenance: Path,
    twist_panel: Path,
    raw_dir: Path,
    u40_summary: Path,
    u40_rows: Path,
    gz_points: Path,
    output_dir: Path,
) -> None:
    command = [
        sys.executable,
        str(ANALYZER),
        "--campaign-root",
        str(campaign_root),
        "--manifest",
        str(manifest),
        "--provenance",
        str(provenance),
        "--twist-panel",
        str(twist_panel),
        "--raw-dir",
        str(raw_dir),
        "--u40-summary",
        str(u40_summary),
        "--u40-rows",
        str(u40_rows),
        "--gz-points",
        str(gz_points),
        "--identity-tolerance",
        "1e-8",
        "--u40-panel-bias-tolerance",
        "1e-6",
        "--output-dir",
        str(output_dir),
    ]
    proc = subprocess.run(
        command,
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise GateError(
            "Reviewed 25-panel analyzer refused the inputs "
            f"(exit {proc.returncode}).\nstdout:\n{proc.stdout[-5000:]}"
            f"\nstderr:\n{proc.stderr[-5000:]}"
        )


def analyze_decision(analysis_dir: Path) -> dict[str, Any]:
    panel = read_csv(analysis_dir / "fig4_cnn_campaign_panel_summary.csv")
    calibration = read_csv(analysis_dir / "fig4_cnn_u40_panel_calibration.csv")
    pointwise = read_csv(analysis_dir / "fig4_cnn_pointwise_eq10.csv")
    provenance = json.loads(
        (analysis_dir / "fig4_cnn_analysis_provenance.json").read_text()
    )
    if len(panel) != 12 or len(calibration) != 4 or len(pointwise) != 16:
        raise GateError("Reviewed analyzer emitted unexpected table cardinalities")
    if {canonical_case(row["U"], row["V"]) for row in panel} != set(EXPECTED_CASES):
        raise GateError("Panel summary is not the exact twelve-case inventory")
    if not all(row["passes_panel_bias_gate"].lower() == "true" for row in calibration):
        raise GateError("At least one U40 panel/full-861 calibration row failed")

    calibration_values: list[dict[str, float]] = []
    for row in calibration:
        values = {
            "bias": float(row["abs_panel_minus_full"]),
            "spread": float(row["C_NN_panel_spread"]),
            "symmetry": float(
                row["abs_C_NN_symmetry_weighted_minus_primary"]
            ),
        }
        if not all(math.isfinite(value) and value >= 0.0 for value in values.values()):
            raise GateError("U40 calibration contains a non-finite or negative diagnostic")
        calibration_values.append(values)

    max_abs_bias = max(row["bias"] for row in calibration_values)
    max_calibration_spread = max(row["spread"] for row in calibration_values)
    max_calibration_symmetry = max(row["symmetry"] for row in calibration_values)
    spread_ratios = [
        row["bias"] / row["spread"]
        for row in calibration_values
        if row["spread"] > 0.0
    ]
    symmetry_ratios = [
        row["bias"] / row["symmetry"]
        for row in calibration_values
        if row["symmetry"] > 0.0
    ]
    if (
        not spread_ratios
        or not symmetry_ratios
        or max_abs_bias > 1.0e-6
        or max_calibration_spread <= 0.0
        or max_calibration_symmetry <= 0.0
    ):
        raise GateError("U40 calibration is absent or exceeds the reviewed 1e-6 gate")
    max_bias_to_spread = max(spread_ratios)
    max_bias_to_symmetry = max(symmetry_ratios)
    observed_calibration = {
        "max_abs_C_NN_panel_minus_full861": max_abs_bias,
        "max_abs_bias_to_panel_spread_ratio": max_bias_to_spread,
        "max_abs_bias_to_symmetry_diagnostic_ratio": max_bias_to_symmetry,
        "max_U40_panel_spread": max_calibration_spread,
        "max_abs_U40_symmetry_weighted_minus_primary": max_calibration_symmetry,
    }
    for key, expected in EXPECTED_U40_CALIBRATION.items():
        if not math.isclose(
            observed_calibration[key],
            expected,
            rel_tol=FLOAT_REL_TOL,
            abs_tol=FLOAT_ABS_TOL,
        ):
            raise GateError(
                "Hash-pinned U40 calibration drifted unexpectedly: "
                f"{key}={observed_calibration[key]:.17g}, expected={expected:.17g}"
            )

    point_by_case = {
        canonical_case(row["U"], row["V"]): row for row in pointwise
    }
    if len(point_by_case) != len(pointwise):
        raise GateError("Pointwise table contains duplicate (U,V) cases")
    target_metrics: list[dict[str, Any]] = []
    for row in sorted(panel, key=lambda item: (float(item["U"]), float(item["V"]))):
        case = canonical_case(row["U"], row["V"])
        observed = point_by_case.get(case)
        if observed is None:
            raise GateError(f"Pointwise table lacks campaign case {case}")
        spread = float(row["C_NN_spread"])
        symmetry_diagnostic = abs(
            float(row["C_NN_symmetry_weighted_minus_primary"])
        )
        signed_residual = float(
            observed["eq10_residual_observed_minus_prediction"]
        )
        residual = abs(signed_residual)
        if not all(
            math.isfinite(value)
            for value in (spread, symmetry_diagnostic, signed_residual)
        ):
            raise GateError(f"Non-finite decision input at case {case}")
        if spread < 0.0:
            raise GateError(f"Negative C_NN panel spread at case {case}")

        bias_components = {
            "U40_absolute_bias_floor": max_abs_bias,
            "range_scaled_transfer": max_bias_to_spread * spread,
            "symmetry_scaled_transfer": (
                max_bias_to_symmetry * symmetry_diagnostic
            ),
        }
        c_bias_envelope = CALIBRATION_SAFETY_FACTOR * max(
            bias_components.values()
        )
        U, V = case
        eq10_factor = (2.0 * U - V) / (U - V)
        abs_ds_dcnn = abs(2.0 * eq10_factor)
        s_bias_envelope = abs_ds_dcnn * c_bias_envelope
        roughness_ratio = spread / max_calibration_spread
        symmetry_ratio = symmetry_diagnostic / max_calibration_symmetry
        exceeds_s_tolerance = s_bias_envelope >= ABS_PROPAGATED_S_TOLERANCE
        exits_roughness_domain = roughness_ratio > ROUGHNESS_EXIT_MULTIPLIER
        exits_symmetry_domain = (
            symmetry_ratio > SYMMETRY_DIAGNOSTIC_EXIT_MULTIPLIER
        )
        target_metrics.append(
            {
                "U": U,
                "V": V,
                "C_NN_panel_spread": spread,
                "abs_C_NN_symmetry_weighted_minus_primary": symmetry_diagnostic,
                "calibrated_roughness_ratio": roughness_ratio,
                "calibrated_symmetry_diagnostic_ratio": symmetry_ratio,
                "C_NN_bias_components_before_safety_factor": bias_components,
                "conservative_C_NN_bias_envelope": c_bias_envelope,
                "abs_ds_NN_dC_NN": abs_ds_dcnn,
                "conservative_abs_delta_s_NN": s_bias_envelope,
                "exceeds_absolute_s_tolerance": exceeds_s_tolerance,
                "exits_roughness_calibrated_domain": exits_roughness_domain,
                "exits_symmetry_calibrated_domain": exits_symmetry_domain,
                "secondary_eq10_residual_signed_observed_minus_prediction": (
                    signed_residual
                ),
                "secondary_abs_eq10_residual": residual,
                "secondary_abs_delta_s_to_abs_eq10_residual_ratio": (
                    s_bias_envelope / residual if residual > 0.0 else None
                ),
                "eq10_residual_used_for_decision": False,
            }
        )

    slope_exceedances = [
        row for row in target_metrics if row["exceeds_absolute_s_tolerance"]
    ]
    roughness_exits = [
        row for row in target_metrics if row["exits_roughness_calibrated_domain"]
    ]
    symmetry_exits = [
        row for row in target_metrics if row["exits_symmetry_calibrated_domain"]
    ]
    spreads = [float(row["C_NN_panel_spread"]) for row in target_metrics]
    residuals = [float(row["secondary_abs_eq10_residual"]) for row in target_metrics]
    correlation = pearson(spreads, residuals)
    residual_ratios = [
        float(row["secondary_abs_delta_s_to_abs_eq10_residual_ratio"])
        for row in target_metrics
        if row["secondary_abs_delta_s_to_abs_eq10_residual_ratio"] is not None
    ]

    approved = bool(slope_exceedances or roughness_exits or symmetry_exits)
    reasons: list[str] = []
    if slope_exceedances:
        reasons.append(
            f"{len(slope_exceedances)} target(s) reach the fixed 5e-4 "
            "absolute propagated |delta s_NN| tolerance"
        )
    if roughness_exits:
        reasons.append(
            f"{len(roughness_exits)} target(s) leave the 4x U40 panel-range envelope"
        )
    if symmetry_exits:
        reasons.append(
            f"{len(symmetry_exits)} target(s) leave the 4x U40 "
            "symmetry-diagnostic envelope"
        )
    if not reasons:
        reasons.append(
            "all target quadrature diagnostics remain inside the predeclared "
            "calibration envelopes and propagated |delta s_NN| remains below 5e-4"
        )

    return {
        "schema_version": 2,
        "gate_algorithm": "fig4_cnn_25_to_861_quadrature_v2",
        "decision": "APPROVE_EXPANSION" if approved else "NO_EXPANSION",
        "approved": approved,
        "reasons": reasons,
        "thresholds": {
            "calibration_safety_factor": CALIBRATION_SAFETY_FACTOR,
            "absolute_propagated_s_tolerance": ABS_PROPAGATED_S_TOLERANCE,
            "roughness_exit_multiplier": ROUGHNESS_EXIT_MULTIPLIER,
            "symmetry_diagnostic_exit_multiplier": (
                SYMMETRY_DIAGNOSTIC_EXIT_MULTIPLIER
            ),
        },
        "methodology": {
            "decision_observable": "dimensionless signed s_NN",
            "absolute_tolerance_basis": (
                "half of a 0.001 dimensionless slope reporting/figure increment"
            ),
            "calibration_role": (
                "empirical U40 full-861 transfer with a fivefold safety factor"
            ),
            "eq10_residual_role": "secondary dimensionless diagnostic only",
            "eq10_residual_used_for_decision": False,
            "gz_curve_fit_rmse_used_for_decision": False,
            "gz_curve_fit_rmse_exclusion_reason": (
                "energy-unit curve-shape misfit is not uncertainty in dimensionless s_NN"
            ),
        },
        "calibration": {
            "control_count": len(calibration),
            "max_abs_C_NN_panel_minus_full861": max_abs_bias,
            "max_abs_bias_to_panel_spread_ratio": max_bias_to_spread,
            "max_abs_bias_to_symmetry_diagnostic_ratio": max_bias_to_symmetry,
            "max_U40_panel_spread": max_calibration_spread,
            "max_abs_U40_symmetry_weighted_minus_primary": (
                max_calibration_symmetry
            ),
            "empirical_calibration_is_not_a_formal_bound": True,
        },
        "quadrature_diagnostics": {
            "target_count": len(target_metrics),
            "slope_tolerance_exceedance_count": len(slope_exceedances),
            "roughness_calibrated_domain_exit_count": len(roughness_exits),
            "symmetry_calibrated_domain_exit_count": len(symmetry_exits),
            "max_conservative_abs_delta_s_NN": max(
                float(row["conservative_abs_delta_s_NN"])
                for row in target_metrics
            ),
            "max_target_roughness_ratio": max(
                float(row["calibrated_roughness_ratio"])
                for row in target_metrics
            ),
            "max_target_symmetry_diagnostic_ratio": max(
                float(row["calibrated_symmetry_diagnostic_ratio"])
                for row in target_metrics
            ),
        },
        "secondary_eq10_diagnostics": {
            "used_for_decision": False,
            "residual_units": "dimensionless signed s_NN",
            "pearson_panel_spread_vs_abs_eq10_residual": correlation,
            "max_abs_eq10_residual": max(residuals),
            "max_abs_delta_s_to_abs_eq10_residual_ratio": (
                max(residual_ratios) if residual_ratios else None
            ),
        },
        "targets": target_metrics,
        "source_raw_inventory": provenance["raw_output_inventory"],
        "source_pinned_solver": provenance["campaign_pinned_solver"],
    }


def atomic_certificate(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    if os.path.lexists(path):
        raise GateError(f"Refusing to overwrite certificate: {path}")
    if not path.parent.is_dir():
        raise GateError(f"Certificate parent does not exist: {path.parent}")
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary):
        raise GateError(f"Refusing pre-existing temporary path: {temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def evaluate(args: argparse.Namespace, analysis_dir: Path) -> dict[str, Any]:
    campaign_root = args.campaign_root.expanduser().resolve()
    manifest, provenance, twist_panel, raw_dir = campaign_layout(campaign_root)
    if args.manifest:
        manifest = args.manifest.expanduser().resolve()
    if args.provenance:
        provenance = args.provenance.expanduser().resolve()
    if args.twist_panel:
        twist_panel = args.twist_panel.expanduser().resolve()
    if args.raw_dir:
        raw_dir = args.raw_dir.expanduser().resolve()
    u40_summary = args.u40_summary.expanduser().resolve()
    u40_rows = args.u40_rows.expanduser().resolve()
    gz_points = args.gz_points.expanduser().resolve()

    validate_frozen_inputs(
        manifest,
        provenance,
        twist_panel,
        u40_summary,
        u40_rows,
        gz_points,
    )
    run_analyzer(
        campaign_root,
        manifest,
        provenance,
        twist_panel,
        raw_dir,
        u40_summary,
        u40_rows,
        gz_points,
        analysis_dir,
    )
    decision = analyze_decision(analysis_dir)
    decision.update(
        {
            "created_at": dt.datetime.now().astimezone().isoformat(),
            "submission_performed": False,
            "expansion_contract": {
                "cases": [{"U": U, "V": V} for U, V in EXPECTED_CASES],
                "reused_coordinates_per_case": 25,
                "missing_coordinates_per_case": 836,
                "expansion_target_count": 10032,
                "full_coordinates_per_case": 861,
                "wedge_sha256": EXPECTED_WEDGE_SHA256,
                "complement_sha256": EXPECTED_COMPLEMENT_SHA256,
                "package_contract_sha256": EXPECTED_CONTRACT_SHA256,
            },
            "input_sha256": {
                "reviewed_analyzer": EXPECTED_ANALYZER_SHA256,
                "source_manifest": EXPECTED_MANIFEST_SHA256,
                "source_provenance": EXPECTED_PROVENANCE_SHA256,
                "source_twist_panel": EXPECTED_TWIST_PANEL_SHA256,
                "u40_rows": EXPECTED_U40_ROWS_SHA256,
                "u40_summary": EXPECTED_U40_SUMMARY_SHA256,
                "gz_points": EXPECTED_GZ_POINTS_SHA256,
            },
            "expected_runtime_provenance": {
                "solver_sha256": EXPECTED_SOLVER_SHA256,
                "source_sha256": EXPECTED_SOURCE_SHA256,
                "qbasis_library_sha256": EXPECTED_QBASIS_SHA256,
                "locate_E0_lanczos_maxit": 10000,
                "physics": {
                    "Lx": 4,
                    "Ly": 4,
                    "Nup": 8,
                    "Ndn": 8,
                    "Qm": 0,
                    "Qn": 0,
                    "tp": 0,
                },
            },
        }
    )
    return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--twist-panel", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument(
        "--u40-summary",
        type=Path,
        default=REPO / "results" / "fullobs_U40_observable_summary_by_V_20260723_091307.csv",
    )
    parser.add_argument(
        "--u40-rows",
        type=Path,
        default=REPO / "results" / "fullobs_U40_observable_rows_20260723_091307.csv.gz",
    )
    parser.add_argument(
        "--gz-points",
        type=Path,
        default=REPO / "results" / "pnas_scale_rule_points_eta0p05.csv",
    )
    parser.add_argument(
        "--analysis-output-dir",
        type=Path,
        help="Optional fresh directory retaining reviewed-analyzer outputs.",
    )
    parser.add_argument(
        "--certificate",
        type=Path,
        help="Optional new JSON certificate path; existing paths are refused.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.analysis_output_dir:
            analysis_dir = args.analysis_output_dir.expanduser().resolve()
            if os.path.lexists(analysis_dir):
                raise GateError(f"Analysis output path already exists: {analysis_dir}")
            analysis_dir.mkdir(parents=False)
            decision = evaluate(args, analysis_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="fig4_cnn_861_decision_") as temporary:
                decision = evaluate(args, Path(temporary) / "analysis")
        if args.certificate:
            atomic_certificate(args.certificate, decision)
        print(json.dumps(decision, indent=2, sort_keys=True))
        return 0 if decision["approved"] else 3
    except (GateError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
