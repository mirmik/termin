# Termin

`termin-app` — основной application/editor слой монорепозитория Termin. Здесь живут редактор, project tooling и интеграция engine/domain-модулей в пользовательское приложение.

tcgui является primary UI. Qt поддерживается по возможности, но новые editor-flow и архитектурные решения должны сначала проходить через tcgui.

## Актуальные документы

- [Архитектура редактора](editor-architecture.md)
- [Project build manifest](project-build-manifest.md)
- [Плоская модель Viewport / RenderTarget](rendering-flat-viewport-target-model.md)
- [Scene extensions architecture](scene_extensions_architecture.md)

## Содержание

```{toctree}
:maxdepth: 2

getting-started
concepts
editor-architecture
project-build-manifest
rendering-flat-viewport-target-model
scene_extensions_architecture
api/index
```
