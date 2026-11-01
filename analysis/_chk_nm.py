import json
d=json.load(open(r'E:\n0r53\analysis\aftershock_analysis.json'))
for m in sorted(d):
    nm=(d[m].get('summary') or {}).get('ms_no_mirror')
    if nm:
        pr=nm['prediction_log_rmse']; rw=nm.get('R_over_w')
        print(m.ljust(9),'n=%d'%nm['n'],'R/w=%.2f'%(rw if not isinstance(rw,dict) else rw.get('median',0)),
              'w0=%.3f wfit=%.3f res=%.3f'%(pr['w_zero_param'],pr['w_fitted_cv'],pr['res_fitted_cv']))
