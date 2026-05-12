# Termin Documentation Hub

Документация монорепозитория **Termin** — 3D-движка с ECS-архитектурой, физикой, рендерингом, анимацией и навигацией.

---

## Как поддерживается документация

- [Documentation System](./documentation-system.md) — где должны жить разные типы документов.
- [Module Map](./modules.md) — границы ответственности модулей и правила переноса кода.
- [Architecture Notes](./architecture/index.md) — cross-module архитектурные заметки.
- [Plans And Migration Notes](./plans/index.md) — исторические планы и миграционные чеклисты.
- [Главный вход Obsidian](../docs.md) — навигационная страница vault.

## Проекты

| Проект | Описание |
|--------|----------|
| [termin-app](./modules.md#termin-app) | Основное приложение/редактор |
| [termin-base](../termin-base/docs/index.md) | Базовые типы, logging, settings, geometry, low-level utilities |
| [termin-mesh](../termin-mesh/docs/index.md) | Canonical mesh/resource data layer |
| [termin-graphics](../termin-graphics/docs/index.md) | tgfx/tgfx2, backend-neutral GPU API |
| [termin-render](../termin-render/docs/index.md) | Render framework, pipelines, frame graph |
| [termin-display](../termin-display/docs/index.md) | Windows/display/platform integration |
| [termin-inspect](../termin-inspect/docs/index.md) | Система инспекции: Kind-типы, рефлексия полей, сериализация C/C++/Python |
| [termin-scene](../termin-scene/docs/index.md) | ECS-сцена: Entity, Component, SoA-хранилище, хэндлы, lifecycle |
| [termin-collision](../termin-collision/docs/index.md) | Коллизии: GJK, коллайдеры, collision world, C/Python API |
| [termin-physics](../termin-physics/docs/index.md) | Physics-domain bindings |
| [termin-input](../termin-input/docs/index.md) | Input abstractions |
| [termin-gui](../termin-gui/docs/index.md) | UI фреймворк (tcgui): виджеты, лейауты, диалоги, Canvas/Viewport |
| [termin-modules](../termin-modules/docs/index.md) | Система модулей: C++/Python плагины, дескрипторы, lifecycle, callbacks |
| [termin-components](../termin-components/docs/index.md) | Component packages |
| [tcplot](../tcplot/docs/index.md) | Plotting library поверх tgfx/tcgui |

## Архитектура

- [Граф зависимостей библиотек](./library-dependencies.md)
- [Карта модулей](./modules.md)
- [Архитектурные заметки](./architecture/index.md)
