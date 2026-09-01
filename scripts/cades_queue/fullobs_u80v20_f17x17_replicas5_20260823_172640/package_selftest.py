#!/usr/bin/env /usr/bin/python3.11
import csv,hashlib,json,os,re,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent;REMOTE='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640'
SEEDS=[436887014,3276620531,3952085789,2430698334,1012333963];EFFECTIVE=[436887014,1129136884,1804602142,283214687,1012333963];ORDS=['4','5','6','7','8'];PATCHED_SOURCE='fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
err=[]
build_text=(B/'build_pins.py').read_text()
if "'-Wl,-rpath,$ORIGIN'" not in build_text or "'-Wl,-rpath='+str(INSTALL_LIB)" in build_text:err.append('nonisolated_build_rpath')
for token in ('subprocess.Popen','start_new_session=True','proof_reached','proof_basis','requested_after_proof','terminate_sent_at','wait_finished_at','os.killpg','SMOKE_TERM_GRACE','SMOKE_KILL_GRACE','partial_obs_removed','common_prefix_evidence','SMOKE_STABLE_POLLS=3','SMOKE_PROOF_TIMEOUT=720.0',"'OMP_NUM_THREADS':'1'","'MKL_NUM_THREADS':'1'"):
 if token not in build_text:err.append('bounded_smoke_recipe='+token)
for ledger in ('PACKAGE_SHA256SUMS','SOURCE_SHA256SUMS'):
 for line in (B/ledger).read_text().splitlines():
  if line.strip():
   h,rel=line.split(None,1);p=B/rel.strip()
   if not p.is_file() or p.is_symlink() or sha(p)!=h:err.append(ledger+':'+rel.strip())
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
if len(rows)!=5 or [int(r['seed']) for r in rows]!=SEEDS or [r['replica_ordinal'] for r in rows]!=ORDS:err.append('manifest_cardinality_seed_ordinal')
if [x%2147483647 or 1 for x in SEEDS]!=EFFECTIVE or len(set(EFFECTIVE))!=5 or 0 in EFFECTIVE:err.append('minstd_effective_state_gate')
if len({r['replica_result'] for r in rows})!=5 or len({r['script'] for r in rows})!=5:err.append('path_uniqueness')
for r in rows:
 p=B/'jobs'/Path(r['script']).name;t=p.read_text() if p.is_file() else ''
 for x in ('#SBATCH -A ccsd','#SBATCH -p burst','#SBATCH -N 1','#SBATCH -n 32','#SBATCH -c 1','#SBATCH -J F4U80R5','#SBATCH --mem=100G','#SBATCH -t 47:00:00'):
  if x not in t:err.append('resource='+p.name+':'+x)
 if re.search(r'(^|[^A-Za-z])python(?:[0-9.]*)?([^A-Za-z]|$)',t,re.I):err.append('compute_python='+p.name)
 for x in ('QBASIS_LANCZOS_SEED','MAXIT=\'50000\'','effective-seed proof missing/nonunique','BUILT_PIN_SHA256SUMS'):
  if x not in t:err.append('hardening='+p.name+':'+x)
 if re.search(r'\b(?:cp|mv|rm|unlink|install|truncate|tee)\b[^\n]*\$\{?CANONICAL\}?',t):err.append('canonical_write='+p.name)
 q=subprocess.run(['bash','-n',str(p)],text=True,capture_output=True)
 if q.returncode:err.append('bash_syntax='+p.name+':'+q.stderr)
for p,e in ((B/'source_provenance/qbasis_original/model.cc','ffdcbb4d15a64f8e703e81d642edb0036a6e87e1937191c3474e740c1940d3e7'),(B/'build_sources/qbasis/model.cc','c7a45062ce4d8b45e60768519276044f748de6d955095a2a1bd828b0d451c510'),(B/'source_provenance/Hubbard_sym_testobs_UV.original.cc','f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73'),(B/'build_sources/Hubbard_sym_testobs_UV.cc',PATCHED_SOURCE)):
 if not p.is_file() or sha(p)!=e:err.append('source='+str(p))
mt=(B/'build_sources/qbasis/model.cc').read_text();ht=(B/'build_sources/Hubbard_sym_testobs_UV.cc').read_text()
if 'QBASIS_LANCZOS_SEED is required' not in mt or 'parsed_seed > (4294967295ULL - digit) / 10ULL' not in mt or 'uint32_t seed   = 1;' in mt:err.append('seed_patch_semantics')
if ht.count('locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, 50000)')!=1 or 'locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, 10000)' in ht:err.append('maxit_patch_semantics')
if (B/'submission_header.tsv').read_text()!='submitted_at\taccount\tjob_id\treplica_index\treplica_ordinal\tsource_index\tsource_job_id\tU\tV\tkx\tky\tseed\tscript\treplica_result\n':err.append('submission_header_template')
if os.path.lexists(B/'submission.tsv'):err.append('mutable_submission_ledger_preexists')
# Old unsafe runtime pins must not be packaged before the controlled build.
pins=B/'pinned_solver';built=pins.is_dir()
if built:
 ledger=B/'BUILT_PIN_SHA256SUMS';receipt=B/'BUILD_RECEIPT.json'
 if not ledger.is_file() or not receipt.is_file():err.append('incomplete_build_artifacts')
 else:
  for line in ledger.read_text().splitlines():
   if line.strip():
    h,rel=line.split(None,1);p=B/rel.strip()
    if not p.is_file() or p.is_symlink() or sha(p)!=h:err.append('built_pin='+rel.strip())
  try:r=json.loads(receipt.read_text())
  except Exception as e:err.append('build_receipt_json='+str(e));r={}
  if r.get('patched_model_sha256')!='c7a45062ce4d8b45e60768519276044f748de6d955095a2a1bd828b0d451c510' or r.get('patched_hubbard_sha256')!=PATCHED_SOURCE or r.get('shared_tree_writes') is not False or r.get('make_install_invoked') is not False:err.append('build_receipt_identity')
  smoke=r.get('true_seed_smoke',{})
  if smoke.get('schema')!='actual_solver_bounded_two_seed_proof_v1' or smoke.get('passed') is not True or smoke.get('bounded_process_end') is not True or not smoke.get('different_common_prefix_trace_files') or [x.get('seed') for x in smoke.get('runs',[])]!=SEEDS[:2]:err.append('true_seed_build_smoke')
else:
 for p in (B/'BUILD_RECEIPT.json',B/'BUILT_PIN_SHA256SUMS'):
  if os.path.lexists(p):err.append('orphan_build_artifact='+str(p))
print(json.dumps({'schema':'fig4_u80v20_true_seed_maxit50000_local_package_selftest_v1','pass':not err,'batch':str(B),'remote_batch':REMOTE,'replicas':len(rows),'ordinals':ORDS,'seeds':SEEDS,'build_status':'BUILT' if built else 'NOT_BUILT','errors':err},sort_keys=True,indent=2));raise SystemExit(2 if err else 0)
