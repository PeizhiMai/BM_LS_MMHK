#!/usr/bin/env python3
"""Synthetic end-to-end tests for the all-F861 publication analyzer."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fig4_cnn_prediction_input as prediction_input  # noqa: E402
import freeze_fig4_cnn_full861_release as release_freezer  # noqa: E402


SCRIPT = ROOT / "scripts/analyze_fig4_cnn_full861_campaign.py"
PACKAGE = ROOT / "scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821"
GENERATOR_PATH = PACKAGE / "generate_batch.py"
FINALIZER = ROOT / "scripts/cades_queue/finalize_fullobs_861expand_fig4_cnn.py"
CORE_FINALIZER = ROOT / "scripts/cades_queue/finalize_fullobs_25twist_fig4_cnn.py"
MONITOR = ROOT / "scripts/cades_queue/monitor_fullobs_batch.py"
U40_SUMMARY = ROOT / "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv"
U40_ROWS = ROOT / "results/fullobs_U40_observable_rows_20260723_091307.csv.gz"
GZ_POINTS = ROOT / "results/pnas_scale_rule_points_eta0p05.csv"
EXPANSION_MANIFEST_SHA256 = (
    "53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31"
)
EXPANSION_PLAN_SHA256 = (
    "368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("fig4_full861_analysis_test_generator", GENERATOR_PATH)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_output(U: float, V: float, kx: int, ky: int) -> tuple[str, float]:
    phase = 0.071 * kx + 0.113 * ky
    C = -0.34 + 3.0e-4 * math.sin(phase) + 1.5e-4 * (V / U)
    D = 0.008 + 2.0e-5 * (1.0 + math.cos(phase))
    nn = 0.985 + 3.0e-5 * math.sin(phase)
    kinetic_nn = -0.24 + 2.0e-5 * math.cos(phase)
    kinetic_nnn = 0.0
    kinetic = kinetic_nn + kinetic_nnn
    E0 = 16.0 * (kinetic + U * D + 2.0 * V * nn)
    Sc = 0.032
    mcdw = Sc / 16.0
    text = f"""Lx\t4
Ly\t4
tp\t0.000000000000000000e+00
U\t{U:.18e}
V\t{V:.18e}
E0\t{E0:.18e}
Gap\t0.000000000000000000e+00

<nn_NN> {nn:.18e}
<delta_n_delta_n_NN> {nn - 1.0:.18e}
<Kinetic_NN_per_site> {kinetic_nn:.18e}
<Kinetic_NNN_per_site> {kinetic_nnn:.18e}
<Kinetic_per_site> {kinetic:.18e}
<C1_NN> {C:.18e}
Q\t0,0
<nq> 1.000000000000000000e+00
<nq_upnq_dn> 2.500000000000000000e-01
<ni_upni_dn> {D:.18e}
<Spipi> 1.000000000000000000e+00
<Sc_pipi> {Sc:.18e}
<mCDW2_pipi> {mcdw:.18e}
status\tCOMPLETE
"""
    return text, float(f"{C:.18e}")


def quadrature_weight(kx: int, ky: int) -> float:
    return (
        (1.0 if kx == ky else 2.0)
        * (0.5 if kx in (0, 40) else 1.0)
        * (0.5 if ky in (0, 40) else 1.0)
    )


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def decision_certificate(
    source_rows: list[dict],
    source_inventory: list[dict],
    source_digest: str,
) -> dict:
    calibration = dict(GENERATOR.EXPECTED_U40_CALIBRATION)
    max_bias = calibration["max_abs_C_NN_panel_minus_full861"]
    max_bias_to_spread = calibration["max_abs_bias_to_panel_spread_ratio"]
    max_bias_to_symmetry = calibration[
        "max_abs_bias_to_symmetry_diagnostic_ratio"
    ]
    max_spread = calibration["max_U40_panel_spread"]
    max_symmetry = calibration[
        "max_abs_U40_symmetry_weighted_minus_primary"
    ]
    inventory_by_index = {
        int(row["index"]): float(row["C_NN"]) for row in source_inventory
    }
    groups: dict[tuple[float, float], list[tuple[int, int, float]]] = {}
    for row in source_rows:
        case = (float(row["U"]), float(row["V"]))
        groups.setdefault(case, []).append(
            (
                int(row["kx"]),
                int(row["ky"]),
                inventory_by_index[int(row["index"])],
            )
        )

    targets = []
    for (U, V), values in sorted(groups.items()):
        C = [value for _, _, value in values]
        weights = [1.0 if kx == ky else 2.0 for kx, ky, _ in values]
        primary = sum(C) / len(C)
        symmetry_weighted = sum(
            weight * value for weight, value in zip(weights, C)
        ) / sum(weights)
        spread = max(C) - min(C)
        symmetry = abs(symmetry_weighted - primary)
        components = {
            "U40_absolute_bias_floor": max_bias,
            "range_scaled_transfer": max_bias_to_spread * spread,
            "symmetry_scaled_transfer": max_bias_to_symmetry * symmetry,
        }
        C_bias = 5.0 * max(components.values())
        ds_dcnn = abs(2.0 * (2.0 * U - V) / (U - V))
        delta_s = ds_dcnn * C_bias
        roughness = spread / max_spread
        symmetry_ratio = symmetry / max_symmetry
        signed_residual = 0.01
        targets.append(
            {
                "U": U,
                "V": V,
                "C_NN_panel_spread": spread,
                "abs_C_NN_symmetry_weighted_minus_primary": symmetry,
                "calibrated_roughness_ratio": roughness,
                "calibrated_symmetry_diagnostic_ratio": symmetry_ratio,
                "C_NN_bias_components_before_safety_factor": components,
                "conservative_C_NN_bias_envelope": C_bias,
                "abs_ds_NN_dC_NN": ds_dcnn,
                "conservative_abs_delta_s_NN": delta_s,
                "exceeds_absolute_s_tolerance": delta_s >= 5.0e-4,
                "exits_roughness_calibrated_domain": roughness > 4.0,
                "exits_symmetry_calibrated_domain": symmetry_ratio > 4.0,
                "secondary_eq10_residual_signed_observed_minus_prediction": signed_residual,
                "secondary_abs_eq10_residual": abs(signed_residual),
                "secondary_abs_delta_s_to_abs_eq10_residual_ratio": (
                    delta_s / abs(signed_residual)
                ),
                "eq10_residual_used_for_decision": False,
            }
        )

    slope_count = sum(row["exceeds_absolute_s_tolerance"] for row in targets)
    roughness_count = sum(
        row["exits_roughness_calibrated_domain"] for row in targets
    )
    symmetry_count = sum(
        row["exits_symmetry_calibrated_domain"] for row in targets
    )
    if not (slope_count or roughness_count or symmetry_count):
        raise RuntimeError("Synthetic decision fixture does not approve expansion")
    return {
        "schema_version": 2,
        "gate_algorithm": prediction_input.DECISION_GATE_ALGORITHM,
        "decision": "APPROVE_EXPANSION",
        "approved": True,
        "thresholds": {
            "calibration_safety_factor": 5.0,
            "absolute_propagated_s_tolerance": 5.0e-4,
            "roughness_exit_multiplier": 4.0,
            "symmetry_diagnostic_exit_multiplier": 4.0,
        },
        "methodology": {
            "decision_observable": "dimensionless signed s_NN",
            "eq10_residual_used_for_decision": False,
            "gz_curve_fit_rmse_used_for_decision": False,
        },
        "input_sha256": dict(GENERATOR.EXPECTED_DECISION_INPUT_HASHES),
        "expansion_contract": {
            "cases": [
                {"U": float(U), "V": float(V)} for U, V in GENERATOR.PAIRS
            ],
            "reused_coordinates_per_case": 25,
            "missing_coordinates_per_case": 836,
            "expansion_target_count": 10_032,
            "full_coordinates_per_case": 861,
            "wedge_sha256": GENERATOR.EXPECTED_WEDGE_SHA256,
            "complement_sha256": GENERATOR.EXPECTED_COMPLEMENT_SHA256,
            "package_contract_sha256": GENERATOR.EXPECTED_CONTRACT_SHA256,
        },
        "expected_runtime_provenance": {
            "solver_sha256": GENERATOR.EXPECTED_SOLVER_SHA256,
            "source_sha256": GENERATOR.EXPECTED_SOURCE_SHA256,
            "qbasis_library_sha256": GENERATOR.EXPECTED_QBASIS_SHA256,
        },
        "source_pinned_solver": {
            "solver_sha256": GENERATOR.EXPECTED_SOLVER_SHA256,
            "source_sha256": GENERATOR.EXPECTED_SOURCE_SHA256,
            "qbasis_library_sha256": GENERATOR.EXPECTED_QBASIS_SHA256,
        },
        "source_raw_inventory": {
            "count": 300,
            "ordered_filename_sha256_digest": source_digest,
            "all_status_complete": True,
            "max_abs_identity_residual": 0.0,
            "identity_tolerance": 1.0e-8,
        },
        "calibration": {
            "control_count": 4,
            **calibration,
            "empirical_calibration_is_not_a_formal_bound": True,
        },
        "targets": targets,
        "quadrature_diagnostics": {
            "target_count": 12,
            "slope_tolerance_exceedance_count": slope_count,
            "roughness_calibrated_domain_exit_count": roughness_count,
            "symmetry_calibrated_domain_exit_count": symmetry_count,
            "max_conservative_abs_delta_s_NN": max(
                row["conservative_abs_delta_s_NN"] for row in targets
            ),
            "max_target_roughness_ratio": max(
                row["calibrated_roughness_ratio"] for row in targets
            ),
            "max_target_symmetry_diagnostic_ratio": max(
                row["calibrated_symmetry_diagnostic_ratio"] for row in targets
            ),
        },
        "secondary_eq10_diagnostics": {
            "used_for_decision": False,
            "residual_units": "dimensionless signed s_NN",
        },
    }


def make_snapshot_read_only(snapshot: Path) -> None:
    for path in snapshot.rglob("*"):
        if path.is_file():
            relative = path.relative_to(snapshot).as_posix()
            path.chmod(
                0o555
                if relative in prediction_input.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS
                else 0o444
            )
    for path in sorted(
        (candidate for candidate in snapshot.rglob("*") if candidate.is_dir()),
        reverse=True,
    ):
        path.chmod(0o555)
    snapshot.chmod(0o555)


def make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    root.chmod(0o700)
    for current, directory_names, file_names in os.walk(root):
        current_path = Path(current)
        current_path.chmod(0o700)
        for name in directory_names:
            path = current_path / name
            if not path.is_symlink():
                path.chmod(0o700)
        for name in file_names:
            path = current_path / name
            if not path.is_symlink():
                path.chmod(0o600)


@contextmanager
def rewritten_snapshot_files(snapshot: Path, replacements: dict[str, bytes]):
    ledger_path = snapshot / prediction_input.SNAPSHOT_LEDGER_RELATIVE
    original_ledger = ledger_path.read_bytes()
    originals = {
        relative: (snapshot / relative).read_bytes() for relative in replacements
    }

    def install(relative: str, payload: bytes) -> None:
        path = snapshot / relative
        path.chmod(0o600)
        path.write_bytes(payload)
        path.chmod(
            0o555
            if relative in prediction_input.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS
            else 0o444
        )

    try:
        for relative, payload in replacements.items():
            install(relative, payload)
        ledger = pd.read_csv(ledger_path, sep="\t", dtype=str)
        for relative in replacements:
            path = snapshot / relative
            match = ledger["relative_path"].eq(relative)
            if int(match.sum()) != 1:
                raise RuntimeError(f"Fixture ledger lacks exact path {relative}")
            ledger.loc[match, "sha256"] = sha256(path)
            ledger.loc[match, "size_bytes"] = str(path.stat().st_size)
        ledger_path.chmod(0o600)
        ledger.to_csv(ledger_path, sep="\t", index=False)
        ledger_path.chmod(0o444)
        yield
    finally:
        for relative, payload in originals.items():
            install(relative, payload)
        ledger_path.chmod(0o600)
        ledger_path.write_bytes(original_ledger)
        ledger_path.chmod(0o444)


def make_synthetic_snapshot(root: Path) -> Path:
    snapshot = root / "fullobs_861twist_fig4_cnn_20260821"
    metadata = snapshot / "metadata"
    raw_dir = snapshot / "raw"
    local_analysis = snapshot / "analysis"
    remote_analysis = metadata / "analysis"
    reviewed = metadata / "reviewed_inputs"
    for path in (raw_dir, local_analysis, remote_analysis, reviewed):
        path.mkdir(parents=True, exist_ok=True)

    source_path = PACKAGE / "reviewed_inputs/source_25_manifest.tsv"
    shutil.copy2(source_path, reviewed / source_path.name)
    source = GENERATOR.load_source_manifest(source_path)
    _, complement = GENERATOR.load_coordinate_contracts()
    plan = GENERATOR.build_plan(GENERATOR.BASE_DEFAULT, source, complement)
    for row in plan:
        row["template"] = str(
            GENERATOR.BATCH_DEFAULT
            / "templates"
            / (
                f"{GENERATOR.TEMPLATE_PREFIX}{row['index']:05d}_U{row['U']}_"
                f"V{GENERATOR.decimal_tag(row['V'])}_f{row['kx']}x{row['ky']}.sh"
            )
        )
    manifest_path = metadata / "manifest.tsv"
    GENERATOR.write_tsv(manifest_path, plan, list(plan[0]))
    if GENERATOR.sha256(manifest_path) != EXPANSION_MANIFEST_SHA256:
        raise RuntimeError("Synthetic fixture could not reproduce reviewed manifest bytes")

    all_rows: list[dict] = []
    for row in plan:
        all_rows.append({"source": "expansion", **row})
    for row in source:
        all_rows.append({"source": "reused_25", **row})

    raw_records: list[dict] = []
    local_raw_records: list[dict] = []
    reused_records: list[dict] = []
    source_decision_inventory: list[dict] = []
    groups: dict[tuple[int, float], list[tuple[float, float]]] = {}
    for global_index, row in enumerate(all_rows, 1):
        U, V = int(row["U"]), float(row["V"])
        kx, ky = int(row["kx"]), int(row["ky"])
        filename = Path(str(row["result"])).name
        text, C = synthetic_output(U, V, kx, ky)
        path = raw_dir / filename
        path.write_text(text)
        digest = sha256(path)
        size = path.stat().st_size
        raw_records.append(
            {
                "index": global_index,
                "U": U,
                "V": V,
                "kx": kx,
                "ky": ky,
                "filename": filename,
                "size_bytes": size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sha256": digest,
            }
        )
        local_raw_records.append(
            {
                "index": global_index,
                "source_campaign": row["source"],
                "U": U,
                "V": V,
                "kx": kx,
                "ky": ky,
                "C_NN": C,
                "sha256": digest,
            }
        )
        groups.setdefault((U, V), []).append((quadrature_weight(kx, ky), C))
        if row["source"] == "reused_25":
            source_decision_inventory.append(
                {"index": int(row["index"]), "C_NN": C}
            )
            reused_records.append(
                {
                    "source_index": row["index"],
                    "U": row["U"],
                    "V": row["V"],
                    "V_over_U": row["V_over_U"],
                    "expected_phase": row["expected_phase"],
                    "source_twist_index": row["twist_index"],
                    "kx": row["kx"],
                    "ky": row["ky"],
                    "seed": row["seed"],
                    "result": row["result"],
                    "size_bytes": size,
                    "sha256": digest,
                    "state": "reused_complete_25",
                }
            )

    reused_path = metadata / "reused_25.tsv"
    write_tsv(reused_path, reused_records, list(reused_records[0]))
    write_tsv(
        metadata / "remote_results_sha256.tsv",
        raw_records,
        list(raw_records[0]),
    )
    pd.DataFrame(local_raw_records).to_csv(
        local_analysis / "fig4_cnn_full861_raw_validation.csv", index=False
    )

    summaries = []
    for (U, V), values in sorted(groups.items()):
        total = sum(weight for weight, _ in values)
        mean = sum(weight * C for weight, C in values) / total
        std = math.sqrt(sum(weight * (C - mean) ** 2 for weight, C in values) / total)
        factor = (2.0 * U - V) / (U - V)
        summaries.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "complete_wedge": 861,
                "quadrature_weight": total,
                "C_NN_full_861": mean,
                "C_NN_full_quadrature_weighted_population_std": std,
                "s_eq10_signed": 1.0 + factor * (2.0 * mean - 0.5),
            }
        )
    remote_summary = remote_analysis / "fig4_cnn_full861_summary.csv"
    pd.DataFrame(summaries).to_csv(remote_summary, index=False)
    local = pd.DataFrame(summaries)
    local["twist_spread_is_standard_error"] = False
    local.to_csv(local_analysis / "fig4_cnn_full861_summary.csv", index=False)

    source_raw = sorted(
        (row for row in raw_records if int(row["index"]) > 10_032),
        key=lambda row: row["filename"],
    )
    source_digest = hashlib.sha256(
        "".join(f"{row['filename']}\t{row['sha256']}\n" for row in source_raw).encode()
    ).hexdigest()
    decision = decision_certificate(source, source_decision_inventory, source_digest)
    decision_path = metadata / "decision_certificate.json"
    decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    _, verified_decision_sha256 = GENERATOR.validate_decision_certificate(
        decision_path
    )
    source_decision_revalidation = GENERATOR.validate_source_decision_inputs(
        decision,
        source,
        source_decision_inventory,
    )

    remote_tools = metadata / "tools"
    remote_tools.mkdir()
    package_tool_names = (
        "generate_batch.py",
        "decision_gate.py",
        "reviewed_analyze_fig4_cnn_campaign.py",
        "audit_status.py",
        "handoff_receipt.py",
    )
    for name in package_tool_names:
        shutil.copy2(PACKAGE / name, remote_tools / name)
    campaign_provenance = {
        "schema_version": 1,
        "manifest_sha256": EXPANSION_MANIFEST_SHA256,
        "source_manifest_sha256": GENERATOR.EXPECTED_SOURCE_MANIFEST_SHA256,
        "plan_sha256": EXPANSION_PLAN_SHA256,
        "wedge_sha256": GENERATOR.EXPECTED_WEDGE_SHA256,
        "source_result_inventory_digest": source_digest,
        "decision_certificate_sha256": verified_decision_sha256,
        "decision_gate_algorithm": prediction_input.DECISION_GATE_ALGORITHM,
        "source_decision_revalidation": source_decision_revalidation,
        "solver_sha256": GENERATOR.EXPECTED_SOLVER_SHA256,
        "source_sha256": GENERATOR.EXPECTED_SOURCE_SHA256,
        "qbasis_library_sha256": GENERATOR.EXPECTED_QBASIS_SHA256,
        "reused_total": 300,
        "expansion_total": 10_032,
        "combined_total": 10_332,
        "full_coordinates_per_case": 861,
        "pairs": [
            {"U": U, "V": V, "V_over_U": float(V) / U}
            for U, V in GENERATOR.PAIRS
        ],
        "package_tools_sha256": {
            name: sha256(remote_tools / name) for name in package_tool_names
        },
    }
    (metadata / "provenance.json").write_text(
        json.dumps(campaign_provenance, indent=2) + "\n"
    )
    snapshot_provenance = {
        "schema_version": 1,
        "immutable_add_only": True,
        "expansion_targets": 10_032,
        "reused_targets": 300,
        "combined_targets": 10_332,
        "manifest_sha256": EXPANSION_MANIFEST_SHA256,
        "plan_sha256": EXPANSION_PLAN_SHA256,
        "solver_sha256": GENERATOR.EXPECTED_SOLVER_SHA256,
        "source_sha256": GENERATOR.EXPECTED_SOURCE_SHA256,
        "qbasis_library_sha256": GENERATOR.EXPECTED_QBASIS_SHA256,
        "local_monitor_sha256": sha256(MONITOR),
        "finalizer_sha256": sha256(FINALIZER),
        "core_finalizer_sha256": sha256(CORE_FINALIZER),
        "validation": {
            "remote_counts": {"COMPLETE": 10_032},
            "local_counts": {"COMPLETE": 10_332},
            "remote_activity": {},
        },
    }
    (metadata / "snapshot_provenance.json").write_text(
        json.dumps(snapshot_provenance, indent=2) + "\n"
    )
    remote_provenance = {
        "schema_version": 1,
        "data_product": "fig4_cnn_full861_direct_fullobs_C_NN_eq10",
        "combined_raw_output_count": 10_332,
        "case_count": 12,
        "coordinates_per_case": 861,
        "quadrature_weight_per_case": 1600.0,
        "C_NN_observable": "<C1_NN>",
        "spread_is_standard_error": False,
        "manifest_sha256": sha256(manifest_path),
        "reused_25_sha256": sha256(reused_path),
        "summary_sha256": sha256(remote_summary),
    }
    (remote_analysis / "fig4_cnn_full861_provenance.json").write_text(
        json.dumps(remote_provenance, indent=2) + "\n"
    )

    tools = metadata / "local_tools"
    tools.mkdir()
    for tool in (MONITOR, FINALIZER, CORE_FINALIZER):
        shutil.copy2(tool, tools / tool.name)
    (snapshot / "README.md").write_text(
        "# Synthetic immutable full-861 snapshot contract fixture\n"
    )
    ledger_path = metadata / "snapshot_file_sha256.tsv"
    ledger_rows = []
    for path in sorted(candidate for candidate in snapshot.rglob("*") if candidate.is_file()):
        if path == ledger_path:
            continue
        ledger_rows.append(
            {
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "relative_path": path.relative_to(snapshot).as_posix(),
            }
        )
    write_tsv(
        ledger_path,
        ledger_rows,
        ["sha256", "size_bytes", "relative_path"],
    )
    make_snapshot_read_only(snapshot)
    return snapshot


class Full861AnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="fig4_cnn_full861_analyzer_test_")
        cls.work = Path(cls.temp.name)
        cls.snapshot = make_synthetic_snapshot(cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        make_tree_writable(cls.snapshot)
        durable_root = cls.work / "durable_results"
        if durable_root.is_dir():
            for release in durable_root.iterdir():
                if release.is_dir():
                    release.chmod(0o700)
                    for path in release.iterdir():
                        path.chmod(0o600)
        cls.temp.cleanup()

    def command(self, output: Path) -> list[str]:
        return [
            sys.executable,
            str(SCRIPT),
            "--snapshot-root",
            str(self.snapshot),
            "--u40-summary",
            str(U40_SUMMARY),
            "--u40-rows",
            str(U40_ROWS),
            "--gz-points",
            str(GZ_POINTS),
            "--output-dir",
            str(output),
        ]

    def test_end_to_end_all_f861_bundle_and_exact_u40_regression(self) -> None:
        output = self.work / (
            release_freezer.CANDIDATE_PREFIX + "synthetic_end_to_end"
        )
        result = subprocess.run(
            self.command(output),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("10332/10332 COMPLETE and hash-matched", result.stdout)
        raw = pd.read_csv(output / "fig4_cnn_full861_campaign_raw_validation.csv")
        campaign = pd.read_csv(output / "fig4_cnn_full861_campaign_summary.csv")
        controls = pd.read_csv(output / "fig4_cnn_full861_u40_control_summary.csv")
        pointwise = pd.read_csv(output / "fig4_cnn_pointwise_eq10.csv")
        provenance = json.loads(
            (output / "fig4_cnn_analysis_provenance.json").read_text()
        )
        self.assertEqual((len(raw), len(campaign), len(controls), len(pointwise)), (10_332, 12, 4, 16))
        self.assertEqual(pointwise["C_NN_fidelity"].value_counts().to_dict(), {"F861": 16})
        self.assertEqual(
            pointwise["C_NN_sampling"].value_counts().to_dict(),
            {"full_861_wedge_exchange_trapezoidal_weight_1600": 16},
        )
        self.assertTrue(pointwise["C_NN_full_wedge_rows"].eq(861).all())
        self.assertTrue(pointwise["C_NN_quadrature_weight"].eq(1600.0).all())
        self.assertEqual(
            pointwise["C_NN_source"].value_counts().to_dict(),
            {
                "fullobs F861 expansion (25 reused + 836 complement)": 12,
                "fullobs F861 existing U=40 control": 4,
            },
        )
        u40_v8 = pointwise[(pointwise["U"] == 40.0) & (pointwise["V"] == 8.0)].iloc[0]
        self.assertAlmostEqual(u40_v8["s_eq10_signed"], -1.681755579831535, places=13)
        self.assertEqual(provenance["schema_version"], 3)
        self.assertEqual(
            provenance["data_product"],
            "fig4_pointwise_full861_direct_fullobs_C_NN_eq10",
        )
        self.assertEqual(provenance["raw_output_inventory"]["count"], 10_332)
        self.assertEqual(
            provenance["decision_certificate_sha256"],
            sha256(self.snapshot / "metadata/decision_certificate.json"),
        )
        self.assertEqual(
            provenance["decision_gate_algorithm"],
            prediction_input.DECISION_GATE_ALGORITHM,
        )
        self.assertTrue(
            provenance["expansion_decision"][
                "all_decision_driving_target_metrics_match_source_bytes"
            ]
        )
        self.assertTrue(provenance["snapshot"]["remote_local_analysis_agreement"])
        self.assertFalse(provenance["publication_artifacts_modified"])

        provenance_path = output / "fig4_cnn_analysis_provenance.json"
        original_provenance = provenance_path.read_bytes()
        for label, mutate, expected_message in (
            (
                "missing_revalidation_field",
                lambda payload: payload["expansion_decision"].pop("case_count"),
                "exact approved expansion decision",
            ),
            (
                "tampered_revalidation_digest",
                lambda payload: payload["expansion_decision"].__setitem__(
                    "source_decision_inputs_sha256", "0" * 64
                ),
                "differs from campaign provenance",
            ),
        ):
            with self.subTest(provenance_contract=label):
                tampered_provenance = json.loads(original_provenance)
                mutate(tampered_provenance)
                provenance_path.write_text(
                    json.dumps(tampered_provenance, indent=2, sort_keys=True) + "\n"
                )
                try:
                    with (
                        mock.patch.object(
                            prediction_input,
                            "REVIEWED_SNAPSHOT_ROOT",
                            self.snapshot,
                        ),
                        self.assertRaisesRegex(
                            prediction_input.PointwisePredictionError,
                            expected_message,
                        ),
                    ):
                        prediction_input.load_validated_fullobs_eq10_bundle(
                            output,
                            scale_points_path=GZ_POINTS,
                        )
                finally:
                    provenance_path.write_bytes(original_provenance)

        durable_root = self.work / "durable_results"
        durable_root.mkdir()
        durable_release = durable_root / (
            release_freezer.RELEASE_PREFIX + "synthetic_end_to_end"
        )
        with (
            mock.patch.object(
                prediction_input,
                "REVIEWED_SNAPSHOT_ROOT",
                self.snapshot,
            ),
            mock.patch.object(release_freezer, "TMP_ROOT", self.work),
            mock.patch.object(release_freezer, "RESULTS_ROOT", durable_root),
        ):
            release_freezer.freeze_full861_publication_bundle(
                candidate_dir=output,
                release_dir=durable_release,
                scale_points_path=GZ_POINTS,
            )
            bundle = prediction_input.load_validated_fullobs_eq10_bundle(
                durable_release,
                scale_points_path=GZ_POINTS,
            )
        self.assertEqual(len(bundle.rows), 16)
        self.assertEqual(
            {path.name for path in durable_release.iterdir()},
            {
                *release_freezer.ANALYSIS_BASENAMES,
                release_freezer.RELEASE_MANIFEST_BASENAME,
            },
        )
        for basename in release_freezer.ANALYSIS_BASENAMES:
            self.assertEqual(
                (durable_release / basename).read_bytes(),
                (output / basename).read_bytes(),
            )

        raw_path = next((self.snapshot / "raw").glob("*_obs.dat"))
        original_raw = raw_path.read_bytes()
        raw_path.chmod(0o600)
        raw_path.write_bytes(original_raw + b"\n")
        raw_path.chmod(0o444)
        try:
            with (
                mock.patch.object(
                    prediction_input,
                    "REVIEWED_SNAPSHOT_ROOT",
                    self.snapshot,
                ),
                self.assertRaisesRegex(
                    prediction_input.PointwisePredictionError,
                    "finalizer ledger",
                ),
            ):
                prediction_input.load_validated_fullobs_eq10_bundle(
                    durable_release,
                    scale_points_path=GZ_POINTS,
                )
        finally:
            raw_path.chmod(0o600)
            raw_path.write_bytes(original_raw)
            raw_path.chmod(0o444)

        linked_snapshot_root = self.work / "loader_linked_snapshot_root"
        linked_snapshot_root.symlink_to(self.snapshot, target_is_directory=True)
        try:
            with (
                mock.patch.object(
                    prediction_input,
                    "REVIEWED_SNAPSHOT_ROOT",
                    linked_snapshot_root,
                ),
                self.assertRaisesRegex(
                    prediction_input.PointwisePredictionError,
                    "snapshot root must not be a symlink",
                ),
            ):
                prediction_input.load_validated_fullobs_eq10_bundle(
                    durable_release,
                    scale_points_path=GZ_POINTS,
                )
        finally:
            linked_snapshot_root.unlink()

    def test_decision_certificate_missing_tampered_and_no_are_refused(self) -> None:
        certificate_path = self.snapshot / "metadata/decision_certificate.json"
        campaign_path = self.snapshot / "metadata/provenance.json"

        certificate_bytes = certificate_path.read_bytes()
        certificate_path.parent.chmod(0o755)
        certificate_path.unlink()
        certificate_path.parent.chmod(0o555)
        try:
            output = self.work / "analysis_missing_decision_certificate"
            result = subprocess.run(
                self.command(output),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Immutable snapshot file inventory differs",
                result.stdout + result.stderr,
            )
            self.assertFalse(output.exists())
        finally:
            certificate_path.parent.chmod(0o755)
            certificate_path.write_bytes(certificate_bytes)
            certificate_path.chmod(0o444)
            certificate_path.parent.chmod(0o555)

        for label, mutate, expected_message in (
            (
                "tampered",
                lambda payload: payload["targets"][0].__setitem__(
                    "conservative_C_NN_bias_envelope",
                    payload["targets"][0]["conservative_C_NN_bias_envelope"]
                    + 1.0e-5,
                ),
                "Archived expansion decision verifier refused",
            ),
            (
                "no_expansion",
                lambda payload: (
                    payload.__setitem__("decision", "NO_EXPANSION"),
                    payload.__setitem__("approved", False),
                ),
                "does not approve expansion",
            ),
        ):
            with self.subTest(label=label):
                certificate = json.loads(certificate_bytes)
                mutate(certificate)
                replacement_certificate = (
                    json.dumps(certificate, indent=2, sort_keys=True) + "\n"
                ).encode()
                campaign = json.loads(campaign_path.read_text())
                campaign["decision_certificate_sha256"] = hashlib.sha256(
                    replacement_certificate
                ).hexdigest()
                replacement_campaign = (
                    json.dumps(campaign, indent=2, sort_keys=True) + "\n"
                ).encode()
                with rewritten_snapshot_files(
                    self.snapshot,
                    {
                        "metadata/decision_certificate.json": replacement_certificate,
                        "metadata/provenance.json": replacement_campaign,
                    },
                ):
                    output = self.work / f"analysis_decision_{label}"
                    result = subprocess.run(
                        self.command(output),
                        cwd=ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected_message, result.stdout + result.stderr)
                    self.assertFalse(output.exists())

    def test_snapshot_root_directory_file_modes_and_symlinks_are_refused(self) -> None:
        mode_cases = (
            (self.snapshot, 0o755, "directory mode must be exactly 0555"),
            (
                self.snapshot / "metadata",
                0o755,
                "directory mode must be exactly 0555",
            ),
            (
                self.snapshot / "metadata/decision_certificate.json",
                0o644,
                "file mode differs from the reviewed finalizer",
            ),
        )
        for index, (path, wrong_mode, expected_message) in enumerate(mode_cases):
            with self.subTest(path=path):
                correct_mode = path.stat().st_mode & 0o777
                path.chmod(wrong_mode)
                try:
                    output = self.work / f"analysis_wrong_snapshot_mode_{index}"
                    result = subprocess.run(
                        self.command(output),
                        cwd=ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected_message, result.stdout + result.stderr)
                    self.assertFalse(output.exists())
                finally:
                    path.chmod(correct_mode)

        metadata = self.snapshot / "metadata"
        linked = metadata / "linked_decision_certificate.json"
        metadata.chmod(0o755)
        linked.symlink_to("decision_certificate.json")
        metadata.chmod(0o555)
        try:
            output = self.work / "analysis_linked_snapshot_entry"
            result = subprocess.run(
                self.command(output),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("contains a symlink", result.stdout + result.stderr)
            self.assertFalse(output.exists())
        finally:
            metadata.chmod(0o755)
            linked.unlink()
            metadata.chmod(0o555)

        linked_root = self.work / "linked_full861_snapshot"
        linked_root.symlink_to(self.snapshot, target_is_directory=True)
        try:
            output = self.work / "analysis_linked_snapshot_root"
            command = self.command(output)
            command[command.index(str(self.snapshot))] = str(linked_root)
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("root must not be a symlink", result.stdout + result.stderr)
            self.assertFalse(output.exists())
        finally:
            linked_root.unlink()

    def test_missing_raw_and_nonreviewed_tolerance_refuse_without_output(self) -> None:
        raw = next((self.snapshot / "raw").glob("*_obs.dat"))
        held = raw.with_suffix(raw.suffix + ".held")
        raw.parent.chmod(0o755)
        raw.rename(held)
        raw.parent.chmod(0o555)
        try:
            output = self.work / "analysis_missing_raw"
            result = subprocess.run(
                self.command(output),
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Immutable snapshot file inventory differs",
                result.stdout + result.stderr,
            )
            self.assertFalse(output.exists())
        finally:
            raw.parent.chmod(0o755)
            held.rename(raw)
            raw.parent.chmod(0o555)

        output = self.work / "analysis_wrong_tolerance"
        command = self.command(output) + ["--identity-tolerance", "1e-7"]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact identity tolerance 1e-8", result.stdout + result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
