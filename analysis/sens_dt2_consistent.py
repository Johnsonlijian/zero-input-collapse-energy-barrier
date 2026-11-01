"""Consistent dt2 check: numerator AND denominator on the dt/2 trajectory.
For each sens state, compare  beta^2*KE / Wc  computed under the reference
step vs under the halved step (release state, snapshot KE and barrier all
reproduced under dt/2 by push_dt2)."""
import json, glob, os
import numpy as np

BASE = r'E:\n0r53\runs'
M = 'SMF4B'
TH = 0.15


def load(phase):
    return {os.path.basename(p): json.load(open(p))
            for p in glob.glob(os.path.join(BASE, phase, M, '*.json'))}


def w_to_sdr(curve, lim, w_edge):
    wp, sp = 0.0, 0.0
    for pt in curve:
        s, w = pt[2], pt[3]
        if s >= lim and s > sp:
            return wp + (lim - sp) / (s - sp) * (w - wp)
        wp, sp = w, s
    return w_edge


K, K2 = load('kick'), load('kick_dt2')
P, P2 = load('push'), load('push_dt2')
sens = sorted(set(K) & set(K2) & set(P) & set(P2))
print(len(sens), 'paired')

rows = []
for k in sens:
    d2, d1 = K2[k], K[k]
    p2, p1 = P2[k], P[k]
    bc1, bc2 = d1.get('beta_crit'), d2.get('beta_crit')
    if bc1 is None or bc2 is None:
        continue
    def ke_of(p_rec, k_rec):
        v = (p_rec.get('release_snapshot') or {}).get('ke')
        if v is None:
            v = p_rec.get('ke_reproduced')
        if v is None:
            for r in (k_rec.get('runs') or {}).values():
                sr = r.get('snapshot_release') or {}
                if sr.get('ke') is not None:
                    v = sr['ke']
                    break
        return v
    ke1 = ke_of(p1, d1)
    ke2 = ke_of(p2, d2)
    w1 = w_to_sdr(p1.get('curve') or [], TH, p1.get('W_barrier'))
    w2 = w_to_sdr(p2.get('curve') or [], TH, p2.get('W_barrier'))
    if not all(x for x in (ke1, ke2, w1, w2)) or min(w1, w2) <= 0:
        continue
    rows.append(dict(key=k,
                     c_ref=bc1 ** 2 * ke1 / w1,
                     c_dt2=bc2 ** 2 * ke2 / w2,
                     ke_ratio=ke2 / ke1,
                     w_ratio=w2 / w1,
                     b2_ratio=bc2 ** 2 / bc1 ** 2))

n = len(rows)
print(n, 'usable')
for f in ('c_ref', 'c_dt2', 'ke_ratio', 'w_ratio', 'b2_ratio'):
    v = np.array([r[f] for r in rows])
    print('%-9s median %.4f  IQR [%.4f, %.4f]' % (f, np.median(v),
          np.percentile(v, 25), np.percentile(v, 75)))
rat = np.array([r['c_dt2'] / r['c_ref'] for r in rows])
print('c_dt2/c_ref  median %.3f  p10 %.3f  p90 %.3f' % (
    np.median(rat), np.percentile(rat, 10), np.percentile(rat, 90)))
json.dump(rows, open(r'E:\n0r53\analysis\sens_dt2_consistent.json', 'w'), indent=1)
