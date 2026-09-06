# Аудит готовности графического стека к production — 2026-09-06

После аудита выполнен [первый пакет исправлений](2026-09-06-graphics-repair-pass-1.md):
#2197, #2198, #2199 и #2203 закрыты. Ниже сохранены исходные результаты аудита;
актуальные изменения и результаты проверок приведены в отчёте об исправлениях.

## Вывод

У стека есть пригодная для дальнейшего развития архитектурная основа, но считать
текущую реализацию production-ready нельзя. Найдены воспроизводимые ошибки памяти,
ошибки OpenGL при обычных операциях и массовые нарушения синхронизации Vulkan.
Есть также доказуемые по коду нарушения публичного контракта D3D11/WebGPU и потери
метаданных между framegraph и физическими ресурсами. Успешный CTest сейчас не
означает корректный GPU execution: validation errors не превращаются в ошибки тестов.

Главное направление работы — сделать существующий backend-neutral контракт
проверяемым от публичного descriptor до native submission и lifetime ресурса.
Для этого не требуется переписывать весь стек или сливать framegraph с GPU API.
Нужны ясные границы владения, порядка команд, capabilities и ошибок, после чего
можно последовательно закрывать конкретные нарушения общими механизмами.

## Область, метод и ограничения

- Проверены `graphics/termin-graphics`: C registry, Python texture bindings,
  tgfx2 interfaces, GraphicsHost/RenderContext2, caches/pools, reusable renderers,
  OpenGL, Vulkan, D3D11 и WebGPU; дополнительно — потребители в render-core,
  graph compiler, display presenter и shadow pass.
- Базовый HEAD: `a5d4b82475f8910301537f79d5c586f0ddd53ecb`. Аудит относится к
  локальному рабочему дереву на дату отчёта; дерево содержит параллельные изменения.
- **R — воспроизведено:** выполненная проверка показала нарушение инварианта.
  **S — подтверждено кодом:** конкретная ветка нарушает контракт; platform runtime
  для этого случая не запускался. **A — архитектурный риск:** отсутствует нужная
  гарантия или контракт, а реальная достижимость зависит от способа использования.
- P1 — ошибка памяти, зависание, нарушение GPU synchronization либо потеря
  корректности базовых операций. P2 — ограниченный сценарий, утечка, неверная
  capability/метаданные или функция, которую API принимает, но не реализует верно.
  Приоритет платформенного дефекта зависит от того, входит ли платформа в релиз.
- Runtime: Linux; OpenGL 4.5 core, llvmpipe LLVM 20.1.2, Mesa 25.2.8.
  Windows/D3D11, browser/WebGPU и Quest/Adreno в этом проходе не проверялись.
  Успех на llvmpipe не является проверкой всех desktop GPU; static findings
  не представлены как наблюдённые артефакты на Windows, в браузере или на Quest.
- Это аудит, а не проход исправления реализации. Отдельные диагностические
  программы в `/tmp` не заменяют постоянные regression tests.

## Что фактически показали проверки

Центральная команда:

```bash
BUILD_JOBS=8 TGFX2_VULKAN_VALIDATION=1 \
  VK_LAYER_ENABLES=VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT \
  task test:cpp
```

Получено 233 прошедших CTest execution; ещё четыре inventory entries пропущены.
При этом 22 регистрации тестов печатают в сумме **4300 validation errors**:

| Сообщение | Количество | Что подтверждает |
| --- | ---: | --- |
| `SYNC-HAZARD-READ-AFTER-WRITE` | 4294 | Отсутствующие зависимости между записью и чтением GPU ресурсов |
| `VUID-VkImageMemoryBarrier-oldLayout-01211` | 4 | Некорректное использование image layout относительно usage |
| `VUID-VkShaderModuleCreateInfo-pCode-08737` | 2 | SPIR-V 1.5 передан устройству с контрактом Vulkan 1.0 |

Это количество сообщений, а не 4300 независимых багов. Нельзя закрывать их
подавлением callback: обязательна корректировка команд и regression gates.
Первый запуск внутри sandbox имел три сбоя из-за `socket: EPERM`; повторный
разрешённый запуск прошёл. Эти три сбоя не классифицированы как баги продукта.

Дополнительные probes дали следующие результаты:

| Проверка | Результат |
| --- | --- |
| C API: RGB 1×1 → `prepare_tc_texture_upload`, ASan | Heap-buffer-overflow: чтение четырёх байт из allocation в три байта |
| Vulkan `create_shader`: bytecode длиной 5 байт, ASan | Heap-buffer-overflow: запись пяти байт в allocation на четыре байта |
| Move assignment непустого `TexturePool` | Создано 2 texture, уничтожена 1 |
| Move assignment непустого `RenderTargetPool` | Создано 4 texture, уничтожены 2 |
| OpenGL: семь независимых инвариантов | Все семь нарушены; подробности ниже |

## 1. Безопасность CPU данных и базовое владение

### 1.1. RGB данные маркируются RGBA8 и читаются за границей allocation — P1, R, #2197

[`tc_texture_registry.c:456–477`](../../graphics/termin-graphics/src/resources/tc_texture_registry.c#L456)
выделяет `width * height * channels`, но безусловно записывает формат RGBA8.
[`tc_texture_upload.cpp:274`](../../graphics/termin-graphics/src/tgfx2/tc_texture_upload.cpp#L274)
затем копирует размер, вычисленный по формату. Обычный RGB 1×1 даёт allocation=3,
declared_bytes=4 и ASan heap-buffer-overflow. Это путь с корректными RGB входными
данными, без необходимости подавать повреждённый файл.

[`texture_bindings.cpp:52,107–119`](../../graphics/termin-graphics/python/bindings/texture_bindings.cpp#L52)
использует format-based размер для `.data`; `from_data` также не сверяет размер
ndarray с запрошенными dimensions/channels. Последствия этих Python путей
подтверждены анализом, отдельно в Python не воспроизводились.
Нужен единый validated texture data descriptor: формат, размер буфера, dimensions,
mip layout, проверенная арифметика размеров и явная нормализация каналов.

### 1.2. Некратный четырём SPIR-V bytecode переполняет CPU vector — P1, R, #2203

[`vulkan_pipeline_resource_sets.cpp:149–150`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_pipeline_resource_sets.cpp#L149)
выделяет `bytecode.size()/4` слов, затем копирует все `bytecode.size()` байт.
Обрезанный artifact длиной 1–3 байта пишет в нулевой vector; другие некратные
четырём размеры переполняют его на 1–3 байта. Перед копированием отсутствует
проверка длины, минимального заголовка и SPIR-V формата. Исправление должно
отклонять артефакт с диагностикой его происхождения до reflection/native calls.
Дополнительный probe на текущей `build/Release/bin/libtermin_graphics2.so`
с payload `{3, 2, 35, 7, 0}` подтвердил ASan `WRITE of size 5` за allocation
размером четыре байта внутри `VulkanRenderDevice::create_shader`.

### 1.3. Move assignment GPU pools теряет старые native resources — P2, R, #2198

[`texture_pool.hpp:35,78`](../../graphics/termin-graphics/include/tgfx2/texture_pool.hpp#L35)
объявляет default move assignment. При замене непустого destination его vector
уничтожает прежние entries, у которых нет освобождающего native handles destructor.
Pool destructor позднее видит только новые entries. Probe подтвердил утечку для
обоих типов. Нужен единственный путь освобождения с явным owning/borrowed
контрактом; assignment обязан освободить прежнее владение до его замены.

## 2. Vulkan: синхронизация, submission и presentation

### 2.1. Upload/copy буфера не создаёт зависимости до draw — P1, R + S, #2200

[`vulkan_transfer.cpp:227–233`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_transfer.cpp#L227)
и `vulkan_command_list.cpp:545–556` записывают `vkCmdCopyBuffer` без дальнейшего
barrier. Submission в `vulkan_render_device.cpp:1665–1697` рассчитывает на порядок
command buffers. Он не заменяет execution/memory dependency. В реализации нет
access masks для vertex/index/uniform read; validation фиксирует upload→draw hazards.
Затронут обычный путь mesh/fullscreen quad/line/point rendering. Перезапись
используемого GPU buffer также требует зависимости от предыдущих readers.

### 2.2. Image transitions не описывают реальных consumers — P1, R + S, #2201

[`vulkan_transfer.cpp:120–154`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_transfer.cpp#L120)
не задаёт destination transfer-read access для `TRANSFER_SRC_OPTIMAL`, а shader
read связывает только с fragment stage. Readback/copy после записи получает
неполную dependency; vertex sampling тоже исключён из stage coverage.
Маски и стадии должны выводиться из usage конкретной операции и subresource,
а не только из имени layout. Проверки должны покрывать transfer и vertex consumers.

### 2.3. Swapchain error paths могут навсегда оставить fence/semaphore без signal — P1, S, #2205

[`vulkan_swapchain.cpp:306–309,382–401`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_swapchain.cpp#L306)
сбрасывает frame fence до acquire. Некоторые ошибки acquire выходят без submit,
поэтому следующий frame ждёт несигнализируемый fence. Ветка отсутствующего source
submit-ит пустую работу без signal semaphore, затем передаёт этот semaphore в
present; также отсутствует требуемый переход image в present layout.
Нужна небольшая явная state machine acquire→record→submit→present; fence следует
сбрасывать перед реально выполняемым submit. Проверять ошибки через fault injection.

### 2.4. Present semaphores переиспользуются по frame slot — P1, S, #2206

[`vulkan_swapchain.cpp:262–276,530–549`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_swapchain.cpp#L262)
выбирает `render_finished` по `current_frame_`. Graphics fence не подтверждает,
что presentation engine уже завершил ожидание этого semaphore. Нужен semaphore
на acquired swapchain image либо явный present-completion механизм.
Реальное проявление зависит от WSI scheduling; window stress в аудите не выполнен.

### 2.5. Разные graphics/present queue families выбираются, но ownership не передаётся — P1, S, #2207

`vulkan_render_device.cpp:538–551` допускает отдельную present queue;
[`vulkan_swapchain.cpp:198,422–449`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_swapchain.cpp#L198)
создаёт exclusive swapchain без корректных release/acquire ownership transfers.
На устройстве с разными queue families это нарушение native контракта.
Нужно реализовать ownership transfer либо согласованное concurrent sharing.

### 2.6. Readback не обеспечивает host visibility и cache invalidation — P1/P2, S, #2202

[`vulkan_transfer.cpp:495–498,579–583,664–668,944–948,1063–1065`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_transfer.cpp#L495)
читает mapped GPU_TO_CPU allocations без `vmaInvalidateAllocation`; transfer→host
read barrier тоже отсутствует. GPU_TO_CPU не гарантирует coherent memory.
На non-coherent allocation можно получить старые picking/depth/capture данные.
Общий readback helper должен владеть barrier, ожиданием, invalidate и проверкой
формата/размера. Ожидание fence и map сами по себе этот протокол не заменяют.

### 2.7. Неуспешные native операции переводят состояние как при успехе — P1, S, #2213

[`vulkan_render_device.cpp:1628–1704`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp#L1628)
игнорирует результаты wait/reset/submit и отмечает fence in-flight после любого
`vkQueueSubmit`. `vulkan_transfer.cpp:218–225,284–291` не проверяет allocation/map
перед `memcpy`; command-list allocation/begin/end также не везде проверены.
OOM/submit failure может стать CPU crash или последующим бесконечным ожиданием.
Нужен checked-result policy и error/device-lost state, запрещающий дальнейшие
success-only переходы. Частично созданные native объекты требуют RAII cleanup.

### 2.8. Shader target не согласован с API устройства — P1/P2, R, #2204

[`vulkan_shader_compiler.cpp:191–193`](../../graphics/termin-graphics/src/tgfx2/vulkan/vulkan_shader_compiler.cpp#L191)
всегда выбирает Vulkan 1.2/SPIR-V 1.5, а устройство может запрашивать Vulkan 1.0
(включая Android default). В cache key target отсутствует. Два validation errors
в центральном прогоне подтвердили несовместимость именно в API 1.0 smoke scenario;
это не общий shader failure на desktop Vulkan 1.2. Нужен согласованный negotiated
target в compiler, artifact resolver и cache identity; проверять его на Vulkan 1.0.

## 3. Vulkan: дополнительные нарушения публичного контракта

| Приоритет/статус | Дефект и сценарий | Опорные места |
| --- | --- | --- |
| P2, S | Offset обычного, не ring UBO теряется: descriptor offset и dynamic offset становятся нулём; две subrange читают начало buffer | `vulkan_pipeline_resource_sets.cpp:563–565,727–745` |
| P2, S | `PipelineDesc.color_mask` игнорируется: write mask всегда RGBA | `vulkan_pipeline_resource_sets.cpp:499–500` |
| P2, S | `clear_texture(..., viewport)` очищает весь image | `vulkan_render_device.cpp:2269–2284` |
| P2, S | Storage textures рекламируются, но bind отклоняется; отдельный sampled-image descriptor принимается layout-ом, но не заполняется | `vulkan_pipeline_resource_sets.cpp:574–617,721–795` |
| P2, S | Compute capability не обеспечена публичным compute pipeline; geometry/anisotropy/depthBiasClamp используются без полного enabled-feature контракта | `vulkan_render_device.cpp:244–257,557–574`; `vulkan_pipeline_resource_sets.cpp:254–265,328–329,471` |
| P2, S | `max_texture_units` берётся из `maxBoundDescriptorSets`, то есть из другой аппаратной величины | `vulkan_render_device.cpp:243` |
| P2, S/A | ResourceSetHandle зависит от frame pool; reset после шести submit либо destroy постороннего ресурса инвалидирует retained sets | `vulkan_render_device.cpp:1637–1641,1405–1418`; `vulkan_pipeline_resource_sets.cpp:669–683` |
| P2, S | Жёсткий pool: 2048 sets / 512 storage descriptors; ring sets не переиспользуются, превышение обрывает обычный many-draw frame | `vulkan_render_device.cpp:737–750`; `vulkan_pipeline_resource_sets.cpp:649–665` |
| P2, S | Dynamic offsets молча ограничены восемью; для descriptor arrays порядок элементов не гарантирован | `vulkan_pipeline_resource_sets.cpp:805–811` |
| P1/P2, S | RGBA8 pixel readback не проверяет формат/sample count и выделяет четыре байта даже для RGBA16F/RGBA32F GPU copy | `vulkan_transfer.cpp:504–518,1004–1020` |
| P2, S | Depth MSAA отправляется в color-only resolve; multisample blit и финальный sampled layout не проверяют допустимость | `vulkan_command_list.cpp:617–704`; `vulkan_render_device.cpp:2231–2244` |
| P2, S | Единственный image view охватывает все mips, затем используется как framebuffer attachment | `vulkan_render_device.cpp:1225–1226` |

Эти случаи требуют общей descriptor/operation validation и явной lifetime модели
sets; исправления отдельных `if` без уточнения контракта оставят соседние пути.
Capabilities должны означать работоспособную публичную операцию от shader/layout
до draw/dispatch, а не наличие возможности только у physical device.

## 4. OpenGL: семь воспроизведённых дефектов

Полный probe использует небольшой 8×8 target и намеренно проверяет состояние
между операциями. Успешный exit code означает завершение диагностики, а не
прохождение проверок. SDK и build GL library совпадали по SHA256.

| Приоритет | Нарушение | Воспроизведение и влияние |
| --- | --- | --- |
| P1 | Upload не устанавливает unpack layout | R8 3×2 `[10,20,30;40,50,60]` возвращает верхний ряд `20,30,0`. Default `GL_UNPACK_ALIGNMENT=4` несовместим с tightly packed rows; native чтение может выйти за временный CPU buffer |
| P1 | MSAA resolve наследует последнюю draw scissor | Clear всего MSAA target красным, финальная scissor 1×1, resolve поверх синего: pixel(4,4) остаётся синим |
| P1/P2 | Device destructor удаляет borrowed external texture/buffer | После teardown `glIsTexture/glIsBuffer` меняются `1→0`, хотя ownership осталось у host |
| P2 | `clear_texture` игнорирует rectangle | Clear 1×1 поверх синего 8×8 делает pixel(4,4) красным; viewport не ограничивает `glClear`, inherited scissor тоже влияет |
| P2 | Частичный blit использует bottom-up y | Blit в верхнюю половину по публичному top-left контракту окрашивает нижнюю; display presenter использует viewport rectangles |
| P2 | Sync depth readback меняет draw framebuffer state | `GL_DRAW_BUFFER` меняется с COLOR_ATTACHMENT0 на NONE: `glDrawBuffer` применён к caller draw FBO при binding только READ FBO |
| P2 | Buffer upload сбрасывает index binding текущего VAO | После index upload EBO меняется `2→0`; последующий indexed draw лишается ранее установленного buffer |

Опорные места:
[`opengl_render_device.cpp`](../../graphics/termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp)
`:245–253,733–736,1192–1194,1214–1272,1283–1290,1497–1504,1527–1547`;
[`opengl_command_list.cpp:162–185`](../../graphics/termin-graphics/src/tgfx2/opengl/opengl_command_list.cpp#L162);
[`opengl_texture_readback.cpp:66–72,133–138`](../../graphics/termin-graphics/src/tgfx2/opengl/opengl_texture_readback.cpp#L66).

Для borrowed teardown не найден текущий production GL consumer помимо самого
публичного interop API. Partial clear в presenter сейчас обычно full-target,
но inherited scissor затрагивает и такой вызов. Depth readback используется в
editor picking/frame capture; новый begin-pass может маскировать повреждение state.
Это уточняет достижимость, не отменяя подтверждённого нарушения контракта.

Нужен единый GL state ownership contract и общие transfer/attachment helpers:
pixel-store/PBO state, top-left rectangles, scissor, FBO bindings, sRGB и ownership
должны устанавливаться там, где операция от них зависит. Buffer transfer следует
отделить от binding target, являющегося VAO state. Полные глобальные resets между
passes не исправляют readback/upload внутри pass и слишком дороги как основная модель.

Дополнительно подтверждено кодом: sampling shim в `opengl_render_device.cpp:830–852`
переворачивает `texture`, но не `textureLod/textureGrad`; overload с третьим
аргументом превращает bias в абсолютный LOD. Center-pixel smoke это скрывает.
Текущего production shader consumer explicit LOD/Grad не найдено. Legalization
координат лучше перенести в shader compilation, с явным покрытием операций.
Creation часто возвращает valid-looking handle после GL error; invalid bindings
могут оставлять предыдущий ресурс, а `first_instance!=0` логируется и рисуется
с неверной семантикой. Эти пути должны завершаться однозначной ошибкой.

## 5. D3D11 и WebGPU: подтверждено статически

### D3D11 — P2

[`d3d11_render_device.cpp:944–952`](../../graphics/termin-graphics/src/tgfx2/d3d11/d3d11_render_device.cpp#L944)
делает любой upload CPU-visible buffer через `WRITE_DISCARD`, затем записывает
только patch. Вызов с offset или коротким prefix теряет гарантию сохранения всего
остального buffer. Публичный offset API предполагает sub-update; current tcplot
append buffers не CPU-visible, поэтому текущая регрессия tcplot здесь не заявляется.
Замена на `NO_OVERWRITE` сама по себе неверна без контракта in-flight ranges.

Дополнительные S/A: pipeline хранит ShaderHandles и при bind заново находит VS/PS,
поэтому lifetime pipeline зависит от недокументированного lifetime shader;
timestamp capability=true не подкреплена frame-timing hooks; MSAA raw copy
передаёт запрещённый ненулевой source box (`d3d11_render_device.cpp:1306`).

### WebGPU — P1 для полного browser renderer, P2 для отдельных операций

| Нарушение | Причина и обязательная проверка |
| --- | --- |
| Binding layout теряет sample/access/sampler type | `WebGpuLayoutEntry` не несёт нужную семантику; Texture всегда Float, sampler Filtering, StorageBuffer writable. D32F/comparison, portable R32F textureLoad и read-only vertex storage требуют других layouts |
| Pipeline теряет raster state | `webgpu_render_device.cpp:1185–1198` не переносит depth bias и polygon mode. Shadow pass задаёт slope bias, который backend потеряет; wireframe молча превращается в fill |
| Indexed strips не могут быть корректно созданы | При допустимых LineStrip/TriangleStrip отсутствует `stripIndexFormat`; его нет и в canonical PipelineDesc. Проверять оба index types |
| Sampling view используется как attachment view | `webgpu_render_device.cpp:1019` создаёт default view всех mips; `webgpu_command_list.cpp:67,85` использует его в pass, где нужен один mip |

Опорные места для layouts:
[`webgpu_render_device.hpp:25`](../../graphics/termin-graphics/include/tgfx2/webgpu/webgpu_render_device.hpp#L25),
[`webgpu_render_device.cpp:1092–1110,1266`](../../graphics/termin-graphics/src/tgfx2/webgpu/webgpu_render_device.cpp#L1092).
Также `attribute_count` в loop `:1139` не ограничен вместимостью массива: malformed
native descriptor способен вызвать CPU out-of-bounds read. Нужна общая validation.

Ограниченный RGBA8 2D browser showcase не доказывает эти функции и не объявляется
сломавшимся. Нужны actual browser bind-group/pipeline/draw проверки: offline WGSL
validation не обнаружит неправильный native layout, построенный C++ backend-ом.

## 6. Shared renderers и framegraph integration

| Приоритет/статус | Дефект | Триггер и направление решения |
| --- | --- | --- |
| P1 условно, S | FontAtlas смешивает devices bitmap/SDF и upload-ит до owner check | Atlas A→SDF на B→bitmap на B оставляет числовой handle A в B; возможна запись в постороннюю texture с совпавшим ID. Нужен per-device atlas либо строгий single-device owner token |
| P2, S | Atlas isolated host не освобождает textures | `release_gpu` проверяет равенство global application device, поэтому drops handles live isolated host; global pointer не доказывает lifetime произвольного device |
| P2, S | Utility renderers удерживают shaders после reload | Text2D/3D, Canvas2D, lines/points проверяют только device pointer/nonzero handles; второй consumer refresh-ит cache и уничтожает старые shaders первого. Нужны registry generation/version и resolver revision |
| P2, S | `ResourceSpec.scale/viewport_name` не участвуют в allocation | Scale=0.5 для 1920×1080 остаётся 1920×1080, то есть 4× intended pixels; named target другого размера также игнорируется |
| P2, S | Authored clear/filter metadata теряется в template | `tc_pipeline_template` не хранит clear_color/depth/filter; resource-node значения не переживают template→instance |
| P2, S | Split color/depth resources не получают requested clear | Runtime явно пропускает clear для color_texture/depth_texture; composed FBO не совпадает с именем исходного attachment для deferred clear |

Опорные места: [`font_atlas.cpp:570–620,731–795`](../../graphics/termin-graphics/src/tgfx2/font_atlas.cpp#L570);
`text2d_renderer.cpp:114`, `text3d_renderer.cpp:89`, `canvas2d_renderer.cpp:1072`,
`point_cloud_renderer.cpp:195`, `line_renderer_common.cpp:22,54`;
[`render_engine.cpp:428,644–798,1586–1601`](../../graphics/termin-render-core/src/render_engine.cpp#L428);
[`tc_pipeline_template.h:39–50`](../../graphics/termin-render-core/include/render/tc_pipeline_template.h#L39);
`engine/termin-render/src/graph_compiler.cpp:897–945,1085–1116`.

Для FontAtlas требуется разделение устройств; обычный single-device editor этот
сценарий не доказывает. Для shader reload важно проверять два одновременно живых
renderer instances и новый pipeline state после reload. Resource metadata нужно
один раз сохранять в canonical descriptor и одинаково разрешать для allocation,
export eligibility, viewport, initialization и inspection по physical attachment.

## 7. Оценка архитектуры и оставшиеся риски

Сильные стороны: `GraphicsHost` уже объединяет device/cache/context и interop domain;
`IRenderDevice/ICommandList` отделяют consumers от native API; semantic shader
contract и artifact resolver дают основу общей reflection; typed color и общий
top-left контракт уменьшают неоднозначность; generational `tc_*` registry защищает
от обычного повторного использования stale registry slot. Граница GPU utilities
и framegraph в документации выбрана разумно. D3D11 использует COM ownership и
очищает SRVs на границах passes; WebGPU имеет uncaptured-error/device-loss hooks.

Эти решения пока не образуют сквозных гарантий:

1. **Capabilities и validation.** Обязательный baseline, optional features,
   включённые native features и limits должны описывать одну реальность.
   Неподдерживаемый descriptor отклоняется до выдачи handle; ошибка не оставляет
   старый binding или «успешный» draw с другой семантикой.
2. **Порядок команд и synchronization.** Vulkan `execute_immediate` фактически
   откладывает prelude перед draw CB. Поздний clear/blit/upload может изменить
   API order; `current_layout` меняется при recording, включая abandoned lists.
   Нужен согласованный command stream или command-local state reconciliation
   при submit. Persistent CPU-visible buffers требуют in-flight ownership/renaming;
   существующий RenderContext uniform ring не объявляется сломанным.
3. **Device, lifetime, subresource identity.** Числовой handle и raw device pointer
   недостаточны для cross-device/recreation безопасности. Frame-local и persistent
   descriptors требуют разных lifetime гарантий. Texture views должны явно нести
   mip/layer/aspect. Framebuffer cache по raw VkImageView требует eviction при
   destroy; скрытое обязательство caller вызвать отдельную invalidation ненадёжно.
4. **Владение потоками.** Vulkan tc-cache header обещает any-thread безопасность,
   но map mutex не защищает shared handle pools, command pool, queues и invalidation.
   GL registry destroy hooks требуют current context. Нужно выбрать явную renderer
   thread/context affinity и очередь upload/retirement либо доказать синхронизацию
   всего reachable пути. В этом аудите race detector/stress не запускался.
5. **Compiled frame plan.** Extents, physical resource liveness, initialization,
   sampling metadata и output ownership должны быть вычислены в одном валидированном
   immutable плане из простых descriptors. Сейчас authoring/template/allocation/execution дублируют часть
   модели, теряют поля и повторно строят maps/specs/contexts каждый execution.
6. **Error-state и conformance.** Allocation/compile/submit failure обязаны иметь
   лог и однозначный результат; device-lost требует управляемого shutdown/recreate.
   Проверка результата rendering и validation errors должна быть release gate.

Отдельные performance smells: GL создаёт/удаляет VAO на каждом pipeline bind;
transient buffer reuse без orphan/явного ring retirement может вызывать stalls;
Vulkan sets имеют cliff capacity и per-draw allocations. Их следует измерять после
закрытия correctness blockers, сохраняя уже заведённые задачи по performance.
В D3D11 уже есть pooled high-water transient uniform buffers
(`d3d11_render_device.cpp:1036–1095`); старое утверждение #561 о новом constant
buffer на каждый upload не описывает текущий код. Description #561 актуализирован
по этому результату; в #1317 выделены ссылки на конкретные SPIR-V/copy/descriptor
follow-ups и заменены старые команды сборки/тестов штатным Taskfile workflow.

## 8. Порядок доведения до production

| Этап | Содержание | Критерий выхода |
| --- | --- | --- |
| 1. Безопасность и честные проверки | RGB/SPIR-V bounds, pool ownership, checked native failures; validation errors делают тест красным | ASan probes превращены в regression tests; центральные тесты не скрывают validation |
| 2. Базовая корректность Linux backend-ов | Vulkan buffer/image/host dependencies и WSI state machine; семь GL defects | Zero validation errors; pixel/state tests проходят на asymmetric images и polluted GL state |
| 3. Сквозной публичный контракт | Extent/clear/filter metadata, UBO offsets, masks, transfer legality, capabilities, shader reload/device ownership | Backend conformance suite имеет общие ожидаемые результаты и явные unsupported cases |
| 4. Lifetime и устойчивость | Device/generation identity, frame/persistent sets, subresource views, compiled resource plan, retirement/error state | Resize/reload/recreate, failure injection и много кадров не дают stale resources/утечек/зависаний |
| 5. Платформенная приёмка и производительность | D3D debug layer, browser validation, реальный Quest/Adreno, discrete GPU/WSI matrix; allocation/draw profiling | Каждая заявленная release platform проходит свой native и визуальный gate; бюджет кадра измерен |

Минимальный набор regression scenarios: odd-width R8/RG8/RGB upload; top/bottom
asymmetric images; partial clear/blit и сохранность pixels вне rect; MSAA resolve
после scissor; draw после depth readback/index upload; borrowed resources после
teardown; middle buffer patch; nonzero UBO offset; retained resource set через
frames; два devices с совпадающими handle IDs; template roundtrip и split clears;
shader reload при двух renderers; mip attachment/depth sampling/vertex storage.
Для WSI нужны resize/minimize/recreate, отдельные queue families и acquire/submit
failure injection; для readback — non-coherent configuration.

## 9. Связь с доской

Существующие карточки дают контекст, но их старые описания не являются доказательством
текущего состояния кода: #95 — интерфейсы; #554 — compiled execution plans;
#556 — frame ownership; #557 — reachable outputs; #560 — state resets;
#561 — allocations; #562 — dirty scheduling; #1576 — transient overflow 8 MiB;
#1926 — Wayland; #1317 — Quest follow-ups; #2156 — shader cache.
Новые конкретные нарушения следует связывать с этими направлениями, сохраняя
отдельные acceptance criteria для memory safety, synchronization и WSI correctness.

По итогам прохода создан umbrella **#2230** и 33 предметные карточки **#2197–2229**:
32 переведены в Ready, #2212 оставлена в Backlog для декомпозиции lifetime/arena
контракта. Состояния приведены на дату аудита. Карта тем:

| Направление | Карточки |
| --- | --- |
| CPU texture payload; pool move; validation gate | #2197; #2198; #2199 |
| Vulkan buffer/image/host synchronization | #2200; #2201; #2202 |
| SPIR-V input safety и API target | #2203; #2204 |
| WSI errors, present semaphore reuse, queue ownership | #2205; #2206; #2207 |
| Vulkan capabilities, UBO offset, color mask | #2208; #2209; #2210 |
| Clear rectangle; descriptor lifetime; native errors; attachment views | #2211; #2212; #2213; #2214 |
| GL unpack; resolve; borrowed teardown | #2215; #2216; #2217 |
| GL partial blit; depth-read state; EBO state; sampling legalization | #2218; #2219; #2220; #2221 |
| FontAtlas ownership; renderer shader reload | #2222; #2223 |
| Resource extent/target и authored initialization | #2224; #2225 |
| D3D partial uploads | #2226 |
| WebGPU binding types; raster state; indexed strips | #2227; #2228; #2229 |

Дальнейшие исследования command ordering, thread promises, transfer legality
и device loss записаны в #2230; отсутствие отдельной карточки не означает, что
эти риски проверены или устранены.

## 10. Воспроизводимость и первичные источники

Локальные артефакты диагностики:

- `/tmp/termin-graphics-audit/last-ctest.log` — полный сохранённый CTest log;
  `/tmp/termin-graphics-audit/validation-errors.log` — выделенные validation errors.
- `/tmp/termin-graphics-audit/texture-probe.cpp` и `texture-probe.log` — RGB ASan;
  `pool-probe.cpp` и `pool-probe` в той же директории — счётчики native lifetime.
- `/tmp/termin-graphics-audit/spirv-probe.cpp` и `spirv-probe.log` — ASan
  воспроизведение записи за allocation при пятибайтном shader bytecode.
- `/tmp/termin-gl-audit-probe.cpp` и `/tmp/termin-gl-audit-probe.log` — семь GL
  проверок. Они собраны против текущего build/SDK; постоянных repo tests пока нет.

Повторение основного прогона приведено выше; для свежей машины сначала штатный
`task build`. `/tmp` временный: для будущего исправления следует перенести нужный
минимальный сценарий в тестовый набор, а не рассчитывать на сохранность binaries.
Не требуется вручную копировать SDK native библиотеки в исходники.

Native API основания выводов:

- Порядок submit не создаёт memory dependency; upload/readback требуют barriers:
  [Vulkan synchronization specification](https://docs.vulkan.org/spec/latest/chapters/synchronization.html),
  [Khronos synchronization examples](https://docs.vulkan.org/guide/latest/synchronization_examples.html).
- Completion graphics fence не равен completion presentation:
  [Swapchain semaphore reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html);
  queue ownership и present wait: [Vulkan WSI](https://docs.vulkan.org/spec/latest/chapters/VK_KHR_surface/wsi.html).
- Mapping не выполняет non-coherent invalidate:
  [VMA memory mapping](https://gpuopen-librariesandsdks.github.io/VulkanMemoryAllocator/html/memory_mapping.html).
- Pixel layout и blit scissor:
  [OpenGL PixelStore](https://wikis.khronos.org/opengl/GLAPI/glPixelStore),
  [Framebuffer operations](https://wikis.khronos.org/opengl/Framebuffer).
- Семантика `WRITE_DISCARD`:
  [Microsoft D3D11_MAP](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/ne-d3d11-d3d11_map).
- WebGPU layout/view/pipeline требования:
  [WebGPU specification](https://www.w3.org/TR/webgpu/),
  [Dawn bind-group validation tests](https://dawn.googlesource.com/dawn/+/d527ffa3c0adb58dfe47c48cf7f3e1c42c4c54b8/src/dawn/tests/unittests/validation/BindGroupValidationTests.cpp).
