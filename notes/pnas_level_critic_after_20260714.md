# Critic Report: pnas_critic_packet

Generated: 2026-07-14T10:57:06-04:00
Target: pnas_critic_packet
Kind: project
Style: balanced
Goal: Final submission audit: judge whether this revised main manuscript plus SI is credible and competitive for PNAS, distinguishing remaining new-calculation needs from textual or factual defects.
Packet: 4 included, 0 skipped, 58748 content bytes

---

# Executive Verdict

This is a promising and potentially publishable paper, but it is not yet credible enough for a competitive PNAS submission. The two strong-coupling limits are the strongest contribution: the \(4C_1\) and \(8/7\) results are concrete, interpretable, and plausibly novel. The central finite-\(U,V\) claim, however, rests entirely on one \(4\times4\) interaction resolution, one broadening, sparse sampling near \(V/U=1/4\), and no independent calculation of the competing phase boundary. Most seriously, the manuscript repeatedly calls a finite-\(\eta\) root of \(\operatorname{Re}G\) a “Green-function zero,” even though the complex \(G\) generally does not vanish there. Unless that terminology and the fixed-resolution scope are corrected—and targeted robustness calculations are added—the paper risks being judged as an interesting MMHK observation overinterpreted as extended-Hubbard physics.

# Top Critical Issues

1. **The reported observable is not demonstrably a zero of the Green function.**
   - **Why it matters:** The operational definition is \(\operatorname{Re}G(\mathbf k,\omega_0)=0\) at fixed \(\eta=0.05\). At finite broadening, \(\operatorname{Im}G\) is generally nonzero, so \(G\neq0\). “Low spectral weight” does not make the complex function vanish. This affects the title, abstract, significance statement, and central conceptual claim.
   - **Concrete fix:** Either demonstrate convergence toward a genuine zero as \(\eta\to0^+\)—including \(\operatorname{Im}G(\omega_0)\), root motion, and scale \(s(\eta)\)—or consistently call the observable a “gap-interior zero crossing of \(\operatorname{Re}G\)” or “real-part sign-change dispersion.” Reserve “Green-function zero” for the limiting object and state the conditions under which the identification is justified.

2. **The headline reorganization is established only at one interaction resolution.**
   - **Why it matters:** A \(4\times4\) mixing resolution is not the thermodynamic extended Hubbard model. Continuous twists improve external momentum sampling but do not restore the omitted interaction channels. No evidence shows that the maximum, discontinuity, or fitted branches survive increasing mixing resolution.
   - **Concrete fix:** The high-value new calculation is at least one additional interaction resolution for representative Mott-side, \(V/U=1/4\), and charge-side points. If infeasible, the title, abstract, significance statement, and conclusions must explicitly describe a “fixed-resolution MMHK reorganization,” not an established property of the extended Hubbard model.

3. **The claimed maximum exactly at \(V/U=1/4\) is stronger than the sampling supports.**
   - **Why it matters:** The boundary point is sampled by construction, excluded from both fits, and followed by unevenly spaced charge-side points: \(0.275\), \(0.30\), and \(0.2625\) for the three families. This establishes a sampled maximum, not the location of a continuous maximum. For \(U=40\), the first charge-side point is particularly remote, so “immediately above” is inaccurate.
   - **Concrete fix:** Add dense scans on both sides of \(1/4\), especially for \(U=40\), and report ground-state crossings or avoided crossings, sector energies, gaps, and hysteresis/branch coexistence if applicable. Without those calculations, use exact language: “the largest sampled value occurs at \(V/U=1/4\), followed by a lower value at the first sampled point above it.”

4. **There is no direct evidence that the observed switch corresponds to Mott–charge-order competition.**
   - **Why it matters:** The momentum-distribution variance is independent of root selection but is not an order parameter and does not distinguish a genuine background change from a finite-sector level crossing or altered spectral weights. The manuscript itself admits that charge structure factors and independently minimized sector gaps are missing.
   - **Concrete fix:** Calculate at minimum the checkerboard charge structure factor, spin correlations, double occupancy, and relevant ground-state/sector energies across the same dense boundary grid. This is new-calculation work, not a textual repair.

5. **The model definition is explicit but not yet conceptually clean enough.**
   - **Why it matters:** Equations 2–5 alternate between the “target extended-Hubbard Hamiltonian,” the retained \(16\)-mode interaction, and a dual periodic \(16\)-orbital problem. The statement that “the interaction terms of Eq. 2 act inside” the sector can be read as exact equivalence, although cross-twist scattering is omitted. Readers need to know precisely which Hamiltonian is diagonalized.
   - **Concrete fix:** Present one boxed MMHK sector Hamiltonian containing kinetic energy, chemical potential, \(U\), and \(V_{\mathbf q}\), followed by a precise map to the target model and an explicit list of omitted scattering processes. Clearly distinguish exact statements about the sector Hamiltonian from conjectured implications for the extended Hubbard model.

6. **The first-moment language remains more exact than the derivation warrants.**
   - **Why it matters:** Equation 8 is exact only for the constructed two-effective-pole approximation. For the full spectral measures it is an asymptotic result requiring separated sectors, controlled widths, and a root sufficiently far from spectral support. The phrase “normalized first moments” may suggest exact determination of the actual root.
   - **Concrete fix:** State at first use that this is a leading strong-coupling reconstruction, not an exact moment identity for the full \(G\). Quantify the correction using the direct-root versus first-moment discrepancies already shown, and verify the predicted \(1/U\) or \(1/V\) scaling rather than merely writing \(O(t^2/U)\) and \(O(t^2/V)\).

7. **The regression and bootstrap analysis overstates statistical precision.**
   - **Why it matters:** Bootstrap intervals over deterministic, correlated calculation points do not capture resolution, broadening, frequency-grid, truncation, branch-definition, or model-form uncertainty. With only three \(U\) families, leave-one-family-out selection is weak, and the 5% parsimony threshold appears arbitrary.
   - **Concrete fix:** Emphasize effect sizes and sensitivity rather than narrow “95%” intervals. Add model-form envelopes, frequency/Lanczos convergence, \(\eta\) sensitivity, and boundary-point sensitivity. Treat Eqs. 11–12 as descriptive parameterizations unless a perturbative derivation is supplied.

# Hidden Assumptions

- Continuous twist sampling is assumed to compensate sufficiently for the fixed \(16\)-mode interaction truncation; it does not restore omitted cross-twist scattering.
- A low-\(\rho_G\) crossing of \(\operatorname{Re}G\) at finite \(\eta\) is assumed to represent a true zero of \(G\).
- The branch selected by continuity is assumed to be physically unique rather than an algorithmically preferred path through multiple sign changes.
- The \(16\)-site Heisenberg correlator is assumed to be the correct asymptote of the finite-resolution MMHK calculation; the derivation needs a clearer connection between the sector Hamiltonian and that spin problem.
- The charge-ordered translation-symmetric state is assumed to represent the relevant charge background without explicit symmetry-breaking or finite-resolution scaling.
- The rapid decrease above \(1/4\) is assumed to reflect competing insulating mechanisms rather than a finite-sector ground-state level crossing.
- Path variance of \(n(\mathbf k)\) is assumed to be an independent physical confirmation, although it derives from the same Lanczos spectral data and Hamiltonian.
- A scaled nearest-neighbor band plus offset is assumed to capture the full zero curve; no systematic comparison with higher harmonics is reported.
- The atomic ratio \(V/U=1/4\) is assumed to remain the meaningful organizing point at finite hopping and at this resolution.

# Weak Evidence or Logic Gaps

- The paper does not show \(|G|\), \(\operatorname{Im}G\) at the root, or \(\eta\to0\) behavior.
- No dense scan establishes the peak location or the width and character of the reorganization.
- No charge structure factor, spin structure factor, double occupancy, or sector-energy crossing accompanies the claimed mechanism switch.
- Root-rule agreement is less independent than presented: all seven rules operate on the same candidate roots generated from the same broadened continued fractions.
- The \(n(\mathbf k)\) check is independent of root fitting but not independent of the underlying calculation.
- The strong-coupling remainder estimates are asserted without numerical scaling tests of the residuals.
- The charge-side \(8/7\) derivation is persuasive in the atomic background, but the connection to the symmetric finite-sector ground state and possible degeneracy handling needs demonstration.
- The single-band fit lacks tests for \(\cos k_x\cos k_y\), second harmonics, or localized deviations near symmetry points.
- The statement that spectroscopy can determine the zero by Kramers–Kronig transform is technically qualified by the need for a sufficiently complete frequency range, normalization, resolution, and tails. “Concrete experimental target” is currently aspirational.
- Data and code are promised only “with submission.” A final audit cannot assess reproducibility without the root tables, raw continued fractions, convergence logs, and scripts.
- The supplied SI contains figure references and captions but not the underlying rendered figure content or numerical source data, limiting independent visual and quantitative verification.

# Failure Modes

- Referees may reject the paper on the definitional point that a zero of \(\operatorname{Re}G\) at finite broadening is not a zero of \(G\).
- Resolution scaling may shift, smooth, or eliminate the apparent maximum and branch jump.
- Dense sampling may locate the maximum away from \(1/4\) or reveal a narrow crossover/level crossing rather than a universal reorganization.
- Direct charge and spin observables may not change at the same location as the zero scale.
- The rational and quadratic fits may prove nonunique once additional \(U\) families or boundary points are included.
- Higher-harmonic dispersion may become visible with reduced broadening or improved resolution, undermining the single scale \(s\).
- PNAS editors may see the result as method-specific and specialized unless the broad conceptual significance is supported by an independent solver, controlled convergence, or a credible observable consequence.
- The experimental framing may invite skepticism because zeros are not directly bright spectral features and Kramers–Kronig reconstruction is demanding.

# Missing Work or Comparisons

**Likely necessary new calculations:**

1. \(\eta\)-dependence of the root, \(\operatorname{Im}G(\omega_0)\), \(|G(\omega_0)|\), and fitted scale.
2. Dense \(V/U\) scans around \(1/4\) for all three \(U\) values.
3. Checkerboard charge correlations, spin correlations, double occupancy, ground-state energies, and central/sector gaps across the same scan.
4. At least a limited momentum-mixing-resolution comparison.
5. Frequency-grid and Lanczos-step convergence.
6. Fits including higher lattice harmonics and pointwise residual plots.
7. If feasible, comparison at selected points with an independent method capable of real-frequency or Matsubara self-energy/Green-function analysis.

**Textual or factual repairs:**

- Replace unconditional “Green-function zero” language unless an \(\eta\to0\) demonstration is added.
- Replace “maximum at \(V/U=1/4\)” with “sampled maximum” unless densely resolved.
- Replace “immediately above” where the next point is \(0.30\).
- Make “at the present momentum-mixing resolution” unavoidable in every principal claim.
- Separate the exact sector Hamiltonian from the target extended-Hubbard Hamiltonian.
- Describe Eqs. 11–12 as empirical constrained fits, not predictive laws.
- Temper “establish,” “quantitative marker,” and experimental claims.
- State explicitly that bootstrap intervals exclude dominant systematic errors.

# Concrete Next Actions

1. **Resolve the observable-definition problem first:** run an \(\eta\) sequence and decide whether the paper concerns a true \(G\) zero or a zero crossing of \(\operatorname{Re}G\).
2. **Densify the boundary scan** and calculate charge, spin, double-occupancy, gap, and sector-energy diagnostics at identical points.
3. **Perform a limited resolution study** concentrated on the two asymptotes and three boundary-adjacent points.
4. **Audit numerical convergence:** Lanczos length, frequency mesh, root refinement, spectral window, and missing-row cases.
5. **Test dispersion form robustness** with higher harmonics and publish pointwise residuals.
6. **Rewrite the model section** around one explicit Hamiltonian actually diagonalized, followed by an exact statement of how it differs from the target model.
7. **Rewrite all headline claims** to distinguish analytic limiting results, fixed-resolution numerical observations, and conjectures about the extended Hubbard model.
8. **Replace narrow bootstrap emphasis with systematic-error accounting.**
9. **Release the complete data and scripts before submission** and regenerate every figure from the public tables.
10. **Reframe editorial significance:** lead with the two analytically distinct strong-coupling mechanisms; present the finite-ratio reorganization as a controlled numerical question rather than a settled phase-boundary result.

# Questions You Must Answer

1. At the reported \(\omega_0\), what are \(\operatorname{Im}G\) and \(|G|\), and do they vanish as \(\eta\to0^+\)?
2. Does the fitted scale and apparent branch switch remain stable for several broadenings below \(0.05\)?
3. What is the finest \(V/U\) spacing computationally feasible around \(1/4\), and where is the actual maximum within that spacing?
4. Do charge and spin correlations switch at the same coupling as the zero-dispersion branch?
5. Is the rapid change a ground-state level crossing in the \(16\)-orbital sector? If so, what symmetry sectors cross?
6. Which exact scattering terms are omitted relative to the extended Hubbard Hamiltonian, and why should they not control the boundary behavior?
7. What survives at another momentum-mixing resolution?
8. How accurately do the root residuals scale as \(t^2/U\) and \(t^2/V\)?
9. Does a fit with additional lattice harmonics materially improve the zero dispersion near the boundary?
10. Why should PNAS readers regard this as a general property of correlated insulators rather than a distinctive feature of the MMHK approximation?
11. Can the experimental claim be made quantitative—what spectral range and resolution would be required for a reliable Kramers–Kronig reconstruction?
12. If no further resolution or phase-diagnostic calculations are possible, are the authors willing to retitle and reframe the paper explicitly as a fixed-resolution MMHK result?
