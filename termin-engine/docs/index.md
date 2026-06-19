# termin-engine

`termin-engine` содержит engine-level orchestration поверх scene/render/input/domain modules.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-engine)
- [Engine Managers](managers.md)
- [EngineCore](engine-core.md)
- [SceneManager](scene-manager.md)
- [RenderingManager](rendering-manager.md)
- [ViewportRenderState](viewport-render-state.md)
- [termin-scene](../../termin-scene/docs/index.md)
- [termin-render](../../termin-render/docs/index.md)

## Основные области

- Public headers в `include/`.
- Engine implementation в `src/`.
- Python bindings в `bindings/`.
- Python package в `python/termin/engine`.

## Ключевые классы

- [EngineCore](engine-core.md) - runtime owner и frame loop.
- [SceneManager](scene-manager.md) - registry/lifecycle/update cycle сцен.
- [RenderingManager](rendering-manager.md) - displays, viewports, render targets, pipelines и presentation.
- [ViewportRenderState](viewport-render-state.md) - GPU output state для viewport/render target.
- `register_default_scene_extensions` / `create_scene_with_render` - engine-level helpers для render-enabled scene lifecycle и регистрации render/collision extensions.
- `TermModulesIntegration` - связывает `termin_modules::ModuleRuntime` с live scenes: при unload module деградирует module-owned components в unknown components, при load пробует поднять их обратно.

Подробнее: [Engine Managers](managers.md).

## Публичный API

Python package: `termin.engine` через пакет `termin-engine`. Module runtime integration доступна как `termin.engine.TermModulesIntegration` и `termin.engine.modules.TermModulesIntegration`.

Модуль связывает нижележащие подсистемы, но не является application/editor слоем. Application policy живет в `termin-app`.
