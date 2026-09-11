"""Float64 strict greedy scenario objective; compiled kernel is a local artifact."""
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import os
import numpy as np

SOURCE = Path(__file__).with_suffix('.c')
WORK = SOURCE.parents[2]
RUNTIME = WORK / 'results/q2_direct_v4/runtime'
RUNTIME.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(RUNTIME)
digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
build = RUNTIME / digest
build.mkdir(exist_ok=True)
binary = build / ('kernel.dylib' if platform.system() == 'Darwin' else 'kernel.so')
command = ['cc', '-O3', '-std=c99', '-dynamiclib' if platform.system() == 'Darwin' else '-shared',
           '-fPIC', str(SOURCE), '-o', str(binary)]
if not binary.exists():
    subprocess.run(command, check=True, capture_output=True, text=True)
    (build / 'build.json').write_text(json.dumps({'command': command, 'source_sha256': digest,
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'compiler': subprocess.run(['cc','--version'], check=True, capture_output=True, text=True).stdout}, indent=2)+'\n')
lib = ctypes.CDLL(str(binary))
vec = np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')
lib.objective.argtypes = [ctypes.c_int,ctypes.c_int,vec,vec,vec,ctypes.c_double,ctypes.c_double,ctypes.c_double,vec,vec,vec]
lib.objective.restype = ctypes.c_double


def evaluate(q, net, price, initial, kappa=5., mu=.38232):
    q, net, price = [np.ascontiguousarray(x,dtype=np.float64) for x in [q,net,price]]
    assert net.ndim == 2 and len(net) > 0 and net.shape[1] == len(q) == len(price)
    grad=np.empty(len(q)); fees=np.empty(len(net)); end=np.empty(len(net))
    score=lib.objective(len(net),len(q),q,net,price,initial,kappa,mu,grad,fees,end)
    assert np.isfinite(score) and np.all(np.isfinite(grad))
    return {'score': score, 'gradient': grad, 'emergency_fee': fees, 'end_energy': end}
