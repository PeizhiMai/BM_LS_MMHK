# PNAS corpus audit and manuscript revision

**Date:** 2026-07-14  
**Corpus:** `references/pnas_80_papers_20260703`  
**Files available:** 73 research PDFs (the requested set contained seven undownloaded items)  
**Use:** structural and editorial comparison only; no wording was copied.

## Corpus-level practices adopted

A page/figure audit of the local corpus gave a median of roughly seven article pages and four main figures. The closest strongly correlated/numerical exemplars consistently use the following devices:

1. **Problem before method.** The first paragraph names an unresolved physical problem; the solver is introduced only after the knowledge gap is clear.
2. **Advance declared early.** The final Introduction paragraph states the result, the mechanism, and why it matters rather than previewing a work plan.
3. **Four-figure causal sequence.** Representative mechanism → parameter evolution → quantitative collapse/rule → independent validation.
4. **One main conclusion per figure.** Main figures avoid exhaustive grids; detailed scans and extraction diagnostics move to the SI Appendix.
5. **Independent observables.** A dynamic or fitted claim is paired with a static or methodologically independent response.
6. **Limits in Discussion.** Caveats are collected once after the result has been established, rather than repeated in the Abstract and Results.
7. **Self-contained methods.** The Hamiltonian, approximation hierarchy, measured object, and extraction rule are defined without private code paths.

The most relevant structural comparators were the local PDFs on spin–charge pseudogap scaling (`001`), the thermodynamic Hubbard calculation (`047`), pseudogap band splitting (`024`), charge/nematic numerical work (`023`), global strongly correlated phase diagrams (`011`), optimized many-body wave functions (`014`, `048`), machine-learning phase discrimination (`052`), and stripe-enhanced pairing (`058`). These papers were used to judge narrative density, figure hierarchy, and placement of validation—not as scientific sources unless cited separately in the manuscript.

## Baseline strengths

- Two parameter-free strong-coupling endpoints: (4C_1) on the Mott axis and (8/7) on the charge axis.
- Dense real-frequency data with no analytic continuation.
- Refined (U=20,40,80) interaction grids bracketing (V/U=1/4).
- Machine-readable roots and alternative branch-selection audits.
- A potentially broad organizing idea: zeros retain information about the mechanism of an insulator after low-energy poles disappear.

## Baseline editorial-rejection risks

1. The benchmark and exhaustive scans obscured the discovery.
2. MMHK was described through internal code and occasionally with misleading finite-system language.
3. The fit was chosen in-sample and the claim-status file predated completed interaction points.
4. Candidate-root and missing-row robustness were not synthesized into a main-text validation.
5. References remained placeholders; authors and affiliation were placeholders.
6. Limitations and internal advice appeared repeatedly, weakening the central claim before it was presented.
7. The principal object alternated among “Luttinger surface,” “LS,” and a finite-frequency zero without a precise distinction.

## Claims directly established by the present data

- A low-spectral-weight solution of (mathrm{Re},G(mathbf{k},omega)=0) traverses the central gap for the analyzed interaction sets.
- On the (V=0) axis, the large-(U) scale approaches the first-moment result (4|C_1|) at the employed momentum-mixing resolution.
- On the (U=0) axis, the scale converges numerically to (8/7) over (V/t=4,ldots,20).
- For (U/t=20,40,80), the scale rises on the Mott side, is maximal at the sampled (V/U=1/4) points, and is much smaller at the first sampled charge-side points.
- For audited (U\ge20) cases, seven root-selection rules give the same scale to numerical precision.
- Every retained interaction set has at least 111/121 accepted path points; complete-path-only fitting changes the selected coefficients only slightly.
- The path variance of (n(mathbf{k})), computed independently of root finding, rises and then collapses across the same interaction range.

## Claims treated as interpretation rather than direct determination

- The reorganization is tied to the **strong-coupling Mott–charge competition scale**, but the present data do not independently locate the thermodynamic CDW boundary.
- The rational Mott-side and quadratic charge-side expressions are constrained fixed-resolution scale rules, not universal equations of state.
- The (n(mathbf{k})) response supports a ground-state reorganization but is not a substitute for (S_c(pi,pi)).
- The thermodynamic value (4C_1^{\infty}) is a comparison; the calculated asymptote is governed by the spin correlator at the employed interaction resolution.

## Before/after audit

| Dimension | Before | After |
|---|---|---|
| Title | Descriptive and method centered | “Green-function zeros reveal competing Mott and charge-ordering scales” |
| Abstract | Detailed and partially defensive | 159 words; mechanism, reorganization, and validation only |
| Introduction | Benchmark-heavy; placeholders | Four problem-first paragraphs with verified numerical, zero, MMHK, and extended-Hubbard citations |
| Main figures | Benchmark + multiple exhaustive scans | Four-figure discovery sequence: endpoints, spectral switch, scale rule, independent robustness |
| MMHK definition | Private code path and ambiguous physical-size language | Target Hamiltonian, twist-sector momentum mixing, thermodynamic sampling, and resolution hierarchy |
| Central object | Mixed LS/zero terminology | (omega_0(mathbf{k})), explicitly distinguished from (G(mathbf{k},0)=0) |
| Scale fit | In-sample empirical rule | (U\ge20), constrained asymptotes, leave-one-(U)-family-out selection, bootstrap intervals |
| Robustness | Dispersed diagnostics | (n(mathbf{k})), branch spread, residuals, and accepted-path fraction in one main figure |
| Limitations | Repeated in Abstract/Results/Discussion | One focused Discussion paragraph |
| References | `[REF: ...]` scaffolding | Numerical BibTeX citations plus a legal-access link checklist |
| SI Appendix | Derivation note only | Benchmarks, full scans, audits, sensitivity, (t'), and both detailed derivations |

## Remaining scientific risk after revision

The strongest remaining reviewer request is predictable: direct charge structure, sector-resolved gaps, and resolution scaling near (V/U=1/4). The revised paper does not hide this gap, but neither does it allow the absent diagnostics to erase what the current calculation directly establishes: a repeated, analytically anchored, extraction-robust reorganization of the gap-interior zero dispersion.
