import json, csv
d=json.load(open(r'E:\n0r53\analysis\horizon_audit.json'))
tot=0
for m,v in d['zic'].items():
    n=v['rec_settled']+v['rec_horizon']+v['committed']+v['censored']
    tot+=n
    print(m.ljust(9),'releases=%d horizon=%d'%(n,v['rec_horizon']))
print('total releases:',tot)
# law hit tags
rows=list(csv.DictReader(open(r'E:\n0r53\analysis\law_table.csv',newline='',encoding='utf-8-sig')))
hz=set()
for m,v in d['zic'].items():
    for h in v['horizon_states']:
        hz.add((m,h['rid'],round(float(h['t_r']),4)))
hits=[r for r in rows if (r['model'],r['rid'],round(float(r['t_r']),4)) in hz]
for r in hits: print(r['model'],r['rid'],r['t_r'],r['tag'],r.get('label_r52'))
