# RenderingManager

`EngineCore` владеет `RenderTopology` и `RenderingManager`. `RenderTopology`
хранит scene-keyed live pipelines, render targets и viewport attachments;
`RenderingManager` исполняет рендер, управляет displays, GPU output state и
presentation.

Исходники:

- `include/termin/render/rendering_manager.hpp`
- `include/termin/render/render_topology.hpp`
- `src/rendering_manager.cpp` - публичный фасад и orchestration.
- `src/render_display_registry.cpp` - scene/editor display списки и display input routers.
- `src/render_frame_planner.cpp` - обновление viewport rects и план render target на offscreen-кадр.
- `src/render_state_store.cpp` - runtime GPU output state helpers.
- `src/render_target_context_builder.cpp` - сбор `RenderTargetContext` для 2D и provider-backed render target.
- `src/render_topology.cpp` - attached scenes, compiled pipelines, scene-owned render targets и viewport attachments.
- `src/display_presenter.cpp` - presentation/blit display surfaces.
- `src/default_pipeline_factory.cpp` - builtin default pipeline.
- `src/scene_light_collector.cpp` - сбор light data через capability system.
- `bindings/rendering_manager_bindings.cpp`

## Роль

`RenderingManager` отвечает на главный вопрос: куда и как рендерить currently attached scenes?

`RenderTopology` отслеживает:

- attached scenes;
- managed render targets, индексированные по сцене;
- compiled scene pipelines и их target names;
- связь каждого участвующего в рендере viewport с его scene и display.

`RenderingManager` отслеживает и исполняет:

- scene displays;
- editor displays;
- render output state;
- display/pipeline factories и host integration callbacks.

Display и его surface остаются host-owned. `ViewportAttachment` хранит только
non-owning ссылку на display и признак teardown policy. Scene-created viewport
удаляется при обычном scene detach; host-created editor viewport остаётся жив,
пока host явно не удалит его или не запросит forced teardown при закрытии
сцены/движка.

## Managed Render Targets

Самая важная граница владения — `RenderTopology::managed_render_targets()`.

В engine есть global pools для handles, но `RenderingManager` никогда не должен использовать global pool как источник владения или как способ найти “свои” render targets. В global pools могут лежать объекты, к которым `RenderingManager` вообще не имеет отношения: editor-owned, game-owned, временные, stale или duplicate handles.

Authoritative render-target set для одного `EngineCore` — только его
`RenderTopology`. Этот список определяет:

- какие render targets рендерятся;
- какие render targets освобождаются при detach;
- какие render targets участвуют в rebinding pipeline assets.

Практическое правило: если runtime-код хочет найти render target для render,
detach, cleanup или pipeline rebinding, он должен идти через scene-qualified
`RenderTopology`, а не сканировать global pool.

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

Перед исполнением scene pipeline `RenderingManager` передаёт нейтральные target
contexts в scene adapter. Adapter использует `TcSceneRenderItemSource` для
публикации immutable `RenderItemSnapshot`, создаёт `SceneRenderServices` для
каждого target, после чего вызывает единственный
`RenderEngine::execute_pipeline()`. Generic executor и общий
`RenderItemSource` contract не обходят `tc_scene` и не владеют entity/light
semantics.

Viewport ссылается на render target; он не является доменным владельцем этого render target.
Любой viewport, участвующий в кадре, должен быть явно зарегистрирован в
`RenderTopology`. Display list больше не используется как второй неявный индекс
для планирования кадра.

## Отключение сцены

Detach scene должен быть зеркалом attach:

1. вызвать `on_render_detach(context)`, пока targets и pipelines ещё живы;
2. уничтожить compiled scene pipelines;
3. убрать scene-owned viewports с их displays согласно topology teardown policy;
4. очистить GPU output state;
5. освободить managed render targets, принадлежащие этой сцене.

Editor displays отслеживаются отдельно и не удаляются при scene detach.

Render lifecycle capability должен получать сбалансированные переходы:

- повторный `attach_scene()` сначала вызывает `on_render_detach` для старой
  topology, затем `on_render_attach` для новой;
- `detach_scene()` вызывает `on_render_detach` один раз и затем уничтожает
  compiled pipelines;
- публичный `clear_scene_pipelines()` сохраняет поведение cleanup API и
  вызывает `on_render_detach` перед уничтожением pipeline-ов.

Attach/detach callbacks получают attachment-scoped `RenderAttachmentContext`,
а не `RenderingManager`. Через него доступны только текущая сцена, её live
render targets, target для конкретной камеры и scene pipeline по имени. Копии
context остаются валидны до начала detach teardown и становятся невалидны после
возврата из `on_render_detach`.

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

Шаги 1-5 строятся по `RenderTopology::viewport_attachments()`. Вариант
`render_display(display)` фильтрует тот же topology snapshot по конкретному
display; отдельного сканирования display viewport lists для offscreen-плана нет.

## Обновление выходов

`EngineCore` вызывает `RenderingManager::render_pending()` для обычного кадра.
`SceneManager` отвечает за пробуждение и гасит флаги запроса при `tick`.
Ревизии сцены и цели сохраняются, поэтому потребность скрытого выхода в
обновлении переживает этот кадр.

- `tc_scene_request_render` обновляет все выходы этой сцены. Цели сцены в
  `PLAY` обновляются на каждом её кадре. Для данных сцены, трансформов и
  материалов в `STOP` вызывающий код запрашивает обновление сцены.
- `tc_render_target_request_render` обновляет одну цель. Настройки цели,
  размер и редакторская камера используют этот запрос. Смена геометрии
  вьюпорта и размера поверхности планирует кадр для пересчёта размера цели
  и композиции. Вьюпорт с фиксированным разрешением переиспользует текстуру.
- `SceneManager::request_render()` сбрасывает кэш всех выходов. Этим путём
  пользуются запуск и обновление общих ресурсов. `request_frame()` будит
  цикл для уже известных запросов, например захвата FrameGraph Debugger.
- Явные `render_all()` и `render_display()` по-прежнему позволяют хосту
  синхронно принудительно обновить выходы. Picking и debugger могут явно
  запрашивать кадр выбранной цели.

Планировщик начинает с включённых вьюпортов и явных запросов. Он хранит
зависимости последнего успешно отрисованного задания. Обновившийся producer
делает зависимых consumers устаревшими, включая скрытые. При обходе новый
consumer использует готовый producer, если у него есть актуальная текстура.
При холодном старте и после инвалидации producer выполняется первым.
Один pipeline с несколькими именованными выходами выполняется как одно
задание. Дисплей композитится заново при изменении текстур, состава или
раскладки вьюпортов. Отдельный repaint UI обслуживает хост.

`TERMIN_TRACE_RENDER_SCHEDULER=1` пишет выбранные задания и причины их
запуска в лог. При требовании повторного кадра из собственного pass или
провайдера используйте scene/target invalidation после изменения данных.
