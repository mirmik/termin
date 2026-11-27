r"""Compare the two Termin contact schemes on the shared six-foot spider.

From the Termin checkout with sibling twister-capper and termin-spider-control:

    mkdir -p build/spider-contacts
    g++ -std=c++20 -O2 -fPIC -shared -Isdk/include benchmarks/physics-small/spider_contact_observer.cpp \
        -Lsdk/lib -ltermin_physics_qopt -ldl -o build/spider-contacts/observe.so
    LD_LIBRARY_PATH="$PWD/sdk/lib" LD_PRELOAD="$PWD/build/spider-contacts/observe.so" \
        sdk/bin/termin_python benchmarks/physics-small/spider_contact_schemes.py quality predicted \
        --case sweep --dt .001 --output build/spider-contacts/predicted.npz
    taskset -c 2 sdk/bin/termin_python benchmarks/physics-small/spider_contact_schemes.py time predicted --dt .001

For the reference run substitute corrected for predicted. Compile the observer
against each SDK separately when comparing builds. For MuJoCo timing use the
twister-capper Python and select mujoco (NoSlip 10). Time runs use fresh
uninstrumented processes. Each timed sweep covers simulated seconds 1–4.
"""
import argparse
import ctypes
import json
import math
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns

import numpy as np

SPIDER = Path(__file__).resolve().parents[3] / "twister-capper/scripts/spider"
sys.path.insert(0, str(SPIDER))
import run


class Contact(ctypes.Structure):
    _fields_ = [(name, ctypes.c_double) for name in
                ("x", "y", "z", "gap", "normal_impulse", "tangent_speed", "tangent_travel", "work")] + [("sliding", ctypes.c_int)]


def trajectory(args, joints, advance, observe):
    probe = ctypes.CDLL(None)
    probe.spider_contacts.restype = ctypes.POINTER(Contact)
    probe.spider_contacts.argtypes = [ctypes.POINTER(ctypes.c_int)] * 3
    t = np.arange(round(4 / args.dt) + 1) * args.dt
    target = np.zeros(len(t)) if args.case == "hold" else np.array([run.command(time) for time in t])
    frames = [observe()]
    shape = (len(t), len(run.FEET))
    impulse, speed, travel, work = [np.zeros(shape) for _ in range(4)]
    gap = np.full(shape, np.nan)
    sliding = np.zeros(shape, dtype=bool)
    passes = np.zeros(len(t), dtype=int)
    other_impulse = np.zeros(len(t))
    for k, angle in enumerate(target[:-1], start=1):
        probe.spider_begin_observation()
        advance(angle)
        frame = observe()
        frames.append(frame)
        centers = np.asarray(frame[1])
        count, evaluations, accepted = [ctypes.c_int() for _ in range(3)]
        rows = probe.spider_contacts(ctypes.byref(count), ctypes.byref(evaluations), ctypes.byref(accepted))
        if accepted.value != 1:
            raise RuntimeError(f"Step {k} committed {accepted.value} contact sets")
        passes[k] = evaluations.value
        for index in range(count.value):
            row = rows[index]
            # Dynamic material point on a sphere of radius 25 mm. Body-ground
            # contacts in the tumbling stress run do not belong to a foot.
            distance = np.linalg.norm(centers - (row.x, row.y, row.z), axis=1)
            leg = int(distance.argmin())
            if distance[leg] > 0.030:
                other_impulse[k] += row.normal_impulse
                continue
            impulse[k, leg] += row.normal_impulse
            gap[k, leg] = np.fmin(gap[k, leg], row.gap)
            speed[k, leg] = max(speed[k, leg], row.tangent_speed)
            travel[k, leg] = max(travel[k, leg], row.tangent_travel)
            work[k, leg] += row.work
            sliding[k, leg] |= bool(row.sliding)
    body, feet, q, torque = map(np.stack, zip(*frames, strict=True))
    if not all(np.isfinite(value).all() for value in (body, feet, q, torque, impulse, speed, travel, work)):
        raise ValueError("Nonfinite trajectory")
    expected = 1 if args.scheme == "predicted" else 2
    if not np.any(passes == expected) or np.any((passes != 0) & (passes != expected)):
        raise RuntimeError(f"Selected scheme {args.scheme} produced pass counts {np.unique(passes)}")
    # The floor is horizontal at z=0. All six colliders are spheres of radius
    # 25 mm centred at the recorded sites, including before contact detection.
    np.savez_compressed(args.output, t=t, body=body, feet=feet, q=q, torque=torque, joints=joints,
                        foot_names=run.FEET, hip_offset_rad=target, normal_impulse=impulse,
                        normal_force=impulse / args.dt, contact_gap=feet[:, :, 2] - 0.025,
                        material_point_gap=gap, tangent_speed=speed, tangent_travel=travel, sliding=sliding, work=work,
                        other_impulse=other_impulse, friction_passes=passes)


def timing(args, joints, advance, observe):
    commands = [run.command(k * args.dt) for k in range(round(4 / args.dt))]
    warmup = round(1 / args.dt)
    for angle in commands[:warmup]:
        advance(angle)
    observe()
    elapsed = 0
    for k in range(warmup, len(commands), 100):
        batch = commands[k:k + 100]
        start = perf_counter_ns()
        for angle in batch:
            advance(angle)
        elapsed += perf_counter_ns() - start
        observe()
    mean = elapsed / (len(commands) - warmup) * 1e-3
    print(f"{mean:.3f} us/step, {mean / (args.dt * 1000):.3f} ms/simulated second")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("quality", "time"))
    parser.add_argument("scheme", choices=("corrected", "predicted", "mujoco"))
    parser.add_argument("--case", default="sweep", choices=("hold", "sweep", "slide", "plus", "minus"))
    parser.add_argument("--dt", type=float, choices=(.0005, .001, .002, .005), default=.001)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "quality" and (args.output is None or args.scheme == "mujoco"):
        parser.error("Termin quality runs require --output. Use spider_mujoco_contacts.py for MuJoCo loads.")
    if args.mode == "time" and args.case != "sweep":
        parser.error("Timing uses the matched loaded sweep")
    if args.case in ("plus", "minus"):
        sign = 1 if args.case == "plus" else -1
        run.command = lambda t: sign * .55 * (1 - math.cos(math.pi * min(max((t - 1) / .24, 0.), 1.))) / 2
    run.record = trajectory if args.mode == "quality" else timing
    if args.scheme == "mujoco":
        args.model = run.MODEL
        args.noslip_iterations = 10
        run.run_mujoco(args)
        return
    with tempfile.TemporaryDirectory() as tmp:
        source = json.loads(run.SOURCE.read_text())
        worlds = [c["data"] for e in run.walk(source["scene"]["entities"]) for c in e["components"]
                  if c["type"] == "FEMPhysicsWorldComponent"]
        world, = worlds
        if args.scheme == "predicted":
            world["experimental_single_pass_contacts"] = True
        else:
            world.pop("experimental_single_pass_contacts", None)
        if args.case == "slide":
            world["contact_friction_coefficient"] = .15
        args.scene = Path(tmp) / "spider.scene"
        args.scene.write_text(json.dumps(source))
        run.run_termin(args)


if __name__ == "__main__":
    main()
