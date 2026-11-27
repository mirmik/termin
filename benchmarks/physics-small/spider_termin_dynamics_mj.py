"""Use Termin CRBA/RNEA in a live MuJoCo 3.15.0 spider step (Linux).

Build against the installed Termin SDK and the sibling MuJoCo wheel:

    mjpkg=$(../twister-capper/.venv/bin/python -c 'import mujoco; print(mujoco.__path__[0])')
    g++ -std=c++20 -O3 -DNDEBUG -fPIC -shared -Isdk/include -I"$mjpkg/include" \
        benchmarks/physics-small/spider_termin_dynamics_mj.cpp -Lsdk/lib -ltermin_robotics \
        "$mjpkg/libmujoco.so.3.15.0" -Wl,-rpath,"$PWD/sdk/lib:$mjpkg" -o /tmp/dynamics.so
    ../twister-capper/.venv/bin/python benchmarks/physics-small/spider_termin_dynamics_mj.py \
        --library /tmp/dynamics.so quality sweep /tmp/sweep.npz
    taskset -c 6 ../twister-capper/.venv/bin/python benchmarks/physics-small/spider_termin_dynamics_mj.py \
        --library /tmp/dynamics.so time

Pass --geometry /path/to/geometry.so to time or record with the Termin
sphere/box collision callback from spider_mujoco_hybrid.cpp. Its shared library
requires the Termin SDK on LD_LIBRARY_PATH (LD_LIBRARY_PATH="$PWD/sdk/lib").
"""
import argparse
import ctypes as ct
import json
import math
import statistics
import sys
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from time import perf_counter_ns

import mujoco as mj
import numpy as np

from spider_mujoco_contacts import record

SPIDER = Path(__file__).resolve().parents[3] / "twister-capper/scripts/spider"
sys.path.insert(0, str(SPIDER))
import run


class Bridge:
    def __init__(self, library):
        self.lib = ct.CDLL(str(library.resolve()))
        ptr = ct.c_void_p
        double_ptr = ct.POINTER(ct.c_double)
        self.lib.spider_dynamics_create.argtypes = [ptr]
        self.lib.spider_dynamics_create.restype = ptr
        self.lib.spider_dynamics_destroy.argtypes = [ptr]
        self.lib.spider_dynamics_destroy.restype = None
        self.lib.spider_dynamics_step.argtypes = [ptr, ptr, ct.c_int]
        self.lib.spider_dynamics_errors.argtypes = [ptr, double_ptr, double_ptr]
        self.lib.spider_dynamics_errors.restype = None
        self.lib.spider_dynamics_batch.argtypes = [ptr, ptr, ptr, ct.c_int, double_ptr, ct.c_int]

    @contextmanager
    def workspace(self, model, *, predict=False):
        work = self.lib.spider_dynamics_create(model._address)
        if not work:
            raise ValueError("Unsupported model")
        try:
            if predict:
                self.lib.spider_dynamics_enable_prediction.argtypes = [ct.c_void_p]
                if self.lib.spider_dynamics_enable_prediction(work):
                    raise RuntimeError("Could not initialize predictive contacts")
            yield work
        finally:
            self.lib.spider_dynamics_destroy(work)


def hybrid_record(bridge, path, case, time_constant, *, predict=False):
    # record constructs its own model and supplies that live model on every step.
    with ExitStack() as stack:
        work = None
        hits = []
        earliest = []
        if predict:
            bridge.lib.spider_dynamics_prediction_hits.argtypes = [ct.c_void_p]
            bridge.lib.spider_dynamics_prediction_fraction.argtypes = [ct.c_void_p, ct.c_int]
            bridge.lib.spider_dynamics_prediction_fraction.restype = ct.c_double

        def step(model, data):
            nonlocal work
            if work is None:
                work = stack.enter_context(bridge.workspace(model, predict=predict))
            if bridge.lib.spider_dynamics_step(work, data._address, 1):
                raise RuntimeError(f"Hybrid dynamics failed in {case} at t={data.time:.9g} s")
            if predict:
                count = bridge.lib.spider_dynamics_prediction_hits(work)
                fractions = [bridge.lib.spider_dynamics_prediction_fraction(work, i) for i in range(count)]
                if count < 0 or not all(0 <= fraction <= 1 for fraction in fractions):
                    raise RuntimeError("Invalid predictive contact telemetry")
                hits.append(count)
                earliest.append(min(fractions, default=1.))

        values = record(run, path, case, .001, contact_time_constant=time_constant, step=step)
        mass_error, bias_error = ct.c_double(), ct.c_double()
        bridge.lib.spider_dynamics_errors(work, ct.byref(mass_error), ct.byref(bias_error))
        if not max(mass_error.value, bias_error.value) < 1e-8:
            raise RuntimeError(f"Mass/bias mismatch {mass_error.value}, {bias_error.value}")
        print(json.dumps(dict(peak_mass_error=mass_error.value, peak_bias_error=bias_error.value)))
        if predict:
            values.update(swept_hits=np.array([0, *hits]), earliest_sweep_fraction=np.array([1., *earliest]))
        return values


def time_run(bridge, use_termin, time_constant):
    model = mj.MjModel.from_xml_path(str(run.MODEL))
    model.opt.timestep = .001
    model.opt.noslip_iterations = 10
    if time_constant is not None:
        if not math.isfinite(time_constant) or time_constant < 2 * model.opt.timestep:
            raise ValueError("Contact time constant must be finite and at least twice dt")
        model.geom_solref[:, 0] = time_constant
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    hip = model.actuator(run.HIP).id
    targets = np.array([run.command(k * .001) for k in range(4000)])
    workspace = bridge.workspace(model) if use_termin else nullcontext()
    with workspace as work:
        def batch(commands):
            ptr = commands.ctypes.data_as(ct.POINTER(ct.c_double))
            ret = bridge.lib.spider_dynamics_batch(work, model._address, data._address, hip, ptr, len(commands))
            if ret:
                raise RuntimeError("Hybrid timing failed")

        batch(targets[:1000])
        start = perf_counter_ns()
        batch(targets[1000:])
        micros = (perf_counter_ns() - start) / 3e6
    if np.any(data.warning.number) or data.nefc != 18 or not np.isfinite(data.qpos).all():
        raise RuntimeError("Invalid timed trajectory")
    return micros, np.concatenate((data.qpos, data.qvel, data.efc_force))


def geometry(library):
    if library is None:
        return nullcontext()
    from spider_mujoco_hybrid import geometry_bridge
    return geometry_bridge(library)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--geometry", type=Path)
    subs = parser.add_subparsers(dest="mode", required=True)
    quality_parser = subs.add_parser("quality")
    quality_parser.add_argument("case", choices=("hold", "sweep", "slide", "plus", "minus"))
    quality_parser.add_argument("output", type=Path)
    quality_parser.add_argument("--contact-time-constant", type=float)
    subs.add_parser("time").add_argument("--contact-time-constant", type=float)
    args = parser.parse_args()
    bridge = Bridge(args.library)
    if args.mode == "quality":
        with geometry(args.geometry):
            np.savez_compressed(args.output, **hybrid_record(bridge, run.MODEL, args.case, args.contact_time_constant))
        return
    modes = {"mujoco": (False, None), "termin_dynamics": (True, None)}
    if args.geometry:
        modes["termin_dynamics_geometry"] = (True, args.geometry)
    samples = {mode: [] for mode in modes}
    reference = None
    for i in range(7):
        for name in (modes if i % 2 == 0 else reversed(modes)):
            dynamics, geom = modes[name]
            with geometry(geom):
                micros, state = time_run(bridge, dynamics, args.contact_time_constant)
            if reference is None:
                reference = state
            np.testing.assert_allclose(state, reference, rtol=1e-9, atol=1e-9)
            samples[name].append(micros)
    print(json.dumps({k: dict(median_us=statistics.median(v), samples_us=v) for k, v in samples.items()}))


if __name__ == "__main__":
    main()
