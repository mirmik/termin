# RenderingManager

`RenderingManager` владеет live render topology: displays, viewports, render targets, scene pipelines и presentation state.

Исходники:

- `include/termin/render/rendering_manager.hpp`
- `src/rendering_manager.cpp` - публичный фасад и orchestration.
- `src/render_state_store.cpp` - runtime GPU output state для viewport/render target.
- `src/display_presenter.cpp` - presentation/blit display surfaces.
- `src/default_pipeline_factory.cpp` - builtin default pipeline.
- `src/scene_light_collector.cpp` - сбор light data через capability system.
- `bindings/rendering_manager_bindings.cpp`

## Роль

`RenderingManager` отвечает на главный вопрос: куда и как рендерить currently attached scenes?

Он отслеживает:

- scene displays;
- editor displays;
- связи viewport-to-render-target;
- managed render targets;
- compiled scene pipelines;
- render output state;
- display/pipeline factories и host callbacks.

## Managed Render Targets

Самая важная граница владения - `managed_render_targets_`.

В engine есть global pools для handles, но `RenderingManager` никогда не должен использовать global pool как источник владения или как способ найти “свои” render targets. В global pools могут лежать объекты, к которым `RenderingManager` вообще не имеет отношения: editor-owned, game-owned, временные, stale или duplicate handles.

Authoritative render-target set для `RenderingManager` - только `managed_render_targets_`. Этот список определяет:

- какие render targets рендерятся;
- какие render targets освобождаются при detach;
- какие render targets участвуют в rebinding pipeline assets.

Практическое правило: если код в `RenderingManager` хочет найти render target для render, detach, cleanup или pipeline rebinding, он должен идти через `managed_render_targets_`, а не сканировать global pool.

## Подключение сцены

Attach scene восстанавливает live render topology из persistent scene render data.

Концептуально он делает следующее:

1. создает live render targets из render target configs;
2. создает viewports из viewport configs;
3. размещает viewports на displays;
4. связывает viewports с render targets;
5. компилирует scene pipeline templates;
6. помечает viewports как управляемые scene pipelines.

Получающаяся модель плоская:

```text
RenderTarget = что рендерим
Viewport     = где показываем
Display      = поверхность презентации
Pipeline     = как рендерим
```

Обычный `texture_2d` render target получает одну `CameraComponent` и строит один
`RenderTargetContext`. `xr_stereo` target не переиспользует camera slot как
скрытый rig: он ссылается на `XrOriginComponent`, а OpenXR runtime каждый кадр
создает per-eye `RenderCamera` из transform этого origin и позы OpenXR view.

Viewport ссылается на render target; он не является доменным владельцем этого render target.

## Отключение сцены

Detach scene должен быть зеркалом attach:

1. убрать scene viewports со scene displays;
2. освободить managed render targets, принадлежащие этой сцене;
3. очистить GPU output state;
4. уничтожить compiled scene pipelines;
5. уведомить render-detach callbacks.

Editor displays отслеживаются отдельно и не удаляются при scene detach.

Render lifecycle notifications должны приходить строго один раз на явное
подключение/отключение render state:

- `attach_scene()` перекомпилирует старые scene pipelines без
  `on_render_detach`, затем вызывает `on_render_attach`;
- `detach_scene()` вызывает `on_render_detach` один раз и затем уничтожает
  compiled pipelines;
- публичный `clear_scene_pipelines()` сохраняет поведение cleanup API и
  вызывает `on_render_detach` перед уничтожением pipeline-ов.

## Кадр рендера

Текущая rendering model - offscreen-first:

```text
render_all()
  render_all_offscreen()
  present_all()
```

Это значит, что render outputs сначала создаются в textures, а потом презентуются на displays.

Почему такая форма важна:

- scene pipelines могут target-ить несколько viewports/displays;
- render target output может стать pipeline input;
- editor displays и scene displays могут использовать один presentation path;
- presentation остается отдельным шагом, не смешанным со scene rendering.

Порядок кадра:

1. обновить viewport pixel rects по размерам display surfaces;
2. синхронизировать dynamic-resolution render targets с viewport sizes;
3. отрендерить managed render targets;
4. выполнить scene pipelines для attached scenes;
5. отрендерить unmanaged viewports;
6. презентовать outputs на displays.

## Pull Hosts

Некоторые hosts не рендерят непрерывно. Для них `RenderingManager` предоставляет render-request callback integration. Когда assets/pipelines перебинжены, manager может попросить host запланировать еще один кадр.
