#!/usr/bin/env /usr/bin/python3.11
"""Build true-seed qbasis and maxit=50000 solver only inside this batch.

This script never installs into the shared qbasis tree and never submits a job.
It is intentionally one-shot: partial build artifacts require controlled review.
"""
import datetime as dt,hashlib,json,os,platform,shutil,signal,subprocess,sys,time
from pathlib import Path
B=Path(__file__).resolve().parent
REMOTE=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640')
GXX=Path('/sw/cades-open/gcc/12.2.0/bin/g++')
MKL_INC=Path('/home/9pm/intel/oneapi/mkl/2024.2/include');MKL_LIB=Path('/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64')
TBB_LIB=Path('/home/9pm/intel/oneapi/tbb/latest/lib');INSTALL_INC=Path('/home/9pm/installs/include');INSTALL_LIB=Path('/home/9pm/installs/lib')
PATCHED_MODEL_SHA='c7a45062ce4d8b45e60768519276044f748de6d955095a2a1bd828b0d451c510'
PATCHED_HUBBARD_SHA='fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b'
ORIGINAL_MODEL_SHA='ffdcbb4d15a64f8e703e81d642edb0036a6e87e1937191c3474e740c1940d3e7'
ORIGINAL_HUBBARD_SHA='f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(cmd,env,log,cwd=None,timeout=None):
 started=dt.datetime.now().astimezone().isoformat();p=subprocess.run([str(x) for x in cmd],text=True,capture_output=True,env=env,cwd=cwd,timeout=timeout)
 record={'started_at':started,'finished_at':dt.datetime.now().astimezone().isoformat(),'argv':[str(x) for x in cmd],'cwd':str(cwd) if cwd else None,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr};log.append(record)
 if p.returncode:raise RuntimeError('command failed: '+repr(record))
 return p
if B!=REMOTE:raise SystemExit('REFUSE wrong remote batch: '+str(B))
for p in (GXX,MKL_INC,MKL_LIB,TBB_LIB,INSTALL_INC,INSTALL_LIB):
 if not p.exists():raise SystemExit('REFUSE missing build dependency: '+str(p))
for p in (B/'build',B/'pinned_solver',B/'BUILD_RECEIPT.json',B/'BUILT_PIN_SHA256SUMS'):
 if os.path.lexists(p):raise SystemExit('REFUSE existing build artifact: '+str(p))
# Verify immutable package and complete source snapshot before any write.
for ledger in ('PACKAGE_SHA256SUMS','SOURCE_SHA256SUMS'):
 for line in (B/ledger).read_text().splitlines():
  if line.strip():
   expected,rel=line.split(None,1);p=B/rel.strip()
   if not p.is_file() or p.is_symlink() or sha(p)!=expected:raise SystemExit('REFUSE '+ledger+' mismatch: '+rel.strip())
orig_model=B/'source_provenance/qbasis_original/model.cc';patch_model=B/'build_sources/qbasis/model.cc'
orig_hubbard=B/'source_provenance/Hubbard_sym_testobs_UV.original.cc';patch_hubbard=B/'build_sources/Hubbard_sym_testobs_UV.cc'
for p,e in ((orig_model,ORIGINAL_MODEL_SHA),(patch_model,PATCHED_MODEL_SHA),(orig_hubbard,ORIGINAL_HUBBARD_SHA),(patch_hubbard,PATCHED_HUBBARD_SHA)):
 if sha(p)!=e:raise SystemExit('REFUSE source identity: '+str(p))
mt=patch_model.read_text();ht=patch_hubbard.read_text()
required_model=('std::getenv("QBASIS_LANCZOS_SEED")','QBASIS_LANCZOS_SEED is required','parsed_seed > (4294967295ULL - digit) / 10ULL','const uint32_t seed = static_cast<uint32_t>(parsed_seed)','QBASIS_LANCZOS_SEED = ')
if any(mt.count(x)!=1 for x in required_model) or 'uint32_t seed   = 1;' in mt:raise SystemExit('REFUSE true-seed patch semantics')
if ht.count('Hubbard.locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, 50000);')!=1 or 'locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, 10000)' in ht:raise SystemExit('REFUSE maxit patch semantics')
build=B/'build';qsrc=build/'qbasis';candidate=build/'candidate_pins';qsrc.mkdir(parents=True,mode=0o700);candidate.mkdir(mode=0o700)
for p in (B/'build_sources/qbasis').iterdir():
 if p.is_file():shutil.copy2(p,qsrc/p.name)
shutil.copy2(patch_hubbard,candidate/'Hubbard_sym_testobs_UV.cc')
env=os.environ.copy();env.update({'MKL_INC_DIR':str(MKL_INC),'MKL_LIB_DIR':str(MKL_LIB),'PATH':'/sw/cades-open/gcc/12.2.0/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin','LD_LIBRARY_PATH':':'.join((str(candidate),str(INSTALL_LIB),str(MKL_LIB),str(TBB_LIB),'/sw/cades-open/gcc/12.2.0/lib64'))})
flags=['-std=c++17','-Wall','-O3','-funroll-loops','-m64','-DMKL_ILP64','-march=native','-fPIC','-fopenmp','-I'+str(qsrc),'-I'+str(INSTALL_INC),'-I'+str(MKL_INC)]
libs=['-L'+str(INSTALL_LIB),'-larpackILP64','-fopenmp','-L'+str(MKL_LIB),'-Wl,--no-as-needed','-lmkl_intel_ilp64','-lmkl_tbb_thread','-lmkl_core','-lpthread','-L'+str(TBB_LIB),'-ltbb','-lm','-ldl','-Wl,-rpath,$ORIGIN']
logs=[];objects=[]
for stem in ('basis','ckpt','lanczos','lattice','miscellaneous','model','operators','sparse'):
 obj=qsrc/(stem+'.o');run([GXX,*flags,'-c','-o',obj,qsrc/(stem+'.cc')],env,logs);objects.append(obj)
lib=candidate/'libqbasis.so';run([GXX,'-shared','-fPIC',*objects,*libs,'-o',lib],env,logs)
solver=candidate/'Hubbard_sym_testobs_UV.x';run([GXX,*flags,candidate/'Hubbard_sym_testobs_UV.cc','-L'+str(candidate),'-lqbasis',*libs,'-o',solver],env,logs)
# Static and dynamic linkage gates on the candidates.
strings=run(['/usr/bin/strings',lib],env,logs).stdout
for token in ('QBASIS_LANCZOS_SEED','QBASIS_LANCZOS_SEED is required','QBASIS_LANCZOS_SEED = '):
 if token not in strings:raise SystemExit('REFUSE built library lacks '+token)
readelf=run(['/usr/bin/readelf','-d',solver],env,logs).stdout
if 'Shared library: [libqbasis.so]' not in readelf:raise SystemExit('REFUSE solver is not dynamically linked to libqbasis.so')
if '$ORIGIN' not in readelf or str(INSTALL_LIB) in readelf:raise SystemExit('REFUSE solver rpath is not isolated to $ORIGIN')
lib_readelf=run(['/usr/bin/readelf','-d',lib],env,logs).stdout
if '$ORIGIN' not in lib_readelf or str(INSTALL_LIB) in lib_readelf:raise SystemExit('REFUSE libqbasis rpath is not isolated to $ORIGIN')
ldd=run(['/usr/bin/ldd',solver],env,logs).stdout
resolved=None
for line in ldd.splitlines():
 if line.strip().startswith('libqbasis.so => '):resolved=line.split('=>',1)[1].strip().split()[0]
if not resolved or Path(resolved).resolve()!=lib.resolve():raise SystemExit('REFUSE ldd did not resolve candidate libqbasis: '+repr(resolved))
# Exercise the actual patched solver/library in two independent tiny sectors.
# A full solver invocation proceeds into expensive observable evaluation, which is
# irrelevant to this build gate. Poll only until the exact seed marker and a
# nonempty allowed Lanczos/CG trace prove consumption, then terminate exclusively
# the new smoke process group. No canonical/shared path is ever an argument.
SMOKE_PROOF_TIMEOUT=720.0;SMOKE_POLL_SECONDS=0.25;SMOKE_STABLE_POLLS=3;SMOKE_TERM_GRACE=10.0;SMOKE_KILL_GRACE=10.0
ALLOWED_TRACES=('log_Lanczos_sr_val0.txt','log_CG.txt')
def exact_line_count(path,target):
 try:
  with path.open(errors='replace') as f:return sum(1 for line in f if line.rstrip('\n')==target)
 except OSError:return 0
def hash_first_lines(path,count):
 h=hashlib.sha256();seen=0
 with path.open('rb') as f:
  while seen<count:
   line=f.readline()
   if not line:break
   h.update(line);seen+=1
 if seen!=count:raise RuntimeError('trace shorter than recorded prefix: '+str(path))
 return h.hexdigest()
def nonempty_trace_snapshot(work):
 traces={}
 for name in ALLOWED_TRACES:
  p=work/name
  try:
   if p.is_file() and not p.is_symlink() and p.stat().st_size>0:
    traces[name]={'sha256':sha(p),'bytes':p.stat().st_size,'lines':sum(1 for _ in p.open(errors='replace'))}
  except OSError:continue
 return traces
def stop_owned_smoke(proc,proof_reached):
 # The executable is launched in a new session, so this can signal only the
 # smoke process group. ProcessLookupError is a benign natural-exit race.
 terminate_sent_at=None;kill_sent_at=None
 if proc.poll() is None:
  try:
   os.killpg(proc.pid,signal.SIGTERM);terminate_sent_at=dt.datetime.now().astimezone().isoformat()
  except ProcessLookupError:pass
  if terminate_sent_at is not None:
   try:proc.wait(timeout=SMOKE_TERM_GRACE)
   except subprocess.TimeoutExpired:
    try:
     os.killpg(proc.pid,signal.SIGKILL);kill_sent_at=dt.datetime.now().astimezone().isoformat()
    except ProcessLookupError:pass
    try:proc.wait(timeout=SMOKE_KILL_GRACE)
    except subprocess.TimeoutExpired:raise RuntimeError('owned smoke process group did not stop within TERM/KILL bounds')
  else:proc.wait(timeout=SMOKE_TERM_GRACE)
 terminate_sent=terminate_sent_at is not None;kill_sent=kill_sent_at is not None;returncode=proc.returncode
 if kill_sent:disposition='proof_then_killed' if proof_reached else 'failure_cleanup_killed'
 elif terminate_sent and returncode==0:disposition='proof_then_natural_exit_race' if proof_reached else 'failure_cleanup_natural_exit_race'
 elif terminate_sent:disposition='proof_then_terminated' if proof_reached else 'failure_cleanup_terminated'
 else:disposition='proof_then_natural_exit' if proof_reached else 'failure_cleanup_natural_exit'
 return {'no_signal_before_proof':proof_reached,'requested_after_proof':proof_reached and terminate_sent,'terminate_sent':terminate_sent,'terminate_sent_at':terminate_sent_at,'kill_sent':kill_sent,'kill_sent_at':kill_sent_at,'wait_finished_at':dt.datetime.now().astimezone().isoformat(),'term_grace_seconds':SMOKE_TERM_GRACE,'kill_grace_seconds':SMOKE_KILL_GRACE,'disposition':disposition,'returncode':returncode}
smoke=[]
for smoke_seed in (436887014,3276620531):
 work=build/('smoke_seed_'+str(smoke_seed));work.mkdir(mode=0o700)
 smoke_identity_env={'QBASIS_LANCZOS_SEED':str(smoke_seed),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OMP_PROC_BIND':'close','OMP_PLACES':'cores'}
 smoke_env=env.copy();smoke_env.update(smoke_identity_env)
 command=[str(solver),'1','1','17','17','0','0','80','20','0'];stdout_path=work/'solver.stdout';stderr_path=work/'solver.stderr';marker='QBASIS_LANCZOS_SEED = '+str(smoke_seed)
 started_at=dt.datetime.now().astimezone().isoformat();t0=time.monotonic();proof_at=None;proof_basis=None;proof_traces={};last_trace_signature=None;stable_trace_polls=0
 with stdout_path.open('x') as stdout_file,stderr_path.open('x') as stderr_file:
  proc=subprocess.Popen(command,stdout=stdout_file,stderr=stderr_file,text=True,env=smoke_env,cwd=work,start_new_session=True)
  while True:
   marker_count=exact_line_count(stdout_path,marker);proof_traces=nonempty_trace_snapshot(work)
   trace_signature=tuple((name,meta['sha256'],meta['bytes']) for name,meta in sorted(proof_traces.items()))
   if marker_count==1 and proof_traces:
    if trace_signature==last_trace_signature:stable_trace_polls+=1
    else:last_trace_signature=trace_signature;stable_trace_polls=1
    if stable_trace_polls>=SMOKE_STABLE_POLLS:
     proof_rc=proc.poll()
     if proof_rc not in (None,0):raise SystemExit('REFUSE smoke failed at seed/trace proof: '+str(smoke_seed)+' rc='+str(proof_rc))
     proof_at=dt.datetime.now().astimezone().isoformat();proof_basis='stable_trace_snapshots_while_running' if proof_rc is None else 'clean_natural_exit_with_final_trace';break
   else:
    last_trace_signature=None;stable_trace_polls=0
   if marker_count>1:
    stop_owned_smoke(proc,False);raise SystemExit('REFUSE smoke duplicate effective-seed marker: '+str(smoke_seed))
   if proc.poll() is not None:
    # A clean natural exit freezes stdout and traces, so one exact marker plus
    # a nonempty trace is final evidence even if the three-poll stability gate
    # lost the race. Never accept a nonzero exit as a successful proof.
    if proc.returncode==0 and marker_count==1 and proof_traces:
     proof_at=dt.datetime.now().astimezone().isoformat();proof_basis='clean_natural_exit_with_final_trace';last_trace_signature=trace_signature;break
    raise SystemExit('REFUSE smoke exited before seed/trace proof: '+str(smoke_seed)+' rc='+str(proc.returncode))
   if time.monotonic()-t0>=SMOKE_PROOF_TIMEOUT:
    stop_owned_smoke(proc,False);raise SystemExit('REFUSE smoke proof timeout: '+str(smoke_seed))
   time.sleep(SMOKE_POLL_SECONDS)
  proof_latency=time.monotonic()-t0
  termination=stop_owned_smoke(proc,True);disposition=termination['disposition'];returncode=termination['returncode']
  if disposition not in ('proof_then_terminated','proof_then_killed','proof_then_natural_exit','proof_then_natural_exit_race') or (disposition in ('proof_then_natural_exit','proof_then_natural_exit_race') and returncode!=0):
   raise SystemExit('REFUSE smoke process disposition after proof: '+str(smoke_seed))
 finished_at=dt.datetime.now().astimezone().isoformat()
 marker_count=exact_line_count(stdout_path,marker);traces=nonempty_trace_snapshot(work)
 final_trace_signature=tuple((name,meta['sha256'],meta['bytes']) for name,meta in sorted(traces.items()))
 if marker_count!=1 or not traces or final_trace_signature!=last_trace_signature:raise SystemExit('REFUSE unstable smoke seed/trace proof: '+str(smoke_seed))
 removed_partial_obs=[]
 for obs in sorted(work.glob('*_obs.dat')):
  if not obs.is_file() or obs.is_symlink():raise SystemExit('REFUSE unsafe smoke partial output: '+str(obs))
  removed_partial_obs.append({'name':obs.name,'sha256':sha(obs),'bytes':obs.stat().st_size});obs.unlink()
 if list(work.glob('*_obs.dat')):raise SystemExit('REFUSE smoke partial output remains: '+str(smoke_seed))
 smoke.append({'schema':'actual_solver_bounded_seed_trace_proof_v1','seed':smoke_seed,'effective_minstd_rand0_state':smoke_seed%2147483647 or 1,'command':command,'environment':smoke_identity_env,'cwd':str(work),'pid':proc.pid,'process_group_id':proc.pid,'started_at':started_at,'proof_at':proof_at,'finished_at':finished_at,'proof_basis':proof_basis,'proof_timeout_seconds':SMOKE_PROOF_TIMEOUT,'poll_seconds':SMOKE_POLL_SECONDS,'stable_trace_polls_required':SMOKE_STABLE_POLLS,'stable_trace_polls_observed':stable_trace_polls,'proof_trace_signature':[list(x) for x in last_trace_signature],'proof_latency_seconds':proof_latency,'proof_reached':True,'stdout_seed_marker_count':marker_count,'stdout':{'path':str(stdout_path.relative_to(B)),'sha256':sha(stdout_path),'bytes':stdout_path.stat().st_size},'stderr':{'path':str(stderr_path.relative_to(B)),'sha256':sha(stderr_path),'bytes':stderr_path.stat().st_size},'traces':traces,'termination':termination,'partial_obs_removed':removed_partial_obs,'partial_obs_remaining':0})
common=set(smoke[0]['traces'])&set(smoke[1]['traces'])
different=[name for name in sorted(common) if smoke[0]['traces'][name]['sha256']!=smoke[1]['traces'][name]['sha256']]
common_prefix_evidence={};different_common_prefix=[]
for name in sorted(common):
 line_count=min(smoke[0]['traces'][name]['lines'],smoke[1]['traces'][name]['lines'])
 if line_count<1:continue
 hashes={str(sr['seed']):hash_first_lines(Path(sr['cwd'])/name,line_count) for sr in smoke}
 is_different=len(set(hashes.values()))==2
 common_prefix_evidence[name]={'line_count':line_count,'sha256_by_seed':hashes,'different':is_different}
 if is_different:different_common_prefix.append(name)
if not different_common_prefix:raise SystemExit('REFUSE two true-seed smoke traces have identical same-length common prefixes')
# Atomically establish the batch-local three-file runtime pin set; never touch shared installs.
pins=B/'pinned_solver';pins.mkdir(mode=0o700)
for src,name,mode in ((solver,'Hubbard_sym_testobs_UV.x',0o555),(candidate/'Hubbard_sym_testobs_UV.cc','Hubbard_sym_testobs_UV.cc',0o444),(lib,'libqbasis.so',0o444)):
 dst=pins/name
 with src.open('rb') as fi,dst.open('xb') as fo:shutil.copyfileobj(fi,fo)
 os.chmod(dst,mode)
pin_hashes={n:sha(pins/n) for n in ('Hubbard_sym_testobs_UV.x','Hubbard_sym_testobs_UV.cc','libqbasis.so')}
ledger=''.join(f"{pin_hashes[n]}  pinned_solver/{n}\n" for n in ('Hubbard_sym_testobs_UV.x','Hubbard_sym_testobs_UV.cc','libqbasis.so'))
(B/'BUILT_PIN_SHA256SUMS').write_text(ledger)
compiler=run([GXX,'--version'],env,logs).stdout.splitlines()
receipt={'schema':'fig4_u80v20_true_seed_maxit50000_isolated_build_v2','built_at':dt.datetime.now().astimezone().isoformat(),'batch':str(B),'compiler':str(GXX),'compiler_version':compiler,'platform':platform.platform(),'machine':platform.machine(),'compile_flags':flags,'link_flags':libs,'original_model_sha256':ORIGINAL_MODEL_SHA,'patched_model_sha256':PATCHED_MODEL_SHA,'original_hubbard_sha256':ORIGINAL_HUBBARD_SHA,'patched_hubbard_sha256':PATCHED_HUBBARD_SHA,'runtime_pins':pin_hashes,'effective_changes':['QBASIS_LANCZOS_SEED required and strictly parsed as full decimal uint32 1..4294967295','Lanczos/CG maxit raised from 10000 to 50000'],'true_seed_smoke':{'schema':'actual_solver_bounded_two_seed_proof_v1','passed':True,'bounded_process_end':True,'runs':smoke,'different_trace_files':different,'common_prefix_evidence':common_prefix_evidence,'different_common_prefix_trace_files':different_common_prefix},'commands':logs,'shared_tree_writes':False,'make_install_invoked':False}
(B/'BUILD_RECEIPT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
for p in (B/'BUILT_PIN_SHA256SUMS',B/'BUILD_RECEIPT.json'):os.chmod(p,0o444)
print(json.dumps({'built':True,'batch':str(B),'runtime_pins':pin_hashes},sort_keys=True,indent=2))
