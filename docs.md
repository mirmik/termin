# Termin Docs

Главный вход в документацию репозитория для Obsidian и обычного Markdown.

## Маршруты

- [Documentation System](docs/documentation-system.md) - правила, по которым поддерживается документация.
- [Module Map](docs/modules.md) - карта модулей, границы ответственности и ссылки на локальные docs.
- [Architecture Index](docs/index.md) - существующий верхнеуровневый индекс.
- [Architecture Notes](docs/architecture/index.md) - cross-module архитектурные заметки.
- [Library Dependencies](docs/library-dependencies.md) - граф зависимостей модулей.

## Живые области

- [termin-graphics](termin-graphics/docs/index.md) - tgfx/tgfx2, GPU runtime, render-device abstraction.
- [termin-render](docs/modules.md#termin-render) - render framework поверх canonical engine resources.
- [termin-gui](termin-gui/docs/index.md) - tcgui widgets, layout, dialogs, canvas.
- [tcplot](docs/modules.md#tcplot) - plotting поверх tgfx/tcgui.
- [termin-scene](termin-scene/docs/index.md) - scene/ECS ownership, handles, lifecycle.
- [termin-inspect](termin-inspect/docs/index.md) - inspect/kind/field metadata.
- [termin-collision](termin-collision/docs/index.md) - collision world, colliders, algorithms.
- [termin-modules](termin-modules/docs/index.md) - module descriptors, lifecycle, callbacks.

## Рабочие заметки

- [Plans](docs/plans/index.md) - временные планы и миграционные заметки.
- [Architecture TODO](docs/architecture/2026-03-16-architecture-todo.md) - исторический список архитектурных задач.
