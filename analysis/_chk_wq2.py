import json
d=json.load(open(r'E:\n0r53\analysis\aftershock_analysis.json'))
print('=== ms_sub.own.within_q (A12 subset, what macros emit) ===')
for m in sorted(d):
    s=d[m].get('summary',{})
    own=(s.get('ms_sub') or {}).get('own') or {}
    wq=own.get('within_q')
    if not wq or not wq.get('rho_signed'): print(m,'none'); continue
    rs=wq['rho_signed']; ci=wq['ci95']
    print(m.ljust(9),'n=%s'%own.get('n'),'w=%.3f res=%.3f diffCI=[%.3f,%.3f]'%(rs['w'],rs['res'],ci['w_minus_res'][0],ci['w_minus_res'][1]))
print('=== ms_within_q (all ms states) ===')
for m in sorted(d):
    s=d[m].get('summary',{})
    wq=s.get('ms_within_q')
    if wq and wq.get('rho_signed'):
        rs=wq['rho_signed']; ci=wq['ci95']
        print(m.ljust(9),'w=%.3f res=%.3f diffCI=[%.3f,%.3f]'%(rs['w'],rs['res'],ci['w_minus_res'][0],ci['w_minus_res'][1]))
