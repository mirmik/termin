# Termin Documentation Hub

Документация монорепозитория **Termin** — 3D-движка с ECS-архитектурой, физикой, рендерингом, анимацией и навигацией.

---

## Проекты

| Проект | Описание |
|--------|----------|
| [termin](./termin/) | 3D-движок: entity system, рендеринг, физика, навигация, анимация, скелеты, воксели |
| [termin-inspect](./termin-inspect/) | Система инспекции: Kind-типы, рефлексия полей, сериализация C/C++/Python |
| [termin-scene](./termin-scene/) | ECS-сцена: Entity, Component, SoA-хранилище, хэндлы, lifecycle |
| [termin-collision](./termin-collision/) | Коллизии: GJK, коллайдеры, collision world, C/Python API |
| [termin-gui](./termin-gui/) | Immediate-mode UI фреймворк (tcgui): виджеты, лейауты, диалоги, Canvas/Viewport |
| [termin-modules](./termin-modules/) | Система модулей: C++/Python плагины, дескрипторы, lifecycle, callbacks |

## Архитектура

- [Граф зависимостей библиотек](./library-dependencies.md)
