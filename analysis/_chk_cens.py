import json, glob, os
from collections import Counter
ROOT=r'E:\n0r53'
both=Counter(); onlynull=Counter(); mid_cens=Counter()
for f in glob.glob(os.path.join(ROOT,'runs','kick','*','*.json')):
    m=f.replace("\\","/").split("/runs/")[1].split("/")[1]
    j=json.load(open(f))
    ca=j.get('censored_at'); bc=j.get('beta_crit')
    if ca is not None and bc is not None: both[m]+=1
    elif ca is not None and bc is None: onlynull[m]+=1
    elif bc is None: mid_cens[m]+=1
print('censored_at + beta_crit written:',dict(both))
print('censored_at + beta_crit null  :',dict(onlynull))
print('beta_crit null w/o censored_at:',dict(mid_cens))
