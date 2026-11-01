"""Follow-up: distribution-level dt2 check + theta010 diagnosis."""
import json, glob, os
import numpy as np

BASE = r'E:\n0r53\runs'
MODEL = 'SMF4B'


def load(phase):
    return {os.path.basename(p): json.load(open(p))
            for p in glob.glob(os.path.join(BASE, phase, MODEL, '*.json'))}


K = load('kick'); D2 = load('kick_dt2'); T10 = load('kick_theta010')
T20 = load('kick_theta020')
sens = sorted(set(D2) & set(K))
print(f'{len(sens)} dt2-paired')

# distribution comparison of beta^2 and label agreement at beta=1
b2 = np.array([K[k].get('beta_crit') for k in sens], dtype=float)
b2h = np.array([D2[k].get('beta_crit') for k in sens], dtype=float)
m = ~np.isnan(b2) & ~np.isnan(b2h)
print('dt2 paired:', m.sum())
print('  beta^2 median  ref %.4f  dt/2 %.4f' % (np.median(b2[m] ** 2), np.median(b2h[m] ** 2)))
print('  beta^2 IQR     ref [%.4f,%.4f]  dt/2 [%.4f,%.4f]' % (np.percentile(b2[m]**2,25), np.percentile(b2[m]**2,75), np.percentile(b2h[m]**2,25), np.percentile(b2h[m]**2,75)))
print('  median ratio dt2/ref %.3f' % np.median((b2h[m]/b2[m])**2))
# beta=1 label agreement
agree = sum((K[k].get('label_beta1') == D2[k].get('label_beta1')) for k in sens)
print('  beta=1 label agreement: %d/%d' % (agree, len(sens)))
flips = [(k, K[k].get('label_beta1'), D2[k].get('label_beta1')) for k in sens
         if K[k].get('label_beta1') != D2[k].get('label_beta1')]
for f in flips:
    print('   flip:', f)

# theta010: are release drifts already past 0.10?
n_past = 0
n_tot = 0
for k in sorted(set(T10) & set(K)):
    d = T10[k]
    sr = None
    for v in (d.get('runs') or {}).values():
        s0 = v.get('snapshot_release') or {}
        if s0.get('sdr') is not None:
            sr = s0['sdr']; break
    if sr is not None:
        n_tot += 1
        if max(abs(x) for x in sr) >= 0.10:
            n_past += 1
print('theta010: %d/%d states released with max|sdr|>=0.10 (degenerate)' % (n_past, n_tot))

# theta020: is beta_crit identical to reference kick?
same = sum(1 for k in set(T20) & set(K)
           if T20[k].get('beta_crit') == K[k].get('beta_crit'))
n20 = len(set(T20) & set(K))
print('theta020: beta_crit identical to th=0.15 in %d/%d states' % (same, n20))
