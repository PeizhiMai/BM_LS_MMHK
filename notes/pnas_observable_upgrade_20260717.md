# PNAS manuscript enrichment from the all-momentum observable scan

**Date:** 2026-07-17  
**Primary sources:** `results/fullobs_U40_observable_summary_by_V_20260717_123231.csv` and `results/fullobs_U40_data_quality_20260717_123231.json`

## Editorial advance

The previous manuscript inferred the Mott--charge reorganization mainly from the Green-function-zero scale, a path momentum distribution, and extraction audits. The completed all-twist calculation supplies the missing physical identification. At `U=40`, every direct charge and spin observable switches between `V=10` and `11`, and the exact Hellmann--Feynman derivative of the energy changes discontinuously. The paper can therefore present the dynamical zero-dispersion anomaly as coincident with a first-order branch crossing in the present momentum-mixing construction, rather than only as an extraction-robust crossover.

## Main-text changes

1. The abstract and Significance Statement now connect the hidden zero dispersion to the independently measured ground-state branch crossing.
2. Main Figure 4 now shows charge observables, spin observables, the energy derivative, and `n_Gamma`; the former extraction-audit figure moved to the SI.
3. The Results section reports the direct jump in double occupancy, checkerboard structure, spin correlations, and `d(E/N)/dV`.
4. The full momentum distribution is interpreted through the virtual defect denominators `U-V` and `7V-U`.
5. The Discussion no longer says that direct charge structure factors are unavailable. The remaining scope question is interaction-resolution and sector scaling, not absence of a physical diagnostic.

## SI additions

- Symmetry and trapezoidal weighting of the `41x41` twist grid.
- Data completeness and exact identity checks.
- Full two-dimensional `n(k)` maps, separated into Mott and CDW rows, with a noninteracting reference.
- Strong-coupling predictions for energy, kinetic energy, `D_i`, nearest-neighbor density, and `n(k)`.
- Full `4x2` exact-diagonalization validation of every added observable operator.
- The former main-text root/fit/coverage audit.

## PNAS-level claim hierarchy

- **Derived:** asymptotic zero scales `4 C_1` and `8/7`.
- **Directly calculated:** zero-scale reorganization for `U=20,40,80`; first-order equal-time branch crossing at `U=40`; virtual-denominator control of the full `n(k)` map.
- **Scoped interpretation:** the coincidence reflects Mott--charge competition at the present momentum-mixing resolution.
- **Remaining test:** repeat boundary-adjacent observables at another interaction resolution and, if feasible, another large `U`.

## Validation

- Abstract: 161 words.
- Significance Statement: 113 words.
- No unresolved citations, references, figures, placeholders, or internal paths.
- All new quoted values match machine-readable outputs.
- Main, SI, and combined packet compile and pass visual inspection.
