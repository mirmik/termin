# Native solver oracle

`solver_oracle.json` is a language-neutral mathematical contract for the
`termin-qopt` native migration. It is deliberately not a dump of values
returned by the current Python implementation.

The corpus contains three kinds of cases:

- QP cases define `H`, `g`, equalities, inequalities, a semantic status, and
  either a primal solution with KKT tolerances or a verifiable certificate.
- Nullspace cases define rank policy and basis-independent residual and
  orthogonality bounds. Implementations may return different bases.
- HQP cases define priority levels, an admissible primal result, and task
  residuals at every priority. Iteration counts and active-set ordering are not
  part of the contract. The robotics-oriented case uses a redundant Jacobian
  and verifies that a lower joint-space target moves only in its nullspace.

The objective and constraint conventions are stored at the document root.
Empty constraint matrices are encoded as `[]`; their column count is the
number of variables derived from `H` or `n_variables`.

## Relationship to the Python implementation

`solver_oracle_test.py` runs all `optimal` cases through the current Python
implementation and validates mathematical invariants. `infeasible`,
`unbounded`, and `invalid_input` cases are validated through their
certificates or structural error because the current Python API does not
return semantic statuses for them. This omission is a known contract gap, not
accepted legacy behavior.

Native tests consume all three sections through the generated C++ adapter. A
native solver conforms to a
QP case only when it returns the declared status and, for `optimal`, satisfies
the declared primal and KKT bounds. Exact multipliers, iteration counts,
factorization choices, and nullspace basis vectors are intentionally not
frozen.

## Multibody dynamics

`multibody_oracle.json` is a separate language-neutral dynamics corpus. It
records frame/order conventions, integration sampling, physical invariant
bounds and the migrate/reference/retire classification of the legacy Python
multibody modules. In particular, the old 3D `RevoluteJoint3D` is classified
as a point/ball joint because it does not constrain relative axes. The 3D
fixtures also certify off-center spatial inertia, world-frame gravity/free
fall, quaternion normalization, fixed-point behavior, a true five-row fixed
hinge, and a two-link 3D revolute pendulum. Hinge bounds cover anchor/axis
drift, the single allowed twist DOF, reaction work along that axis, and energy.
