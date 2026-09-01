#!/usr/bin/env python3
"""Validate the active two-column REVTeX manuscript and its five main figures."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript"
RESULTS = ROOT / "results"
TEX = MANUSCRIPT / "main_current.tex"
LOG = MANUSCRIPT / "main_current.log"
PDF = MANUSCRIPT / "main_current.pdf"
OUTPUT_PDF = ROOT / "output/pdf/MMHK.pdf"
COMBINED_PDF = ROOT / "output/pdf/MMHK_with_SI.pdf"


def main() -> None:
    tex = TEX.read_text()
    abstract = tex.split(r"\begin{abstract}", 1)[1].split(r"\end{abstract}", 1)[0]
    supplement = (MANUSCRIPT / "supplement_pnas_style.tex").read_text()
    references = (MANUSCRIPT / "references.bib").read_text()
    log = LOG.read_text(errors="replace")
    figure_names = [
        "fig1_multidensity_benchmark.pdf",
        "fig2_mott_zero_mechanism.pdf",
        "fig3_cdw_zero_mechanism.pdf",
        "fig4_scale_and_transition_boundary.pdf",
        "fig2_interaction_axis_finite_tprime_combined_2x4.pdf",
    ]
    supplement_figure_names = re.findall(
        r"\\includegraphics(?:\[[^]]*\])?\{([^}]+\.pdf)\}", supplement
    )

    checks = {
        "revtex_prl_reprint_class": (
            r"\documentclass[aps,prl,reprint,superscriptaddress,"
            r"nofootinbib,longbibliography]{revtex4-1}"
        )
        in tex,
        "five_main_figures": (
            tex.count(r"\begin{figure*}") == 4
            and tex.count(r"\begin{figure}") == 1
            and tex.count(r"\includegraphics") == 5
        ),
        "figures_1_to_5_present": all(name in tex for name in figure_names),
        "main_figures_in_separate_directory": (
            r"\graphicspath{{figures/}}" in tex
            and all((MANUSCRIPT / "figures" / name).is_file() for name in figure_names)
        ),
        "supplement_figures_in_separate_directory": (
            r"\graphicspath{{supp_figures/}}" in supplement
            and all(
                (MANUSCRIPT / "supp_figures" / name).is_file()
                for name in supplement_figure_names
            )
        ),
        "no_input_figures_beside_tex_sources": all(
            not (MANUSCRIPT / name).exists()
            for name in [*figure_names, *supplement_figure_names]
        ),
        "superseded_tprime_figures_removed": (
            "prl_fig5_tprime_bond_resolved.pdf" not in tex
            and "prl_fig6_bond_resolved_mott_charge.pdf" not in tex
            and r"\label{fig:tprime-bond}" not in tex
            and r"\label{fig:bond-resolved-mechanisms}" not in tex
        ),
        "static_evidence_in_supplement": (
            "pnas_fig4_static_branch_crossing.pdf" not in tex
            and "Figs.~S5--S7" in tex
            and r"\label{fig:static-crossing}" not in tex
        ),
        "redundant_asymptotic_supplement_figure_removed": (
            "supp_figS1_asymptotic_mechanisms.pdf" not in supplement
            and r"\label{fig:s-asymptotic}" not in supplement
            and "Supplemental Material, Fig.~S1(d)" not in tex
        ),
        "optional_audits_removed_from_submission": (
            "Figs.~S8 and S12" not in tex
            and "Root-candidate audit" not in tex
            and "Extraction and fit robustness" not in tex
        ),
        "no_unresolved_references": not re.search(
            r"(Citation|Reference).*undefined|There were undefined references",
            log,
        ),
        "no_overfull_boxes": (
            r"Overfull \hbox" not in log and r"Overfull \vbox" not in log
        ),
        "supplement_wording": (
            "SI Appendix" not in tex and "Supplemental Material" in tex
        ),
        "gz_notation": (
            r"\newcommand{\wzero}{\omega_{\mathrm{GZ}}}" in tex
        ),
        "abstract_has_no_abbreviations": (
            all(
                token not in abstract
                for token in [
                    "MMHK", "GZ", "CDW", "AFQMC", "DMET",
                    r"\mathrm{NN}", r"\mathrm{NNN}",
                    r"\wzero", r"\epsk", r"\hk", r"\mmhk",
                ]
            )
        ),
        "main_text_abbreviations_defined": all(
            any(phrase in tex for phrase in alternatives)
            for alternatives in [
                ["A Green-function zero (GZ)", "a Green-function zero (GZ)"],
                [
                    "momentum-mixing Hatsugai--Kohmoto (MMHK)",
                    "momentum-mixing Hatsugai/Kohmoto (MMHK)",
                ],
                [
                    "Hatsugai--Kohmoto (HK) limit",
                    "Hatsugai/Kohmoto (HK) limit",
                ],
                ["nearest-neighbor (NN) repulsion"],
                [
                    "charge-density-wave (CDW) order",
                    "charge-density wave (CDW)",
                    "charge density wave (CDW)",
                ],
                ["next-nearest-neighbor (NNN) hopping"],
                [
                    "reduced Brillouin zone (rBZ)",
                    r"reduced Brillouin zone (${\rm rBZ}_n$)",
                ],
                [
                    r"Hermitian conjugation denoted by $\mathrm{H.c.}$",
                    r"Denoting Hermitian conjugation  $\mathrm{H.c.}$",
                ],
                ["auxiliary-field quantum Monte Carlo (AFQMC)"],
                ["density-matrix embedding theory (DMET)"],
            ]
        ),
        "constrained_path_not_abbreviated": (
            "CP-AFQMC" not in tex
            and "CP-AFQMC" not in supplement
            and "open circles are AFQMC or constrained-path AFQMC" in tex
            and "constrained-path AFQMC" in supplement
        ),
        "signed_zero_offset_coefficient": (
            r"\wzero(\mathbf{k})=s_{\mathrm{NN}}\epsk" in tex
            and r"\wzero(\mathbf{k})=s\epsk" not in tex
            and "is the signed, dimensionless NN coefficient used throughout" in tex
        ),
        "signed_bond_coefficients": (
            r"\wzero^{(U)}(\mathbf{k})=4C_{\mathrm{NN}}\epsk" in tex
            and r"$(-1.4029,0.8355)$ in (c)" in tex
            and r"$(-1.3983,0.7948)$ in (d)" in tex
        ),
        "bond_resolved_formula_and_derivation_present": (
            r"\wzero(\mathbf k)=4\sum_b C_b\varepsilon_b(\mathbf k)"
            in tex
            and "Supplemental Material, Sec.~4" in tex
            and r"\section{Mott-side derivation of the bond-resolved $4\sum_b C_b\varepsilon_b$ rule}"
            in supplement
            and r"\label{eq:s-bond-resolved-result}" in supplement
            and r"\label{eq:s-bond-resolved-boxed}" in supplement
        ),
        "physical_bond_class_notation": (
            all(token not in tex for token in [r"\varepsilon_1", r"\varepsilon_2", "C_1", "C_2"])
            and all(token not in supplement for token in [r"\varepsilon_1", r"\varepsilon_2", "C_1", "C_2"])
            and r"s_{\mathrm{NN}}" in tex
            and r"s_{\mathrm{NNN}}" in tex
        ),
        "doublon_hopping_components_explicit": (
            r"\label{eq:s-explicit-doublon-components}" in supplement
            and r"\mathcal T_{+1}" in supplement
            and r"\mathcal T_{-1}" in supplement
            and r"\mathcal T_0" in supplement
            and r"\bar n_{i\bar\sigma}=1-n_{i\bar\sigma}" in supplement
            and "ordered sum includes both hopping directions" in supplement
        ),
        "schrieffer_wolff_hubbard_reference": (
            r"\cite{macdonald1988tu,auerbach1994interacting}" in supplement
            and "@article{macdonald1988tu" in references
            and "10.1103/PhysRevB.37.9753" in references
            and "@book{auerbach1994interacting" in references
        ),
        "sw_commutator_intermediate_steps": (
            r"[\mathcal T_{+1},\mathcal T_{+1}]" in supplement
            and r"P_0[\mathcal T_{+1},\mathcal T_{-1}]P_0" in supplement
            and r"=-P_0\mathcal T_{-1}\mathcal T_{+1}P_0" in supplement
        ),
        "gnn_defined_before_fourier_use": (
            "g_{\\mathrm{NN}}\n&\\equiv" in supplement
            and supplement.index("g_{\\mathrm{NN}}\n&\\equiv")
            < supplement.index(r"2g_{\mathrm{NN}}(\cos k_x+\cos k_y)")
        ),
        "grand_canonical_hamiltonian_convention": (
            "Throughout this paper, $H$ denotes the full grand-canonical Hamiltonian"
            in tex
            and r"H&=H_t+H_U-\mu N" in supplement
            and r"\mu=U/2" in supplement
            and r"\widetilde H" not in supplement
        ),
        "s31_lehmann_moment_derivation": (
            r"\sum_m(E_m^+-E_0)" in supplement
            and r"\sum_n(E_n^--E_0)" in supplement
            and r"c_{\mathbf k\sigma}[H,c^\dagger_{\mathbf k\sigma}]" in supplement
            and r"\bigl[H,c^\dagger_{\mathbf k\sigma}\bigr]" in supplement
            and "exact first spectral-moment" in supplement
        ),
        "lehmann_green_function_precedes_s31": (
            r"G(\mathbf k,\omega)" in supplement
            and r"\omega-(E_m^+-E_0)+i0^+" in supplement
            and r"\omega+(E_n^--E_0)+i0^+" in supplement
            and supplement.index(r"\omega-(E_m^+-E_0)+i0^+")
            < supplement.index(r"\label{eq:s-commutator-moments}")
        ),
        "s28_to_s29_zeroth_moment_identity": (
            r"w_h-w_p}{2}=n_{\mathbf k\sigma}-\frac12" in supplement
            and r"\langle c^\dagger_{\mathbf k\sigma}c_{\mathbf k\sigma}\rangle"
            in supplement
            and r"\langle c_{\mathbf k\sigma}c^\dagger_{\mathbf k\sigma}\rangle"
            in supplement
        ),
        "charge_side_unit_projector_derivation": (
            r"\langle C|n_{i\sigma}(1-n_{j\sigma})|C\rangle=1"
            in supplement
            and "fluctuating singlet--triplet composition" in supplement
            and "only odd powers occur" in supplement
            and "No spin-correlation factor accompanies it" in tex
        ),
        "no_explicit_main_fit_statistics": (
            "RMSE" not in tex
            and r"R^2" not in tex
            and r"R^{2}" not in tex
        ),
        "pdfs_exist": all(
            path.exists() and path.stat().st_size > 0
            for path in (PDF, OUTPUT_PDF, COMBINED_PDF)
        ),
    }

    main_pages = len(PdfReader(str(PDF)).pages)
    combined_pages = len(PdfReader(str(COMBINED_PDF)).pages)
    report = {
        "main_tex": str(TEX),
        "main_pdf": str(PDF),
        "output_pdf": str(OUTPUT_PDF),
        "combined_main_and_si": str(COMBINED_PDF),
        "main_pages": main_pages,
        "combined_pages": combined_pages,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "editorial_note": (
            "The source uses compact two-column REVTeX styling, but the current "
            f"{main_pages}-page draft still requires substantial text "
            "compression before a PRL-length submission."
        ),
    }
    output = RESULTS / "manuscript_validation_20260731.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not report["all_checks_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
