# Termin Documentation Hub

Документация монорепозитория **Termin** — 3D-движка с ECS-архитектурой, физикой, рендерингом, анимацией и навигацией.

---

## Как поддерживается документация

- [Documentation System](./documentation-system.md) — где должны жить разные типы документов.
- [Module Map](./modules.md) — границы ответственности модулей и правила переноса кода.
- [Linting And Static Analysis](./linting.md) — общий план Python и C/C++ lint/static-analysis.
- [Python Linting](./python-linting.md) — Ruff baseline для Python-кода.
- [C++ Style Guide](./cpp-style.md) — порядок членов C++-классов и структур.
- [Code Duplication Check](./code-duplication.md) — jscpd-прогон для поиска copy/paste-дублей.
- [Render Phase Semantics](./render-phase-semantics.md) — контракт `phase_mark`, pass-owned shader contracts, allowed/forbidden responsibilities.
- [SDK Python Wheelhouse](./sdk-python-wheelhouse.md) — wheels из SDK для внешних Python-проектов.
- [Python Package Naming](./python-package-naming.md) — canonical source path / distribution / import namespace policy.
- [Taskboard CLI](./taskboard-tool.md) — использование глобального Kanboard-инструмента для доски Termin.
- [Taskboard Guidelines](./taskboard-guidelines.md) — короткие правила ведения Kanboard-карточек.
- [Native Editor UI Style Guide](./ui/native-editor-ui-style-guide.md) — визуальные токены и правила композиции `termin-gui-native`.
- [Architecture Notes](./architecture/index.md) — cross-module архитектурные заметки.
- [Plans And Migration Notes](./plans/index.md) — исторические планы и миграционные чеклисты.
- [Главный вход Obsidian](https://github.com/mirmik/termin-monorepo/blob/master/docs.md) — навигационная страница vault.

## Проекты

| Проект | Описание |
|--------|----------|
| [termin-app](./modules.md#termin-app) | Основное приложение/редактор |
| [termin-base](https://github.com/mirmik/termin-monorepo/blob/master/termin-base/docs/index.md) | Базовые типы, logging, settings, geometry, low-level utilities |
| [termin-mesh](https://github.com/mirmik/termin-monorepo/blob/master/termin-mesh/docs/index.md) | Canonical mesh/resource data layer |
| [termin-default-assets](https://github.com/mirmik/termin-monorepo/blob/master/termin-default-assets/docs/index.md) | Default asset adapters for domain packages |
| [termin-graphics](https://github.com/mirmik/termin-monorepo/blob/master/termin-graphics/docs/index.md) | tgfx/tgfx2, backend-neutral GPU API |
| [termin-render](https://github.com/mirmik/termin-monorepo/blob/master/termin-render/docs/index.md) | Render framework, pipelines, frame graph |
| [termin-display](https://github.com/mirmik/termin-monorepo/blob/master/termin-display/docs/index.md) | Windows/display/platform integration |
| [termin-inspect](https://github.com/mirmik/termin-monorepo/blob/master/termin-inspect/docs/index.md) | Система инспекции: Kind-типы, рефлексия полей, сериализация C/C++/Python |
| [termin-scene](https://github.com/mirmik/termin-monorepo/blob/master/termin-scene/docs/index.md) | ECS-сцена: Entity, Component, SoA-хранилище, хэндлы, lifecycle |
| [termin-collision](https://github.com/mirmik/termin-monorepo/blob/master/termin-collision/docs/index.md) | Коллизии: GJK, коллайдеры, collision world, C/Python API |
| [termin-physics](https://github.com/mirmik/termin-monorepo/blob/master/termin-physics/docs/index.md) | C++ rigid-body physics bindings |
| [termin-physics-fem](https://github.com/mirmik/termin-monorepo/blob/master/termin-physics-fem/docs/index.md) | Experimental Python FEM scene components |
| [termin-input](https://github.com/mirmik/termin-monorepo/blob/master/termin-input/docs/index.md) | Input abstractions |
| [termin-gui](https://github.com/mirmik/termin-monorepo/blob/master/termin-gui/docs/index.md) | UI фреймворк (tcgui): виджеты, лейауты, диалоги, Canvas/Viewport |
| [termin-modules](https://github.com/mirmik/termin-monorepo/blob/master/termin-modules/docs/index.md) | Система модулей: C++/Python плагины, дескрипторы, lifecycle, callbacks |
| [termin-components](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/docs/index.md) | Component packages |
| [tcplot](https://github.com/mirmik/termin-monorepo/blob/master/tcplot/docs/index.md) | Plotting library поверх tgfx/tcgui |

## Архитектура

- [Граф зависимостей библиотек](./library-dependencies.md)
- [Карта модулей](./modules.md)
- [Архитектурные заметки](./architecture/index.md)
