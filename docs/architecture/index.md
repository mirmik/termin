# Architecture Notes

Этот раздел хранит cross-module архитектурные заметки и правила, которые не принадлежат одному конкретному модулю.

Для module-local архитектуры используйте `<module>/docs/`. Для исторических планов и чеклистов используйте [plans](../plans/index.md).

## Current Notes

- [Canonical naming](2026-03-15-canonical-naming.md) - канонические Python namespace'ы и правила импортов.
- [Architecture TODO](2026-03-16-architecture-todo.md) - открытые архитектурные вопросы.
- [Scene rendering lifecycle](2026-05-07-scene-rendering-lifecycle.md) - заметки по lifecycle scene rendering.
- [Clip space policy](2026-06-26-clip-space-policy.md) - целевая политика `TerminClip -> NativeClip` и план миграции 3D render paths.
- [UI storage and plot annotations](2026-07-07-ui-storage-and-plot-annotations.md) - целевая модель владения UI-виджетами и границы plot annotations.
