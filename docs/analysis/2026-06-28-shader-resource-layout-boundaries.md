# Shader resource layout boundaries после текущего рефакторинга

Дата: 2026-06-28

Статус: архитектурная инспекция `termin-graphics`, `termin-render` и
соседних render components. Связано с Kanboard #85 и #137.

## Краткий вывод

Текущая конструкция не выглядит избыточной в своей основе. Разделение на
`tc_shader_contract`, reflected/generated resource layout,
`BackendBindingPlan` и runtime-bound values оправдано, потому что эти слои
отвечают на разные вопросы:

```text
shader contract       -> что шейдер семантически требует
resource layout       -> что реально отражено/скомпилировано и с какой metadata
backend binding plan  -> как это представить конкретному backend-у
bound resource values -> какие buffers/textures/samplers привязаны сейчас
```

Если эти слои слить, backend placement снова начнет протекать в pass/material
код, или runtime будет вынужден угадывать слоты по именам. Это ровно тот класс
проблем, от которого миграция сейчас уходит.

При этом текущая реализация все еще содержит миграционную избыточность:
contract и layout местами дублируют `name/kind/scope/stage/size`,
material/vertex-transform assembly местами требует resolved placement слишком
рано, а compiler/runtime пока разделяют общий transitional allocator numeric
ranges. Это нормально как промежуточное состояние, но не должно стать целевой
архитектурой.

## Что уже получается хорошо

Главная архитектурная линия правильная:

- shader source и pass/render code работают с логическими ресурсами и scopes;
- `termin_shaderc` отражает declarations, пишет sidecar metadata и патчит
  backend artifacts только там, где это пока требуется target compiler-ом;
- `RenderContext2` резолвит symbolic bind-ы через активный shader layout;
- backend получает resolved `BackendPlacement`, а не угадывает смысл из
  resource name или historical binding slot.

Практически важные признаки здоровой системы уже есть:

- migrated render paths вызывают `use_shader_resource_layout()` и
  `bind_uniform_data()` / `bind_texture()` по имени;
- missing resource layout чаще логируется и пропускается, а не падает в
  fixed-slot fallback;
- `tc_shader_contract` уже стал requirement-only моделью и не хранит
  draw/pass intent;
- `engine-shader-catalog.json` сужен до source metadata и больше не должен
  расти как runtime source of truth для contracts/layouts.

Это близко к модели, которой пользуются современные движки и API:
shader/pass interface описывается semantic parameter set-ом, а конкретные
descriptor/register/binding layouts создаются reflection/generation/backend
слоем. В терминах Vulkan это похоже на pipeline layout/descriptor set layout,
в D3D - на register/root-signature lowering, в движковых системах уровня
Unreal/Unity - на shader parameter metadata и material/pass resource binding,
а не на одну глобальную таблицу binding numbers.

## Целевые границы

### Shader source

Владеет:

- resource names;
- resource kinds;
- logical scopes через `[[TerminScope("...")]]`;
- entry points;
- stage IO semantics;
- shader-owned local algorithm details.

Не владеет по умолчанию:

- Vulkan `set/binding`;
- OpenGL binding points / texture units;
- D3D `b#/t#/s#/u#` registers;
- pass/draw ownership policy.

Исключение возможно только как явно opt-in advanced path. Такой shader должен
проходить validation против backend policy и reserved ranges.

### `tc_shader_contract`

Целевая форма: requirement-only ABI.

Владеет:

- required vertex inputs;
- required shader-visible resources: `name`, `kind`, `scope`, `stage_mask`,
  buffer size, fields, element stride;
- source kind/debug metadata для diagnostics.

Не владеет:

- `set/binding`;
- D3D register placement;
- OpenGL binding points;
- render-pass/draw intent;
- backend-specific lowering.

Если contract начнет хранить placement, он превратится во второй layout и
сломает смысл разделения.

### Resource layout

Целевая форма: reflected/generated facts about a compiled shader artifact.

Владеет:

- фактическими reflected resources;
- field layout для buffers;
- artifact schema/version;
- target/language/stage metadata;
- временно: backend placement, пока artifacts требуют заранее пропатченных
  numeric decorations/registers.

Не владеет:

- semantic ownership inference;
- fallback policy;
- runtime resource values.

Важно: `unscoped` должен оставаться compiler/import state, а не runtime
semantic scope. Production migrated artifacts должны либо иметь explicit
scope, либо получать scope от caller-а через явную default policy.

### Backend placement policy

Целевая форма: backend-owned placement allocator/planner.

Владеет:

- Vulkan descriptor set/binding allocation;
- D3D register class/index allocation;
- OpenGL UBO/SSBO/image binding point and texture/sampler unit allocation;
- backend-specific conflict validation;
- backend capabilities and unsupported resource classes.

Не владеет:

- semantic resource ownership;
- canonical engine resource names as policy input beyond declared
  requirement/scope/kind;
- runtime values.

Текущее `transitional_backend_binding_range()` полезно как shared migration
glue, но в финальной форме оно не должно жить как публичная universal policy.
Его место - за backend-specific policy boundary, с одинаковыми входными
семантическими фактами и разными backend outputs.

### Runtime binding

Целевая форма: strict bind-by-name against active shader layout/plan.

Владеет:

- symbolic pending binds;
- grouping by update scope;
- dirty tracking;
- value validation against active layout;
- logging when shader/layout/plan does not accept a bind.

Не владеет:

- missing-resource fallback;
- historical numeric slots;
- semantic name alias inference;
- backend placement generation.

Numeric APIs могут остаться только как legacy/low-level side channel для
tests, old GLSL compatibility и backend smoke code. Production migrated paths
не должны добавлять новые numeric calls.

### Render/pass/material layer

Владеет:

- какие ресурсы производятся pass-ом;
- какие logical resources нужны material/pass/draw;
- typed helpers for engine resources;
- CPU-side packing of known structs;
- validation that pass/material contract is satisfied.

Не владеет:

- backend placement;
- target-specific register/binding syntax;
- compiler artifact patching.

Имена вроде `per_frame`, `lighting`, `shadow_block`, `shadow_maps`,
`material`, `draw_data`, `bone_block` являются shader interface names, а не
backend policy. Их лучше держать в typed helpers / named constants / contract
builders, а не размазывать строками по pass code.

## Остаточные риски

### Transitional allocator стал новой общей магией

`transitional_backend_binding_range()` ушел от per-resource special cases и
использует `scope + kind + stable name hash`. Это лучше старой таблицы
`shadow_maps -> binding 8`, но все еще глобальная numeric policy.

Риск: если этот allocator останется публичным долгосрочно, backend autonomy
будет только частичной. Vulkan, D3D11 и OpenGL имеют разные binding spaces и
разные constraints, а общий allocator будет тянуть их к усредненной модели.

### Material/vertex-transform assembly требует placement слишком рано

`MaterialPipelineResourceDecl` сейчас объединяет semantic requirement и
resolved placement. Из-за этого vertex transform contracts все еще несут
binding numbers для `per_frame`, draw data и `bone_block`.

Целевое состояние: material/vertex-transform/pass contracts должны отдавать
requirements, а placement должен появляться позже, после сборки shader layout
и выбора backend policy.

### Legacy GLSL inference еще существует

Raw GLSL path в shader registry все еще угадывает engine resources по токенам
и назначает fixed bindings. Это допустимо только как явно legacy-only bridge.
Его нельзя использовать как пример для новых migrated Slang paths.

### Semantic aliases надо ограничить

Helper-ы, которые ищут несколько исторических имен (`lighting`,
`lighting_ubo`, `LightingBlock`; `shadow_maps`, `u_shadow_map`), полезны для
миграции. Но если оставить их бессрочно, canonical shader interface станет
нечетким.

Целевое состояние: один canonical resource name на engine contract, старые
имена - либо documented legacy aliases с removal plan, либо explicit adapter
на границе old assets.

## Рекомендации

1. Сделать `tc_shader_contract` окончательно placement-free. Любой новый код,
   который хочет записать `set/binding` в contract, считать архитектурной
   ошибкой.

2. Разделить `MaterialPipelineResourceDecl` на requirement и optional legacy
   placement. Для новых assembled shaders placement должен назначаться
   backend policy, а не vertex-transform contract builder-ом.

3. Перенести transitional range allocator из публичного
   `tgfx2/backend_binding_plan.hpp` за explicit policy boundary. На первом
   шаге это может быть общий `BackendPlacementAllocator` с backend-specific
   implementations, но public API должен видеть результат, а не ranges.

4. Добавить migrated-path gate: artifact-required Slang shaders с `unscoped`
   resources должны fail/log-error до draw path, кроме явно помеченных legacy
   или debug-local exceptions.

5. Свести engine resource names в typed helpers/central constants:
   frame camera, lighting, shadows, material UBO/textures, draw transforms,
   bone block, foliage instance stream. Pass code должен использовать helper
   там, где ресурс является частью engine ABI.

6. Зафиксировать policy для aliases: какие имена canonical, какие legacy, где
   они разрешены и чем проверяется их удаление.

7. Держать numeric binding APIs рядом с explicit legacy markers. Тестами
   проверять, что representative production render paths не используют
   `bind_uniform_buffer(binding)` / `bind_sampled_texture(binding)`.

8. Дальше двигаться к backend-owned artifacts: compiler может продолжать
   патчить SPIR-V/HLSL/GLSL, но placement input должен приходить из той же
   backend policy, которую runtime использует для `BackendBindingPlan`.

## Не-рекомендации

Не стоит упрощать систему путем удаления `tc_shader_contract` или
`BackendBindingPlan`. Это сэкономит один слой только на бумаге, но вернет
скрытые зависимости:

- pass code снова начнет знать slots/registers;
- backend code снова начнет распознавать engine resource names;
- diagnostics потеряют различие между "shader requires" и "artifact layout
  contains";
- D3D11/OpenGL/Vulkan снова придется подгонять под одну неявную Vulkan-like
  модель.

Более правильное упрощение - не удалять слои, а очистить их границы:
contract без placement, layout без policy, backend plan без semantic guessing,
runtime без fallback slots.

## Целевая схема

```text
Slang / generated shader source
  declares names, kinds, scopes, stage IO

tc_shader_contract
  stores semantic requirements only

termin_shaderc + reflection
  produces artifact facts and resource layout sidecar

backend placement policy
  maps resource facts to backend placement

BackendBindingPlan
  carries concrete Vulkan/D3D11/OpenGL placement

RenderContext2
  binds values by logical name and scope

Backend command list
  applies native descriptors/registers/binding points
```

Это не минималистичная конструкция, но для multi-backend renderer она
соответствует реальным границам ответственности. Избыточной она станет только
если transitional placement duplication останется навсегда.

