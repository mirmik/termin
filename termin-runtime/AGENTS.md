# AGENTS.md

Этот файл дополняет корневой `AGENTS.md` указаниями для `termin-runtime`.

## Назначение

`termin-runtime` — встраиваемая C/C++ библиотека для загрузки и запуска уже
собранного runtime package внутри host-приложения. Каноническая граница с
`termin-player` описана в
`docs/architecture/2026-07-15-player-and-runtime-boundary.md`.

## Граница

Разрешено зависеть от native engine/scene/render/component/runtime-asset
пакетов, необходимых для построения runtime domain objects.

Запрещены обязательные зависимости на `termin-player`, `termin-app`,
editor-модули, Python/nanobind, MCP, source-project discovery, file watchers,
asset import и project build tooling.

Bindings и host-specific интеграция должны жить отдельным слоем над
`termin-runtime`; они не должны становиться обязательной частью библиотеки.
