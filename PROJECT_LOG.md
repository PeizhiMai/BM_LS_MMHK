# Project Log

## 2026-03-16

- Submitted GSE analysis for `t' = -0.25`, `U = 6`.
- Planned for later today: complete all calculations for `t' = 0`, `U = 10`.

## 2026-03-19

- Completed all benchmark calculations for `t' = 0` at `U = 2, 4, 6, 8, 10, 12`, including ground state energy, double occupancy, and magnetism.
- Updated the paper with the comparison figure including all `t' = 0` data for `U = 2, 4, 6, 8, 10, 12`.
- Next: work on `t' = -0.25`, `U = 6`, for both hole-doped and electron-doped cases for potential future use.
- After that: calculate `G` for all of these cases; expected runtime is on the order of a week of CPU time.

## 2026-04-06

- Started runs for `t' = -0.25` at `U = 6, 8, 10, 12`.
- For this set of cases, the insulating phase occurs at half-filling.
- `U = 6` is complete.
- `U = 10` and `U = 12` are about halfway done; the ground state energy has been calculated for all total momenta.

## 2026-06-11

- Refined the project direction.
- Benchmark presentation plan:
  - Use one figure for the benchmark at `t' = 0`.
  - Keep the separate benchmark figure at `t' = -0.25`.
  - Use these to show that our `4x4-MMHK` results match the previous study.
- Main science focus: study the Luttinger surface for the following cases:
  1. `t' = 0`, `U = 8, 12, 20, 40`, `V = 0`
  2. `t' = -0.25`, `U = 8, 12, 20, 40`, `V = 0`
  3. Either:
     - `t' = 0`, `U = 8`, `V = 1, 2, 3, 4`, or
     - `t' = 0`, `U = 20`, `V = 2, 4, 6, 8`
- Additional focus: characterize quantum fluctuations through `n_k` as a function of `k_x` and `k_y`.

## 2026-06-13

- Implemented the manuscript upgrade from placeholders to finite-`V` results.
- Regenerated all primary `eta=0.05` finite-`V` spectral maps and root CSVs with expanded `omega in [-120,120]`, candidate-root lists, clean-candidate lists, and missing-row flags.
  - Complete groups: `U=8,V=1..4`, `U=20,V=2,4,6,8`, `U=40,V=4,8` have `121/121` accepted roots.
  - Incomplete but retained: `U=40,V=12` and `U=40,V=16` have `120/121` accepted roots and one explicit `missing_raw_data` row each.
- Added finite-`V` transition diagnostics:
  - `results/finite_v_ls_transition_metrics.csv`
  - `results/root_multiplicity_flags.csv`
  - `figures/finite_v_luttinger_summary_eta0p05.pdf/png`
  - Main trend: LS affine scale grows below `V/U≈1/4` and drops below the `V=0` scale above it on the available `U=8,20,40` grids.
- Added path-resolved `n(k)` analysis from the raw hole-sector Lanczos norms:
  - `scripts/compute_nk_maps.py`
  - `results/nk_metrics.csv`
  - `results/nk_path_cuts.csv`
  - `figures/nk_fluctuation_summary.pdf/png`
  - Note: current Green-function raw files support Gamma-X-M-Gamma path cuts, not full 4x4 BZ heat maps.
- Added LS scale/broadening summary:
  - `scripts/ls_scale_summary.py`
  - `results/ls_noninteracting_scale_summary.csv`
  - `figures/ls_scale_vs_u_eta_robustness.pdf/png`
- Added `scripts/finite_v_transition_diagnostics.py` and `scripts/cluster_convergence_summary.py`.  The latter records which requested 1x1/2x2/4x4-ED convergence values are not available in the current checkout.
- Staged the refined boundary grid for future CADES runs at `scripts/cades_queue/UVset_refined_U20_boundary_20260613.txt` with `(20,4.5),(20,5),(20,5.5)`.
- Rewrote `manuscript/main.tex` to define the MMHK construction from `../ML_MMHK/create_code/*_UV.cc`, promote finite-`V` LS figures, replace the `n(k)` placeholder with the path-resolved diagnostic, retire the “98% Mottness” slogan, and add the needed Luttinger-surface/extended-Hubbard references.

## 2026-06-15

- Downloaded requested `U=0`, `V=4,8,12`, `tp=0`, `Q=0,0` Lanczos raw Green-function data from CADES Gcalpath into `data/Gcalpath/Lanczos_raw_data` add-only; all three groups are complete (`240/240` Gh/Gp files, `120/120` unique raw pairs, `121/121` path rows).
- Extracted eta=0.05 Luttinger surfaces with enlarged `omega in [-120,120]`:
  - `figures/luttinger_eta0p05_U0_finiteV/rhoG_LS_all_other_parameter_sets_eta0p05.pdf/png`
  - `figures/luttinger_eta0p05_U0_finiteV/u0_v_luttinger_surface_overlay_eta0p05.pdf/png`
  - `data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV/*_roots.csv`
  - `results/u0_finite_v_luttinger_surface_metrics.csv`
- Result: all three U=0 finite-V groups have `121/121` clean roots; the LS dispersion is nearly V-independent over `V=4,8,12` with bandwidth about `9.13--9.14`.

## 2026-06-16

- Implemented the critic-response pass for takeaways 1--4 with all manuscript results fixed at `eta=0.05`.
- Added conservative finite-`V` diagnostics:
  - `scripts/compute_finite_v_charge_diagnostics.py`
  - `scripts/update_refined_finite_v_zero_metrics.py`
  - `results/finite_v_charge_diagnostics.csv`
  - `results/refined_finite_v_data_availability.csv`
  - `results/finite_v_zero_dispersion_claim_status.json`
  - `figures/finite_v_zero_dispersion_diagnostics_eta0p05.pdf/png`
- Added fixed-`eta=0.05` branch robustness audit:
  - `scripts/audit_zero_branch_tracking.py`
  - `results/zero_branch_robustness_eta0p05.csv`
  - `figures/zero_branch_candidate_audit_eta0p05.pdf`
  - Audited high-multiplicity cases: `(8,1)`, `(8,2)`, `(20,4)`, `(20,6)`, `(40,8)`, `(40,12)`.
- Updated `results/finite_v_ls_transition_metrics.csv` with joined diagnostic/status columns while preserving explicit missing-row flags for incomplete raw groups.
- Reframed the manuscript terminology from finite-frequency “Luttinger surface” language to the safer primary term “Green-function-zero dispersion” `omega_0(k)`, defined by `Re G(k,omega_0)=0` inside the central gap.
- Current limitation recorded in manuscript and CSVs: true sector scans, charge gaps, and `S_c(pi,pi)` are not available in the current Green-function raw files; the refined boundary points `(20,4.5)`, `(20,5)`, `(20,5.5)`, `(40,9)`, `(40,10)`, `(40,11)`, `(80,16)`, `(80,20)`, `(80,24)` are still absent locally.

## 2026-06-16 queue automation update

- Dropped priority-2 recommendation `(0,16)` from `results/recommended_large_uv_rule_points.csv` because `U=0,V=16` is already included in the current/failed-case job set.
- Updated the hourly CADES GUV monitor automation so that, after all main `GUV` jobs finish, it runs `generate_jobs_G_UV.sh` in CADES Gcalpath to check whether additional jobs/templates are needed, without submitting them automatically.
- The automation is instructed to ignore the special failed `U=0,V=16,k=(30,30)` case because it is handled separately in `failed_GUV_cases*`.

## 2026-07-14 — PNAS-style manuscript upgrade

- Reviewed all 73 locally available papers in `references/pnas_80_papers_20260703` as structural exemplars; recorded the corpus and claim audit in `notes/pnas_corpus_audit_and_revision_20260714.md`.
- Ran balanced-harsh baseline and final critic passes:
  - `notes/pnas_level_critic_before_20260714.md`
  - `notes/pnas_level_critic_after_20260714.md`
- Refreshed the finite-interaction availability/claim files and refit the `U>=20` scale data with leave-one-`U`-family-out selection and stratified bootstrap:
  - Mott side: `s=s(U,0)/(1-lambda V/U)`, `lambda=0.84446`.
  - Charge side: `s=8/7+beta[U/(4V)]^2`, `beta=0.18467`.
  - Complete-path-only values are `lambda=0.83614`, `beta=0.18183`; minimum path coverage is `111/121`.
- Added reproducible scripts and outputs:
  - `scripts/refit_pnas_scale_rule.py`
  - `scripts/build_pnas_manuscript_figures.py`
  - `scripts/validate_pnas_manuscript.py`
  - `results/pnas_scale_model_comparison_eta0p05.csv`
  - `results/pnas_scale_rule_points_eta0p05.csv`
  - `results/pnas_scale_rule_summary_eta0p05.json`
  - `results/pnas_manuscript_validation_20260714.json`
- Rebuilt the main hierarchy as four figures under `figures/pnas_main/`: asymptotic mechanisms, finite-`U,V` spectral reorganization, scale across the interaction plane, and independent robustness.
- Rewrote `manuscript/main_pnas_style.tex` around the zero-dispersion discovery; restored actual authors/affiliation; replaced reference holders; added the explicit finite-resolution interaction Hamiltonian and controlled first-moment language.
- Created `manuscript/supplement_pnas_style.tex` with relocated benchmarks/scans/audits, missing-row sensitivity, `t'` robustness, and detailed `4C_1` and `8/7` derivations.
- Created the separate 111-word Significance Statement and a 158-word abstract.
- Created `references/mmhk_reference_download_links.md`; no additional papers were downloaded.
- Compiled and visually inspected all PDF pages. No unresolved citations, placeholders, missing figures, visible internal paths, or prohibited MMHK finite-system wording remain.
- Remaining scientific requests identified by the final critic are new-calculation items rather than writing defects: broadening-to-zero behavior, a higher interaction resolution, and direct charge/sector diagnostics near the boundary.

## 2026-07-17 — All-momentum observables and PNAS manuscript enrichment

- Validated and analyzed 7,736 completed all-twist ground-state outputs at `U=40`, `t'=0`, `Q=(0,0)` for `V=0,4,8,9,10,11,12,16,20`.
  - Seven interaction sets are complete (`861/861` wedge rows).
  - `V=16` and `20` have 99.75% and 98.69% quadrature coverage; no missing row is imputed in averages.
  - SHA-256 checks, unique parameter keys, physical ranges, and four exact observable identities pass; the maximum energy-identity residual is `2.2e-10`.
- Direct equal-time observables identify a collective branch crossing between `V=10` and `11`:
  - `D_i: 0.005155 -> 0.497100`
  - `m_CDW^2: 0.001297 -> 0.989141`
  - `C_1: -0.345285 -> -0.001083`
  - `Szz(pi,pi): 1.455514 -> 0.002888`
  - `2<ni nj>_NN: 1.994840 -> 0.020273`
- The Hellmann--Feynman derivative discontinuity establishes a first-order branch crossing for the present sector Hamiltonian. Local tangent integration gives `V_c=10.01535`, `V_c/U=0.25038366`, while the direct grid establishes `10<V_c<11`.
- Full two-dimensional `n(k)` maps follow two parameter-free virtual-hopping denominators:
  - Mott side: `n(k)=1-[4(1/4-C1)/(U-V)] epsilon_k`
  - charge side: `n(k)=1-[2/(7V-U)] epsilon_k`
  - maximum slope errors are 1.44% and 0.68%, respectively.
- Rebuilt the PNAS main Figure 4 as direct charge/spin/energy-derivative/`n_Gamma` evidence and moved the former extraction robustness summary to the SI.
- Expanded `manuscript/supplement_pnas_style.tex` with:
  - all-momentum aggregation and completeness;
  - full `n(k)` maps plus the noninteracting reference;
  - `4x2` unrestricted full-ED operator validation;
  - finite-`U,V` strong-coupling formulas for energy, kinetic energy, double occupancy, density bonds, and `n(k)`.
- Rewrote the abstract, Significance Statement, Results, Discussion, and Methods to incorporate the direct first-order signature while retaining the scope of the present interaction resolution.
- Validation passes: 161-word abstract, 113-word Significance Statement, one main-text broadening mention, no unresolved references or placeholders, and every quoted number matched to CSV/JSON.
- Final PDFs:
  - `output/pdf/MMHK_PNAS_enriched_20260717_main_and_SI.pdf` (24 pages)
  - `output/pdf/MMHK_PNAS_enriched_20260717_full_packet.pdf` (25 pages)

## 2026-07-24 — Supplemental multi-density benchmark

- Kept the script-generated half-filled benchmark as Fig. S1.
- Reproduced the original three-panel benchmark presentation from machine-readable tables and added it as Fig. S2:
  - MMHK at `n=1`, `0.875`, and `0.8`;
  - half-filled AFQMC and DMET references;
  - ground-state energy, double occupancy, and magnetization.
- Added `pnas_supp_figS2_multidensity_benchmark.pdf/png` to the reproducible supplemental-figure builder and provenance audit.
- Renumbered the subsequent SI figures through Fig. S11 and updated all hard-coded main-text SI citations.
- Recompiled the main text and SI, rebuilt the review packet, and passed manuscript, figure-provenance, source-grid, citation, and path validation.

## 2026-07-24 — Updated V-only row of Fig. S4

- Downloaded the complete `U=0,V=2` and `U=0,V=5`, `t'=0`, `Q=(0,0)` Lanczos Green-function sets from CADES into `data/Gcalpath/Lanczos_raw_data` using an add-only transfer:
  - `240/240` files and `120/120` unique `Gh/Gp` pairs for each interaction;
  - no local filename conflicts and no remotely present files missing after transfer.
- Recomputed the spectral maps and gap-interior zero dispersions at the manuscript broadening:
  - both new groups have `121/121` accepted roots;
  - zero-offset scales are `1.135996` at `V=2` and `1.141690` at `V=5`.
- Rebuilt Fig. S4 so that panels D and E use `V=2` and `V=5`, while panel F compares `V=2,5,8`.
- The panel-F zero-offset reference is fitted to `V=8`, giving `alpha_V=1.142398` (caption: `1.14240`) with RMSE `2.68e-4`.
- Updated the SI caption, fit CSV, figure provenance, and validation checks; recompiled the 16-page SI and rebuilt the current main-plus-SI and full submission packets.

## 2026-07-25 — Condensed density benchmark

- Replaced the earlier `3x3` density-comparison layout with a three-panel Fig. S2:
  - ground-state energy for `n=1,0.875,0.8`;
  - double occupancy `D` for the same three densities;
  - magnetization restricted to `n=1`.
- Panels A and B retain all compatible AFQMC/CP-AFQMC and DMET comparisons assembled in `results/away_half_filling_comparison_data.csv`, including open flagged/stripe-resolved/finite-embedding values.
- Panel C omits doped MMHK curves as well as doped external points because the available doped magnetic observables are not directly comparable to the present scalar estimator.
- Consolidated the density and method legend in panel A, updated the SI discussion and caption, and preserved Fig. S1 as the dedicated half-filled validation.
- Added an explicit open-symbol legend key: open external markers denote flagged extrapolations, stripe/system-resolved values, or finite-embedding results rather than compact benchmark estimates.
- Recompiled and visually inspected the SI page, rebuilt the current submission packets, and passed manuscript and figure-provenance validation.

## 2026-07-27 — Strict finite-reference filter for Fig. S2

- Removed all doped thermodynamic-limit extrapolations from Fig. S2, including
  the previously flagged DMET rows.
- Restricted the doped CP-AFQMC comparison to the 16 explicitly TABC
  system-resolved rows from Zheng et al.; excluded non-TABC and BCS-state
  calculations.
- Replaced the mixed-size DMET embedding set with 11 unextrapolated `4x4`
  ancillary values from LeBlanc et al. (eight energies and three double
  occupancies).
- Added `results/figS2_filtered_comparison_data.csv`,
  `results/figS2_open_marker_inventory.csv`, and
  `results/figS2_source_filter_audit.json` so the source-selection rules are
  machine checked.

## 2026-07-27 — Two-panel scale and transition-boundary figure

- Added `scripts/build_scale_and_transition_figure.py`.
- Panel A reproduces the current main Figure 3 from the scale-point CSV and
  constrained-fit JSON.
- Panel B plots the independently bracketed critical ratio `(V/U)_c` versus
  `U_c/t`, restricted to `U_c/t>=4`, with bracket half-widths and distinct
  markers for full 861-twist grids and five-twist refinements.
- Wrote the exact plotted boundary subset to
  `results/transition_brackets_Uge4_for_combined_figure.csv`.
- Promoted this two-panel artifact to the canonical manuscript Figure 3 and
  updated its main-text discussion, caption, generator manifest, provenance,
  and validation checks.
- Expanded the Fig. S2 benchmark explanation with a seven-row source table
  that accounts for all 27 open markers by density, interaction, finite
  geometry, stripe wavelength, observable, and method.

## 2026-07-27 — Largest-system and energy-paired Fig. S2 references

- Deduplicated the strict Fig. S2 literature set after preserving the
  27-row candidate table for audit:
  - at each doped `(n,U)`, retained only the largest finite CP-AFQMC TABC
    system (`20x8`);
  - compared that retained CP-AFQMC energy with the unextrapolated `4x4`
    DMET energy and plotted the lower value;
  - paired double occupancy with the selected energy's method and system
    whenever available.
- The final doped comparison contains 12 open markers: nine energies and
  three double occupancies. Two double occupancies correspond exactly to
  selected DMET energies. The sole fallback is the same-parameter `4x4`
  DMET value at `(n,U/t)=(0.875,8)`, where the selected `20x8` CP-AFQMC
  energy has no reported double occupancy. No value is borrowed across
  interaction or density.
- Applied the same lowest-energy/corresponding-double-occupancy rule to the
  half-filled energy and double-occupancy references: DMET is selected at
  `U/t=2,4`, and AFQMC at `U/t=6,8,12`. Both direct magnetization series are
  retained.
- Added candidate, selected, half-filled pairing, open-marker inventory, and
  JSON audit outputs; updated the SI text/table, figure provenance, and
  manuscript validation accordingly.

## 2026-07-27 — Promoted the interaction-axis comparison to Figure 2

- Promoted the former six-panel Fig. S4 to the canonical main-text Figure 2:
  - upper row: `U`-only spectra at `U=8,20` and zero dispersions at
    `U=8,20,40`;
  - lower row: nearest-neighbor-only spectra at `V=2,5` and zero dispersions
    at `V=2,5,8`;
  - zero-offset fits give `alpha_U=1.39286` and `alpha_V=1.14240`.
- Wrote the promoted artifact as
  `figures/pnas_main/pnas_fig2_interaction_axis_comparison.pdf` and its fit
  data as `results/pnas_fig2_axis_fit_metrics.csv`.
- Moved the former main Figure 2 (`U=40`, `V=0,8,12,16`) into the vacated
  Figure S4 slot as
  `figures/pnas_supplement/pnas_supp_figS4_finite_uv_spectral_reorganization.pdf`.
  Later SI figure numbers therefore remain unchanged.
- Updated main/SI prose, captions, manifests, provenance, and validation.

## 2026-07-27 — Simplified the three-panel density benchmark

- Reworked Fig. S2 with one consistent visual grammar suitable for eventual
  promotion to a main-text three-panel figure:
  - color encodes density (`n=1` red, `n=0.875` blue, `n=0.8` purple);
  - filled circles connected by lines denote MMHK;
  - open circles denote AFQMC/CP-AFQMC;
  - open triangles denote DMET.
- Removed the previous method-specific colors and density-specific MMHK marker
  shapes, reducing the figure to two external-reference marker shapes.
- The distinct density colors make the doped double-occupancy groups
  unambiguous without additional text labels.
- Put the complete panel-A legend in one column at the upper left and removed
  the long in-figure methodological footnote; the selection details remain in
  the caption, table, and machine-readable audit.

## 2026-07-27 — Promoted the density benchmark to Figure 1

- Promoted the condensed three-panel density benchmark to canonical main-text
  Figure 1 as `figures/pnas_main/pnas_fig1_multidensity_benchmark.pdf`.
- Kept Figures 2--4 unchanged so the main hierarchy is now benchmark,
  interaction-axis limits, scale/boundary, and static branch crossing.
- Moved the former main Figure 1 to SI Figure S2 as
  `figures/pnas_supplement/pnas_supp_figS2_asymptotic_mechanisms.pdf`.
- Retained the detailed reference-selection table in the SI and updated the
  manuscript, figure manifests, provenance map, and validation rules.

## 2026-07-27 — Rebuilt SI spectral sequences and lower-band snapshots

- Rebuilt Figure S3 as only the four `V=0` spectral panels at
  `U/t=8,12,20,40`; removed the former overlay and fit panels E and F.
- Added Figure S4 for the nearest-neighbor-only sequence at
  `V/t=2,5,8,12`, using `V/t=12` as the requested point above 8.
- Added Figures S5 and S6 as occupied-band crops of Figures S3 and S4.
  Every panel has the same `10t` vertical span, while its absolute energy
  window follows the corresponding lower-band weight.
- Renumbered the previous Figures S4--S11 to S7--S14 and updated every
  main-text/SI reference, filename, manifest, provenance entry, and validation
  rule.

## 2026-07-29 — General MMHK Hamiltonian and unified zero scale

- Replaced the finite-grid density-form Hamiltonian in
  `manuscript/main_prl_current.tex` by the general `n`-MMHK sector
  Hamiltonian, with the common mixed momentum `f` explicit on the kinetic,
  on-site, nearest-neighbor, and number operators.
- Specialized the general construction to the `4x4` (`n=16`) interaction
  resolution used here and wrote its compact internal-coordinate hopping
  representation for both `t` and `t'`.
- Standardized the Green-function-zero scaling factor to `s` in the active
  manuscript and Figures 2--4; removed the separate `alpha_U` and `alpha_V`
  notation and point-by-point scale lists from the prose.
- Expanded the main-text strong-coupling intuition: an `O(t/U)` or `O(t/V)`
  spectral-weight imbalance multiplies an `O(U)` or `O(V)` sector separation,
  leaving an order-`t` zero dispersion. The spin-side cancellation gives
  `4 C_1`, while checkerboard defect counting gives `(1/7V)(8V)=8/7`.
- Recompiled and visually checked the nine-page main manuscript and 20-page
  SI with no overfull boxes or unresolved references; refreshed
  `output/pdf/MMHK_PRL.pdf` and `output/pdf/MMHK_PRL_with_SI.pdf`.

## 2026-07-29 — Expanded the SI derivation from Eqs. S13 to S15

- Kept the numbered results S13--S15 fixed while adding the intervening
  commutator, first-moment sum-rule, particle--hole-symmetry, and
  weight-normalization algebra as unnumbered equations.
- Made explicit that the weighted moments are
  `U/4 + epsilon_k/2` and `-U/4 + epsilon_k/2` to leading order, and that
  division by the unequal particle/hole weights shifts both normalized
  sector centers by the same spin-correlation term.
- Displayed the final cancellation term by term: the two spin-independent
  `1/2` contributions cancel, whereas the two `2 C_1` contributions add to
  the `4 C_1` Green-function-zero dispersion.
- Recompiled and visually checked SI pages 17--18 with no LaTeX warnings and
  refreshed `output/pdf/MMHK_PRL_with_SI.pdf`.

## 2026-07-31 — Bond-resolved fit for the frustrated U-only zero dispersion

- Refit all four complete `t'=-0.25`, `V=0`, `eta=0.05` zero curves
  (`U/t=8,12,20,40`; 121/121 path points each) with separate nearest- and
  next-nearest-neighbor harmonics.
- Found that one scale multiplying the complete bare `t-t'` band is invalid:
  at `U=40` its RMSE is `1.4248t`.  The minimal bond-resolved fit
  `E_GZ=-lambda1 epsilon1+lambda2 epsilon2+delta` gives
  `(lambda1,lambda2,delta/t)=(1.3911,0.8346,0.0001)`, RMSE `0.0303t`, and
  `R^2=0.99993`.
- Exactly diagonalized the periodic `4x4` leading strong-coupling `J1-J2`
  spin model with `J2/J1=(t'/t)^2=1/16`.  The resulting
  `(C1,C2)=(-0.3507319025,0.2088713786)` predicts the two amplitudes without
  fitting: `4|C1|=1.4029276100` and `4C2=0.8354855142`, within `0.8462%` and
  `0.1073%` of the `U=40` extraction.
- Generalized the first-moment result bond by bond to
  `E_GZ(k)=4 sum_r C_r epsilon_r(k)+O(t_max^2/U)`.  The NN harmonic is
  inverted because `C1<0`, while the diagonal harmonic is not inverted
  because `C2>0`; this explains the failure of a global bare-band scale.
- Added `scripts/fit_tpn25_zero_dispersion.py`, machine-readable fit/curve/spin
  tables, a summary JSON, a diagnostic figure, and a detailed report.  Updated
  SI Figure S13 and its discussion, then recompiled the 21-page SI without
  unresolved references or LaTeX warnings.

## 2026-07-31 — Promoted the bond-resolved result to main-text Figure 5

- Added the frustrated-hopping result immediately after the Figure 4
  scale/boundary discussion in `manuscript/main_prl_current.tex`; the former
  static-observable Figure 5 is now Figure 6.
- Created the canonical three-panel artifact
  `figures/prl_main/prl_fig5_tprime_bond_resolved.pdf`, showing the failure of
  a single bare-band scale, convergence of `s_NN` and `s_NNN`, and the fit-error
  hierarchy.
- Added the bond-resolved strong-coupling identity
  `omega_GZ(k)=4 sum_r C_r epsilon_r(k)+O(t_max^2/U)` and compared it with the
  `J1-J2` spin ground state at `J2/J1=1/16`.
- Added Han et al. (NJP 18, 103004) and Stepanov et al. (PRB 110, L161106) to
  the manuscript literature context. Their spin-renormalized zero dispersions
  motivate the comparison, while the present result supplies the explicit
  equal-time `4 C_r` coefficient and its bond-by-bond test.
- Recompiled and visually inspected the active PRL-style manuscript and the
  21-page Supplemental Material; all citations and figure references resolve.

## 2026-07-31 — Expanded the S5-to-S6 Hellmann--Feynman derivation

- Expanded the spin-side derivation in both
  `manuscript/supplement_pnas_style.tex` and
  `manuscript/supplement_zero_scale_derivation.tex`.
- The text now introduces a bond-resolved hopping parameter, derives the
  Hellmann--Feynman identity explicitly from the differentiated eigenvalue
  expectation, explains why no separate derivative of the spin correlator
  appears, and tracks the two spin and two hopping-direction factors that
  convert the bond kinetic expectation into Eq. S6.
- Preserved the intended numbering: Eq. S5 defines the nearest-neighbor spin
  correlator and Eq. S6 gives the corresponding one-body bond coherence.
- Standing manuscript-build rule: after every manuscript or Supplemental
  Material source change, recompile all seven TeX entry points and rebuild all
  current PNAS, PRL, four-figure PRL, and legacy main-plus-supplement PDFs.

## 2026-07-31 — Added the canonical transformation preceding Eq. S5

- Expanded both Supplemental Material sources with the explicit
  Schrieffer--Wolff transformation from the half-filled Hubbard model to the
  nearest-neighbor Heisenberg background.
- Decomposed hopping into doublon-number-changing operators
  `T_{-1}, T_0, T_{+1}`, specified the anti-Hermitian generator, carried the
  Baker--Campbell--Hausdorff expansion through second order, and projected onto
  the singly occupied subspace.
- Evaluated the surviving bond operator as the singlet projector to obtain
  `H_spin=(4t^2/U) sum_<ij> (S_i.S_j-1/4)`, thereby establishing the spin
  background whose nearest-neighbor correlator is defined in Eq. S5.
- Kept all added intermediate equations unnumbered so that Eqs. S5--S7 retain
  their established numbering. Rebuilt every manuscript entry point and all
  current combined review/submission PDFs without unresolved references.

## 2026-07-31 — Numbered and labelled every Supplemental equation

- Corrected the malformed literal `qquad` in the canonical-transformation
  Hamiltonian to the LaTeX spacing command `\qquad` in both Supplemental
  sources.
- Converted every displayed equation in `supplement_pnas_style.tex` and
  `supplement_zero_scale_derivation.tex` to a numbered equation and assigned
  each a unique semantic `\label{...}` key.
- The integrated SI now contains a continuous sequence of 51 labelled
  equations, S1--S51. The standalone derivation note contains 39 labelled
  equations with its own S-prefixed sequence.
- Because all intermediate derivation steps are now numbered, the former
  S5--S7 numbering is intentionally superseded; all internal references use
  LaTeX labels and resolve to the new numbers automatically.
- Recompiled all seven TeX entry points, visually checked the corrected
  canonical-transformation pages, and rebuilt every current combined PDF.

## 2026-07-31 — Condensed the static crossing into a five-figure main text

- Removed the former main-text Figure 6 and its long equal-time-observable
  subsection from `manuscript/main_prl_current.tex`; the active hierarchy is
  now Figures 1--5, ending with the bond-resolved frustrated-hopping result.
- Added a compact, independent static-evidence paragraph immediately after
  Figure 4. It retains the direct `10.01 < V_c < 10.02` bracket, the
  Hellmann--Feynman discontinuity, simultaneous charge/spin reorganization,
  and the `U-V` versus `7V-U` momentum-distribution denominators.
- Kept the detailed static scans, two-dimensional `n(k)` maps, boundary table,
  and strong-coupling tests in Supplemental Figures S9--S11 and Table S3;
  the finite-`U,V` momentum-distribution equations now appear only there.
- Preserved the root-rule and missing-row audit as a short main-text check,
  with its full evidence in Supplemental Figures S8 and S12 and Table S2.
- Updated the figure plan, manuscript-version note, and active PRL validation
  script. Recompiled all seven TeX entry points and rebuilt the current PNAS,
  active PRL, original four-figure PRL, and legacy review PDFs. The active
  manuscript is 9 pages (30 with the 21-page supplement), with no unresolved
  references or overfull boxes; all validation checks pass.

## 2026-07-31 — Adopted signed bond-resolved GZ coefficients

- Replaced the positive-amplitude convention
  `omega_GZ=-s_NN epsilon_1+s_NNN epsilon_2+delta` by the signed convention
  `omega_GZ=s_NN epsilon_1+s_NNN epsilon_2+delta` in the active manuscript,
  Supplemental Material, fit report, data products, and plotting scripts.
- The nearest-neighbor coefficient now carries its known antiferromagnetic
  sign explicitly: at `U=40`, `s_NN=-1.3911`, while the strong-coupling value
  is `s_NN=4C_1=-1.4029`. The diagonal coefficient remains
  `s_NNN=+0.8346`, approaching `4C_2=+0.8355`.
- Regenerated main-text Figure 5 with a signed coefficient axis and dashed
  `4C_1<0` and `4C_2>0` references. The fit, residuals, and physical content
  are unchanged; the revision only makes the bond-correlation signs explicit.

## 2026-07-31 — Removed explicit fit statistics from the main narrative

- Removed all explicit RMSE and `R^2` values from the active main text and
  replaced percentage-level fit comparisons by the physical statement that
  the extracted signed bond coefficients approach `4C_1` and `4C_2`.
- Simplified main-text Figure 5 from three panels to two: the visible
  dispersion comparison and the signed NN/NNN coefficient convergence. The
  statistical model-comparison panel is now generated only as a separate
  analysis artifact, while numerical diagnostics remain in the Supplemental
  Material, report, and machine-readable tables.
- Rewrote the Figure 5 discussion around the physical sign structure:
  antiferromagnetic NN correlations invert the NN harmonic, whereas positive
  same-sublattice NNN correlations preserve the NNN harmonic.

## 2026-07-31 — Removed the redundant independent-fit curve from Figure 5

- Removed the independent NN+NNN-fit curve from main-text Figure 5A.
- The panel now makes the physics comparison directly: extracted GZ
  dispersion, the visibly inadequate one-scale bare-band result, and the
  parameter-free `4C_1 epsilon_1 + 4C_2 epsilon_2` spin-correlation result.
- Retained the independently extracted signed coefficients in Figure 5B to
  show their convergence toward `4C_1` and `4C_2`; the detailed independent
  fit remains available only as a diagnostic outside the main figure.

## 2026-07-31 — Reduced Figure 5 to the parameter-free spin comparison

- Removed the former coefficient panel and the one-scale bare-band curve from
  main-text Figure 5. The main figure is now a single-column, single-panel
  comparison between the extracted `U=40`, `t'=-0.25t` GZ dispersion and
  `4C_1 epsilon_1 + 4C_2 epsilon_2`.
- Rewrote the main frustrated-hopping section to derive the bond-resolved
  expression directly, without introducing an independent NN+NNN fit or fit
  coefficients in the main narrative.
- Retained coefficient extraction and model diagnostics outside the main
  figure. A future `V`-only result can occupy the companion Figure 5 panel.

## 2026-07-31 — Launched the V-only / second-t-prime GZ test as the priority CADES batch

- Restored the approved implementation plan at
  `notes/2026-07-31_vonly_tprime_zero_dispersion_plan.md` and added the
  reproducible CADES setup script
  `scripts/cades_queue/setup_vonly_tprime_zero_dispersion.py`.
- Created and compiled the dedicated CADES batch
  `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_tprime_scan` for exactly
  `(U,V,t')=(40,0,-0.4),(0,8,-0.25),(0,8,-0.4)`: 120 unique
  `Gamma-X-M-Gamma` momenta per set, 360 targets, and 720 expected raw files.
  Jobs use 32 tasks, 100 GB, 8 h, `steps_max=1000`, and self-refilling caps of
  40 on `ccsd` and 60 on `cnms`.
- Added pair validation that requires matching metadata, `Q=(0,0)`, finite
  positive norm, and exactly 999 stored `a` plus 999 stored `b` continued-
  fraction coefficients in both `Gh` and `Gp`. The batch includes isolated
  fresh-seed repair jobs and an auditable submission ledger.
- Verified no planned filename conflicts locally or in the original CADES
  `Gcalpath` directory. Downloaded the already-existing `U=0`, `t'=0`,
  `V=16,20` sets add-only (480 files) and verified zero missing files.
- Added the general single-group fitter
  `scripts/fit_bond_resolved_zero_dispersion.py` and the complete planned
  multi-group analysis/figure driver
  `scripts/analyze_bond_resolved_zero_theorem.py`. Outputs are staged for
  generation after the new raw data finish; both positive-amplitude and
  signed-NN conventions are retained so the active manuscript keeps its
  signed bond-coefficient notation.
- Priority-paused only the older full-861 batch's pending work. A marker blocks
  its automatic refill; 101 old pending jobs were placed on reversible Slurm
  hold, while three jobs that began during the hold race and all previously
  running jobs were deliberately left running. The exact IDs and resume state
  are recorded remotely in `priority_pause_state.json`. The new batch was then
  submitted at 40 `ccsd` plus 60 `cnms` jobs and is monitored every two hours.

## 2026-07-31 — Adopted journal-neutral filenames and clarified the bond prefactor

- Renamed the active source from `manuscript/main_prl_current.tex` to
  `manuscript/main_current.tex` and the canonical review PDFs to
  `output/pdf/MMHK.pdf` and `output/pdf/MMHK_with_SI.pdf`. Older active aliases
  carrying `PRL` were archived; the preserved historical four-figure PRL and
  PNAS versions remain separate snapshots.
- Renamed the active validator to `scripts/validate_manuscript.py` and its
  output to `results/manuscript_validation_20260731.json`. The rebuilt
  nine-page main PDF and 31-page main-plus-Supplemental-Material PDF pass all
  checks, including resolved citations/references and no overfull boxes.
- Clarified in the main text and Supplemental Material that the factor `4` in
  `omega_GZ = 4 sum_r C_r epsilon_r` comes from the two complementary
  first-moment contributions, not from shell coordination. Coordination is
  already contained in `epsilon_r(k)`, so a third hopping shell contributes
  `4 C_3 epsilon_3`, not `8 C_3 epsilon_3`.

## 2026-07-31 — Streamlined the submitted Supplemental Material

- Removed the submitted sections `Root-candidate audit` and `Extraction and
  fit robustness`, together with their former Figs. S8 and S12. The remaining
  figures were renumbered consecutively: the all-momentum static, momentum-map,
  strong-coupling, and frustrated-hopping figures are now S8--S11.
- Removed the corresponding audit paragraph from the active main text and
  updated every Supplemental Material cross-reference. The production root-
  tracking definition remains in Materials and Methods, while model selection
  and missing-row sensitivity remain in submitted Table S2.
- Preserved the omitted text and both figures in the standalone three-page
  referee-response backup
  `manuscript/referee_backup_zero_extraction_robustness.tex` and its PDF. The
  original generated figures, scripts, and machine-readable audit results were
  retained unchanged.
- Rebuilt all manuscript entry points and review packets. The current main
  manuscript remains nine pages; the submitted supplement is now 21 pages and
  the combined review PDF is 30 pages. Both the neutral active validator and
  the PNAS validator pass without unresolved references or overfull boxes.

## 2026-07-31 — Promoted the bond-resolved spin rule and completed its derivation

- Displayed the leading strong-coupling formula
  `omega_GZ(k) = 4 sum_r C_r epsilon_r(k)` explicitly in the active main text,
  with the correction order and the definitions of `C_r` and `epsilon_r` kept
  in the surrounding prose. The main text now points directly to Supplemental
  Material Sec. 11.
- Retitled Sec. 11 as the spin-side derivation of the bond-resolved rule and
  added a shell-by-shell extension of the existing nearest-neighbor argument:
  Schrieffer--Wolff plus Hellmann--Feynman gives the bond coherence, its Fourier
  transform gives the particle--hole weight imbalance, and the normalized
  first moments give the sector center. Substitution into the shared two-sector
  zero identity yields the displayed sum over hopping shells.
- Made explicit that the two correlation-dependent first-moment terms add to
  `4 C_r`, while the spin-independent halves cancel. Shell coordination is
  already contained in `epsilon_r(k)` and does not alter the common factor 4.
- Rebuilt and visually inspected the main formula and Sec. 11 derivation. The
  active manuscript remains nine pages, the supplement remains 21 pages, and
  all active validation checks pass.

## 2026-07-31 — Matched Fig. S11 to Fig. 2 and resolved the doublon hopping

- Rebuilt Fig. S11 with the same geometry as main-text Fig. 2: a compact
  two-by-two block of spectral maps in the first two columns, the two analysis
  panels stacked in the third column, and one horizontal color bar above the
  spectral block. The generated figure remains fully script-reproducible.
- Expanded Supplemental Material Eq. S12 by writing the three projected
  hopping operators explicitly in creation and annihilation operators. The
  ordered-bond convention includes both hopping directions, so no separate
  Hermitian-conjugate term is needed.
- Clarified that `T_{+1}` creates a virtual doublon--holon pair, `T_{-1}`
  removes it, and the two terms of `T_0` preserve doublon number by moving an
  existing doublon or an electron in the no-doublon sector. The standalone
  derivation note was updated consistently.
- Recompiled every manuscript entry point and visually checked the embedded
  Fig. S11 and the explicit operator equations. The active main text remains
  nine pages, the supplement remains 21 pages, and the combined review PDF is
  30 pages, with no unresolved references or overfull boxes.
- Extended the active manuscript validator to require the explicit projected
  hopping components; both active and PNAS validation suites pass.

## 2026-07-31 — Added the Hubbard canonical-transformation source and expanded the algebra

- Cited MacDonald, Girvin, and Yoshioka, Phys. Rev. B 37, 9753 (1988), as the
  direct source for the Hubbard `t/U` transformation and doublon-number
  decomposition, with Auerbach's textbook included as the pedagogical source.
- Expanded Eq. S16 through the full commutator bilinearity, cancellation of
  the two self-commutators, antisymmetry of the mixed commutators, and the
  final `P_0` projection that produces `-P_0 T_{-1}T_{+1}P_0`.
- Defined the nearest-neighbor bond coherence `g_NN` explicitly in Eq. S26,
  including its equal x- and y-bond forms, before using it in the Fourier
  transform in Eq. S27. The standalone derivation note was synchronized.
- Recompiled and visually inspected Eqs. S16 and S26--S27. The supplement
  remains 21 pages, with resolved citations and no overfull boxes; both
  manuscript validation suites pass.

## 2026-07-31 — Unified the grand-canonical Hamiltonian and derived Eq. S31

- Made the Hamiltonian convention explicit in every active main-text variant:
  `H` always denotes the full grand-canonical Hamiltonian including `-mu N`,
  while symbols such as `H_t` and `H_U` denote components. Removed the
  redundant `\widetilde H` notation from the supplement.
- Restored `-mu N` with `mu=U/2` in the spin-side Hubbard Hamiltonian. The
  Schrieffer--Wolff transformation leaves it unchanged because every `T_m`
  conserves total particle number; the projected `-mu N_s` contribution is
  displayed explicitly before being identified as a common constant.
- Expanded Eq. S31 directly from the Lehmann representation: complete `N+1`
  and `N-1` eigenstate sums are converted first to matrix elements of
  `H-E_0` and then to equal-time commutators with the same grand-canonical
  `H`. Added prose explaining that this identity is exact and is used to
  obtain spectral first moments without identifying individual poles.
- Corrected Eq. S32 so both commutator left-hand sides render explicitly; the
  original leading square bracket had been consumed as an optional alignment
  argument by LaTeX. Visual inspection now confirms Eqs. S31--S33 are complete.
- The expanded supplement is 22 pages and the active combined PDF is 31 pages.
  All entry points compile without unresolved references or overfull boxes,
  and both validation suites pass.

## 2026-07-31 — Made the S28-to-S29 weight identity explicit

- Expanded Eq. S29 with the exact zeroth-moment Lehmann identities
  `w_h=<c^dagger c>=n_k` and `w_p=<c c^dagger>=1-n_k`.
- Combined these identities with the previously defined
  `w_h=1/2+delta_k` and `w_p=1/2-delta_k` to show explicitly that
  `delta_k=(w_h-w_p)/2=n_k-1/2`; substitution of Eq. S28 then gives the final
  momentum-dependent expression in Eq. S29.
- Synchronized the standalone derivation note, visually inspected the
  expanded equation, rebuilt all review PDFs, and reran both validation
  suites successfully.

## 2026-07-31 — Started the Eq. S31 derivation from the Lehmann representation

- Inserted the exact zero-temperature retarded Green function immediately
  before Eq. S31, first in resolvent form and then as complete `N+1` and
  `N-1` Lehmann sums for the same grand-canonical Hamiltonian `H` used
  throughout the manuscript.
- Identified the particle-addition poles at `E_m^+-E_0` and the
  particle-removal poles at `-(E_n^--E_0)`, so their residue-weighted pole
  positions give the signed particle and hole first moments.
- Showed explicitly how completeness and `H|0>=E_0|0>` convert those Lehmann
  sums first into matrix elements of `H-E_0` and then into the equal-time
  commutators displayed in Eq. S31. The moment identity is exact; the
  strong-coupling approximation enters only when each spectral continuum is
  represented by its total weight and normalized first moment.
- Synchronized the standalone zero-scale derivation note and extended the
  manuscript validator to require the Lehmann Green function before Eq. S31.
  Rebuilt the canonical review PDFs: 9 pages for the active main text,
  22 pages for the Supplement, and 31 pages for the combined manuscript.
  Both manuscript validation suites pass without unresolved references or
  overfull boxes.

## 2026-07-31 — Exposed the unit charge-side hopping matrix element in Eq. S49

- Expanded the step from the checkerboard defect denominator
  `Delta_hop=7V` in Eq. S48 to the bond coherence `t/(7V)` in Eq. S49.
  Defined the one-hop defect
  `|b_ij,sigma>=c^dagger_j,sigma c_i,sigma|C>` and wrote the first-order
  checkerboard wave function explicitly.
- Evaluated the allowed-hop projector as
  `<C|n_i,sigma(1-n_j,sigma)|C>=1`: the source doublon contains either spin,
  the target is empty, and the directed per-spin coherence has only one
  nonzero cross term. Thus its leading matrix element is a fixed number,
  rather than an undetermined many-body correlator.
- Contrasted this with a Mott bond, where two singly occupied sites have a
  fluctuating singlet--triplet composition and the virtual-hop projector
  produces `1/4-<S_i.S_j>`. Empty and doubly occupied checkerboard sites both
  carry zero atomic spin, so no analogous spin factor appears. The two spin
  channels merely double the spin-summed coherence.
- Explained that virtual spin correlations first enter with probability
  `O(t^2/V^2)` and that bipartite gauge symmetry makes the bond coherence odd
  in `t`, leaving `O(t^3/V^3)` as the first correction. Added the same physical
  explanation to the active main text and standalone derivation note.
- Recompiled and visually inspected Supplemental pages 20--21. Eqs. S48 and
  S49 retain their numbering; the active main text, Supplement, and combined
  manuscript remain 9, 22, and 31 pages, respectively. Both validation suites
  pass without unresolved references or overfull boxes.

## 2026-07-31 — Boxed the general-coordination charge-side result

- Boxed Supplemental Eq. S53,
  `omega_GZ^(V)(k)=-[2z/(2z-1)] epsilon_0,k+O(t^2/V)`, so the general
  bipartite-lattice result is visually emphasized alongside the square-lattice
  `8/7` result in Eq. S52.
- Applied the same formatting to the standalone derivation note, rebuilt all
  canonical review PDFs, and visually checked Supplemental page 21. Equation
  numbering and page counts are unchanged, and both validation suites pass.

## 2026-08-03 — Added the two-by-four finite-$t'$ interaction-axis figure

- Added
  `pnas_fig2_interaction_axis_finite_tprime_combined_2x4.pdf` as main-text
  Figure 7 in the active journal-neutral manuscript `main_current.tex`; the
  preserved historical four-figure manuscript was not modified.
- The new full-width figure compares `t'=-0.25t` and `-0.4t`: its top row
  contains `U=20,V=0` spectra and `U=8,20,40` GZ sequences, while its bottom
  row contains `U=0,V=5` spectra and `V=2,5,8` GZ sequences.
- Added a results paragraph and caption explaining that the Mott branches
  approach the NN+NNN spin-correlation harmonics whereas the charge branches
  collapse onto `omega_GZ=-(8/7)epsilon_1+epsilon_2`. Explicit RMSE and
  percentage-fit language was removed from the surrounding main-text
  discussion in favor of the physical comparison.
- Updated the active figure plan, manuscript-version note, graphics search
  path, and validator for seven main figures. The active manuscript compiles
  to 10 pages; with the current 23-page Supplement the combined review PDF is
  33 pages. Figure 7 was visually inspected on page 9, with no clipping,
  overfull boxes, or unresolved references; all active validation checks pass.

## 2026-08-03 — Shortened and clarified the active abstract

- Removed the parenthetical `MMHK` abbreviation and the word `itself` from
  the framework sentence.
- Replaced the vague statement that spin correlations "fix the Mott-side
  harmonics" by the explicit bond-resolved result: the coefficient of each
  Mott-side hopping harmonic is
  `4 <S_i . S_(i+r)>`, while the charge-side form is
  `-(8/7) epsilon_1 + epsilon_2`.
- Replaced the explicit `U/t=20,40,80` list by `for large U`, changed the
  organizing ratio to `V/U approximately 1/4`, and removed the ground-state
  scan and all subsequent sentences from the abstract as requested.
- The revised abstract is approximately 106 words. Recompiled and visually
  inspected the first page, rebuilt the 10-page current manuscript and
  33-page main-plus-Supplement PDF, and passed all active validation checks.

## 2026-08-03 — Refined the opening abstract sentence

- Changed the opening claim to say that the Green function retains **clean**
  momentum structure through zeros and removed `thermodynamic` from the
  description of the momentum-mixing Hatsugai--Kohmoto framework.
- Rebuilt the current 10-page manuscript and 33-page combined PDF; all active
  validation checks pass.

## 2026-08-03 — Adopted a signed, zero-offset GZ coefficient and consolidated the main figures

- Replaced the positive-amplitude convention `omega_GZ=-s epsilon+delta` by
  the signed zero-offset convention `omega_GZ=s epsilon`. The sign now belongs
  to the coefficient itself: on the Mott axis `s=4C_1<0`, while on the charge
  axis `s=-8/7`. Magnitude trends are denoted explicitly by `|s|`.
- Extended the same convention to frustrated hopping,
  `omega_GZ=sum_r s_r epsilon_r`, with `s_r=4C_r` on the Mott side and
  `(s_NN,s_NNN)=(-8/7,1)` in the checkerboard limit. Removed the negligible
  constant offset from the displayed scalar and bond-resolved formulas and
  regenerated all retained coefficient plots with zero-offset fits.
- Removed the former main-text Figures 5 and 6. The former Figure 7, the
  two-by-four finite-`t'` interaction-axis test, is now the only main-text
  frustrated-hopping figure and renumbers automatically as Figure 5. Detailed
  representative-point and coefficient diagnostics remain in the Supplement.
- Updated the main text, Supplement, standalone derivation note, figure plan,
  figure builders, signed machine-readable figure metrics, and active
  validator. The active manuscript now has five main figures and compiles to
  9 pages; the 23-page Supplement gives a 32-page combined review PDF.
- Visually inspected the regenerated main figures, the signed asymptotic
  Supplemental figure, all nine main-text pages, and the opening Supplemental
  pages. All active validation checks pass with no unresolved references or
  overfull boxes.

## 2026-08-03 — Clarified scattering and physical momentum labels

- Replaced the statement that the internal Fourier transformation produces
  physical mixed momenta. The discrete set `K_4` is now defined explicitly as
  the scattering/mixing momenta retained by the `4x4` construction.
- Defined the physical single-particle momentum unambiguously as `k=K+f`.
  In the extended-zone spectral convention the measured component is `K=0`,
  so the plotted path has `k=f`.
- Clarified that internal Fourier transformation labels the discrete `K`
  components and that the sector offset shifts each component to the physical
  momentum entering `epsilon(K+f)`. Recompiled and visually checked page 2;
  the five-figure manuscript remains 9 pages and all validation checks pass.

## 2026-08-03 — Removed redundant extended-zone path explanation

- Removed the sentence explaining that the spectral path uses an equivalent
  extended-zone label and the `K=0` internal mode. The model section now stops
  at the essential distinction: `K` is a retained mixing momentum and the
  physical momentum is `k=K+f`.
- Simplified the Green-function paragraph to state only that varying `f` along
  the 121-point path generates the momentum-resolved spectrum. Recompiled the
  9-page manuscript and rebuilt the 32-page combined PDF; validation passes.

## 2026-08-03 — Simplified the Green-function methods introduction

- Replaced the particle-addition/removal continued-fraction wording by
  `single-particle Green function by Lanczos exact diagonalization`.
- Removed the path-construction, sector-by-sector, and interpolation details
  from the introductory methods paragraph.
- Moved the sole numerical value `eta=0.05` to the paragraph introducing the
  first spectral figure.
- Clarified the finite-broadening criterion: Lorentzian tails leave a small
  residual imaginary part in the gap, so the numerical branch is located from
  the sign change of `Re G`; the residual disappears as broadening is removed.
- Recompiled the 9-page manuscript and 32-page combined PDF; validation passes.

## 2026-08-03 — Moved main figures next to their discussion

- Reordered all five main-text figure environments so each is declared
  immediately before its dedicated discussion paragraph, and strengthened the
  float preference from `[t]` to `[!t]` without forcing disruptive page breaks.
- Figure 1 now appears at the top of page 3 beside the benchmark discussion;
  Figures 2, 3, 4, and 5 appear on pages 5, 6, 7, and 8, respectively, adjacent
  to their corresponding Mott-axis, charge-axis, interaction-plane, and finite-
  `t'` discussions.
- Recompiled and visually inspected all nine main-text pages, rebuilt the
  32-page main-plus-Supplement review PDF, and reran the manuscript validator.
  All active checks pass with no unresolved references or overfull boxes.

## 2026-08-03 — Advanced main-text Figures 2–5 by one page

- Moved the float declarations earlier in the source while preserving figure
  order and the `[!t]` REVTeX placement preference.
- Figures 2, 3, 4, and 5 now appear on pages 4, 5, 6, and 7, respectively;
  Figure 1 remains on page 3.
- Recompiled and visually inspected pages 3–8, rebuilt the 32-page combined
  main-plus-Supplement PDF, and reran the manuscript validator. All active
  checks pass with no unresolved references or overfull boxes.

## 2026-08-03 — Aligned the Fig. 3(f) panel label

- Raised the `(f)` label in Fig. 3 to the same vertical position as `(c)` and
  `(d)` while retaining its horizontal offset.
- Regenerated the reproducible Fig. 3 source, recompiled the manuscript,
  visually checked page 5, rebuilt the combined PDF, and passed all active
  manuscript validation checks.

## 2026-08-03 — Repositioned the Fig. 4(a) annotations and legend

- Moved the `Mott / spin side` and `CDW / charge side` labels just inside the
  upper frame and anchored them downward so neither protrudes above the axes.
- Lowered the one-column interaction legend into the empty upper-left Mott-side
  region, keeping it clear of all data and fitted curves.
- Regenerated Fig. 4, recompiled and visually inspected manuscript page 6,
  rebuilt the combined PDF, and passed all active validation checks.

## 2026-08-03 — Prepared a clean Overleaf upload bundle

- Created `output/overleaf/MMHK_overleaf_upload_20260803.zip` with `main.tex`
  at the archive root, the current Supplement and Significance Statement,
  `references.bib`, and only the 16 figure PDFs actually referenced.
- Rewrote the copied `graphicspath` entries for the archive-root layout while
  leaving the working manuscript sources unchanged.
- Excluded raw data, analysis outputs, scripts, stale manuscript versions,
  compiled manuscript PDFs, SyncTeX files, and other auxiliary files.
- Independently compiled the bundled `main.tex` (9 pages) and
  `supplement.tex` (23 pages) successfully with pdfLaTeX/TeX Live.

## 2026-08-03 — Matched the Fig. 3(f) legend layout to Fig. 2(f)

- Changed the Fig. 3(f) legend from one horizontal row to two rows in one
  column and moved it from the lower left to the upper left, using the same
  placement and typography as Fig. 2(f).
- Regenerated Fig. 3, recompiled and visually inspected manuscript page 5,
  rebuilt the combined PDF, and synchronized the clean Overleaf ZIP.

## 2026-08-03 — Restyled the fitted-parameter estimates

- Replaced exact equality signs by approximate signs for the fitted
  `lambda` and `kappa` values.
- Removed the enclosing square brackets around their confidence intervals and
  rewrote the sentence using a separate `respective 95% bootstrap intervals`
  clause.
- Applied the approximate-value convention consistently in the Supplement,
  recompiled both documents, visually checked page 6, rebuilt the combined
  PDF, and synchronized the Overleaf bundle.

## 2026-08-03 — Replaced the Overleaf project with the current manuscript

- Removed the previous contents of Overleaf project
  `69a6167f2a22f821b5beb97d` after explicit confirmation.
- Uploaded a clean, flat 21-file source set containing `main.tex`,
  `supplement.tex`, the Significance Statement, `references.bib`, README, and
  the 16 currently referenced figure PDFs; no obsolete project files remain.
- Kept `main.tex` as the Overleaf main document and successfully recompiled it
  online to the expected 9-page manuscript titled *Green-function zeros reveal
  competing Mott and charge-ordering scales*.
- Independently verified the same flattened source set locally: the main text
  compiles to 9 pages and the Supplement to 23 pages.

## 2026-08-03 — Removed journal-style prefixes from active figure names

- Removed the `pnas_` and `prl_` filename prefixes from all 12 figure PDFs
  used by the current main text and Supplement, and renamed the matching local
  PNG previews.
- Updated the active manuscript sources, figure plan, validators, provenance
  audit, and figure-generation scripts to use the neutral filenames.
- Rebuilt the clean Overleaf bundle and verified both the active local sources
  and flattened upload sources: main text 9 pages, Supplement 23 pages.
- Uploaded the neutral filenames to Overleaf, removed all 12 obsolete prefixed
  copies, and successfully recompiled the 9-page online manuscript.

## 2026-08-03 — Unified the bare-band harmonic notation

- Removed the redundant nearest-neighbor notation
  `\varepsilon_{0,\mathbf k}` and use `\varepsilon_1(\mathbf k)` consistently
  for the nearest-neighbor hopping harmonic.
- Defined the complete bare dispersion as
  `\varepsilon(\mathbf k)=\varepsilon_1(\mathbf k)+\varepsilon_2(\mathbf k)`,
  with `\varepsilon_2` reserved for next-nearest-neighbor hopping.
- Updated the active main text, Supplement, reproducible Fig. 2/3 and Fig. S1
  builders, figure labels, and Overleaf upload bundles. The main text and
  Supplement recompile successfully to 9 and 23 pages, respectively.
# 2026-08-04: Overleaf-first benchmark-definition update

- Established the current Overleaf project as the manuscript source of truth;
  future edits must first refresh the Overleaf source before modifying the
  local mirror.
- Replaced direct main-text figure-reference syntax with `\figdisp{...}` and
  the explicit single-reference construction with `\refdisp{...}`.
- Defined the plotted MMHK staggered-moment estimator explicitly as
  $m=[\overline{S^{zz}_{\mathbf f}(\pi,\pi)}/16]^{1/2}$, including the
  normalization of $S^z_{\mathbf Q}$.
- Expanded AFQMC, CP-AFQMC, DMET, and TABC at first benchmark use and moved
  detailed external-source selection out of the main Figure 1 caption.
- Added reproducible pointwise and density/observable percentage-deviation
  tables generated by `scripts/summarize_benchmark_percentage_deviations.py`.
- Updated Supplemental Table S1 with the aggregated deviations and retained
  the detailed marker/source rules there.
- Compiled and visually checked the nine-page main manuscript and 23-page
  supplement, synchronized both sources to Overleaf, and refreshed
  `output/pdf/MMHK.pdf`, `output/pdf/MMHK_supplement.pdf`, and
  `output/pdf/MMHK_with_SI.pdf`.
### 2026-08-04 — Benchmark prose and figure-reference style
- Refreshed the manuscript from the latest Overleaf source and preserved the manual removal of the former magnetization display equation.
- Added sentence-initial `\Figdisp` references (``Figure``), retained `\figdisp` (``Fig.``) within sentences, and standardized panel letters to lowercase in the main text, captions, and SI.
- Reorganized benchmark interpretation into separate paragraphs: ground-state energy/double occupancy first, then staggered magnetization. Added the interaction-dependent absolute-versus-relative deviation analysis backed by Table S1.
- Compiled the main text and SI, refreshed `output/pdf/MMHK.pdf`, `MMHK_supplement.pdf`, and `MMHK_with_SI.pdf`, and synchronized the revisions to Overleaf.
### 2026-08-04 — GZ terminology standardized
- Defined GZ once in both the main text and standalone SI, then used `GZ`, `GZ dispersion`, `GZ curve`, or `GZ branch` consistently thereafter.
- Retained expanded ``Green-function zero`` wording only in the title/abstract/introduction and at the formal abbreviation definitions.
- Recompiled, visually checked, synchronized to Overleaf, and refreshed the main, SI, and combined PDFs.

### 2026-08-04 — Mott--CDW terminology, asymptote labels, and bracket definition
- Refreshed the active sources from the current Overleaf project and replaced all visible `Mott--charge` and `charge-side` terminology by `Mott--CDW` and `CDW-side` in the main text and Supplement.
- Removed the legends from Fig. 2(f) and Fig. 3(f), replacing them with right-side annotations above the asymptotic guides: the Mott value now includes the $U\to\infty$ qualifier and the CDW value is written explicitly as $-8/7=-1.1429$.
- Simplified the interaction-plane labels to `Mott side` and `CDW side`; retained a dashed Mott asymptote and changed the CDW asymptote to dotted styling.
- Corrected the Fig. 3 interaction list and caption punctuation, and repaired a Supplemental caption grammar error.
- Expanded the Fig. 4(b) caption and Supplemental Sec. 8 to define each transition point as the midpoint of the closest sampled Mott/CDW endpoints and its bar as the sampled half-bracket, with endpoint assignment based on coincident ground-state-observable discontinuities over the complete mixed-momentum grid.
- Uploaded the revised sources and Fig. 2--4 PDFs to Overleaf, compiled the nine-page main text successfully, compiled the 23-page Supplement locally, visually inspected the changed pages, passed all manuscript validation checks, and refreshed the main, SI, and combined PDFs.

### 2026-08-04 — Active benchmark flow and asymptotic annotations
- Refreshed the manuscript from the current Overleaf source before editing.
- Rewrote the two benchmark-validation paragraphs in an active research sequence beginning with “We first benchmark 16-MMHK against ...”, while separating local-observable accuracy from the more method-sensitive staggered magnetization.
- Replaced the misleading statement that the CDW-side coefficient “reduces to a denominator” with the physical result that local charge-defect kinematics fixes the parameter-free coefficient to $-8/7$; the $7V$ denominator remains one intermediate ingredient in the derivation.
- Replaced the remaining `XXX` marker with a concise finite-$t'$ result: Mott-side hopping harmonics inherit the corresponding spin correlations, whereas CDW-side harmonics follow checkerboard-defect kinematics.
- Simplified the Fig. 2(f) annotation to $4\langle\mathbf S_i\!\cdot\!\mathbf S_j\rangle_{\rm NN,U\to\infty}$ and the Fig. 3(f) annotation to $-8/7$, with no numerical values in the panels.
- Regenerated Figs. 2 and 3, uploaded the revised source and figures to Overleaf, compiled and visually checked the nine-page manuscript, passed all validation checks, and refreshed the main and combined PDFs.

### 2026-08-04 — Enlarged Fig. 2(f) and Fig. 3(f) asymptote labels
- Increased the Fig. 2(f) and Fig. 3(f) asymptote-annotation font sizes by exactly $1.3\times$ and shifted both right-aligned labels slightly left.
- Regenerated both figures, checked them standalone and in the compiled manuscript, uploaded them to Overleaf, and refreshed the nine-page main and 32-page combined PDFs.
- All manuscript validation checks pass.

### 2026-08-04 — Sharpened transition and benchmark framing
- Refreshed the manuscript from the latest Overleaf source and preserved the intervening manual edits.
- Condensed the finite-$U,V$ result into one sentence: the GZ coefficient reorganizes sharply between the two mechanisms across a first-order Mott--CDW transition independently identified by the ground-state scan.
- Reframed magnetization as a more sensitive test of 16-MMHK rather than invoking generic estimator and method sensitivity.
- Replaced the categorical “validates” conclusion with the more appropriate statement that the benchmark agreement and strong-coupling magnetic trend make 16-MMHK a promising framework for real-frequency GZ analysis and nearest-neighbor interactions.
- Synchronized the revised source to Overleaf, compiled and visually checked the nine-page manuscript, passed all validation checks, and refreshed the main and combined PDFs.

### 2026-08-04 — Spectrum-first results transition and Figure 4 caption
- Refreshed the manuscript from the current Overleaf source and preserved the latest manual edits.
- Added a transition from the static benchmark to the central dynamical analysis at the start of the spin/charge-background subsection.
- Reorganized the opening results narrative to begin with the contrasting Mott- and CDW-side pole spectra, then follow $\mathrm{Re}\,G$ into the gap and introduce the GZ dispersion and coefficient.
- Rewrote the Figure 4 caption to identify the extracted data, constrained side-specific forms, asymptotic guides, $V/U=1/4$ marker, independently bracketed first-order transition ratios, and error-bar construction.
- Uploaded the revised source to Overleaf, compiled and visually checked the nine-page manuscript, passed all validation checks, and refreshed the main and combined PDFs.

## 2026-08-04 — Removed the redundant asymptotic SI figure and strengthened the GZ introduction

- Refreshed the manuscript from the current Overleaf source before editing.
- Removed the former Supplemental Fig. S1 asymptotic-comparison panel and its
  active source reference; subsequent supplementary figure references were
  renumbered consistently.
- Reframed the Results transition around the extended 16-MMHK construction at
  half filling and its real-frequency Green function and associated zeros.
- Identified main-text Fig. 2 explicitly as the U-only sequence and Fig. 3 as
  the V-only sequence.
- Added the Lehmann-sign argument that the separated removal/addition spectra
  enforce a gap-interior zero and connected that zero through Dyson's equation
  to a divergent, nonperturbative self-energy.
- Recompiled the 10-page main text and 22-page Supplement, passed all active
  manuscript validation checks, and synchronized the revision to Overleaf.

## 2026-08-04 — Abbreviation policy standardized

- Refreshed the current Overleaf manuscript before editing.
- Removed every abbreviation from the abstract, including symbolic interaction
  shorthand, while preserving the full physical content.
- Defined all manuscript-specific abbreviations before first use in the main
  text: Green-function zero (GZ), momentum-mixing Hatsugai--Kohmoto (MMHK),
  nearest neighbor (NN), charge-density wave (CDW), Hatsugai--Kohmoto (HK),
  reduced Brillouin zone (rBZ), next-nearest neighbor (NNN), Hermitian
  conjugation (H.c.), auxiliary-field quantum Monte Carlo (AFQMC),
  constrained-path AFQMC (CP-AFQMC), and density-matrix embedding theory
  (DMET).
- Added automated validation for an abbreviation-free abstract and ordered
  first-use definitions in the main text.
- Recompiled and visually checked the 10-page manuscript, refreshed the main,
  supplement, and 32-page combined PDFs, passed every validation check, and
  synchronized `main.tex` to Overleaf.

## 2026-08-04 — Green-function sign, panel references, and figure typography

- Corrected the gap sign-change statement from $G$ to $\operatorname{Re}G$;
  the spectral function remains nonnegative and vanishes in the ideal gap.
- Removed the repeated explicit noninteracting dispersion from Eq. 5, leaving
  only the GZ scaling relation already supported by the preceding definition.
- Added explicit Fig. 2(a--d) and Fig. 3(a--d) references for the Hubbard
  continua and the particle-removal/addition bands, respectively.
- Shifted panel labels (a) and (c) slightly left in both Figs. 2 and 3.
- Increased the legends in Fig. 5(c,d,g,h) by exactly $1.2\times$ and verified
  that the larger legends remain inside their panels without obscuring curves.
- Recompiled and visually checked the 10-page manuscript, passed all active
  validation checks, refreshed the main, supplement, and combined PDFs, and
  synchronized the revised source and figures to Overleaf.

## 2026-08-04 — Differential Fig. 5 legend sizing and explicit interaction limits

- Enlarged the current Fig. 5(c,d) legends by an additional $1.1\times$ and
  the Fig. 5(g,h) legends by an additional $1.2\times$; all four remain inside
  their panels without obscuring the GZ curves.
- Replaced the abstract phrase “both axes” with the explicit statement that
  the $U$-only and $V$-only limits each exhibit a smooth GZ dispersion.
- Added direct references to Fig. 2(e) and Fig. 3(e) where the extracted GZ
  curves and their differing amplitudes are first discussed.
- Standardized nearby prose and the Fig. 5 caption from “interaction axis” to
  the clearer “$U$-only” and “$V$-only” sequence/limit terminology.
- Recompiled and visually checked the 10-page manuscript, passed every active
  validation check, refreshed the main and combined PDFs, and synchronized
  the revised source and Fig. 5 to Overleaf.

## 2026-08-04 — Equation-reference convention and consolidated spectral setup

- Refreshed the manuscript from the latest Overleaf source and preserved the
  intervening manual edits.
- Cited Dave, Phillips, and Kane immediately before the two-sector Green
  function and its leading GZ relation, now Eqs. 6 and 7.
- Added `\\Disp` alongside `\\disp` and standardized every main-text equation
  citation: `Equation` at sentence openings and `Eq.` within sentences.
- Moved the fixed broadening, selected $U$ and $V$ grids, and the contrasting
  Mott/CDW spectral evolution to the opening of the dynamical-results
  subsection, with explicit Fig. 2(a--d) and Fig. 3(a--d) references.
- Removed the later redundant U-only and V-only descriptive paragraphs while
  retaining the panel-(e) comparison and both strong-coupling derivations.
- Recompiled and visually checked the resulting nine-page manuscript, passed
  all validation checks, refreshed the main and combined PDFs, and synchronized
  the source to Overleaf.

## 2026-08-05 — Overleaf source-of-record synchronization

- Uploaded the reorganized `main.tex` and `supplement.tex` to the live Overleaf
  project, preserving the project assets and replacing only the two revised
  source files.
- Verified the nine-page main manuscript and 20-page supplement compile on
  Overleaf with zero errors, then restored `main.tex` as the main document.
- Established a durable project rule in `AGENTS.md`: future manuscript, figure,
  bibliography, and supplement updates must be applied to Overleaf as part of
  the same task, after first inspecting the live sources for manual edits.

## 2026-08-05 — Introduction methods context and stronger novelty framing

- Refreshed the live Overleaf manuscript before editing and preserved the current source-of-record version.
- Rebuilt the opening paragraph around method-specific Hubbard references drawn from the MMHK Nature Physics paper: AFQMC, DMET, DMRG, DMFT, DCA, and diagrammatic extensions are now named and cited individually at first mention.
- Reframed prior zero-dispersion work as an observation rather than the present derivation: the missing contributions are identified explicitly as an equal-time coefficient, bond-by-bond resolution, and evolution into a CDW-dominated insulator.
- Added the principal methodological obstacles to a systematic finite-frequency GZ map: the QMC sign problem away from special regimes, ill-conditioned analytic continuation, and the nonperturbative self-energy divergence.
- Introduced MMHK before motivating its nearest-neighbor extension, used the established GZ terminology, and stated explicitly that the $V$-extended Hamiltonian is solved at half filling and zero temperature.
- Added a clear statement that independent analytical strong-coupling calculations derive the two asymptotic coefficients and their bond-resolved generalization, complementing the numerical Green-function results.
- Added six bibliography entries supporting the new discussion, synchronized `main.tex` and `references.bib` to Overleaf, compiled the nine-page main text and 20-page Supplement there with zero errors, and restored `main.tex` as the main document.
- Refreshed the local main, Supplement, 29-page combined PDF, Overleaf upload bundle, and manuscript validator; all active validation checks pass.

## 2026-08-05 — Concise GZ definition and benchmark-language cleanup

- Started from the current live Overleaf sources and preserved the user's manual
  removal of method abbreviations from the opening paragraph.
- Replaced the post-definition wording with the direct statement that
  $\omega_{\rm GZ}(\mathbf{k})$ denotes the GZ dispersion, and condensed the
  finite-broadening qualification into one sentence.
- Compressed the motivation for the missing finite-frequency GZ literature into
  three phrases: the fermion sign problem, ill-conditioned analytic
  continuation, and the nonperturbative self-energy divergence.
- Standardized the benchmark terminology to AFQMC, constrained-path AFQMC, and
  DMET without introducing a CP-AFQMC acronym; kept only the abbreviations in
  the Fig. 1 caption.
- Added the benchmark-data citations directly to the validation section,
  cited the Heisenberg reference data, replaced “density-averaged energy” by
  “ground-state energy,” and removed the matched-data qualifier.
- Compiled the nine-page main manuscript and 20-page Supplement locally and on
  Overleaf. Both have zero compilation errors, `main.tex` is restored as the
  Overleaf main document, and all active manuscript validation checks pass.

## 2026-08-05 — Reordered GZ mechanism and Supplemental Material

- Refreshed from the latest live Overleaf sources and preserved the user's
  manual edits, including the revised perturbative-obstacle ordering, the
  zero-frequency condition, and the streamlined benchmark wording.
- Removed both `XXX` markers by linking the Mott and CDW pole structures to
  the occupied-band snapshots in Supplemental Figs. S1 and S2.
- Reordered the dynamical narrative: the spectral maps are introduced first,
  the existence of a gap-interior zero is then established from the sign of
  $\mathrm{Re}\,G$, and only afterward is the smooth white-line GZ-dispersion
  pattern discussed.
- Replaced the variance/statistics-heavy moment paragraph with the physical
  strong-coupling picture of a large sector separation multiplied by a small
  virtual-hopping spectral-weight transfer.
- Combined each asymptotic-coefficient statement with its corresponding panel
  (Fig. 2f or 3f), changed “spin-side” to “Mott-side” in the derivation link,
  and explained the CDW-side minus sign through
  $\delta_{\mathbf k}=-\varepsilon_{\mathrm{NN}}(\mathbf k)/(7V)$.
- Regenerated Figs. 2 and 3 with panel-f ordinate labels
  “Estimated $s_{\mathrm{NN}}(U,0)$” and
  “Estimated $s_{\mathrm{NN}}(0,V)$,” respectively.
- Reordered the SI to follow first mention in the main text: benchmark;
  occupied-band comparison; shared moment relation; Mott derivation; CDW
  derivation; finite-interaction scans; model selection; static observables;
  and frustrated-hopping robustness. All nine SI sections and eight SI figures
  are cited from the main text.
- Compiled and visually inspected the nine-page main text and 20-page SI
  locally and on Overleaf. Both compile with zero errors; `main.tex` is restored
  as the Overleaf main document, and every active validation check passes.

## 2026-08-05 — Clarified the Mott and CDW first-moment mechanisms

- Made the Mott-side cancellation in the two-sector identity explicit: the
  common moment center and weight-separation term each contribute
  `2 C_NN epsilon_NN`, while their spin-independent `+epsilon_NN/2` and
  `-epsilon_NN/2` pieces cancel.
- Derived the CDW-side weight imbalance step by step from the directed bond
  coherence `g_NN=t/(7V)`, its Fourier transform over the four nearest-neighbor
  displacements, and the definition of the bare NN dispersion.
- Explained why only the weight-separation term contributes at leading order
  for NN hopping at `t'=0`: first-order hopping does not translate the lowest
  checkerboard defect within its manifold, so the common moment center starts
  at `O(t^2/V)`. The supplement notes explicitly that same-sublattice NNN
  hopping changes this kinematics.
- Reworded the finite-interaction result as a discontinuous switch, cited the
  independent static evidence for first-order behavior before the coefficient
  fit discussion, and deferred the first mention of Fig. 4(b) until after
  Eqs. 10 and 11.
- Regenerated Fig. 4(a) with the ordinate `Estimated s_NN(U,V)`, compiled the
  nine-page main text and 21-page supplement, visually inspected the revised
  pages, synchronized the revised sources and figures to Overleaf, and passed
  all manuscript validation checks. Both Overleaf documents compile with zero
  errors, and `main.tex` is restored as the main document.

## 2026-08-05 — Refocused the finite-interaction discussion on physics

- Restored the compact main-text CDW relation
  `delta_k=n_{k sigma}-1/2=-epsilon_NN(k)/(7V)` together with the `8V`
  particle-addition/removal separation; the intermediate bond-coherence and
  Fourier-transform derivation remains in the supplement.
- Replaced “this reorganization is first order” by “this transition is first
  order,” removed the parameter-specific `U=40` spectral narration, and merged
  the remaining gap statement into the opening finite-interaction paragraph.
- Removed the leave-one-family-out selection procedure from the main text and
  stated the status of Eqs. 10--11 precisely: their asymptotes are analytic,
  while the finite-ratio forms and coefficients are constrained numerical
  parameterizations.
- Rewrote the interpretation around the physical switch from spin-controlled
  virtual exchange to checkerboard charge-defect kinematics at `(V/U)_c`, and
  clarified that Fig. 4(b) independently locates the same first-order
  many-body transition.
- Added a transition into the finite-`t'` section explaining that
  next-nearest-neighbor hopping tests whether the GZ resolves individual
  hopping bonds once particle-hole symmetry is absent.
- Compiled and visually checked the nine-page manuscript, passed all active
  validation checks, and synchronized `main.tex` to Overleaf with zero errors.

## 2026-08-05 — Streamlined the transition evidence and finite-$t'$ analysis

- Moved the independent charge, spin, and Hellmann--Feynman evidence for a
  first-order transition to immediately after the discussion of Eqs. 10--11
  and directly before Fig. 4(b).
- Reframed the finite-$t'$ motivation as an exploration of how the GZ
  dispersion evolves after particle--hole symmetry is broken, and shortened
  the spectral description accordingly.
- Generalized the one-scale nearest-neighbor relation directly to separate NN
  and NNN dispersion components, placed the $O(t_{\max}^2/U)$ correction inside
  Eq. 12, and removed the redundant coordination explanation.
- Consolidated the bond-class argument, its Supplemental Material citation,
  and the comparison of Fig. 5(c,d); replaced the enumerated interaction grid
  by a reference to a more complete supplemental check.
- Simplified the CDW-side discussion to state that Fig. 5(g,h) approaches the
  parameter-free rule for both values of $t'$, removed the redundant finite-$V$
  convergence and summary sentences, and moved the detailed derivation link to
  immediately after Eq. 13.
- Recompiled and visually checked the nine-page manuscript, regenerated the
  30-page main-plus-Supplement PDF, and passed all active validation checks.

## 2026-08-05 — Clarified further-neighbor generalization

- Replaced the comparison against a single rescaling of the complete bare band
  with the direct physical conclusion that the spin-correlation mechanism
  generalizes to further-neighbor hopping.
- Removed the unnecessary “at $U=40$” qualifier from the Discussion statement
  connecting the ground-state observables to the first-order Mott--CDW crossing.
- Recompiled and visually checked the nine-page manuscript and passed every
  active validation check.

## 2026-08-05 — Clarified the Discussion physics and large-$U$ scope

- Synchronized from the current Overleaf source and preserved the user's manual
  Discussion restructuring.
- Replaced “low-energy pole spectra” by the physically precise “low-energy
  quasiparticle poles.”
- Clarified that the virtual hopping processes determining the GZ coefficients
  also shape $n(\mathbf{k})$ and kinetic energy, so the equal-time observables
  independently register the same Mott--CDW reorganization.
- Added the analytical strong-coupling calculations to the opening Discussion
  paragraph and scoped the first-order Mott--CDW statement explicitly to large
  $U$.
- Recompiled and visually checked the nine-page manuscript, regenerated the
  30-page main-plus-Supplement PDF, and passed all active validation checks.

## 2026-08-05 — Tightened the second Discussion paragraph

- Removed the detailed Hellmann--Feynman crossing interval, momentum-mixing
  resolution caveat, and total-momentum-sector caveat from the second
  Discussion paragraph.
- Reconnected the paragraph to the preceding dynamical/equal-time conclusion
  with a concise statement that the correspondence persists across interaction
  scales, the two parameter-free asymptotes, and frustrated hopping.
- Recompiled and visually checked the nine-page manuscript and regenerated the
  30-page main-plus-Supplement PDF.

## 2026-08-05 — Elevated the analytical–numerical correspondence in Discussion

- Synchronized from the latest Overleaf source and preserved the user's manual
  change from “Mott--CDW reorganization” to “Mott--CDW transition.”
- Added a concise impact statement identifying the analytical derivation and
  numerical GZ agreement as a rare quantitative paradigm for strongly
  correlated systems: a dynamical Green-function singularity fixed by
  microscopic correlations and defect kinematics.
- Recompiled and visually checked the nine-page manuscript, regenerated the
  30-page main-plus-Supplement PDF, and passed all active validation checks.

## 2026-08-05 — Polished and reorganized the Discussion

- Synchronized from the latest Overleaf source and replaced the incomplete
  manually edited Discussion with a clean three-paragraph argument.
- Organized the section around (i) the analytical--numerical strong-coupling
  correspondence, (ii) the discontinuous finite-$(U,V)$ Mott--CDW
  reorganization and its equal-time signatures, and (iii) the finite-$t'$
  bond-resolved generalization and experimental/numerical observability.
- Retained the central impact statement that the GZ dispersion provides a rare
  quantitative paradigm linking a dynamical Green-function singularity to
  microscopic correlations and defect kinematics.
- Removed obsolete commented prose and sharpened the distinction between the
  two correlated insulators despite their common absence of low-energy
  quasiparticle poles.
- Recompiled and visually checked the nine-page manuscript, regenerated the
  30-page main-plus-Supplement PDF, and passed all active validation checks.

## 2026-08-05 — Separated main and Supplemental figure assets

- Synchronized from the current Overleaf source and preserved the latest
  manual manuscript edits.
- Moved the five main-text figure PDFs into `figures/` and the ten
  Supplemental figure PDFs into `supp_figures/`, both locally and on Overleaf.
- Updated `main.tex` and `supplement.tex` to use the corresponding
  `\graphicspath` directories and documented the layout in `README.md`.
- Removed all input figure PDFs from beside the TeX sources, recompiled the
  nine-page manuscript and 21-page Supplement on Overleaf with zero errors,
  and restored `main.tex` as the project's main document.
- Downloaded the reorganized Overleaf source and verified byte-for-byte source
  and figure agreement, with no root-level PDFs remaining.

## 2026-08-06 — Reframed the closing Discussion around reach and outlook

- Synchronized from the current Overleaf source before editing.
- Rewrote the final Discussion paragraph to emphasize that the Mott-side
  strong-coupling GZ relation remains quantitatively robust down to $U=8t$, a
  widely used one-band cuprate-scale interaction, rather than only near the
  formal $U\to\infty$ limit.
- Presented the clean, single-valued GZ trajectory as an organizing constraint
  for constructing the full momentum--frequency spectroscopic map when the
  pole spectrum is broad.
- Extended the outlook to other correlated insulators and to the evolution,
  fragmentation, or pole reconnection of the GZ dispersion under doping.
- Updated Overleaf, verified the downloaded source byte-for-byte, compiled the
  nine-page manuscript with zero errors, and regenerated the 30-page
  main-plus-Supplement PDF.

## 2026-08-07 — Sealed the pre-Philip manuscript baseline

- Captured the live Overleaf project at `2026-08-07T22:20:06-04:00`
  (`2026-08-08T02:20:06Z`) immediately before Philip begins contributing.
- Preserved the exact Overleaf source ZIP and extracted source tree, the
  Overleaf main-text PDF, exact-source local main and Supplemental PDFs, and a
  30-page combined review PDF under
  `manuscript/archive/baselines/pre_philip_2026-08-07_22-20-06_EDT/`.
- Verified the nine-page main text and 21-page Supplement on Overleaf with zero
  compilation errors, then restored `main.tex` as the main document.
- Added SHA-256 integrity hashes, machine-readable provenance metadata, and
  `scripts/compare_manuscript_versions.py` so the posted manuscript can later
  be compared against this fixed baseline at the source, bibliography, label,
  section, and figure-file levels.
- Adopted a no-direct-edit policy for Overleaf: future changes are made in a
  freshly synchronized local copy, validated locally, and then synchronized to
  Overleaf as complete affected files.

## 2026-08-07 — Built a local analytical-first narrative experiment

- Inspected the current live Overleaf project without editing its source and
  created an isolated comparison draft under
  `manuscript/local_drafts/analytic_first_2026-08-07/`.
- Reorganized only the central $U$-only/$V$-only Results subsection into a
  phenomenon--derivation--numerical-test sequence: the common two-sector moment
  identity and the $4C_{\mathrm{NN}}$ and $-8/7$ predictions now precede their
  quantitative tests in Figs. 2 and 3.
- Preserved the original source beside the experiment and generated a unified
  diff, review notes, source bundle, nine-page manuscript PDF, 21-page
  Supplement, and 30-page combined review PDF.
- Both documents compile locally with zero errors and no unresolved citations
  or references. The main text retains one nonfatal RevTeX float-placement
  warning, while visual inspection confirms that all figures render correctly.
- This was deliberately kept as a local, noncanonical draft; no Overleaf source
  file was changed.

## 2026-08-10 — Merged Philip's Introduction revision into the analytical-first local draft

- Downloaded a fresh copy of the live Overleaf project and compared it against
  the sealed pre-Philip baseline.
- Verified that the only upstream change is one hunk at the opening of the
  Introduction in `main.tex`: all 19 other files, including the Supplement,
  bibliography, significance statement, and 15 figure PDFs, are byte-identical.
- Incorporated Philip's substantive reframing into the isolated
  `analytic_first_2026-08-07` draft: the Hubbard model is introduced as a grand
  challenge motivated by the parent cuprates, the unresolved real-frequency
  Green function is distinguished from mature static benchmarks, and zeros are
  presented as the possible surviving organizing principle.
- Incorporated Philip's current Introduction verbatim so that none of his
  changes appears in the analytical-first-versus-Overleaf diff; the local
  analytical-first difference is confined to the Results reordering.
- Consolidated the working comparison to the single requested diff,
  `output/analytic_first_vs_overleaf.diff`, which compares the current
  Overleaf `main.tex` directly with the local analytical-first `main.tex`.
- Removed the reconstructed before-Philip/pre-Philip working copies and diffs
  from the analytical-first folder and refreshed its source bundle. The
  separately sealed authorship baseline archive remains untouched.
- Recompiled the manuscript and Supplement locally with zero errors and no
  unresolved citations or references, and visually inspected the changed
  Introduction and analytical-first Results pages.
- The live Overleaf project was not edited.

## 2026-08-10 — Added visual analytical-first versus Overleaf diff

- Rendered the sole `analytic_first_vs_overleaf.diff` as a self-contained HTML
  actual-change report: paired passages show only changed words in red/green,
  unchanged spans are collapsed, and pure figure relocation is separated from
  substantive rewriting. The complete source diff remains in a collapsible
  appendix.
- Exported and visually checked a five-page landscape PDF of the focused
  report; it contains 13 word-level edits, three new passages, one
  removed/recast passage, and two relocated figure blocks.
- Added `scripts/render_manuscript_actual_changes.py` for regenerating this
  focused report. The earlier line-level renderer remains available for a raw
  source-oriented view.

## 2026-08-10 — Applied the analytical-first Results structure to Overleaf

- Refreshed `main.tex`, `supplement.tex`, and `references.bib` from the live
  Overleaf project before editing. Several sentence-level analytical-first
  changes were already present in the live manuscript.
- Applied the remaining analytical-first revision only within the subsection
  `Spin and charge backgrounds predict distinct GZ coefficients`: the Mott and
  CDW predictions now precede Figs. 2 and 3, respectively, and each figure is
  followed by its numerical-test paragraph.
- Verified byte-for-byte that the complete Introduction, the prefix before the
  target subsection, and the suffix after it were unchanged. This preserves
  Philip's current Introduction and every newer edit outside the target block.
  The complete audit is stored in
  `manuscript/archive/overleaf_sync_20260810_analytic_first/merge_audit.json`.
- Synchronized the complete merged `main.tex` to Overleaf and verified an exact
  readback (`SHA-256 3cda33510b09e99da49dc6f518d2b71fd137c7cafed87fd41cc1add016d9a0f5`).
- Compiled both documents on Overleaf: the 9-page main text has zero errors
  (two pre-existing layout/package warnings), and the 21-page Supplement has
  zero errors and zero warnings. Restored `main.tex` as the main document.
- Refreshed the local 9-page manuscript, 21-page Supplement, 30-page combined
  review PDF, and `output/overleaf/MMHK_overleaf_upload_20260810.zip`.
  `scripts/validate_manuscript.py` passes every active check.

## 2026-08-10 — Moved all main-text figures one page earlier

- Refreshed the live Overleaf `main.tex` and `supplement.tex` before changing
  float placement, then moved only the five unchanged figure environments.
- Figures 1--5 now begin on pages 3--7 rather than pages 4--8. All prose,
  equations, captions, labels, and figure graphics are unchanged; an automated
  audit confirms that both the nonfigure text and each figure block were
  preserved.
- Synchronized the complete updated `main.tex` to Overleaf and verified an
  exact readback (`SHA-256
  cfed3f8b89b3fda0634455620277ff7dbbcdf3e6514bb1af24bc0ff5a490d5fc`).
- Compiled both documents on Overleaf: the 9-page main text has zero errors and
  one pre-existing `nameref` package warning, while the 21-page Supplement has
  zero errors and zero warnings. Restored `main.tex` as the main document.
- Refreshed the local manuscript, Supplement, 30-page combined PDF, and
  `output/overleaf/MMHK_overleaf_upload_20260810.zip`. The placement and sync
  audit is stored at
  `manuscript/archive/overleaf_sync_20260810_figures_up/figure_move_audit.json`,
  and `scripts/validate_manuscript.py` passes every active check.

## 2026-08-10 — Promoted the revised Results order to the canonical manuscript

- Retired the separate working-version label: the reordered analytical and
  numerical narrative is now simply the current manuscript in Overleaf,
  `manuscript/main.tex`, and `manuscript/main_current.tex`.
- Moved the obsolete local-draft directory into the neutral historical archive
  `manuscript/archive/results_reorganization_20260810/` and renamed its source,
  PDF, bundle, diff, and report artifacts accordingly.
- Recast the visual comparison as “earlier Results order” versus “current
  manuscript,” regenerated its five-page PDF, and updated both report-rendering
  scripts so the retired label is not reintroduced.
- No manuscript source or Overleaf file changed in this housekeeping step.

## 2026-08-12 — Created an editable two-insulator schematic

- Created a one-slide, two-panel PowerPoint schematic contrasting the
  spin-correlated Mott insulator with the checkerboard CDW insulator.
- The panels combine editable real-space backgrounds, virtual-hopping
  processes, schematic momentum--frequency spectra, white GZ branches, and the
  respective strong-coupling rules $4\langle\mathbf S_i\!\cdot\!\mathbf
  S_j\rangle_{\rm NN}$ and $-8/7$.
- Every visual element is a native PowerPoint shape or text object; the PPTX
  contains no embedded raster media. Rendering and slide-boundary tests pass
  with no clipping or overflow.
- Saved the deck as
  `output/pptx/two_correlated_insulators_schematic_editable.pptx`. It has not
  yet been inserted into the manuscript or synchronized to Overleaf.

## 2026-08-12 — Preserved the concept slide and redesigned a paper figure

- Preserved the full spectrum/process/GZ schematic without modification as
  `output/pptx/archive/two_correlated_insulators_full_schematic_concept_draft_20260812.pptx`
  for future presentation use.
- Created a separate publication-aspect editable PowerPoint containing only
  the two requested real-space backgrounds: singly occupied local moments with
  antiferromagnetic NN correlations and a doublon--empty checkerboard CDW.
- Exported a one-page vector PDF at a full-width paper aspect ratio. Every
  visible object in the PowerPoint remains editable, and slide-boundary testing
  reports no overflow.
- Saved the editable candidate as
  `output/pptx/fig1_correlated_insulators_realspace_editable.pptx` and the
  vector figure as `output/figures/fig1_correlated_insulators_realspace.pdf`.
  This candidate has not yet replaced the current Fig. 1 or been synchronized
  to Overleaf pending review.

## 2026-08-12 — Simplified the real-space Fig. 1 candidate

- Archived the first publication-layout draft before revision.
- Removed the panel background colors, borders, colored header bars,
  subtitles, and bottom explanatory text.
- The revised figure is a conventional two-panel composition containing only
  panel labels, concise insulator names, and the two real-space lattice
  backgrounds on white.
- Refreshed the editable PowerPoint and vector PDF at their stable output
  paths. The original full presentation schematic remains preserved separately
  for future use, and no manuscript or Overleaf source was changed.

## 2026-08-12 — Created an oblique-projection real-space variant

- Sealed the approved flat two-panel candidate under dated archive filenames
  before developing the alternative projection.
- Created a separate oblique-projection version using parallel receding lattice
  lines, foreshortening, and no perspective convergence. The projected site
  markers are ellipses, consistent with the oblique view, while occupancies and
  spin arrows retain the same visual convention as the flat version.
- Saved the editable deck as
  `output/pptx/fig1_correlated_insulators_realspace_oblique_editable.pptx` and
  the vector export as
  `output/figures/fig1_correlated_insulators_realspace_oblique.pdf`.
- The deck contains no embedded raster media, passes slide-boundary testing,
  and remains entirely editable. Neither variant has yet been inserted into the
  manuscript or synchronized to Overleaf.

## 2026-08-12 — Added virtual fluctuations to both real-space candidates

- Archived the pre-fluctuation flat and oblique candidates under dated names in
  `output/pptx/archive/` and `output/figures/archive/`.
- Added an editable nearest-neighbor virtual-hop process below each real-space
  background in both the normal and oblique versions. The Mott panel shows
  $(\uparrow,\downarrow)\rightarrow(0,\uparrow\downarrow)$ with excitation
  cost $\Delta E=U$; the CDW panel shows
  $(\uparrow\downarrow,0)\rightarrow(\uparrow,\downarrow)$ with the
  strong-coupling defect cost $\Delta E=7V$.
- Updated the current oblique candidate to use circular site glyphs while
  retaining the oblique bond projection.
- Refreshed both editable PowerPoints and vector PDFs at their stable output
  paths. Both decks contain only native editable objects, contain no embedded
  media, and pass slide-boundary tests with no overflow.
- These candidates have not been inserted into the manuscript or synchronized
  to Overleaf.

## 2026-08-12 — Enforced circular sites in the oblique candidate

- Replaced the visually projected site markers in the oblique figure with
  equal-width/equal-height circular glyphs matching the normal version; only
  the lattice coordinates and bonds retain the oblique projection.
- Applied the same circular convention to the virtual-fluctuation inset,
  refreshed the editable PowerPoint and vector PDF, and copied the updated
  files to `/Users/cosdis/LocalFiles/MMHK_fig1_noncloud_20260812.nosync/`.
- The revised deck passes slide-boundary testing, contains no embedded media,
  and has not been inserted into the manuscript or synchronized to Overleaf.

## 2026-08-12 — Prepared three minimal virtual-hop conventions

- Created three separate editable oblique-projection figure candidates while
  preserving the same circular site glyphs and physical configurations:
  option 1 uses a dashed arrow labeled $t$; option 2 explicitly labels the
  arrow ``virtual hop ($t$)''; and option 4 uses a solid outward $t$ arrow with
  a lighter dashed return arrow.
- Exported a vector PDF for each candidate and copied all six artifacts to the
  non-cloud directory
  `/Users/cosdis/LocalFiles/MMHK_fig1_noncloud_20260812.nosync/oblique_virtual_hop_options/`.
- All three decks pass slide-boundary testing and contain no embedded media.
  No manuscript or Overleaf files were changed.

## 2026-08-12 — Revised oblique option 4 to a dashed curved fluctuation

- Archived the earlier option-4 convention with one solid outward arrow and a
  straight dashed return arrow.
- Replaced it with a native editable curved connector carrying dashed
  arrowheads in both directions. This treats the full out-and-back process as
  virtual rather than visually privileging its outward leg.
- Refreshed the option-4 editable PowerPoint and vector PDF in both the project
  outputs and the non-cloud folder. Slide-boundary testing passes, the deck has
  no embedded media, and no manuscript or Overleaf files were changed.

## 2026-08-12 — Separated the two curved virtual-hop arrows

- Archived the joined, double-headed curved-arrow candidate.
- Revised option 4 so the outward and return legs are two distinct, vertically
  separated dashed curved arrows. Their endpoints no longer meet, while their
  opposite arrowheads retain the out-and-back virtual-fluctuation meaning.
- Refreshed and verified the project and non-cloud PPTX/PDF outputs. No
  manuscript or Overleaf files were changed.

## 2026-08-12 — Matched the reference lens-shaped curved arrows

- Reworked option 4 to follow the supplied reference: two opposing curved arcs
  form a narrow lens, remain separated at the left and right endpoints, and
  carry arrowheads along the middle of the curves rather than at the ends.
- Retained dashed strokes on both arcs so the entire out-and-back process reads
  as virtual. The arc paths and arrowheads remain editable PowerPoint objects.
- Refreshed the vector PDF and non-cloud copies, with no manuscript or Overleaf
  changes.

## 2026-08-12 — Created a background-integrated virtual-hop candidate

- Preserved the approved option-4 figure with its separate two-site process
  diagram unchanged.
- Created a new compact candidate that places the dashed lens-shaped virtual
  hop directly on a representative nearest-neighbor bond in each oblique
  background. The selected Mott bond is $(\uparrow,\downarrow)$ and the selected
  CDW bond is $(\uparrow\downarrow,0)$; $t$ sits inside the lens and the
  corresponding $\Delta E=U$ or $7V$ is shown immediately below the lattice.
- Saved separate editable PPTX and vector-PDF outputs in the project and
  non-cloud folders. The deck passes slide-boundary testing and contains no
  embedded media. No manuscript or Overleaf files were changed.

## 2026-08-14 — Built a discovery-led Nature Physics Fig. 1 candidate

- Selected the compact merged oblique virtual-hop artwork as the real-space
  Mott and checkerboard-CDW backgrounds, preserving its native editable
  PowerPoint objects.
- Added representative $U=40,V=0$ and $U=0,V=12$ spectral maps with white GZ
  dispersions, followed by the signed nearest-neighbor coefficient across the
  $U=40$ Mott--CDW switch and its two strong-coupling limits.
- Exported an editable PowerPoint plus a publication-quality vector PDF and
  PNG under `figures/nature_phys/fig1_discovery_overview*`. The PPTX passes
  boundary, rendering, and template-fidelity checks and includes source notes.
- This remains a review candidate: the canonical manuscript figure and
  Overleaf project were not changed.

## 2026-08-17 — Synchronized approved introduction/model revisions

- Refreshed the manuscript from the live Overleaf source before editing, then
  applied the approved introduction and model-language revisions locally and
  to Overleaf. Added diagrammatic quantum Monte Carlo to the numerical-method
  context, clarified the mixed-momentum geometry, standardized the
  `$V$`-extended MMHK wording, and related the zero-frequency cut of the GZ
  dispersion to the conventional Luttinger surface.
- Defined nearest neighbor (NN) and next-nearest neighbor (NNN) at their first
  main-text occurrences. The Han--Stepanov attribution was deliberately left
  unchanged, as requested.
- Added the Science diagrammatic-Monte-Carlo reference to `references.bib` and
  removed all remaining `XXX` drafting comments.
- Local validation and TeX compilation pass. The live Overleaf project was
  compiled from scratch with zero errors for both `main.tex` (9 pages) and
  `supplement.tex` (21 pages), and `main.tex` was restored as the main document.
- Archived the pre-edit Overleaf source, approved diffs, and synchronized
  source snapshots under
  `manuscript/archive/overleaf_sync_20260817_approved_intro_model_edits/`.

## 2026-08-18 — Sharpened the benchmark-to-discovery hierarchy

- Refreshed `main.tex` and `supplement.tex` from the live Overleaf project
  before editing, preserving the current collaborative manuscript state.
- Recast the Introduction roadmap so the purpose of the $V$ extension is
  explicit: it resolves how the real-frequency GZ dispersion evolves across
  the Mott--CDW competition after the Hubbard benchmark.
- Retitled Fig. 1 as a benchmark validation of $16$-MMHK and tightened the
  benchmark section's closing sentence so it establishes the static baseline
  for the subsequent real-frequency problem.
- Synchronized the complete edited `main.tex` to Overleaf. During upload, the
  live supplement was briefly overwritten by a stale editor selection; it was
  immediately restored byte-for-byte from the pre-edit live snapshot before
  compilation.
- Local validation passed. Overleaf compiled `main.tex` from scratch with zero
  errors (9 pages) and `supplement.tex` from scratch with zero errors (21
  pages), then restored `main.tex` as the main document. Canonical local PDFs,
  the combined PDF, and the dated Overleaf bundle were refreshed.

## 2026-08-18 — Derived the $V$-extended MMHK extended-Hubbard limit

- Refreshed the live Overleaf `main.tex` and `supplement.tex` before editing and
  used both the generalized momentum-mixing note and the published MMHK
  Hubbard-limit construction as the algebraic starting point.
- Added Supplemental Sec. 1, which writes the on-site and nearest-neighbor
  interactions in the restricted momentum-transfer basis, applies the
  internal-orbital Fourier transform, and shows explicitly that
  `n=N` recovers the full grand-canonical extended-Hubbard Hamiltonian. The
  thermodynamic `n\to\infty` interpretation is stated separately from the
  exact finite-lattice endpoint.
- Linked the derivation from the main Hamiltonian discussion and incremented
  all subsequent Supplemental Material section references without changing
  the scientific results or figures.
- Synchronized the complete updated `main.tex` and `supplement.tex` to the live
  Overleaf project. Overleaf compiled the Supplemental Material with zero
  errors and zero warnings (23 pages), and the main manuscript with zero
  errors (9 pages); `main.tex` was restored as the main document.
- Refreshed the canonical local source files, main PDF, Supplemental Material
  PDF, 32-page combined PDF, archive snapshots, and the clean dated Overleaf
  upload bundle `output/overleaf/MMHK_overleaf_upload_20260818_vextended.zip`.

## 2026-08-20 — Removed all horizontal offsets from benchmark Fig. 1

- Refreshed the manuscript and Supplemental Material from the live Overleaf
  project before changing the figure, preserving the current collaborative
  text.
- Removed the AFQMC/DMET horizontal plotting shifts from all three benchmark
  panels. Every MMHK and literature marker now lies at its exact physical
  $U/t$; marker shape, fill, and density color provide the source encoding.
- Regenerated `fig1_multidensity_benchmark.pdf` and its PNG, updated the
  machine-readable open-marker inventory so `plotted_x=U` for every retained
  row, and removed the obsolete offset statement from active manuscript
  variants and the marker guide.
- Updated the live Overleaf figure, compiled the 23-page Supplemental Material
  with zero errors or warnings, compiled the 9-page main manuscript with zero
  errors, and restored `main.tex` as the main document.
- Refreshed the canonical main, Supplemental Material, and 32-page combined
  PDFs plus the dated upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_no_offsets.zip`.

## 2026-08-20 — Added the spinless $t$--$V$ interaction benchmark to Supplemental Sec. 2

- Completed and analyzed all 2583 spinless $16$-MMHK targets: 861
  symmetry-reduced mixed-momentum points at each of $V/t=1,2,$ and 4.
- Regenerated the energy comparison without horizontal offsets. Solid markers
  denote $16$-MMHK, while CT-QMC and DMRG are overlaid as open markers at the
  same physical $V/t$ values.
- Added the comparison, Hamiltonian and quadrature details, and the two source
  citations as a new subsection of the existing Supplemental Material Sec. 2;
  no additional top-level supplemental section was created.
- Shifted the subsequent supplemental figure references consistently, compiled
  the local main text (9 pages) and supplement (23 pages) with zero errors, and
  refreshed the 32-page combined PDF and dated upload bundle.
- Synchronized the complete affected source files and the new figure to the
  live Overleaf project. Overleaf compiled the supplement with zero errors and
  zero warnings and the main text with zero errors; `main.tex` remains the main
  document.

## 2026-08-20 — Local-only spinless benchmark layer-order revision

- Raised the solid spinless $16$-MMHK markers above the open CT-QMC and DMRG
  markers at coincident $V/t$ values, without introducing horizontal offsets.
- Regenerated the local figure, 23-page supplement, and 32-page combined PDF.
  This layer-order revision has deliberately not been synchronized to Overleaf.

## 2026-08-20 — Restored original-style finite-$t'$ Supplemental Figs. S8 and S9

- Reverted Supplemental Fig. S8 to the original six-panel $t'=-0.25t$
  reproduction: four spectral maps, the four-$U$ GZ overlay, and the $U=40$
  NN+NNN comparison.
- Added the matching original-style $t'=-0.4t$ reproduction as Fig. S9. The
  coefficient-versus-$t/U$ convergence layouts and explicit $U\to\infty$
  panels requested in the intervening revision are no longer used.
- Synchronized `main.tex`, `supplement.tex`, and the new S9 PDF to Overleaf.
  Overleaf compiled the 23-page supplement and 9-page main manuscript with
  zero errors, and `main.tex` was restored as the main document.
- Refreshed the 32-page combined PDF and the dated Overleaf upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_180426_tprime_original_style.zip`.

## 2026-08-20 — Compacted main Figures 2 and 3 and preserved the full scans in the supplement

- Archived the live pre-edit Overleaf sources and the complete six-panel
  versions of main-text Figs. 2 and 3 before changing the layouts.
- Rebuilt main Fig. 2 as a compact $2\times2$ figure containing the $U/t=8$
  and 20 spectra, the complete four-$U$ GZ overlay, and the coefficient
  convergence. Rebuilt main Fig. 3 analogously with the $V/t=2$ and 5
  spectra, the complete four-$V$ GZ overlay, and the coefficient convergence.
- Added the former complete six-panel Mott- and CDW-side figures as Figs. S1
  and S2 in Supplemental Sec. 3. Existing supplemental figures and all
  main-text cross-references were renumbered consistently.
- Added the reproducible builder
  `scripts/build_compact_main_axis_figures.py` and a machine-readable output
  manifest in `results/compact_main_axis_figures_manifest_20260820.json`.
- Local TeX compilation passed with zero undefined citations or references;
  the main manuscript is 10 pages and the supplement is 24 pages. Visual QA
  confirmed the compact and full layouts are unclipped and legible.
- Synchronized the complete affected TeX and figure files to Overleaf. The
  supplement compiled there with zero errors and warnings, and the main text
  with zero errors; `main.tex` was restored as the main document.
- Refreshed the 34-page combined PDF and the dated upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_181736_compact_fig2_fig3.zip`.

## 2026-08-20 — Compacted main Figure 5 and limited supplemental precision

- Archived the live pre-edit Overleaf sources and the former eight-panel
  finite-$t'$ main figure before making changes.
- Removed the four $t'=-0.4t$ panels from main Fig. 5 and rebuilt the retained
  $t'=-0.25t$ results as a compact $2\times2$ layout: Mott spectrum and
  $U$-only GZ comparison in the first row, followed by the CDW spectrum and
  $V$-only GZ comparison. The complete $t'=-0.4t$ check remains in
  Supplemental Fig. S11.
- Updated the Fig. 5 caption and every main-text panel reference from the old
  eight-panel labels to the new panels (a--d). Added the reproducible builder
  `scripts/build_compact_finite_tprime_figure.py` and its CSV/JSON manifests.
- Rounded every displayed decimal literal in `supplement.tex` to at most four
  places, including Table S3, the finite-$V$ coefficient rule, and the
  frustrated-spin correlation values. A source and rendered-PDF audit found
  no remaining values with five or more decimal places.
- Local compilation and visual QA passed for the 10-page main text and
  24-page supplement with no unresolved references. Overleaf compiled the
  supplement with zero errors and warnings and the main text with zero
  errors; `main.tex` was restored as the main document.
- Refreshed the 34-page combined PDF and the dated upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_182740_fig5_tpn25_four_decimals.zip`.

## 2026-08-20 — Preserved panel geometry in compact main Figures 2, 3, and 5

- Kept the approved panel removals in main Figs. 2, 3, and 5, but restored the
  retained axes to the same physical dimensions and aspect ratios used before
  the panels were removed. The figures now become smaller through a reduced
  canvas and reduced LaTeX display width, rather than by stretching the
  remaining panels.
- Set the main-text display widths to `0.69\textwidth` for Figs. 2 and 3 and
  `0.49\textwidth` for Fig. 5, matching the fractions of the original
  six- and eight-panel canvases occupied by the retained panels.
- Reduced the left--right gap in Fig. 5 to 0.55 in while preserving each
  panel's former dimensions and aspect ratio. Visual QA confirmed that the
  axis labels, tick labels, color bars, panel labels, and legends remain
  unclipped and nonoverlapping.
- Local compilation succeeded for the 9-page main text and 24-page
  supplement. Overleaf compiled both documents with zero errors, and
  `main.tex` was restored as the main document.
- Refreshed the canonical 9-page main PDF, 24-page supplement, 33-page
  combined PDF, and the dated upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_185350_preserve_panel_geometry.zip`.

## 2026-08-20 — Approved panel-label and Figure 5 legend refinements

- Began from a fresh download of the live Overleaf project and preserved its
  current `main.tex`, `supplement.tex`, and bibliography without textual edits.
- Moved panel labels (a,c) slightly left in main Figs. 1, 2, 3, and 5.
- Reorganized the Fig. 5(b,d) legends into separate interaction and analytic-
  formula rows, retained the approved slight upward shift in panel (b), and
  enlarged only the analytic-formula row in panel (d) from 10.8 pt to 12.4 pt.
  Every other Fig. 5 legend row remains at 10.8 pt.
- Promoted the approved settings into the reproducible figure builders and
  verified the regenerated PDFs are pixel-identical to the approval previews.
- Synchronized the four complete figure PDFs to Overleaf. The 8-page main
  manuscript and 24-page supplement compile there with zero errors; the
  supplement has zero warnings, and `main.tex` was restored as the main
  document. The current main-source warnings predate and are independent of
  this figure-only update.
- Refreshed the local main, supplement, 32-page combined PDF, and upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_1950_approved_figures.zip`.

## 2026-08-20 — Analytic finite-$(U,V)$ scale laws and CDW moment centering

- Replaced the empirical finite-$(U,V)$ branches in main-text Eqs. (10) and
  (11) by the controlled leading strong-coupling laws
  $s_{\rm NN}^{\rm M}=1+(2U-V)(2C_{\rm NN}-1/2)/(U-V)$ and
  $s_{\rm NN}^{\rm C}=-(8V-U)/(7V-U)$, with their stated remainders.
- Added the detailed supplemental derivation from the exact signed first
  moment, including the virtual-hop denominators $D_{\rm M}=U-V$ and
  $D_{\rm C}=7V-U$, the sector separation $\Delta_{\rm C}=8V-U$, and the
  same-momentum CDW cancellation
  $\mathcal C_{\mathbf k}=M_1+\delta_{\mathbf k}\Delta_{\rm C}$.
- Rebuilt Fig. 4(a) from the leading analytic laws. The Mott curves use only
  their independently measured $V=0$ family anchors; the CDW curve is
  parameter-free. No finite-$V$ fit parameter is retained.
- Added reproducible validation artifacts in
  `results/finite_uv_strong_coupling_validation_eta0p05.{csv,json}`. The
  displayed nonanchor/nonboundary RMSE values are 0.01836 (Mott) and 0.00487
  (CDW), and residuals decrease strongly with interaction strength.
- Local compilation and visual QA passed for the 8-page main manuscript and
  27-page supplement; the combined document has 35 pages. The source and PDF
  mirror groups are byte-identical.
- Synchronized the complete affected `main.tex`, `supplement.tex`, and Fig. 4
  PDF to Overleaf, then downloaded the post-sync source and verified all three
  files byte-for-byte. Overleaf compiled the supplement with 0 errors and 0
  warnings and the main manuscript with 0 errors (3 pre-existing warnings);
  `main.tex` was restored as the main document.
- Archived the verified post-sync project under
  `manuscript/archive/overleaf_sync_20260820_finite_uv_scale_laws/` and created
  the complete upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260820_205725_finite_uv_scale_laws.zip`
  (SHA-256 `2713ae2aa2adbb46692624ca923a722a563ff0542084f456f86fea9de032e089`).

### 2026-08-21 — Green-function calculation detail moved to Materials and Methods
- Started from a fresh download of the live Overleaf source and preserved all intervening collaborator edits.
- Removed the procedural Lanczos sentence from the main-text GZ-definition subsection and placed it at the start of **Materials and Methods — Ground state and Green functions**; the redundant later Lanczos sentence was removed.
- Synchronized the complete updated `main.tex` to Overleaf, verified the post-upload source hash against the local mirror, and restored `main.tex` as the main document.
- Validation: main manuscript compiled with 0 errors (3 pre-existing warnings); Supplemental Material compiled with 0 errors and 0 warnings. Refreshed local main, supplement, combined PDFs, and the upload bundle.

### 2026-08-21 — Figure 1 reorganized into two rows
- Removed the three panel titles from the benchmark figure.
- Placed panels (a,b) in the first row and centered panel (c) in the second
  row while preserving every axes frame's former physical width, height, and
  aspect ratio.
- Tight-cropped the unused left/right canvas with a 0.02-in safety pad. The
  PDF width decreased from 734.4 pt to 480.8 pt without changing any axes
  dimensions or aspect ratios.
- Updated the reproducible builder and the canonical local/main-manuscript
  Figure 1 PDFs. The revised asset was synchronized to Overleaf without
  changing any collaborator-edited TeX source; its Overleaf blob hash
  (`c0d1a6ce4c079d30d77ade9f36e7418984c51345`) matches the local Git object.
- The current Overleaf main manuscript recompiles with zero errors; the two
  reported warnings are the existing package/float warnings.

### 2026-08-24 — Oblique strong-coupling schematic promoted to main-text Figure 1
- Began from a fresh download of the live Overleaf source and archived it under
  `manuscript/archive/overleaf_before_new_fig1_20260824_1415/`, preserving all
  collaborator edits before making the figure integration locally.
- Added `figures/fig1_oblique_virtual_merged.pdf` as the new full-width Figure 1,
  illustrating the spin-correlated Mott and checkerboard CDW backgrounds and
  their representative virtual hops with costs $U$ and $7V$.
- Added a concise introductory cross-reference and caption. The former main
  figures now renumber automatically as Figs. 2--6; the explicit main-figure
  numbers in the Supplemental Material were updated consistently.
- Local pdfLaTeX/BibTeX compilation succeeded for the 8-page main manuscript
  and 27-page supplement with no unresolved references or citations. Visual QA
  confirmed the new schematic and caption are unclipped and legible on page 3.
- Synchronized the complete affected `main.tex`, `supplement.tex`, and new
  figure PDF to Overleaf. Overleaf compiled the supplement with 0 errors and 0
  warnings and the main manuscript with 0 errors (3 pre-existing warnings);
  `main.tex` was restored as the main document.
- Refreshed `manuscript/main.pdf`, `manuscript/supplement.pdf`, the 35-page
  `manuscript/MMHK_current_with_supplement.pdf`, and upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260824_1415_new_fig1.zip`.

### 2026-08-24 — Figure 1 stacked vertically as a single-column schematic
- Refreshed `main.tex` from the live Overleaf source before editing, thereby
  preserving the collaborator-written title **Distinct correlated insulators**
  and all other intervening manuscript changes.
- Reworked the editable PowerPoint schematic without redrawing its content:
  panel (b) is translated directly below panel (a), both panels share the same
  horizontal alignment, and the canvas is resized from 1260 x 350 to 630 x 690
  px. The previous horizontal version is retained in the figure archives.
- Changed the LaTeX float from `figure*` to `figure` and sized the asset to
  `\columnwidth`; the caption title is now **Distinct correlated insulators.**
- Presentation QA passed with no canvas overflow and no template-fidelity
  issues. Local compilation produced an 8-page main manuscript and 27-page
  supplement with no unresolved citations or references; visual inspection
  confirmed that Figure 1 is legible and confined to one column on page 2.
- Synchronized the complete updated `main.tex` and Figure 1 PDF to Overleaf.
  Overleaf compiled the supplement with 0 errors/0 warnings and the main
  manuscript with 0 errors (3 pre-existing warnings), with `main.tex` left as
  the active document.
- Refreshed the editable PPTX, local main/supplement/35-page combined PDFs, and
  upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260824_105828_fig1_vertical_single_column.zip`.

### 2026-08-24 — Figure 1 panels connected explicitly to the physics discussion
- Refreshed and archived the live Overleaf sources under
  `manuscript/archive/overleaf_before_fig1_panel_refs_20260824/` before editing,
  preserving all collaborator changes.
- Replaced the generic introductory Figure 1 citation with an explicit
  `Figure 1(a,b)` reference identifying the Mott- and CDW-side backgrounds and
  their respective virtual hops.
- Added `Fig. 1(a)` directly to the large-$U$, $V=0$ derivation, where the
  singly occupied spin background produces the virtual doublon--holon process,
  and added `Fig. 1(b)` to the large-$V$, $U=0$ derivation, where the
  checkerboard background produces the $7V$ charge defect.
- Local visual and text QA passed. Overleaf compiled the 29-page supplement
  with 0 errors/0 warnings and the 8-page main manuscript with 0 errors and
  the 3 pre-existing warnings; `main.tex` was left active.
- Refreshed the local main, supplement, and 37-page combined PDFs and created
  `output/overleaf/MMHK_overleaf_upload_20260824_115314_fig1_panel_refs.zip`.

### 2026-08-25 — Supplemental revision and unambiguous mixing-resolution notation
- Began from a fresh download of the live Overleaf project, revised the
  Supplemental Material locally, and synchronized the complete affected files
  back to Overleaf. A collaborator edited the Introduction during validation;
  the final local mirror was refreshed from Overleaf so that this concurrent
  change was preserved rather than overwritten.
- Reserved $n$ for electronic density and introduced
  $n_{\mathrm{mix}}$ exclusively for the MMHK mixing resolution throughout the
  main text, supplement, and the spinless-$t$--$V$ benchmark figure. Other uses
  of $n$, including $n(\mathbf k)$, $n_0(\mathbf k)$, and integer momentum
  labels, were left unchanged.
- Reorganized and tightened the supplement: clarified the $V$-extended MMHK
  endpoint, distinguished the exact extended-Hubbard first moment from its
  strong-coupling reduction, streamlined the Mott/CDW and finite-$t'$ hopping
  derivations, defined all static-observable normalizations, added the complete
  Mott--CDW transition-bracket table, and removed redundant audit/fitting text.
- Updated `supp_figS1_spinless_tV_benchmarks.pdf` and its reproducible builder
  to display $n_{\mathrm{mix}}$. The final Overleaf source and figure hashes
  were verified against the local files.
- Overleaf validation: Supplemental Material compiled with 0 errors and 0
  warnings; the main manuscript compiled with 0 errors and the two existing
  package/float warnings. `main.tex` was restored as the main document.
- Refreshed `manuscript/main.pdf`, `manuscript/supplement.pdf`, the 38-page
  `manuscript/MMHK_current_with_supplement.pdf`, and upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260825_1435_supplement_revision_nmix.zip`.

### 2026-08-25 — Unified virtual-excitation energy notation
- Began from a fresh download of the live Overleaf project and preserved all
  collaborator edits while revising the main text and Supplemental Material
  locally.
- Removed the one-use form factor $\mathcal F_{\mathbf k}$ from the main-text
  discussion above Eq. 7. The exact commutator is now reduced there directly
  to $\mathcal M_1(\mathbf k)=\varepsilon_{\mathrm{NN}}(\mathbf k)
  -V\delta_{\mathbf k}+O(t^2/V)$ at leading order; the exact
  $\mathcal F_{\mathbf k}$ definition remains in the Supplemental Material.
- Replaced the finite-$(U,V)$ virtual-energy symbols $D_{\mathrm M}$ and
  $D_{\mathrm C}$ by $\Delta E_{\mathrm M}=U-V$ and
  $\Delta E_{\mathrm C}=7V-U$ throughout the main text and supplement, while
  retaining $\Delta_{\mathrm M}$ and $\Delta_{\mathrm C}$ for the distinct
  particle--hole sector separations.
- Updated Figure 1 and its caption consistently to label the limiting virtual
  costs as $\Delta E_{\mathrm M}=U$ and $\Delta E_{\mathrm C}=7V$. The
  editable PPTX was refreshed and its previous version archived under
  `archive_20260825_before_energy_subscripts/`.
- Verified byte-for-byte identity of the final Overleaf `main.tex`,
  `supplement.tex`, and Figure 1 PDF against the local synchronized files.
  Overleaf compiled the 30-page supplement without errors or warnings and the
  8-page main manuscript with 0 errors and its two existing package/float
  warnings; `main.tex` remains the main document.
- Refreshed `manuscript/main.pdf`, `manuscript/supplement.pdf`, the 38-page
  `manuscript/MMHK_current_with_supplement.pdf`, and
  `manuscript/MMHK_overleaf_upload_20260825_energy_notation.zip`.

### 2026-08-25 — Local-only clarification of the two-sector moment representation
- Revised only the local `manuscript/main.tex`, leaving the live Overleaf
  project unchanged as requested.
- After Eq. 4, clarified that $E_h$ and $E_p$ are centroids of the complete
  many-pole removal and addition sectors and that $w_h$ and $w_p$ are their
  integrated spectral weights; the two-sector representation does not assume
  a two-pole spectrum.
- After Eq. 5, added the physical meanings of $\mathcal C_{\mathbf k}$
  (sector-centroid midpoint), $\delta_{\mathbf k}$ (integrated spectral-weight
  imbalance), and $\Delta_{\mathbf k}$ (centroid separation), and explained
  how the latter two generate an $O(t)$ GZ displacement.
- Local compilation succeeded with no errors or unresolved references. Visual
  inspection of pages 4--5 found no clipping or overlap. Refreshed the local
  8-page `main.pdf` and 38-page combined PDF; no Overleaf files or upload
  bundles were modified.

### 2026-08-25 — Local-only leading-zero scope clarification
- Further tightened the local text after Eqs. 4 and 5. It now states explicitly
  that the sector-centroid expansion is used only to locate the leading
  gap-interior zero, while retaining the warning that the spectrum is not
  assumed to contain only two poles.
- Condensed the definitions of $\mathcal C_{\mathbf k}$,
  $\delta_{\mathbf k}$, and $\Delta_{\mathbf k}$ to remove repeated
  references to sector centroids without losing their physical meanings.
- Local compilation and page-level visual inspection succeeded. Refreshed the
  local main and combined PDFs. Overleaf was not modified.

### 2026-08-25 — Overleaf synchronization of sector-centroid clarification
- Began from a fresh download of the live Overleaf project and applied only the
  approved Eq. 4--5 clarification, preserving all intervening collaborator
  changes. A second source download confirmed that no concurrent edits occurred
  before upload, and the final post-upload source was verified byte-for-byte.
- Clarified that $E_h,E_p$ and $w_h,w_p$ describe the centroids and integrated
  weights of the complete many-pole removal/addition sectors, that the spectrum
  is not assumed to contain only two poles, and that the sector-centroid
  expansion is used only to locate the leading gap-interior GZ.
- Defined the physical roles of $\mathcal C_{\mathbf k}$,
  $\delta_{\mathbf k}$, and $\Delta_{\mathbf k}$ immediately after Eq. 5 and
  condensed the subsequent strong-coupling scaling explanation.
- Overleaf validation: the 30-page Supplemental Material compiled with 0 errors
  and 0 warnings; the 8-page main manuscript compiled with 0 errors. The main
  log retains seven pre-existing warnings, including the collaborator-added
  unresolved bibliography key `chubukov`; no unrelated bibliography text was
  changed. `main.tex` was restored as the active main document.
- Refreshed the canonical local `main.tex` and `supplement.tex` from the final
  Overleaf snapshot, the corresponding 8- and 30-page PDFs, the 38-page
  `MMHK_current_with_supplement.pdf`, and exact post-upload source bundles in
  `manuscript/` and `output/overleaf/`.

### 2026-08-25 — Supplemental numerical-precision standardization
- Edited and uploaded **only** `supplement.tex`; `main.tex` was not uploaded or
  modified by this task. A concurrent collaborator edit to `main.tex` was
  preserved on Overleaf and mirrored locally only after the supplemental update.
- Standardized displayed numerical values in the Supplemental Material to at
  most three decimal places and percentage values to at most two decimal places.
  Scientific notation is retained for small residuals when fixed three-decimal
  notation would erase useful information.
- Automated source and embedded-supplementary-figure audits found no remaining
  decimal token above the requested precision. The 30-page supplement compiled
  on Overleaf with 0 errors and 0 warnings, and `main.tex` was restored as the
  active main document.
- Verified byte-for-byte equality of the final local and Overleaf
  `supplement.tex`; refreshed the 8-page main PDF, 30-page supplement PDF,
  38-page combined PDF, validation report
  `results/supplement_precision_validation_20260825.json`, and upload bundle
  `output/overleaf/MMHK_overleaf_upload_20260825_supp_precision3.zip`.

### 2026-08-27 — Finite-ratio and mixing-resolution clarification
- Began from a fresh download of the live Overleaf project, applied the approved
  changes only to `main.tex`, and used a second pre-upload source snapshot to
  confirm that no concurrent collaborator edits had occurred. The final
  post-upload source is byte-for-byte identical to the synchronized local file;
  `supplement.tex` and all figures were unchanged.
- Removed the explicit small-$U/V$ expansion after Eq. 9 from the main text and
  replaced it with the physical statement that the leading CDW-side
  strong-coupling coefficient depends only on $U/V$. The detailed expansion
  remains available in the Supplemental Material.
- Distinguished the neutral virtual-defect costs $\Delta E_{\mathrm M}$ and
  $\Delta E_{\mathrm C}$, which control hopping coherence and spectral-weight
  transfer, from the charged addition--removal centroid separations
  $\Delta_{\mathrm M}$ and $\Delta_{\mathrm C}$ entering the GZ moment identity.
- Added a Discussion clarification that finite-resolution 16-MMHK approximates
  the full extended-Hubbard $U$--$V$ physics, whereas the leading GZ relations
  are independently supported by strong-coupling expansions of the underlying
  Hamiltonian. Increasing momentum-mixing resolution should refine numerical
  correlators such as $\langle\mathbf S_i\!\cdot\!\mathbf S_j\rangle_b$ toward
  their thermodynamic values without changing the leading momentum form of
  $\omega_{\rm GZ}$.
- Overleaf validation: the 30-page supplement compiled with 0 errors and 0
  warnings; the 8-page main manuscript compiled with 0 errors and 4 existing
  warnings. `main.tex` was restored as the main document.
- Refreshed `manuscript/main.tex`, `manuscript/supplement.tex`, their 8- and
  30-page PDFs, the 38-page `manuscript/MMHK_current_with_supplement.pdf`, and
  the post-upload source bundles in `manuscript/` and `output/overleaf/`.

### 2026-08-28 — Spin-resolved momentum weights in the main-text moment relation
- Began from a fresh Overleaf source snapshot and confirmed with a second
  pre-upload download that no concurrent collaborator edits occurred. The only
  intentional source edit was to `main.tex`; `supplement.tex`, the bibliography,
  and all figures were unchanged on Overleaf.
- Replaced the abstract removal/addition weights $w_h,w_p$ in the main-text
  sector-centroid Green function by the exact zeroth-moment identities
  $n_{\mathbf k\sigma}$ and $1-n_{\mathbf k\sigma}$, with
  $n_{\mathbf k\sigma}=\langle c^\dagger_{\mathbf k\sigma}
  c_{\mathbf k\sigma}\rangle$ defined explicitly as the spin-resolved momentum
  distribution.
- Rewrote the leading gap-interior relation as
  $\omega_{\rm GZ}\simeq n_{\mathbf k\sigma}E_p+
  (1-n_{\mathbf k\sigma})E_h=\mathcal C_{\mathbf k}+
  \delta_{\mathbf k}\Delta_{\mathbf k}$ and defined
  $\delta_{\mathbf k}=n_{\mathbf k\sigma}-1/2$. The signed first moment now uses
  the complementary weighting directly in the same notation. Formal
  $w_h,w_p$ Lehmann notation remains in the Supplemental Material, where it is
  useful for the detailed derivation.
- Local compilation and visual inspection of the affected main-text pages
  succeeded. Overleaf validation: the 31-page supplement compiled with 0 errors
  and 0 warnings; the 8-page main manuscript compiled with 0 errors and 4
  existing warnings. `main.tex` was restored as the main document.
- Verified the post-upload Overleaf `main.tex` byte-for-byte, synchronized the
  complete current Overleaf snapshot locally, and refreshed the 8-page main,
  31-page supplement, 39-page combined PDF, and upload bundles in `manuscript/`
  and `output/overleaf/`.

### 2026-08-28 — Strong-coupling selection rules and one-hop derivation
- Began from a fresh Overleaf source snapshot and changed only
  `supplement.tex`, preserving the current collaborator-edited `main.tex`.
- Made the reduction after Eq. S44 explicit: the first-order
  Schrieffer--Wolff correction contains only nearest-neighbor virtual hops;
  bipartite particle--hole symmetry removes all same-sublattice coherences;
  and the first allowed longer-range opposite-sublattice coherences begin at
  three hops, $O(t^3/U^3)$. A direct inverse Fourier transform of the
  all-momentum $U=40,V=0$ data confirms that the leading distance-three
  coherences are below 0.7% of the nearest-neighbor value.
- Added the reproducible audit script
  `scripts/analyze_u40v0_real_space_coherence.py` and output
  `results/u40v0_real_space_coherence_from_fullobs_nk.csv`.
- Clarified that the quoted 16-site $U\to\infty$ spin correlator comes from one
  periodic $4\times4$ Heisenberg exact diagonalization, not an average over
  continuous mixed-momentum sectors. At leading $t^2/U$, sector phases cancel
  in each forward--reverse virtual hop. Added the expectation that increasing
  momentum-mixing resolution approaches the thermodynamic spin correlator.
- Expanded the CDW one-hop construction following Eq. S66: defined
  $H=H_0+H_t$, evaluated the matrix element and $7V$ denominator explicitly,
  constructed the first-order wavefunction, and showed why only one cross term
  contributes to the directed per-spin coherence $t/(7V)$.
- Removed Supplemental Sec. 8.3, “Direct comparison with the numerical
  coefficients,” including its residual table and auxiliary finite-ratio curve
  construction.
- Overleaf validation: the 32-page supplement compiled with 0 errors and 0
  warnings; the 8-page main manuscript compiled with 0 errors and 4 existing
  warnings. `main.tex` was restored as the main document. Refreshed local
  sources, PDFs, combined 40-page review PDF, and Overleaf upload bundles.

### 2026-08-28 — Fixed-$U$ labels and $V$-only frustrated-hopping scans
- Began from a fresh Overleaf source snapshot and confirmed with a second
  pre-upload download that no concurrent collaborator edits occurred.
- Added a visible $U/t=40$ annotation to Supplemental Figs. S9 and S10 and
  stated the fixed interaction in both captions.
- Removed the standalone $4\times2$ observable-check paragraph from the
  Supplemental Material.
- Added the $V$-only counterparts of Figs. S11 and S12 as Figs. S13 and S14
  for $t'=-0.25t$ and $-0.4t$. Each figure contains the $V/t=2,5,8,12$
  spectral sequence, the extracted GZ dispersions, and a direct comparison of
  the $V=12$ curve with the parameter-free
  $-(8/7)\varepsilon_{\mathrm{NN}}+\varepsilon_{\mathrm{NNN}}$ rule.
- Added the reproducible generator
  `scripts/build_supp_vonly_tprime_figures.py` and its machine-readable fit
  receipt `results/supp_vonly_tprime_bond_coefficients.json`.
- Overleaf validation: the 34-page supplement compiled with 0 errors and 0
  warnings; the 8-page main manuscript compiled with 0 errors and the 4
  existing typesetting warnings. The post-upload source and all four affected
  figure PDFs were verified byte-for-byte, and `main.tex` remains the main
  document. Refreshed local sources, PDFs, the 42-page combined review PDF,
  and the Overleaf upload bundle.

### 2026-08-28 — Explicit Fig. S10 rules and streamlined fixed-$U$ labeling
- Began from the current Overleaf source snapshot and changed only the
  supplement source and Figs. S9--S10; the collaborator-edited `main.tex`
  remained unchanged.
- Removed the visible `$U/t=40$` headings from Figs. S9 and S10 while retaining
  the fixed interaction in both captions.
- Added the complete leading strong-coupling formulas used in Fig. S10 for
  $E_0/N_s$, the $n(\mathbf k)$ slope, $K/N_s$, double occupancy, and the NN
  density product. The text and caption now map each row of the formula table
  to panels (a)--(d), state why panels (b,c) carry a minus sign, and identify
  the dotted atomic envelope in panel (a).
- Updated `scripts/analyze_fullobs_u40_scan.py` so the regenerated figure uses
  Mott/CDW terminology consistently and no longer draws the redundant fixed-$U$
  headings.
- Overleaf validation: the 34-page supplement compiled with 0 errors and 0
  warnings; the 8-page main manuscript compiled with 0 errors and the 4
  existing typesetting warnings. `main.tex` was restored as the main document.
  Refreshed local PDFs, the 42-page combined review PDF, and the Overleaf upload
  bundle.

### 2026-08-28 — Added physical discussion of Figs. S13--S14
- Began from the current Overleaf source and changed only `supplement.tex`; the
  collaborator-edited `main.tex` and all figure files were left unchanged.
- Expanded the short introduction to Figs. S13 and S14 to describe the visible
  separation between the interaction-scale particle-addition/removal bands and
  the finite-$O(t)$ gap-interior GZ dispersion, the rapid collapse of the
  extracted curves with increasing $V$, and the $V/t=12$ agreement with
  $-(8/7)\varepsilon_{\mathrm{NN}}+\varepsilon_{\mathrm{NNN}}$.
- Clarified that changing $|t'|$ from $0.25t$ to $0.4t$ reshapes the GZ through
  the NNN dispersion while preserving the local-defect NN and NNN coefficients,
  rather than producing a new global rescaling.
- Local and Overleaf validation both succeeded: the 34-page supplement compiled
  with 0 errors and 0 warnings; the 8-page main manuscript compiled with 0
  errors and the 4 existing typesetting warnings. `main.tex` was restored as
  the Overleaf main document. Refreshed the local PDFs, 42-page combined review
  PDF, and Overleaf upload bundle.

### 2026-08-31 — Synchronized the Supplemental Material author list
- Began from a fresh download of the current Overleaf source of record and
  changed only the Supplemental Material author declaration.
- Replaced the two consecutive standard-article `\\author` declarations with
  `\\author{Peizhi Mai and Philip W. Phillips}`, preserving the author order in
  the main manuscript and ensuring that both names render on the SI title page.
- Overleaf validation: the 34-page supplement compiled with 0 errors and 0
  warnings; the unchanged 8-page main manuscript compiled with 0 errors and the
  4 existing warnings. `main.tex` was restored as the Overleaf main document.
- Synchronized the current Overleaf sources locally and refreshed the local
  main/SI PDFs, 42-page combined review PDF, audit patch, and upload bundle.

### 2026-08-31 — Matched Supplemental Material affiliations to the main text
- Began from a fresh Overleaf source download and confirmed immediately before
  upload that `main.tex`, `supplement.tex`, and `references.bib` had not changed
  concurrently.
- Added numbered affiliations to the SI title page: Peizhi Mai carries the
  University of Tennessee and University of Illinois affiliations, while
  Philip W. Phillips carries the University of Illinois affiliation, matching
  the main-text front matter.
- Split the longer Illinois affiliation across two centered lines so the title
  block remains within the page margins.
- Overleaf validation: the 34-page supplement compiled with 0 errors and 0
  warnings; the unchanged 8-page main manuscript compiled with 0 errors and the
  4 existing warnings. `main.tex` was restored as the Overleaf main document.
- Refreshed the synchronized local sources, PDFs, 42-page combined review PDF,
  audit patch, and Overleaf upload bundle.
