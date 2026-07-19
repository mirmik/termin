# termin-components-mesh

Mesh component package for attaching mesh data to entities.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-mesh](../../../termin-mesh/docs/index.md)
- [termin-scene](../../../termin-scene/docs/index.md)

## Основные области

- Component headers in `components/`.
- Build and packaging metadata in `CMakeLists.txt` / `setup.py`.

## Публичный API

Python package is installed as part of the Termin component packages. Canonical import naming is tracked in [canonical naming](../../../docs/architecture/2026-03-15-canonical-naming.md).

## Mesh publication contract

`MeshComponent` различает asset-backed и generated geometry:

- `set_mesh()` публикует обычную сериализуемую asset-ссылку;
- `set_generated_mesh()` публикует derived mesh, чей transient handle не
  сериализуется и должен быть восстановлен компонентом-провайдером;
- после изменения данных существующего `TcMesh` in-place провайдер обязан
  вызвать `notify_mesh_changed()`.

Каждая публикация увеличивает `mesh_revision` и отправляет scene-local событие
`termin.mesh_component.changed`. Потребители CPU geometry, включая
`ColliderComponent`, должны перестраивать производные данные по этому событию,
а не полагаться на порядок `on_added()` или опрашивать mesh каждый кадр.
