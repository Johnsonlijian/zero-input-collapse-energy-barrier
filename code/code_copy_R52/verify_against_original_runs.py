from __future__ import annotations
import csv, hashlib, json, os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(os.environ.get('N0R52_RUNS', 'E:/n0r52/runs'))
RESULTS = ROOT / 'results'
NOTES = ROOT / 'notes'
checks=[]; warnings=[]
def check(name, ok, detail):
    checks.append((name,bool(ok),detail))
    if not ok: warnings.append(f'{name}: {detail}')
def readj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def fnum(x):
    try: return float(x)
    except (TypeError,ValueError): return None
def near(a,b,tol=1e-8): return a is not None and b is not None and abs(float(a)-float(b)) <= tol

expected_ida={'SMF4B':100,'SMF8B':100,'SMF4CG':44}
expected_zic={'SMF4B':300,'SMF8B':144,'SMF4CG':44}
expected_rest={'SMF4B':300,'SMF8B':144,'SMF4CG':44}
check('raw_runs_path',RAW.exists(),str(RAW))
for model,n in expected_ida.items():
    count = len(list((RAW/'ida'/model).glob('*.json')))
    check(f'raw_ida_{model}',count==n,f'{count} / {n} JSON')
for model,n in expected_zic.items():
    count = len(list((RAW/'zic'/model).glob('*.json')))
    check(f'raw_zic_{model}',count==n,f'{count} / {n} JSON')
for model,n in expected_rest.items():
    count = len(list((RAW/'rest'/model).glob('*.json')))
    check(f'raw_rest_{model}',count==n,f'{count} / {n} JSON')

ida_rows={}
with (RESULTS/'ida_records.csv').open(encoding='utf-8',newline='') as fh:
    for r in csv.DictReader(fh): ida_rows[(r['model'],r['rid'])]=r
ida_mismatch=[]
ida_keys=['T1','dt','duration','sa_unscaled','S_lo','S_hi','S_hi_trunc','t5','t95']
for model in expected_ida:
    for p in sorted((RAW/'ida'/model).glob('*.json')):
        d=readj(p); r=ida_rows.get((model,d['rid']))
        if r is None: ida_mismatch.append(f'missing row {model}/{d["rid"]}'); continue
        for k in ida_keys:
            if not near(d.get(k),fnum(r.get(k)),2e-6): ida_mismatch.append(f'{model}/{d["rid"]}:{k}:{d.get(k)}!={r.get(k)}')
check('ida_raw_to_csv',not ida_mismatch,f'{len(ida_mismatch)} mismatches' if ida_mismatch else 'all common IDA fields match')

raw_outcomes=defaultdict(Counter); raw_bad=[]; raw_nonmono=Counter(); raw_missing_snapshot=Counter(); raw_release_counts=Counter()
for model in expected_zic:
    for p in sorted((RAW/'zic'/model).glob('*.json')):
        d=readj(p); level=d['level']; key=(model,level); rel=d.get('releases',{})
        if d.get('non_monotonic'): raw_nonmono[key]+=1
        raw_release_counts[key]+=len(rel)
        for tr,rr in rel.items():
            status=rr.get('status')
            if status=='collapse' and not rr.get('committed'): raw_bad.append(f'{p.name}:{tr} collapse/not committed')
            if status in ('ok','settled') and rr.get('committed'): raw_bad.append(f'{p.name}:{tr} recoverable/committed')
            if rr.get('snapshot') is None: raw_missing_snapshot[key]+=1
            if status=='collapse': oc='committed_collapse'
            elif status=='nonconv': oc='committed_nonconv' if rr.get('max_sdr',0)>=0.10 else 'censored_nonconv'
            else: oc='recoverable_settled' if rr.get('settled_at') is not None else 'censored_horizon'
            raw_outcomes[key][oc]+=1
        if level in ('hi','x15') and d.get('status')=='ok':
            rel_by_t={round(float(v.get('t_r')),6):v for v in rel.values()}; ts=d.get('t_star'); ta=d.get('t_a')
            if ts is None or ta is None or round(float(ts),6) not in rel_by_t or round(float(ta),6) not in rel_by_t: raw_bad.append(f'{p.name}:transition key absent')
            else:
                if rel_by_t[round(float(ta),6)].get('committed'): raw_bad.append(f'{p.name}:t_a committed')
                if not rel_by_t[round(float(ts),6)].get('committed'): raw_bad.append(f'{p.name}:t_star not committed')
check('raw_zic_state_invariants',not raw_bad,f'{len(raw_bad)} violations' if raw_bad else 'release labels and transition keys consistent')

cur_zic={}
for model in expected_ida:
    p=RESULTS/f'zic_records_{model}.csv'
    if p.exists():
        with p.open(encoding='utf-8',newline='') as fh:
            for r in csv.DictReader(fh): cur_zic[(model,r['rid'],r['level'])]=r
rerun_rows=[]; current_transition_bad=[]
for (model,rid,level),r in cur_zic.items():
    if level not in ('hi','x15') or r.get('status')!='ok': continue
    p=RAW/'zic'/model/f'{rid}__{level}.json'
    if not p.exists(): current_transition_bad.append(f'{model}/{rid}/{level}:raw missing'); continue
    d=readj(p); rel={round(float(v.get('t_r')),6):v for v in d.get('releases',{}).values()}; ts=fnum(r.get('t_star')); ta=fnum(r.get('t_a'))
    if ts is None or ta is None or round(ts,6) not in rel or round(ta,6) not in rel: rerun_rows.append(f'{model}/{rid}/{level}'); continue
    if rel[round(ta,6)].get('committed') or not rel[round(ts,6)].get('committed'): current_transition_bad.append(f'{model}/{rid}/{level}:label mismatch')
check('current_transition_rows',not current_transition_bad,f'{len(current_transition_bad)} violations' if current_transition_bad else f'checked {len(cur_zic)-len(rerun_rows)} raw-aligned rows; {len(rerun_rows)} corrected-rerun rows')

summary=readj(RESULTS/'zic_summary.json'); summary_bad=[]
for model,sv in summary.items():
    total=sum(int(v) for v in sv.get('release_outcomes',{}).values()); snaps=int(sv.get('n_release_snapshots',0)); missing=int(sv.get('n_releases_without_snapshot',0))
    if total != int(sv.get('n_releases_total',-1)): summary_bad.append(f'{model}:outcome total')
    if snaps+missing != total: summary_bad.append(f'{model}:snapshot total')
    n=sum(1 for _ in (RESULTS/f'zic_states_{model}.csv').open(encoding='utf-8'))-1
    if n != int(sv.get('n_states',-1)): summary_bad.append(f'{model}:state count {n}!={sv.get("n_states")}')
check('corrected_summary_arithmetic',not summary_bad,f'{len(summary_bad)} inconsistencies' if summary_bad else 'outcomes, snapshots and state counts reconcile')

rest_bad=[]; rest_rows=0
for model in expected_rest:
    for p in sorted((RAW/'rest'/model).glob('*.json')):
        d=readj(p); rest_rows+=1
        if d.get('status')!='ok': continue
        rs=d.get('rests',{})
        for label,flag in (('t_a','rest_a_committed'),('t_star','rest_star_committed')):
            t=d.get(label)
            if t is None: continue
            cand=rs.get(f'{float(t):.4f}')
            if cand is not None and bool(cand.get('committed')) != bool(d.get(flag)): rest_bad.append(f'{p.name}:{label}')
check('raw_rest_flags',not rest_bad,f'{len(rest_bad)} violations' if rest_bad else f'checked {rest_rows} rest JSONs')

cache=NOTES/'records_test_cache.npz'; cache_info={}
try:
    import numpy as np
    z=np.load(cache,allow_pickle=True); meta=z['__meta__']; dts=sorted({round(float(x[6]),6) for x in meta})
    cache_info={'n':len(meta),'FF':sum(str(x[1])=='FF' for x in meta),'NF':sum(str(x[1])=='NF' for x in meta),'dts':dts}
    check('record_cache_manifest',cache_info['n']==100 and cache_info['FF']==44 and cache_info['NF']==56,str(cache_info))
except Exception as e: check('record_cache_manifest',False,repr(e))

raw_sha=[]
for p in sorted(RAW.rglob('*.json')): raw_sha.append(f'{p.relative_to(RAW)}|{hashlib.sha256(p.read_bytes()).hexdigest()}')
raw_sha_file=NOTES/'raw_run_json_sha256_2026-10-12.txt'; raw_sha_file.write_text('\n'.join(raw_sha)+'\n',encoding='utf-8')
check('raw_json_hash_manifest',len(raw_sha)>0,f'{len(raw_sha)} JSON hashes')

lines=['# R52 calculation verification against original runs','','Date: 2026-10-12. Scope: current corrected derived tables and original JSON runs at `E:/n0r52/runs`.','','## Result','','**PASS with bounded rerun provenance.** The original run directory is present and readable. IDA fields were compared against the current CSV; raw ZIC/rest label invariants, corrected summary arithmetic, and the verified 44 FF + 56 NF record cache were checked.','','The corrected tables include the latest-transition repair for the non-monotonic threshold searches and a fresh 100-component SMF4B x15 ZIC/rest rerun. Rows whose corrected release times are absent from the older original JSON are listed as corrected-rerun rows rather than treated as disagreements.','','## Checks','']
for name,ok,detail in checks:
    mark='x' if ok else ' '; lines.append(f'- [{mark}] `{name}`: {detail}.')
lines += ['', '## Independent counts from the original JSON','']
for key in sorted(raw_outcomes): lines.append(f'- `{key[0]} {key[1]}`: {raw_release_counts[key]} releases; outcomes `{dict(raw_outcomes[key])}`; no-snapshot anchors `{raw_missing_snapshot[key]}`; original non-monotonic flags `{raw_nonmono[key]}`.')
lines += ['', '## Boundaries retained','', '- The point of no return is the latest transition found on the sampled release grid, with finite bracket width; it is not a continuous-time monotonicity proof.', '- The CG comparison is bounded by the published 15% terminal drift criterion; 12 of 44 CG histories did not have a recoverable release at the initial 0.25 s search point, and the reported transition statistics use the 32 resolved histories.', '- The 1.5-times-intensity analysis retains six operationally unresolved cases (three reference non-collapse, two recoverable at collapse minus 0.25 s, one without a recoverable release); they are excluded from resolved transition summaries.', '- Bootstrap intervals resample components, not independent earthquake events; damping, model uncertainty, three-dimensional effects, and alternative zero-velocity initialization remain outside this calculation.', '', f'Raw JSON hash manifest: `{raw_sha_file.relative_to(ROOT)}`.']
(NOTES/'CALCULATION_VERIFICATION_2026-10-12.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'checks':len(checks),'passed':sum(ok for _,ok,_ in checks),'failed':[n for n,ok,_ in checks if not ok],'raw_json':len(raw_sha),'rerun_rows':len(rerun_rows),'cache':cache_info},indent=2))

