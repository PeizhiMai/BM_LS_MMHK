#!/usr/bin/env /usr/bin/python3.11
import argparse,csv,hashlib,json,os,re,subprocess
from collections import Counter
from pathlib import Path
from validate_output import validate
B=Path(__file__).resolve().parent;JOB='F4U80R3';SOURCE_JOB='5619905';PINS={'Hubbard_sym_testobs_UV.x': 'b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b', 'Hubbard_sym_testobs_UV.cc': 'f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73', 'libqbasis.so': 'be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85'}
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def run(a):return subprocess.run(a,text=True,capture_output=True)
def complete(p):
 try:return p.is_file() and re.search(r'^status\s+COMPLETE$',p.read_text(errors='replace'),re.M) is not None
 except OSError:return False
ap=argparse.ArgumentParser();ap.add_argument('--json',action='store_true');a=ap.parse_args();an=[]
with (B/'replica_manifest.tsv').open(newline='') as f:rows=list(csv.DictReader(f,delimiter='\t'))
ledger={}
with (B/'submission.tsv').open(newline='') as f:
 for r in csv.DictReader(f,delimiter='\t'):ledger[r['replica_index']]=r
if len(rows)!=3 or len({r['seed'] for r in rows})!=3:an.append('cardinality_or_seed')
q=run(['squeue','-h','-r','-u','9pm','-n',JOB,'-o','%i|%j|%T|%a|%P|%C|%D|%m|%l']);active={}
if q.returncode:an.append('squeue='+q.stderr)
for line in q.stdout.splitlines():
 x=line.split('|')
 if len(x)!=9:an.append('squeue_line='+line);continue
 active[x[0]]=dict(zip(('job_name','state','account','partition','cpus','nodes','memory','time_limit'),x[1:]))
known={v['job_id'] for v in ledger.values()}
for jid,r in active.items():
 if jid not in known:an.append('unmapped='+jid)
 for k,e in [('job_name',(JOB,)),('account',('ccsd',)),('partition',('burst',)),('cpus',('32',)),('nodes',('1',)),('memory',('100G',)),('time_limit',('8:00:00','08:00:00'))]:
  if r[k] not in e:an.append(f'resource_{jid}_{k}={r[k]}')
ids=list(known);terminal={}
if ids:
 s=run(['sacct','-X','-n','-P','-j',','.join(ids),'--format=JobIDRaw,JobName,Account,Partition,State,ExitCode,Elapsed,Timelimit,AllocCPUS,NNodes,ReqMem'])
 if s.returncode:an.append('sacct='+s.stderr)
 else:
  for line in s.stdout.splitlines():
   x=line.split('|')
   if len(x)>=11 and x[0] in ids:terminal[x[0]]=dict(zip(('job_name','account','partition','state','exit_code','elapsed','time_limit','cpus','nodes','memory'),x[1:11]))
pins=[]
for n,e in PINS.items():
 p=B/'pinned_solver'/n;act=sha(p) if p.is_file() else '';pins.append({'file':n,'expected':e,'actual':act,'match':act==e})
 if act!=e:an.append('pin='+n)
for fn in ('PACKAGE_SHA256SUMS','SUBMISSION_SHA256SUMS'):
 p=B/fn
 if p.is_file():
  for line in p.read_text().splitlines():
   if line.strip():
    h,rel=line.split(None,1);x=B/rel.strip()
    if not x.is_file() or sha(x)!=h:an.append(fn+':'+rel.strip())
 elif fn=='PACKAGE_SHA256SUMS':an.append('missing_package')
counts=Counter();details=[]
for r in rows:
 err,res=validate(r['replica_result'],r['U'],r['V']);jid=ledger.get(r['replica_index'],{}).get('job_id','');rp=Path(r['replica_result']);cp=Path(r['canonical_result'])
 if rp.exists():st='COMPLETE' if not err else 'INVALID'
 elif jid in active:st=active[jid]['state']
 elif jid in terminal:
  x=terminal[jid]['state'].split()[0].split('+')[0];st='SKIPPED_CANONICAL' if x=='COMPLETED' and complete(cp) else ('COMPLETED_NO_OUTPUT' if x=='COMPLETED' else x)
 elif jid:st='SUBMITTED_UNKNOWN'
 else:st='UNSUBMITTED'
 counts[st]+=1
 if rp.exists() and err:an.append('invalid='+str(rp)+':'+','.join(err))
 details.append({'replica_index':r['replica_index'],'replica_ordinal':r['replica_ordinal'],'seed':r['seed'],'job_id':jid,'status':st,'validation_errors':err,'identity_residuals':res,'canonical_exists':os.path.lexists(cp),'canonical_complete':complete(cp),'result':str(rp)})
src=run(['squeue','-h','-r','-u','9pm','-j',SOURCE_JOB,'-o','%i|%j|%T|%M|%l'])
report={'schema':'fig4_u80v20_one_target_three_replicas_monitor_v1','batch':str(B),'job_name':JOB,'count':3,'target':{'U':80,'V':20,'kx':17,'ky':17,'source_job_id':SOURCE_JOB},'counts':dict(sorted(counts.items())),'pins':pins,'anomalies':an,'source_active':src.stdout.strip().splitlines(),'details':details,'read_only':True}
print(json.dumps(report,sort_keys=True,indent=2) if a.json else json.dumps(report,sort_keys=True));raise SystemExit(2 if an else 0)
