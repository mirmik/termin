# AGENTS.md

Этот файл дополняет корневой `AGENTS.md` указаниями для `termin-player`.

## Назначение

`termin-player` владеет standalone/source/headless player-логикой и
`termin_player` executable. Модуль может потребляться `termin-app`, но не должен
импортировать editor/app-private код.

## Граница

Разрешено зависеть от `termin-runtime`, engine/display/render/component пакетов,
`termin-modules`, `termin-mcp` и asset/runtime пакетов.

Запрещена зависимость на `termin-app`.
