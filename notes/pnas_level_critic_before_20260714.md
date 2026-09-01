# Critic Report: main_pnas_style.pdf

Generated: 2026-07-14T09:26:36-04:00
Target: main_pnas_style.pdf
Kind: paper
Style: balanced
Goal: Assess whether this manuscript meets the editorial and scientific standard of a PNAS numerical condensed-matter research article
Packet: 1 included, 0 skipped, 25174 content bytes

---

# Executive Verdict

The manuscript is **promising but substantially under-supported for PNAS**. Its strongest result is the agreement of two large-coupling zero-dispersion scales with physically motivated values, \(4|C_1|\) and \(8/7\); however, the central finite-\(U,V\) claim rests on one fixed 4×4 MMHK construction, an algorithmically selected broadened-\(\mathrm{Re}\,G\) root, and no direct charge-order measurement. The paper therefore does not yet establish that the reported branch change reflects general extended-Hubbard physics rather than a finite-resolution sector crossing or root-selection feature of MMHK. MMHK itself is insufficiently defined for independent assessment: citing source files as the “source of truth” is not acceptable methodology. In its current form, an editor could reasonably reject the paper for limited generality, incomplete validation, placeholder scholarship, and a novelty claim not yet demonstrated against the existing Green-function-zero and extended-Hubbard literature.

# Top Critical Issues

## 1. The central crossover claim lacks the observables needed to identify its physical origin

**Issue:** The scale jump near \(V/U\approx1/4\) is interpreted as reorganization from Mott/spin to charge-dominated physics, but the study reports neither \(S_c(\pi,\pi)\), real-space density correlations, charge susceptibility, nor properly minimized sector-resolved charge gaps. It remains in a fixed \(Q=(0,0)\) sector, and \(n(\mathbf k)\) variance is only a proxy.

**Why it matters:** This is the manuscript’s main result. Without direct charge diagnostics, the coincidence with the classical atomic-limit boundary may be numerical or imposed by the restricted representation. Momentum-distribution variance cannot distinguish charge ordering from localization, level crossings, symmetry-sector restrictions, or changes in matrix elements.

**Concrete fix:** At every point around the anomaly, report \(S_c(\pi,\pi)\), nearest-neighbor connected density correlations, double occupancy, spin correlations, relevant ground-state energies in competing momentum/symmetry sectors, and the \(N\pm1\) charge gap. Demonstrate that the zero-scale anomaly coincides—or explicitly does not coincide—with independently measured changes in the many-body state. Until then, describe it only as an MMHK root-dispersion anomaly, not as established competition between insulating mechanisms.

## 2. MMHK is not defined rigorously enough to evaluate or reproduce

**Issue:** Equation (1) is the target extended-Hubbard Hamiltonian, not evidently the actual momentum-mixing MMHK Hamiltonian. The paper does not state the approximation, Hilbert-space organization, momentum mixing, relation to the lattice model, role of \(Q\), treatment of nonlocal \(V\), or why a 4×4 label is not an ordinary finite cluster. “Project source files … are treated as the source of truth” is especially problematic.

**Why it matters:** Readers cannot determine what problem was solved, which symmetries and correlations were retained, or whether the results are properties of the extended Hubbard model or of a particular surrogate. This ambiguity undermines both novelty and scientific validity.

**Concrete fix:** Write down the actual MMHK Hamiltonian and mapping explicitly. Define every index and sector, the momentum tiling/mixing rule, boundary twists or Peierls phases, conserved quantities, Hilbert-space size, and implementation of nearest-neighbor \(V\). State what becomes exact in any limit and what is uncontrolled. Provide convergence or comparison across at least two mixing resolutions. Code should support the paper, not replace the method.

## 3. The apparent discontinuity may be a level/sector or root-identity switch

**Issue:** The scale drops from about 1.7–1.8 to about 1.27 across sparsely sampled ratios. Branch tracking selects among multiple roots through a cost function involving continuity, spectral weight, and proximity to a presumed gap, while the ground-state sector is restricted. The manuscript has not shown that the root on one side is analytically connected to the root on the other.

**Why it matters:** A root-switching algorithm can turn a multiroot evolution into an apparent sharp branch change. Alternatively, a finite MMHK system may undergo a level crossing near the atomic-limit boundary. Either would invalidate language suggesting a general, non-smooth physical crossover.

**Concrete fix:** Plot all candidate zeros, their residues or local slopes, \(\rho(\mathbf k,\omega)\), and selected-root costs at densely spaced \(V/U\) values through the boundary. Track many-body energy levels, quantum numbers, and overlaps between neighboring ground states. Scan all relevant \(Q\) and symmetry sectors. Report results as a function of \(\eta\), frequency-grid spacing, Lanczos convergence, and MMHK resolution.

## 4. The zero is not established independently of finite broadening

**Issue:** The reported object solves \(\operatorname{Re}G_\eta(\mathbf k,\omega)=0\) at \(\eta=0.05\). For a broadened finite-system Green function, zeros of the real part need not be zeros of the complex Green function and can occur near spectral features without representing a self-energy pole.

**Why it matters:** The physical framing relies on genuine Green-function zeros, but the operational definition may instead select finite-\(\eta\) crossings. Root locations and multiplicity can be broadening-sensitive, especially near the boundary where the paper admits ambiguity.

**Concrete fix:** Show systematic \(\eta\to0\) behavior for representative Mott, boundary, and charge-side points. Demonstrate simultaneous suppression of \(|G|\) or divergence of an appropriately defined self-energy, not merely \(\operatorname{Re}G=0\). Give quantitative root uncertainties and state precisely which conclusions survive extrapolation.

## 5. The asymptotic derivations carry most of the novelty but are presented only as asserted supplementary results

**Issue:** The \(4C_1\) and \(8/7\) relations are compelling, yet the packet supplies no derivation detailed enough to check their assumptions, signs, denominators, or applicability to MMHK. The manuscript itself says these should be promoted to controlled expansions.

**Why it matters:** Without rigorous derivations, the strongest results look like post hoc interpretations of fitted numbers. The exceptionally close \(8/7\) agreement particularly demands a transparent calculation and tests beyond the dataset used to motivate it.

**Concrete fix:** Put the essential moment expansion in the main text. Define addition/removal weights and moments, identify approximations and correction orders, and show how the actual MMHK correlators enter. Validate the derivation against directly computed spectral moments. Separate exact identities from checkerboard-background assumptions.

## 6. The manuscript does not yet demonstrate PNAS-level novelty or breadth

**Issue:** It asserts a gap between conceptual work on zeros and systematic numerical dispersion maps, but references remain placeholders and no direct comparison establishes what is new relative to cluster DMFT/DCA, exact diagonalization, strong-coupling expansions, Hubbard-I approaches, or prior extended-Hubbard studies.

**Why it matters:** A specialized fixed-resolution method study needs either broad conceptual significance, decisive new physics, or unusually strong validation. Presently the result may be viewed as a property of one compact construction rather than a field-level advance.

**Concrete fix:** Build a precise literature comparison table: prior method, model, zero definition, momentum/frequency resolution, phases studied, and what this work adds. Validate at least selected parameter points with an independent solver or exact diagonalization. Explain why the finite-frequency zero dispersion is observable or useful beyond fitting a band-shaped curve.

## 7. Figure hierarchy does not support the evidentiary burden

**Issue:** Six figures devote substantial space to spectral sequences and line cuts, while the decisive missing information—sector energies, charge correlations, gap confirmation, resolution and broadening dependence—is absent. Figure 5 apparently shows only one representative audit despite text claiming several.

**Why it matters:** The visual narrative makes a clean crossover appear established before its identity and robustness are proven. Reviewers will notice that presentation strength exceeds validation strength.

**Concrete fix:** Make the scale anomaly plus direct spin/charge diagnostics the central figure. Pair it with sector energies and uncertainty bars. Move repetitive spectral panels and \(n(\mathbf k)\) cuts to the supplement. Replace the single-case audit with a compact robustness matrix covering \(\eta\), resolution, algorithms, missing-point fractions, and boundary cases.

# Hidden Assumptions

- The 4×4 MMHK spin background adequately represents the relevant thermodynamic correlations even though its \(4|C_1|\) differs appreciably from the thermodynamic value.
- Extending MMHK with real-space nearest-neighbor \(V\) preserves a controlled relationship to the extended Hubbard model.
- The fixed \(Q=(0,0)\) sector can represent or faithfully signal checkerboard charge physics at \((\pi,\pi)\).
- The particle-hole symmetric chemical potential \(\mu=U/2+4V\) is implemented consistently with the actual MMHK interaction counting.
- A zero of broadened \(\operatorname{Re}G\) within a low-weight region is the physically relevant Green-function zero.
- The same zero branch exists and retains the same identity across the sharp scale drop.
- A good fit to \(-s\epsilon_{0,\mathbf k}+\delta\) demonstrates a meaningful single scale rather than reflecting the limited harmonic content of the construction.
- Missing momentum points are unbiased and do not cluster where the dispersion most strongly deviates from the fitted band.
- Collapse versus \(V/U\) for \(U=20,40,80\) constitutes strong-coupling scaling despite only three \(U\) values and incomplete boundary sampling.
- The classical ratio \(V/U=1/4\) remains the appropriate organizing scale after kinetic and finite-resolution effects.
- Agreement with static half-filled Hubbard observables validates real-frequency zeros and the newly introduced nonlocal interaction.
- The \(V\)-only checkerboard state assumed in defect counting is the ground state selected by the numerical implementation.

# Weak Evidence or Logic Gaps

- Static energy, double occupancy, and magnetization benchmarks do not validate the frequency-dependent Green function, zero locations, or extended-\(V\) implementation.
- The text calls the scale change “non-smooth,” but no finite-size or resolution scaling distinguishes a discontinuity from a steep crossover.
- The boundary sampling is asymmetric: for \(U=40\), the next quoted charge-side point is \(V/U=0.30\), leaving a large interval precisely where the claim is strongest.
- The paper provides no statistical or systematic uncertainty on \(s\), despite root ambiguity, missing momenta, finite \(\eta\), and fit-model dependence.
- RMSE values for empirical formulas do not establish predictive theory; coefficients \(\lambda,\alpha,\beta\) are not cross-validated or derived.
- The Mott-side formula diverges outside its fitted interval and may simply parametrize a few points.
- “Independent audits” are algorithmic variants applied to the same data, not independent physical validation.
- No evidence shows that the central gap remains well-defined and comparable at all boundary points.
- No full momentum-space check establishes that behavior along \(\Gamma-X-M-\Gamma\) represents a two-dimensional zero surface.
- The extrapolation from finite-resolution \(4C_1\) to thermodynamic Heisenberg physics is discussed but not tested by increasing resolution.
- The manuscript conflates “simulates extended-Hubbard physics” with solving or approximating the extended Hubbard model without quantifying approximation error.
- The conclusion that zeros are “sensitive markers” is incomplete without showing specificity: could the same feature arise from a generic level crossing or root relabeling?
- No comparison demonstrates that the zero anomaly adds information beyond ordinary observables once direct charge and spin diagnostics are included.

# Failure Modes

- **Restricted-sector artifact:** The apparent charge branch may be produced by forcing a state into \(Q=(0,0)\) rather than allowing the true checkerboard sector.
- **Finite-resolution level crossing:** A sharp 4×4 MMHK crossing could smooth, shift, or disappear at larger mixing resolution.
- **Root-selection artifact:** The dynamic program may switch between distinct roots as their weights change, manufacturing the scale drop.
- **Broadening artifact:** Some \(\operatorname{Re}G_\eta=0\) crossings may move or vanish as \(\eta\to0\).
- **Model-specific result:** The two attractive asymptotic values may survive, while the finite-\(U,V\) piecewise rule fails in the actual extended Hubbard model.
- **Circular interpretation:** Choosing a checkerboard strong-coupling picture and emphasizing \(V/U=1/4\) may bias branch identification and fitting around the expected boundary.
- **Insufficient novelty:** Reviewers may regard the work as a numerical illustration of known atomic-limit competition plus known Green-function-zero ideas.
- **Reproducibility failure:** Reliance on internal filenames, placeholders, and unavailable project data prevents verification.
- **Editorial scope failure:** PNAS may see neither broad enough conceptual reach nor sufficiently definitive numerical evidence for a general-interest result.
- **Terminology challenge:** Referees may reject “Green-function zero” unless complex-\(G\) or self-energy evidence replaces the finite-\(\eta\) real-part criterion.

# Missing Work or Comparisons

- A complete mathematical definition of the \(U\)–\(V\) MMHK construction.
- Mixing-resolution convergence, not merely comparison with a thermodynamic correlator.
- Relevant \(Q\)-sector and symmetry-sector scans around \(V/U=1/4\).
- \(S_c(\pi,\pi)\), connected density correlations, charge susceptibility, and independently computed charge gaps.
- Spin structure factor or nearest-neighbor spin correlations across the same crossover.
- Ground-state energy levels, crossings, quantum numbers, and neighboring-state overlaps.
- \(\eta\)-dependence and preferably \(\eta\to0\) extrapolation of zero locations.
- Direct evidence for \(|G|\to0\) or self-energy poles.
- Validation of real-frequency spectra and zeros against exact diagonalization or another solver at matched small size/parameters.
- Validation of the nonlocal-\(V\) implementation in atomic and exactly tractable limits.
- Quantitative uncertainties from root choice, grid spacing, missing momenta, fit window, and spectral-weight thresholds.
- Dense two-sided boundary sampling for every large \(U\).
- Full Brillouin-zone maps rather than only a high-symmetry path.
- Tests with \(t'\neq0\) or another perturbation sufficient to show that the effect is not particle-hole-symmetry-specific.
- A complete, current literature review of Green-function zeros and extended-Hubbard charge ordering.
- Archival code/data and enough metadata to regenerate every figure.
- A convincing statement of experimental or theoretical utility: what measurable consequence follows from the finite-frequency zero dispersion?

# Concrete Next Actions

1. **Resolve the physical identity of the anomaly.** Compute charge and spin correlations, charge gaps, competing-sector energies, and state overlaps densely across \(V/U=1/4\).
2. **Write and validate the actual MMHK method.** Present its Hamiltonian, mapping, sectors, approximation structure, and \(V\) implementation; test exact limits.
3. **Establish root robustness physically, not only algorithmically.** Perform \(\eta\)-scaling, show \(|G|\) or self-energy behavior, and track root identity through the boundary.
4. **Test resolution dependence.** Repeat decisive points at another momentum-mixing resolution; without this, avoid claims about general extended-Hubbard behavior.
5. **Benchmark independently.** Compare several Mott-, boundary-, and charge-side points with exact diagonalization or another real-frequency-capable calculation.
6. **Promote the strong-coupling derivations.** Include checkable derivations and numerical spectral-moment tests in the main paper.
7. **Quantify all systematic errors.** Add uncertainty bands to \(E_{\mathrm{LS}}\) and \(s\), including root rule, broadening, grid, missing points, and fit form.
8. **Rebuild the figure hierarchy.** Center the paper on one figure combining zero-scale behavior, direct order diagnostics, sector information, and robustness.
9. **Complete literature positioning.** Replace every placeholder and state explicitly how the result differs from prior zero-surface, extended-Hubbard, and cluster-solver work.
10. **Narrow claims if the missing tests are infeasible.** Present the work as a methodological and strong-coupling study of a fixed-resolution MMHK construction, not a demonstrated phase-sensitive result for the extended Hubbard model.

# Questions You Must Answer

1. What is the exact \(U\)–\(V\) MMHK Hamiltonian actually diagonalized, and how does it differ from Eq. (1)?
2. What controlled limit or convergence parameter connects 4×4 MMHK to the thermodynamic extended Hubbard model?
3. Can a fixed \(Q=(0,0)\) calculation represent checkerboard charge order, and what happens when all relevant sectors are compared?
4. Does the scale drop coincide with a many-body level crossing, a change in symmetry, or a rapid but continuous change within one state?
5. How do you prove that the selected root before and after the drop is the same physical analytic branch?
6. Do the reported roots persist as \(\eta\to0\), and does \(|G|\) vanish there?
7. How large are the systematic uncertainties on every plotted scale once all reasonable extraction choices are included?
8. What do \(S_c(\pi,\pi)\), spin correlations, double occupancy, and the charge gap do at the same parameter points?
9. Does the anomaly survive a larger MMHK resolution or an independent solver?
10. Why should the close \(8/7\) result be interpreted as a prediction rather than a feature built into the assumed checkerboard defect picture?
11. What new conclusion becomes possible from the zero dispersion that could not be obtained from standard spin and charge observables?
12. Which prior papers have already computed finite-frequency Green-function zeros in Hubbard or extended-Hubbard settings, and what precise result here was unavailable in them?
13. Is the empirical piecewise rule predictive for withheld \(U,V\) points, or is it merely a compact interpolation?
14. What evidence supports the word “non-smooth” in the absence of resolution scaling?
15. If the crossover feature disappears or moves substantially at larger resolution, what scientifically durable result remains?
