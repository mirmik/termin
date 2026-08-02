# termin-qopt

Quadratic optimization, FEM, multibody dynamics, and robotics helpers for Termin.

The native `termin_qopt::termin_qopt` library is the current runtime foundation
for dense optimization and contribution-based multibody dynamics. The
`termin.fem`, `termin.linalg`, and `termin.robot` Python namespaces remain in
this package as research/reference implementations; the native FEM scene
components do not import them or NumPy at runtime.

The native migration foundation provides the shared C++ target
`termin_qopt::termin_qopt`, private Eigen integration, and caller-owned dense
vector/matrix views. Native equality and active-set QP APIs cover convex dense
problems, semantic statuses, rank diagnostics, KKT residuals, inequalities,
bounds, checked warm starts, and Phase I infeasibility detection.

Native subspace helpers expose QR-first orthonormal nullspace bases and
projectors through fixed-capacity caller-owned matrices; SVD is an explicit
rank-deficient policy rather than an implicit ABI choice. The native
`HierarchicalQpSolver` owns copied task/constraint data, solves priorities in
ascending order through the active-set API, accumulates hard constraints, and
restricts each lower level to directions preserving higher-level task values.
Rank exhaustion and incompatible lower levels return explicit statuses.
The implementation is usable as a tested foundation, but is not yet integrated
into a robot controller or the multibody step. Its exact scope and remaining
gaps are recorded in [HQP_STATUS.md](HQP_STATUS.md).

The first end-to-end multibody slice is also native: deterministic dense block
assembly, typed dynamics assembly for `M a = f + Jᵀ λ`, and a maximal-coordinate
2D rigid-body system with fixed-point and revolute joints. Its public model API
uses `termin-base` value types and does not expose either Eigen or assembled
matrices. The double-pendulum example and tests exercise assembly, constrained
solve, semi-implicit integration, position/velocity projection, reactions,
constraint drift, and energy drift.

The native 3D foundation uses the same pipeline with right-trivialized,
body-local `[linear, angular]` velocities and accelerations, constant local
spatial inertia, SE(3) exponential updates, and fixed/two-body point joints.
`termin::SpatialInertia3`, `termin::se3_exp()`, and `termin::se3_log()` are
shared `termin-base` primitives; qopt owns only their dense assembly boundary
and the equations of its concrete contributions.
Twists, accelerations, wrenches, and joint reactions use the common
`termin::Screw3` pair. Frame and origin changes operate on that pair through
adjoint/coadjoint transforms; the dense assembler alone maps it explicitly to
its internal `[linear, angular]` row order.
The public names include the reference point: body velocity is exposed as
`velocity_at_body_origin_world()`, external load as
`wrench_at_body_origin_world()`, and a constraint reaction as
`reaction_at_joint_anchor_world()`. These are not spatial twists or wrenches
reduced to the world origin.
Gravity, external wrenches, poses, joint anchors, constraint rows, and reactions
cross the model boundary in their explicitly named world or local frames. A
point joint constrains only coincident anchors and intentionally leaves three
relative rotational degrees of freedom. Fixed and two-body revolute joints add
two axis-alignment rows, leaving exactly one relative twist DOF, and expose the
anchor force plus the axis-orthogonal reaction torque. The legacy Python
`RevoluteJoint3D` remains reference-only and is retired as a model name because
that class is only a point joint; the native revolute contract is intentionally
stricter. Native solver/model Python bindings have not migrated; see
[CPP_MIGRATION.md](CPP_MIGRATION.md).

The first reduced-coordinate articulation slice is native as well.
`Articulation3DContribution` represents a fixed-base tree as one generalized
DOF block with one scalar coordinate per link joint. Each link stores the
parent-to-zero-joint pose, a local one-DOF motion twist, the joint-to-link pose,
and spatial inertia. Forward kinematics uses `Exp(S q)` and inverse dynamics
uses a recursive Newton-Euler pass. The current correctness backend obtains the
dense reduced mass matrix by repeated inverse-dynamics passes, so it already
fits the generic `DynamicsSystem` contract while leaving CRBA as an internal
optimization. Internal tree joints need no constraint rows or projection.
Analytic revolute/prismatic equations, branching, energy, and a
double-pendulum comparison against the maximal-coordinate model are covered by
native tests. Optional per-link minimum and maximum coordinates become
transient velocity inequalities only when reached or predictively crossed;
their public state reports separate reactions and active flags without
clamping the coordinate after integration.

The solver-neutral `PointKinematics3D` contract now gives a static world point,
a material point on `RigidBody3DContribution`, or a material point on any
`Articulation3DContribution` link the same representation: world position,
world linear velocity, the owning DOF block, and a row-major `3 x n` generalized
Jacobian. `map_force_to_generalized_effort()` applies `J^T` without exposing
Eigen. The model owner keeps local spatial-vector conventions internal; contact
contributions can consume the result without knowing the coordinate
formulation. Native tests verify `J qdot`, finite-difference columns on a
branching tree, the virtual-work identity, static zero-DOF behavior, and error
diagnostics.

Frictionless normal contact is the next implemented native slice.
`ContactSet3DContribution` accepts caller-keyed pairs of static, maximal-body,
or articulation-link endpoints together with a unit world normal and signed
gap. It registers transient `C v <= d` rows each step, exposes the resulting
normal impulse/reaction and tight-row state, and has no dependency on scene
entities, colliders, or Eigen. Penetration uses split position projection:
configuration correction is solved in the mass metric, while the physical
midpoint velocity is preserved until the separate unilateral velocity solve.
Consequently correction does not manufacture rebound energy. Native tests
cover exact Jacobian signs, mixed endpoint formulations, penetration recovery,
impact, resting support, separation, contact removal, and invalid transactional
input. Collision-world adaptation, persistent manifold matching, warm starts,
and friction remain later integration slices.

The separate
`termin-components-physics-fem` layer now compiles
an explicit root/joint/body entity hierarchy into this public model and keeps
solved joint coordinates synchronized with `RotatorComponent` or
`ActuatorComponent`. Floating bases, collision-world contact adaptation, and a
linear-time dynamics backend remain subsequent slices.

The language-neutral solver contract lives in
[`tests/oracle/solver_oracle.json`](tests/oracle/solver_oracle.json). It records
analytic solutions, KKT bounds, infeasibility/unboundedness certificates,
nullspace invariants, and HQP priority outcomes without freezing Python
iteration counts or implementation details.

The multibody migration contract lives in
[`tests/oracle/multibody_oracle.json`](tests/oracle/multibody_oracle.json).
It fixes coordinate and constraint conventions, classifies the legacy Python
models, and supplies free-fall, anchored-body, fixed-hinge, and 2D/3D
double-pendulum fixtures shared by Python and native tests.

`termin.robot.conditions` owns `SymCondition` and `ConditionCollection` because
they depend on the qopt linear-algebra stack. Base `termin.kinematic` remains
independent of `termin-qopt` and SciPy.
