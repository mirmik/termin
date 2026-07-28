# Готовность рендерера Termin к deferred и альтернативным pipelines

Дата: 2026-07-28.

Статус: статический read-only анализ. Код рендерера во время исследования не
изменялся.

Связанные decision-карточки:

- #991 `[render/material] Определить полноценный SurfaceData contract`;
- #992 `[graphics/render] Определить backend-neutral MRT contract`.

## Краткий вывод

Архитектура кадра уже неплохо подготовлена к нескольким методам рендеринга:
framegraph, независимые passes, именованные ресурсы, render phases и
pass-specific shader contracts позволяют собирать разные pipeline templates без
ветвления одного монолитного renderer.

Однако полноценный deferred shading пока нельзя добавить только новым
`GBufferPass` и fullscreen lighting pass. Два обязательных контракта ещё не
сформированы:

1. `RenderContext2`, pipeline cache и render-target resource model поднимают
   наверх только один color attachment, хотя low-level backend descriptors уже
   допускают несколько attachments.
2. Material fragment shader выдаёт окончательно освещённый цвет. У материала
   нет переиспользуемого surface-evaluation контракта, который одинаково
   применим в forward lighting, G-buffer encoding, depth/shadow alpha test и
   material debug views.

Рекомендуемая цель — hybrid pipeline: deferred для совместимой opaque geometry,
forward для transparency и материалов с нестандартной shading model.

## Текущий pipeline

Default pipeline уже является цепочкой независимых стадий:

```text
Shadow
  -> Skybox
  -> Forward opaque
  -> Forward transparent
  -> World2D
  -> Resolve
  -> Bloom
  -> UI
  -> Present
```

`tc_pipeline_template` хранит backend-independent pass plan, resource specs,
dependencies, attachment views и FBO compositions. Live passes, framegraph,
textures и device-local caches принадлежат отдельному `RenderPipeline`
execution instance.

Это здоровая граница для альтернативных методов рендеринга:

```text
authored pass list / node graph
  -> canonical pipeline template
  -> device-local execution instance
```

`CxxFramePass` независимо объявляет reads, writes, resource specs и
in-place aliases. `ExecuteContext` передаёт pass именованные color/depth texture
maps, scene/view state, lights и общий `RenderSceneItemSnapshot`.

### Сильные стороны

- pipeline topology не зашита в `RenderEngine`;
- pass type registry допускает project-owned passes;
- resource dependencies формируют framegraph schedule;
- opaque, transparent, normal, depth, id, shadow и project phases используют
  один 64-bit phase registry;
- geometry passes используют общий frame/view scene-item snapshot;
- material shader assembly уже различает material, vertex transform и
  pass-owned contracts;
- framegraph debugger умеет показывать именованные промежуточные ресурсы.

Поэтому depth prepass, SSAO, outline, debug visualization и большинство
fullscreen postprocess effects укладываются в текущую модель естественно.

## Разрыв 1: MRT поддержан внизу, но не в RenderContext2

Низкоуровневый `RenderPassDesc` содержит список `colors`, а `PipelineDesc`
содержит список `color_formats`. Vulkan и D3D11 command lists уже перебирают
несколько color attachments.

Высокоуровневый путь остаётся single-target:

- `RenderContext2::begin_pass()` принимает один `TextureHandle color`;
- mutable context хранит один `color_format_`;
- `PipelineCacheKeyState` хранит один `color_format`;
- `PipelineCache` публикует `desc.color_formats = {key.color_format}`;
- `FBOPool` и framegraph FBO composition моделируют один color и один depth;
- `ExecuteContext` передаёт плоскую карту текстур, но не typed attachment set.

OpenGL backend создаёт FBO и присоединяет все элементы `pass.colors`, однако
общий MRT draw-buffer selection через `glDrawBuffers` в этом пути отсутствует.
Один факт создания нескольких attachments ещё не образует работающий portable
MRT contract.

### Требуемая foundation

Нужен один backend-neutral контракт render pass attachments:

```cpp
struct RenderPassAttachmentSet {
    span<const ColorAttachmentDesc> colors;
    optional<DepthAttachmentDesc> depth;
};
```

Точная форма API является отдельным decision, но контракт обязан обеспечить:

- упорядоченное соответствие `SV_TargetN` и color attachment `N`;
- массив color formats в pipeline cache identity;
- явные load/store/clear operations для каждого attachment;
- проверку одинаковых width, height и sample count;
- проверку `BackendCapabilities::max_color_attachments`;
- OpenGL `glDrawBuffers` и per-attachment clear;
- одинаковое поведение Vulkan, OpenGL и D3D11;
- framegraph pass с несколькими независимыми именованными output textures;
- debugger capture каждого G-buffer plane как обычного ресурса.

Не обязательно превращать весь framegraph resource в монолитный persistent
FBO. Предпочтительнее сохранить G-buffer planes отдельными ресурсами, а
attachment set компилировать для конкретного pass. Так lifetime/alias analysis
останется на уровне отдельных текстур.

## Разрыв 2: отсутствует полноценный SurfaceData contract

Сейчас PBR material fragment shader одновременно:

- семплирует material textures;
- вычисляет normal mapping;
- строит albedo, metallic, roughness, occlusion, emission и alpha;
- обходит lights;
- применяет shadows и BRDF;
- возвращает окончательный `SV_Target0`.

Такая форма удобна для forward, но не даёт G-buffer pass переиспользовать
material-specific surface evaluation. Pass-level `fragment_source_override`
сам по себе проблему не решает: generic override не знает, как конкретный
материал вычисляет свои параметры.

Целевая декомпозиция:

```text
material resources + fragment inputs
  -> evaluate_surface()
  -> SurfaceData
       ├─> forward lighting integrator
       ├─> G-buffer encoder
       ├─> depth/shadow alpha policy
       └─> debug material views
```

Минимальный canonical payload может начинаться с:

```cpp
struct SurfaceData {
    float3 base_color;
    float3 normal_world;
    float metallic;
    float roughness;
    float occlusion;
    float3 emission;
    float alpha;
};
```

Но финальный contract нельзя фиксировать только по текущему Cook-Torrance
shader. Нужно заранее решить:

- как кодируется shading model;
- какие поля обязательны, а какие расширяемы;
- где живут alpha test и discard;
- как unlit, subsurface, clearcoat и project-owned materials расширяют модель;
- как один material source компилируется в forward и G-buffer variants;
- как surface contract отражается в shader artifact metadata и variant
  fingerprint;
- как offline shader usage collection узнаёт требуемые variants;
- что делают legacy/custom fragments, которые возвращают только final color.

Стабильной единицей контракта должен быть semantic surface output, а не
конкретная раскладка G-buffer. G-buffer layout принадлежит pipeline/pass и может
меняться независимо от material authoring model.

## Рекомендуемый deferred pipeline

Первый production-вариант:

```text
ShadowPass
  -> optional DepthPrepass
  -> GBufferPass (opaque, deferred-compatible)
  -> DeferredLightingPass
  -> Skybox/composite
  -> ColorPass (transparent and forward-only materials)
  -> World2D/editor overlays
  -> Bloom/Tonemap/UI/Present
```

World position лучше восстанавливать из depth, а не хранить отдельным
G-buffer plane.

Пример стартовой раскладки:

- base color + AO;
- encoded normal + roughness;
- metallic + emission/shading-model data;
- отдельный depth attachment.

Конкретную упаковку следует выбирать после расширения pixel-format и color-space
contract. Сейчас `PixelFormat` не различает linear и sRGB formats и не содержит
нескольких распространённых packed render-target formats. Фиксировать layout
поверх этого ограничения преждевременно.

### MSAA

Default/editor pipelines широко используют 4x MSAA. Multisampled G-buffer
существенно увеличивает память и усложняет resolve каждого plane.

Для первой версии разумная policy:

- deferred G-buffer — single-sample;
- transparency — forward поверх deferred composite;
- AA — FXAA/TAA либо отдельный forward-MSAA pipeline;
- deferred MSAA — отдельная последующая задача после измерений.

## Другие методы рендеринга

### Хорошо ложатся уже сейчас

- depth prepass;
- normal/depth/id debug views;
- SSAO на fragment/fullscreen passes;
- outlines и selection effects;
- raster postprocessing;
- render-to-texture и дополнительные camera pipelines;
- raster light volumes после завершения MRT.

### Требуют SurfaceData и MRT

- классический deferred shading;
- material/debug views без дублирования material evaluation;
- hybrid deferred/forward;
- decal pipelines, если decals должны изменять material attributes до lighting.

### Требуют отдельной compute/resource foundation

- Forward+;
- clustered lighting;
- GPU-driven culling;
- compute SSAO/SSR;
- compute bloom;
- path tracing и другие storage-image pipelines.

В tgfx2 уже существуют `ShaderStage::Compute`, `QueueType::Compute`,
`ICommandList::dispatch()` и capability flags. Но полноценного
`ComputePipelineDesc`, high-level bind/dispatch context и generic framegraph
buffer/storage-image resource contract нет.

Состояние неоднородно:

- Vulkan заявляет compute и storage textures;
- OpenGL 3.3 path их не поддерживает;
- D3D11 умеет создать native compute shader и содержит `Dispatch`, но публичные
  capabilities считают compute неподдержанным;
- graphics `PipelineDesc` не имеет compute shader identity.

Это полезная заготовка, но не production compute abstraction.

## Производительность и связанные хвосты

Deferred увеличит число pass boundaries и промежуточных ресурсов, поэтому
существующие framegraph costs станут заметнее.

На доске уже зафиксированы:

- #554 — компилировать execution descriptor только при изменении pipeline;
- #557 — исполнять только достижимые output roots;
- #560 — убрать полный backend reset перед каждым framegraph pass.

Scene-item snapshot уже общий для logical view, но shader/task planning остаётся
pass-local. Для первой реализации это допустимо. После появления G-buffer и
нескольких geometry variants стоит рассмотреть compiled scene submission plan,
из которого passes получают собственные shader/resource variants без повторной
маршрутизации каждого item.

## Последовательность работ

1. Принять backend-neutral MRT decision.
2. Реализовать и проверить MRT foundation на Vulkan, OpenGL и D3D11.
3. Принять semantic `SurfaceData`/material evaluation decision.
4. Мигрировать один canonical PBR material на forward + G-buffer variants.
5. Добавить `GBufferPass` и простой fullscreen `DeferredLightingPass`.
6. Оставить transparency и несовместимые материалы в forward path.
7. Зафиксировать pixel-format, color-space и initial G-buffer layout.
8. Выбрать AA policy на основе профилирования.
9. Отдельно проектировать compute/storage framegraph foundation для
   Forward+/clustered.

## Итоговая оценка

Готовность по слоям:

| Слой | Оценка |
|---|---|
| Pipeline templates и framegraph topology | высокая |
| Независимые render passes | высокая |
| Именованные texture resources и debugger | высокая |
| Geometry phase routing | высокая |
| Pass-specific shader assembly | средняя/высокая |
| MRT high-level contract | низкая |
| Semantic material surface output | низкая |
| Compute/storage framegraph resources | низкая |

Движок удобен для внедрения новых raster pipelines на уровне композиции кадра.
Deferred потребует двух крупных, но хорошо локализуемых foundation-изменений:
MRT в graphics/render-target path и `SurfaceData` в material shader contract.

Если сначала закрыть эти контракты, deferred станет естественным новым pipeline
поверх существующего framegraph. Если сразу написать специальный
`GBufferPass`, появятся параллельные material shaders, backend-specific MRT
обходы и ещё один special-case resource path.
