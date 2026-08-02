# Termin Web Runtime: feasibility and architecture

Date: 2026-08-02

## Decision

Запуск собранной сцены Termin как веб-приложения реален. Рекомендуемая цель —
не перенос desktop editor целиком и не постоянная трансляция сцены в three.js,
а отдельный `Termin Web Runtime`:

```text
desktop editor/exporter
        |
        v
self-contained runtime package
        |
        v
HTTP fetch -> browser package storage -> Termin C/C++ runtime in WebAssembly
                                           |
                                           v
                                  tgfx2 WebGPU backend
                                           |
                                           v
                                       <canvas>
```

Первый web host должен запускать тот же native scene/component/render runtime,
который потребляет обычный runtime package. Web-specific код должен оставаться
в platform host, package transport и graphics backend. Python, native plugins,
source-project discovery, asset import, file watchers, MCP и runtime shader
compilation не входят в первый web profile.

Это не требует переписывания scene model или engine на JavaScript. Основные
новые подсистемы — Emscripten build profile, tgfx2 WebGPU backend, offline WGSL
shader target и тонкий browser host.

## Product variants

Под общей формулировкой «Termin в вебе» скрываются три продукта с разной
ценностью и стоимостью.

| Вариант | Реалистичность | Результат |
|---|---:|---|
| Экспорт в three.js/Babylon.js | высокая, быстрый путь | Веб-вьюер, но не runtime Termin |
| Termin Runtime в Wasm + WebGPU | высокая, рекомендуемый путь | Настоящая исполняемая сцена Termin |
| Полный Termin Editor в браузере | технически возможен, дорог | Отдельный многомесячный продукт |

### Exported web viewer

Экспорт meshes, transforms и части материалов в web-native формат подходит для
preview, публикации статических моделей и быстрой демонстрации. Такой путь
полезен, если не нужны component lifecycle, поведение сцены, frame graph и
точное совпадение рендера.

Он не должен становиться каноническим runtime. Иначе появятся две реализации
материалов, света, animation, scene update, picking и UI, которые будут
неизбежно расходиться.

### Termin Web Runtime

Это предпочтительная цель. Desktop toolchain собирает готовый package, а
браузер исполняет native runtime, скомпилированный в WebAssembly. Такой подход:

- сохраняет один scene/component contract;
- использует один runtime package format;
- позволяет разделять большую часть тестов с native runtime;
- не заставляет переносить engine logic в TypeScript;
- отделяет authoring/tooling от deployment target;
- создаёт основу не только для web viewer, но и для интерактивных приложений и
  игр.

### Browser editor

Native UI Termin потенциально можно рисовать в canvas, но полный editor требует
решить значительно более широкий набор задач: project filesystem, dialogs,
clipboard, drag-and-drop, Python и nanobind modules, native module loading,
build tools, asset import, hot reload, subprocesses и интеграцию с ОС.

Поэтому browser editor не должен быть acceptance condition первого web runtime.
Позже он может использовать готовый Wasm runtime как viewport/runtime kernel,
оставляя часть authoring UI в HTML или в native Termin GUI.

## Existing foundations

### Runtime boundary

`termin-runtime` уже определён как встраиваемая C/C++ библиотека для загрузки и
запуска собранного runtime package. Его архитектурная граница явно запрещает
обязательные зависимости на editor, Python, MCP, source discovery, import и
build tooling.

`RuntimePackageLoader` загружает package format version 2, bootstrap-ит native
types, восстанавливает resources и десериализует entry scene. Package уже может
нести:

- shaders и shader programs;
- meshes и textures;
- sprites и materials;
- pipelines;
- foliage data;
- UI documents;
- одну или несколько scenes.

Shader runtime package уже выставляет `dev_compile_enabled = false`. Это
подходящая политика для браузера: все backend artifacts должны производиться
offline exporter-ом.

### Backend-neutral graphics API

tgfx2 уже имеет `IRenderDevice`, `ICommandList`, typed handles и descriptors для
buffers, textures, samplers, shaders, pipelines, resource sets, render passes,
draw/dispatch/copy и presentation. Эта модель хорошо сопоставляется с WebGPU:

```text
tgfx2                         WebGPU
---------------------------------------------------
IRenderDevice                 GPUDevice
ICommandList                  GPUCommandEncoder
PipelineHandle                GPURenderPipeline
ResourceSetHandle             GPUBindGroup
RenderPassDesc                GPURenderPassDescriptor
Buffer/Texture/Sampler        GPUBuffer/GPUTexture/GPUSampler
```

Device factory уже является естественной точкой включения нового
`BackendType::WebGPU` и `WebGpuRenderDevice`.

### Current webscene example

`examples/webscene` подтверждает, что Termin scene data можно показать в
браузере. Python example извлекает vertices, indices, normals и transforms в
JSON, а web page пересобирает сцену в three.js.

Это полезный exporter spike, но не proof of the Termin runtime:

- материалы заменяются на `THREE.MeshStandardMaterial`;
- camera, lights, fog и shadows задаются заново на стороне three.js;
- отсутствуют Termin components и update lifecycle;
- не используется Termin render graph;
- сцена не загружается из runtime package;
- server-side Python остаётся необходим для подготовки данных.

Пример стоит сохранять как демонстрацию export/viewer пути либо заменить в
будущем более общим glTF exporter-ом. Он не должен определять архитектуру web
runtime.

## Proposed architecture

### Web build profile

Нужен явный platform profile, например:

```text
TERMIN_PLATFORM_WEB=ON
TERMIN_BUILD_PYTHON=OFF
TERMIN_BUILD_TESTS=OFF
TERMIN_ENABLE_SDL=OFF
TERMIN_ENABLE_OPENGL=OFF
TERMIN_ENABLE_VULKAN=OFF
TERMIN_ENABLE_WEBGPU=ON
TERMIN_ENABLE_PCH=OFF
```

Web target должен статически линковать необходимый runtime slice в один Wasm
module. Текущая сборка широко использует unconditional `SHARED` libraries,
RPATH и platform-specific optional packages. Build helpers и module CMake
contracts потребуется сделать aware of static WebAssembly composition.

Не следует начинать с эмуляции всего desktop SDK. Web SDK должен содержать
только:

- Wasm runtime module;
- JS/ESM loader;
- HTML host template;
- builtin WebGPU shader artifacts;
- runtime package deployment helpers;
- browser test harness.

### WebGPU backend

Рекомендуемый backend — WebGPU через официальный Emscripten port
`emdawnwebgpu`, предоставляющий Dawn-подобный `webgpu.h` C API поверх browser
WebGPU.

`WebGpuRenderDevice` должен владеть:

- adapter/device acquisition;
- device-lost and uncaptured-error reporting;
- backend resource pools for tgfx2 handles;
- pipeline and bind-group caches;
- command encoding and queue submission;
- canvas surface configuration and resize;
- staging/readback operations;
- explicit capability reporting.

Особое внимание потребуется для асинхронных операций. Browser device creation,
pipeline creation, resource download и readback не должны превращаться в
скрытые blocking calls. Composition root должен иметь явные startup states:

```text
loading wasm
-> acquiring GPU device
-> downloading/mounting package
-> loading runtime resources
-> running
-> device lost/error
```

### Why WebGL2 is not the primary backend

Emscripten умеет SDL и OpenGL ES/WebGL, поэтому WebGL2 кажется коротким путём.
Однако существующий tgfx2 OpenGL backend рассчитан на desktop OpenGL и использует
операции, отсутствующие или ограниченные в WebGL2: polygon mode, clip control,
base-vertex drawing, buffer mapping и другие desktop paths. Builtin shaders
также ориентируются на desktop GLSL profiles.

WebGL2 потребует отдельного capability-restricted backend и shader profile, а
не только нового compiler flag. Он может быть полезен позже для старых
браузеров, но одновременная реализация WebGPU и WebGL2 существенно расширит
первый этап и будет маскировать ошибки лишними fallback paths.

Первый production target следует ограничить WebGPU с feature detection и
явным сообщением о неподдерживаемой платформе.

### Offline WGSL shader pipeline

WebGPU принимает WGSL source. Текущий `termin_shaderc` производит artifacts для
Vulkan, OpenGL и D3D11; необходимо добавить target:

```text
termin_shaderc compile --language slang --target webgpu \
    --stage vertex --input shader.slang --output shader.vert.wgsl
```

Предлагаемый contract:

- Slang остаётся canonical authored language для portable shaders;
- `slangc -target wgsl` запускается только на host build/export machine;
- `.wgsl` и versioned layout sidecar входят в runtime package;
- browser runtime не содержит `slangc` и не запускает subprocesses;
- весь builtin shader catalog компилируется и валидируется в CI;
- package export отклоняет shader, не имеющий WebGPU artifact;
- shader capability profile запрещает неподдерживаемые stages/features до
  запуска приложения.

WGSL backend Slang всё ещё обозначен upstream как work in progress. Это главный
technical-risk spike: нужно проверить реальной компиляцией полный builtin
shader matrix, resource binding placement, matrix layout, texture/sampler
separation, uniform layout и generated WGSL validation.

Geometry shaders в WebGPU отсутствуют. Их использование должно либо исключать
shader из web profile, либо заменяться vertex instancing/mesh expansion/compute
подготовкой в конкретной подсистеме. Не следует имитировать geometry shader
неявным runtime fallback.

### Runtime package transport

Текущий loader использует `std::filesystem` и синхронный `ifstream`. Для MVP
это совместимо с Emscripten virtual filesystem:

```text
fetch package blob/data files
-> mount or unpack into MEMFS
-> load_runtime_package("/package")
```

Это позволяет проверить runtime без преждевременной переделки package loader.
Но production architecture не должна навсегда зависеть от directory-shaped
MEMFS. Следующим шагом нужен `RuntimePackageReader`/`ResourceProvider`, который
отделит package semantics от physical filesystem и позволит:

- загружать единый archive;
- стримить крупные resources;
- использовать HTTP и browser cache;
- не держать лишние копии assets в linear Wasm memory;
- проверять hashes и content identities;
- в будущем переиспользовать provider в Android и embedded hosts.

### Browser host

Desktop `termin-player` не является подходящим web entry point: production
player composition требует Python host, Python modules и SDL window target.
Нужен отдельный тонкий `termin-web-host`, который:

- экспортирует async initialization API в JavaScript;
- получает canvas и package URL/config;
- создаёт WebGPU device;
- создаёт engine/display/runtime composition;
- переводит browser input в Termin input events;
- обслуживает resize, DPR и visibility changes;
- вызывает frame tick через `requestAnimationFrame`;
- публикует structured startup/runtime errors наружу.

JS должен оставаться platform adapter, а не вторым engine layer. Scene update,
components, render planning и resource identity остаются в C++.

### Threads

Первый runtime целесообразно сделать single-threaded. Основной engine/render
путь уже рассчитан на owning render thread, а browser main loop естественно
работает через `requestAnimationFrame`.

Emscripten pthreads доступны через workers и `SharedArrayBuffer`, но deployment
требует COOP/COEP headers. Потоки стоит включать только после измеренного
CPU bottleneck. Они не должны быть условием первого результата.

## Architectural gaps and code smells

### Runtime bootstrap is wider than the declared runtime boundary

Хотя `termin-runtime` имеет правильную концептуальную границу, его обязательная
зависимость на `termin-bootstrap` фактически притягивает широкий набор domain
modules и component registrations: audio, prefab, render passes, collision,
skeleton, voxels, navmesh, FEM, foliage и UI.

Для desktop monorepo это почти незаметно, но в WebAssembly приводит к:

- большому download и compile size;
- увеличению startup time;
- platform blockers из неиспользуемых модулей;
- невозможности честно описать capabilities package;
- слабому dead stripping из-за явных registration calls.

На 2026-08-02 граница разрезана явным `RuntimeBootstrapProfile`. Native default
остаётся `Full`, а `Minimal` регистрирует только core scene domain. Для
Emscripten `TERMIN_BOOTSTRAP_MINIMAL_ONLY` собирает отдельный implementation
unit и линкует только `termin-base`, `termin-inspect` и `termin-scene`, поэтому
desktop domains не просачиваются даже как неиспользуемые зависимости.

`RuntimePackageLoader` принимает выбранный профиль. Minimal package может
содержать core entities без domain resources; неизвестные resource/component
types и scene extensions отклоняются до частичной десериализации с точной
логированной диагностикой. Последующее расширение профиля должно добавлять
малые registration units вместе с соответствующей manifest capability, не
возвращать единый обязательный full bootstrap.

### Shared-library assumptions

Многие runtime libraries объявлены как `SHARED` и используют install/RPATH
policy. Emscripten поддерживает dynamic linking, но он увеличивает размер и
сложность, ограничивает dead-code elimination и не нужен для первого web
runtime. Web profile должен предпочитать static targets и один main Wasm
module.

Native user modules нельзя считать переносимыми автоматически. Если
расширяемость понадобится в web production, модули должны либо компилироваться
в основной Wasm во время export, либо иметь отдельный versioned Wasm module
contract. Desktop `.so`/`.dll` в браузере загрузить невозможно.

### Browser compatibility is a product constraint

WebGPU доступен только в secure context. Chromium является наиболее надёжной
первой целью. Safari поставляет WebGPU начиная с Safari 26. Firefox включает
его в release на Windows и Apple Silicon macOS, но Linux и часть других
конфигураций ещё имеют ограничения. Поэтому публичное приложение должно делать
feature detection и показывать понятную диагностику, а не предполагать наличие
GPU device.

Если обязательна поддержка широкого набора старых браузеров, WebGL2 backend
следует оценивать отдельным этапом после стабилизации WebGPU contract.

## Delivery plan

### Phase 0: toolchain and core Wasm

Цель — доказать, что core slice компилируется Emscripten без desktop platform
assumptions.

- добавить `TERMIN_PLATFORM_WEB`;
- собрать `termin-base`, `termin-inspect`, `termin-scene` и `termin-mesh`;
- исключить Python, SDL, Vulkan, desktop OpenGL и shared-library requirements;
- экспортировать минимальный C API в JS;
- добавить browser smoke test загрузки Wasm.

Оценка: 1–2 недели после установки и фиксации Emscripten toolchain.

Статус на 2026-08-02: core Wasm и minimal-only bootstrap собираются Emscripten.
Minimal bootstrap dependency closure ограничен `termin-base`, `termin-inspect`
и `termin-scene`; native-тест package loader подтверждает загрузку core fixture
и fail-closed поведение для отсутствующих component/resource domains.

### Phase 1: WebGPU vertical slice

Цель — пройти весь native render path до canvas.

- добавить `BackendType::WebGPU`;
- реализовать минимальные buffers, textures, shaders, pipeline, render pass и
  indexed draw;
- скомпилировать один Slang shader в WGSL offline;
- вывести triangle, затем mesh через tgfx2;
- добавить resize и device-error diagnostics.

Оценка: ещё 2–4 недели.

Статус на 2026-08-02: vertical slice реализован в рабочей ветке карточки
Kanboard #1240. `WebGpuRenderDevice` является обычным `IRenderDevice`, а не
scene-specific renderer; adapter/device создаются отдельной async factory без
Asyncify. Backend принимает prebuilt WGSL и обязательный sidecar v3, строит
group-0 bind layout/resource set, исполняет render pass, обычный и indexed draw,
submit/present и повторную конфигурацию canvas surface. Web smoke использует два
checked-in artifact fixtures и весь draw проходит через public tgfx2 handles и
descriptors.

Текущая capability boundary намеренно узкая и явная: compute pipeline пока не
представлен в `PipelineDesc`, geometry shaders отсутствуют в WebGPU, push
constants, storage textures и synchronous readback отклоняются с логированной
ошибкой. Wasm build и Node smoke прошли. Browser smoke с Chrome for Testing,
WebGPU через Vulkan/SwiftShader и настоящим canvas также прошёл: он отрисовал
оба pipeline, выполнил resize с повторной конфигурацией surface и завершился
маркером `TERMIN_WEB_CORE_SMOKE_PASSED`.

### Phase 2: runtime package scene

Цель — загрузить не hard-coded geometry, а экспортированный package v2.

- скачать/mount package в MEMFS;
- запустить `RuntimePackageLoader`;
- восстановить mesh, texture, material, camera и entry scene;
- исполнять scene update и кадр через browser main loop;
- добавить pointer/keyboard input;
- проверить cleanup и repeated load.

Оценка: ещё 4–8 недель, сильно зависит от shader matrix и bootstrap slicing.

Статус на 2026-08-02: первый core-only host slice реализован в карточке
Kanboard #1241. Web build включает отдельный minimal-only implementation
`RuntimePackageLoader` без desktop resource domains. ESM host скачивает
package-v2 manifest и scene files, монтирует их в generation-specific MEMFS,
запускает entry scene и обслуживает update через `requestAnimationFrame`.
Состояния загрузки и ошибки опубликованы наружу; repeated load и teardown
уничтожают сцены и очищают MEMFS.

Детерминированный Node/Wasm smoke проверяет load/update/reload/cleanup и
отрицательные случаи: неверную версию, отсутствующий manifest, выход пути за
package root, `MeshComponent` и resource типа `Texture`. Строгий browser smoke
через Chrome DevTools проходит тот же host lifecycle на живой странице, затем
рисует WebGPU-кадр и проверяет resize. В ходе проверки устранён ложноположительный
старый `--dump-dom` gate и исправлена browser semantics `present()`: Emdawnwebgpu
не допускает `wgpuSurfacePresent`, canvas публикуется самим браузером в конце
RAF callback.

Это ещё не вся Phase 2: остаются package provider/archive и расширение scene
renderer composition за пределы текущего render-only профиля.

Статус карточки Kanboard #1242 на 2026-08-02: первый настоящий scene/render
vertical slice завершён. Web profile теперь композитит render-only bootstrap,
`RuntimePackageLoader`, `EngineCore`, `RenderingManager`, offscreen display и
`WebGpuRenderDevice`. Backend реализует общий bridge для `tc_texture`,
`tc_mesh` и `tc_shader`, включая per-device cache, prebuilt WGSL sidecar v3,
default sampler, GPU-first render targets и depth-stencil render passes.

Acceptance fixture экспортируется штатным strict resource policy из source
project и содержит scene, camera, OBJ mesh, PNG texture, material и Slang
shader; browser скачивает обычный package v2 graph. Chrome/SwiftShader smoke
проверяет пиксели canvas, затем выполняет reload, teardown, отрицательные
package cases и прежний direct-backend smoke. Кадровый callback принадлежит
Emscripten HTML5 main loop: emdawnwebgpu публикует canvas только на его RAF
boundary; JS host наблюдает состояния и метрики.

Измеренный Release baseline на локальном headless Chrome/SwiftShader:

- `termin_web_core.wasm`: 1 896 467 bytes;
- generated Emscripten module: 122 573 bytes;
- ESM host: 17 884 bytes;
- strict render fixture: 104 208 bytes в 87 файлах;
- package fetch: примерно 90–92 ms;
- WebGPU init: примерно 12 ms;
- native load/composition: примерно 20–23 ms;
- startup до running: примерно 122–126 ms;
- first presented frame: примерно 142–153 ms;
- steady RAF interval на SwiftShader: около 16.7 ms (60 Hz).

Это несжатые локальные размеры и synthetic software-GPU timings, поэтому они
служат regression baseline, а не production budget. Не закрыты: archive/cache
transport, device-loss recovery, partial/scaled blit, полная PBR/shadow shader
matrix и Safari/Firefox CI.

Статус карточки Kanboard #1243 на 2026-08-02: добавлен самостоятельный browser
input/canvas adapter и полноэкранный `viewer.html`. Adapter переводит
pointer/mouse/wheel/keyboard/text events в native display contract, учитывает
CSS coordinates, DPR, pointer capture, focus loss и resize canvas surface.
Render-only bootstrap включает `OrbitCameraController`; fixture теперь является
текстурированным кубом, которым в web viewer можно управлять левой/правой
кнопками мыши и колесом. Mouse buttons контроллера сериализуются в сцене, а его
desktop default остаётся DCC-подобным с orbit на средней кнопке. Web host
владеет viewport input managers симметрично desktop player: display router сам
по себе принимает события, но без manager не передаёт их scene input handlers.
Именно отсутствие этого lifecycle-звена ранее давало наблюдаемое состояние,
когда browser event counter рос, а камера не двигалась. Browser smoke
через Chrome/SwiftShader воспроизводит orbit и wheel как на smoke harness, так
и непосредственно на полноэкранной viewer page,
скрывает HUD перед сравнением, проверяет изменение пикселей самой сцены и
повторную конфигурацию backing surface.
Firefox и аппаратные Chrome/Safari конфигурации этой проверкой пока не покрыты.

### Phase 3: production runtime

- standard render passes и post-processing capability matrix;
- shadows, UI, picking и asynchronous readback;
- compressed textures и asset-size policy;
- package archive/provider и browser cache;
- device-loss recovery;
- browser CI и GPU test matrix;
- startup progress/error UI;
- profiling размера, startup и frame time;
- deployment headers, caching and content security policy.

Оценка: ещё 2–4 месяца.

Ориентир для одного разработчика, знакомого с Termin: 4–6 календарных месяцев
до production-quality Web Runtime и 6–10 engineer-months до широкого desktop
runtime parity. Three.js viewer можно довести до полезного ограниченного
результата за 2–4 недели. Полный browser editor — отдельный проект порядка
9–18 месяцев и не должен смешиваться с runtime roadmap.

## First spike acceptance

Первый spike следует считать успешным, если одновременно выполнены условия:

1. Web build воспроизводим зафиксированной версией Emscripten.
2. Результат состоит из одного main Wasm module, JS loader и web assets.
3. Browser загружает обычный runtime package contract, а не специальный
   three.js JSON scene.
4. Mesh и material проходят существующие scene/render abstractions.
5. WGSL производится offline и валидируется до публикации package.
6. Web-specific ветвления не проникают в scene/component domain.
7. Input и resize проходят через явный browser adapter.
8. Ошибки package, shader, adapter/device и device loss видны в логах и host UI.
9. Chrome и Safari проходят smoke; Firefox запускается там, где WebGPU включён.
10. Зафиксированы compressed Wasm size, package size, startup stages и frame
    timing, чтобы последующие решения принимались по измерениям.

## Explicit non-goals for the first runtime

- запуск desktop Python components в браузере;
- загрузка desktop `.so`/`.dll` plugins;
- source project editing;
- asset import и build tools в браузере;
- MCP server внутри web runtime;
- runtime invocation of `slangc`;
- полный editor UI;
- WebGL2 fallback;
- multithreaded engine before profiling demonstrates a need.

## External references

- [Emscripten: Using WebGPU](https://emscripten.org/docs/porting/multimedia_and_graphics/WebGPU-support.html)
- [Emscripten runtime environment and SDL/browser integration](https://emscripten.org/docs/porting/emscripten-runtime-environment.html)
- [Emscripten main-loop API](https://emscripten.org/docs/api_reference/emscripten.h.html)
- [Emscripten file-system overview](https://emscripten.org/docs/porting/files/file_systems_overview.html)
- [Emscripten pthreads and deployment headers](https://emscripten.org/docs/porting/pthreads.html)
- [WebGPU specification](https://www.w3.org/TR/webgpu/)
- [WGSL specification](https://www.w3.org/TR/WGSL/)
- [Slang WebGPU target](https://docs.shader-slang.org/en/stable/external/slang/docs/user-guide/09-targets.html)
- [MDN WebGPU compatibility overview](https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API)
- [WebKit: WebGPU in Safari 26](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/)
- [Mozilla WebGPU platform status](https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Experimental_features)

## Repository references

- `termin-runtime/AGENTS.md`
- `termin-runtime/include/termin/runtime/runtime_package.hpp`
- `termin-runtime/src/runtime_package.cpp`
- `termin-runtime/CMakeLists.txt`
- `termin-graphics/include/tgfx2/i_render_device.hpp`
- `termin-graphics/include/tgfx2/i_command_list.hpp`
- `termin-graphics/src/tgfx2/device_factory.cpp`
- `termin-graphics/tools/termin_shaderc.cpp`
- `termin-bootstrap/CMakeLists.txt`
- `termin-bootstrap/src/bootstrap_core.cpp`
- `termin-player/CMakeLists.txt`
- `examples/webscene/main.py`
- `examples/webscene/static/index.html`

## Board status

Направление принято и ведётся отдельным swimlane Web Runtime. Phase 0 bootstrap,
Phase 1 WebGPU vertical slice, core-only package host и первый packaged
scene/render slice завершены карточками #1238, #1240, #1241 и #1242. Browser
input/resize vertical slice #1243 реализован и передан на ручную проверку;
production-хвосты ведутся отдельно и не смешиваются с полным browser editor.
