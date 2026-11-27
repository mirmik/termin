"""Compare generic swept contacts on the combined Termin/MuJoCo spider.

Build the predict_contact and predict_geometry targets (see CMakeLists.txt).
Run with the resulting libraries, for example from the repository root:

    LD_LIBRARY_PATH="$PWD/sdk/lib" ../twister-capper/.venv/bin/python \
        benchmarks/physics-small/predict_contact_spider.py --library /tmp/predict.so \
        --geometry /tmp/geometry.so quality /tmp/quality
    LD_LIBRARY_PATH="$PWD/sdk/lib" taskset -c 6 ../twister-capper/.venv/bin/python \
        benchmarks/physics-small/predict_contact_spider.py --library /tmp/predict.so \
        --geometry /tmp/geometry.so time

Timing includes setting targets and stepping + end-pose FK in a native batch.
The impact number measures steps 99–103 ms, divided by four. The loaded number
measures 1–4 s with the moving hip and the standing number covers 4–5 s after
the command returns to zero. All times are wall microseconds per step.
"""
import argparse
import ctypes as ct
import json
import statistics
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from time import perf_counter_ns

import mujoco as mj
import numpy as np

from spider_contact_metrics import summarize
from spider_termin_dynamics_mj import Bridge, geometry, hybrid_record, run


def record_study(bridge, args):
    args.output.mkdir(parents=True, exist_ok=True)
    for label, offset in (("low", -.0004), ("nominal", 0.), ("high", .0004)):
        cases = ["hold", "sweep", "slide", "plus", "minus"] if not offset else ["hold"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "spider.xml"
            tree = ET.parse(run.MODEL)
            root = tree.find("./worldbody/body[freejoint]")
            position = np.fromstring(root.attrib["pos"], sep=" ")
            position[2] += offset
            root.set("pos", " ".join(map(str, position)))
            tree.write(path, encoding="utf-8")
            for case in cases:
                if args.case and args.case != case:
                    continue
                control = None
                for mode in args.modes:
                    values = hybrid_record(bridge, path, case, .002, predict=mode == "predict")
                    if np.any(values["other_ground_force"]):
                        raise RuntimeError("Unexpected ground force away from the feet")
                    file = args.output / f"{mode}-{label}-{case}.npz"
                    loads = values["normal_force"].sum(axis=1)
                    first = int(np.flatnonzero(loads > 1e-5)[0])
                    if mode == "control":
                        control = values
                    elif control is not None:
                        prior = min(first, np.flatnonzero(control["normal_force"].sum(axis=1) > 1e-5)[0])
                        for field in ("body", "feet", "q", "torque"):
                            np.testing.assert_allclose(values[field][:prior], control[field][:prior],
                                                       rtol=0., atol=1e-12)
                    gaps = values["contact_gap"]
                    # Require actual loss of support before labeling clearance a rebound.
                    landing = gaps[first:251].min(axis=1)
                    unloaded = loads[first:251] < 1e-5
                    positive_rebound = np.maximum(0., landing[unloaded]).max(initial=0.)
                    center_ref = values["feet"][first-1, :, :2]
                    foot_travel = np.linalg.norm(values["feet"][:, :, :2] - center_ref, axis=2)
                    metrics = summarize(values)
                    metrics.update(first_response_s=float(values["t"][first]),
                                   pre_response_gap_mm=float(gaps[first-1].min()*1000),
                                   first_response_Ns=float(loads[first]*.001),
                                   landing_impulse_through_150ms_Ns=float(loads[:151].sum()*.001),
                                   unsupported_rebound_through_250ms_mm=float(positive_rebound*1000),
                                   landing_foot_center_drift_through_1s_mm=float(foot_travel[first:1001].max()*1000),
                                   final_foot_displacement_since_landing_mm=float(foot_travel[-1].max()*1000))
                    if mode == "predict":
                        metrics.update(first_response_swept_hits=int(values["swept_hits"][first]),
                                       total_swept_hits=int(values["swept_hits"].sum()))
                    np.savez_compressed(file, **values)
                    print(file.stem, json.dumps(metrics), flush=True)


def time_run(bridge, model, predict):
    hip = model.actuator(run.HIP).id
    targets = np.array([run.command(i*.001) for i in range(5000)])
    pointers = {i: targets[i:].ctypes.data_as(ct.POINTER(ct.c_double)) for i in (0, 99, 103, 1000, 4000)}
    def batch(data, work, start, stop):
        if bridge.lib.spider_dynamics_batch(work, model._address, data._address, hip, pointers[start], stop-start):
            raise RuntimeError("Spider batch failed")

    impact = []
    for trial in range(31):
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        with bridge.workspace(model, predict=predict) as work:
            # Start each repeat with a real fall. This also initializes the
            # predictor's pair history and kinematic caches before the timer.
            batch(data, work, 0, 99)
            start = perf_counter_ns()
            batch(data, work, 99, 103)
            impact.append((perf_counter_ns()-start)/4000.)
            if trial == 30:
                batch(data, work, 103, 1000)
                start = perf_counter_ns()
                batch(data, work, 1000, 4000)
                loaded = (perf_counter_ns()-start)/3e6
                start = perf_counter_ns()
                batch(data, work, 4000, 5000)
                standing = (perf_counter_ns()-start)/1e6
            if np.any(data.warning.number) or not np.isfinite(data.qpos).all():
                raise RuntimeError("Invalid timed trajectory")
    return statistics.median(impact), loaded, standing


def time_study(bridge, args):
    model = mj.MjModel.from_xml_path(str(run.MODEL))
    model.opt.timestep = .001
    model.opt.noslip_iterations = 10
    model.geom_solref[:, 0] = .002
    samples = {mode: [] for mode in args.modes}
    for trial in range(7):
        for mode in (args.modes if trial % 2 == 0 else reversed(args.modes)):
            samples[mode].append(time_run(bridge, model, mode == "predict"))
    for key, values in samples.items():
        print(key, json.dumps(dict(impact_loaded_standing_us=values, medians_us=np.median(values, axis=0).tolist())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--mode", choices=["control", "predict", "both"], default="both")
    commands = parser.add_subparsers(dest="action", required=True)
    quality = commands.add_parser("quality")
    quality.add_argument("output", type=Path)
    quality.add_argument("--case", choices=["hold", "sweep", "slide", "plus", "minus"])
    commands.add_parser("time")
    args = parser.parse_args()
    args.modes = ["control", "predict"] if args.mode == "both" else [args.mode]
    with geometry(args.geometry):
        (record_study if args.action == "quality" else time_study)(Bridge(args.library), args)
