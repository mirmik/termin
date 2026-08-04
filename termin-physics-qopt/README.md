# termin-physics-qopt

`termin-physics-qopt` is the physical simulation layer built on
`termin-qopt`. It owns the contribution-based dynamics problem, physical
contacts and time stepping; it does not own robot-control policy.

The native library contains:

- `DynamicsSystem` and typed topology/assembly contracts;
- maximal-coordinate 2D and 3D rigid bodies and joints;
- `Articulation3DDynamicsContribution`, which borrows a
  `termin::robotics::Articulation3D`;
- bounded articulation motor efforts;
- unilateral contacts, persistence and warm-start state;
- the Coulomb-friction approximation;
- acceleration solve, integration, position/velocity projection and
  transactional rollback.

Its dependency direction is:

```text
termin-qopt          termin-robotics
        \             /
         termin-physics-qopt
                    ↑
     termin-components-physics-fem
```

Physical types live in `termin::physics_qopt` and are included through
`<termin/physics_qopt/...>`. Numerical solver types remain in `termin::qopt` and
are included through `<termin/qopt/...>`.

The multibody oracle and native regression corpus live under `tests/`. The
separate scene-component module compiles authored entities into these physical
contributions.
