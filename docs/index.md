# Termin Documentation Hub

Документация монорепозитория **Termin** — 3D-движка с ECS-архитектурой, физикой, рендерингом, анимацией и навигацией.

---

## Как поддерживается документация

- [Documentation System](./documentation-system.md) — где должны жить разные типы документов.
- [Module Map](./modules.md) — границы ответственности модулей и правила переноса кода.
- [Главный вход Obsidian](../docs.md) — навигационная страница vault.

## Проекты

| Проект | Описание |
|--------|----------|
| [termin-app](./modules.md#termin-app) | Основное приложение/редактор |
| [termin-inspect](../termin-inspect/docs/index.md) | Система инспекции: Kind-типы, рефлексия полей, сериализация C/C++/Python |
| [termin-scene](../termin-scene/docs/index.md) | ECS-сцена: Entity, Component, SoA-хранилище, хэндлы, lifecycle |
| [termin-collision](../termin-collision/docs/index.md) | Коллизии: GJK, коллайдеры, collision world, C/Python API |
| [termin-gui](../termin-gui/docs/index.md) | UI фреймворк (tcgui): виджеты, лейауты, диалоги, Canvas/Viewport |
| [termin-modules](../termin-modules/docs/index.md) | Система модулей: C++/Python плагины, дескрипторы, lifecycle, callbacks |
| [termin-graphics](../termin-graphics/docs/migration-tgfx2.md) | tgfx/tgfx2, backend-neutral GPU API |
| [tcplot](./modules.md#tcplot) | Plotting library поверх tgfx/tcgui |

## Архитектура

- [Граф зависимостей библиотек](./library-dependencies.md)
- [Карта модулей](./modules.md)
