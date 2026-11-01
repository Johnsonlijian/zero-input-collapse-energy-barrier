import json
d=json.load(open(r'E:\n0r53\analysis\ews_control.json'))
for m,v in sorted(d['per_model'].items()):
    print(m.ljust(9),'best=%s'%v['best_ews'],'gapCI=[%d,%d]'%(100*v['auc_gap_ci95'][0],100*v['auc_gap_ci95'][1]),
          'bestCI=[%.2f,%.2f]'%(v['best_auc_ci95'][0],v['best_auc_ci95'][1]),'nev=%d'%v['n_events'])
