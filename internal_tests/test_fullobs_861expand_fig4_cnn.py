"""Contract and decision tests for the conditional Fig. 4 25→861 package."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
PACKAGE = (
    REPO
    / "scripts"
    / "cades_queue"
    / "fullobs_861expand_fig4_cnn_20260821"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("fig4_cnn_861_generator_test", PACKAGE / "generate_batch.py")
DECISION = load_module("fig4_cnn_861_decision_test", PACKAGE / "decision_gate.py")
ANALYZER = load_module(
    "fig4_cnn_861_reviewed_analyzer_test",
    PACKAGE / "reviewed_analyze_fig4_cnn_campaign.py",
)
RECEIPT = load_module("fig4_cnn_861_handoff_receipt_test", PACKAGE / "handoff_receipt.py")


def synthetic_complete_output(U: float, V: float, kx: int, ky: int) -> str:
    """Return a physically consistent COMPLETE full-observable fixture."""
    phase = 0.17 * kx + 0.11 * ky
    C = -0.34 + 7.0e-6 * math.sin(phase) + 1.5e-4 * (V / U)
    D = 0.008 + 2.0e-5 * (1.0 + math.cos(phase))
    nn = 0.985 + 3.0e-5 * math.sin(phase)
    kinetic_nn = -0.24 + 2.0e-5 * math.cos(phase)
    kinetic_nnn = 0.0
    kinetic = kinetic_nn + kinetic_nnn
    E0 = 16.0 * (kinetic + U * D + 2.0 * V * nn)
    Sc = 0.032
    mcdw = Sc / 16.0
    return f"""Lx\t4
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


class CoordinateAndHashContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_manifest = (
            PACKAGE / "reviewed_inputs" / "source_25_manifest.tsv"
        )
        self.source_rows = GENERATOR.load_source_manifest(self.source_manifest)
        self.wedge, self.complement = GENERATOR.load_coordinate_contracts()

    def test_exact_cardinality_disjointness_and_plan_digest(self) -> None:
        self.assertEqual(len(self.wedge), 861)
        self.assertEqual(len(set(self.wedge)), 861)
        self.assertEqual(len(self.complement), 836)
        self.assertEqual(len(set(self.complement)), 836)
        reused = GENERATOR.source_twists()
        self.assertEqual(len(reused), 25)
        self.assertTrue(reused.isdisjoint(self.complement))
        self.assertEqual(reused | set(self.complement), set(self.wedge))

        plan = GENERATOR.build_plan(
            GENERATOR.BASE_DEFAULT,
            self.source_rows,
            self.complement,
        )
        self.assertEqual(len(plan), 10_032)
        counts = {}
        for row in plan:
            key = (row["U"], row["V"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(set(counts.values()), {836})
        self.assertEqual(len({row["seed"] for row in plan}), 10_032)
        self.assertFalse(
            {row["seed"] for row in plan}
            & {int(row["seed"]) for row in self.source_rows}
        )
        self.assertEqual(
            GENERATOR.plan_digest(plan),
            "368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e",
        )

    def test_coordinate_collision_is_refused(self) -> None:
        reused = GENERATOR.source_twists()
        colliding = list(self.complement)
        colliding[0] = next(iter(reused))
        with self.assertRaises(GENERATOR.Refusal):
            GENERATOR.validate_coordinate_contract(reused, self.wedge, colliding)

    def test_pinned_hashes_match_reviewed_files(self) -> None:
        checks = (
            (
                self.source_manifest,
                GENERATOR.EXPECTED_SOURCE_MANIFEST_SHA256,
            ),
            (
                PACKAGE / "reviewed_inputs" / "source_25_twist_panel.tsv",
                GENERATOR.EXPECTED_SOURCE_PANEL_SHA256,
            ),
            (
                PACKAGE / "reviewed_inputs" / "source_25_provenance.json",
                GENERATOR.EXPECTED_SOURCE_PROVENANCE_SHA256,
            ),
            (PACKAGE / "wedge_861.tsv", GENERATOR.EXPECTED_WEDGE_SHA256),
            (
                PACKAGE / "complement_836.tsv",
                GENERATOR.EXPECTED_COMPLEMENT_SHA256,
            ),
            (
                PACKAGE / "reviewed_analyze_fig4_cnn_campaign.py",
                DECISION.EXPECTED_ANALYZER_SHA256,
            ),
            (PACKAGE / "contract.json", GENERATOR.EXPECTED_CONTRACT_SHA256),
            (
                PACKAGE / "audit_status.py",
                GENERATOR.EXPECTED_AUDIT_STATUS_SHA256,
            ),
            (
                PACKAGE / "handoff_receipt.py",
                GENERATOR.EXPECTED_HANDOFF_RECEIPT_SHA256,
            ),
        )
        for path, expected in checks:
            with self.subTest(path=path.name):
                self.assertEqual(GENERATOR.sha256(path), expected)

        contract = json.loads((PACKAGE / "contract.json").read_text())
        self.assertEqual(contract["schema_version"], 5)
        self.assertEqual(
            contract["decision_gate"]["exact_u40_calibration"],
            GENERATOR.EXPECTED_U40_CALIBRATION,
        )
        self.assertEqual(
            GENERATOR.EXPECTED_U40_CALIBRATION,
            DECISION.EXPECTED_U40_CALIBRATION,
        )
        self.assertTrue(
            contract["decision_gate"][
                "materialization_rederives_target_metrics_from_exact_300_raw_bytes"
            ]
        )
        self.assertTrue(
            contract["materialization_integrity"][
                "submit_helper_runs_preflight_before_every_sbatch_call"
            ]
        )
        self.assertTrue(
            contract["materialization_integrity"][
                "template_atomically_claimed_before_sbatch"
            ]
        )
        self.assertTrue(
            contract["materialization_integrity"][
                "materialized_preflight_verifies_both_audit_tool_copies"
            ]
        )
        for key in (
            "handoff_policy_state_and_receipts_exclusive_fsync_mode_0444",
            "rebalance_policy_inputs_outputs_recomputed_before_heartbeat",
            "rebalance_selection_interleaved_across_physics_cases",
            "submission_ledger_records_kind_action_id_and_selection_rank",
            "terminal_receipt_binds_selected_manifest_indices_and_slurm_job_ids",
            "terminal_receipt_records_explicit_allowed_refill_accounts",
        ):
            with self.subTest(materialization_integrity=key):
                self.assertTrue(contract["materialization_integrity"][key])
        self.assertEqual(
            contract["materialization_integrity"][
                "handoff_receipt_schema_version"
            ],
            2,
        )
        self.assertTrue(
            contract["handoff"][
                "finalizer_requires_no_claims_and_zero_exact_name_activity_pre_and_post_transfer"
            ]
        )
        self.assertTrue(
            contract["handoff"][
                "standing_user_authorization_conditioned_on_valid_approve_certificate"
            ]
        )

        ledger = PACKAGE / "PACKAGE_SHA256SUMS"
        listed = {}
        for line in ledger.read_text().splitlines():
            digest, relative = line.split("  ", 1)
            listed[relative] = digest
        expected_files = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and path != ledger
            and "__pycache__" not in path.parts
        }
        self.assertEqual(set(listed), expected_files)
        self.assertEqual(
            listed["audit_status.py"], GENERATOR.EXPECTED_AUDIT_STATUS_SHA256
        )
        for relative, expected in listed.items():
            with self.subTest(ledger_path=relative):
                self.assertEqual(GENERATOR.sha256(PACKAGE / relative), expected)

        handoff = (PACKAGE / "HANDOFF.md").read_text()
        self.assertNotIn("rm -f /tmp/f4cnn861x_", handoff)
        self.assertIn("unlink /tmp/f4cnn861x_dryrun_$$.json", handoff)
        self.assertIn("unlink /tmp/f4cnn861x_cert_$$.json", handoff)
        for block in re.findall(r"```bash\n(.*?)```", handoff, re.DOTALL):
            syntax = subprocess.run(
                ["bash", "-n"],
                input=block,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(syntax.returncode, 0, msg=syntax.stderr)

    def test_u40_calibration_emits_both_quadrature_diagnostics(self) -> None:
        controls, calibration = ANALYZER.validate_and_load_u40_controls(
            REPO
            / "results"
            / "fullobs_U40_observable_summary_by_V_20260723_091307.csv",
            REPO
            / "results"
            / "fullobs_U40_observable_rows_20260723_091307.csv.gz",
            1.0e-6,
        )
        self.assertEqual(len(controls), 4)
        self.assertEqual(len(calibration), 4)
        self.assertIn(
            "abs_C_NN_symmetry_weighted_minus_primary", calibration.columns
        )
        self.assertAlmostEqual(
            calibration[
                "abs_C_NN_symmetry_weighted_minus_primary"
            ].max(),
            1.4500127483163538e-6,
            places=16,
        )

    def test_decision_cli_runs_frozen_analyzer_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_e2e_test_") as temporary:
            root = Path(temporary)
            campaign = root / "campaign"
            raw = campaign / "raw"
            raw.mkdir(parents=True)
            for name in (
                "source_25_manifest.tsv",
                "source_25_provenance.json",
                "source_25_twist_panel.tsv",
            ):
                destination = {
                    "source_25_manifest.tsv": "manifest.tsv",
                    "source_25_provenance.json": "provenance.json",
                    "source_25_twist_panel.tsv": "twist_panel.tsv",
                }[name]
                shutil.copy2(
                    PACKAGE / "reviewed_inputs" / name,
                    campaign / destination,
                )
            for row in self.source_rows:
                result = raw / Path(row["result"]).name
                result.write_text(
                    synthetic_complete_output(
                        float(row["U"]),
                        float(row["V"]),
                        int(row["kx"]),
                        int(row["ky"]),
                    )
                )

            analysis = root / "analysis"
            certificate = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "decision_gate.py"),
                    "--campaign-root",
                    str(campaign),
                    "--analysis-output-dir",
                    str(analysis),
                    "--certificate",
                    str(certificate),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, msg=proc.stdout + proc.stderr)
            payload = json.loads(certificate.read_text())
            self.assertEqual(payload["decision"], "NO_EXPANSION")
            self.assertFalse(payload["approved"])
            self.assertFalse(
                payload["methodology"]["gz_curve_fit_rmse_used_for_decision"]
            )
            self.assertEqual(len(payload["targets"]), 12)
            with (
                analysis / "fig4_cnn_u40_panel_calibration.csv"
            ).open(newline="") as handle:
                fieldnames = csv.DictReader(handle).fieldnames
            self.assertIn(
                "abs_C_NN_symmetry_weighted_minus_primary", fieldnames
            )

    def test_default_cli_is_write_free_dry_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_cli_test_") as temporary:
            nonexistent_batch = Path(temporary) / "must_not_be_created"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "generate_batch.py"),
                    "--batch",
                    str(nonexistent_batch),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["mode"], "DRY_RUN_ONLY")
            self.assertFalse(payload["submission_performed"])
            self.assertEqual(payload["expansion_total"], 10_032)
            self.assertFalse(nonexistent_batch.exists())

    def test_materialization_without_certificate_is_refused_before_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_materialize_test_") as temporary:
            batch = Path(temporary) / "must_not_be_created"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "generate_batch.py"),
                    "--materialize",
                    "--batch",
                    str(batch),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("requires --decision-certificate", proc.stderr)
            self.assertFalse(batch.exists())

    def test_verify_certificate_mode_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_verify_cert_") as temporary:
            root = Path(temporary)
            certificate = root / "approved.json"
            certificate.write_text(
                json.dumps(QuantitativeDecisionTests().valid_certificate())
            )
            nonexistent_batch = root / "must_not_be_created"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "generate_batch.py"),
                    "--verify-certificate",
                    "--decision-certificate",
                    str(certificate),
                    "--batch",
                    str(nonexistent_batch),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["mode"], "VERIFY_CERTIFICATE_ONLY")
            self.assertEqual(payload["decision"], "APPROVE_EXPANSION")
            self.assertFalse(payload["submission_performed"])
            self.assertFalse(nonexistent_batch.exists())

    def test_materialization_exception_removes_incomplete_batch(self) -> None:
        source_rows = GENERATOR.load_source_manifest(
            PACKAGE / "reviewed_inputs" / "source_25_manifest.tsv"
        )
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_transaction_") as temporary:
            root = Path(temporary)
            batch = root / "batch"
            with (
                mock.patch.object(
                    GENERATOR,
                    "validate_decision_certificate",
                    return_value=(
                        {
                            "source_raw_inventory": {
                                "ordered_filename_sha256_digest": "a" * 64
                            }
                        },
                        "b" * 64,
                    ),
                ),
                mock.patch.object(GENERATOR, "require_hash"),
                mock.patch.object(GENERATOR, "active_source_jobs", return_value=[]),
                mock.patch.object(
                    GENERATOR, "load_source_manifest", return_value=source_rows
                ),
                mock.patch.object(
                    GENERATOR, "validate_source_results", return_value=[]
                ),
                mock.patch.object(
                    GENERATOR,
                    "validate_source_decision_inputs",
                    return_value={},
                ),
                mock.patch.object(
                    GENERATOR,
                    "_materialize_created_tree",
                    side_effect=RuntimeError("injected materialization failure"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "injected materialization failure"
                ):
                    GENERATOR.materialize(
                        base=root / "base",
                        source_batch=root / "source_batch",
                        batch=batch,
                        solver=root / "solver",
                        source=root / "source",
                        qbasis=root / "libqbasis.so",
                        certificate_path=root / "certificate.json",
                    )
            self.assertFalse(batch.exists())

    def test_rendered_template_and_utilities_are_syntactically_valid(self) -> None:
        plan = GENERATOR.build_plan(
            GENERATOR.BASE_DEFAULT,
            self.source_rows,
            self.complement,
        )
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_render_test_") as temporary:
            root = Path(temporary)
            template = root / "template.sh"
            template.write_text(
                GENERATOR.template_text(
                    plan[0],
                    root / "batch",
                    root / "base",
                    root / "solver",
                    root / "libqbasis.so",
                )
            )
            syntax = subprocess.run(
                ["bash", "-n", str(template)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(syntax.returncode, 0, msg=syntax.stderr)
            utilities = {
                "submit_fill.py": GENERATOR.submit_helper_text(
                    root / "batch",
                    "c" * 64,
                    "d" * 64,
                    "e" * 64,
                    "f" * 64,
                    "a" * 64,
                ),
                "status.py": GENERATOR.status_text(root / "batch"),
                "preflight.py": GENERATOR.preflight_text(
                    root / "batch",
                    "c" * 64,
                    "d" * 64,
                    "e" * 64,
                    "f" * 64,
                ),
                "analyze.py": GENERATOR.analyze_text(root / "batch"),
            }
            for name, source in utilities.items():
                with self.subTest(name=name):
                    compile(source, name, "exec")
            self.assertIn("PREFLIGHT REFUSED BEFORE SBATCH", utilities["submit_fill.py"])
            self.assertIn("selected template content hash mismatch", utilities["submit_fill.py"])
            self.assertIn("materialization-incomplete marker", utilities["submit_fill.py"])
            self.assertIn("manifest plan digest mismatch", utilities["preflight.py"])
            self.assertIn("installed audit tool hash mismatch", utilities["preflight.py"])
            self.assertIn("archived audit tool hash mismatch", utilities["preflight.py"])
            self.assertIn(
                "archived handoff-receipt tool hash mismatch", utilities["preflight.py"]
            )

    def test_manifest_and_template_byte_tampering_are_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_integrity_test_") as temporary:
            batch = Path(temporary) / "batch"
            (batch / "templates").mkdir(parents=True)
            (batch / "submitted").mkdir()
            templates = []
            for index in (1, 2):
                path = batch / "templates" / f"{GENERATOR.TEMPLATE_PREFIX}{index:05d}.sh"
                path.write_text(f"#!/bin/bash\necho {index}\n")
                templates.append(path)
            rows = [
                {
                    "index": index,
                    "U": 20,
                    "V": "0",
                    "kx": index,
                    "ky": index,
                    "seed": 100 + index,
                    "result": f"/tmp/result_{index}.dat",
                }
                for index in (1, 2)
            ]
            GENERATOR.write_tsv(batch / "manifest.tsv", rows, list(rows[0]))
            manifest_bytes = (batch / "manifest.tsv").read_bytes()
            manifest_sha = GENERATOR.sha256(batch / "manifest.tsv")
            plan_sha = GENERATOR.plan_digest(rows)
            ledger = batch / "TEMPLATE_SHA256SUMS"
            ledger.write_text(GENERATOR.template_hash_ledger_text(templates))
            ledger_sha = GENERATOR.sha256(ledger)

            GENERATOR.validate_materialized_static_integrity(
                batch=batch,
                expected_manifest_sha256=manifest_sha,
                expected_plan_sha256=plan_sha,
                expected_template_ledger_sha256=ledger_sha,
                expected_template_count=2,
            )

            (batch / "manifest.tsv").write_bytes(manifest_bytes + b"# tampered\n")
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_materialized_static_integrity(
                    batch=batch,
                    expected_manifest_sha256=manifest_sha,
                    expected_plan_sha256=plan_sha,
                    expected_template_ledger_sha256=ledger_sha,
                    expected_template_count=2,
                )
            (batch / "manifest.tsv").write_bytes(manifest_bytes)
            templates[0].write_text("#!/bin/bash\necho tampered\n")
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_materialized_static_integrity(
                    batch=batch,
                    expected_manifest_sha256=manifest_sha,
                    expected_plan_sha256=plan_sha,
                    expected_template_ledger_sha256=ledger_sha,
                    expected_template_count=2,
                )

    def test_generated_submit_helper_refuses_tampering_before_sbatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_submit_guard_") as temporary:
            batch = Path(temporary) / "batch"
            for name in ("templates", "submitted", "pinned_solver", "tools"):
                (batch / name).mkdir(parents=True, exist_ok=True)
            templates = []
            rows = []
            index = 0
            for U, V in GENERATOR.PAIRS:
                for position in range(2):
                    index += 1
                    path = batch / "templates" / (
                        f"{GENERATOR.TEMPLATE_PREFIX}{index:05d}_U{U}_p{position}.sh"
                    )
                    path.write_text(
                        "#!/bin/bash\n"
                        "#SBATCH -A __ACCOUNT__\n"
                        f"#SBATCH -J {GENERATOR.JOB_NAME}\n"
                        f"INDEX='{index}'\n"
                        "echo guarded\n"
                    )
                    templates.append(path)
                    rows.append(
                        {
                            "index": str(index),
                            "U": str(U),
                            "V": V,
                            "kx": str(position),
                            "ky": str(index),
                            "seed": str(100 + index),
                            "result": f"/tmp/expansion_{index}.dat",
                        }
                    )
            original_template_bytes = {
                path: path.read_bytes() for path in templates
            }
            GENERATOR.write_tsv(batch / "manifest.tsv", rows, list(rows[0]))
            manifest_bytes = (batch / "manifest.tsv").read_bytes()
            manifest_sha = GENERATOR.sha256(batch / "manifest.tsv")
            plan_sha = GENERATOR.plan_digest(rows)
            ledger = batch / "TEMPLATE_SHA256SUMS"
            ledger.write_text(GENERATOR.template_hash_ledger_text(templates))
            ledger_sha = GENERATOR.sha256(ledger)

            reused_result = batch / "reused.dat"
            reused_result.write_text("status COMPLETE\n")
            reused = [
                {
                    "U": "999",
                    "V": "0",
                    "kx": "3",
                    "ky": "3",
                    "result": str(reused_result),
                    "sha256": GENERATOR.sha256(reused_result),
                }
            ]
            GENERATOR.write_tsv(batch / "reused_25.tsv", reused, list(reused[0]))
            certificate = batch / "decision_certificate.json"
            certificate.write_text("{}\n")
            decision_sha = GENERATOR.sha256(certificate)
            (batch / "submission.tsv").write_text(
                "submitted_at\taccount\tjob_id\tindex\tU\tV\tkx\tky\t"
                "run_script\tresult\tsubmission_kind\taction_id\tselection_rank\n"
            )

            audit_source = b"# synthetic pinned scheduler audit\n"
            (batch / "audit_status.py").write_bytes(audit_source)
            (batch / "tools/audit_status.py").write_bytes(audit_source)
            audit_sha = GENERATOR.sha256(batch / "audit_status.py")
            receipt_source = b"# synthetic pinned handoff receipt\n"
            (batch / "tools/handoff_receipt.py").write_bytes(receipt_source)
            receipt_sha = GENERATOR.sha256(batch / "tools/handoff_receipt.py")

            pin_hashes = {}
            for name, content in (
                ("Hubbard_sym_testobs_UV.x", b"solver"),
                ("Hubbard_sym_testobs_UV.cc", b"source"),
                ("libqbasis.so", b"library"),
            ):
                path = batch / "pinned_solver" / name
                path.write_bytes(content)
                pin_hashes[name] = GENERATOR.sha256(path)

            preflight = batch / "preflight.py"
            preflight.write_text(
                GENERATOR.preflight_text(
                    batch,
                    decision_sha,
                    plan_sha,
                    manifest_sha,
                    ledger_sha,
                    expected_expansion_total=24,
                    expected_reused_total=1,
                    expected_combined_total=25,
                    expected_per_case=2,
                    expected_solver_sha=pin_hashes["Hubbard_sym_testobs_UV.x"],
                    expected_source_sha=pin_hashes["Hubbard_sym_testobs_UV.cc"],
                    expected_qbasis_sha=pin_hashes["libqbasis.so"],
                    expected_audit_status_sha=audit_sha,
                    expected_handoff_receipt_sha=receipt_sha,
                )
            )
            preflight_sha = GENERATOR.sha256(preflight)
            (batch / "provenance.json").write_text(
                json.dumps(
                    {
                        "plan_sha256": plan_sha,
                        "manifest_sha256": manifest_sha,
                        "template_content_ledger_sha256": ledger_sha,
                        "package_tools_sha256": {
                            "audit_status.py": audit_sha,
                            "handoff_receipt.py": receipt_sha,
                        },
                    }
                )
            )
            helper = batch / "submit_fill.py"
            helper.write_text(
                GENERATOR.submit_helper_text(
                    batch,
                    decision_sha,
                    plan_sha,
                    manifest_sha,
                    ledger_sha,
                    preflight_sha,
                    expected_template_count=24,
                    expected_solver_sha=pin_hashes["Hubbard_sym_testobs_UV.x"],
                    expected_source_sha=pin_hashes["Hubbard_sym_testobs_UV.cc"],
                    expected_qbasis_sha=pin_hashes["libqbasis.so"],
                )
            )

            fake_bin = Path(temporary) / "bin"
            fake_bin.mkdir()
            sentinel = Path(temporary) / "sbatch_was_called"
            (fake_bin / "squeue").write_text("#!/bin/bash\nexit 0\n")
            (fake_bin / "sbatch").write_text(
                f"#!/bin/bash\ntouch '{sentinel}'\necho 'Submitted batch job 123'\n"
            )
            for name in ("squeue", "sbatch"):
                (fake_bin / name).chmod(0o700)
            env = dict(os.environ)
            env[GENERATOR.CONFIRM_ENV] = "YES"
            env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

            limited_dry_run = subprocess.run(
                [sys.executable, str(helper), "--limit", "1"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(
                limited_dry_run.returncode,
                0,
                msg=limited_dry_run.stdout + limited_dry_run.stderr,
            )
            self.assertIn("would_submit=1", limited_dry_run.stdout)

            interleaved_dry_run = subprocess.run(
                [sys.executable, str(helper), "--limit", "12"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(
                interleaved_dry_run.returncode,
                0,
                msg=interleaved_dry_run.stdout + interleaved_dry_run.stderr,
            )
            selected_indices = [
                int(re.search(r"_(\d{5})_", line).group(1))
                for line in interleaved_dry_run.stdout.splitlines()
                if line.startswith("WOULD_SBATCH")
            ]
            self.assertEqual(selected_indices, list(range(1, 24, 2)))

            wrong_bound_selection = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--submit",
                    "--one",
                    "--submission-kind",
                    "initial_launch",
                    "--action-id",
                    "a" * 64,
                    "--expected-indices",
                    "2",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertNotEqual(wrong_bound_selection.returncode, 0)
            self.assertIn(
                "live interleaved selection differs",
                wrong_bound_selection.stdout + wrong_bound_selection.stderr,
            )
            self.assertFalse(sentinel.exists())

            (batch / "manifest.tsv").write_bytes(manifest_bytes + b"# tampered\n")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--submit",
                    "--submission-kind",
                    "chain_refill",
                    "--action-id",
                    "test-action",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("manifest hash mismatch", proc.stdout + proc.stderr)
            self.assertFalse(sentinel.exists())

            (batch / "manifest.tsv").write_bytes(manifest_bytes)
            templates[0].write_text(templates[0].read_text() + "echo tampered\n")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--submit",
                    "--submission-kind",
                    "chain_refill",
                    "--action-id",
                    "test-action",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("template content mismatch", proc.stdout + proc.stderr)
            self.assertFalse(sentinel.exists())

            templates[0].write_bytes(original_template_bytes[templates[0]])
            proc = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--submit",
                    "--one",
                    "--submission-kind",
                    "chain_refill",
                    "--action-id",
                    "test-action",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertTrue(sentinel.exists())
            self.assertTrue(
                (
                    batch
                    / "submitted"
                    / (templates[0].stem + ".template")
                ).is_file()
            )
            self.assertFalse(
                (batch / "submitted" / (templates[0].stem + ".claim")).exists()
            )
            reused_action = subprocess.run(
                [
                    sys.executable,
                    str(helper),
                    "--submit",
                    "--one",
                    "--submission-kind",
                    "chain_refill",
                    "--action-id",
                    "test-action",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertNotEqual(reused_action.returncode, 0)
            self.assertIn(
                "submission action id already exists",
                reused_action.stdout + reused_action.stderr,
            )
            with (batch / "submission.tsv").open(newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle, delimiter="\t"))), 1)
            post_submit_preflight = subprocess.run(
                [sys.executable, str(preflight)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(
                post_submit_preflight.returncode,
                0,
                msg=post_submit_preflight.stdout + post_submit_preflight.stderr,
            )
            post_submit_dry_run = subprocess.run(
                [sys.executable, str(helper), "--limit", "12"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(
                post_submit_dry_run.returncode,
                0,
                msg=post_submit_dry_run.stdout + post_submit_dry_run.stderr,
            )
            post_indices = [
                int(re.search(r"_(\d{5})_", line).group(1))
                for line in post_submit_dry_run.stdout.splitlines()
                if line.startswith("WOULD_SBATCH")
            ]
            self.assertEqual(post_indices, list(range(3, 24, 2)) + [2])

    def test_full861_spread_is_quadrature_weighted_and_labeled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_weighted_std_") as temporary:
            batch = Path(temporary) / "batch"
            raw = batch / "raw"
            raw.mkdir(parents=True)
            rows = []
            weighted_values = []
            unweighted_values = []
            for index, (kx, ky) in enumerate(
                ((x, y) for y in range(41) for x in range(y + 1)), 1
            ):
                C = -0.1 if (kx, ky) == (0, 0) else -0.2
                result = raw / f"row_{index:04d}.dat"
                result.write_text(f"<C1_NN> {C:.17g}\nstatus COMPLETE\n")
                rows.append(
                    {
                        "U": "20",
                        "V": "0",
                        "kx": str(kx),
                        "ky": str(ky),
                        "result": str(result),
                    }
                )
                weight = (1.0 if kx == ky else 2.0) * (
                    0.5 if kx in (0, 40) else 1.0
                ) * (0.5 if ky in (0, 40) else 1.0)
                weighted_values.append((weight, C))
                unweighted_values.append(C)
            GENERATOR.write_tsv(batch / "manifest.tsv", rows, list(rows[0]))
            (batch / "reused_25.tsv").write_text("U\tV\tkx\tky\tresult\n")
            (batch / "decision_certificate.json").write_text("{}\n")
            (batch / "preflight.py").write_text("raise SystemExit(0)\n")
            script = batch / "analyze.py"
            script.write_text(GENERATOR.analyze_text(batch, expected_case_count=1))
            proc = subprocess.run(
                [sys.executable, str(script)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            with (
                batch / "analysis" / "fig4_cnn_full861_summary.csv"
            ).open(newline="") as handle:
                summary = next(csv.DictReader(handle))
            self.assertIn(
                "C_NN_full_quadrature_weighted_population_std", summary
            )
            self.assertNotIn("C_NN_full_population_std", summary)
            total_weight = sum(weight for weight, _ in weighted_values)
            mean = sum(weight * value for weight, value in weighted_values) / total_weight
            expected = math.sqrt(
                sum(weight * (value - mean) ** 2 for weight, value in weighted_values)
                / total_weight
            )
            observed = float(
                summary["C_NN_full_quadrature_weighted_population_std"]
            )
            unweighted_mean = sum(unweighted_values) / len(unweighted_values)
            unweighted_std = math.sqrt(
                sum((value - unweighted_mean) ** 2 for value in unweighted_values)
                / len(unweighted_values)
            )
            self.assertAlmostEqual(observed, expected, places=15)
            self.assertGreater(abs(observed - unweighted_std), 1.0e-3)
            provenance = json.loads(
                (
                    batch
                    / "analysis"
                    / "fig4_cnn_full861_provenance.json"
                ).read_text()
            )
            self.assertEqual(
                provenance["data_product"],
                "fig4_cnn_full861_direct_fullobs_C_NN_eq10",
            )
            self.assertFalse(provenance["spread_is_standard_error"])
            rerun = subprocess.run(
                [sys.executable, str(script)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(rerun.returncode, 0, msg=rerun.stdout + rerun.stderr)
            summary_path = batch / "analysis" / "fig4_cnn_full861_summary.csv"
            summary_path.write_text(summary_path.read_text() + "tampered\n")
            refused = subprocess.run(
                [sys.executable, str(script)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(
                "existing analysis summary differs; refusing overwrite",
                refused.stdout + refused.stderr,
            )


class HandoffReceiptTests(unittest.TestCase):
    @staticmethod
    def observation(
        *,
        P: int,
        Q: int,
        Rc: int,
        Rn: int,
        pending_ccsd: int | None = None,
        pending_cnms: int = 0,
        user_ccsd: int = 0,
        user_cnms: int = 0,
    ) -> dict[str, object]:
        pending_ccsd = P - pending_cnms if pending_ccsd is None else pending_ccsd
        return {
            "P": P,
            "Q": Q,
            "B": P + Q,
            "Rc": Rc,
            "Rn": Rn,
            "pending_by_account": {
                "ccsd": pending_ccsd,
                "cnms": pending_cnms,
            },
            "running_or_completing_by_account": {
                "ccsd": Rc,
                "cnms": Rn,
            },
            "all_user_active_by_account": {
                "ccsd": user_ccsd,
                "cnms": user_cnms,
            },
            "exact_name_account_state_counts": {},
        }

    @staticmethod
    def policy_payload(
        *,
        phase: str,
        created_at: str,
        path_order: list[int],
        observation: dict[str, object],
        account_cap: int,
        ledger_rows: int,
        previous_path: Path | None = None,
        previous: dict[str, object] | None = None,
    ) -> dict[str, object]:
        previous_observation = previous["observation"] if previous else None
        policy = RECEIPT.compute_policy(
            phase=phase,
            observation=observation,
            previous_observation=previous_observation,
            account_cap=account_cap,
            interleaved_unsubmitted_indices=path_order,
        )
        order_text = "".join(f"{index}\n" for index in path_order)
        payload: dict[str, object] = {
            "artifact_type": "fig4_cnn_861_handoff_policy_state",
            "schema_version": RECEIPT.POLICY_STATE_SCHEMA_VERSION,
            "phase": phase,
            "created_at": created_at,
            "standing_user_authorization": True,
            "certificate_decision": "APPROVE_EXPANSION",
            "certificate_sha256": "a" * 64,
            "certificate_path": "/tmp/certificate.json",
            "remote_host": "cades",
            "remote_batch": str(RECEIPT.REMOTE_BATCH),
            "remote_reviewed_holding_package": "/remote/package",
            "remote_external_decision_certificate": "/remote/certificate",
            "holding_package_certificate_revalidated": True,
            "manifest_sha256": RECEIPT.EXPECTED_MANIFEST_SHA256,
            "plan_sha256": RECEIPT.EXPECTED_PLAN_SHA256,
            "handoff_receipt_tool_sha256": RECEIPT.sha256(RECEIPT.SCRIPT),
            "previous_receipt_path": str(previous_path) if previous_path else None,
            "previous_receipt_sha256": (
                RECEIPT.sha256(previous_path) if previous_path else None
            ),
            "previous_state_digest": (
                previous["state_digest"] if previous is not None else None
            ),
            "previous_observation": previous_observation,
            "account_cap": account_cap,
            "observation": observation,
            "policy": policy,
            "interleaved_unsubmitted_indices": path_order,
            "interleaved_unsubmitted_indices_sha256": hashlib.sha256(
                order_text.encode()
            ).hexdigest(),
            "submission_ledger_before": {
                "file_sha256": "c" * 64,
                "semantic_rows_sha256": "d" * 64,
                "row_count": ledger_rows,
            },
            "submission_accounts_before": {},
            "template_count": len(path_order),
            "archive_count": ledger_rows,
            "claim_count": 0,
            "repair_submission_count": 0,
            "runtime_pins_matching": 3,
        }
        payload["state_digest"] = RECEIPT.state_digest(payload)
        return payload

    @staticmethod
    def receipt_payload(
        *,
        phase: str,
        created_at: str,
        policy_path: Path,
        policy_state: dict[str, object],
        post_observation: dict[str, object],
        submission_accounts: dict[str, int],
        before_rows: int,
        after_rows: int,
        previous_path: Path | None = None,
        previous: dict[str, object] | None = None,
    ) -> dict[str, object]:
        terminal = phase == "rebalance_20m"
        effective = int(policy_state["policy"]["effective_n"])
        selected = list(policy_state["policy"]["selected_manifest_indices"])
        payload: dict[str, object] = {
            "artifact_type": "fig4_cnn_861_handoff_receipt",
            "schema_version": RECEIPT.RECEIPT_SCHEMA_VERSION,
            "phase": phase,
            "created_at": created_at,
            "standing_user_authorization": True,
            "holding_package_certificate_revalidated": True,
            "certificate_decision": "APPROVE_EXPANSION",
            "certificate_sha256": "a" * 64,
            "manifest_sha256": RECEIPT.EXPECTED_MANIFEST_SHA256,
            "plan_sha256": RECEIPT.EXPECTED_PLAN_SHA256,
            "claim_count": 0,
            "repair_submission_count": 0,
            "runtime_pins_matching": 3,
            "handoff_receipt_tool_sha256": RECEIPT.sha256(RECEIPT.SCRIPT),
            "policy_state_path": str(policy_path),
            "policy_state_sha256": RECEIPT.sha256(policy_path),
            "policy_state_digest": policy_state["state_digest"],
            "policy_observation": policy_state["observation"],
            "policy": policy_state["policy"],
            "handoff_action": {
                "submission_kind": phase,
                "action_id": policy_state["state_digest"],
                "target_account": policy_state["policy"]["target_account"],
                "selected_manifest_indices": selected,
                "selected_job_ids": [str(1000 + index) for index in range(effective)],
                "selection_is_interleaved": True,
            },
            "bound_submission_ledger_delta": {
                "before_file_sha256": "c" * 64,
                "before_semantic_rows_sha256": "d" * 64,
                "before_row_count": before_rows,
                "after_file_sha256": "e" * 64,
                "after_semantic_rows_sha256": "f" * 64,
                "after_row_count": after_rows,
                "rows_appended": after_rows - before_rows,
                "appended_rows_semantic_sha256": "1" * 64,
                "action_id": policy_state["state_digest"],
                "action_row_count": effective,
                "action_rows_semantic_sha256": "2" * 64,
            },
            "previous_receipt_path": str(previous_path) if previous_path else None,
            "previous_receipt_sha256": (
                RECEIPT.sha256(previous_path) if previous_path else None
            ),
            "previous_state_digest": (
                previous["state_digest"] if previous is not None else None
            ),
            "observation": post_observation,
            "submission_accounts": submission_accounts,
            "allowed_refill_accounts": RECEIPT.expected_allowed_refill_accounts(
                submission_accounts
            ),
            "rebalance_cycle_complete": terminal,
            "eligible_for_two_hour_expansion_heartbeat": terminal,
        }
        payload["state_digest"] = RECEIPT.state_digest(payload)
        return payload

    def test_add_only_policy_records_and_recomputes_every_required_quantity(self) -> None:
        initial_observation = self.observation(P=0, Q=10_032, Rc=0, Rn=0)
        initial = RECEIPT.compute_policy(
            phase="initial_launch",
            observation=initial_observation,
            previous_observation=None,
            account_cap=150,
            interleaved_unsubmitted_indices=list(range(1, 10_033)),
        )
        self.assertEqual(initial["inputs"]["B"], 10_032)
        self.assertEqual(initial["requested_n"], 10_032)
        self.assertEqual(initial["effective_n"], 150)
        self.assertEqual(initial["selected_manifest_indices"], list(range(1, 151)))

        at_ten = self.observation(P=130, Q=9_880, Rc=20, Rn=0, user_cnms=3)
        probe = RECEIPT.compute_policy(
            phase="rebalance_10m",
            observation=at_ten,
            previous_observation=initial_observation,
            account_cap=150,
            interleaved_unsubmitted_indices=list(range(153, 10_033)),
        )
        self.assertTrue(probe["counts_changed"])
        self.assertEqual(probe["requested_n"], 10)
        self.assertEqual(probe["effective_n"], 10)
        self.assertEqual(probe["target_account"], "cnms")

        unchanged = RECEIPT.compute_policy(
            phase="rebalance_20m",
            observation=at_ten,
            previous_observation=at_ten,
            account_cap=150,
            interleaved_unsubmitted_indices=list(range(153, 10_033)),
        )
        self.assertFalse(unchanged["counts_changed"])
        self.assertEqual(unchanged["requested_n"], 0)
        self.assertEqual(unchanged["rule_branch"], "no_pending_or_running_count_change")

        at_twenty = self.observation(
            P=110,
            Q=9_850,
            Rc=30,
            Rn=10,
            pending_ccsd=100,
            pending_cnms=10,
            user_cnms=149,
        )
        ratio = RECEIPT.compute_policy(
            phase="rebalance_20m",
            observation=at_twenty,
            previous_observation=at_ten,
            account_cap=150,
            interleaved_unsubmitted_indices=list(range(183, 10_033)),
        )
        self.assertTrue(ratio["counts_changed"])
        self.assertEqual(ratio["requested_n"], 2463)
        self.assertEqual(ratio["inputs"]["capacity"], 1)
        self.assertEqual(ratio["effective_n"], 1)

    def test_exclusive_writer_fsync_contract_mode_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_exclusive_") as temporary:
            path = Path(temporary) / "artifact.json"
            payload = {"value": 1}
            with mock.patch.object(RECEIPT.os, "fsync", wraps=os.fsync) as fsync:
                RECEIPT.exclusive_write_json(path, payload)
                self.assertGreaterEqual(fsync.call_count, 3)
            self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            self.assertEqual(path.stat().st_nlink, 1)
            with self.assertRaises(RECEIPT.Refusal):
                RECEIPT.exclusive_write_json(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text()), payload)

    def test_ledger_delta_binds_interleaved_indices_and_job_ids(self) -> None:
        observation = self.observation(P=0, Q=10_032, Rc=0, Rn=0)
        policy_state = self.policy_payload(
            phase="initial_launch",
            created_at="2026-08-21T10:00:00-04:00",
            path_order=list(range(1, 10_033)),
            observation=observation,
            account_cap=2,
            ledger_rows=0,
        )
        policy_state["submission_ledger_before"]["semantic_rows_sha256"] = (
            RECEIPT.canonical_rows_digest([])
        )
        policy_state["state_digest"] = RECEIPT.state_digest(policy_state)
        action_id = policy_state["state_digest"]
        rows = [
            {
                "submitted_at": "2026-08-21T10:00:01-04:00",
                "account": "ccsd",
                "job_id": str(7000 + index),
                "index": str(index),
                "U": "20",
                "V": "0",
                "kx": "0",
                "ky": str(index),
                "run_script": f"run_{index}",
                "result": f"result_{index}",
                "submission_kind": "initial_launch",
                "action_id": action_id,
                "selection_rank": str(index),
            }
            for index in (1, 2)
        ]
        remote = {
            "submission_rows": rows,
            "submission_ledger_sha256": "e" * 64,
            "submission_rows_digest": RECEIPT.canonical_rows_digest(rows),
        }
        delta, action = RECEIPT.validate_ledger_action(
            policy_state=policy_state, remote=remote
        )
        self.assertEqual(action["selected_manifest_indices"], [1, 2])
        self.assertEqual(action["selected_job_ids"], ["7001", "7002"])
        self.assertEqual(delta["action_row_count"], 2)

        rows[0]["index"], rows[1]["index"] = rows[1]["index"], rows[0]["index"]
        with self.assertRaises(RECEIPT.Refusal):
            RECEIPT.validate_ledger_action(policy_state=policy_state, remote=remote)

    def test_three_phase_policy_bound_receipt_chain_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_receipt_chain_") as temporary:
            root = Path(temporary)
            policy_paths = [root / f"policy_{name}.json" for name in RECEIPT.PHASES]
            receipt_paths = [root / f"receipt_{name}.json" for name in RECEIPT.PHASES]

            initial_pre = self.observation(P=0, Q=10_032, Rc=0, Rn=0)
            initial_policy = self.policy_payload(
                phase="initial_launch",
                created_at="2026-08-21T10:00:00-04:00",
                path_order=list(range(1, 10_033)),
                observation=initial_pre,
                account_cap=2,
                ledger_rows=0,
            )
            RECEIPT.exclusive_write_json(policy_paths[0], initial_policy)
            initial_post = self.observation(P=1, Q=10_029, Rc=1, Rn=0)
            launch = self.receipt_payload(
                phase="initial_launch",
                created_at="2026-08-21T10:00:01-04:00",
                policy_path=policy_paths[0],
                policy_state=initial_policy,
                post_observation=initial_post,
                submission_accounts={"ccsd": 3},
                before_rows=0,
                after_rows=3,
            )
            RECEIPT.exclusive_write_json(receipt_paths[0], launch)

            r10_pre = self.observation(P=1, Q=10_029, Rc=1, Rn=0)
            r10_policy = self.policy_payload(
                phase="rebalance_10m",
                created_at="2026-08-21T10:10:01-04:00",
                path_order=list(range(4, 10_033)),
                observation=r10_pre,
                account_cap=2,
                ledger_rows=3,
                previous_path=receipt_paths[0],
                previous=launch,
            )
            RECEIPT.exclusive_write_json(policy_paths[1], r10_policy)
            r10_post = self.observation(P=1, Q=10_025, Rc=2, Rn=1)
            r10 = self.receipt_payload(
                phase="rebalance_10m",
                created_at="2026-08-21T10:10:02-04:00",
                policy_path=policy_paths[1],
                policy_state=r10_policy,
                post_observation=r10_post,
                submission_accounts={"ccsd": 3, "cnms": 4},
                before_rows=3,
                after_rows=7,
                previous_path=receipt_paths[0],
                previous=launch,
            )
            RECEIPT.exclusive_write_json(receipt_paths[1], r10)

            r20_pre = self.observation(P=1, Q=10_025, Rc=2, Rn=1, user_cnms=1)
            r20_policy = self.policy_payload(
                phase="rebalance_20m",
                created_at="2026-08-21T10:20:02-04:00",
                path_order=list(range(8, 10_033)),
                observation=r20_pre,
                account_cap=2,
                ledger_rows=7,
                previous_path=receipt_paths[1],
                previous=r10,
            )
            RECEIPT.exclusive_write_json(policy_paths[2], r20_policy)
            r20_post = self.observation(P=1, Q=10_023, Rc=2, Rn=2)
            r20 = self.receipt_payload(
                phase="rebalance_20m",
                created_at="2026-08-21T10:20:03-04:00",
                policy_path=policy_paths[2],
                policy_state=r20_policy,
                post_observation=r20_post,
                submission_accounts={"ccsd": 3, "cnms": 6},
                before_rows=7,
                after_rows=9,
                previous_path=receipt_paths[1],
                previous=r10,
            )
            RECEIPT.exclusive_write_json(receipt_paths[2], r20)

            observed = RECEIPT.validate_receipt_chain(receipt_paths[2])
            self.assertTrue(observed["eligible_for_two_hour_expansion_heartbeat"])
            self.assertTrue(observed["rebalance_cycle_complete"])
            self.assertEqual(observed["allowed_refill_accounts"], ["ccsd", "cnms"])
            self.assertEqual(observed["policy"]["algorithm"], RECEIPT.POLICY_ALGORITHM)

            receipt_paths[0].chmod(0o644)
            receipt_paths[0].write_text(receipt_paths[0].read_text() + "\n")
            receipt_paths[0].chmod(0o444)
            with self.assertRaises(RECEIPT.Refusal):
                RECEIPT.validate_receipt_chain(receipt_paths[2])

    def test_receipt_remote_probe_contains_no_scheduler_mutation(self) -> None:
        probe = RECEIPT.REMOTE_STATE_PROGRAM
        compile(probe, "<handoff-remote-state-program>", "exec")
        for forbidden in ("sbatch", "scancel", "scontrol", "rm -", "unlink("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, probe)
def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class QuantitativeDecisionTests(unittest.TestCase):
    def make_analysis(
        self,
        root: Path,
        *,
        wide_panel: bool = False,
        symmetry_exit: bool = False,
        rmse: float = 0.01,
        panel_metrics: dict[tuple[float, float], tuple[float, float]] | None = None,
    ) -> Path:
        analysis = root / "analysis"
        analysis.mkdir(parents=True)
        panel = []
        pointwise = []
        for index, (U, V) in enumerate(DECISION.EXPECTED_CASES):
            if panel_metrics is not None:
                spread, symmetry_diagnostic = panel_metrics[(U, V)]
            else:
                spread = 0.01 if wide_panel and index < 2 else 2.0e-5
                symmetry_diagnostic = (
                    1.0e-5 if symmetry_exit and index == 0 else 5.0e-7
                )
            panel.append(
                {
                    "U": U,
                    "V": V,
                    "C_NN_spread": spread,
                    "C_NN_symmetry_weighted_minus_primary": symmetry_diagnostic,
                }
            )
            pointwise.append(
                {
                    "U": U,
                    "V": V,
                    "eq10_residual_observed_minus_prediction": 0.01,
                    "rmse": rmse,
                }
            )
        # Four controls make the reviewed analyzer output cardinality 16.
        for V in (0.0, 4.0, 8.0, 9.0):
            pointwise.append(
                {
                    "U": 40.0,
                    "V": V,
                    "eq10_residual_observed_minus_prediction": 0.001,
                    "rmse": rmse,
                }
            )
        calibration = [
            {
                "U": 40.0,
                "V": V,
                "abs_panel_minus_full": bias,
                "C_NN_panel_spread": spread,
                "abs_C_NN_symmetry_weighted_minus_primary": symmetry,
                "passes_panel_bias_gate": True,
            }
            for V, bias, spread, symmetry in (
                (
                    0.0,
                    1.3510893387413958e-7,
                    1.530864841103874e-5,
                    5.03466764667504e-7,
                ),
                (
                    4.0,
                    1.760218488744414e-7,
                    2.447600760407953e-5,
                    7.485825450070926e-7,
                ),
                (
                    8.0,
                    2.4414020122209834e-7,
                    4.396618752744441e-5,
                    1.243810605344731e-6,
                ),
                (
                    9.0,
                    2.6920934537155716e-7,
                    5.229141656709624e-5,
                    1.450012748316354e-6,
                ),
            )
        ]
        write_csv(analysis / "fig4_cnn_campaign_panel_summary.csv", panel)
        write_csv(analysis / "fig4_cnn_u40_panel_calibration.csv", calibration)
        write_csv(analysis / "fig4_cnn_pointwise_eq10.csv", pointwise)
        (analysis / "fig4_cnn_analysis_provenance.json").write_text(
            json.dumps(
                {
                    "raw_output_inventory": {
                        "count": 300,
                        "ordered_filename_sha256_digest": "a" * 64,
                        "all_status_complete": True,
                        "max_abs_identity_residual": 1.0e-10,
                        "identity_tolerance": 1.0e-8,
                    },
                    "campaign_pinned_solver": {
                        "solver_sha256": GENERATOR.EXPECTED_SOLVER_SHA256,
                        "source_sha256": GENERATOR.EXPECTED_SOURCE_SHA256,
                        "qbasis_library_sha256": GENERATOR.EXPECTED_QBASIS_SHA256,
                    },
                }
            )
        )
        return analysis

    def test_in_domain_sub_tolerance_diagnostics_refuse_expansion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_gate_test_") as temporary:
            result = DECISION.analyze_decision(
                self.make_analysis(Path(temporary))
            )
        self.assertFalse(result["approved"])
        self.assertEqual(result["decision"], "NO_EXPANSION")
        diagnostics = result["quadrature_diagnostics"]
        self.assertEqual(diagnostics["slope_tolerance_exceedance_count"], 0)
        self.assertEqual(diagnostics["roughness_calibrated_domain_exit_count"], 0)
        self.assertEqual(diagnostics["symmetry_calibrated_domain_exit_count"], 0)

    def test_wide_panel_approves_expansion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_gate_test_") as temporary:
            result = DECISION.analyze_decision(
                self.make_analysis(Path(temporary), wide_panel=True)
            )
        self.assertTrue(result["approved"])
        self.assertEqual(result["decision"], "APPROVE_EXPANSION")
        self.assertGreaterEqual(
            result["quadrature_diagnostics"][
                "slope_tolerance_exceedance_count"
            ],
            2,
        )
        self.assertGreaterEqual(
            result["quadrature_diagnostics"][
                "roughness_calibrated_domain_exit_count"
            ],
            2,
        )

    def test_symmetry_diagnostic_exit_approves_expansion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_gate_test_") as temporary:
            result = DECISION.analyze_decision(
                self.make_analysis(Path(temporary), symmetry_exit=True)
            )
        self.assertTrue(result["approved"])
        self.assertEqual(
            result["quadrature_diagnostics"][
                "symmetry_calibrated_domain_exit_count"
            ],
            1,
        )

    def test_gz_rmse_is_dimensionally_excluded_and_cannot_change_decision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_rmse_test_") as temporary:
            root = Path(temporary)
            low = DECISION.analyze_decision(
                self.make_analysis(root / "low", rmse=1.0e-12)
            )
            high = DECISION.analyze_decision(
                self.make_analysis(root / "high", rmse=1.0e12)
            )
        self.assertEqual(low, high)
        self.assertFalse(
            low["methodology"]["gz_curve_fit_rmse_used_for_decision"]
        )
        self.assertNotIn("gz_fit_rmse", json.dumps(low))

    def test_exact_calibration_and_source_bound_targets_refuse_fabrication(self) -> None:
        # A calibration value cannot be replaced even if the rest of the
        # certificate remains internally self-consistent.
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_calibration_tamper_") as temporary:
            certificate = Path(temporary) / "certificate.json"
            payload = self.valid_certificate()
            payload["calibration"]["max_abs_C_NN_panel_minus_full861"] *= 0.9
            certificate.write_text(json.dumps(payload))
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_decision_certificate(certificate)

        # More importantly, an otherwise coherent synthetic APPROVE decision
        # with the *actual* raw-byte digest must still match the two metrics
        # independently rederived from those exact 300 bytes.
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_target_binding_") as temporary:
            root = Path(temporary)
            base = root / "source"
            base.mkdir()
            source_rows = []
            for original in GENERATOR.load_source_manifest(
                PACKAGE / "reviewed_inputs" / "source_25_manifest.tsv"
            ):
                row = dict(original)
                name = GENERATOR.result_name(
                    int(row["U"]),
                    row["V"],
                    int(row["kx"]),
                    int(row["ky"]),
                )
                path = base / name
                path.write_text(
                    synthetic_complete_output(
                        float(row["U"]),
                        float(row["V"]),
                        int(row["kx"]),
                        int(row["ky"]),
                    )
                )
                row["result"] = str(path)
                source_rows.append(row)
            digest = hashlib.sha256(
                "".join(
                    f"{path.name}\t{GENERATOR.sha256(path)}\n"
                    for path in sorted(base.glob("*_obs.dat"), key=lambda item: item.name)
                ).encode()
            ).hexdigest()
            inventory = GENERATOR.validate_source_results(source_rows, base, digest)

            by_index = {int(row["index"]): row for row in inventory}
            grouped: dict[tuple[float, float], list[tuple[int, int, float]]] = {}
            for row in source_rows:
                case = (float(row["U"]), float(row["V"]))
                grouped.setdefault(case, []).append(
                    (
                        int(row["kx"]),
                        int(row["ky"]),
                        float(by_index[int(row["index"])]["C_NN"]),
                    )
                )
            metrics = {}
            for case, values in grouped.items():
                C = [value for _, _, value in values]
                primary = sum(C) / len(C)
                weights = [1.0 if kx == ky else 2.0 for kx, ky, _ in values]
                weighted = sum(
                    weight * value
                    for weight, (_, _, value) in zip(weights, values)
                ) / sum(weights)
                metrics[case] = (max(C) - min(C), abs(weighted - primary))

            actual = DECISION.analyze_decision(
                self.make_analysis(root / "actual", panel_metrics=metrics)
            )
            actual["source_raw_inventory"]["ordered_filename_sha256_digest"] = digest
            result = GENERATOR.validate_source_decision_inputs(
                actual, source_rows, inventory
            )
            self.assertTrue(
                result["all_decision_driving_target_metrics_match_source_bytes"]
            )

            fabricated = DECISION.analyze_decision(
                self.make_analysis(root / "fabricated", wide_panel=True)
            )
            self.assertTrue(fabricated["approved"])
            fabricated["source_raw_inventory"][
                "ordered_filename_sha256_digest"
            ] = digest
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_source_decision_inputs(
                    fabricated, source_rows, inventory
                )

    def valid_certificate(self) -> dict[str, object]:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_valid_cert_") as temporary:
            payload = DECISION.analyze_decision(
                self.make_analysis(Path(temporary), wide_panel=True)
            )
        payload.update(
            {
                "input_sha256": GENERATOR.EXPECTED_DECISION_INPUT_HASHES,
                "expansion_contract": {
                    "cases": [
                        {"U": float(U), "V": float(V)}
                        for U, V in GENERATOR.PAIRS
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
            }
        )
        return payload

    def test_valid_and_no_expansion_certificate_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_cert_test_") as temporary:
            path = Path(temporary) / "certificate.json"
            path.write_text(json.dumps(self.valid_certificate()))
            accepted, digest = GENERATOR.validate_decision_certificate(path)
            self.assertTrue(accepted["approved"])
            self.assertEqual(digest, GENERATOR.sha256(path))

            payload = self.valid_certificate()
            payload["approved"] = False
            payload["decision"] = "NO_EXPANSION"
            path.write_text(json.dumps(payload))
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_decision_certificate(path)

            payload = self.valid_certificate()
            payload["methodology"]["gz_curve_fit_rmse_used_for_decision"] = True
            path.write_text(json.dumps(payload))
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_decision_certificate(path)

            payload = self.valid_certificate()
            payload["targets"][0]["gz_fit_rmse"] = 0.01
            path.write_text(json.dumps(payload))
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_decision_certificate(path)

    def test_no_expansion_cli_and_wrong_hash_are_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="f4cnn861x_block_test_") as temporary:
            root = Path(temporary)
            path = root / "no_expansion.json"
            payload = self.valid_certificate()
            payload["approved"] = False
            payload["decision"] = "NO_EXPANSION"
            path.write_text(json.dumps(payload))
            batch = root / "must_not_be_created"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "generate_batch.py"),
                    "--materialize",
                    "--decision-certificate",
                    str(path),
                    "--batch",
                    str(batch),
                    "--source-batch",
                    str(root / "nonexistent_source"),
                ],
                cwd=REPO,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("does not approve expansion", proc.stderr)
            self.assertFalse(batch.exists())

            payload = self.valid_certificate()
            payload["input_sha256"] = dict(GENERATOR.EXPECTED_DECISION_INPUT_HASHES)
            payload["input_sha256"]["u40_rows"] = "0" * 64
            path.write_text(json.dumps(payload))
            with self.assertRaises(GENERATOR.Refusal):
                GENERATOR.validate_decision_certificate(path)


if __name__ == "__main__":
    unittest.main()
