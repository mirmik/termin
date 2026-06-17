# FEM Tests

Tests for `termin.fem` in `termin-qopt`.

- `fem_test.py` — assembler, constraints, conditioning, simple systems.
- `mechanic_test.py` — bars, beams, triangular elements, body loads.
- `electric2_test.py` — electrical nodes, sources, R/L/C elements.
- `mbody2d_test.py`, `mbody3d_test.py` — multibody dynamics and constraints.
- `spatial_inertia2d_test.py`, `spatial_inertia3d_test.py` — spatial inertia.
- `doll2d_test.py` — articulated 2D body helpers.

Run with:

```bash
python -m pytest termin-qopt/tests/fem -v
```
