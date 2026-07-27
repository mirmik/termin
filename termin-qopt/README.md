# termin-qopt

Quadratic optimization, FEM, multibody dynamics, and robotics helpers for Termin.

This package owns the `termin.fem`, `termin.linalg`, and `termin.robot`
namespaces. The current solver and model implementations remain Python-based
and are installed before `termin-physics-fem`, which embeds them into
experimental runtime/editor components.

The native migration foundation provides the shared C++ target
`termin_qopt::termin_qopt`, private Eigen integration, and preliminary
caller-owned dense vector/matrix views. Solver APIs and Python bindings have
not migrated yet; see [CPP_MIGRATION.md](CPP_MIGRATION.md).

`termin.robot.conditions` owns `SymCondition` and `ConditionCollection` because
they depend on the qopt linear-algebra stack. Base `termin.kinematic` remains
independent of `termin-qopt` and SciPy.
