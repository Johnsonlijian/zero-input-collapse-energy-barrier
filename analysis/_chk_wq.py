import json
d=json.load(open(r'E:\n0r53\analysis\aftershock_analysis.json'))
for m in sorted(d):
    s=d[m].get('summary',{})
    wq=s.get('ms_within_q')
    if not wq: continue
    rs=wq['rho_signed']
    dr=wq.get('diff_ci95') or wq.get('w_minus_res') or wq.get('diff')
    print(m.ljust(9), 'w=%.3f res=%.3f  w-res=%+.3f'%(rs['w'],rs['res'],rs['w']-rs['res']), 'keys:', [k for k in wq if k not in ('rho_signed','ci95')])
    for k in wq:
        if k not in ('rho_signed','ci95'): print('    ',k,str(wq[k])[:140])
