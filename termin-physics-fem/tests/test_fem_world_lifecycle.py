from types import SimpleNamespace


def test_fem_world_destroy_releases_solver_component_graph() -> None:
    from termin.physics_fem import (
        FEMFixedJointComponent,
        FEMPhysicsWorldComponent,
        FEMRevoluteJointComponent,
        FEMRigidBodyComponent,
    )

    world = FEMPhysicsWorldComponent()
    body = FEMRigidBodyComponent()
    fixed_joint = FEMFixedJointComponent()
    revolute_joint = FEMRevoluteJointComponent()

    world._initialized = True
    world._scene = SimpleNamespace()
    world._assembler = SimpleNamespace()
    world._bodies.append(body)
    world._fixed_joints.append(fixed_joint)
    world._revolute_joints.append(revolute_joint)

    body._fem_world = world
    body._fem_body = SimpleNamespace()
    fixed_joint._fem_world = world
    fixed_joint._fem_joint = SimpleNamespace()
    fixed_joint._body_component = body
    revolute_joint._fem_world = world
    revolute_joint._fem_joint = SimpleNamespace()
    revolute_joint._body_a_component = body
    revolute_joint._body_b_component = body

    world.on_destroy()

    assert not world._initialized
    assert world._scene is None
    assert world.assembler is None
    assert world._bodies == []
    assert world._fixed_joints == []
    assert world._revolute_joints == []
    assert body._fem_world is None
    assert body.fem_body is None
    assert fixed_joint._fem_world is None
    assert fixed_joint._fem_joint is None
    assert fixed_joint._body_component is None
    assert revolute_joint._fem_world is None
    assert revolute_joint._fem_joint is None
    assert revolute_joint._body_a_component is None
    assert revolute_joint._body_b_component is None
