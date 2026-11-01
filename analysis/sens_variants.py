"""Sensitivity-variant analysis on the paired 4B FF subset.

Variants (kick_*): damp05/damp20 (Rayleigh x0.5/x2 at release), dt2 (halved
analysis step), theta010/theta020 (collapse limit 0.10/0.20).  Reference is
`kick` (damped) and `kick_undamped` (s=0).  For the theta variants the barrier
is recomputed from the stored push curve to the corresponding drift surface.
Writes sens_variants.json and prints summary stats.
"""
import json, glob, os
import numpy as np

BASE = r'E:\n0r53\runs'
MODEL = 'SMF4B'
THETA_REF = 0.15


def load(phase):
    return {os.path.basename(p): json.load(open(p))
            for p in glob.glob(os.path.join(BASE, phase, MODEL, '*.json'))}


def load_push():
    """release-key -> push record (curve truncated version is fine for W(theta))."""
    out = {}
    for p in glob.glob(os.path.join(BASE, 'push', MODEL, '*.json')):
        d = json.load(open(p))
        out[os.path.basename(p)] = d
    return out


def w_to_sdr(curve, sdr_lim, w_ref):
    """Accumulated external work at first crossing of peak-storey-drift sdr_lim.
    Returns w_ref (reference barrier) if the surface is never reached (edge first)."""
    w_prev, s_prev = 0.0, 0.0
    for pt in curve:
        # curve entries: [droof, lam, sdr_max, W]  (see driver53.barrier)
        s = pt[2]
        w = pt[3]
        if s >= sdr_lim and s > s_prev:
            f = (sdr_lim - s_prev) / (s - s_prev)
            return w_prev + f * (w - w_prev)
        w_prev, s_prev = w, s
    return w_ref


sens = {k for k in load('kick_damp05')}
sens &= set(load('kick_damp20'))
sens &= set(load('kick_dt2'))
sens &= set(load('kick_theta010'))
sens &= set(load('kick_theta020'))
sens &= set(load('kick'))
sens &= set(load('kick_undamped'))
sens &= set(load_push())
sens = sorted(k for k in sens if k.startswith('FF'))
print(f'{len(sens)} paired states')

D = {ph: load(ph) for ph in
     ('kick', 'kick_undamped', 'kick_damp05', 'kick_damp20', 'kick_dt2',
      'kick_theta010', 'kick_theta020')}
P = load_push()

rows = []
for k in sens:
    r = {'key': k}
    for ph in D:
        r[ph] = D[ph][k].get('beta_crit')
    d = P[k]
    curve = d.get('curve') or []
    w_edge = d.get('W_barrier')          # work to zero-resistance edge (or None)
    w15 = w_to_sdr(curve, THETA_REF, w_edge)
    r['Wc'] = {'0.10': w_to_sdr(curve, 0.10, w_edge),
               '0.15': w15,
               '0.20': w_to_sdr(curve, 0.20, w_edge)}
    r['edge_first'] = (w_edge is not None and
                       not any(pt[2] >= THETA_REF for pt in curve))
    snap = (D['kick'][k].get('runs', {}).get('1.00000') or {})
    r['ke'] = None
    for v in (D['kick'][k].get('runs') or {}).values():
        sr = v.get('snapshot_release') or {}
        if sr.get('ke') is not None:
            r['ke'] = sr['ke']
            break
    rows.append(r)

ok = [r for r in rows if all(r[p] is not None for p in
                             ('kick', 'kick_undamped', 'kick_dt2'))]
print(f'{len(ok)} with core variants')

# --- dt2 robustness -------------------------------------------------------
db = np.array([r['kick_dt2'] - r['kick'] for r in ok])
print('dt2: median |dbeta|=%.4f  max |dbeta|=%.4f' %
      (np.median(np.abs(db)), np.max(np.abs(db))))

# --- damping affinity -------------------------------------------------------
okd = [r for r in ok if r['kick_damp05'] is not None and r['kick_damp20'] is not None]
s = np.array([0.0, 0.5, 1.0, 2.0])
b2 = np.array([[r['kick_undamped'], r['kick_damp05'], r['kick'], r['kick_damp20']]
               for r in okd]) ** 2
coef = np.array([np.polyfit(s, y, 1) for y in b2])
print('damp: median beta^2 at s=0/0.5/1/2 = ' +
      ' '.join('%.4f' % np.median(b2[:, i]) for i in range(4)))
print('      intercept/meas(s=0) median %.3f  p10 %.3f  p90 %.3f' %
      (np.median(coef[:, 1] / b2[:, 0]),
       np.percentile(coef[:, 1] / b2[:, 0], 10),
       np.percentile(coef[:, 1] / b2[:, 0], 90)))

# --- theta variants -------------------------------------------------------
okt = [r for r in rows if r['kick_theta010'] is not None
       and r['kick_theta020'] is not None
       and r['kick'] is not None and r['kick_undamped'] is not None
       and r['ke'] and all(r['Wc'][t] for t in ('0.10', '0.15', '0.20'))]
print(f'{len(okt)} with theta variants + barrier + KE')
for lab, ph, th in (('th=0.10', 'kick_theta010', '0.10'),
                    ('th=0.15', 'kick', '0.15'),
                    ('th=0.20', 'kick_theta020', '0.20')):
    cd = np.array([r[ph] ** 2 * r['ke'] / r['Wc'][th] for r in okt])
    cu = np.array([(r['kick_undamped'] ** 2) * r['ke'] / r['Wc'][th]
                   for r in okt])
    print('%s: c=%.3f [%.3f,%.3f]   c0=%.3f [%.3f,%.3f]' %
          (lab, np.median(cd), np.percentile(cd, 25), np.percentile(cd, 75),
           np.median(cu), np.percentile(cu, 25), np.percentile(cu, 75)))

json.dump({'n': len(sens), 'rows': rows},
          open(r'E:\n0r53\analysis\sens_variants.json', 'w'), indent=1)
print('wrote sens_variants.json')
