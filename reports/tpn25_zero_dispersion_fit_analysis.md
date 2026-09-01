# U-only \(t'=-0.25\) Green-function-zero dispersion

## Scope and reproducibility

This analysis uses the four complete, independently extracted
\(\eta=0.05\) root curves at \(U/t=8,12,20,40\).  Every curve contains all
121 points on the repeated-endpoint \(\Gamma-X-M-\Gamma\) path.  Run

```bash
~/.venvs/myenv/bin/python scripts/fit_tpn25_zero_dispersion.py
```

to regenerate the fit tables, exact spin correlations, curve table, summary,
and figure.

## Why one scale is insufficient when \(t'\ne0\)

Separate the noninteracting dispersion into its bond harmonics,

\[
\varepsilon_1(\mathbf k)=-2t(\cos k_x+\cos k_y),\qquad
\varepsilon_2(\mathbf k)=-4t'\cos k_x\cos k_y.
\]

For \(t'=-0.25t\), \(\varepsilon_2=+t\cos k_x\cos k_y\).  A single
inverted-band fit forces the same coefficient on \(\varepsilon_1\) and
\(\varepsilon_2\),

\[
E_{\rm GZ}=-s(\varepsilon_1+\varepsilon_2)+\delta.
\]

That constraint is strongly rejected: at \(U=40\), its RMSE is
\(1.4248t\).  The minimal successful fit is instead

\[
\boxed{
E_{\rm GZ}(\mathbf k)
=s_{\rm NN}\varepsilon_1(\mathbf k)
+s_{\rm NNN}\varepsilon_2(\mathbf k)+\delta}
,
\qquad s_{\rm NN}<0.
\]

The signs are carried by the coefficients themselves.  The two coefficients
therefore have opposite signs on the two band harmonics.
At \(U=40\),

\[
s_{\rm NN}=-1.3911,\qquad
s_{\rm NNN}=0.8346,\qquad
\delta=0.0001t,
\]

with RMSE \(0.0303t\) and \(R^2=0.99993\).  Thus the residual is already
smaller than the spectral broadening.  The RMSE is reduced by 97.87% relative
to the one-scale bare-band model.

An equivalent two-parameter shape representation is

\[
E_{\rm GZ}=s_{\rm NN}
\left[-2t(\cos k_x+\cos k_y)-4t'_{\rm GZ}\cos k_x\cos k_y\right]+\delta,
\]

where

\[
t'_{\rm GZ}=t'\frac{s_{\rm NNN}}{s_{\rm NN}}=0.1500t
\quad (U=40).
\]

The positive \(t'_{\rm GZ}\) is a zero-dispersion shape parameter, not a
renormalized one-electron hopping.  Its sign is opposite to the bare
\(t'=-0.25t\).

## Bond-resolved strong-coupling relation

The nearest-neighbor derivation generalizes bond by bond.  Let
\(C_{\mathbf r}=\langle\mathbf S_i\cdot\mathbf S_{i+\mathbf r}\rangle\)
and let \(\varepsilon_{\mathbf r}(\mathbf k)\) be the contribution of hopping
on that bond shell to the bare dispersion.  The particle/hole first-moment
cancellation gives, to leading order in the Mott expansion,

\[
\delta_{\mathbf k}=\frac1U\sum_{\mathbf r}
  (2C_{\mathbf r}-1/2)\varepsilon_{\mathbf r}(\mathbf k),
\qquad
\mathcal C_{\mathbf k}=\sum_{\mathbf r}\varepsilon_{\mathbf r}(\mathbf k)
  +U\delta_{\mathbf k}.
\]

Here \(\delta_{\mathbf k}\) is the particle/removal weight imbalance and
\(\mathcal C_{\mathbf k}\) is the average of the normalized particle and hole
first moments.  The second relation requires only the exact total first-moment
sum; it does not require particle--hole symmetry.  Inserting these two terms
and \(\Delta_{\mathbf k}=U+O(t)\) into
\(E_{\rm GZ}=\mathcal C_{\mathbf k}+\delta_{\mathbf k}\Delta_{\mathbf k}\)
gives

\[
\boxed{
E_{\rm GZ}(\mathbf k)
=4\sum_{\mathbf r}C_{\mathbf r}\,
  \varepsilon_{\mathbf r}(\mathbf k)
+O(t_{\max}^2/U).}
\]

For the \(t-t'\) model this becomes

\[
E_{\rm GZ}(\mathbf k)
=4C_1\varepsilon_1(\mathbf k)
+4C_2\varepsilon_2(\mathbf k)+\cdots .
\]

The spin state in the strict large-\(U\) limit is governed, at leading order,
by

\[
H_{\rm spin}=J_1\sum_{\langle ij\rangle}\mathbf S_i\cdot\mathbf S_j
+J_2\sum_{\langle\!\langle ij\rangle\!\rangle}
 \mathbf S_i\cdot\mathbf S_j,
\qquad
\frac{J_2}{J_1}=\left(\frac{t'}{t}\right)^2=\frac1{16}.
\]

Exact diagonalization at the present \(4\times4\) momentum-mixing
resolution gives

\[
C_1=-0.3507319025,\qquad C_2=+0.2088713786.
\]

There are therefore no free asymptotic shape parameters:

\[
 s_{\rm NN}^{\infty}=4C_1=-1.4029276100,
\qquad
s_{\rm NNN}^{\infty}=4C_2=0.8354855142,
\]

and

\[
(t'_{\rm GZ})^{\infty}
=t'\frac{C_2}{C_1}=0.1488825062t.
\]

The directly fitted \(U=40\) coefficients differ in magnitude from these
predictions by only \(0.8462\%\) and \(0.1073\%\), respectively.  A fit that fixes their
ratio to the spin prediction needs only one overall finite-\(U\) factor,
\(\gamma=0.9917\), and an offset \(0.0012t\); its RMSE is \(0.0306t\), nearly
identical to the unconstrained two-amplitude fit.

The physical sign structure is important.  Nearest neighbors are
antiferromagnetically correlated (\(C_1<0\)), so the nearest-neighbor harmonic
is inverted.  Diagonal neighbors lie on the same Néel sublattice and have
\(C_2>0\), so the diagonal harmonic is *not* inverted.  This is why scaling
the complete bare \(t-t'\) band by one number fails.

## Finite-\(U\) correction and charge correlations

If sub-broadening precision is desired, the leading useful extra harmonic is

\[
\chi_{21}(\mathbf k)=-4[\cos(2k_x)\cos k_y+
\cos k_x\cos(2k_y)].
\]

Adding \(\kappa_{21}\chi_{21}\) lowers the \(U=40\) RMSE from \(0.0303t\) to
\(0.0147t\), but \(\kappa_{21}=-0.0077t\) is below 1% of either leading bond
coefficient and decreases toward zero with increasing \(U\).  It is best
interpreted as a finite-\(U\), multi-hop correction rather than a third
leading scale.

There is no independent charge-correlation coefficient in the leading
half-filled U-only formula.  In the projected Mott manifold, \(n_i=1\), so
the density part of the exchange operator is a constant; after the
particle/hole first-moment cancellation, the dispersive coefficient is the
spin correlator on each hopping bond.  Double occupancy and connected density
correlations can enter the finite-\(U\) corrections.  Establishing their
individual coefficients would require matching full-observable
\(t'=-0.25\) calculations at \(U=20,40\); the present data do not require such
an extra leading parameter.

## Fit sequence

| \(U/t\) | \(s_{\rm NN}\) | \(s_{\rm NNN}\) | \(\delta/t\) | \(t'_{\rm GZ}/t\) | RMSE/\(t\) |
|---:|---:|---:|---:|---:|---:|
| 8  | -1.3486 | 0.8993 | 0.1040 | 0.1667 | 0.2584 |
| 12 | -1.3014 | 0.9379 | 0.0494 | 0.1802 | 0.1832 |
| 20 | -1.3561 | 0.8275 | -0.0020 | 0.1526 | 0.0919 |
| 40 | -1.3911 | 0.8346 | 0.0001 | 0.1500 | 0.0303 |

The repeated-endpoint and unique-120-point fits agree at \(U=40\) within
\(1.8\times10^{-4}\) for \(s_{\rm NN}\) and \(5.9\times10^{-4}\) for
\(s_{\rm NNN}\), so endpoint weighting is negligible.

## Outputs

- `results/tpn25_zero_dispersion_fit_metrics_eta0p05.csv`
- `results/tpn25_zero_dispersion_fit_curves_eta0p05.csv`
- `results/tpn25_j1j2_spin_correlations.csv`
- `results/tpn25_zero_dispersion_fit_summary_eta0p05.json`
- `figures/prl_main/prl_fig5_tprime_bond_resolved.pdf`
- `figures/pnas_supplement/tpn25_zero_dispersion_harmonic_fit_eta0p05.pdf`
