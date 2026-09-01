#!/usr/bin/env /usr/bin/python3.11
import csv,datetime as dt,hashlib,json,os,re,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent;REMOTE=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640');ROOT=REMOTE.parent
SOURCE=ROOT/'fullobs_25twist_u80v20_fig4_cnn_20260822_213314';PRIOR=ROOT/'fullobs_u80v20_f17x17_replicas3_20260823_002730';JOB='F4U80R5';CANON=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat')
SEEDS=[436887014,3276620531,3952085789,2430698334,1012333963];PATCHED_MODEL='c7a45062ce4d8b45e60768519276044f748de6d955095a2a1bd828b0d451c510';PATCHED_SOURCE='fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b'
SOURCE_HASHES={'manifest.tsv':'e5e95fa9b65d312b79f3a6349252a37c9ea60c1ce95df50a3be142b334c97117','twist_panel.tsv':'688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b','analyze.py':'aec1ad91ce09913a89f8acf21b28d9e58912f430323133088d3d03e4d977c15c'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(a,env=None):return subprocess.run(a,text=True,capture_output=True,env=env)
err=[];scan={'files':0,'bytes':0,'errors':0,'hits':{}}
if "'-Wl,-rpath,$ORIGIN'" not in (B/'build_pins.py').read_text():err.append('nonisolated_build_rpath')
if B!=REMOTE:err.append('wrong_remote_batch='+str(B))
for ledger in ('PACKAGE_SHA256SUMS','SOURCE_SHA256SUMS','BUILT_PIN_SHA256SUMS'):
 p=B/ledger
 if not p.is_file() or p.is_symlink():err.append('missing_ledger='+ledger);continue
 for line in p.read_text().splitlines():
  if line.strip():
   h,rel=line.split(None,1);x=B/rel.strip()
   if not x.is_file() or x.is_symlink() or sha(x)!=h:err.append(ledger+':'+rel.strip())
try:receipt=json.loads((B/'BUILD_RECEIPT.json').read_text())
except Exception as e:receipt={};err.append('build_receipt='+str(e))
if receipt.get('schema')!='fig4_u80v20_true_seed_maxit50000_isolated_build_v2' or receipt.get('patched_model_sha256')!=PATCHED_MODEL or receipt.get('patched_hubbard_sha256')!=PATCHED_SOURCE or receipt.get('shared_tree_writes') is not False or receipt.get('make_install_invoked') is not False:err.append('build_receipt_identity')
smoke=receipt.get('true_seed_smoke',{});smoke_runs=smoke.get('runs',[])
if smoke.get('schema')!='actual_solver_bounded_two_seed_proof_v1' or smoke.get('passed') is not True or smoke.get('bounded_process_end') is not True or [x.get('seed') for x in smoke_runs]!=SEEDS[:2]:err.append('true_seed_build_smoke')
else:
 trace_sets=[]
 expected_solver=str(B/'build/candidate_pins/Hubbard_sym_testobs_UV.x')
 for sr in smoke_runs:
  seed=sr.get('seed');work=B/'build'/('smoke_seed_'+str(seed));expected_command=[expected_solver,'1','1','17','17','0','0','80','20','0']
  expected_env={'QBASIS_LANCZOS_SEED':str(seed),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OMP_PROC_BIND':'close','OMP_PLACES':'cores'}
  if sr.get('schema')!='actual_solver_bounded_seed_trace_proof_v1' or sr.get('command')!=expected_command or sr.get('environment')!=expected_env or sr.get('cwd')!=str(work) or sr.get('proof_reached') is not True or sr.get('stdout_seed_marker_count')!=1 or not isinstance(sr.get('pid'),int) or sr.get('pid',0)<=0 or sr.get('process_group_id')!=sr.get('pid'):err.append('smoke_process_identity='+str(seed))
  latency=sr.get('proof_latency_seconds');timeout=sr.get('proof_timeout_seconds')
  if not isinstance(latency,(int,float)) or not isinstance(timeout,(int,float)) or latency<0 or timeout!=720.0 or latency>timeout or not (sr.get('started_at') and sr.get('proof_at') and sr.get('finished_at')) or not (sr['started_at']<=sr['proof_at']<=sr['finished_at']):err.append('smoke_timing='+str(seed))
  basis=sr.get('proof_basis');observed=sr.get('stable_trace_polls_observed')
  if sr.get('poll_seconds')!=0.25 or sr.get('stable_trace_polls_required')!=3 or not isinstance(observed,int) or observed<1 or basis not in ('stable_trace_snapshots_while_running','clean_natural_exit_with_final_trace') or (basis=='stable_trace_snapshots_while_running' and observed<3) or not sr.get('proof_trace_signature'):err.append('smoke_trace_stability='+str(seed))
  term=sr.get('termination',{});disp=term.get('disposition');rc=term.get('returncode')
  terminate_sent=term.get('terminate_sent');kill_sent=term.get('kill_sent');requested=term.get('requested_after_proof');term_at=term.get('terminate_sent_at');kill_at=term.get('kill_sent_at');wait_at=term.get('wait_finished_at')
  term_bad=term.get('no_signal_before_proof') is not True or requested is not terminate_sent or disp not in ('proof_then_terminated','proof_then_killed','proof_then_natural_exit','proof_then_natural_exit_race') or (disp=='proof_then_terminated' and (terminate_sent is not True or kill_sent is not False or rc!=-15)) or (disp=='proof_then_killed' and (terminate_sent is not True or kill_sent is not True or rc!=-9)) or (disp=='proof_then_natural_exit' and (terminate_sent is not False or kill_sent is not False or rc!=0)) or (disp=='proof_then_natural_exit_race' and (terminate_sent is not True or kill_sent is not False or rc!=0)) or term.get('term_grace_seconds')!=10.0 or term.get('kill_grace_seconds')!=10.0 or (basis=='clean_natural_exit_with_final_trace' and disp!='proof_then_natural_exit')
  try:
   started_t=dt.datetime.fromisoformat(sr['started_at']);proof_t=dt.datetime.fromisoformat(sr['proof_at']);wait_t=dt.datetime.fromisoformat(wait_at);finished_t=dt.datetime.fromisoformat(sr['finished_at'])
   if not started_t<=proof_t<=wait_t<=finished_t:term_bad=True
   if terminate_sent:
    term_t=dt.datetime.fromisoformat(term_at)
    if not proof_t<=term_t<=wait_t:term_bad=True
   elif term_at is not None:term_bad=True
   if kill_sent:
    kill_t=dt.datetime.fromisoformat(kill_at)
    if not term_t<=kill_t<=wait_t or (wait_t-kill_t).total_seconds()>11:term_bad=True
   elif kill_at is not None:term_bad=True
   if terminate_sent and not kill_sent and (wait_t-term_t).total_seconds()>11:term_bad=True
  except Exception:term_bad=True
  if term_bad:err.append('smoke_termination='+str(seed))
  for stream in ('stdout','stderr'):
   meta=sr.get(stream,{});expected_rel='build/smoke_seed_'+str(seed)+'/solver.'+stream;p=B/meta.get('path','')
   if meta.get('path')!=expected_rel or not p.is_file() or p.is_symlink() or sha(p)!=meta.get('sha256') or p.stat().st_size!=meta.get('bytes'):err.append('smoke_'+stream+'_artifact='+str(seed))
  stdout_path=work/'solver.stdout'
  try:marker_count=sum(1 for line in stdout_path.open(errors='replace') if line.rstrip('\n')=='QBASIS_LANCZOS_SEED = '+str(seed))
  except OSError:marker_count=-1
  if marker_count!=1:err.append('smoke_marker_artifact='+str(seed))
  traces=sr.get('traces',{});names=set(traces);trace_sets.append(names)
  expected_signature=[[name,traces[name].get('sha256'),traces[name].get('bytes')] for name in sorted(traces)]
  if sr.get('proof_trace_signature')!=expected_signature:err.append('smoke_trace_signature='+str(seed))
  if not names or not names.issubset({'log_Lanczos_sr_val0.txt','log_CG.txt'}) or len(names)>2:err.append('smoke_trace_cardinality='+str(seed))
  for name,meta in traces.items():
   p=work/name
   actual_lines=sum(1 for _ in p.open('rb')) if p.is_file() and not p.is_symlink() else -1
   if not p.is_file() or p.is_symlink() or sha(p)!=meta.get('sha256') or p.stat().st_size!=meta.get('bytes') or meta.get('bytes',0)<=0 or meta.get('lines',0)<=0 or actual_lines!=meta.get('lines'):err.append('smoke_trace_artifact='+str(p))
  if sr.get('partial_obs_remaining')!=0 or list(work.glob('*_obs.dat')):err.append('smoke_partial_obs='+str(seed))
  if not isinstance(sr.get('partial_obs_removed'),list):err.append('smoke_partial_obs_receipt='+str(seed))
 common=trace_sets[0]&trace_sets[1] if len(trace_sets)==2 else set()
 actual_different=sorted(name for name in common if smoke_runs[0]['traces'][name].get('sha256')!=smoke_runs[1]['traces'][name].get('sha256'))
 if smoke.get('different_trace_files')!=actual_different:err.append('smoke_trace_difference')
 actual_prefix={};actual_prefix_different=[]
 for trace_name in sorted(common):
  line_count=min(smoke_runs[0]['traces'][trace_name].get('lines',0),smoke_runs[1]['traces'][trace_name].get('lines',0))
  if line_count<1:continue
  hashes={}
  for sr in smoke_runs:
   h=hashlib.sha256();seen=0;p=B/'build'/('smoke_seed_'+str(sr['seed']))/trace_name
   try:
    with p.open('rb') as f:
     while seen<line_count:
      line=f.readline()
      if not line:break
      h.update(line);seen+=1
   except OSError:seen=-1
   if seen!=line_count:err.append('smoke_prefix_read='+str(p))
   hashes[str(sr['seed'])]=h.hexdigest()
  is_different=len(set(hashes.values()))==2
  actual_prefix[trace_name]={'line_count':line_count,'sha256_by_seed':hashes,'different':is_different}
  if is_different:actual_prefix_different.append(trace_name)
 if not actual_prefix_different or smoke.get('common_prefix_evidence')!=actual_prefix or smoke.get('different_common_prefix_trace_files')!=actual_prefix_different:err.append('smoke_common_prefix_difference')
effective=[x%2147483647 or 1 for x in SEEDS]
if effective!=[436887014,1129136884,1804602142,283214687,1012333963] or len(set(effective))!=5:err.append('minstd_effective_state_gate')
pinrows={}
if (B/'BUILT_PIN_SHA256SUMS').is_file():
 for line in (B/'BUILT_PIN_SHA256SUMS').read_text().splitlines():
  if line.strip():h,rel=line.split(None,1);pinrows[rel.strip()]=h
if set(pinrows)!={'pinned_solver/Hubbard_sym_testobs_UV.x','pinned_solver/Hubbard_sym_testobs_UV.cc','pinned_solver/libqbasis.so'} or pinrows.get('pinned_solver/Hubbard_sym_testobs_UV.cc')!=PATCHED_SOURCE:err.append('built_pin_cardinality_or_source')
if receipt.get('runtime_pins')!={Path(rel).name:h for rel,h in pinrows.items()}:err.append('build_receipt_pin_binding')
lib=B/'pinned_solver/libqbasis.so';solver=B/'pinned_solver/Hubbard_sym_testobs_UV.x'
env=os.environ.copy();env['LD_LIBRARY_PATH']=':'.join((str(B/'pinned_solver'),'/home/9pm/installs/lib','/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64','/home/9pm/intel/oneapi/tbb/latest/lib','/sw/cades-open/gcc/12.2.0/lib64'))
if lib.is_file():
 s=run(['/usr/bin/strings',str(lib)],env).stdout
 for token in ('QBASIS_LANCZOS_SEED','QBASIS_LANCZOS_SEED is required','QBASIS_LANCZOS_SEED = '):
  if token not in s:err.append('lib_seed_token='+token)
if solver.is_file():
 rd=run(['/usr/bin/readelf','-d',str(solver)],env)
 if rd.returncode or '$ORIGIN' not in rd.stdout or '/home/9pm/installs/lib' in rd.stdout:err.append('solver_rpath')
 l=run(['/usr/bin/ldd',str(solver)],env)
 if l.returncode:err.append('ldd='+l.stderr)
 found=''
 for line in l.stdout.splitlines():
  if line.strip().startswith('libqbasis.so => '):found=line.split('=>',1)[1].strip().split()[0]
 if not found or Path(found).resolve()!=lib.resolve():err.append('ldd_qbasis='+found)
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
if len(rows)!=5 or [r['replica_index'] for r in rows]!=['1','2','3','4','5'] or [r['replica_ordinal'] for r in rows]!=['4','5','6','7','8'] or [int(r['seed']) for r in rows]!=SEEDS:err.append('manifest_cardinality_ordinal_seed')
if len({r['replica_result'] for r in rows})!=5 or len({r['script'] for r in rows})!=5:err.append('manifest_path_uniqueness')
if (B/'submission_header.tsv').read_text()!='submitted_at\taccount\tjob_id\treplica_index\treplica_ordinal\tsource_index\tsource_job_id\tU\tV\tkx\tky\tseed\tscript\treplica_result\n':err.append('submission_header_template')
if os.path.lexists(B/'submission.tsv') or (B/'submission_receipt.json').exists() or (B/'SUBMISSION_SHA256SUMS').exists():err.append('prior_submission_artifacts')
for r in rows:
 p=Path(r['script']);rp=Path(r['replica_result']);t=p.read_text() if p.is_file() and not p.is_symlink() else ''
 for x in ('#SBATCH -A ccsd','#SBATCH -p burst','#SBATCH -N 1','#SBATCH -n 32','#SBATCH -c 1','#SBATCH -J F4U80R5','#SBATCH --mem=100G','#SBATCH -t 47:00:00'):
  if x not in t:err.append('resource='+p.name+':'+x)
 if re.search(r'(^|[^A-Za-z])python(?:[0-9.]*)?([^A-Za-z]|$)',t,re.I):err.append('compute_python='+p.name)
 for x in ('QBASIS_LANCZOS_SEED','effective-seed proof missing/nonunique','BUILT_PIN_SHA256SUMS','MAXIT=\'50000\''):
  if x not in t:err.append('hardening='+p.name+':'+x)
 if re.search(r'\b(?:cp|mv|rm|unlink|install|truncate|tee)\b[^\n]*\$\{?CANONICAL\}?',t):err.append('canonical_write='+p.name)
 if not r['replica_result'].startswith(str(B)+'/results/') or not r['script'].startswith(str(B)+'/jobs/'):err.append('nonlocal_path='+r['replica_index'])
 if os.path.lexists(rp):err.append('result_exists='+str(rp))
for d in ('results','work','locks','logs'):
 p=B/d
 if os.path.lexists(p) and (not p.is_dir() or p.is_symlink() or any(p.iterdir())):err.append('nonempty_or_unsafe_dir='+str(p))
for n,h in SOURCE_HASHES.items():
 p=SOURCE/n
 if not p.is_file() or p.is_symlink() or sha(p)!=h:err.append('source_hash='+n)
pattern=re.compile(rb'(?<![0-9])(?:'+b'|'.join(str(x).encode() for x in SEEDS)+rb')(?![0-9])')
for dp,dnames,fnames in os.walk(ROOT):
 pp=Path(dp)
 if pp==B or B in pp.parents:dnames[:]=[];continue
 for name in fnames:
  p=pp/name
  try:
   if not p.is_file() or p.is_symlink():continue
   data=p.read_bytes();scan['files']+=1;scan['bytes']+=len(data)
  except OSError as e:scan['errors']+=1;err.append('seed_scan_read='+str(p)+':'+str(e));continue
  for m in pattern.finditer(data):scan['hits'].setdefault(m.group().decode(),[]).append(str(p))
if scan['hits']:err.append('live_seed_occurrence='+json.dumps(scan['hits'],sort_keys=True))
if os.path.lexists(CANON):err.append('canonical_exists')
aud=run(['/usr/bin/python3.11',str(SOURCE/'audit_status.py'),'--batch',str(SOURCE),'--job-name','F4C80V20','--job-name','F4C80V20R','--pin-file','PINNED_SHA256SUMS','--submission-log','repair_submission.tsv','--require-pins','--since','2026-08-22','--expect-targets','25','--expect-per-case','25','--expect-account','ccsd','--expect-partition','burst','--expect-cpus','32','--expect-nodes','1','--expect-memory','100G','--expect-time-limit','08:00:00'])
for x in ('TARGETS 25 | COMPLETE=24 FAILED=1','ANOMALIES 0','REPAIR_CANDIDATES 1','PINS 3/3 MATCH'):
 if x not in aud.stdout:err.append('source_audit_missing='+x)
if aud.returncode:err.append('source_audit_rc='+str(aud.returncode)+':'+aud.stderr)
prior=run(['/usr/bin/python3.11',str(PRIOR/'audit_replicas.py'),'--json']);pr={}
try:pr=json.loads(prior.stdout)
except Exception as e:err.append('prior_audit_json='+str(e))
if prior.returncode or pr.get('counts')!={'FAILED':1,'TIMEOUT':2} or pr.get('anomalies')!=[]:err.append('prior_replica_endpoint')
activity=[]
for name in ('F4C80V20','F4C80V20R','F4U80R3','F4U80R5'):
 q=run(['squeue','-h','-r','-u','9pm','-n',name,'-o','%i|%j|%T|%a|%P|%C|%D|%m|%l'])
 if q.returncode:err.append('squeue_'+name+'='+q.stderr)
 if q.stdout.strip():activity.extend(q.stdout.strip().splitlines());err.append('unexpected_activity_'+name+'='+q.stdout.strip())
hist=run(['sacct','-X','-n','-P','-S','2026-01-01','--name',JOB,'--format=JobIDRaw,JobName,State'])
if hist.returncode:err.append('sacct_history='+hist.stderr)
if hist.stdout.strip():err.append('job_name_history='+hist.stdout.strip())
cap_total=run(['squeue','-h','-r','-u','9pm','-o','%i']);used_total=len([x for x in cap_total.stdout.splitlines() if x.strip()]) if cap_total.returncode==0 else 999
cap_ccsd=run(['squeue','-h','-r','-u','9pm','-A','ccsd','-o','%i']);used_ccsd=len([x for x in cap_ccsd.stdout.splitlines() if x.strip()]) if cap_ccsd.returncode==0 else 999
if cap_total.returncode or cap_ccsd.returncode or 150-used_total<5:err.append('capacity_total='+str(used_total)+':'+cap_total.stderr+cap_ccsd.stderr)
report={'schema':'fig4_u80v20_true_seed_maxit50000_five_replica_preflight_v1','pass':not err,'batch':str(B),'job_name':JOB,'replicas':len(rows),'new_seeds':SEEDS,'maxit':50000,'resources':{'account':'ccsd','partition':'burst','nodes':1,'tasks':32,'cpus_per_task':1,'memory':'100G','time_limit':'47:00:00'},'runtime_pins':pinrows,'seed_live_scan':scan,'user_active_total':used_total,'user_headroom_under_150':150-used_total,'ccsd_active':used_ccsd,'prior_replica_counts':pr.get('counts',{}),'exact_name_activity':activity,'errors':err}
print(json.dumps(report,sort_keys=True,indent=2));raise SystemExit(2 if err else 0)
