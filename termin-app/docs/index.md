# Termin

`termin-app` — основной application/editor слой монорепозитория Termin. Здесь живут редактор, project tooling и интеграция engine/domain-модулей в пользовательское приложение.

Native UI является production frontend редактора. Legacy tcgui сохраняется для
сравнения на время миграции; Qt/PyQt-версия удалена.

## Актуальные документы

- [Архитектура редактора](editor-architecture.md)
- [Project build manifest](project-build-manifest.md)
- [Editor MCP diagnostics](editor-mcp.md)
- [Плоская модель Viewport / RenderTarget](rendering-flat-viewport-target-model.md)
- [Scene extensions architecture](scene_extensions_architecture.md)

## Содержание

```{toctree}
:maxdepth: 2

getting-started
concepts
editor-architecture
project-build-manifest
editor-mcp
rendering-flat-viewport-target-model
scene_extensions_architecture
api/index
```
