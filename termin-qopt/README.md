# termin-qopt

Quadratic optimization, FEM, multibody dynamics, and robotics helpers for Termin.

This package owns the `termin.fem`, `termin.linalg`, and `termin.robot`
namespaces. It is Python-only and is installed before packages that embed these
systems into runtime/editor components, such as `termin-physics`.

`termin.robot.conditions` owns `SymCondition` and `ConditionCollection` because
they depend on the qopt linear-algebra stack. Base `termin.kinematic` remains
independent of `termin-qopt` and SciPy.
