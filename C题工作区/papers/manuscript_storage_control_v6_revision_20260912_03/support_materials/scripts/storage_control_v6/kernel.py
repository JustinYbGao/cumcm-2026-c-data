"""Strict float64 greedy regression and reserve-policy scenario objectives.

The compiled artifact and compiler temporary files are local to v6. The legacy
module is never imported, and no v5 runtime is read or written.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

import numpy as np

SOURCE = Path(__file__).with_suffix('.c')
WORK = SOURCE.parents[2]
RUNTIME = WORK / 'results/storage_control_v6/runtime'
RUNTIME.mkdir(parents=True, exist_ok=True)
digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
build = RUNTIME / digest
build.mkdir(exist_ok=True)
binary = build / ('kernel.dylib' if platform.system() == 'Darwin' else 'kernel.so')
command = ['cc', '-O3', '-std=c99', '-dynamiclib' if platform.system() == 'Darwin' else '-shared',
           '-fPIC', str(SOURCE), '-o', str(binary)]
if not binary.exists():
    environment = dict(os.environ, TMPDIR=str(RUNTIME))
    subprocess.run(command, check=True, capture_output=True, text=True, env=environment)
    (build / 'build.json').write_text(json.dumps({
        'command': command, 'source_sha256': digest,
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'compiler': subprocess.run(['cc', '--version'], check=True, capture_output=True,
                                   text=True, env=environment).stdout}, indent=2) + '\n')
lib = ctypes.CDLL(str(binary))
vec = np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')
lib.legacy_objective.argtypes = [ctypes.c_int, ctypes.c_int, vec, vec, vec,
    ctypes.c_double, ctypes.c_double, ctypes.c_double, vec, vec, vec]
lib.legacy_objective.restype = ctypes.c_double
lib.reserve_objective.argtypes = [ctypes.c_int, ctypes.c_int, vec, vec, vec, vec,
    ctypes.c_double, ctypes.c_double, ctypes.c_double, vec, vec, vec, vec]
lib.reserve_objective.restype = ctypes.c_double


def _inputs(q, net, price, initial, kappa, mu):
    q, net, price = [np.ascontiguousarray(x, dtype=np.float64) for x in (q, net, price)]
    if (q.ndim != 1 or price.shape != q.shape or len(q) == 0 or net.ndim != 2
            or len(net) == 0 or net.shape[1] != len(q)):
        raise ValueError('q and price must have length T; net must have nonempty shape (S,T)')
    if not all(np.all(np.isfinite(x)) for x in (q, net, price, initial, kappa, mu)):
        raise ValueError('objective inputs must be finite')
    return q, net, price


def legacy_evaluate(q, net, price, initial, kappa=5., mu=.38232):
    """The old C arithmetic retained for regression and matched greedy searches."""
    q, net, price = _inputs(q, net, price, initial, kappa, mu)
    grad, fees, end = np.empty(len(q)), np.empty(len(net)), np.empty(len(net))
    score = lib.legacy_objective(len(net), len(q), q, net, price, initial, kappa, mu,
                                 grad, fees, end)
    if not np.isfinite(score) or not np.all(np.isfinite(grad)):
        raise FloatingPointError('legacy objective returned nonfinite score or gradient')
    return {'score': score, 'gradient': grad, 'emergency_fee': fees, 'end_energy': end}


def evaluate(q, reserve, net, price, initial, kappa=5., mu=.38232):
    """Evaluate a shared causal (q,R) policy and its piecewise derivatives.

    At an E == R tie, the active reserve branch is used: the R derivative is
    one-sided from decreasing R, and the E derivative from increasing E. Other
    demand/power/space ties use the legacy branch ordering. These local choices
    are not global optimality certificates for the nonsmooth objective.
    """
    q, net, price = _inputs(q, net, price, initial, kappa, mu)
    reserve = np.ascontiguousarray(reserve, dtype=np.float64)
    if (reserve.shape != q.shape or not np.all(np.isfinite(reserve))
            or np.any(reserve < 1200.) or np.any(reserve > 10800.)):
        raise ValueError('reserve must have length T and finite values in [1200,10800]')
    grad, reserve_grad = np.empty(len(q)), np.empty(len(q))
    fees, end = np.empty(len(net)), np.empty(len(net))
    score = lib.reserve_objective(len(net), len(q), q, reserve, net, price, initial,
                                  kappa, mu, grad, reserve_grad, fees, end)
    if not np.isfinite(score) or not all(np.all(np.isfinite(x)) for x in (grad, reserve_grad)):
        raise FloatingPointError('reserve objective returned nonfinite score or gradient')
    return {'score': score, 'gradient': grad, 'reserve_gradient': reserve_grad,
            'emergency_fee': fees, 'end_energy': end}
