# termin-qopt

Quadratic optimization, FEM, multibody dynamics, and robotics helpers for Termin.

This package owns the `termin.fem`, `termin.linalg`, and `termin.robot`
namespaces. The current solver and model implementations remain Python-based
and are installed before `termin-physics-fem`, which embeds them into
experimental runtime/editor components.

The native migration foundation provides the shared C++ target
`termin_qopt::termin_qopt`, private Eigen integration, and preliminary
caller-owned dense vector/matrix views. A provisional native equality-QP API
now covers convex dense problems, semantic statuses, rank diagnostics, and KKT
residuals. The provisional native active-set API adds linear inequalities,
lower/upper bounds, checked warm starts, deterministic working-set updates, and
Phase I infeasibility detection. Python bindings have not migrated yet; see
[CPP_MIGRATION.md](CPP_MIGRATION.md).

The language-neutral solver contract lives in
[`tests/oracle/solver_oracle.json`](tests/oracle/solver_oracle.json). It records
analytic solutions, KKT bounds, infeasibility/unboundedness certificates,
nullspace invariants, and HQP priority outcomes without freezing Python
iteration counts or implementation details.

`termin.robot.conditions` owns `SymCondition` and `ConditionCollection` because
they depend on the qopt linear-algebra stack. Base `termin.kinematic` remains
independent of `termin-qopt` and SciPy.
