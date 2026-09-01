#!/usr/bin/env /usr/bin/python3.11
import csv,datetime as dt,hashlib,json,os,re,subprocess,sys
from pathlib import Path
B=Path(__file__).resolve().parent;JOB='F4U80R5';CANON=Path('/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(a):return subprocess.run(a,text=True,capture_output=True)
if os.environ.get('F4U80R5_CONFIRM_SUBMIT')!='YES':print('DISARMED: set F4U80R5_CONFIRM_SUBMIT=YES only after reviewing a passing preflight',file=sys.stderr);raise SystemExit(2)
p=run(['/usr/bin/python3.11',str(B/'preflight.py')]);print(p.stdout,end='')
if p.returncode:print(p.stderr,file=sys.stderr);raise SystemExit(p.returncode)
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
header=(B/'submission_header.tsv').read_text()
with (B/'submission.tsv').open('x') as f:f.write(header);f.flush();os.fsync(f.fileno())
for d in ('results','work','locks','logs'):
 x=B/d;x.mkdir(mode=0o700,exist_ok=False)
submitted=[]
for r in rows:
 if os.path.lexists(CANON):print('REFUSE: canonical path appeared',file=sys.stderr);raise SystemExit(4)
 for name in ('F4C80V20','F4C80V20R','F4U80R3'):
  q=run(['squeue','-h','-r','-u','9pm','-n',name,'-o','%i|%j|%T'])
  if q.returncode or q.stdout.strip():print('REFUSE: unexpected exact-name activity '+name+' '+q.stdout+q.stderr,file=sys.stderr);raise SystemExit(5)
 qnew=run(['squeue','-h','-r','-u','9pm','-n',JOB,'-o','%A'])
 active_new={x.strip() for x in qnew.stdout.splitlines() if x.strip()};recorded={x['job_id'] for x in submitted}
 if qnew.returncode or not active_new.issubset(recorded):print('REFUSE: unmapped new-name activity '+qnew.stdout+qnew.stderr,file=sys.stderr);raise SystemExit(9)
 cap=run(['squeue','-h','-r','-u','9pm','-o','%i']);used=len([x for x in cap.stdout.splitlines() if x.strip()]) if cap.returncode==0 else 999
 if cap.returncode or used>=150:print('REFUSE: total user job capacity unavailable',file=sys.stderr);raise SystemExit(6)
 s=run(['sbatch','-A','ccsd',r['script']])
 if s.returncode:print('SBATCH_FAILED '+s.stderr,file=sys.stderr);raise SystemExit(7)
 m=re.fullmatch(r'Submitted batch job\s+(\d+)\s*',s.stdout)
 if not m:print('UNPARSED_SBATCH '+s.stdout,file=sys.stderr);raise SystemExit(8)
 jid=m.group(1);now=dt.datetime.now().astimezone().isoformat()
 fields=[now,'ccsd',jid,r['replica_index'],r['replica_ordinal'],r['source_index'],r['source_job_id'],r['U'],r['V'],r['kx'],r['ky'],r['seed'],r['script'],r['replica_result']]
 with (B/'submission.tsv').open('a') as f:f.write('\t'.join(fields)+'\n');f.flush();os.fsync(f.fileno())
 submitted.append({'replica_index':r['replica_index'],'replica_ordinal':r['replica_ordinal'],'seed':r['seed'],'job_id':jid})
receipt={'schema':'fig4_u80v20_five_additional_replicas_submission_v1','submitted_at':dt.datetime.now().astimezone().isoformat(),'batch':str(B),'job_name':JOB,'source_job_id':'5619905','count':len(submitted),'jobs':submitted,'manifest_sha256':sha(B/'replica_manifest.tsv'),'package_sha256s_sha256':sha(B/'PACKAGE_SHA256SUMS'),'build_receipt_sha256':sha(B/'BUILD_RECEIPT.json'),'built_pin_ledger_sha256':sha(B/'BUILT_PIN_SHA256SUMS')}
with (B/'submission_receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
(B/'SUBMISSION_SHA256SUMS').write_text(f"{sha(B/'submission.tsv')}  submission.tsv\n{sha(B/'submission_receipt.json')}  submission_receipt.json\n")
for x in ('submission.tsv','submission_receipt.json','SUBMISSION_SHA256SUMS'):os.chmod(B/x,0o444)
print('SUBMITTED count=5 job_name=F4U80R5 job_ids='+','.join(x['job_id'] for x in submitted))
