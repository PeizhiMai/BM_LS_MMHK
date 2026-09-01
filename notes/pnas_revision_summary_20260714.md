# PNAS-style revision summary — 2026-07-14

## Delivered changes

- Rewrote the manuscript around the zero-dispersion discovery rather than the Hubbard benchmark.
- Restored Peizhi Mai and Philip W. Phillips with their Illinois affiliation.
- Replaced every reference placeholder with numerical citations.
- Defined the (V)-extended thermodynamic MMHK construction without private code paths or misleading finite-system terminology.
- Standardized the central observable as the gap-interior Green-function-zero dispersion (omega_0(mathbf{k})).
- Reduced the main narrative to four reproducible figures.
- Moved static benchmarks, exhaustive scans, candidate-root details, missing-row sensitivity, (t'), and full (4C_1)/(8/7) derivations to a new SI Appendix.
- Refit the (U\ge20) scale data with asymptotic constraints and leave-one-(U)-family-out model selection.
- Added 5,000-resample stratified-bootstrap intervals and complete-path-only sensitivity.
- Refreshed availability and claim-status outputs before quoting results.
- Created a separate 111-word Significance Statement and a 158-word abstract.
- Created a legal reference-download checklist; no new papers were downloaded.

## Quantitative fit now reported

- Mott side: (s=s(U,0)/(1-\lambda V/U)), (lambda=0.84446), 95% interval (0.82910\)–(0.85731).
- Charge side: (s=8/7+\beta[U/(4V)]^2), (eta=0.18467), 95% interval (0.18047\)–(0.19122).
- Leave-one-family-out errors: 0.01208 (Mott) and 0.00738 (charge).
- Minimum path coverage: 111/121 = 91.7%.
- Complete-path-only coefficients: (lambda=0.83614), (eta=0.18183).

## Files

- Main source/PDF: `manuscript/main_pnas_style.tex`, `manuscript/main_pnas_style.pdf`
- Significance source/PDF: `manuscript/significance_statement_pnas_style.tex`, `manuscript/significance_statement_pnas_style.pdf`
- SI source/PDF: `manuscript/supplement_pnas_style.tex`, `manuscript/supplement_pnas_style.pdf`
- Combined review PDF: `manuscript/MMHK_PNAS_revised_with_supplement.pdf`
- Reference links: `references/mmhk_reference_download_links.md`
- Baseline critic: `notes/pnas_level_critic_before_20260714.md`
- Final critic: `notes/pnas_level_critic_after_20260714.md`

## Final critic outcome

The final balanced-harsh review judged the endpoint physics intellectually strong and potentially publishable, while identifying three remaining PNAS-level new-calculation risks: finite-broadening versus true-complex-zero behavior, interaction-resolution scaling, and direct charge/sector diagnostics near the boundary. The final text now distinguishes the finite-broadening `Re G` sign-change branch from exact vanishing of the broadened complex Green function, states the sampled nature of the maximum, makes the solved finite-resolution Hamiltonian explicit, and labels fit intervals as conditional. No new simulations were introduced in this writing pass.
