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
  part of the contract.

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

Native tests should consume this JSON directly. A native solver conforms to a
QP case only when it returns the declared status and, for `optimal`, satisfies
the declared primal and KKT bounds. Exact multipliers, iteration counts,
factorization choices, and nullspace basis vectors are intentionally not
frozen.
