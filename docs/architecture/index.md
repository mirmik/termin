# Architecture Notes

Этот раздел хранит cross-module архитектурные заметки и правила, которые не принадлежат одному конкретному модулю.

Для module-local архитектуры используйте `<module>/docs/`. Для исторических планов и чеклистов используйте [plans](../plans/index.md).

## Current Notes

- [Canonical naming](2026-03-15-canonical-naming.md) - канонические Python namespace'ы и правила импортов.
- [Architecture TODO](2026-03-16-architecture-todo.md) - открытые архитектурные вопросы.
- [Scene rendering lifecycle](2026-05-07-scene-rendering-lifecycle.md) - заметки по lifecycle scene rendering.
- [Clip space policy](2026-06-26-clip-space-policy.md) - целевая политика `TerminClip -> NativeClip` и план миграции 3D render paths.
- [UI storage and plot annotations](2026-07-07-ui-storage-and-plot-annotations.md) - целевая модель владения UI-виджетами и границы plot annotations.
- [Multilanguage component/pass/widget lifetime model](2026-07-09-multilanguage-component-lifetime-model.md) - направление для единой модели владения `tc_component`, `tc_pass` и `tc_widget`; связано с refcount/ownership cleanup задачами.
- [Native prefab runtime](2026-07-15-native-prefab-runtime.md) - Python-free prefab runtime, stable source identity, native instance reconciliation and editor/tooling boundaries.
- [Player host and embeddable runtime boundary](2026-07-15-player-and-runtime-boundary.md) - `termin-player` as an editor-adjacent CLI/Play Mode host versus `termin-runtime` as an editor-free embeddable native library.
- [Build profiles and product composition](2026-07-16-build-profiles-and-product-composition.md) - project-owned product recipes, typed target variants, explicit scene/module roots and the boundary between portable intent, local toolchains, resolved requests and artifact manifests.
- [Display render surface contract](2026-07-19-display-render-surface-contract.md) - целевая граница между `tc_display`, backend-neutral offscreen texture output, display-owned input routing и native window presentation.
- [Centralized frame memory](2026-07-21-centralized-frame-memory.md) - архитектурный набросок общей CPU frame arena, scoped scratch-регионов, telemetry и политики миграции hot-path allocations.
