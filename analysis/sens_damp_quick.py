import json, glob, os
import numpy as np

base = r'E:\n0r53\runs'


def load(phase):
    out = {}
    for p in glob.glob(os.path.join(base, phase, 'SMF4B', '*.json')):
        d = json.load(open(p))
        out[os.path.basename(p)] = d
    return out


phases = {'kick': 1.0, 'kick_damp05': 0.5, 'kick_damp20': 2.0, 'kick_undamped': 0.0}
D = {ph: load(ph) for ph in phases}
sens_keys = set(D['kick_damp05']) | set(D['kick_damp20']) | set(load('kick_dt2'))
sens_keys = {k for k in sens_keys if k.startswith('FF')}
print('sens states:', len(sens_keys))
rows = []
for k in sorted(sens_keys):
    r = {'key': k}
    for ph, s in phases.items():
        d = D[ph].get(k)
        r[s] = d.get('beta_crit') if d else None
    rows.append(r)
ok = [r for r in rows if all(r[s] is not None for s in (0.0, 0.5, 1.0, 2.0))]
print(f'{len(ok)} states with all four beta_crit')
for s in (0.0, 0.5, 1.0, 2.0):
    b2 = np.array([r[s] ** 2 for r in ok])
    print(f's={s}: median beta^2 = {np.median(b2):.4f}  IQR [{np.percentile(b2, 25):.4f},{np.percentile(b2, 75):.4f}]')
res = []
for r in ok:
    s = np.array([0.0, 0.5, 1.0, 2.0])
    y = np.array([r[s_] for s_ in s]) ** 2
    a, b = np.polyfit(s, y, 1)
    res.append((a, b, y[0], b / y[0] if y[0] > 0 else np.nan))
res = np.array(res)
print('per-state fit beta^2 = a*s + b:')
print('  slope a      median %.4f  p10 %.4f  p90 %.4f' % (np.median(res[:, 0]), np.percentile(res[:, 0], 10), np.percentile(res[:, 0], 90)))
print('  intercept b  median %.4f' % np.median(res[:, 1]))
print('  meas s=0     median %.4f' % np.median(res[:, 2]))
print('  ratio b/meas median %.3f  p10 %.3f  p90 %.3f' % (np.nanmedian(res[:, 3]), np.nanpercentile(res[:, 3], 10), np.nanpercentile(res[:, 3], 90)))
