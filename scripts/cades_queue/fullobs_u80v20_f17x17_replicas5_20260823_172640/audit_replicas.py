#!/usr/bin/env /usr/bin/python3.11
import sys
sys.dont_write_bytecode=True
import argparse,csv,datetime as dt,hashlib,json,os,re,subprocess
from collections import Counter
from pathlib import Path
from validate_output import validate
B=Path(__file__).resolve().parent;JOB='F4U80R5';SOURCE_JOB='5619905';PRIOR_JOBS={'5620075','5620076','5620077'}
PINS={}
EXPECTED_SEEDS=['436887014','3276620531','3952085789','2430698334','1012333963']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(a):return subprocess.run(a,text=True,capture_output=True)
def complete(p):
 try:return p.is_file() and not p.is_symlink() and re.search(r'^status\s+COMPLETE$',p.read_text(errors='replace'),re.M) is not None
 except OSError:return False
def base_state(s):return s.split()[0].split('+')[0]
def resource_errors(jid,r):
 out=[]
 for k,e in [('job_name',(JOB,)),('account',('ccsd',)),('partition',('burst',)),('cpus',('32',)),('nodes',('1',)),('memory',('100G',)),('time_limit',('1-23:00:00','47:00:00'))]:
  if r.get(k) not in e:out.append(f'resource_{jid}_{k}={r.get(k)}')
 return out
ap=argparse.ArgumentParser();ap.add_argument('--json',action='store_true');a=ap.parse_args();an=[]
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
if len(rows)!=5 or [r['replica_index'] for r in rows]!=['1','2','3','4','5'] or [r['replica_ordinal'] for r in rows]!=['4','5','6','7','8'] or [r['seed'] for r in rows]!=EXPECTED_SEEDS:an.append('cardinality_ordinal_or_seed')
ledger={};ledger_rows=[]
subledger=B/'submission.tsv'
if subledger.is_file() and not subledger.is_symlink():
 with subledger.open(newline='') as f:
  for r in csv.DictReader(f,delimiter='\t'):
   ledger_rows.append(r)
   if r['replica_index'] in ledger:an.append('duplicate_ledger_index='+r['replica_index'])
   ledger[r['replica_index']]=r
elif os.path.lexists(subledger):an.append('unsafe_submission_ledger')
if len({r.get('job_id') for r in ledger_rows})!=len(ledger_rows):an.append('duplicate_job_id')
for r in ledger_rows:
 m=next((x for x in rows if x['replica_index']==r['replica_index']),None)
 if not m or any(r[k]!=m[k] for k in ('replica_ordinal','source_index','source_job_id','U','V','kx','ky','seed','script','replica_result')) or r['account']!='ccsd':an.append('ledger_manifest_mismatch='+r['replica_index'])
q=run(['squeue','-h','-r','-u','9pm','-n',JOB,'-o','%i|%j|%T|%a|%P|%C|%D|%m|%l']);active={}
if q.returncode:an.append('squeue='+q.stderr)
for line in q.stdout.splitlines():
 x=line.split('|')
 if len(x)!=9:an.append('squeue_line='+line);continue
 active[x[0]]=dict(zip(('job_name','state','account','partition','cpus','nodes','memory','time_limit'),x[1:]))
known={v['job_id'] for v in ledger.values()}
for jid,r in active.items():
 if jid not in known:an.append('unmapped='+jid)
 an.extend(resource_errors(jid,r))
ids=sorted(known);terminal={}
if ids:
 s=run(['sacct','-X','-n','-P','-j',','.join(ids),'--format=JobIDRaw,JobName,Account,Partition,State,ExitCode,Elapsed,Timelimit,AllocCPUS,NNodes,ReqMem'])
 if s.returncode:an.append('sacct='+s.stderr)
 else:
  for line in s.stdout.splitlines():
   x=line.split('|')
   if len(x)>=11 and x[0] in ids:terminal[x[0]]=dict(zip(('job_name','account','partition','state','exit_code','elapsed','time_limit','cpus','nodes','memory'),x[1:11]))
for jid,r in terminal.items():an.extend(resource_errors(jid,r))
pins=[]
built_ledger=B/'BUILT_PIN_SHA256SUMS'
if built_ledger.is_file():
 for line in built_ledger.read_text().splitlines():
  if line.strip():
   e,rel=line.split(None,1);p=B/rel.strip();act=sha(p) if p.is_file() and not p.is_symlink() else '';pins.append({'file':p.name,'expected':e,'actual':act,'match':act==e})
   if act!=e:an.append('pin='+p.name)
else:an.append('missing_BUILT_PIN_SHA256SUMS')
if len(pins)!=3 or {x['file'] for x in pins}!={'Hubbard_sym_testobs_UV.x','Hubbard_sym_testobs_UV.cc','libqbasis.so'}:an.append('pin_cardinality')
if next((x['actual'] for x in pins if x['file']=='Hubbard_sym_testobs_UV.cc'),'')!='fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b':an.append('patched_source_identity')
# Bind the built runtime to exact patched sources and actual two-seed solver smoke evidence.
build_receipt={};build_receipt_path=B/'BUILD_RECEIPT.json'
try:build_receipt=json.loads(build_receipt_path.read_text())
except Exception as e:an.append('build_receipt='+str(e))
if build_receipt.get('schema')!='fig4_u80v20_true_seed_maxit50000_isolated_build_v2' or build_receipt.get('patched_model_sha256')!='c7a45062ce4d8b45e60768519276044f748de6d955095a2a1bd828b0d451c510' or build_receipt.get('patched_hubbard_sha256')!='fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b' or build_receipt.get('shared_tree_writes') is not False or build_receipt.get('make_install_invoked') is not False:an.append('build_receipt_identity')
if build_receipt.get('runtime_pins')!={x['file']:x['actual'] for x in pins}:an.append('build_receipt_pin_binding')
smoke=build_receipt.get('true_seed_smoke',{});smoke_runs=smoke.get('runs',[])
if smoke.get('schema')!='actual_solver_bounded_two_seed_proof_v1' or smoke.get('passed') is not True or smoke.get('bounded_process_end') is not True or [x.get('seed') for x in smoke_runs]!=[436887014,3276620531]:an.append('true_seed_build_smoke')
else:
 trace_sets=[];expected_solver=str(B/'build/candidate_pins/Hubbard_sym_testobs_UV.x')
 for sr in smoke_runs:
  seed=sr.get('seed');work=B/'build'/('smoke_seed_'+str(seed));expected_command=[expected_solver,'1','1','17','17','0','0','80','20','0']
  expected_env={'QBASIS_LANCZOS_SEED':str(seed),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OMP_PROC_BIND':'close','OMP_PLACES':'cores'}
  if sr.get('schema')!='actual_solver_bounded_seed_trace_proof_v1' or sr.get('command')!=expected_command or sr.get('environment')!=expected_env or sr.get('cwd')!=str(work) or sr.get('proof_reached') is not True or sr.get('stdout_seed_marker_count')!=1 or not isinstance(sr.get('pid'),int) or sr.get('pid',0)<=0 or sr.get('process_group_id')!=sr.get('pid'):an.append('smoke_process_identity='+str(seed))
  latency=sr.get('proof_latency_seconds');timeout=sr.get('proof_timeout_seconds')
  if not isinstance(latency,(int,float)) or not isinstance(timeout,(int,float)) or latency<0 or timeout!=720.0 or latency>timeout or not (sr.get('started_at') and sr.get('proof_at') and sr.get('finished_at')) or not (sr['started_at']<=sr['proof_at']<=sr['finished_at']):an.append('smoke_timing='+str(seed))
  basis=sr.get('proof_basis');observed=sr.get('stable_trace_polls_observed')
  if sr.get('poll_seconds')!=0.25 or sr.get('stable_trace_polls_required')!=3 or not isinstance(observed,int) or observed<1 or basis not in ('stable_trace_snapshots_while_running','clean_natural_exit_with_final_trace') or (basis=='stable_trace_snapshots_while_running' and observed<3) or not sr.get('proof_trace_signature'):an.append('smoke_trace_stability='+str(seed))
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
  if term_bad:an.append('smoke_termination='+str(seed))
  for stream in ('stdout','stderr'):
   meta=sr.get(stream,{});expected_rel='build/smoke_seed_'+str(seed)+'/solver.'+stream;p=B/meta.get('path','')
   if meta.get('path')!=expected_rel or not p.is_file() or p.is_symlink() or sha(p)!=meta.get('sha256') or p.stat().st_size!=meta.get('bytes'):an.append('smoke_'+stream+'_artifact='+str(seed))
  stdout_path=work/'solver.stdout'
  try:marker_count=sum(1 for line in stdout_path.open(errors='replace') if line.rstrip('\n')=='QBASIS_LANCZOS_SEED = '+str(seed))
  except OSError:marker_count=-1
  if marker_count!=1:an.append('smoke_marker_artifact='+str(seed))
  traces=sr.get('traces',{});names=set(traces);trace_sets.append(names)
  expected_signature=[[name,traces[name].get('sha256'),traces[name].get('bytes')] for name in sorted(traces)]
  if sr.get('proof_trace_signature')!=expected_signature:an.append('smoke_trace_signature='+str(seed))
  if not names or not names.issubset({'log_Lanczos_sr_val0.txt','log_CG.txt'}) or len(names)>2:an.append('smoke_trace_cardinality='+str(seed))
  for name,meta in traces.items():
   p=work/name
   actual_lines=sum(1 for _ in p.open('rb')) if p.is_file() and not p.is_symlink() else -1
   if not p.is_file() or p.is_symlink() or sha(p)!=meta.get('sha256') or p.stat().st_size!=meta.get('bytes') or meta.get('bytes',0)<=0 or meta.get('lines',0)<=0 or actual_lines!=meta.get('lines'):an.append('smoke_trace_artifact='+str(p))
  if sr.get('partial_obs_remaining')!=0 or list(work.glob('*_obs.dat')):an.append('smoke_partial_obs='+str(seed))
  if not isinstance(sr.get('partial_obs_removed'),list):an.append('smoke_partial_obs_receipt='+str(seed))
 common=trace_sets[0]&trace_sets[1] if len(trace_sets)==2 else set()
 actual_different=sorted(name for name in common if smoke_runs[0]['traces'][name].get('sha256')!=smoke_runs[1]['traces'][name].get('sha256'))
 if smoke.get('different_trace_files')!=actual_different:an.append('smoke_trace_difference')
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
   if seen!=line_count:an.append('smoke_prefix_read='+str(p))
   hashes[str(sr['seed'])]=h.hexdigest()
  is_different=len(set(hashes.values()))==2
  actual_prefix[trace_name]={'line_count':line_count,'sha256_by_seed':hashes,'different':is_different}
  if is_different:actual_prefix_different.append(trace_name)
 if not actual_prefix_different or smoke.get('common_prefix_evidence')!=actual_prefix or smoke.get('different_common_prefix_trace_files')!=actual_prefix_different:an.append('smoke_common_prefix_difference')
# Verify both immutable ledgers explicitly.
for source_line in (B/'SOURCE_SHA256SUMS').read_text().splitlines():
 if source_line.strip():
  h,rel=source_line.split(None,1);x=B/rel.strip()
  if not x.is_file() or x.is_symlink() or sha(x)!=h:an.append('SOURCE_SHA256SUMS:'+rel.strip())
for line in (B/'PACKAGE_SHA256SUMS').read_text().splitlines():
 if line.strip():
  h,rel=line.split(None,1);x=B/rel.strip()
  if not x.is_file() or x.is_symlink() or sha(x)!=h:an.append('PACKAGE_SHA256SUMS:'+rel.strip())
submission_receipt={};submission_receipt_path=B/'submission_receipt.json'
if ledger_rows:
 if len(ledger_rows)!=5:an.append('submission_cardinality='+str(len(ledger_rows)))
 try:submission_receipt=json.loads(submission_receipt_path.read_text())
 except Exception as e:an.append('submission_receipt='+str(e))
 expected_jobs=[{'replica_index':r['replica_index'],'replica_ordinal':r['replica_ordinal'],'seed':r['seed'],'job_id':r['job_id']} for r in ledger_rows]
 if submission_receipt.get('schema')!='fig4_u80v20_five_additional_replicas_submission_v1' or submission_receipt.get('count')!=5 or submission_receipt.get('jobs')!=expected_jobs or submission_receipt.get('manifest_sha256')!=sha(B/'replica_manifest.tsv') or submission_receipt.get('package_sha256s_sha256')!=sha(B/'PACKAGE_SHA256SUMS') or submission_receipt.get('build_receipt_sha256')!=(sha(build_receipt_path) if build_receipt_path.is_file() else '') or submission_receipt.get('built_pin_ledger_sha256')!=(sha(built_ledger) if built_ledger.is_file() else ''):an.append('submission_receipt_binding')
subhash=B/'SUBMISSION_SHA256SUMS'
if subhash.is_file():
 for line in subhash.read_text().splitlines():
  if line.strip():
   h,rel=line.split(None,1);x=B/rel.strip()
   if not x.is_file() or x.is_symlink() or sha(x)!=h:an.append('SUBMISSION_SHA256SUMS:'+rel.strip())
elif ledger_rows:an.append('missing_SUBMISSION_SHA256SUMS')
counts=Counter();details=[]
for r in rows:
 verr,res=validate(r['replica_result'],r['U'],r['V']);jid=ledger.get(r['replica_index'],{}).get('job_id','');rp=Path(r['replica_result']);cp=Path(r['canonical_result'])
 if rp.exists() or rp.is_symlink():st='COMPLETE' if not verr else 'INVALID'
 elif jid in active:st=active[jid]['state']
 elif jid in terminal:
  x=base_state(terminal[jid]['state']);st='SKIPPED_CANONICAL' if x=='COMPLETED' and complete(cp) else ('COMPLETED_NO_OUTPUT' if x=='COMPLETED' else x)
 elif jid:st='SUBMITTED_UNKNOWN'
 else:st='UNSUBMITTED'
 counts[st]+=1
 if (rp.exists() or rp.is_symlink()) and verr:an.append('invalid='+str(rp)+':'+','.join(verr))
 proof_path=B/'work'/('replica_'+r['replica_index']+'_'+jid)/'solver.combined.log' if jid else None
 proof_count=0
 if proof_path and proof_path.is_file() and not proof_path.is_symlink():
  try:proof_count=sum(1 for line in proof_path.open(errors='replace') if line.rstrip('\n')=='QBASIS_LANCZOS_SEED = '+r['seed'])
  except OSError:proof_count=-1
 proof_ok=proof_count==1
 if st in ('COMPLETE','COMPLETED_NO_OUTPUT','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL') and not proof_ok:an.append('effective_seed_proof_'+r['replica_index']+'='+str(proof_count))
 details.append({'replica_index':r['replica_index'],'replica_ordinal':r['replica_ordinal'],'seed':r['seed'],'effective_minstd_rand0_state':int(r['seed'])%2147483647 or 1,'effective_seed_proof':proof_ok,'effective_seed_marker_count':proof_count,'effective_seed_log':str(proof_path) if proof_path else '', 'job_id':jid,'status':st,'validation_errors':verr,'identity_residuals':res,'canonical_exists':os.path.lexists(cp),'canonical_complete':complete(cp),'result':str(rp)})
# Detect exact-name terminal jobs not mapped by the immutable submission receipt.
history=run(['sacct','-X','-n','-P','-S','2026-01-01','--name',JOB,'--format=JobIDRaw,JobName,State'])
terminal_unmapped=[]
if history.returncode:an.append('sacct_name_history='+history.stderr)
else:
 for line in history.stdout.splitlines():
  x=line.split('|')
  if len(x)>=3 and x[1]==JOB and x[0] not in known:terminal_unmapped.append(line);an.append('unmapped_terminal='+x[0])
# Canonical and prior exact-name activity must remain zero; new activity must map above.
unrelated_activity=[]
for name in ('F4C80V20','F4C80V20R','F4U80R3'):
 x=run(['squeue','-h','-r','-u','9pm','-n',name,'-o','%i|%j|%T'])
 if x.returncode:an.append('squeue_'+name+'='+x.stderr)
 if x.stdout.strip():unrelated_activity.extend(x.stdout.strip().splitlines());an.append('unexpected_activity_'+name+'='+x.stdout.strip())
report={'schema':'fig4_u80v20_true_seed_maxit50000_five_replica_monitor_v1','batch':str(B),'job_name':JOB,'count':5,'maxit':50000,'time_limit':'47:00:00','target':{'U':80,'V':20,'kx':17,'ky':17,'source_job_id':SOURCE_JOB},'counts':dict(sorted(counts.items())),'pins':pins,'package_manifest_sha256':sha(B/'replica_manifest.tsv'),'package_ledger_sha256':sha(B/'PACKAGE_SHA256SUMS'),'source_ledger_sha256':sha(B/'SOURCE_SHA256SUMS'),'build_receipt_sha256':sha(build_receipt_path) if build_receipt_path.is_file() else '','submission_ledger_rows':len(ledger_rows),'anomalies':an,'unrelated_exact_name_activity':unrelated_activity,'unmapped_terminal_activity':terminal_unmapped,'details':details,'read_only':True}
print(json.dumps(report,sort_keys=True,indent=2) if a.json else json.dumps(report,sort_keys=True));raise SystemExit(2 if an else 0)
