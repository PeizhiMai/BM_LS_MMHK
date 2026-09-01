#!/usr/bin/env /usr/bin/python3.11
import math,re
from collections import Counter
from pathlib import Path
NUMERIC=re.compile(r'^[-+]?(([0-9]+([.][0-9]*)?)|([.][0-9]+))([eE][-+]?[0-9]+)?$')
REQ=('Lx','Ly','tp','U','V','E0','<nn_NN>','<delta_n_delta_n_NN>','<Kinetic_NN_per_site>','<Kinetic_NNN_per_site>','<Kinetic_per_site>','<C1_NN>','<ni_upni_dn>','<Sc_pipi>','<mCDW2_pipi>')
def close(a,b,tol=1e-10):return abs(a-b)<=tol*max(1.0,abs(b))
def validate(path,U,V):
 p=Path(path);errors=[];residuals={}
 if not p.is_file() or p.is_symlink():return ['missing_or_not_regular'],residuals
 vals={};counts=Counter()
 try:text=p.read_text(errors='replace')
 except OSError as e:return ['read='+str(e)],residuals
 for line in text.splitlines():
  x=line.split(None,1)
  if len(x)==2:
   counts[x[0]]+=1
   if counts[x[0]]==1:vals[x[0]]=x[1].strip()
 if counts['status']!=1 or vals.get('status')!='COMPLETE':errors.append('missing_or_nonunique_COMPLETE')
 if counts['Q']!=1 or vals.get('Q','').replace(' ','')!='0,0':errors.append('metadata_or_nonunique_Q='+repr(vals.get('Q')))
 bad_counts=[k for k in REQ if counts[k]!=1]
 if bad_counts:return errors+['key_count='+','.join(f'{k}:{counts[k]}' for k in bad_counts)],residuals
 try:
  if any(not NUMERIC.fullmatch(vals[k]) for k in REQ):return errors+['nonnumeric'],residuals
  obs={k:float(vals[k]) for k in REQ}
  if any(not math.isfinite(x) or abs(x)>1e100 for x in obs.values()):errors.append('nonfinite_or_unbounded')
  for k,a,e in [('Lx',obs['Lx'],4),('Ly',obs['Ly'],4),('tp',obs['tp'],0),('U',obs['U'],float(U)),('V',obs['V'],float(V))]:
   if not close(a,e):errors.append(f'metadata_{k}={a:.17g}_expected={e:.17g}')
  residuals={'energy_per_site':obs['E0']/16-(obs['<Kinetic_per_site>']+obs['U']*obs['<ni_upni_dn>']+2*obs['V']*obs['<nn_NN>']),'connected_density':obs['<delta_n_delta_n_NN>']-(obs['<nn_NN>']-1),'kinetic_sum':obs['<Kinetic_per_site>']-(obs['<Kinetic_NN_per_site>']+obs['<Kinetic_NNN_per_site>']),'charge_Sc_over_N':obs['<mCDW2_pipi>']-obs['<Sc_pipi>']/16}
  for k,v in residuals.items():
   if not math.isfinite(v) or abs(v)>1e-8:errors.append(f'identity_{k}={v:.6e}')
  c=obs['<C1_NN>'];D=obs['<ni_upni_dn>'];mc=obs['<mCDW2_pipi>']
  if not -0.75000001<=c<=0.25000001:errors.append(f'C1_NN_out_of_bounds={c:.17g}')
  if not 0<=D<=1 or not 0<=mc<=1:errors.append('physical_bounds')
 except (ValueError,TypeError,OverflowError) as e:errors.append('numeric_parse='+str(e))
 return errors,residuals
