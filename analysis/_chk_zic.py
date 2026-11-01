import json, glob
f=glob.glob(r'E:\n0r53\runs\zic\*\*.json')[0]
j=json.load(open(f))
print('file keys:', sorted(j.keys()))
for k in j:
    v=j[k]
    if isinstance(v,list) and v: print(k,'list of',type(v[0]),'len',len(v), str(v[0])[:200])
    elif isinstance(v,dict): print(k,'dict keys',list(v.keys())[:15])
    else: print(k,'=',str(v)[:80])
