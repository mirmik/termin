# Termin Docs

Короткий вход в документацию репозитория для Obsidian, обычного Markdown и тех
случаев, когда браузер ещё не открыт, а вопрос уже вооружён.

## Главные маршруты

- [Портал документации](docs/index.md) — верхнеуровневый вход в GitHub Pages.
- [Карта районов](docs/districts/index.md) — кто за что отвечает и где проходят
  границы архитектурной санитарной зоны.
- [Core](docs/districts/core/index.md) — базовые типы, диспетчеризация, инспекция,
  Python-host, MCP и инструменты сборки.
- [Graphics](docs/districts/graphics/index.md) — данные изображения и геометрии,
  GPU-контракты, рендер, окна, UI, графы и plotting без Engine и редактора.

## Инженерные карты

- [Система документации](docs/documentation-system.md) — где живёт источник истины
  и как материал попадает в Pages.
- [Система сборки](docs/build-system.md) — профили, SDK-префиксы и package graph.
- [Карта возможностей модулей](docs/modules.md) — семантический срез библиотек;
  это не карта владения.
- [Архитектурные заметки](docs/architecture/index.md) — решения, границы и долги,
  которые ещё способны укусить.
- [Граф библиотечных зависимостей](docs/library-dependencies.md) — машинная анатомия
  без обезболивающего.

## Специализированные сайты

- [Editor](editor/termin-app/docs/index.md) — приложение редактора, CLI и его
  архитектурные контракты.
- [Collision](physics/termin-collision/docs/index.md) — столкновения и запросы.
- [Scene](engine/termin-scene/docs/index.md) — ECS, handles и lifecycle.
- [Modules](engine/termin-modules/docs/index.md) — дескрипторы и жизненный цикл
  модулей.

Временные миграционные документы лежат в [планах](docs/plans/index.md). Они могут
быть полезны как история болезни, но не должны подменять текущие контракты.
