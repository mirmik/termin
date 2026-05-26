# `termin.fem`

Python FEM, multibody dynamics, and electromechanics code used by `termin-qopt`
and the FEM runtime components in `termin-physics`.

## Core

- `assembler.py` — `Variable`, `Contribution`, constraints, Lagrange
  multipliers, global matrix assembly, diagnostics, and solve helpers.
- `dynamic_assembler.py` — dynamic system assembly and integration helpers.
- `mechanic.py` — structural mechanics elements: bars, beams, triangular
  elements, and body loads.

## Electrical And Electromechanical

- `electrical_2.py` — electrical nodes and R/L/C/source contributions.
- `electromechanic_2.py` — `DCMotor` coupling electrical and mechanical
  variables.

## Multibody

- `inertia2d.py`, `inertia3d.py` — spatial inertia utilities.
- `multibody2d_3.py` — 2D rigid bodies, external forces, fixed and revolute
  joints.
- `multibody3d_3.py` — 3D rigid bodies, external forces, fixed and revolute
  joints.
- `doll2d.py` — articulated 2D body helpers.

## Tests

Tests live in `termin-qopt/tests/fem/`.
