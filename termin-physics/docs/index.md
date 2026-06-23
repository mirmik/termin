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
