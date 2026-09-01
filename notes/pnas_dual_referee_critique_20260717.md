# Critic Report: main_pnas_style.tex

Generated: 2026-07-17T14:06:30-04:00
Target: main_pnas_style.tex
Kind: paper
Style: balanced
Goal: Judge whether this manuscript meets PNAS standards. Review it from two perspectives: a senior strongly-correlated-matter referee focused on conceptual novelty, generality, and claim validity, and a junior numerical researcher focused on reproducibility, convergence, extraction choices, and figures.
Packet: 1 included, 0 skipped, 29501 content bytes

---

# Executive Verdict

The manuscript is conceptually promising but under-supported for PNAS. Its strongest result is the proposed connection between an in-gap sign change of \(\mathrm{Re}\,G\) and distinct spin- versus charge-controlled strong-coupling backgrounds; however, the paper does not yet establish that the extracted object is a true Green-function zero rather than a finite-broadening cancellation, nor that the behavior survives improvement beyond the \(4\times4\) MMHK interaction resolution. The first-order claim is convincing only for the particular projected sector Hamiltonian, not for the target extended Hubbard model, and even there the transition is sampled too coarsely to characterize rigorously. A specialist journal could consider a substantially strengthened version, but the present evidence does not support the generality, claim validity, and broad significance expected at PNAS. Likely recommendation: **major revision bordering on reject/resubmit**.

# Top Critical Issues

1. **The reported “Green-function zero” is not demonstrated to be a zero of the complex Green function.**
   - **Why it matters:** The central conceptual claim relies on zeros, self-energy poles, and their physical interpretation. At \(\eta=0.05\), the manuscript extracts a sign change of \(\mathrm{Re}\,G\) in a low-weight region while explicitly conceding that the broadened complex \(G\) does not vanish. A sign change of \(\mathrm{Re}\,G\) can occur between spectral features without an exact real-axis zero, especially when \(\mathrm{Im}\,G\neq0\).
   - **Concrete fix:** Show systematic \(\eta\to0\) and Lanczos-depth convergence of the root; report \(|G|\), \(\mathrm{Im}\,G\), and spectral weight at every extracted root; and demonstrate the corresponding divergence or pole evolution of the self-energy. Where possible, locate zeros directly from the unbroadened Lehmann rational function rather than from a broadened frequency mesh. If this cannot be done, rename the object throughout as an “in-gap \(\mathrm{Re}\,G\) sign-change dispersion” and narrow all claims accordingly.

2. **There is no MMHK interaction-resolution convergence, so the central physics may be a \(4\times4\) projection artifact.**
   - **Why it matters:** Continuous twist sampling is not thermodynamic convergence of the interaction approximation. The method omits scattering between different twist labels, and the authors explicitly admit that transition evolution with resolution and comparison among total-momentum sectors remain unknown. Those omissions could control the unusually abrupt, nearly atomic Mott-to-CDW switch and the coefficient \(4C_1=-1.4036\), which differs appreciably from the thermodynamic Heisenberg value.
   - **Concrete fix:** Provide at least two additional mixing resolutions wherever feasible, or smaller-resolution sequences demonstrating controlled trends in the zero scale, \(C_1\), transition location, and discontinuities. Compare competing total-momentum sectors and state symmetries. A benchmark of double occupancy alone is insufficient; benchmark energy, spin correlations, charge response, spectral moments, and transition behavior against established extended-Hubbard results.

3. **The first-order claim is overextended beyond what the data establish.**
   - **Why it matters:** The static scan jumps from \(V/U=0.25\) to \(0.275\), across which nearly every observable changes from one almost pure atomic branch to another. This supports a branch switch in the finite-resolution Hamiltonian, but it does not resolve hysteresis, coexistence, avoided crossing, intermediate order, or the transition width. “Continuity of the energy together with this derivative jump” is asserted without displaying energy branches or direct evidence of continuity at the inferred crossing. The quoted \(V_c/U=0.25038\) is far more precise than the direct numerical bracket \(0.25<V/U<0.275\).
   - **Concrete fix:** Scan densely near the crossing, calculate the lowest competing eigenstates and their quantum numbers, plot both energy branches and their derivatives, and show the actual crossing or finite-resolution gap. Test initialization/Krylov-sector dependence and possible metastability. Report \(V_c\) only to precision justified by the sampling and systematic errors. Restrict the claim explicitly to the \(4\times4\) MMHK Hamiltonian unless resolution convergence is demonstrated.

4. **The analytical results central to novelty are not sufficiently established in the supplied manuscript.**
   - **Why it matters:** The parameter-free limits \(4C_1\) and \(8/7\) are the most potentially publishable results, yet their derivations are deferred to an unavailable SI. The two-effective-pole argument is not itself exact for a many-pole Green function, and the statement that sector variances shift the root only at \(O(t^2/U)\) or \(O(t^2/V)\) is not proven here. Likewise, the counts \(7V\), \(8V\), and the formulas for \(n(\mathbf k)\) appear without enough derivation to check conventions or degeneracy effects.
   - **Concrete fix:** Put a self-contained derivation of both asymptotes in the main paper. Clearly distinguish exact identities, controlled strong-coupling expansions, and heuristic two-pole reconstructions. Give the perturbative order, assumptions about the ground-state manifold, chemical-potential convention, and treatment of checkerboard degeneracy. Validate the derivations against exact spectral moments computed from commutators.

5. **The PNAS-level significance and generality are not yet demonstrated.**
   - **Why it matters:** The calculation currently shows that one approximate solver can distinguish two already familiar insulating backgrounds in a canonical model. It remains unclear whether the proposed zero scale provides information not already available more robustly from spin/charge correlations, \(n(\mathbf k)\), or spectral edges. The finite-frequency root is also not obviously experimentally observable with the precision implied.
   - **Concrete fix:** Demonstrate portability to another controlled method, cluster size, or model regime; establish a quantitative relation to an observable reconstruction protocol; and articulate what the zero predicts that conventional diagnostics do not. A convincing independent calculation at selected parameters would materially improve the PNAS case.

# Hidden Assumptions

- A low-\(\rho_G\) sign change of \(\mathrm{Re}\,G_\eta\) continuously approaches a zero of the physical retarded \(G\) as \(\eta\to0^+\).
- The root selected by continuity is physically privileged when multiple in-gap sign changes exist.
- The “central gap” can be identified unambiguously and consistently across the transition and all momenta.
- Two sector means and weights control the zero while higher moments contribute only at the claimed subleading order.
- Twist integration compensates sufficiently for the limited interaction-momentum resolution.
- The \(Q=(0,0)\) ground state remains globally lowest throughout the parameter range.
- The translation-symmetric checkerboard combination faithfully represents the thermodynamic charge-ordered phase and its Green function.
- Agreement in double occupancy establishes adequacy for nonlocal correlations and Green-function zeros.
- The branch switch near \(V/U=1/4\) is physical rather than enhanced by the restricted scattering space or sector choice.
- Conditional bootstrap intervals quantify meaningful uncertainty despite excluding dominant systematic errors from resolution, broadening, model selection, and transition sampling.
- A Kramers–Kronig reconstruction from experimental spectra could locate the proposed zero despite finite energy range, backgrounds, matrix elements, and noise.

# Weak Evidence or Logic Gaps

- No \(\eta\)-dependence is presented even though the definition explicitly depends on \(\eta=0.05\).
- No frequency-grid convergence, continued-fraction convergence, Lanczos residuals, spectral sum-rule errors, or root uncertainties are reported.
- Retaining 111 of 121 momentum points measures coverage, not correctness of the extracted branch.
- Agreement among seven root-selection rules is not independent physical validation because all rules operate on the same broadened data.
- The linear form \(\omega_0=-s\epsilon_{\mathbf k}+\delta\) is assumed without reporting residuals, higher harmonics, parameter covariance, or where it fails.
- The empirical finite-\(U,V\) rules are selected from an unspecified candidate set. Leave-one-\(U\)-family-out validation across only three families provides weak evidence of universality.
- The Mott-side denominator explanation invokes \(U-V\), but the fitted rational denominator is \(1-0.8445V/U\), not the naive \(1-V/U\). The physical origin of the fitted coefficient is unresolved.
- The first charge-side sampled point differs among \(U\) families, limiting claims of a common abrupt branch.
- Static “independence” from the root finder is useful but not methodological independence: the observables use the same approximate Hamiltonian and resolution.
- The text calls the gap-interior curve “dark” yet offers no realistic uncertainty analysis for Kramers–Kronig extraction from finite-window spectra.
- Figures and SI are not available in the supplied packet, so visual quality, fit residuals, derivations, benchmark details, and audit results cannot be verified.
- The positioning cites broad zero literature but does not sharply compare this finite-frequency construction with prior cluster-DMFT, exact-diagonalization, strong-coupling, or self-energy-zero analyses of Mott and extended-Hubbard systems.

# Failure Modes

- The \(\mathrm{Re}\,G\) root moves, splits, or disappears as \(\eta\to0\), revealing a broadened interband cancellation rather than a genuine Green-function zero.
- Increasing MMHK resolution changes \(C_1\), the zero amplitude, or the apparent discontinuity enough to invalidate the quantitative rules.
- A different total-momentum or symmetry sector lies below the assumed \(Q=(0,0)\) state near the transition.
- Dense sampling uncovers an intermediate phase, avoided crossing, or shifted boundary hidden by the \(V=10\) to \(11\) interval.
- Higher spectral moments produce order-\(t\) corrections, undermining the two-sector interpretation and claimed parameter-free coefficients.
- The fitted rational and quadratic laws fail outside the three training families and prove to be convenient interpolation rather than physics.
- Conventional equal-time observables remain more reliable and informative, leaving no compelling reason to use the zero dispersion.
- Experimental reconstruction is too ill-conditioned for the proposed diagnostic to be observable.
- The target extended-Hubbard model behaves differently from the projected MMHK Hamiltonian, making the title and abstract overly general.

# Missing Work or Comparisons

- An \(\eta\to0\) study and direct unbroadened Lehmann-zero calculation.
- \(|G|\), \(\mathrm{Im}\,G\), self-energy, and spectral-weight values at the claimed roots.
- MMHK interaction-resolution scaling for both dynamical and static quantities.
- Comparisons among total-momentum and symmetry sectors near the transition.
- Dense \(V\) sampling and explicit competing energy branches around \(V_c\).
- Independent extended-Hubbard results from auxiliary-field QMC where applicable, DMRG, cluster DMFT/DCA, variational methods, or conventional finite-cluster ED.
- Full spectral-moment checks and sum rules.
- Fit residuals and tests including higher lattice harmonics such as \(\cos k_x\cos k_y\) and \(\cos2k_x+\cos2k_y\).
- A transparent list of candidate scaling models and out-of-sample tests at new \(U\) values.
- Quantitative uncertainty budgets combining broadening, frequency discretization, Lanczos truncation, missing rows, twist quadrature, fitting, and MMHK resolution.
- A sharper literature comparison establishing whether \(4C_1\), \(8/7\), or an equivalent finite-frequency zero relation has appeared previously.
- A realistic synthetic Kramers–Kronig reconstruction test with finite window, noise, and instrumental broadening.
- The referenced SI and actual rendered figures, without which several core claims cannot be assessed fully.

# Concrete Next Actions

1. Establish whether the extracted branch is a genuine zero using unbroadened Lehmann functions, \(\eta\)-scaling, \(|G|\), \(\mathrm{Im}\,G\), and self-energy diagnostics.
2. Perform an MMHK resolution study and compare all relevant momentum/symmetry sectors near the transition.
3. Resolve the transition with a much denser \(V\) grid, explicit low-lying energy branches, derivative data, and defensible uncertainty on \(V_c\).
4. Move the essential strong-coupling derivations into the main text and verify them through exact spectral moments.
5. Obtain at least one independent numerical comparison for representative Mott-side, transition-region, and charge-side points.
6. Replace conditional bootstrap bands with a complete systematic-error budget.
7. Report zero-dispersion fit residuals and test non-nearest-neighbor lattice harmonics.
8. Reframe the claims: distinguish results for \(H_{\mathrm{MMHK}}^{(16)}\) from conclusions about the extended Hubbard model.
9. Explain the unique scientific value of the zero compared with \(C_1\), charge order, double occupancy, and \(n(\mathbf k)\).
10. Only after these checks, streamline the manuscript around the analytically controlled asymptotes and the independently verified mechanism switch.

# Questions You Must Answer

1. In the \(\eta\to0^+\) limit, does both \(\mathrm{Re}\,G\) and \(\mathrm{Im}\,G\) vanish at the reported \(\omega_0(\mathbf k)\), and does the self-energy diverge there?
2. Can the zero be located directly from the finite-system Lehmann rational function without broadening or frequency gridding?
3. How do \(s\), \(C_1\), \(V_c\), and the observable jumps change with MMHK interaction resolution?
4. Why should continuous twist sampling be considered thermodynamic control when omitted interaction-scattering channels remain fixed?
5. Have all total-momentum and symmetry sectors been compared near \(V/U=1/4\)?
6. What direct numerical evidence supports energy continuity and a derivative discontinuity, rather than merely two coarse samples on opposite sides?
7. Why is \(V_c/U=0.25038\) quoted when the direct bracket is only \(0.25\)–\(0.275\)?
8. Which steps in the \(4C_1\) and \(8/7\) derivations are exact, and which rely on the two-effective-pole approximation?
9. Could higher spectral moments or additional harmonics alter the order-\(t\) zero dispersion?
10. Why does the Mott-side fit yield \(\lambda=0.8445\) if the proposed virtual denominator is \(U-V\)?
11. What new physical information does \(\omega_0(\mathbf k)\) provide that is not already evident from spin, charge, and momentum-distribution observables?
12. Can an independent solver reproduce the branch change and asymptotic coefficients?
13. How stable is the result against \(\eta\), Lanczos length, frequency mesh, twist mesh, missing rows, and central-gap definition?
14. What experimental resolution and spectral window would be required to reconstruct this zero reliably by Kramers–Kronig transformation?
15. Is the main conclusion about the extended Hubbard model, or only about the \(4\times4\) projected MMHK sector Hamiltonian?
