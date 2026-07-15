# AGENTS.md

Этот файл дополняет корневой `AGENTS.md` указаниями для `termin-player`.

## Назначение

`termin-player` владеет standalone/source/headless player-логикой и
`termin_player` executable. Это вспомогательный editor-adjacent инструмент для
запуска проекта из командной строки; его поведение должно быть близко к Play
Mode редактора. Player может встраивать Python, загружать source project,
поддерживать hot reload, MCP и другие development-возможности.

Каноническая граница между host-инструментом `termin-player` и встраиваемой
библиотекой `termin-runtime` описана в
`docs/architecture/2026-07-15-player-and-runtime-boundary.md`.

Модуль может потребляться `termin-app`, но не должен импортировать
editor/app-private код. Общую для player и editor Play Mode механику следует
выносить в нейтральный модуль, потребляемый обеими сторонами.

## Граница

Разрешено зависеть от `termin-runtime`, engine/display/render/component пакетов,
`termin-modules`, `termin-mcp` и asset/runtime пакетов.

Запрещена зависимость на `termin-app`.
