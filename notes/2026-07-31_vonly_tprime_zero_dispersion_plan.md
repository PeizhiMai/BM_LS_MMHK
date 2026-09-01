# Plan: V-Only Corrections and a Second \(t'\) Test of the Bond-Resolved GZ Theorem

## Summary

Determine how finite nearest-neighbor repulsion modifies the \(V\)-only Green-function-zero (GZ) dispersion and test the bond-resolved strong-coupling theorem at a second, experimentally relevant negative hopping \(t'=-0.4t\).

Use existing data wherever possible and calculate only these three new sets:

\[
(U,V,t')=(40,0,-0.4),\quad(0,8,-0.25),\quad(0,8,-0.4).
\]

Together with existing data, these provide matched \(t'=0,-0.25,-0.4\) comparisons on both the Mott and charge sides.

## Implementation

### 1. Generate and validate new CADES data

- Create a dedicated CADES directory:
  `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_tprime_scan`.
- Copy and compile the current UV Green-function source using a `buildUV.sh`-style workflow.
- Generate the strict \(\Gamma-X-M-\Gamma\) path with 120 unique momenta; repeat \(\Gamma\) only during plotting.
- Submit 120 jobs per parameter set, totaling:
  - 360 jobs;
  - 720 expected raw files, counting \(G_h\) and \(G_p\).
- Use \(N_\uparrow=N_\downarrow=8\), \(Q=(0,0)\), `steps_max=1000`, 32 cores, 100 GB, and 8 h walltime.
- Use self-refilling queue caps of 40 jobs on `ccsd` and 60 on `cnms`.
- Check existing local and CADES filenames before submission to prevent duplicate jobs.
- Validate continued-fraction length and file structure before copying normalized files into the canonical local raw-data directory.

### 2. Generalize the bond-resolved analysis

Refactor the hard-coded \(t'=-0.25\) fitter into a reusable script accepting \(U,V,t'\), raw-data directory, and \(\eta\). Preserve the existing script as a compatibility wrapper.

At \(\eta=0.05\):

- Extract every gap-interior \(\operatorname{Re}G=0\) candidate.
- Track the continuous, low-spectral-weight branch using the established root audit.
- Fit only the 120 unique momentum points; restore the repeated endpoint for figures.
- Retain a free constant \(\delta\), so the harmonic coefficients are independent of the frequency-origin convention.

Compare:

\[
\omega_{\mathrm{GZ}}
=-s_{\mathrm{NN}}\varepsilon_1
+s_{\mathrm{NNN}}\varepsilon_2+\delta,
\]

against:

1. one scale multiplying the complete bare dispersion;
2. independent NN and NNN coefficients;
3. a fixed strong-coupling coefficient ratio with one amplitude;
4. the fully parameter-free strong-coupling prediction;
5. the existing mixed higher harmonic as a residual diagnostic only.

Record root completeness, \(R^2\), RMSE, maximum residual, fitted coefficients, and deviations from analytic predictions.

### 3. Test the two strong-coupling mechanisms

#### Mott side

Test the generic bond-resolved relation

\[
\omega_{\mathrm{GZ}}^{(U)}(\mathbf k)
=4C_1\varepsilon_1(\mathbf k)
+4C_2\varepsilon_2(\mathbf k)+\delta
+O(t_{\max }^2/U).
\]

For \(t'=-0.4t\), the present \(4\times4\) \(J_1-J_2\) spin calculation predicts

\[
4|C_1|=1.3982755,\qquad 4C_2=0.7947636.
\]

Use only \(U=40\) for the new calculation and compare it with existing \(t'=0\) and \(-0.25\) results.

#### Charge side

Derive the bond-resolved checkerboard-defect result rather than assuming a global rescaling. Test the leading candidate

\[
\omega_{\mathrm{GZ}}^{(V)}
=-\frac87\varepsilon_1+\varepsilon_2+\delta+\cdots,
\]

where NN hopping creates the \(7V\) charge defect responsible for \(8/7\), whereas NNN hopping propagates a defect within the same checkerboard sublattice.

Using existing \(t'=0\) data at \(V=2,4,5,8,12,16,20\), compare constrained corrections to \(8/7\):

\[
\frac87+a_1\frac{t}{V},\quad
\frac87+a_2\left(\frac{t}{V}\right)^2,\quad
\frac87+a_1\frac{t}{V}+a_2\left(\frac{t}{V}\right)^2,
\]

and an even-power model through \((t/V)^4\). Fit primarily with \(V\ge5\), treating \(V=2,4\) as holdouts. Select the simpler model when predictive errors differ by less than 5%.

Establish analytically whether checkerboard symmetry eliminates the linear correction. If it cannot be proved, describe the even-power behavior as numerical evidence rather than a theorem.

### 4. Figure and manuscript integration

Add a new full-width **Figure 6**, after the current Figure 5; renumber the present static-observable Figure 6 as Figure 7.

Use a \(2\times3\) layout:

- **(a)** \(U=40,V=0,t'=-0.4\) spectrum with white GZ curve.
- **(b)** Extracted \(t'=-0.4\) curve versus one-scale, bond-resolved, and spin-correlation predictions.
- **(c)** \(s_{\mathrm{NN}}\) and \(s_{\mathrm{NNN}}\) for \(t'=0,-0.25,-0.4\), compared with \(4|C_1|\) and \(4C_2\).
- **(d)** \(U=0,V=8,t'=-0.4\) spectrum with white GZ curve.
- **(e)** Charge-side curves at \(V=8\) for \(t'=0,-0.25,-0.4\), compared with the derived charge-defect relation.
- **(f)** Charge-side bond coefficients versus \(t'\), with guides from the analytic result and an inset showing the large-\(V\) correction to \(8/7\).

Retain current figure conventions: `imshow`, existing colormap and typography, external panel labels, no figure title, \(\varepsilon\) for bare dispersion, GZ terminology, and no additional visible \(\eta\) labels.

Put detailed derivations, model comparisons, residual harmonics, and root audits in the supplement.

## Outputs and Acceptance Tests

- General analysis outputs:
  - `results/bond_resolved_zero_theorem_eta0p05.csv`
  - `results/vonly_large_v_corrections_eta0p05.csv`
  - `results/bond_resolved_zero_theorem_summary_eta0p05.json`
- Main figure:
  - `figures/prl_main/prl_fig6_bond_resolved_mott_charge.pdf`
- Require 240 valid \(G_h/G_p\) files per new set and 121 plotted path rows.
- Accept the new \(U\)-side theorem test only if the bond-resolved model decisively improves on one-scale fitting and both coefficients agree with the spin predictions within 5%.
- Accept the proposed charge-side bond formula only if both nonzero-\(t'\) cases give consistent coefficient signs, small residuals, and coefficients close to the derived values. Otherwise report the deviation as a finite-\(V\) correction and recommend a later \(V=12\) check.
- Compile and visually inspect the main manuscript and supplement with no unresolved references or stale figure numbering.

## Assumptions

- Positive \(t'\) is not calculated because the half-filled particle-hole transformation relates it to negative \(t'\).
- All spectral results use \(\eta=0.05\).
- No additional interaction points are launched automatically if \(V=8\) proves insufficient; that outcome becomes an explicit follow-up recommendation.
