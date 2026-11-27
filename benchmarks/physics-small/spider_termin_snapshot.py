r"""Transfer the native state at a loaded Termin sweep step into a MuJoCo keyframe.

From the repository root with the Linux free-threaded SDK and sibling robot checkouts:

    out=build/spider-contacts
    mkdir -p "$out"
    g++ -std=c++20 -O2 -fPIC -fvisibility=hidden -shared -DNB_SHARED -DNB_FREE_THREADED \
        -Isdk/include -Isdk/include/python3.14t -Isdk/lib/nanobind/include \
        benchmarks/physics-small/spider_termin_snapshot.cpp -Lsdk/lib -lnanobind-ft -ltermin_robotics \
        -o "$out/_spider_termin_snapshot.so"
    LD_LIBRARY_PATH="$PWD/sdk/lib" sdk/bin/termin_python benchmarks/physics-small/spider_termin_snapshot.py capture "$out/frame.json" \
        --extension-dir "$out"
    ../twister-capper/.venv/bin/python benchmarks/physics-small/spider_termin_snapshot.py keyframe \
        "$out/frame.json" "$out/keyframe.xml" --ground-margin 1e-8

Optionally pass --termin-trace with the corrected 1 ms sweep NPZ produced by
spider_contact_schemes.py to compare each foot's next-step normal reaction.
"""
import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "twister-capper/scripts/spider"))
import run
from export_model import component, walk


def capture(args):
    sys.path.insert(0, str(args.extension_dir.resolve()))
    import _spider_termin_snapshot as native
    from termin.bootstrap import bootstrap_player, shutdown_runtime
    from termin.engine._engine_native.scene import SceneMode
    from termin.physics_fem import FEMArticulationComponent
    from termin.scene import TcScene

    source = json.loads(run.SOURCE.read_text())["scene"]
    joints = {}
    foot_link = {}
    radii = {}
    scales = {}
    for entity in walk(source["entities"]):
        entity["components"] = [c for c in entity["components"] if c["type"].startswith("FEM")
                                or c["type"] in ("ColliderComponent", "RotatorComponent")]
        if not any(c["type"] == "RotatorComponent" for c in entity["components"]):
            continue
        link, = entity["children"]
        joints[entity["name"]] = link["name"]
        scales[entity["name"]] = float(component(entity, "RotatorComponent")["coordinate_scale"])
        # The six foot sites are rigid descendants of their final actuated link.
        if entity["name"].endswith("Knee Pitch"):
            for child in walk(link["children"]):
                if child["name"] in run.FEET:
                    foot_link[child["name"]] = link["name"]
                    collider = component(child, "ColliderComponent")
                    if collider["collider_type"] != "Sphere":
                        raise ValueError(f"Expected spherical foot collider on {child['name']}")
                    radii[child["name"]] = float(collider["box_size"][0]) / 2

    dt = 0.001
    bootstrap_player()
    scene = TcScene.create("Termin contact snapshot")
    try:
        scene.load_from_data(source)
        scene.fixed_timestep = dt
        scene.time_scale = 1
        scene.set_mode(SceneMode.PLAY)
        scene.update(0.)
        root = scene.find_entity_by_name("Spider Body").get_component(FEMArticulationComponent)
        servos = {name: scene.find_entity_by_name(name).get_tc_component("FEMJointServoComponent") for name in joints}
        initial_targets = {name: servo.require_field("target_coordinate") for name, servo in servos.items()}
        for i in range(args.step):
            servos[run.HIP].set_field("target_coordinate", initial_targets[run.HIP] + math.degrees(run.command(i * dt)))
            scene.update(dt)
        if not root.initialized:
            raise RuntimeError("Terminated simulation without a committed articulation")
        state = native.read(root.articulation)
        if set(joints.values()) != set(state["links"]) or set(foot_link) != set(run.FEET):
            raise ValueError("Mismatch between compiled articulation and scene joint/foot names")
        # Set the input that the next step would use, leaving the committed pose and velocity intact.
        servos[run.HIP].set_field("target_coordinate", initial_targets[run.HIP] + math.degrees(run.command(args.step * dt)))
        target_offsets = {name: (servo.require_field("target_coordinate") - initial_targets[name]) * scales[name]
                          for name, servo in servos.items()}
        feet = {}
        for name in run.FEET:
            p = scene.find_entity_by_name(name).transform.global_position
            position = np.array([p.x, p.y, p.z])
            body = state["links"][foot_link[name]]
            velocity = body["linear"] + np.cross(body["angular"], position - body["origin"])
            surface = position - np.array([0, 0, radii[name]])
            jac = native.point_jacobian(root.articulation, body["dof"] - 6, *surface)
            feet[name] = {"position": position.tolist(), "velocity": velocity.tolist(),
                          "surface": surface.tolist(), "jacobian": np.reshape(jac, (3, -1)).tolist()}
        state.update(joints=joints, feet=feet, ctrl=target_offsets, time=args.step * dt, dt=dt)
        args.snapshot.write_text(json.dumps(state, indent=2, allow_nan=False) + "\n")
    finally:
        scene.destroy()
        shutdown_runtime()


def keyframe(args):
    import mujoco as mj

    state = json.loads(args.snapshot.read_text())
    xml = ET.parse(run.MODEL)
    model = mj.MjModel.from_xml_path(str(run.MODEL))
    qpos = model.qpos0.copy()
    qvel = np.zeros(model.nv)
    ctrl = np.zeros(model.nu)
    base = model.joint("base")
    if int(base.qposadr[0]) != 0 or int(base.dofadr[0]) != 0 or model.nv != 6 + len(state["joints"]):
        raise ValueError("Unexpected floating-base layout")
    qpos[:7] = state["base_position"] + state["base_wxyz"]
    qvel[:6] = state["base_linear_world"] + state["base_angular_local"]
    for name, link in state["joints"].items():
        joint = model.joint(name)
        qpos[joint.qposadr[0]] = state["links"][link]["q"]
        qvel[joint.dofadr[0]] = state["links"][link]["v"]
        ctrl[model.actuator(name).id] = state["ctrl"][name]

    if not np.isfinite(args.ground_margin) or args.ground_margin < 0:
        raise ValueError("Ground margin must be finite and nonnegative")
    xml.find(".//geom[@name='Static Ground']").set("margin", str(args.ground_margin))
    xml.find("option").set("timestep", str(state["dt"]))
    xml.find("option").set("noslip_iterations", "10")
    values = {key: " ".join(format(x, ".17g") for x in data)
              for key, data in [("qpos", qpos), ("qvel", qvel), ("ctrl", ctrl)]}
    ET.SubElement(ET.SubElement(xml.getroot(), "keyframe"), "key", name="termin", time=str(state["time"]), **values)
    text = ET.tostring(xml.getroot(), encoding="unicode")
    model = mj.MjModel.from_xml_string(text)
    data = mj.MjData(model)
    mj.mj_resetDataKeyframe(model, data, model.key("termin").id)
    mj.mj_forward(model, data)
    base_body = model.body("Spider Body").id
    np.testing.assert_allclose(data.xpos[base_body], state["base_position"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(data.xquat[base_body], state["base_wxyz"], rtol=0, atol=1e-12)
    position_error = velocity_error = 0.
    jac_error = 0.
    # dq_Termin = transform @ dq_MuJoCo. Local base translation in Termin,
    # world base translation in MuJoCo. Both angular velocities are local.
    transform = np.eye(model.nv)
    transform[:3, :3] = data.xmat[base_body].reshape((3, 3)).T
    transform[6:, 6:] = 0
    for name, link in state["joints"].items():
        transform[state["links"][link]["dof"], model.joint(name).dofadr[0]] = 1
    for foot, material in state["feet"].items():
        site = model.site(foot).id
        twist = np.empty(6)
        mj.mj_objectVelocity(model, data, mj.mjtObj.mjOBJ_SITE, site, twist, 0)
        position_error = max(position_error, np.linalg.norm(data.site_xpos[site] - material["position"]))
        velocity_error = max(velocity_error, np.linalg.norm(twist[3:] - material["velocity"]))
        jac = np.empty((3, model.nv))
        mj.mj_jac(model, data, jac, None, np.array(material["surface"]), model.site_bodyid[site])
        jac_error = max(jac_error, np.abs(jac - material["jacobian"] @ transform).max())
    if not all(error < 1e-8 for error in (position_error, velocity_error, jac_error)):
        raise ValueError(f"Foot kinematics mismatch: dx={position_error}, dv={velocity_error}, dJ={jac_error}")
    if args.termin_trace:
        with np.load(args.termin_trace) as trace:
            step = round(state["time"] / state["dt"])
            np.testing.assert_array_equal(trace["foot_names"], run.FEET)
            np.testing.assert_allclose(trace["t"][step:step + 2], [state["time"], state["time"] + state["dt"]],
                                       rtol=0, atol=1e-12)
            foot_positions = np.array([state["feet"][name]["position"] for name in run.FEET])
            np.testing.assert_allclose(trace["feet"][step], foot_positions, rtol=0, atol=1e-12)
            # Trace forces are the accepted interval impulse divided by dt.
            termin_force = trace["normal_force"][step + 1]
        forces = np.zeros(len(run.FEET))
        ground = model.geom("Static Ground").id
        foot_ids = {model.geom(name).id: i for i, name in enumerate(run.FEET)}
        wrench = np.empty(6)
        for index, contact in enumerate(data.contact):
            g1, g2 = contact.geom
            if ground == g1 and g2 in foot_ids:
                foot, sign = g2, 1
            elif ground == g2 and g1 in foot_ids:
                foot, sign = g1, -1
            else:
                continue
            mj.mj_contactForce(model, data, index, wrench)
            forces[foot_ids[foot]] += sign * (contact.frame.reshape(3, 3).T @ wrench[:3])[2]
        print(f"Upward foot loads [N], order {run.FEET}\nTermin {termin_force}\nMuJoCo {forces}")
    args.xml.write_text(text + "\n")
    print(f"t={data.time:g}s, nv={model.nv}, contacts={data.ncon}, nefc={data.nefc}, "
          f"max foot position difference={position_error:.3g} m, velocity difference={velocity_error:.3g} m/s, "
          f"contact Jacobian max difference={jac_error:.3g}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    cap = modes.add_parser("capture")
    cap.add_argument("snapshot", type=Path)
    cap.add_argument("--step", type=int, default=1500)
    cap.add_argument("--extension-dir", type=Path, required=True)
    key = modes.add_parser("keyframe")
    key.add_argument("snapshot", type=Path)
    key.add_argument("xml", type=Path)
    key.add_argument("--ground-margin", type=float, default=0)
    key.add_argument("--termin-trace", type=Path)
    args = parser.parse_args()
    if args.mode == "capture":
        if args.step <= 0:
            parser.error("--step must be positive")
        capture(args)
    else:
        keyframe(args)


if __name__ == "__main__":
    main()
