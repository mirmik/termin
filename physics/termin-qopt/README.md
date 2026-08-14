# termin-qopt

`termin-qopt` is Termin's solver-neutral dense quadratic-optimization
foundation. Its public C++ API contains no Eigen types; Eigen remains a private
backend dependency.

The native library exports:

- caller-owned dense vector and matrix views;
- deterministic dense block assembly;
- equality-constrained convex QP;
- active-set convex QP with equalities, inequalities and variable bounds;
- QR/SVD nullspace basis and projector helpers;
- strict lexicographic `HierarchicalQpSolver` levels.

It deliberately contains no rigid bodies, contacts, motors, integration or
scene components. Those live in `termin-physics-qopt`. The solver-neutral
articulation tree and future task-based control APIs live in
`termin-robotics`.

```text
termin-qopt
    ↑                 ↑
termin-robotics   termin-physics-qopt
    ↑                 ↑
task control      physical simulation
```

`HierarchicalQpSolver` is a tested dense foundation rather than a complete
robot controller. Its implemented semantics and known gaps are recorded in
[HQP_STATUS.md](HQP_STATUS.md).

The language-neutral QP/HQP oracle is
[`tests/oracle/solver_oracle.json`](tests/oracle/solver_oracle.json). The
legacy Python `termin.fem`, `termin.linalg` and `termin.robot` namespaces remain
in this distribution as research/reference implementations; native runtime
physics does not import them.

The migration history and numerical contracts are documented in
[CPP_MIGRATION.md](CPP_MIGRATION.md).
