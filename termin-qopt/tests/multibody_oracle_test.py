import json
import math
from pathlib import Path

import numpy as np

from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.fem.inertia2d import SpatialInertia2D
from termin.fem.multibody2d_3 import (
    FixedRotationJoint2D,
    RevoluteJoint2D,
    RigidBody2D,
)
from termin.geombase import Vec2
from termin.geombase.pose2 import Pose2


ORACLE_PATH = Path(__file__).parent / "oracle" / "multibody_oracle.json"


def _load_oracle() -> dict:
    return json.loads(ORACLE_PATH.read_text(encoding="utf-8"))


def _body(spec: dict, gravity: np.ndarray, assembler: DynamicMatrixAssembler):
    inertia = SpatialInertia2D(
        mass=spec["mass"],
        inertia=spec["inertia"],
        com=np.asarray(spec["center_of_mass_local"], dtype=float),
    )
    body = RigidBody2D(inertia=inertia, gravity=gravity, assembler=assembler)
    pose = spec["initial_pose"]
    body_pose = Pose2(ang=pose[2], lin=Vec2(pose[0], pose[1]))
    body.set_pose(body_pose)
    world_velocity = spec["initial_velocity"]
    local_linear = body_pose.inverse_rotate_vector(
        Vec2(world_velocity[0], world_velocity[1])
    )
    body.velocity_var.set_value(
        np.array([local_linear[0], local_linear[1], world_velocity[2]])
    )
    return body


def _step(assembler: DynamicMatrixAssembler) -> None:
    matrices = assembler.assemble()
    matrix, rhs, _ = assembler.assemble_extended_system(matrices)
    solution = np.linalg.solve(matrix, rhs)
    acceleration, _, _ = assembler.sort_results(solution)
    assembler.integrate_with_constraint_projection(acceleration, matrices)


def _pose_array(body: RigidBody2D) -> np.ndarray:
    pose = body.pose()
    return np.array([pose.lin[0], pose.lin[1], pose.ang], dtype=float)


def _world_velocity(body: RigidBody2D) -> np.ndarray:
    local = body.velocity_var.value
    linear = body.pose().rotate_vector(Vec2(local[0], local[1]))
    return np.array([linear[0], linear[1], local[2]], dtype=float)


def _energy(body: RigidBody2D, gravity: np.ndarray) -> float:
    pose = body.pose()
    velocity = body.velocity_var.value
    center_world = pose.transform_point(Vec2(*body.inertia.center_of_mass))
    kinetic = body.inertia.get_kinetic_energy(velocity[:2], velocity[2])
    potential = -body.inertia.mass * np.dot(
        gravity, np.array([center_world[0], center_world[1]])
    )
    return float(kinetic + potential)


def test_multibody_oracle_schema_and_classification():
    oracle = _load_oracle()
    assert oracle["schema_version"] == 1
    assert oracle["conventions"]["constraint"] == "J * acceleration = gamma"

    names = [case["name"] for case in oracle["cases"]]
    assert len(names) == len(set(names))
    for case in oracle["cases"]:
        assert case["time_step"] > 0.0
        assert case["steps"] > 0
        assert case["sample_steps"][0] == 0
        assert case["sample_steps"][-1] == case["steps"]
        assert case["sample_steps"] == sorted(set(case["sample_steps"]))

    classifications = {
        item["module"]: item["decision"]
        for item in oracle["legacy_classification"]
    }
    assert (
        classifications["termin.fem.multibody3d_3.RevoluteJoint3D"]
        == "retire-name"
    )


def test_3d_oracle_analytic_certificates():
    cases = {case["kind"]: case for case in _load_oracle()["cases"]}
    free_fall = cases["free_fall_3d"]
    inertia = free_fall["body"]["inertia"]
    mass = inertia["mass"]
    center = np.asarray(
        inertia["inertia_frame_local"]["translation"], dtype=float
    )
    skew = np.array(
        [
            [0.0, -center[2], center[1]],
            [center[2], 0.0, -center[0]],
            [-center[1], center[0], 0.0],
        ]
    )
    central = np.diag(inertia["principal_moments"])
    spatial = np.block(
        [
            [mass * np.eye(3), -mass * skew],
            [
                mass * skew,
                central
                + mass
                * (
                    np.dot(center, center) * np.eye(3)
                    - np.outer(center, center)
                ),
            ],
        ]
    )
    certificate = free_fall[
        "analytic_spatial_inertia_identity_orientation"
    ]
    np.testing.assert_allclose(
        np.diag(spatial), certificate["diagonal"], atol=1e-12
    )
    np.testing.assert_allclose(spatial, spatial.T, atol=1e-12)
    for entry in certificate["nonzero_upper_coupling"]:
        assert (
            spatial[entry["row"], entry["column"]]
            == entry["value"]
        )

    anchored = cases["anchored_point_3d"]
    pose = np.asarray(
        anchored["body"]["initial_pose"]["translation"], dtype=float
    )
    radius = np.asarray(
        anchored["fixed_point_joint"]["body_anchor_local"], dtype=float
    )
    world_anchor = np.asarray(
        anchored["fixed_point_joint"]["world_anchor"], dtype=float
    )
    linear = np.asarray(
        anchored["body"]["initial_velocity"]["linear_world"], dtype=float
    )
    angular = np.asarray(
        anchored["body"]["initial_velocity"]["angular_world"], dtype=float
    )
    np.testing.assert_allclose(pose + radius, world_anchor, atol=1e-12)
    np.testing.assert_allclose(
        linear + np.cross(angular, radius), np.zeros(3), atol=1e-12
    )
    assert anchored["fixed_point_joint"]["relative_rotational_dofs"] == 3

    fixed_hinge = cases["fixed_revolute_3d"]
    fixed_joint = fixed_hinge["fixed_revolute_joint"]
    fixed_pose = np.asarray(
        fixed_hinge["body"]["initial_pose"]["translation"], dtype=float
    )
    fixed_radius = np.asarray(
        fixed_joint["body_anchor_local"], dtype=float
    )
    fixed_linear = np.asarray(
        fixed_hinge["body"]["initial_velocity"]["linear_world"],
        dtype=float,
    )
    fixed_angular = np.asarray(
        fixed_hinge["body"]["initial_velocity"]["angular_world"],
        dtype=float,
    )
    np.testing.assert_allclose(
        fixed_pose + fixed_radius,
        fixed_joint["world_anchor"],
        atol=1e-12,
    )
    np.testing.assert_allclose(
        fixed_linear + np.cross(fixed_angular, fixed_radius),
        np.zeros(3),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        fixed_joint["body_axis_local"],
        fixed_joint["world_axis"],
        atol=1e-12,
    )
    assert fixed_joint["constraint_rows"] == 5
    assert fixed_joint["relative_rotational_dofs"] == 1

    double_hinge = cases["double_pendulum_revolute_3d"]
    bodies = double_hinge["bodies"]
    fixed = double_hinge["fixed_revolute_joint"]
    revolute = double_hinge["revolute_joint"]
    upper_pose = np.asarray(
        bodies[fixed["body"]]["initial_pose"]["translation"], dtype=float
    )
    lower_pose = np.asarray(
        bodies[revolute["body_b"]]["initial_pose"]["translation"],
        dtype=float,
    )
    np.testing.assert_allclose(
        upper_pose + np.asarray(fixed["body_anchor_local"]),
        fixed["world_anchor"],
        atol=1e-12,
    )
    np.testing.assert_allclose(
        upper_pose + np.asarray(revolute["body_a_anchor_local"]),
        lower_pose + np.asarray(revolute["body_b_anchor_local"]),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        revolute["body_a_axis_local"],
        revolute["body_b_axis_local"],
        atol=1e-12,
    )
    assert revolute["constraint_rows"] == 5
    assert revolute["relative_rotational_dofs"] == 1


def test_free_fall_oracle_against_python_reference():
    case = next(
        item for item in _load_oracle()["cases"] if item["kind"] == "free_fall_2d"
    )
    assembler = DynamicMatrixAssembler()
    assembler.time_step = case["time_step"]
    gravity = np.asarray(case["gravity"], dtype=float)
    body = _body(case["body"], gravity, assembler)

    initial_pose = _pose_array(body)
    initial_velocity = np.asarray(case["body"]["initial_velocity"], dtype=float)
    for _ in range(case["steps"]):
        _step(assembler)

    duration = case["steps"] * case["time_step"]
    expected_pose = initial_pose.copy()
    expected_pose[:2] += initial_velocity[:2] * duration
    expected_pose[:2] += 0.5 * gravity * duration**2
    expected_velocity = initial_velocity.copy()
    expected_velocity[:2] += gravity * duration
    tolerance = case["bounds"]["state_linf"]
    np.testing.assert_allclose(_pose_array(body), expected_pose, atol=tolerance)
    np.testing.assert_allclose(_world_velocity(body), expected_velocity, atol=1e-10)


def test_anchored_body_oracle_against_python_reference():
    case = next(
        item
        for item in _load_oracle()["cases"]
        if item["kind"] == "anchored_body_2d"
    )
    assembler = DynamicMatrixAssembler()
    assembler.time_step = case["time_step"]
    gravity = np.asarray(case["gravity"], dtype=float)
    body = _body(case["body"], gravity, assembler)
    joint = FixedRotationJoint2D(
        body=body,
        coords_of_joint=np.asarray(case["fixed_joint"]["world_anchor"]),
        assembler=assembler,
    )
    initial_energy = _energy(body, gravity)
    max_constraint = 0.0
    for _ in range(case["steps"]):
        _step(assembler)
        anchor = np.asarray(body.pose().transform_point(Vec2(*joint.r_local)))
        error = anchor - np.asarray(case["fixed_joint"]["world_anchor"])
        max_constraint = max(max_constraint, float(np.max(np.abs(error))))

    final_energy = _energy(body, gravity)
    relative_drift = abs(final_energy - initial_energy) / max(
        1.0, abs(initial_energy)
    )
    assert max_constraint <= case["bounds"]["constraint_linf"]
    assert relative_drift <= case["bounds"]["relative_energy_drift"]


def test_double_pendulum_oracle_against_python_reference():
    case = next(
        item
        for item in _load_oracle()["cases"]
        if item["kind"] == "double_pendulum_2d"
    )
    assembler = DynamicMatrixAssembler()
    assembler.time_step = case["time_step"]
    gravity = np.asarray(case["gravity"], dtype=float)
    bodies = [_body(spec, gravity, assembler) for spec in case["bodies"]]
    fixed = FixedRotationJoint2D(
        body=bodies[case["fixed_joint"]["body"]],
        coords_of_joint=np.asarray(case["fixed_joint"]["world_anchor"]),
        assembler=assembler,
    )
    revolute_world = np.asarray(
        bodies[0].pose().transform_point(
            Vec2(*case["revolute_joint"]["body_a_anchor_local"])
        )
    )
    revolute = RevoluteJoint2D(
        bodyA=bodies[case["revolute_joint"]["body_a"]],
        bodyB=bodies[case["revolute_joint"]["body_b"]],
        coords_of_joint=revolute_world,
        assembler=assembler,
    )

    initial_energy = sum(_energy(body, gravity) for body in bodies)
    max_constraint = 0.0
    sample_steps = set(case["sample_steps"])
    for step in range(case["steps"] + 1):
        if step in sample_steps:
            fixed_a = np.asarray(
                bodies[0].pose().transform_point(Vec2(*fixed.r_local))
            )
            joint_a = np.asarray(
                bodies[0].pose().transform_point(Vec2(*revolute.rA_local))
            )
            joint_b = np.asarray(
                bodies[1].pose().transform_point(Vec2(*revolute.rB_local))
            )
            max_constraint = max(
                max_constraint,
                float(
                    np.max(
                        np.abs(
                            fixed_a
                            - np.asarray(case["fixed_joint"]["world_anchor"])
                        )
                    )
                ),
                float(np.max(np.abs(joint_a - joint_b))),
            )
            for body in bodies:
                assert np.all(np.isfinite(_pose_array(body)))
                assert np.max(np.abs(_pose_array(body))) < case["bounds"][
                    "finite_state_limit"
                ]
        if step != case["steps"]:
            _step(assembler)

    final_energy = sum(_energy(body, gravity) for body in bodies)
    relative_drift = abs(final_energy - initial_energy) / max(
        1.0, abs(initial_energy)
    )
    assert max_constraint <= case["bounds"]["constraint_linf"]
    assert relative_drift <= case["bounds"]["relative_energy_drift"]
    assert math.isfinite(relative_drift)
