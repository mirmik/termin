# termin-physics

`termin-physics` содержит C++ rigid-body physics bindings.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-physics)
- [termin-collision](../../termin-collision/docs/index.md)
- [termin-physics-fem](../../termin-physics-fem/docs/index.md)

## Основные области

- Public headers в `include/`.
- C++/binding code в `cpp/`.
- Implementation в `src/`.
- Python package в `python/termin/physics`.

## Публичный API

Python package: `termin.physics` через пакет `termin-physics`.

Experimental Python FEM scene components live in `termin.physics_fem` via the
separate `termin-physics-fem` package. `termin-physics` must not depend on
`termin-qopt`/`scipy`.

Collision primitives and collision world API описаны отдельно в [termin-collision](../../termin-collision/docs/index.md).

## Mass properties

`compute_mass_properties(collider, entity_scale, mass)` computes uniform-density
mass properties from the same effective local geometry used by
`AttachedCollider`. Box and sphere use analytic formulas. Capsule is treated as
a cylinder plus two solid hemispheres; its radius uses the minimum radial scale
and its cylindrical half-height uses the local Z scale. Convex hull properties
are integrated over the closed triangular surface, including a displaced
center of mass and rotated principal axes.

`RigidBody.pose.lin` is always the world center of mass. `pose.ang` remains the
authored shape/entity orientation, while `inertia_frame_local` stores the local
center of mass and principal-axis rotation. Use `shape_pose()` and
`set_shape_pose()` when synchronizing an authored transform. Degenerate,
non-finite, non-positive or unsupported geometry is rejected explicitly; it is
never replaced with box inertia.
