import json, glob, os, csv
from collections import Counter, defaultdict
ROOT=r'E:\n0r53'
# kick: beta_crit null vs present; censored flag field names
cnull=Counter(); cmid=Counter(); fields=set()
for f in glob.glob(os.path.join(ROOT,'runs','kick','*','*.json')):
    m=f.replace("\\","/").split("/runs/")[1].split("/")[1]
    j=json.load(open(f))
    fields.update(j.keys())
    if j.get('beta_crit') is None: cnull[m]+=1
    else: cmid[m]+=1
    for k in j:
        if 'cens' in k.lower(): print('cens field:',k,j[k])
print('beta_crit null:',dict(cnull))
print('beta_crit set :',dict(cmid))
print('top fields:',sorted(fields))
# probes with censored_at / censored flag inside runs
cflag=Counter()
for f in glob.glob(os.path.join(ROOT,'runs','kick','*','*.json'))[:400]:
    j=json.load(open(f))
    for b,p in (j.get('runs') or {}).items():
        for k in p:
            if 'cens' in k.lower(): cflag[k]+=1
print('probe cens fields:',dict(cflag))
