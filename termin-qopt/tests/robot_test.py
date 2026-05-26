import numpy as np

from termin.geombase import Pose3
from termin.kinematic.kinematic import Rotator3
from termin.kinematic.transform import Transform3
from termin.robot.robot import Robot
from termin.robot.hqsolver import HQPSolver, Level, QuadraticTask
from termin.kinematic.kinchain import KinematicChain3


def _build_two_link_tree():
    base = Transform3(name="base")

    j0 = Rotator3(axis=np.array([0.0, 0.0, 1.0]), parent=base, name="j0")
    link0 = Transform3(parent=j0.output, local_pose=Pose3.translation(0.0, 0.0, 0.4), name="link0")

    j1 = Rotator3(axis=np.array([0.0, 1.0, 0.0]), parent=link0, name="j1")
    ee = Transform3(parent=j1.output, local_pose=Pose3.translation(0.0, 0.0, 0.2), name="ee")

    # Дополнительная ветвь для проверки, что лишние пары индексируются, но не влияют
    j_branch = Rotator3(axis=np.array([1.0, 0.0, 0.0]), parent=base, name="j_branch")
    Transform3(parent=j_branch.output, local_pose=Pose3.translation(0.3, 0.0, 0.0), name="branch_tip")

    return base, ee, j0, j1, j_branch


def _build_two_link_tree_2():
    base = Transform3(name="base")

    j0 = Rotator3(axis=np.array([0.0, 0.0, 1.0]), parent=base, name="j0")
    link0 = Transform3(parent=j0.output, local_pose=Pose3.translation(1.0, 0.0, 0.0), name="link0")

    j1 = Rotator3(axis=np.array([0.0, 0.0, 1.0]), parent=link0, name="j1")
    ee = Transform3(parent=j1.output, local_pose=Pose3.translation(1.0, 0.0, 0.0), name="ee")

    # Уводим конфигурацию от сингулярного положения, чтобы Якобиан был полноранговым.
    j0.set_coord(0.1)
    j1.set_coord(-0.1)

    return base, ee, j0, j1


def _build_multi_branch_tree():
    base = Transform3(name="base")

    waist = Rotator3(axis=np.array([0.0, 0.0, 1.0]), parent=base, name="waist")
    torso = Transform3(parent=waist.output, local_pose=Pose3.translation(0.0, 0.0, 0.3), name="torso")

    left_mount = Transform3(parent=torso, local_pose=Pose3.translation(-0.15, 0.0, 0.0), name="left_mount")
    j_left_shoulder = Rotator3(axis=np.array([0.0, 1.0, 0.0]), parent=left_mount, name="l_sh")
    j_left_elbow = Rotator3(axis=np.array([0.0, 1.0, 0.0]), parent=j_left_shoulder.output, name="l_el")
    left_ee = Transform3(parent=j_left_elbow.output, local_pose=Pose3.translation(0.0, 0.0, 0.25), name="left_ee")

    right_mount = Transform3(parent=torso, local_pose=Pose3.translation(0.15, 0.0, 0.0), name="right_mount")
    j_right_shoulder = Rotator3(axis=np.array([0.0, 1.0, 0.0]), parent=right_mount, name="r_sh")
    j_right_elbow = Rotator3(axis=np.array([0.0, 1.0, 0.0]), parent=j_right_shoulder.output, name="r_el")
    right_ee = Transform3(parent=j_right_elbow.output, local_pose=Pose3.translation(0.0, 0.0, 0.25), name="right_ee")

    leg_mount = Transform3(parent=base, local_pose=Pose3.translation(0.0, 0.0, -0.2), name="leg_mount")
    j_leg = Rotator3(axis=np.array([1.0, 0.0, 0.0]), parent=leg_mount, name="leg_joint")
    Transform3(parent=j_leg.output, local_pose=Pose3.translation(0.0, 0.0, -0.4), name="leg_tip")

    joints = {
        "waist": waist,
        "l_sh": j_left_shoulder,
        "l_el": j_left_elbow,
        "r_sh": j_right_shoulder,
        "r_el": j_right_elbow,
        "leg": j_leg,
    }
    effectors = {"left": left_ee, "right": right_ee}
    return base, joints, effectors


def test_robot_sensitivity_matches_chain():
    base, ee, *_ = _build_two_link_tree()
    robot = Robot(base)

    chain = KinematicChain3(distal=ee, proximal=base)
    chain_twists = chain.sensitivity_twists(topbody=ee)
    chain_units = chain.kinunits()

    robot_twists = robot.sensitivity_twists(ee)
    assert set(robot_twists.keys()) == set(chain_units)

    # 1 DOF на сустав → массивы сравниваем по одному твисту
    for joint, screw in zip(chain_units, chain_twists):
        joint_twist = robot_twists[joint][0]
        np.testing.assert_allclose(joint_twist.ang, screw.ang, atol=1e-9)
        np.testing.assert_allclose(joint_twist.lin, screw.lin, atol=1e-9)

    expected = np.zeros((6, robot.dofs))
    for joint, twists in robot_twists.items():
        sl = robot.joint_slice(joint)
        for i, twist in enumerate(twists):
            expected[0:3, sl.start + i] = twist.ang
            expected[3:6, sl.start + i] = twist.lin

    np.testing.assert_allclose(robot.jacobian(ee), expected, atol=1e-9)


def test_robot_handles_branching_indices():
    base, ee, j0, j1, j_branch = _build_two_link_tree()
    robot = Robot(base)

    twists = robot.sensitivity_twists(ee)
    assert set(twists.keys()) == {j0, j1}

    jac = robot.jacobian(ee)
    branch_slice = robot.joint_slice(j_branch)
    np.testing.assert_allclose(jac[:, branch_slice], np.zeros((6, branch_slice.stop - branch_slice.start)), atol=1e-12)


def test_robot_multi_branch_selection():
    base, joints, effectors = _build_multi_branch_tree()
    robot = Robot(base)

    left_twists = robot.sensitivity_twists(effectors["left"])
    assert set(left_twists.keys()) == {joints["waist"], joints["l_sh"], joints["l_el"]}

    right_twists = robot.sensitivity_twists(effectors["right"])
    assert set(right_twists.keys()) == {joints["waist"], joints["r_sh"], joints["r_el"]}

    left_jac = robot.jacobian(effectors["left"])
    right_jac = robot.jacobian(effectors["right"])

    for irrelevant in ["r_sh", "r_el", "leg"]:
        sl = robot.joint_slice(joints[irrelevant])
        np.testing.assert_allclose(left_jac[:, sl], 0.0, atol=1e-12)

    for irrelevant in ["l_sh", "l_el", "leg"]:
        sl = robot.joint_slice(joints[irrelevant])
        np.testing.assert_allclose(right_jac[:, sl], 0.0, atol=1e-12)

    waist_slice = robot.joint_slice(joints["waist"])
    assert np.linalg.norm(left_jac[:, waist_slice]) > 0
    assert np.linalg.norm(right_jac[:, waist_slice]) > 0


def test_robot_integrate_joint_speeds():
    base, joints, _ = _build_multi_branch_tree()
    robot = Robot(base)

    speeds = np.zeros(robot.dofs)
    slice_leg = robot.joint_slice(joints["leg"])
    speeds[slice_leg] = 1.5  # rad/s
    slice_waist = robot.joint_slice(joints["waist"])
    speeds[slice_waist] = -0.25

    robot.integrate_joint_speeds(speeds, dt=0.2)

    assert np.isclose(joints["leg"].get_coord(), 0.3)
    assert np.isclose(joints["waist"].get_coord(), -0.05)


def test_robot_hqp_reaches_point():
    base, ee, *_ = _build_two_link_tree()
    robot = Robot(base)

    target = np.array([0.08, 0.08, 0.56])
    dt = 0.2

    for _ in range(60):
        current = ee.global_pose().lin
        err = target - current
        if np.linalg.norm(err) < 1e-4:
            break

        solver = HQPSolver(n_vars=robot.dofs)
        lvl = Level(priority=0)
        J = robot.translation_jacobian(ee)
        lvl.add_task(QuadraticTask(J, err))
        solver.add_level(lvl)

        delta = solver.solve()
        robot.integrate_joint_speeds(delta, dt)

    assert np.linalg.norm(target - ee.global_pose().lin) < 5e-3


def test_robot_hqp_reaches_point_2():
    base, ee, *_ = _build_two_link_tree_2()
    robot = Robot(base)

    target = np.array([0.5, 0.5, 0.0])
    dt = 0.2

    for _ in range(600):
        current = ee.global_pose().lin
        err = target - current
        if np.linalg.norm(err) < 1e-4:
            break

        solver = HQPSolver(n_vars=robot.dofs)
        lvl = Level(priority=0)
        J = robot.translation_jacobian(ee)
        assert J.shape == (3, 2)

        signal = err * 0.1
        lvl.add_task(QuadraticTask(J, signal))
        solver.add_level(lvl)

        delta = solver.solve()
        robot.integrate_joint_speeds(delta, dt)

        print(f"EE pos: {ee.global_pose().lin}, err norm: {np.linalg.norm(err)}")
    
    assert np.linalg.norm(target - ee.global_pose().lin) < 5e-3
