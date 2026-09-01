#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'manuscript/main_pnas_style.tex'
SIG=ROOT/'manuscript/significance_statement_pnas_style.tex'
SUPP=ROOT/'manuscript/supplement_pnas_style.tex'
OUT=ROOT/'results/pnas_manuscript_validation_20260724.json'
FULLOBS_TAG='20260723_091307'

def visible_words(tex:str, env:str|None=None)->int:
    if env:
        tex=re.search(rf'\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}',tex,re.S).group(1)
    tex=re.sub(r'\\(?:mathbf|mathrm|text|emph|cdot|simeq|times|to|ge|gg|ll|quad)', ' ', tex)
    tex=re.sub(r'\\[A-Za-z]+', ' ', tex)
    tex=re.sub(r'[$^_{}\\&!]', ' ', tex)
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*",tex))

def close(a,b,tol=5e-4): return abs(float(a)-float(b))<=tol

main=MAIN.read_text(); sig=SIG.read_text(); supp=SUPP.read_text()
sig_body=sig.split(r'\section*{Significance Statement}',1)[1].split(r'\end{document}',1)[0]
checks={}
checks['abstract_words']=visible_words(main,'abstract')
checks['abstract_150_to_170']=150<=checks['abstract_words']<=170
checks['significance_words']=visible_words(sig_body)
checks['significance_at_most_120']=checks['significance_words']<=120
checks['main_eta_count']=main.count(r'\eta=0.05')
checks['single_main_eta_mention']=checks['main_eta_count']==1
checks['supplement_numeric_eta_count']=supp.count(r'\eta=0.05')
checks['no_supplement_numeric_eta_repeat']=checks['supplement_numeric_eta_count']==0
prohibited=['[REF:','placeholder','project source','MMHK cluster','momentum-mixing cluster','necessary entry ticket','should not be sold']
checks['prohibited_hits']={x:(main+supp+sig).lower().count(x.lower()) for x in prohibited}
checks['no_prohibited_text']=all(v==0 for v in checks['prohibited_hits'].values())
figs=[ROOT/'figures/pnas_main'/f'pnas_fig{i}_{name}.pdf' for i,name in [
 (1,'multidensity_benchmark'),(2,'interaction_axis_comparison'),
 (3,'scale_and_transition_boundary'),(4,'static_branch_crossing')]]
checks['main_figures_exist']=all(p.exists() and p.stat().st_size>0 for p in figs)
supp_figs=[
 ROOT/'figures/pnas_supplement/supp_figS2_uonly_spectral_sequence.pdf',
 ROOT/'figures/pnas_supplement/supp_figS3_uonly_lower_band_snapshots.pdf',
 ROOT/'figures/pnas_supplement/supp_figS4_vonly_spectral_sequence.pdf',
 ROOT/'figures/pnas_supplement/supp_figS5_vonly_lower_band_snapshots.pdf',
 ROOT/'figures/pnas_supplement/supp_figS6_finite_uv_spectral_reorganization.pdf',
 ROOT/'figures/luttinger_eta0p05_other_parameter_sets/eta0p05_V_effect_luttinger_dispersion_comparison_evenV.pdf',
 ROOT/'figures/fullobs/fullobs_static_scan_U40.pdf',
 ROOT/'figures/fullobs/fullobs_nk_maps_U40.pdf',
 ROOT/'figures/fullobs/fullobs_strong_coupling_validation_U40.pdf',
 ROOT/'figures/pnas_supplement/supp_figS13_tpn25_reproduced.pdf',
]
checks['all_supplement_figures_exist']=all(p.exists() and p.stat().st_size>0 for p in supp_figs)
checks['optional_referee_backup_preserved']=all(
 p.exists() and p.stat().st_size>0 for p in [
  ROOT/'manuscript/referee_backup_zero_extraction_robustness.tex',
  ROOT/'manuscript/referee_backup_zero_extraction_robustness.pdf',
  ROOT/'figures/pnas_supplement/pnas_supp_figS8_zero_branch_candidate_audit_eta0p05.pdf',
  ROOT/'figures/pnas_main/pnas_supp_extraction_robustness.pdf',
 ]
)
pdfs=[ROOT/'manuscript'/x for x in ['main_pnas_style.pdf','significance_statement_pnas_style.pdf','supplement_pnas_style.pdf','MMHK_PNAS_current_with_supplement.pdf','MMHK_PNAS_current_full_submission_packet.pdf']]
checks['all_pdfs_exist']=all(p.exists() and p.stat().st_size>0 for p in pdfs)
logs=[ROOT/'manuscript/main_pnas_style.log',ROOT/'manuscript/supplement_pnas_style.log',ROOT/'manuscript/significance_statement_pnas_style.log']
warning_re=re.compile(r'(Citation .* undefined|Reference .* undefined|There were undefined references|File .* not found)',re.I)
checks['unresolved_log_hits']=[m.group(0) for p in logs for m in warning_re.finditer(p.read_text(errors='ignore'))]
checks['no_unresolved_citations_or_figures']=not checks['unresolved_log_hits']

summary=json.loads((ROOT/'results/pnas_scale_rule_summary_eta0p05.json').read_text())
checks['lambda_matches_summary']=close(summary['mott_parameters']['lambda'],0.8445,5e-5)
checks['beta_matches_summary']=close(summary['charge_parameters']['beta'],0.1847,5e-5)
checks['lambda_ci_matches_summary']=all(close(a,b,5e-5) for a,b in zip(summary['mott_95pct_stratified_bootstrap_ci']['lambda'],[0.8291,0.8573]))
checks['beta_ci_matches_summary']=all(close(a,b,5e-5) for a,b in zip(summary['charge_95pct_stratified_bootstrap_ci']['beta'],[0.1805,0.1912]))
checks['coverage_matches_summary']=close(summary['minimum_accepted_fraction'],111/121,1e-10)
checks['complete_only_shift_matches_summary']=close(abs(summary['parameter_shift_when_incomplete_rows_removed']['lambda']),0.0083,5e-5) and close(abs(summary['parameter_shift_when_incomplete_rows_removed']['beta']),0.0028,5e-5)

points=pd.read_csv(ROOT/'results/pnas_scale_rule_points_eta0p05.csv')
def s(U,V): return float(points[(points.U==U)&(points.V==V)].s.iloc[0])
expected={(20,4):1.621,(20,4.5):1.661,(20,5):1.703,(20,5.5):1.285,
          (40,8):1.682,(40,9):1.728,(40,10):1.777,(40,12):1.271,
          (80,20):1.797,(80,21):1.312,(40,0):1.39286,(80,0):1.40084}
checks['quoted_interaction_scales_match_csv']=all(close(s(*k),v,5e-4) for k,v in expected.items())

vsum=json.loads((ROOT/'results/large_uv_luttinger_scale_rule_summary.json').read_text())
vals={int(x['V']):x['s_obs'] for x in vsum['u0_scales_if_available']}
checks['quoted_v_axis_scales_match_json']=all(close(vals[V],v,5e-5) for V,v in {4:1.14105,8:1.14240,12:1.14265,16:1.14274,20:1.14278}.items())

axis_fits=pd.read_csv(ROOT/'results/pnas_fig2_axis_fit_metrics.csv').set_index('axis')
checks['figure2_axis_fit_values_match_csv']=(
 close(axis_fits.loc['U-only','alpha'],1.39286,5e-6)
 and close(axis_fits.loc['V-only','alpha'],1.14240,5e-6)
 and not bool(axis_fits.loc['U-only','offset_in_model'])
 and not bool(axis_fits.loc['V-only','offset_in_model'])
 and close(axis_fits.loc['U-only','diagnostic_unconstrained_offset'],2.06e-4,5e-7)
 and close(axis_fits.loc['V-only','diagnostic_unconstrained_offset'],-2.11e-5,5e-8)
 and r'\alpha_U=1.39286' in main
 and r'\alpha_V=1.14240' in main
)

multidensity=pd.read_csv(ROOT/'results/mmhk_observables_all_cases.csv')
checks['figure1_multidensity_grid_complete']=(
 len(multidensity)==18
 and set(multidensity['n_target'].astype(float))=={0.8,0.875,1.0}
 and set(multidensity['U'].astype(float))=={2.0,4.0,6.0,8.0,10.0,12.0}
 and bool(multidensity.groupby('n_target')['U'].nunique().eq(6).all())
)
figs2_filter=json.loads((ROOT/'results/figS2_source_filter_audit.json').read_text())
checks['figure1_strict_source_filter_pass']=(
 figs2_filter['candidate_external_rows']==27
 and figs2_filter['candidate_cp_afqmc_tabc_rows']==16
 and figs2_filter['candidate_dmet_4x4_rows']==11
 and figs2_filter['selected_external_rows']==12
 and figs2_filter['selected_energy_rows']==9
 and figs2_filter['selected_cp_afqmc_energy_rows']==3
 and figs2_filter['selected_cp_afqmc_systems']==['20x8']
 and figs2_filter['selected_dmet_energy_rows']==6
 and figs2_filter['selected_dmet_double_occupancy_rows']==3
 and figs2_filter['selected_corresponding_do_rows']==2
 and figs2_filter['selected_same_parameter_fallback_do_rows']==1
 and figs2_filter['selected_energy_duplicate_parameter_sets']==0
 and figs2_filter['selected_do_duplicate_parameter_sets']==0
 and figs2_filter['thermodynamic_extrapolation_rows']==0
 and figs2_filter['bcs_state_rows']==0
 and figs2_filter['non_tabc_cp_afqmc_rows']==0
 and figs2_filter['non_4x4_dmet_rows']==0
 and figs2_filter['half_filling_selected_energy_rows']==5
 and figs2_filter['half_filling_selected_do_rows']==5
 and figs2_filter['half_filling_corresponding_do_rows']==5
 and figs2_filter['half_filling_selected_energy_methods_by_U']=={
     '2':'DMET','4':'DMET','6':'AFQMC','8':'AFQMC','12':'AFQMC'
 }
 and figs2_filter['visual_encoding']=={
     'density':'color',
     'MMHK':'colored line with filled circular markers',
     'AFQMC_or_CP_AFQMC':'open circles',
     'DMET':'open triangles',
     'legend':'single column at upper left of panel a',
 }
)
boundary_u4=pd.read_csv(
 ROOT/'results/transition_brackets_Uge4_for_combined_figure.csv'
)
checks['figure3_transition_boundary_subset_pass']=(
 len(boundary_u4)==10
 and set(boundary_u4['U'].astype(int))==
     {4,8,12,16,20,24,28,32,36,40}
 and bool((boundary_u4['U']>=4).all())
 and bool((boundary_u4['V_c_over_U_halfwidth']>0).all())
 and close(
     boundary_u4.loc[boundary_u4['U'].eq(4),'V_c_over_U'].iloc[0],
     0.257375,
     5e-7,
 )
 and close(
     boundary_u4.loc[boundary_u4['U'].eq(40),'V_c_over_U'].iloc[0],
     0.250375,
     5e-7,
 )
 and 'pnas_fig3_scale_and_transition_boundary.pdf' in main
)
checks['figure2_S6_relocation_pass']=(
 'pnas_fig2_interaction_axis_comparison.pdf' in main
 and 'pnas_fig2_finite_uv_spectral_reorganization.pdf' not in main
 and 'supp_figS6_finite_uv_spectral_reorganization.pdf' in supp
 and 'pnas_supp_figS4_interaction_axis_comparison.pdf' not in supp
 and all(
     f'rhoG_LS_U40_V{V}_tp0_eta0p05_spectra_and_roots.npz'
     in (ROOT/'scripts/build_pnas_manuscript_figures.py').read_text()
     for V in [4,8,12,16,20]
 )
 and all(f'$V={V}$' in supp for V in [0,4,8,12,16,20])
)
checks['figure1_benchmark_promotion_pass']=(
 'fig1_multidensity_benchmark.pdf' in main
 and 'pnas_fig1_asymptotic_mechanisms.pdf' not in main
 and 'supp_figS1_asymptotic_mechanisms.pdf' not in supp
 and 'pnas_supp_figS1_half_filling_benchmark.pdf' not in supp
 and 'pnas_supp_figS2_multidensity_benchmark.pdf' not in supp
)
figure_script=(ROOT/'scripts/build_pnas_manuscript_figures.py').read_text()
checks['figure4_six_panel_energy_and_nk_pass']=(
 'E0_per_site_mean' in figure_script
 and 'FULLOBS_ROWS' in figure_script
 and 'noninteracting_nk_map' in figure_script
 and 'same_branch_secant' not in figure_script
 and '(axd, map_arrays[0.0], r"$V/U=0$", "(d)")' in figure_script
 and '(axe, map_arrays[20.0], r"$V/U=0.5$", "(e)")' in figure_script
 and 'panel_label(axf, "(f)")' in figure_script
 and 'free_map = noninteracting_nk_map(points=1001)' in figure_script
 and 'interacting_norm = TwoSlopeNorm(' in figure_script
 and 'free_norm = TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=2.0)' in figure_script
 and 'cax_interacting' in figure_script
 and 'cax_free' in figure_script
 and 'The continuous ground-state energy changes slope' in main
 and r'they share an interaction-resolved color scale centered at $n(\mathbf{k})=1$' in main
 and r'displayed on its own $0\le n_0(\mathbf{k})\le2$ scale' in main
 and r'Fig.~\ref{fig:static-crossing}D--F' in main
 and r'The measured $n_\Gamma$ follows' not in main
)
panel_style=(ROOT/'scripts/manuscript_figure_style.py').read_text()
panel_label_generators=[
 ROOT/'scripts/build_pnas_manuscript_figures.py',
 ROOT/'scripts/build_scale_and_transition_figure.py',
 ROOT/'scripts/build_pnas_supplement_figures.py',
 ROOT/'scripts/build_pnas_spectral_sequence_supplement.py',
 ROOT/'scripts/plot_combined_density_benchmark.py',
 ROOT/'scripts/analyze_fullobs_u40_scan.py',
]
checks['outside_panel_label_rule_pass']=(
 'PANEL_LABEL_X = -0.105' in panel_style
 and 'PANEL_LABEL_Y = 0.985' in panel_style
 and 'ha="right"' in panel_style
 and 'va="top"' in panel_style
 and 'clip_on=False' in panel_style
 and all('outside_panel_label' in path.read_text() for path in panel_label_generators)
 and 'ax.text(0.02, 0.96, f"({label})"' not in
     (ROOT/'scripts/analyze_fullobs_u40_scan.py').read_text()
)

zero_label_generators=[
 ROOT/'scripts/build_pnas_manuscript_figures.py',
 ROOT/'scripts/build_scale_and_transition_figure.py',
 ROOT/'scripts/build_pnas_supplement_figures.py',
]
zero_label_text='\n'.join(path.read_text() for path in zero_label_generators)
checks['zero_dispersion_symbol_consistency_pass']=(
 r'ZERO_DISPERSION_AXIS_LABEL = r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$"' in panel_style
 and r'ZERO_DISPERSION_SCALE_AXIS_LABEL = r"GZ coefficient $s_{\mathrm{NN}}$"' in panel_style
 and all(token not in zero_label_text for token in [
     r'E_{\rm LS}',
     r'E_{\mathrm{LS}}',
     r'\varepsilon_{\rm LS',
     r'\omega_{\rm LS',
     r'\omega_0',
     r'\omega_{\mathrm{z}}',
     'LS scale',
 ])
 and r'\newcommand{\wzero}{\omega_{\mathrm{GZ}}}' in main
 and r'\newcommand{\wzero}{\omega_{\mathrm{GZ}}}' in supp
 and r'\omega_0' not in main
 and r'\omega_0' not in supp
 and r'\omega_{\mathrm{z}}' not in main
 and r'\omega_{\mathrm{z}}' not in supp
)

spectral_windows=json.loads(
 (ROOT/'results/pnas_supp_spectral_sequence_windows.json').read_text()
)
checks['supplement_S2_to_S5_spectral_sequences_pass']=(
 spectral_windows['v_greater_than_8_choice']==12
 and close(spectral_windows['lower_band_window_spans']['S3'],10.0,1e-12)
 and close(spectral_windows['lower_band_window_spans']['S5'],3.0,1e-12)
 and all(
     len(spectral_windows['figures'][figure]['panels'])==4
     for figure in ['S2','S3','S4','S5']
 )
 and [
     int(panel['value'])
     for panel in spectral_windows['figures']['S2']['panels']
 ]==[8,12,20,40]
 and [
     int(panel['value'])
     for panel in spectral_windows['figures']['S4']['panels']
 ]==[2,5,8,12]
 and all(
     close(panel['y_span'],10.0,1e-10)
     for panel in spectral_windows['figures']['S3']['panels']
 )
 and all(
     close(panel['y_span'],3.0,1e-10)
     for panel in spectral_windows['figures']['S5']['panels']
 )
 and 'luttinger_tp0_eta0p05_imshow.pdf' not in supp
 and 'supp_figS2_uonly_spectral_sequence.pdf' in supp
 and 'supp_figS3_uonly_lower_band_snapshots.pdf' in supp
 and 'supp_figS4_vonly_spectral_sequence.pdf' in supp
 and 'supp_figS5_vonly_lower_band_snapshots.pdf' in supp
)

nk=pd.read_csv(ROOT/'results/nk_metrics.csv')
def var(U,V): return float(nk[(nk.U==U)&(nk.V==V)&(nk.tp==0)].variance_nk_path.iloc[0])
checks['quoted_nk_variances_match_csv']=all(close(var(*k),v,5e-5) for k,v in {(20,0):0.0848,(20,4):0.1220,(20,6):0.0522,(20,8):0.0203}.items())

cmp=pd.read_csv(ROOT/'results/pnas_scale_model_comparison_eta0p05.csv')
def lofo(branch,model): return float(cmp[(cmp.branch==branch)&(cmp.model==model)].lofo_rmse.iloc[0])
checks['quoted_lofo_errors_match_csv']=close(lofo('Mott/spin','rational'),0.0121,5e-5) and close(lofo('charge','quadratic'),0.0074,5e-5)

obs=pd.read_csv(ROOT/f'results/fullobs_U40_observable_summary_by_V_{FULLOBS_TAG}.csv').set_index('V')
checks['fullobs_boundary_values_match_csv']=(
 close(obs.loc[10.01,'D_site_mean'],0.005158,5e-7)
 and close(obs.loc[10.02,'D_site_mean'],0.495631,5e-7)
 and close(obs.loc[10.01,'mCDW2_pipi_mean'],0.001298,5e-7)
 and close(obs.loc[10.02,'mCDW2_pipi_mean'],0.983662,5e-7)
 and close(obs.loc[10.01,'Szz_pipi_mean'],1.455499,5e-7)
 and close(obs.loc[10.02,'Szz_pipi_mean'],0.004340,5e-7)
 and close(obs.loc[10.01,'n_k_gamma'],1.304752,5e-7)
 and close(obs.loc[10.02,'n_k_gamma'],1.258645,5e-7)
 and close(2*obs.loc[10.01,'nn_NN_mean'],1.994836,5e-7)
 and close(2*obs.loc[10.02,'nn_NN_mean'],0.030504,5e-7)
)
quality=json.loads((ROOT/f'results/fullobs_U40_data_quality_{FULLOBS_TAG}.json').read_text())
checks['fullobs_crossing_matches_json']=close(
 quality['branch_switch_estimate']['V_c_over_U'],0.2503257878209495,5e-10)
checks['fullobs_data_integrity_pass']=(
 not quality['sha256_mismatches']
 and quality['duplicate_parameter_keys']==0
 and quality['max_abs_identity_residuals']['energy_per_site']<3e-10
 and quality['parsed_rows']==12054
 and all(row['wedge_rows']==861 for row in quality['completeness_by_V'])
)
checks['direct_transition_bracket_is_current']=(
 '10.01<V_c<10.02' in main
 and '$V=10.01$ & $V=10.02$' in supp
)
checks['obsolete_missing_charge_claim_absent']='Direct charge structure factors' not in main
checks['legacy_handy_figures_not_referenced']=all(
 name not in main+supp for name in [
  'half_filling_comparison.pdf','hftp0.pdf','hftpn25.pdf','LStp0','LStpn25'
 ])
provenance_path=ROOT/'results/manuscript_figure_provenance_20260724.json'
provenance=json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
checks['figure_provenance_audit_pass']=bool(provenance.get('all_figures_script_generated'))

# Search rendered text for paths/placeholders.
pdf_text=''
for p in [pdfs[0],pdfs[2]]:
    try: pdf_text += subprocess.check_output(['pdftotext',str(p),'-'],text=True)
    except Exception: pass
checks['visible_internal_path_hits']=[x for x in ['../','/Users/','data/Gcalpath','results/','scripts/'] if x in pdf_text]
checks['no_visible_internal_paths']=not checks['visible_internal_path_hits']
checks['all_boolean_checks_pass']=all(v for k,v in checks.items() if isinstance(v,bool))
OUT.write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
if not checks['all_boolean_checks_pass']:
    raise SystemExit(1)
