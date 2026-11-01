import sys, time, json
sys.path.insert(0, r'E:\n0r53\code_copy')
sys.path.insert(0, r'E:\n0r53\code')
import openseespy.opensees as ops
from opsmodel import replay
import numpy as np

for model in ['SMF4B','SMF20CG']:
    ops.wipe()
    info = replay(model)
    floors = list(info.mf_floor_nodes)
    t0=time.time()
    try:
        ops.wipeAnalysis()
        vals = ops.eigen('-symmBandLapack', 3)
        dt1=time.time()-t0
        phi=np.array([ops.nodeEigenvector(n,1,1) for n in floors])
        print(model,'symmBandLapack ok, %.2fs, T=%.4f, phi roof=%.4f'%(dt1,2*np.pi/vals[0]**0.5 if vals else -1,phi[-1]))
    except Exception as e:
        print(model,'symmBandLapack FAIL:',e)
    # repeat determinism check
    vals2 = ops.eigen('-symmBandLapack', 3)
    phi2=np.array([ops.nodeEigenvector(n,1,1) for n in floors])
    print('   bitwise repeat:', np.array_equal(phi,phi2), 'maxdiff', float(np.abs(np.asarray(vals)-np.asarray(vals2)).max()))
    ops.wipe()
