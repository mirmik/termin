# D3D11/Vulkan Abstraction Boundary Notes

Дата: 2026-06-21

## Вопрос

Как должна выглядеть архитектура render backend abstraction, если один и тот
же frontend должен работать поверх Vulkan, OpenGL и D3D11, но эти API имеют
разную модель pipeline layout, resource binding, shader ABI и command recording?

Короткий ответ: нам нужен не "общий backend API, похожий на один из graphics
API", а несколько явно разделённых уровней:

1. frontend semantic render contract;
2. shader interface contract;
3. backend placement / shader ABI;
4. backend command execution.

Если эти уровни смешиваются, любой backend с другой моделью начинает выглядеть
как "порт Vulkan на D3D11" или "порт OpenGL на Vulkan".

## Архитектурный Принцип

Высокоуровневый render code должен описывать **что** он хочет связать с
шейдером, а backend-specific слой должен решать **как** это представляется в
конкретном graphics API.

Например, pass/material code не должен мыслить такими понятиями:

- Vulkan descriptor set/binding;
- D3D11 `b#`, `t#`, `s#`, `u#`;
- OpenGL texture unit / UBO binding point;
- конкретный slot для эмуляции push constants.

Он должен мыслить ресурсами уровня движка:

- frame constants;
- view/camera constants;
- draw/object constants;
- material constants;
- material textures;
- samplers;
- lighting data;
- shadow maps;
- pass-local constants;
- storage/read-write resources, если backend capability это разрешает.

Эта семантическая модель должна быть стабильной для всех backend-ов.

## Предлагаемые Уровни

### 1. Render Frontend Contract

Это уровень frame graph, passes, materials, render components и draw submission.

Его обязанности:

- объявить semantic resource requirements;
- предоставить данные для этих ресурсов;
- выбрать shader/material variant;
- описать render state, vertex layout, target formats;
- не знать backend-specific placement.

Пример frontend-запроса:

```text
Material phase needs:
- PerFrame constants
- Draw constants
- Material constants
- textures: albedo, normal, metallic_roughness
- sampler: material_sampler
```

Здесь ещё не должно быть `set=0,binding=3` или `register(t4)`.

### 2. Shader Interface Contract

Это ABI между material/pass authoring и runtime. Он отвечает на вопрос:
"какие semantic resources этот shader ожидает?"

Его обязанности:

- хранить canonical resource names или ids;
- хранить kind: constant buffer, texture, sampler, storage buffer, storage image;
- хранить scope: frame, pass, draw, material, global;
- хранить stage visibility;
- хранить expected layout/size для constant buffers;
- быть независимым от Vulkan/D3D11/OpenGL placement.

Важное требование: shader interface не должен угадываться по magic names там,
где ресурсная роль может быть объявлена явно. Имена вроде `per_frame`,
`draw_data`, `material`, `shadow_maps` допустимы как human-readable names, но не
как единственный источник policy.

### 3. Backend Shader ABI / Placement

Это слой, которого, вероятно, не хватает как отдельной явной сущности.

Он берёт shader interface и backend capabilities, после чего строит
backend-specific placement:

```text
Semantic resource       Vulkan              D3D11          OpenGL
---------------------------------------------------------------------------
PerFrame constants      set/binding         b#             UBO binding
Draw constants          set/binding         b#             UBO binding
Material texture        set/binding         t#             texture unit
Material sampler        set/binding         s#             sampler/unit
Pass-local constants    push range / UBO    b# emulation   UBO emulation
Storage image           descriptor          u#             image binding
```

Этот слой должен быть явным артефактом, а не набором условий внутри backend
command list.

Возможные формы:

- расширенный `tc_shader_resource_binding`, если мы готовы сделать его carrier
  не только semantic info, но и backend placement;
- отдельный `ShaderBindingPlan` / `BackendBindingPlan`, что чище разделяет
  semantic interface и concrete placement;
- sidecar-представление per backend, которое runtime превращает в binding plan.

С архитектурной точки зрения отдельный `BindingPlan` выглядит чище: semantic
shader interface остаётся неизменным, а backend ABI становится вычисляемой или
загружаемой производной.

### 4. Backend Command Execution

Это `VulkanCommandList`, `D3D11CommandList`, `OpenGLCommandList`.

Его обязанности:

- получить уже resolved binding plan;
- выполнить native API calls;
- валидировать backend-specific limits;
- логировать unsupported capabilities;
- не выводить semantic meaning из resource names;
- не назначать произвольные slots за frontend.

Хорошее правило: если `D3D11CommandList` должен знать, что ресурс с именем
`material` надо положить в конкретный `b#`, значит ответственность лежит не на
том уровне.

## Push Constants Как Пример

Push constants не являются backend-neutral primitive.

Для frontend-а это лучше формулировать как:

```text
pass-local small constants, max N bytes, updated frequently
```

А placement layer решает:

- Vulkan: native push constant range;
- D3D11: reserved constant buffer slot;
- OpenGL: reserved UBO binding;
- backend without support: capability error or fallback policy.

Такой подход убирает ложное ожидание, что один global binding slot подходит всем
backend-ам.

## Capabilities

Backend abstraction должна быть capability-driven, но capability не должна
протекать наверх в виде постоянных `if backend == d3d11`.

Нужны явные capability records:

- max constant buffer slots per stage;
- max SRV/sampler/UAV slots;
- supported shader stages;
- supports native push constants;
- supports dynamic constant-buffer offsets;
- supports storage buffers/images;
- supports MSAA resolve/readback formats;
- coordinate and viewport conventions, если они нормализуются не в shader.

Frontend может использовать capabilities для выбора features/variants, но
placement и command execution должны оставаться обязанностью backend layer.

## Shader Compilation Pipeline

Желаемый pipeline:

```text
shader source / material declaration
        |
        v
semantic shader interface
        |
        v
backend placement allocation
        |
        v
backend artifact + backend binding plan sidecar
        |
        v
runtime loads shader + binding plan
        |
        v
RenderContext binds semantic resources through plan
        |
        v
backend command list executes native binding calls
```

Ключевой момент: runtime binding should be semantic at the call site, but
backend-specific at the execution site.

## Где Должны Жить Решения

| Решение | Правильный владелец |
| --- | --- |
| Какие ресурсы нужны pass/material | pass/material/shader interface |
| Какой ресурс является frame/draw/material | shader interface / explicit metadata |
| Какой register class у D3D11 resource | backend placement |
| Какой descriptor set у Vulkan resource | backend placement |
| Какой UBO binding у OpenGL resource | backend placement |
| Как выполнить `PSSetShaderResources` | D3D11 command list |
| Как выполнить `vkCmdBindDescriptorSets` | Vulkan command list |
| Как выбрать fallback при unsupported feature | capability/policy layer |

## Антипаттерны

1. **Generic binding number pretending to be universal.**
   Один `binding=14` не может быть одновременно Vulkan binding, OpenGL UBO
   binding и D3D11 `b#`.

2. **Backend command list infers resource meaning from names.**
   Command list должен исполнять plan, а не понимать engine semantics.

3. **Frontend manually assigns backend slots.**
   Pass code не должен знать D3D11 register allocation.

4. **Shader reflection directly drives runtime binding without policy.**
   Reflection говорит, что shader содержит, но не всегда говорит, какую engine
   semantic роль должен иметь ресурс.

5. **Fallbacks silently rewrite ABI.**
   Если backend не может поддержать feature или layout, лучше получить явную
   ошибку/лог, чем незаметно привязать ресурс в "примерно подходящий" slot.

## Вариант Целевой Модели

Можно представить целевой контракт так:

```cpp
struct ShaderResourceSemantic {
    ResourceId id;
    ResourceKind kind;
    ResourceScope scope;
    StageMask stages;
    uint32_t size;
};

struct D3D11Placement {
    D3D11RegisterClass reg; // b/t/s/u
    uint32_t index;
    StageMask stages;
};

struct VulkanPlacement {
    uint32_t set;
    uint32_t binding;
    StageMask stages;
};

struct OpenGLPlacement {
    uint32_t binding;
    StageMask stages;
};

struct BackendBindingPlan {
    ShaderResourceSemantic semantic;
    BackendPlacement placement;
};
```

Это не предложение конкретного ABI в текущем виде, а форма мысли: semantic part
и backend placement должны быть различимы в типах.

## Открытый Архитектурный Выбор

Главный выбор:

1. Расширять `tc_shader_resource_binding` до combined semantic + placement
   структуры.
2. Ввести отдельный `BackendBindingPlan`, который строится из shader interface и
   backend placement metadata.

Первый путь проще миграционно, потому что меньше новых объектов и меньше
переписывания runtime.

Второй путь архитектурно чище: он не заставляет semantic shader interface
носить в себе детали всех backend-ов сразу. Для долгой жизни нескольких
backend-ов второй вариант выглядит устойчивее.

## Related Docs

- `docs/plans/2026-06-15-d3d11-backend-readiness-plan.md`
- `docs/plans/2026-06-20-d3d11-runtime-placement-goal-plan.md`
- `docs/analysis/2026-06-12-hardcoded-bindings-audit.md`
- `docs/analysis/2026-06-12-slang-shader-bind-by-name-review.md`
- `docs/gpu-pipeline-layout.md`
