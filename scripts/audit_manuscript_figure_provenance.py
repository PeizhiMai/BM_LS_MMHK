#!/usr/bin/env python3
"""Verify that every manuscript figure is produced by a project script.

This is intentionally strict: every ``\\includegraphics`` entry in the PNAS
main text or SI must appear in the provenance map below.  Legacy hand-assembled
figure names are rejected even if such files remain elsewhere in the project.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "manuscript" / "main_pnas_style.tex"
SUPP = ROOT / "manuscript" / "supplement_pnas_style.tex"
OUT = ROOT / "results" / "manuscript_figure_provenance_20260724.json"


PROVENANCE = {
    "fig1_multidensity_benchmark.pdf": {
        "path": "figures/pnas_main/fig1_multidensity_benchmark.pdf",
        "generator": "scripts/build_pnas_manuscript_figures.py",
        "sources": [
            "results/half_filling_methods.csv",
            "results/mmhk_observables_all_cases.csv",
            "results/figS2_filtered_candidate_data.csv",
            "results/figS2_filtered_comparison_data.csv",
            "results/figS2_selected_comparison_data.csv",
            "results/figS2_selected_half_filling_references.csv",
            "results/figS2_source_filter_audit.json",
        ],
    },
    "pnas_fig2_interaction_axis_comparison.pdf": {
        "path": "figures/pnas_main/pnas_fig2_interaction_axis_comparison.pdf",
        "generator": "scripts/build_pnas_manuscript_figures.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V2_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V5_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V8_tp0_eta0p05_spectra_and_roots.npz",
            "results/pnas_fig2_axis_fit_metrics.csv",
        ],
    },
    "pnas_fig3_scale_and_transition_boundary.pdf": {
        "path": "figures/pnas_main/pnas_fig3_scale_and_transition_boundary.pdf",
        "generator": "scripts/build_scale_and_transition_figure.py",
        "sources": [
            "results/pnas_scale_rule_points_eta0p05.csv",
            "results/pnas_scale_rule_summary_eta0p05.json",
            "results/transition_brackets_combined_U2_U40.csv",
            "results/transition_brackets_Uge4_for_combined_figure.csv",
        ],
    },
    "pnas_fig4_static_branch_crossing.pdf": {
        "path": "figures/pnas_main/pnas_fig4_static_branch_crossing.pdf",
        "generator": "scripts/build_pnas_manuscript_figures.py",
        "sources": [
            "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv",
            "results/fullobs_U40_observable_rows_20260723_091307.csv.gz",
            "results/fullobs_U40_data_quality_20260723_091307.json",
        ],
    },
    "pnas_supplement/supp_figS1_asymptotic_mechanisms.pdf": {
        "path": "figures/pnas_supplement/supp_figS1_asymptotic_mechanisms.pdf",
        "generator": "scripts/build_pnas_supplement_figures.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V12_tp0_eta0p05_spectra_and_roots.npz",
            "results/additional2_zero_dispersion_scale_fits_eta0p05.csv",
        ],
    },
    "pnas_supplement/supp_figS2_uonly_spectral_sequence.pdf": {
        "path": "figures/pnas_supplement/supp_figS2_uonly_spectral_sequence.pdf",
        "generator": "scripts/build_pnas_spectral_sequence_supplement.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "results/pnas_supp_spectral_sequence_windows.json",
        ],
    },
    "pnas_supplement/supp_figS3_uonly_lower_band_snapshots.pdf": {
        "path": "figures/pnas_supplement/supp_figS3_uonly_lower_band_snapshots.pdf",
        "generator": "scripts/build_pnas_spectral_sequence_supplement.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_U40_eta0p05_lower_frequency_extension.npz",
            "results/pnas_supp_spectral_sequence_windows.json",
        ],
    },
    "pnas_supplement/supp_figS4_vonly_spectral_sequence.pdf": {
        "path": "figures/pnas_supplement/supp_figS4_vonly_spectral_sequence.pdf",
        "generator": "scripts/build_pnas_spectral_sequence_supplement.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V2_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V5_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V8_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V12_tp0_eta0p05_spectra_and_roots.npz",
            "results/pnas_supp_spectral_sequence_windows.json",
        ],
    },
    "pnas_supplement/supp_figS5_vonly_lower_band_snapshots.pdf": {
        "path": "figures/pnas_supplement/supp_figS5_vonly_lower_band_snapshots.pdf",
        "generator": "scripts/build_pnas_spectral_sequence_supplement.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V2_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V5_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V8_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V12_tp0_eta0p05_spectra_and_roots.npz",
            "results/pnas_supp_spectral_sequence_windows.json",
        ],
    },
    "pnas_supplement/supp_figS6_finite_uv_spectral_reorganization.pdf": {
        "path": "figures/pnas_supplement/supp_figS6_finite_uv_spectral_reorganization.pdf",
        "generator": "scripts/build_pnas_manuscript_figures.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets/rhoG_LS_U40_V4_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets/rhoG_LS_U40_V8_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets/rhoG_LS_U40_V12_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets/rhoG_LS_U40_V16_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets/rhoG_LS_U40_V20_tp0_eta0p05_spectra_and_roots.npz",
        ],
    },
    "luttinger_eta0p05_other_parameter_sets/eta0p05_V_effect_luttinger_dispersion_comparison_evenV.pdf": {
        "path": "figures/luttinger_eta0p05_other_parameter_sets/eta0p05_V_effect_luttinger_dispersion_comparison_evenV.pdf",
        "generator": "scripts/plot_v_effect_luttinger_dispersion_even_v.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz",
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets",
        ],
    },
    "pnas_supplement/pnas_supp_figS8_zero_branch_candidate_audit_eta0p05.pdf": {
        "path": "figures/pnas_supplement/pnas_supp_figS8_zero_branch_candidate_audit_eta0p05.pdf",
        "generator": "scripts/build_pnas_supplement_figures.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets",
            "results/pnas_supp_zero_branch_audit_eta0p05.csv",
        ],
    },
    "fullobs/fullobs_static_scan_U40.pdf": {
        "path": "figures/fullobs/fullobs_static_scan_U40.pdf",
        "generator": "scripts/analyze_fullobs_u40_scan.py",
        "sources": [
            "data/fullobs/U40_all_twist_20260723_091307",
            "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv",
        ],
    },
    "fullobs/fullobs_nk_maps_U40.pdf": {
        "path": "figures/fullobs/fullobs_nk_maps_U40.pdf",
        "generator": "scripts/analyze_fullobs_u40_scan.py",
        "sources": [
            "data/fullobs/U40_all_twist_20260723_091307",
            "results/fullobs_U40_observable_rows_20260723_091307.csv.gz",
        ],
    },
    "fullobs/fullobs_strong_coupling_validation_U40.pdf": {
        "path": "figures/fullobs/fullobs_strong_coupling_validation_U40.pdf",
        "generator": "scripts/analyze_fullobs_u40_scan.py",
        "sources": [
            "data/fullobs/U40_all_twist_20260723_091307",
            "results/fullobs_U40_observable_summary_by_V_20260723_091307.csv",
        ],
    },
    "pnas_main/pnas_supp_extraction_robustness.pdf": {
        "path": "figures/pnas_main/pnas_supp_extraction_robustness.pdf",
        "generator": "scripts/build_pnas_manuscript_figures.py",
        "sources": [
            "results/nk_metrics.csv",
            "results/zero_branch_robustness_eta0p05.csv",
            "results/pnas_scale_rule_points_eta0p05.csv",
        ],
    },
    "pnas_supplement/supp_figS13_tpn25_reproduced.pdf": {
        "path": "figures/pnas_supplement/supp_figS13_tpn25_reproduced.pdf",
        "generator": "scripts/build_pnas_supplement_figures.py",
        "sources": [
            "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tpn25_eta0p05_spectra_and_roots.npz",
            "scripts/fit_tpn25_zero_dispersion.py",
            "results/tpn25_j1j2_spin_correlations.csv",
        ],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def figure_references(tex: str) -> list[str]:
    return re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)


def main() -> None:
    references = figure_references(MAIN.read_text()) + figure_references(SUPP.read_text())
    reference_set = set(references)
    mapped_set = set(PROVENANCE)
    missing_mapping = sorted(reference_set - mapped_set)
    unused_mapping = sorted(mapped_set - reference_set)

    records = []
    failures = []
    for reference in references:
        item = PROVENANCE.get(reference)
        if item is None:
            continue
        figure = ROOT / item["path"]
        generator = ROOT / item["generator"]
        source_paths = [ROOT / source for source in item["sources"]]
        missing_sources = [str(path.relative_to(ROOT)) for path in source_paths if not path.exists()]
        record = {
            "reference": reference,
            "figure": item["path"],
            "generator": item["generator"],
            "sources": item["sources"],
            "figure_exists": figure.exists() and figure.stat().st_size > 0,
            "generator_exists": generator.exists(),
            "missing_sources": missing_sources,
        }
        if figure.exists():
            record.update(
                {
                    "sha256": sha256(figure),
                    "size_bytes": figure.stat().st_size,
                    "modified": datetime.fromtimestamp(figure.stat().st_mtime).isoformat(),
                }
            )
        if not record["figure_exists"] or not record["generator_exists"] or missing_sources:
            failures.append(reference)
        records.append(record)

    combined_tex = MAIN.read_text() + "\n" + SUPP.read_text()
    prohibited_legacy_references = [
        name
        for name in [
            "half_filling_comparison.pdf",
            "hftp0.pdf",
            "hftpn25.pdf",
            "LStp0",
            "LStpn25",
        ]
        if name in combined_tex
    ]
    payload = {
        "generated": datetime.now().isoformat(),
        "main_tex": str(MAIN.relative_to(ROOT)),
        "supplement_tex": str(SUPP.relative_to(ROOT)),
        "figure_reference_count": len(references),
        "unique_figure_reference_count": len(reference_set),
        "missing_provenance_mapping": missing_mapping,
        "unused_provenance_mapping": unused_mapping,
        "prohibited_legacy_references": prohibited_legacy_references,
        "failed_records": failures,
        "all_figures_script_generated": not (
            missing_mapping or unused_mapping or prohibited_legacy_references or failures
        ),
        "records": records,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if not payload["all_figures_script_generated"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
