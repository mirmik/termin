"""Record per-foot MuJoCo reactions and signed gaps for the Termin spider comparison.

From the Termin root:
    ../twister-capper/.venv/bin/python benchmarks/physics-small/spider_mujoco_contacts.py sweep sweep.npz

Row k contains the force and impulse over the step ending at t[k], in N and
N s. Row zero contains the initial pose and zero impulse. contact_gap[k] is
the signed foot-to-ground distance at the recorded pose in m.
"""

import argparse
import math
import sys
from pathlib import Path

import mujoco as mj
import numpy as np


def target(run, case, time):
    if case == "hold":
        return 0.0
    if case in ("plus", "minus"):
        phase = min(max((time - 1.0) / 0.24, 0.0), 1.0)
        sign = 1 if case == "plus" else -1
        return sign * 0.55 * (1 - math.cos(math.pi * phase)) / 2
    return run.command(time)


def record(run, model_path, case, dt, noslip=10):
    model = mj.MjModel.from_xml_path(str(model_path))
    model.opt.timestep = dt
    model.opt.noslip_iterations = noslip
    if case == "slide":
        model.geom_friction[:, 0] = 0.15
    data = mj.MjData(model)
    ground = model.geom("Static Ground").id
    base = model.body("Spider Body").id
    sites = [model.site(name).id for name in run.FEET]
    geoms = [model.geom(name).id for name in run.FEET]
    if not np.array_equal(model.geom_bodyid[geoms], model.site_bodyid[sites]):
        raise ValueError("Spider foot geometry and site body differ")
    foot_by_geom = {geom: index for index, geom in enumerate(geoms)}
    joints = [model.actuator(i).name for i in range(model.nu)]
    qpos_index = [model.joint(name).qposadr[0] for name in joints]
    hip = model.actuator(run.HIP).id
    mj.mj_forward(model, data)
    # Local z is the outward normal of the reference ground box's top face.
    ground_up = data.geom_xmat[ground].reshape(3, 3)[:, 2].copy()

    t = np.arange(round(run.DURATION / dt) + 1) * dt
    commands = np.array([target(run, case, time) for time in t])
    forces = np.zeros((len(t), len(geoms)))
    other_ground_force = np.zeros(len(t))
    gap = np.empty_like(forces)
    feet = np.empty((len(t), len(geoms), 3))
    body = np.empty((len(t), 3))
    q = np.empty((len(t), len(joints)))
    torque = np.empty_like(q)
    wrench = np.empty(6)

    for k in range(len(t)):
        if k:
            data.ctrl[hip] = commands[k - 1]
            mj.mj_step(model, data)
            for contact_id in range(data.ncon):
                c = data.contact[contact_id]
                g1, g2 = c.geom
                if g1 == ground:
                    supported, sign = g2, 1
                elif g2 == ground:
                    supported, sign = g1, -1
                else:
                    continue
                mj.mj_contactForce(model, data, contact_id, wrench)
                # The wrench is on geom2. Contact axes are rows of frame.
                force_world = sign * (c.frame.reshape(3, 3).T @ wrench[:3])
                if supported in foot_by_geom:
                    forces[k, foot_by_geom[supported]] += force_world @ ground_up
                else:
                    other_ground_force[k] += force_world @ ground_up
            mj.mj_kinematics(model, data)
        for i, geom in enumerate(geoms):
            gap[k, i] = mj.mj_geomDistance(model, data, geom, ground, np.inf, None)
        feet[k] = data.site_xpos[sites]
        body[k] = data.xpos[base]
        q[k] = data.qpos[qpos_index]
        torque[k] = data.actuator_force

    if np.any(data.warning.number):
        raise RuntimeError(f"MuJoCo warnings: {data.warning.number}")
    if not all(np.isfinite(array).all() for array in (forces, gap, feet, body, q, torque, other_ground_force)):
        raise ValueError("Nonfinite contact record")
    return dict(t=t, feet=feet, body=body, q=q, torque=torque, hip_offset_rad=commands,
                normal_force=forces, normal_impulse=forces * dt, contact_gap=gap, foot_names=run.FEET,
                other_ground_force=other_ground_force, joints=joints,
                weight_N=-model.body_mass.sum() * (model.opt.gravity @ ground_up))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("hold", "sweep", "slide", "plus", "minus"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--twister-root", type=Path, default=Path(__file__).resolve().parents[3] / "twister-capper")
    parser.add_argument("--dt", type=float, choices=(.0005, .001, .002, .005), default=.001)
    args = parser.parse_args()
    sys.path.insert(0, str(args.twister_root / "scripts/spider"))
    import run

    np.savez_compressed(args.output, **record(run, run.MODEL, args.case, args.dt))
