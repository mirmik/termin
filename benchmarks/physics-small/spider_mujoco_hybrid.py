"""Run the MuJoCo spider with Termin's native sphere/box collision query.

Build against the same MuJoCo wheel used by this runner (Linux, from repo root):

    mjdir=$(../twister-capper/.venv/bin/python -c 'import pathlib, mujoco; print(pathlib.Path(mujoco.__file__).parent)')
    c++ -std=c++20 -O3 -shared -fPIC -I"$mjdir/include" -Isdk/include \
        benchmarks/physics-small/spider_mujoco_hybrid.cpp -L"$mjdir" -l:libmujoco.so.3.15.0 \
        -Lsdk/lib -ltermin_collision -o /tmp/spider-geometry.so
    LD_LIBRARY_PATH="$PWD/sdk/lib" ../twister-capper/.venv/bin/python \
        benchmarks/physics-small/spider_mujoco_hybrid.py quality --geometry /tmp/spider-geometry.so \
        --case hold --output /tmp/hybrid.npz

Omit --geometry for the native MuJoCo reference. The timing mode uses the
uninstrumented sweep protocol from spider_contact_schemes.py. Each invocation
owns the single-threaded process and restores MuJoCo's collision table on exit.
"""

import argparse
import contextlib
import ctypes
from pathlib import Path

import numpy as np

from spider_contact_schemes import run, timing
from spider_mujoco_contacts import record


@contextlib.contextmanager
def geometry_bridge(path):
    bridge = ctypes.CDLL(str(path.resolve()))
    count = ctypes.c_uint64()
    returned = ctypes.c_uint64()
    bridge.spider_install_termin_geometry.argtypes = []
    bridge.spider_install_termin_geometry.restype = ctypes.c_int
    bridge.spider_restore_geometry.argtypes = [ctypes.POINTER(ctypes.c_uint64)] * 2
    bridge.spider_restore_geometry.restype = None
    if not bridge.spider_install_termin_geometry():
        raise RuntimeError("Could not install the Termin collision callback with this MuJoCo ABI")
    try:
        yield
    finally:
        bridge.spider_restore_geometry(ctypes.byref(count), ctypes.byref(returned))
    if not 0 < returned.value <= count.value:
        raise RuntimeError("No sphere/box contacts were returned by the Termin callback")
    print(f"Sphere/box queries {count.value}, results within margin {returned.value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("time", "quality"))
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--case", choices=("hold", "sweep", "plus", "minus", "slide"), default="sweep")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--contact-time-constant", type=float, help="Set solref time constant in seconds for quality runs")
    args = parser.parse_args()
    args.dt = .001
    args.noslip_iterations = 10
    if args.mode == "quality" and not args.output:
        parser.error("quality requires --output")
    if args.mode == "time" and args.case != "sweep":
        parser.error("timing uses the hip sweep")
    if args.mode == "time" and args.contact_time_constant is not None:
        parser.error("timing uses the original model's contact parameters")
    args.model = run.MODEL
    with (geometry_bridge(args.geometry) if args.geometry else contextlib.nullcontext()):
        if args.mode == "time":
            run.record = timing
            run.run_mujoco(args)
        else:
            values = record(run, args.model, args.case, args.dt, args.noslip_iterations,
                            contact_time_constant=args.contact_time_constant)
            if np.any(values["other_ground_force"]):
                raise RuntimeError("Ground contacted a body outside the six spherical feet")
            np.savez_compressed(args.output, **values)


if __name__ == "__main__":
    main()
