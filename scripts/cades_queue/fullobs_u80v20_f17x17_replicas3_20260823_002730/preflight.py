#!/usr/bin/env /usr/bin/python3.11
import csv,hashlib,json,os,re,subprocess,sys
from pathlib import Path
B=Path(__file__).resolve().parent; SOURCE=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_u80v20_fig4_cnn_20260822_213314'); JOB='F4U80R3'; SOURCE_JOB='5619905'; CANON=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat')
PINS={'Hubbard_sym_testobs_UV.x': 'b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b', 'Hubbard_sym_testobs_UV.cc': 'f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73', 'libqbasis.so': 'be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85'}
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(a):return subprocess.run(a,text=True,capture_output=True)
err=[]
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
if len(rows)!=3:err.append('cardinality='+str(len(rows)))
if len({(r['U'],r['V'],r['kx'],r['ky'],r['canonical_result']) for r in rows})!=1:err.append('not_one_target')
if {r['replica_ordinal'] for r in rows}!={'1','2','3'}:err.append('bad_ordinals')
seeds=[int(r['seed']) for r in rows]; known={int(x) for x in (B/'known_uint32_inventory.txt').read_text().split()}
if len(set(seeds))!=3 or set(seeds)&known or any(not 0<x<2**32 for x in seeds):err.append('seed_gate')
if os.path.lexists(CANON):err.append('canonical_exists')
with (B/'submission.tsv').open(newline='') as f:old=list(csv.DictReader(f,delimiter='\t'))
if old:err.append('submission_nonempty')
for r in rows:
 p=Path(r['script']); rp=Path(r['replica_result'])
 if not p.is_file():err.append('missing_script='+str(p));continue
 t=p.read_text()
 for x in ('#SBATCH -A ccsd','#SBATCH -p burst','#SBATCH -N 1','#SBATCH -n 32','#SBATCH -c 1','#SBATCH -J F4U80R3','#SBATCH --mem=100G','#SBATCH -t 08:00:00'):
  if x not in t:err.append('resource='+p.name+':'+x)
 if re.search('python',t,re.I):err.append('compute_python='+p.name)
 if 'validate_output.sh' not in t or 'canonical became complete; replica skipped' not in t:err.append('guard='+p.name)
 if re.search(r'\b(?:cp|mv|rm|unlink)\b[^\n]*\$\{CANONICAL\}',t):err.append('canonical_write='+p.name)
 if os.path.lexists(rp):err.append('result_exists='+str(rp))
for n,h in PINS.items():
 p=B/'pinned_solver'/n
 if not p.is_file() or sha(p)!=h:err.append('pin='+n)
for line in (B/'PACKAGE_SHA256SUMS').read_text().splitlines():
 if line.strip():
  h,rel=line.split(None,1);p=B/rel.strip()
  if not p.is_file() or sha(p)!=h:err.append('package='+rel.strip())
aud=run(['/usr/bin/python3.11',str(SOURCE/'audit_status.py'),'--batch',str(SOURCE),'--job-name','F4C80V20','--job-name','F4C80V20R','--pin-file','PINNED_SHA256SUMS','--submission-log','repair_submission.tsv','--require-pins','--since','2026-08-22','--expect-targets','25','--expect-per-case','25','--expect-account','ccsd','--expect-partition','burst','--expect-cpus','32','--expect-nodes','1','--expect-memory','100G','--expect-time-limit','08:00:00'])
if aud.returncode or 'TARGETS 25 | COMPLETE=24 RUNNING=1' not in aud.stdout or 'ANOMALIES 0' not in aud.stdout or 'PINS 3/3 MATCH' not in aud.stdout:err.append('source_audit='+aud.stdout+aud.stderr)
q=run(['squeue','-h','-r','-u','9pm','-j',SOURCE_JOB,'-o','%i|%j|%T|%a|%P|%C|%D|%m|%l'])
lines=[x for x in q.stdout.splitlines() if x.strip()]
if q.returncode or len(lines)!=1:err.append('source_job_activity='+q.stdout+q.stderr)
else:
 x=lines[0].split('|')
 if len(x)!=9 or x[0]!=SOURCE_JOB or x[1]!='F4C80V20' or x[2] not in ('RUNNING','COMPLETING') or x[3]!='ccsd' or x[4]!='burst' or x[5]!='32' or x[6]!='1' or x[7]!='100G' or x[8] not in ('8:00:00','08:00:00'):err.append('source_resource='+lines[0])
q2=run(['squeue','-h','-r','-u','9pm','-n',JOB,'-o','%i|%j|%T'])
if q2.returncode or q2.stdout.strip():err.append('replica_activity='+q2.stdout+q2.stderr)
cap=run(['squeue','-h','-r','-u','9pm','-A','ccsd','-o','%i']); used=len([x for x in cap.stdout.splitlines() if x.strip()]) if cap.returncode==0 else 999
if cap.returncode or 150-used<3:err.append('capacity='+str(used)+':'+cap.stderr)
report={'schema':'fig4_u80v20_one_target_three_replicas_preflight_v1','pass':not err,'replicas':len(rows),'target':{'U':80,'V':20,'kx':17,'ky':17,'source_job_id':SOURCE_JOB},'new_seeds':seeds,'known_overinclusive_uint32_count':len(known),'pins_match':3-sum(x.startswith('pin=') for x in err),'ccsd_active':used,'ccsd_headroom':150-used,'source_audit':aud.stdout.strip().splitlines()[:4],'errors':err}
print(json.dumps(report,sort_keys=True,indent=2));raise SystemExit(2 if err else 0)
