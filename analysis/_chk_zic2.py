import json, glob
f=glob.glob(r'E:\n0r53\runs\zic\*\*.json')[0]
j=json.load(open(f))
r=j['releases']['22.9100']
print(type(r), sorted(r.keys()) if isinstance(r,dict) else r)
print({k:r[k] for k in r if k in ('committed','settled_at','t_r','status','label','t_coll')})
# kick schema
f2=glob.glob(r'E:\n0r53\runs\kick_undamped\*\*.json')[0]
k=json.load(open(f2))
print('kick keys:',sorted(k.keys())[:25])
for kk in k:
    v=k[kk]
    if isinstance(v,list) and v and isinstance(v[0],dict): print('  list:',kk,len(v),sorted(v[0].keys())[:15])
    elif isinstance(v,dict): print('  dict:',kk,list(v.keys())[:12])
