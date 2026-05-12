# SceneManager

`SceneManager` владеет registry сцен и политикой их обновления.

Исходники:

- `include/termin/scene/scene_manager.hpp`
- `src/scene_manager.cpp`
- `bindings/scene_manager_bindings.cpp`

## Роль

`SceneManager` отвечает на главный вопрос: какие сцены существуют и какие из них должны обновляться в этом кадре?

Он отслеживает:

- имя сцены;
- `tc_scene_handle`;
- optional file path;
- режим сцены;
- флаг render-request.

Он не владеет displays, viewports, render targets или render pipelines. Сцена может существовать и при этом не быть видимой. Видимой она становится только после того, как [RenderingManager](rendering-manager.md) подключит для нее render topology.

## Режимы сцен

Scene mode - это политика обновления:

- `INACTIVE` - пропустить update/render callbacks.
- `STOP` - editor update path.
- `PLAY` - full simulation update path.

Так editor-open сцены и play-mode сцены могут жить в одном registry, не притворяясь, что им нужна одинаковая update-семантика.

## Render Requests

`SceneManager.tick(dt)` возвращает, нужен ли render frame. Это не значит, что `SceneManager` рендерит; он только сообщает о потребности.

Render нужен, если:

- хотя бы одна сцена находится в `PLAY`;
- код явно вызвал `request_render()`.

Так editor actions могут запрашивать перерисовку, даже когда simulation остановлена.

## Граница жизненного цикла

Создание или регистрация сцены помещает ее в registry менеджера. Это не создает автоматически displays, viewports или render targets.

Закрытие сцены удаляет ее из registry и освобождает scene handle. Rendering attachments должны быть detached через `RenderingManager` до закрытия или как часть более высокого close-flow.
