# Engine Managers

`termin-engine` - это слой orchestration. Он не является ни scene-core, ни renderer-ом, ни editor-ом. Его задача - связать уже существующие подсистемы в runtime-модель приложения: какие сцены живы, какие из них обновляются, какие render resources должны существовать, и когда надо нарисовать кадр.

В центре этой модели:

- [EngineCore](engine-core.md) - владелец runtime loop.
- [SceneManager](scene-manager.md) - владелец списка сцен и их update-состояния.
- [RenderingManager](rendering-manager.md) - владелец runtime render attachments: displays, viewports, render targets, compiled scene pipelines.
- [ViewportRenderState](viewport-render-state.md) - internal GPU output state helper.

## Модель

Сцена сама по себе не означает, что она видима. Display сам по себе не означает, что на нем есть сцена. Render target сам по себе не означает, что он презентуется на экран.

`termin-engine` связывает эти вещи явно:

```text
SceneManager
  владеет scene registry и scene modes

RenderingManager
  владеет live render attachments

EngineCore
  выполняет frame loop и вызывает оба менеджера в правильном порядке
```

Главное разделение:

- `SceneManager` отвечает на вопрос: “какие сцены существуют и должны ли они тикаться?”
- `RenderingManager` отвечает на вопрос: “куда и через какие пайплайны рендерить эти сцены?”
- `EngineCore` отвечает на вопрос: “когда выполнить update/render frame?”

## Сводка владения

| Объект | Runtime owner |
|--------|---------------|
| Scene registry | `SceneManager` |
| Scene handle memory | scene pool / scene-core |
| Scene update policy | `SceneManager` |
| Displays | host/editor создает, `RenderingManager` отслеживает |
| Editor displays | `RenderingManager`, but not scene-detached |
| Viewports created from scene configs | `RenderingManager` |
| Managed render targets | `RenderingManager` |
| Compiled scene pipelines | `RenderingManager` |
| Render engine | `RenderingManager` лениво создает сам, если engine не был передан извне |
| Цикл кадра | `EngineCore` |

## Поток кадра

```text
poll UI/input events
SceneManager.tick(dt)
if render needed:
  SceneManager.before_render()
  RenderingManager.render_all(present=True)
  SceneManager.after_render callback
```

Scene update идет до render. `before_render` вызывается после update, но до `RenderingManager`, чтобы компоненты могли подготовить render-facing state.

## Типовые сценарии

### Открыть сцену в редакторе

```text
SceneManager создает/регистрирует сцену
RenderingManager подключает render topology сцены
editor регистрирует editor displays/panels
SceneManager mode = STOP
UI changes вызывают request_render()
EngineCore frame loop рендерит по запросу
```

### Запустить сцену

```text
SceneManager mode становится PLAY
tick(dt) выполняет full simulation
tick возвращает render-needed каждый кадр
RenderingManager рендерит attached scene outputs
```

### Перезагрузить pipeline asset

```text
asset изменился
RenderingManager находит live managed render targets / attached scene pipelines
old pipeline handles заменяются или scene pipelines компилируются заново
render-request callback просит pull-mode host запланировать еще один кадр
```
