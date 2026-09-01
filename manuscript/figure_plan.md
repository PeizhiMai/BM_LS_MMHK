# Figure Plan

Updated 2026-08-20 after adding the independent spinless $t$--$V$ benchmark
to the existing Supplemental Material benchmark section. The manuscript uses one fixed
spectral broadening throughout. The primary dynamical object is the
gap-interior Green-function-zero dispersion `omega_GZ(k)`, operationally
defined by the low-weight sign change of `Re G` inside the central gap. All
dynamical figure axes use `omega_GZ(k)/t`; LS-style aliases are not used. For
the nearest-neighbor band, the fitted signed coefficient is `s_NN` in the
zero-offset relation `omega_GZ(k)=s_NN epsilon_NN(k)`. With `t' != 0`, the NN and NNN bond contributions
carry signed coefficients `s_NN` and `s_NNN`; in particular,
`s_NN=4C_NN<0` keeps the antiferromagnetic sign inside the coefficient.

## Five main figures

### Figure 1 — Benchmark across density

- **Artifact:** `figures/pnas_main/fig1_multidensity_benchmark.pdf`
- **Panels:** ground-state energy and double occupancy for `n=1,0.875,0.8`; half-filled magnetization.
- **Encoding:** density is red/blue/purple; MMHK is a filled-circle line; AFQMC or constrained-path AFQMC is an open circle; DMET is an open triangle; every marker is plotted at its exact physical `U/t` with no horizontal offset; the complete legend is one column at the upper left of panel A.
- **Message:** the momentum-mixing resolution captures the interaction and density dependence of established Hubbard observables before it is used to predict Green-function-zero dispersions.

### Figure 2 — Mott-side Green-function-zero mechanism

- **Artifact:** `figures/prl_main/fig2_mott_zero_mechanism.pdf`
- **Panels:** `V=0` spectral maps at `U=8,12,20,40`, extracted zero dispersions, and the estimated `s_NN(U,0)` converging to `4C_NN<0`.
- **Message:** broad Hubbard-band continua coexist with a single-valued gap-interior zero dispersion whose asymptotic coefficient is fixed by the nearest-neighbor spin correlation.

### Figure 3 — CDW-side Green-function-zero mechanism

- **Artifact:** `figures/prl_main/fig3_cdw_zero_mechanism.pdf`
- **Panels:** `U=0` spectral maps at `V=2,5,8,12`, extracted zero dispersions, and the estimated `s_NN(0,V)` converging to `-8/7`.
- **Message:** narrow checkerboard charge-defect bands generate a distinct zero-dispersion coefficient fixed by local defect-energy counting.

### Figure 4 — Scale across the interaction plane

- **Artifact:** `figures/prl_main/fig4_scale_and_transition_boundary.pdf`.
- **Panel A:** estimated signed `s_NN(U,V)` for `U=20,40,80`, compared with the leading finite-`(U,V)` strong-coupling laws.  The Mott curves use only each family's measured `V=0` intercept as a finite-`U` anchor, while the CDW curve is parameter free; neither law is fitted to a finite-`V` coefficient.
- **Panel B:** independently bracketed `(V/U)_c` versus `U/t` for `U/t>=4`.
- **Message:** all three coefficient families reach their largest sampled magnitude at `V/U=1/4` and then switch discontinuously to the first CDW-side branch, while the independently determined first-order boundary approaches the same ratio from above. A concise main-text sentence cites the discontinuous static diagnostics before panel B is discussed; the complete scan is in Supplemental Figures S6--S8 and Table S3.

### Figure 5 — Finite-`t'` interaction-axis sequences

- **Artifact:** `figures/pnas_main/finite_tprime_versions/fig2_interaction_axis_finite_tprime_combined_2x4.pdf`.
- **Top row:** `U=20,V=0` spectra and the `U=8,20,40` GZ sequences for `t'=-0.25t` and `-0.4t`.
- **Bottom row:** `U=0,V=5` spectra and the `V=2,5,8` GZ sequences for the same two hopping ratios.
- **Message:** after establishing the simple NN relation at `t'=0`, further-neighbor hopping shows that the two asymptotic mechanisms resolve the individual hopping bonds even without particle-hole symmetry. The more detailed representative-point and coefficient diagnostics remain supplemental.

## SI Appendix figures

The SI sections follow the order in which they are cited in the main text:
benchmark sources and the independent spinless $t$--$V$ check; direct spectral comparison and occupied-band views; the
shared moment relation; the Mott-side derivation; the merged CDW-side
derivation and bond rule; finite-interaction scans; the finite-`(U,V)`
first-moment derivation and validation; static observables; and
frustrated-hopping robustness. The two
spinless benchmark is Figure S1, and the two occupied-band figures are
therefore Figures S2 and S3.

1. **Spinless $t$--$V$ energy benchmark:** `figures/spinless_tV_pbc_benchmark.pdf`; solid $16$-MMHK markers and open CT-QMC/DMRG markers at the exact physical values $V/t=1,2,4$, with no visual horizontal offset.
2. **On-site lower-band snapshots:** `figures/pnas_supplement/supp_figS3_uonly_lower_band_snapshots.pdf`; occupied bands at `U=8,12,20,40` with an identical `10t` vertical span. The complete spectra are already in main-text Figure 2.
3. **Nearest-neighbor lower-band snapshots:** `figures/pnas_supplement/supp_figS5_vonly_lower_band_snapshots.pdf`; occupied bands at `V=2,5,8,12` with a fixed `3t` span and color upper bound `rho_G=15`. The complete spectra are already in main-text Figure 3.
4. **Finite-interaction spectral reorganization:** `figures/pnas_supplement/supp_figS6_finite_uv_spectral_reorganization.pdf`; fixed `U=40` with `V=0,4,8,12,16,20`.
5. **Full finite-`V` scans:** `figures/luttinger_eta0p05_other_parameter_sets/eta0p05_V_effect_luttinger_dispersion_comparison_evenV.pdf`; even `V` for `U=8,20`, multiples of four for `U=40`. Figures S4 and S5 share one finite-interaction section.
6. **All-momentum static scan:** `figures/fullobs/fullobs_static_scan_U40.pdf`; this and Figures S7--S8 carry the complete static evidence summarized after main-text Figure 4.
7. **Two-dimensional momentum maps and noninteracting reference:** `figures/fullobs/fullobs_nk_maps_U40.pdf`.
8. **Finite-`U,V` strong-coupling validation:** `figures/fullobs/fullobs_strong_coupling_validation_U40.pdf`.
9. **Next-nearest-neighbor-hopping robustness and bond-resolved spin fit:** `figures/pnas_supplement/supp_figS13_tpn25_reproduced.pdf`.

## Machine-readable source artifacts

- `results/pnas_scale_rule_points_eta0p05.csv`
- `results/finite_uv_strong_coupling_validation_eta0p05.csv`
- `results/finite_uv_strong_coupling_validation_eta0p05.json`
- `results/pnas_scale_model_comparison_eta0p05.csv` (historical empirical-model audit)
- `results/pnas_scale_rule_summary_eta0p05.json` (historical empirical-fit summary; not used by the active figure)
- `results/pnas_main_figure_manifest.json`
- `results/pnas_supp_spectral_sequence_windows.json`
- `results/figS2_filtered_candidate_data.csv`
- `results/figS2_selected_comparison_data.csv`
- `results/figS2_selected_half_filling_references.csv`
- `results/figS2_open_marker_inventory.csv`
- `results/figS2_source_filter_audit.json`
- `results/pnas_manuscript_validation_20260714.json`
- `results/additional2_zero_dispersion_scale_fits_eta0p05.csv`
- `results/uonly_asymptotic_scale_decomposition.csv`
- `results/large_uv_luttinger_scale_rule_summary.json`
- `results/zero_branch_robustness_eta0p05.csv`
- `results/nk_metrics.csv`
- `results/nk_path_cuts.csv`
- `results/refined_finite_v_data_availability.csv`
- `results/finite_v_zero_dispersion_claim_status.json`
- `results/fullobs_U40_observable_summary_by_V_20260717_123231.csv`
- `results/fullobs_U40_observable_stats_long_20260717_123231.csv`
- `results/fullobs_U40_data_quality_20260717_123231.json`
- `results/pnas_manuscript_validation_20260717.json`
- `results/fig2_interaction_axis_finite_tprime_combined_2x4_metrics_eta0p05_20260802.csv`
- `results/fig2_interaction_axis_finite_tprime_combined_2x4_manifest_20260802.json`

## Reproducible scripts

- `scripts/refit_pnas_scale_rule.py`
- `scripts/build_pnas_manuscript_figures.py`
- `scripts/build_pnas_spectral_sequence_supplement.py`
- `scripts/validate_pnas_manuscript.py`
- `scripts/analyze_fullobs_u40_scan.py`
- `scripts/build_pnas_submission_packet.py`
- `scripts/build_prl_4fig_finite_tprime_fig2_combined.py`
- Existing extraction/audit scripts remain the source of the underlying root and momentum-distribution tables.
