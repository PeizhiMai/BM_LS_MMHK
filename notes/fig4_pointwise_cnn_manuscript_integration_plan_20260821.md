# Fig. 4 pointwise-\(C_{\rm NN}\) manuscript/SI integration plan

**Status:** planning only. No manuscript, figure, result, or Overleaf artifact was
edited for this audit. This plan is against the local 2026-08-20 snapshot; the
live Overleaf project remains the source of record and must be downloaded and
compared again immediately before any text edit. The deterministic 25-twist
campaign is now a pilot/decision dataset, not the intended publication input:
the completed (U=20,V=2) panel already exceeds both frozen fourfold
sampling-domain guards, so the reviewed 25-to-861 policy will require the full
wedge once the exact 300/300 completeness gate can issue its formal certificate.

Local source hashes at audit time:

- `manuscript/main.tex` and `manuscript/main_current.tex`:
  `fc64c5e3246fe53af3d02dd95c4164bfcfb4cf2d31ca3b61b006f55ba014d1f9`
- `manuscript/supplement.tex` and `manuscript/supplement_pnas_style.tex`:
  `c4499b79c231f465dd6889410e20a6119841f0ff29072649bf6f20abcfb7a582`

## 0. Hard stop before publication integration

Do not promote the pointwise curves or insert numbers until the real analysis
bundle passes all of the following:

1. Exact reviewed 25-point manifest SHA-256
   `baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5`;
   reviewed expansion manifest/plan/certificate hashes; reviewed
   solver/source/qbasis pins; analyzer schema version 3; data product
   `fig4_pointwise_full861_direct_fullobs_C_NN_eq10`; observable `<C1_NN>`;
   reviewed full-861 finalizer SHA-256
   `997814a4f4cd69e45dbce7f6eb78c1102e863d13209e328998c1ad597bd2ed2c`;
   exact approved v2 expansion certificate, archived generator/verifier, and
   revalidation against the same 300 reused raw bytes.
2. Exactly 300 expected pilot outputs plus 10,032 complement outputs, with no
   unexpected `*_obs.dat`: all `status COMPLETE`, exact 12 cases x 861 unique
   wedge coordinates after combining the 25 reused and 836 new coordinates.
3. Observable-identity tolerance at most `1e-8` and every residual below its
   declared tolerance; exact filename/body/manifest agreement and frozen raw
   byte inventories for both campaigns.
4. All twelve new campaign estimates use the complete 861-point
   symmetry-reduced wedge quadrature. Together with the four pre-existing
   \(U=40\) full grids, every one of the 16 publication inputs is an F861
   estimate with total quadrature weight 1600. The quadrature-weighted twist
   population standard deviation is descriptive momentum variation, never a
   SEM or confidence interval.
5. The 25-point estimates and their U40 calibration remain an audit of why the
   expansion was triggered; they are not mixed into the publication curve.
6. Exact 16 unique \((U,V)\) full-861 rows, exact source and sampling labels,
   current GZ-table hash, and independently recomputed signed Eq. (10). Retain
   the \(U=40,V=8\) regression
   \(s_{\rm NN}^{\rm Eq.(10)}=-1.681755579831535\) with source `full_861`.

Data-quality gates must not be confused with a scientific-agreement gate. The
pointwise residuals are an outcome; do not discard valid data merely because an
old axis-anchor baseline happens to have a lower RMSE for one family.

## 1. Main-text patches after a fresh Overleaf download

All locations below refer to current local `manuscript/main.tex`; repeat the
final source identically in `main_current.tex` only after Overleaf synchronization.

### 1.1 Figure 4 caption (current line 216)

Remove “anchored only by each \(U\)-axis value.” Proposed replacement:

```tex
\caption{\textbf{GZ coefficient $s_{\mathrm{NN}}$ across the Mott--CDW
boundary.} (a) Signed coefficients for $U/t=20$, 40, and 80. Filled symbols are
the extracted GZ coefficients. Open symbols connected by colored lines are the
Mott-law prediction in \disp{eq:mott-law}, evaluated separately at every shown
Mott-side $(U,V)$ using the independently measured equal-time
$C_{\mathrm{NN}}(U,V)$; the connecting segments are guides only. No GZ
coefficient or finite-$V$ parameter is fitted. The black dash--dotted curve is
the leading rational term of \disp{eq:charge-law}. Horizontal guides mark the
interaction-axis limits and the vertical dotted line marks $V/U=1/4$.
(b) Independently bracketed first-order transition ratio. Bars show the sampled
brackets, the gray line guides the eye, and the dashed line marks $1/4$;
Supplemental Material gives the ground-state diagnostics.}
```

### 1.2 Eq. (10) setup and equation (current lines 232--239)

Make the interaction dependence of the independent input explicit:

```tex
Combining the exact first moment with the leading virtual-bond coherence fixes
both finite-ratio laws. On the Mott side, $D_{\mathrm M}=U-V$,
$\delta_{\mathbf k}=[2C_{\mathrm{NN}}(U,V)-1/2]\epsk/D_{\mathrm M}$, and
$\Delta_{\mathrm M}=U$. Thus $M_1=\epsk-V\delta_{\mathbf k}$ and
$\wzero=M_1+2\delta_{\mathbf k}\Delta_{\mathbf k}$ give
\begin{equation}
 s_{\mathrm{NN}}^{\mathrm M}(U,V)
 =1+\frac{2U-V}{U-V}
 \left[2C_{\mathrm{NN}}(U,V)-\frac12\right]
 +O\!\left(\frac{t}{D_{\mathrm M}}\right).
 \label{eq:mott-law}
\end{equation}
Here $C_{\mathrm{NN}}(U,V)$ is measured independently from equal-time
full-observable calculations at the same interaction point, rather than
inferred from $s_{\mathrm{NN}}$. We evaluate Eq.~\ref{eq:mott-law} point by
point; at $V=0$ its leading term is $4C_{\mathrm{NN}}(U,0)$. The colored
segments in Fig.~\ref{fig:plane}(a) only connect those predictions. No GZ
coefficient enters the prediction (Supplemental Material, Sec.~8 and
Tables~S4--S5).
```

Keep Eq. (11), the CDW moment-center cancellation, and its parameter-free
rational curve unchanged except for recomputed validation numbers.

### 1.3 Results/discussion references

- In the first sentence discussing Fig. 4(a) (current line 230), describe the
  open comparison nodes as direct Eq. (10) evaluations, not a fitted/anchored
  curve.
- Strengthen current Discussion line 287 only if the real residuals justify it:
  “the Mott-side GZ follows Eq. (10) evaluated with independently measured
  pointwise bond correlations, while the CDW side follows Eq. (11).” Do not add
  “quantitative agreement,” “improvement,” or a quoted RMSE before seeing the
  real table.
- If the new pointwise-input table is inserted as proposed below, the current
  transition-diagnostics citation at line 250 must become Table S6 (it is
  already stale as “Table S3” in the local source). Verify every hard-coded SI
  number after compilation rather than assuming it.
- Optionally add the finite-\((U,V)\) equal-time correspondence to the abstract
  only after the real metrics support it; no abstract change is required merely
  to remove the axis-anchor construction.

## 2. Supplemental Material patches

Locations refer to current `manuscript/supplement.tex`; mirror the final file to
`supplement_pnas_style.tex` only after the live Overleaf source is refreshed.

### 2.1 Finite-\((U,V)\) derivation (current lines 1136--1203)

- Define \(\Cnn\equiv C_{\rm NN}(U,V)\) for this subsection.
- Carry that explicit argument through the coherence, center, GZ, and boxed
  scale equations. The algebra and remainder do not change.

### 2.2 Delete the axis-anchor equation and replace it with the measurement rule

Delete current lines 1204--1215, including
`s_{\mathrm{NN}}^{\rm M,anchor}`, label `eq:s-mott-anchor-uv`, and the claim
that the construction absorbs the finite-\(U\) axis offset. Replace with:

```tex
At each displayed Mott-side point we measure the equal-time bond correlation
independently of the GZ extraction using the complete 861-point
symmetry-reduced wedge quadrature,
\begin{equation}
 \widehat C_{\mathrm{NN}}^{(861)}(U,V)
 =\frac{\sum_\ell w_\ell C_{\mathrm{NN},\ell}}
 {\sum_\ell w_\ell},\qquad \sum_\ell w_\ell=1600,
 \label{eq:s-cnn-full861-estimator}
\end{equation}
with exchange-symmetry and trapezoidal endpoint weights. The same 861-point
rule is used for all 16 displayed Mott-side inputs. The earlier deterministic
25-twist panel serves only as a provenance-gated pilot: its diagnostics crossed
the predeclared sampling-domain guard and therefore triggered completion of the
full wedges. Its range and population standard deviation are not statistical
errors. The prediction plotted in main-text Fig.~4(a) is the direct pointwise
evaluation
\begin{equation}
 \widehat s_{\mathrm{NN}}^{\mathrm M,Eq.(10)}(U,V)
 =1+\frac{2U-V}{U-V}
 \left[2\widehat C_{\mathrm{NN}}(U,V)-\frac12\right],
 \label{eq:s-mott-pointwise-uv}
\end{equation}
with no input from the GZ coefficient at the same point.
```

Insert the final 25-panel/full-861 comparison and the formal expansion
certificate only after both immutable analysis sidecars are frozen; keep this
as a numerical-integration audit rather than as the source of the plotted
values.

### 2.3 Direct comparison subsection (current lines 1290--1323)

Replace every “axis-anchored,” “U-axis anchor,” and “nonanchor” phrase. Proposed
opening:

```tex
The open comparison nodes in main-text Fig.~4(a) evaluate
Eq.~\ref{eq:s-mott-pointwise-uv} from the independently measured
$C_{\mathrm{NN}}(U,V)$ at the same sixteen Mott-side points; colored segments
only connect evaluated nodes. The CDW curve is the leading rational term of
Eq.~\ref{eq:s-cdw-scale-uv}. The boundary ratio is omitted because the two
atomic backgrounds cross there. No GZ coefficient is used as an input and no
finite-$V$ coefficient is fitted.
```

### 2.4 Tables

Add a new Table `tab:finite-uv-cnn-pointwise-inputs` immediately before the
existing validation table. Generate its rows from the frozen 16-row analyzer
CSV, with columns

```text
U/t | V/t | C_NN | sigma_C_NN^(w) | s_NN Eq.(10) | s_NN GZ | source
```

Use source code `F861` for every publication row. Define the displayed spread
as the quadrature-weighted population standard deviation over the full wedge
and explicitly state in the caption that it is a deterministic momentum-space
diagnostic, not a SEM/CI. If the P25/F861 comparison is tabulated, place it in a
separate integration-audit block rather than mixing P25 and F861 inputs in this
table. This becomes Table S4 under the current ordering.

Retain label `tab:finite-uv-analytic-validation` for the following six-row RMSE
table, but replace its caption by:

```tex
\caption{\textbf{Finite-$(U,V)$ strong-coupling validation.} RMSE is computed
from the signed $s_{\mathrm{NN}}$ values in main-text Fig.~4(a). The Mott
prediction is Eq.~\ref{eq:s-mott-pointwise-uv} evaluated with independently
measured $C_{\mathrm{NN}}(U,V)$; its reported finite-$V$ RMSE excludes the
$V=0$ points and the boundary ratios. The CDW prediction is the leading
rational term of Eq.~\ref{eq:s-cdw-scale-uv}.}
```

Replace all three Mott-family RMSE entries and the combined Mott sentence from
the real family-summary CSV. Recompute and re-verify the CDW entries even though
their formula/data are unchanged. Say “finite-\(V\), nonboundary points,” not
“nonanchor, nonboundary points.” With the proposed extra table, this validation
table becomes S5 and the later transition table becomes S6.

## 3. Figure/data pipeline promotion

1. Run `scripts/analyze_fig4_cnn_full861_campaign.py` only into a fresh direct
   child `tmp/fig4_cnn_full861_release_candidate_<version>`, then use
   `scripts/freeze_fig4_cnn_full861_release.py` to install the exact six-file
   product atomically as a read-only direct child
   `results/fig4_cnn_full861_release_<version>`. Never use `.codex_tmp`, a
   synthetic fixture, or the unfrozen candidate for publication. Preserve the
   analysis provenance sidecar inseparably with
   `fig4_cnn_pointwise_eq10.csv`; the schema-2 freeze manifest must pin all six
   files, their bundle digest, and the approved decision-certificate hash.
2. In `scripts/build_scale_and_transition_figure.py`, make the validated real
   bundle mandatory for the publication path. Remove the publication default
   that silently calls `mott_scale_law_from_axis_anchor`; if retained at all, it
   must be an explicitly named legacy diagnostic unavailable to release builds.
   Direct CLI execution is deliberately read-only (including `--help`) so an
   ambiguous invocation cannot overwrite active artifacts; use the explicit
   staging API or the atomic publication-promotion API instead.
3. Pointwise Fig. 4(a) encoding: filled markers = observed GZ; open same-family
   markers = Eq. (10) from fullobs \(C_{\rm NN}\); thin colored segments connect
   only the 5/5/6 evaluated nodes. Do not interpolate \(C_{\rm NN}\) onto a
   continuous ratio grid. Keep the CDW rational curve and asymptotic guides.
4. In `write_analytic_validation`, make `s_eq10_signed` the active Mott
   prediction. Replace stale summary text `s0=s_NN(U,0)=4C_NN`, rename the
   exclusion from “U-only anchors” to “V=0 points excluded only from the
   finite-V RMSE,” and either remove axis-anchor columns from the publication
   CSV or prefix them `diagnostic_` and declare them non-figure baselines.
5. Pass the frozen bundle through both callers:
   `scripts/build_prl_split_axis_figures.py` (vertical current Fig. 4) and
   `scripts/build_pnas_manuscript_figures.py` (horizontal preserved variant).
6. Rebuild and inspect:
   - `figures/prl_main/fig4_scale_and_transition_boundary.{pdf,png}`
   - `figures/pnas_main/pnas_fig3_scale_and_transition_boundary.{pdf,png}`
   - the byte-identical current manuscript copy
     `manuscript/figures/fig4_scale_and_transition_boundary.pdf`.
7. Keep `scripts/plot_fig4_cnn_diagnostic.py` and its three-panel output out of
   the manuscript; it is an audit visualization, not the publication figure.

Update `manuscript/figure_plan.md` Fig. 4 panel-A entry to:

```text
Panel A: estimated signed s_NN(U,V) for U=20,40,80. Filled symbols are the GZ
coefficients; open nodes connected within each U family are Eq. (10) evaluated
with independently measured pointwise C_NN(U,V) from complete 861-point wedge
quadrature at all 16 interaction points. The connecting segments are guides;
no finite-V GZ coefficient is fitted. The CDW branch remains the parameter-free
Eq. (11).
```

Add all six analyzer outputs and their provenance sidecar to its
machine-readable artifact list; retain the old empirical scale-fit files only
as explicitly historical audits.

## 4. Tests, validators, provenance, and bundle receipts

### Tests

- Replace `test_default_panel_retains_continuous_axis_anchor_curves` in
  `internal_tests/test_fig4_cnn_prediction_input.py` with a test that the
  publication path requires the validated real bundle and cannot fall back to
  220-point anchored curves.
- Retain gates for exact 16 rows, duplicates, full-861 source/sampling, signed
  Eq. (10), solver/source/25-manifest/expansion-manifest/certificate hashes,
  exact `1e-8` identity tolerance, U40,V8 regression, fixture opt-in, staging
  confinement, and no partial writes. The `1e-6` P25/F861 calibration gate is
  retained in the pilot/expansion audit but is no longer a mixed-source release
  condition.
- Add a regression that the release figure contains prediction-node counts
  5/5/6 and that its analytic CSV/family RMSE reproduce the analyzer outputs.

### Manuscript validators

Update `scripts/validate_manuscript.py` (and only update the legacy PNAS
validator if that variant is still released) to require:

- exact validated 16-row real bundle and its provenance/hash contract;
- `main.tex == main_current.tex` and
  `supplement.tex == supplement_pnas_style.tex` after synchronization;
- Eq. (10) contains `C_{\mathrm{NN}}(U,V)` and the caption states independent
  pointwise fullobs input;
- no `axis-anchored`, `anchored only`, `eq:s-mott-anchor-uv`, or
  `s_{\mathrm{NN}}^{\rm M,anchor}` in active manuscript/SI;
- all displayed table values and quoted RMSE values match generated CSV/JSON;
- active Fig. 4 hash equals both its generated and manuscript copies;
- zero unresolved references/errors and visual/page checks after compilation.

Remove the legacy empirical `lambda`/`beta` checks in
`scripts/validate_pnas_manuscript.py` from any validator used to certify this
finite-\((U,V)\) figure; those historical fit summaries are not sources for the
pointwise Eq. (10) curve.

### Figure provenance/manifests

- In `scripts/audit_manuscript_figure_provenance.py`, replace the scale-figure
  source list `pnas_scale_rule_summary_eta0p05.json` with the frozen pointwise
  CSV + analyzer provenance, current GZ table, generated analytic validation,
  and boundary table. Add the current vertical `fig4_scale...pdf` mapping or
  generalize the auditor to the active source pair.
- Regenerate a date-current manuscript-figure provenance JSON; do not present
  the stale `20260724` receipt as certification of the new figure.
- Extend `results/pnas_main_figure_manifest.json` and/or create a current-main
  manifest with generator hash, all source hashes, analyzer schema/data-product,
  figure hashes, and the 12+4 inventory. Add Fig. 4 to the compact/current figure
  manifest rather than relying on a manual copy.
- Replace `results/finite_uv_strong_coupling_validation_eta0p05.{csv,json}` with
  pointwise-derived versions only after all gates pass. Archive, rather than
  silently overwrite, the axis-anchor versions.
- Write new dated manuscript-validation, PDF-hash, combined-packet, and upload-
  bundle receipts.

### Source-of-record and bundle sequence

1. After real results are frozen, download/inspect current Overleaf `main.tex`,
   `supplement.tex`, bibliography, README, and affected Fig. 4 PDF; archive the
   pre-edit snapshot.
2. Patch the fresh local copies, regenerate Fig. 4/tables/receipts, compile main
   and supplement locally with zero errors, and visually inspect changed pages.
3. Sync the complete affected files to Overleaf (never edit piecemeal in the
   web editor), compile `main.tex` and `supplement.tex` there with zero errors,
   verify the rendered Fig. 4 and SI tables, and restore `main.tex` as Main.
4. Download the post-sync source and verify byte equality. Refresh
   `main_current.tex`, `supplement_pnas_style.tex`, local PDFs, combined PDF,
   `output/pdf` copies, and a dated complete Overleaf upload ZIP. Include any
   generated table `.tex` fragment if `\input` is used.
5. Update `manuscript/README.md`, `manuscript/figure_plan.md`, and append a new
   `PROJECT_LOG.md` entry. Do not rewrite the historical 2026-08-20 log entry or
   archived legacy manuscript variants.

### Axis-anchor strings that should intentionally remain internal

The publication text, active Fig. 4 builder path, active validation CSV/JSON,
and figure caption must lose the anchor construction. The following occurrences
have a different purpose and should not be mechanically deleted:

- `scripts/analyze_fig4_cnn_campaign.py` may retain the axis-anchor prediction
  and residual as a clearly named diagnostic baseline used to compare methods.
- `scripts/plot_fig4_cnn_diagnostic.py` may retain that baseline in the
  staging-only residual panel.
- `scripts/fig4_cnn_prediction_input.py` may retain wording that says an
  axis-anchor fallback is forbidden.
- `internal_tests/test_fig4_cnn_prediction_input.py` may retain the deliberately
  invalid source string `axis-anchor inferred from GZ slope` to prove rejection.
- The 2026-08-20 `PROJECT_LOG.md` entry and archived manuscript snapshots are
  historical records; append a superseding entry instead of rewriting them.

## 5. Items that must wait for the real campaign

- Twelve new full-861 \(C_{\rm NN}(U,V)\) weighted means, their weighted
  population standard deviations, and the corresponding Eq. (10) predictions.
- The \(U=20\), \(U=40\) (because \(V=6\) is new), and \(U=80\) family RMSE,
  MAE, maximum residual, combined finite-\(V\) RMSE, and any comparison with the
  axis-anchor diagnostic.
- Claims about whether pointwise \(C_{\rm NN}\) resolves the off-data \(U=20\)
  line, improves every family, or gives monotonic convergence with \(U\).
- Final table rows, significant figures, panel limits/legend placement, and
  whether connecting segments remain visually appropriate.
- Final analyzer/figure/table/PDF/ZIP hashes, page counts, and compiled SI table
  numbers.

Until those quantities exist, use placeholders only in this planning document,
never in manuscript or publication artifacts.
