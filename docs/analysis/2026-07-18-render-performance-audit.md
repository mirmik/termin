# Аудит быстродействия render frame в Termin

Дата: 2026-07-18.

Статус: статический read-only аудит. Код во время анализа не изменялся.
Фактический вклад находок в frame time ещё не измерен профилировщиком.

## Резюме

Текущая стоимость кадра на простой сцене объяснима не одним локальным
hotspot, а наложением трёх классов нагрузки:

1. У editor pipeline большой постоянный GPU budget, почти не зависящий от
   числа объектов: 4x MSAA, отдельные depth/id passes, два highlight passes,
   десять bloom subpasses, tonemap, UI и несколько full-frame copies.
2. CPU каждый кадр повторяет работу, которая по смыслу статична или должна
   выполняться один раз на scene/view: сборку execution metadata framegraph,
   обход Drawable для каждого geometry pass, shader/task planning и упаковку
   pass/material resources.
3. Render orchestration и backend boundaries усиливают стоимость: polling
   picking способен запросить несколько полных scene renders, один logical
   frame может распасться на несколько submits, а OpenGL/D3D11 сбрасывают
   значительный объём state на каждой pass boundary.

Наиболее опасный условный фактор — project setting `render_sync_mode`. Если он
равен `flush` или особенно `finish`, синхронизация выполняется после каждого
framegraph pass. Для default editor pipeline это около 19 sync points на
target/frame. Default value — `none`, но значение сохраняется в проекте и
должно быть проверено до любых сравнений.

Наиболее вероятные steady-state направления выигрыша:

- compiled pipeline execution descriptor вместо per-frame metadata assembly;
- frame/view-scoped RenderItem snapshot с маршрутизацией по pass/phase;
- сохранение planned task/encoder от collection до submit;
- разделение pass/material/draw resource scopes;
- одна backend frame/submit boundary на logical frame;
- demand-driven ID/depth/effect branches и раздельная invalidation scene/UI.

## Область и методика

Проверялись:

- default editor pipeline и основные render passes;
- framegraph build/cache/execution path;
- scene Drawable collection и RenderItem planning/submission;
- material/shader resource paths;
- `RenderingManager`, scene scheduling, picking и native editor composition;
- Vulkan, OpenGL и D3D11 command/resource/presentation paths;
- Python pass/component bridges;
- существующие Kanboard cards, чтобы не создавать дубли.

Выводы основаны на статически подтверждённых call paths. Severity отражает
потенциальный эффект и кратность вызова, confidence — уверенность в самом
call path. Без CPU/GPU profile нельзя утверждать, какой пункт доминирует на
конкретной машине и сцене.

## Как читать симптом

- Почти пустая сцена медленна, а стоимость растёт с resolution: сначала
  проверять Bloom, Highlight, MSAA, UI и present copies.
- Стоимость растёт с Drawable/submesh count: проверять повторные scene walks,
  phase lookup, planning и material/resource packing.
- Стоимость растёт с shadow cascades: проверять Shadow task rebuild и repeated
  resource binding.
- Кадр ухудшается при движении мыши: проверять picking invalidation/readback.
- Стоимость растёт с числом viewports/RT/pipelines: проверять global scheduler,
  subgraph submits и repeated light/context collection.
- На D3D11/OpenGL CPU заметно дороже Vulkan: проверять full state reset,
  synchronous readback, constant-buffer/VAO churn и GL validation calls.

## Находки

### 1. Critical conditional: sync mode применяется после каждого pass

`RenderEngine` проверяет project setting внутри schedule loop и вызывает
`device->flush()` или `device->finish()` непосредственно после исполнения
каждого pass:

- `termin-render/src/render_engine.cpp:1060-1066`;
- default C value: `termin-render/src/tc_project_settings.c:3`;
- default project value: `termin-project/python/termin/project/settings.py:108`.

`FINISH` полностью сериализует CPU/GPU около 19 раз на editor target/frame.
`FLUSH` тоже дорог на OpenGL/D3D11 и меняет batching semantics. На explicit
submission backend часть вызовов может быть no-op, но полагаться на это как на
общий contract нельзя.

Первый probe: проверить `project_settings/project.json`, UI Project Settings и
поставить counter на `flush/finish`.

Направление: сделать настройку явно debug-only и синхронизировать максимум на
frame/capture boundary, а не после каждого pass.

### 2. High: default editor имеет большой постоянный GPU budget

Pipeline содержит 19 логических passes:

- пять последовательных `ColorPass` для `opaque`, `transparent`, `editor`,
  `editor_debug`, `editor_debug_transparent`;
- Shadow, Skybox, Collider/Gizmo paths;
- отдельные Depth и Id;
- Resolve, два Highlight, Bloom, Tonemap, UIWidget и Present.

Источники:

- `termin-app/termin/editor_core/editor_pipeline.py:74-188`;
- `msaa_samples = 4` в `editor_pipeline.py:188`.

Один `BloomPass` с default `mip_levels = 5` выполняет:

- bright pass;
- четыре progressive downsample;
- четыре progressive upsample;
- composite.

Итого десять fullscreen draws:

- `termin-render-passes/include/termin/render/bloom_pass.hpp:34`;
- `termin-render-passes/src/bloom_pass.cpp:273-366`.

Оба `HighlightPass` вычисляют `enabled`, но даже при `selected_id == 0`
упаковывают Python uniform bytes, открывают render pass и рисуют fullscreen
quad:

- `termin-render-passes/python/termin/render_passes/highlight.py:118-183`.

`DepthPass` пишет resource `depth`, который в default editor pipeline никто не
читает:

- `termin-app/termin/editor_core/editor_pipeline.py:74`.

Framegraph при этом включает все enabled nodes и не делает reachability/dead
branch pruning:

- `termin-render/src/tc_frame_graph.c:164-240`;
- `termin-render/src/tc_frame_graph.c:334-410`;
- executor: `termin-render/src/render_engine.cpp:861-865`.

`UnifiedGizmoPass` также открывает pass и очищает full-size depth attachment до
того, как становится ясно, есть ли фактическая geometry:

- `termin-render-passes/python/termin/render_passes/unified_gizmo.py:72-137`.

Следствие: простая сцена сохраняет почти весь postprocess/transfer budget.

Probes:

1. GPU timestamps для Depth, Id, HoverHighlight, SelectedHighlight, Bloom,
   Tonemap, Present.
2. A/B: Depth off; оба Highlight off; затем Id off; Bloom off; MSAA 4x -> 1x.
3. Изменение resolution при неизменной сцене.

### 3. High: framegraph execution metadata пересобирается каждый кадр

`tc_pipeline_get_frame_graph()` корректно кэширует dependency graph до dirty:

- `termin-render/src/tc_pipeline.c:763-778`.

Но `RenderEngine::render_scene_pipeline_offscreen()` после получения cached
graph каждый кадр заново:

- вызывает `pipeline.collect_specs()`;
- объединяет specs в `unordered_map<string, ResourceSpec>`;
- перечисляет canonical resources и alias groups;
- строит resource/FBO/texture maps;
- собирает per-pass reads/writes и разрешает их в texture handles.

Основной path:

- `termin-render/src/render_engine.cpp:423-655`;
- `termin-render/src/render_engine.cpp:700-809`;
- `termin-render/src/render_engine.cpp:862-1058`;
- `termin-render/src/render_pipeline.cpp:129-145`.

Canonical enumeration имеет nested scan O(R^2), alias lookup линейно проходит
все resources и вызывается многократно:

- `termin-render/src/tc_frame_graph.c:480-515`.

На каждый pass создаются reads/writes vectors, пять `unordered_map`, recursive
`std::function`, строки и новый `ExecuteContext`. `ExecuteContext` дополнительно
копирует весь `lights` vector:

- `termin-render/include/termin/render/execute_context.hpp:34-57`;
- `termin-render/src/render_engine.cpp:887-1055`.

Для Python passes per-frame metadata path берёт GIL и вызывает Python. Reads и
writes собираются count+fill, поэтому pass с непустыми dependencies получает
как минимум шесть C++/Python crossings: specs, reads x2, writes x2, execute.

- `termin-render/python/tc_pass_bindings.cpp:226-243`;
- `termin-render/python/tc_pass_bindings.cpp:305-368`.

Направление: компилировать merged specs, canonical IDs, aliases, allocation
descriptors и per-pass binding packets вместе с graph. Пересобирать только по
pipeline revision/dirty; resize должен менять size-dependent GPU resources, а
не всю metadata topology.

### 4. High: сцена независимо собирается каждым geometry pass

Пять editor `ColorPass` каждый создают локальный `RenderSceneItemCollector` и
обходят все Drawable:

- `termin-render-passes/src/color_pass.cpp:327-405`;
- `termin-render-passes/src/color_pass.cpp:618-624`;
- `termin-render/src/render_scene_item_collector.cpp:53-85`.

После них отдельный collection выполняют Depth и Id через
`GeometryPassBase`; при наличии directional shadow light добавляется Shadow:

- `termin-components/termin-components-render/src/geometry_pass_base.cpp:247-388`;
- `termin-render-passes/src/id_pass.cpp:173-174`;
- `termin-render-passes/src/shadow_pass.cpp:638-656`.

Итого default editor делает минимум семь полных Drawable walks, до восьми с
тенями. Локальный Color collector не сохраняет vector capacity между вызовами.

`MeshRenderer` до проверки итогового набора phases вычисляет model matrix, а
для каждого submesh/pass создаёт временные `string`/`vector` и повторно ищет
phases:

- `termin-components/termin-components-render/src/mesh_renderer.cpp:577-646`;
- `mesh_renderer.cpp:666-691`.

Для каждой emitted material phase вызывается `tc_material_find_phase_ref`,
который сканирует всю capacity global material pool:

- `termin-graphics/src/resources/tc_material_registry.c:357-405`.

Это даёт O(passes * emitted items * material pool capacity), причём capacity
остаётся большой после resource churn.

Направление: один frame/view-scoped immutable RenderItem snapshot, canonical
material handle/phase index в item и pass routing по компактным индексам.

### 5. High: task/shader planning повторяется и умножается cascades

Color сначала создаёт временный `RenderTaskList`, чтобы получить только
`final_shader`, а затем планирует тот же item ещё раз при построении настоящего
task list:

- `termin-render-passes/src/color_pass.cpp:382-403`;
- `termin-render-passes/src/color_pass.cpp:718-828`.

Shadow делает planning при collection, а затем внутри каждой cascade создаёт
новый `RenderTaskList` и заново планирует всех casters:

- `termin-render-passes/src/shadow_pass.cpp:521-542`;
- `termin-render-passes/src/shadow_pass.cpp:677-693`;
- `termin-render-passes/src/shadow_pass.cpp:847-929`.

При четырёх cascades это около пяти planning calls на caster. Каждый task также
получает heap-owned extension через `unique_ptr`:

- `termin-render/include/termin/render/render_task.hpp:61-84`.

Planning и submission независимо ищут encoder под process-wide mutex:

- `termin-render/src/render_item_submission.cpp:52-79`;
- planning: `render_item_submission.cpp:510-635`;
- submit: `render_item_submission.cpp:699-723`.

Для skinned mesh planning вызывает shader assembler. Assembler строит source
strings/resource vectors и безусловно делает `tc_shader_set_contract()` даже
после получения существующего UUID:

- `termin-render/src/render_item_submission.cpp:261-314`;
- `termin-render/src/material_pipeline_shader_assembler.cpp:244-417`.

Направление:

- сохранять accepted planned task/encoder через sort и submit;
- отделить cascade-invariant task core от per-cascade matrices;
- использовать arena/fixed storage для task extensions;
- cache shader variant по source/pass/transform revision без повторной сборки
  sources и contract на hit.

### 6. High: pass-level resources повторно загружаются на каждый draw

`submit_render_item_draw()` вызывает `prepare_material_pipeline_resources()`
для каждого draw:

- `termin-render/src/render_item_submission.cpp:123-170`;
- `termin-render/src/material_pipeline.cpp:586-662`.

Таким образом повторно обрабатываются:

- per-frame uniforms;
- shadow block;
- lighting UBO;
- shadow textures;
- material UBO и material textures.

`apply_material_phase_ubo()` на каждый draw создаёт heap
`vector<uint8_t> staging`, заново проходит reflected fields/uniforms и пишет
данные в ring UBO:

- `termin-render/src/material_ubo_apply.cpp:339-437`;
- allocation: `material_ubo_apply.cpp:364`.

`RenderContext2::bind_uniform_data()` всегда получает новый ring offset и
помечает resource binding dirty:

- `termin-graphics/src/tgfx2/render_context.cpp:883-927`.

Backend consequences:

- Vulkan почти на каждый draw создаёт новый descriptor set; ring binding
  намеренно обходит descriptor cache и делает `vkAllocateDescriptorSets` плюс
  `vkUpdateDescriptorSets`:
  `termin-graphics/src/tgfx2/vulkan/vulkan_pipeline_resource_sets.cpp:658-835`.
- D3D11 не переопределяет ring API; fallback создаёт новый constant buffer,
  upload и deferred destroy на каждый uniform write:
  `termin-graphics/include/tgfx2/i_render_device.hpp:254-269`,
  `termin-graphics/src/tgfx2/render_context.cpp:902-915`.

Направление: разнести pass/material/draw scopes, кэшировать descriptor identity
отдельно от dynamic offsets и material UBO по material+shader version.

### 7. High: backend frame boundary находится на уровне subgraph

`RenderEngine::render_scene_pipeline_offscreen()` сам открывает frame, если
context idle, и сам завершает его:

- begin: `termin-render/src/render_engine.cpp:659-666`;
- end: `termin-render/src/render_engine.cpp:1077-1081`;
- submit: `termin-graphics/src/tgfx2/render_context.cpp:109-118`.

`RenderingManager::render_all_offscreen()` вызывает этот path отдельно для:

- standalone managed RT;
- каждой пары scene/pipeline;
- viewport-bound RT вне scene pipeline.

См. `termin-engine/src/rendering_manager.cpp:818-853`.

Следствия:

- Vulkan получает N `vkQueueSubmit` на display frame, после каждого двигает
  один из шести frame slots и подготавливает следующий slot:
  `termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp:1178-1268`.
  При большом N fence wait может ожидать работу, отправленную ранее в том же
  logical frame.
- D3D11 делает `Flush()` после каждого subgraph:
  `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp:1249-1252`.
- OpenGL делает `glFlush()`:
  `termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1202-1205`.
- Vulkan presentation добавляет отдельный compose submit:
  `termin-graphics/src/tgfx2/vulkan/vulkan_swapchain.cpp:445-456`.

Направление: RenderingManager-level device/display frame scope. RenderEngine
должен записывать subgraphs в уже открытый context и не владеть submit boundary.

### 8. High для D3D11/OpenGL: полный state reset на каждый pass

Executor безусловно вызывает `device->reset_state()` перед каждым framegraph
pass:

- `termin-render/src/render_engine.cpp:861-874`.

D3D11 реализация делает `ID3D11DeviceContext::ClearState()`:

- `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp:1774-1777`.

Кроме того, `end_render_pass()` отвязывает RTV и очищает все 128 SRV slots для
VS/PS/GS, то есть до 384 slot updates на pass:

- `termin-graphics/src/tgfx2/d3d11/d3d11_command_list.cpp:137-142`;
- `d3d11_command_list.cpp:338-342`.

OpenGL повторно выставляет baseline state, после чего `bind_pipeline()` снова
выпускает raster/depth/blend state:

- `termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1612-1629`;
- `termin-graphics/src/tgfx2/opengl/opengl_command_list.cpp:119-177`.

Направление: точечная invalidation state caches и отдельный full reset только
на external-host/debug recovery boundary.

### 9. High conditional: picking вызывает лишние renders и GPU stalls

Один mouse move проходит следующую последовательность:

1. `on_mouse_move` записывает pending hover и вызывает `_request_update()`.
2. После полного render `_process_pending_hover` ставит async ID readback и
   снова вызывает `_request_update()`.
3. Если poll ещё не готов, снова запрашивается полный render.
4. После готовности `selection.hover()` вызывает новый render для highlight.

Источники:

- `termin-app/cpp/termin/editor/editor_interaction_system.cpp:254-274`;
- `editor_interaction_system.cpp:353-371`;
- `editor_interaction_system.cpp:443-470`;
- `editor_interaction_system.cpp:609-631`;
- scene/UI request связаны в
  `termin-app/termin/editor_core/editor_viewport.py:194-197`.

Polling GPU request не должен требовать повторного исполнения всех 19 scene
passes. Нужны отдельные scene/UI/picking invalidations и freshness/version у ID
buffer.

Vulkan имеет async pixel request/poll. OpenGL и D3D11 не переопределяют async
API и падают в synchronous helpers:

- default API: `termin-graphics/include/tgfx2/i_render_device.hpp:215-235`;
- OpenGL blocking `glReadPixels`:
  `termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1379-1440`;
- D3D11 full-size staging `CopyResource` + blocking `Map`:
  `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp:1553-1568`,
  `d3d11_render_device.cpp:1614-1655`,
  `d3d11_render_device.cpp:1737-1771`.

Направление: PBO/fence ring для GL; reusable 1x1 staging/query ring и
`CopySubresourceRegion` для D3D11.

### 10. Medium-high: scheduling глобальный, а не dirty-target based

`SceneManager` сворачивает requests всех scenes в один bool; наличие любой play
scene делает render обязательным. Затем `before_render` проходит все active
scenes:

- `termin-engine/src/scene_manager.cpp:186-212`.

После этого `RenderingManager` исполняет все standalone RT, pipelines всех
attached scenes и viewport targets:

- `termin-engine/src/rendering_manager.cpp:818-853`.

Один изменившийся target или continuous play scene тем самым перерисовывает
независимые статические attachments.

Направление: dependency-aware dirty set по scene/pipeline/RT/display и
telemetry `request source -> rendered outputs`.

### 11. Medium-high: editor UI и debugger способны доминировать baseline

В game mode каждый engine loop вызывает полный native UI compose. UI host
выполняет layout всех roots, sync previews, paint, rebuild draw list, GPU render
и present:

- `termin-app/termin/editor_native/run_editor.py:1737-1743`;
- `termin-app/termin/editor_native/ui_host.py:269-306`.

На простой сцене editor chrome поэтому может оказаться дороже scene render.
Baseline необходимо сравнивать с player и отдельно смотреть sections
`UI Compose` / `SceneManager Render`.

Открытый Framegraph Debugger образует feedback loop: каждый loop получает
`notify_frame_rendered`, модель emits изменения, UI форматирует stats/JSON и
запрашивает новый scene/UI render:

- `termin-app/termin/editor_native/framegraph_debugger.py:212-216`;
- `framegraph_debugger.py:289-292`;
- `framegraph_debugger.py:392-401`;
- `termin-app/termin/editor_core/framegraph_debugger_model.py:617-621`.

Baseline нельзя снимать с открытым Framegraph Debugger.

### 12. Medium: diagnostic instrumentation не zero-overhead

`TERMIN_RENDER_ENGINE_TIMING` проверяется в начале render call, но clocks,
phase duration calculations и local `unordered_map<string, stats>` обновляются
даже когда timing выключен:

- `termin-render/src/render_engine.cpp:374-385`;
- `render_engine.cpp:402-417`;
- `render_engine.cpp:870`;
- `render_engine.cpp:1069-1073`.

`TGFX2_VULKAN_STATS` также ограничивает только печать. Atomics выполняются на
каждом draw/bind/resource-set и generic `PipelineCache` hit/miss:

- `termin-graphics/src/tgfx2/vulkan/vulkan_command_list.cpp:234-323`;
- `termin-graphics/src/tgfx2/pipeline_cache.cpp:144-168`;
- `termin-graphics/src/tgfx2/vulkan/vulkan_pipeline_resource_sets.cpp:687`.

Command list, submit и swapchain всегда читают `steady_clock` и агрегируют
stats. При этом logged `fence_wait_ms` измеряет весь `prepare_frame_slot`, куда
входят readback completion, pending destroy, descriptor reset/cache cleanup, а
не только `vkWaitForFences`:

- `termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp:1178-1195`;
- `vulkan_render_device.cpp:1259-1264`.

Направление: cached runtime/compile-time gate, render-thread-local counters и
раздельные timings для fence/cleanup/readback.

### 13. Дополнительные backend risks

#### D3D11 WPF bridge сериализует каждый frame

D3DImage presentation вызывает `wait_idle()` после blit/reset:

- `termin-graphics/src/tgfx2_interop.cpp:271-326`;
- public call path: `tgfx2_interop.cpp:737-750`.

D3D11 wait создаёт event query, делает Flush, poll и при необходимости спит с
шагом 1 ms:

- `termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp:709-734`.

Это critical conditional для WPF. Нужна pipelined shared-resource
synchronization без CPU-wide idle.

#### OpenGL upload rings сбрасываются без GPU lifetime boundary

Новый command list сбрасывает offsets UBO/transient/push rings в ноль, но
обычный reset не orphan'ит storage и не ждёт fence:

- `termin-graphics/src/tgfx2/opengl/opengl_command_list.cpp:20-29`;
- `termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1665-1701`;
- `opengl_render_device.cpp:1744-1767`;
- `opengl_render_device.cpp:1804-1838`.

При нескольких subgraph command lists за logical frame driver вынужден stall
или rename на раннем reuse. Нужен persistent/N-buffered ring или корректный
orphan/fence contract.

#### OpenGL pass validation делает synchronous state queries

Каждый `begin_render_pass()` вызывает clip-space enforcement с `glGetError`,
`glClipControl` и несколькими `glGetIntegerv`:

- `termin-graphics/src/tgfx2/opengl/opengl_command_list.cpp:37-56`;
- `termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:129-171`.

Validation должна выполняться на context/host handoff или в debug mode, не на
каждом pass.

#### Vulkan layout planning отсутствует на уровне framegraph

`begin_render_pass()` переводит attachment в render layout, а
`end_render_pass()` сразу возвращает sampled target в shader-read, не зная
следующего consumer:

- `termin-graphics/src/tgfx2/vulkan/vulkan_command_list.cpp:57-123`;
- `vulkan_command_list.cpp:190-228`.

Последовательные write-after-write passes получают лишний layout ping-pong.
Нужен framegraph resource-state plan.

#### Presentation содержит несколько full-frame copies

Обычный путь может включать:

1. `PresentToScreenPass` blit в viewport target;
2. clear display surface и blit viewport;
3. backend copy/blit surface в swapchain/backbuffer.

Источники:

- `termin-render-passes/src/present_pass.cpp:24-44`;
- `termin-engine/src/display_presenter.cpp:67-125`;
- `termin-player/cpp/termin/player/player_runtime_host.cpp:1219-1224`;
- `termin-display/src/platform/backend_window.cpp:613-636`.

Для единственного opaque fullscreen viewport нужен direct/single-copy fast
path.

#### Cold Vulkan pipelines создаются синхронно

Pipeline cache miss синхронно вызывает backend creation на render thread, а
Vulkan передаёт `VK_NULL_HANDLE` вместо native `VkPipelineCache`:

- `termin-graphics/src/tgfx2/pipeline_cache.cpp:144-200`;
- `termin-graphics/src/tgfx2/vulkan/vulkan_pipeline_resource_sets.cpp:515-540`.

Это объясняет first-use spikes, но не steady-state после прогрева. Проверять
`pipelines` и `pipeline_create_ms` в Vulkan stats.

### 14. Нижний приоритет и профилактические хвосты

#### Python lifecycle capabilities не совпадают с scene indexes

Shared Python vtable содержит `update`, `fixed_update`, `before_render`, поэтому
native init первоначально выставляет все три flags:

- `termin-scene/src/tc_component_python.c:130-148`;
- `termin-scene/include/core/tc_component.h:151-166`.

Python base корректирует update/fixed по override identity, но before_render
callback вообще не устанавливается:

- `termin-scene/python/termin/scene/python_component.py:246-256`;
- `termin-scene/cpp/bindings/tc_component_python_bindings.cpp:254-274`.

Каждый Python component поэтому попадает в `before_render_list` и проходит
пустой trampoline на каждом rendered frame:

- `termin-scene/src/tc_scene.c:503-516`;
- `tc_scene.c:753-763`.

Public lifecycle flag setters также не reindex already attached scene. Нужен
единый scene-aware capability API.

#### Fixed timestep не имеет max-substeps/clamp

После hitch оба fixed-update loops выполняют catch-up до полного опустошения
accumulator:

- `termin-scene/src/tc_scene.c:691-703`;
- `tc_scene.c:725-738`.

Возможна spiral-of-death. Нужны configurable max substeps, clamp/drop metric и
WARN/telemetry о потерянном simulation time.

#### Broken render configuration способна устроить log storm

Некоторые invalid viewport/RT/external texture состояния логируются каждый
frame:

- `termin-engine/src/rendering_manager.cpp:938-969`;
- `rendering_manager.cpp:1114-1126`;
- `termin-engine/src/render_target_context_builder.cpp:119-148`.

Ошибки нельзя скрывать, но повтор следует ограничить state-change/once-key
логированием и отдельным counter.

## План профилирования

### Фаза 0. Сделать baseline воспроизводимым

1. Release SDK, прогретые shaders/pipelines.
2. `render_sync_mode=none`.
3. Framegraph Debugger закрыт.
4. Сначала неподвижная мышь.
5. Записать backend, resolution, MSAA, число viewports/RT/scenes и shadow
   cascades.
6. Сравнить editor и player на одной сцене.

Удобный запуск существующей телеметрии:

```bash
TERMIN_RENDER_ENGINE_TIMING=1 \
TGFX2_VULKAN_STATS=1 \
./sdk/bin/termin_editor /path/to/Project.terminproj
```

Нужно учитывать: включение env добавляет вывод, но значительная часть timing и
stats overhead в текущем коде присутствует и без env.

### Фаза 1. Разделить CPU и GPU fixed cost

Снять CPU frame sections и GPU timestamps. Затем A/B по одному изменению:

1. Depth off.
2. HoverHighlight + SelectedHighlight off.
3. Id off после Highlights.
4. Bloom off.
5. MSAA 4x -> 1x.
6. Shadows off; затем cascades 4 -> 1.
7. Player вместо editor.
8. Половинное/двойное resolution.

Если delta масштабируется с pixels, искать в effects/copies/MSAA. Если почти не
зависит от resolution, переходить к CPU metadata/scene/task paths.

### Фаза 2. Добавить краткие counters

Минимальный набор:

- logical EngineCore frames;
- scene renders и причина request;
- RenderEngine calls;
- RenderContext2 submits и swapchain presents;
- `tc_scene_foreach_drawable` calls;
- visited drawables и emitted RenderItems по pass;
- `plan_render_item_task` calls/accepted/rejected;
- encoder registry lookups/locks;
- material phase reverse-scan iterations;
- shader assembly and `tc_shader_set_contract` calls;
- material UBO packs и bytes;
- uniform ring writes по resource scope/name;
- descriptor allocations/updates;
- `flush/finish/reset_state` calls.

Ожидаемые invariants после исправлений:

- один common collection на scene/view/frame;
- один accepted planning на item/pass, а не повтор collection+execution;
- Shadow task core не перестраивается на cascade;
- pass resources загружаются один раз на pass/shader batch;
- один backend submit на logical frame/device плюс обоснованный present submit.

### Фаза 3. Интерпретировать backend telemetry

Для Vulkan:

- `resource_sets ~= draws` подтверждает descriptor churn;
- `pipelines` после warm-up должны быть около нуля;
- submits существенно больше display frames подтверждают неверную frame
  boundary;
- `fence_wait_ms` пока нельзя считать чистым GPU wait: он включает cleanup;
- RenderDoc/Nsight должны показать layout barriers и fullscreen pass timeline.

Для D3D11:

- PIX/ETW: `ClearState`, `*SetShaderResources`, `CreateBuffer`, `Map`, `Flush`;
- отдельно проверить moving mouse и WPF bridge;
- посчитать full-size `CopyResource` для one-pixel picking.

Для OpenGL:

- apitrace/Nsight: `glReadPixels`, `glGet*`, `glGen/DeleteVertexArrays`,
  `glBufferSubData`, `glFlush`, FBO create/delete;
- сравнить первые ring uploads после каждого command-list begin;
- проверить frame time при движении и неподвижной мыши.

### Фаза 4. Проверить scaling hypotheses

Синтетические sweeps при фиксированном остальном:

- N empty passes/resources при пустой сцене;
- N Drawable с одним material;
- N submeshes на одном Drawable;
- material pool capacity/churn при неизменной видимой сцене;
- 1/2/4 shadow cascades;
- 1/N viewports и render targets;
- один mouse move в STOP mode и число scene renders до quiescence.

## Целевая архитектура кадра

```text
logical frame
  -> collect dirty scene/pipeline/target set
  -> begin one backend frame per device/display
  -> fetch compiled pipeline execution descriptors
  -> build/reuse one RenderItem snapshot per scene/view
  -> route compact item indices into pass task batches
  -> bind pass scope once, material scope by version, draw scope per item
  -> execute only live/demanded branches
  -> submit once
  -> compose/present with the minimum required full-frame copy count
```

Ключевой invariant: статичная topology, metadata и pass-level data не должны
пересобираться или копироваться в steady-state draw loop.

## Трекинг на доске

По результатам аудита созданы scoped cards:

- #554 `[render/framegraph] Компилировать execution descriptor только при
  изменении pipeline`;
- #555 `[render] Собирать и маршрутизировать RenderItems один раз на
  сцену/кадр`;
- #556 `[render/frame] Владеть backend frame на уровне RenderingManager`;
- #557 `[render/framegraph] Исполнять только достижимые output roots`;
- #558 `[editor/picking] Не перерисовывать всю сцену ради polling async
  readback`;
- #559 `[graphics/picking] Реализовать async one-pixel readback для OpenGL и
  D3D11`;
- #560 `[graphics/state] Убрать полный backend reset перед каждым framegraph
  pass`;
- #561 `[graphics/resources] Переиспользовать descriptor и constant-buffer
  storage между draws`;
- #562 `[render/scheduler] Перерисовывать dirty targets вместо всех attached
  scenes`;
- #563 `[scene/python] Синхронизировать lifecycle capabilities с scene indexes`
  (`Ready`);
- #564 `[graphics/profiling] Сделать выключенную backend-статистику
  zero-overhead` (`Closed`);
- #565 `[editor/mcp] inspect_framegraph завершает редактор на ChronoSquad`
  (`Backlog`);
- #566 `[render/perf] Планировать ShadowPass draw-задачи один раз на execution`
  (`Closed`);
- #567 `[render/perf] Убрать двойное планирование ColorPass draw-задач`
  (`Closed`).

Существующие cards дополнены комментариями вместо создания дублей:

- #203 `[render/arch] Unify RenderItem task planning and submission`;
- #207 `[graphics/render] Define C-like runtime data contracts`;
- #233 `[render/arch] Split RenderingManager responsibilities`.

## Первый live-проход: ChronoSquad

После статического аудита выполнен Linux/Vulkan probe на
`~/project/chronosquad-termin/ChronoSquad.terminproj` в Play Mode. Frame
Profiler на медианном кадре показал четыре исполнения framegraph и четыре
`RenderContext2::submit` за logical frame. Из примерно 20 мс `SceneManager
Render` основная CPU-стоимость пришлась на повторные geometry consumers:

- `Shadow`: 7.4--7.8 мс, два вызова;
- `Color`: 6.0--6.2 мс, три вызова;
- `Depth`: около 1.5 мс, четыре вызова;
- `Normal`, `ActorAttributePass`, `Id`: примерно по 1.0--1.1 мс.

В рамках #564 выключенная Vulkan telemetry переведена на единый cached gate:
disabled path не выполняет atomic RMW и `steady_clock` в draw/bind,
pipeline-cache, submit и present instrumentation. Проверка gate выполняется
двумя отдельными CTest-процессами:

```bash
ctest --test-dir build/Release-tests \
  -R '^tgfx2_vulkan_stats_' --output-on-failure
```

Live probe выключенного path:

```bash
TERMIN_EDITOR_MCP=1 \
./sdk/bin/termin_editor \
  ~/project/chronosquad-termin/ChronoSquad.terminproj
```

Контроль включённого path использует тот же запуск с
`TGFX2_VULKAN_STATS=1`. Submit telemetry теперь раздельно печатает
`fence_wait_ms`, `readback_cleanup_ms`, `destroy_cleanup_ms` и
`descriptor_cleanup_ms`; прежний общий `fence_wait_ms` включал все эти
операции. На сравнимых, но не лабораторно идентичных capture медиана active
frame изменилась с 22.10 до 21.45 мс. Это ориентировочные ~0.65 мс: первый
capture одновременно печатал backend/render telemetry, поэтому результат не
следует трактовать как строгий isolated A/B.

В рамках #566 ShadowPass перестал планировать один и тот же caster сначала при
collection, а затем заново для каждого каскада каждого directional light.
Один lifetime-safe `RenderTaskList` теперь строится на execution, а
каскадно-зависимые view/projection, camera, viewport и uniform resource packet
обновляются непосредственно перед submit. Сортировка по окончательному shader
variant сохранена через невладеющий список указателей, поэтому owned shader
usages и pass-specific model payload не перемещаются из RAII-хранилища.

На том же ChronoSquad Play Mode probe после прогрева, без backend telemetry и
с выключенным UI profiling, 120 кадров дали:

- active frame p50 20.08 мс, p95 21.63 мс, p99 23.39 мс;
- `SceneManager Render` 17.91 мс;
- `ShadowPass` 4.90 мс против предыдущих 7.40 мс (около -2.50 мс, -34%);
- `ColorPass` 6.45 мс, поэтому общая frame delta меньше изолированной shadow
  delta: active p50 улучшилась примерно с 21.46 до 20.08 мс.

Скриншот live-кадра подтвердил сохранение каскадных теней. Штатные
`./build-sdk.sh --no-wheels` и `./run-tests.sh` прошли полностью; центральный
C/C++ набор содержит 80 тестов, включая Vulkan stats gate, а Python working
set и lint также завершились без ошибок.

В рамках #567 тот же invariant применён к ColorPass. Раньше pass планировал
item при collection ради final shader sort key, а после сортировки создавал
новую задачу повторным вызовом `plan_render_item_task`. Теперь rejected items
отбрасываются до lighting batch, один owned `RenderTaskList` переживает
priority/shader/distance sort, а submission order собирается по стабильному
collected item index. Порядок draw calls меняется, но RAII-состояние задач и
указатели на scene item не перемещаются.

Повторный 120-frame capture на той же конфигурации показал:

- active frame p50 18.99 мс, p95 21.00 мс, p99 21.76 мс;
- `SceneManager Render` 16.77 мс;
- `ColorPass` 4.58 мс против 6.45 мс после shadow-среза (около -1.87 мс,
  -29%);
- `ShadowPass` остался на 4.76 мс;
- совокупная active p50 после #564--#567 снизилась примерно с 21.46 до
  18.99 мс.

Live screenshot сохранил материалы и каскадные тени; priority/shader/distance
ordering остаётся на прежнем коде сортировки. После ColorPass-среза штатная
SDK-сборка и центральный test workflow повторены.

## Общий RenderItem snapshot (#555)

Geometry collection переведён с pass-owned collectors на один lazy immutable
snapshot для каждой пары scene/render-target-view внутри
`render_scene_pipeline_offscreen`. `RenderEngine` владеет переиспользуемым
scratch pool, явно инвалидирует содержимое на границе execution и сохраняет
capacity item/payload/route storage между кадрами. Разные viewport cameras,
layer masks и category masks получают независимые snapshots.

Новый producer contract использует пустой `phase_mark` как pass-neutral
collection: drawable обязан за один вызов опубликовать все phase-варианты.
Mesh, skinned mesh, direct/mesh lines, world text, foliage, navmesh C++ и
существующие Python producers поддерживают этот режим. Snapshot заранее
строит сохраняющие capacity buckets `phase_mark -> item indices`; Color и
Shadow обходят только соответствующий bucket, а Id/Depth/DepthOnly/Normal
выбирают один representation на primitive identity без повторного producer
call.

Owned line/text/foliage payload теперь переиспользует storage между кадрами и
не копируется повторно для соседних material-phase вариантов. Material phases
хранят canonical owner handle/index, поэтому `tc_material_find_phase_ref`
проверяет ссылку за O(1), без прежнего reverse scan всего material pool.

При `TERMIN_RENDER_ENGINE_TIMING=1` строка RenderEngine timing дополнена
`avgRenderItems{sceneTraversals, producers, items}`. Контрактный C++ test
проверяет один traversal/producer invocation, отдельный snapshot второй view,
compact phase payload reuse и сохранение scratch capacity после invalidation.

Live-smoke ChronoSquad потребовал синхронной миграции пяти project-side C++
producer'ов (`ActionPreviewComponent`, `ShootEffectVisualController`,
`BlinkEffectVisualController`, `LedgeComponent`, `CornerLeanZone`): они также
публикуют все свои phase-варианты при пустом `phase_mark`. Legacy fallback в
движок не добавлялся; несовместимый producer останавливает построение snapshot
с диагностикой.

После прогрева Play Mode устойчивый timing interval показал 458 render
executions (примерно четыре viewport execution на frame):

- `sceneTraversals=1.00` при среднем `producers=57.79`, `items=98.56`;
- ни одного повторного producer traversal из Color/Shadow/Id/Depth/Normal;
- средний `RenderEngine total=4.04` мс на execution, то есть примерно 16.2 мс
  на четыре execution кадра;
- Frame Profiler capture на 791 кадр: p50 19.82 мс, p95 22.72 мс,
  p99 24.98 мс. Это контроль корректности и архитектурного invariant, а не
  чистое A/B: число активных viewport и фоновые editor tasks в срезе не
  зафиксированы так же строго, как в измерениях #564--#567.

Скриншот живого Play Mode подтвердил сохранение основного изображения,
материалов и теней. Smoke одновременно обнаружил отдельные дефекты, не
включённые в #555: спам NormalPass для vertex layouts без normal attribute
(#583) и подозрительный lifetime prototype mesh у foliage RenderItem (#584).

## Ограничения и состояние репозитория

- Аудит не заменяет CPU/GPU profile конкретной сцены.
- Исходный статический проход не выполнял runtime measurements и не менял код;
  live-проходы и реализации #564/#566/#567 добавлены позднее отдельным
  разделом выше.
