# Политика reflected placement в shaderc

**Дата:** 2026-06-15  
**Статус:** анализ для Kanboard #21

## Контекст

В задаче #2 из мигрированных material/pass путей убраны runtime fallback-и на
фиксированные binding-слоты. Runtime теперь биндует ресурсы по логическим
именам и использует метаданные `tc_shader_resource_binding`, загруженные из
sidecar-файлов shader artifacts.

Остается важный выбор на уровне компилятора `termin_shaderc`: должен ли
sidecar сохранять backend placement ровно в том виде, в каком его сообщает
Slang, или Termin должен продолжать нормализовать ресурсы в собственный
scope-first binding ABI?

Это не старая проблема runtime fallback. Во всех вариантах ниже runtime
должен продолжать bind-by-name / bind-by-scope и должен падать или громко
логировать ошибку, если обязательных метаданных нет. Выбор здесь о другом:
кто владеет backend placement в сгенерированных artifacts: `set/binding` для
Vulkan/OpenGL-подобной модели или D3D `register`.

## Текущая Реализация

Сейчас `termin_shaderc` использует scope-first normalization:

```text
Slang source
  -> slangc bytecode + reflection
  -> infer resource name/kind/scope
  -> normalize scope/name to Termin backend slots
  -> patch/write artifact and .layout.json sidecar
  -> runtime binds by resource name using sidecar placement
```

Фактически текущие нормализованные слоты такие:

| Resource | Scope | Placement |
|---|---|---|
| `lighting` | `pass` | binding 0 |
| `material` | `material` | binding 1 |
| `per_frame`, `u_per_frame` | `frame` | binding 2 |
| `shadow_block` | `pass` | binding 3 |
| material textures | `material` | binding 4+, skipping 8 |
| `shadow_maps`, `u_shadow_map(s)` | `pass` | binding 8 |
| `bone_block`, `BoneBlock` | `draw` | binding 16 |
| draw constant buffers | `draw` | binding 24 |
| draw storage buffers | `draw` | binding 25 |
| transient textures/storage/samplers | `transient` | binding 32+ |

Все ресурсы сейчас сведены в set 0. Vulkan использует per-pipeline descriptor
layout. OpenGL использует те же метаданные как binding points. D3D11 пока не
реализован, поэтому эта политика еще не проверена на HLSL register classes.

## Вариант A: Оставить Scope-First Canonical Placement

Termin владеет backend placement. Авторы шейдеров объявляют логические
ресурсы и scopes, но не объявляют backend bindings/registers. `termin_shaderc`
назначает placement из engine ABI.

### Как Работает Runtime

```text
Shader source:
  [[TerminScope("material")]]
  ConstantBuffer<MaterialParams> material;

termin_shaderc:
  material + scope=material -> binding/register slot from Termin ABI

Runtime:
  ctx.bind_uniform_data("material", bytes)
  active resource layout resolves "material" -> backend placement

Backend:
  Vulkan: descriptor set/binding from sidecar
  OpenGL: binding point from sidecar
  D3D11: cbuffer/register slot from sidecar-derived mapping
```

### Плюсы

- Стабильный engine ABI. Движковые passes могут полагаться на канонические
  scopes и slots для всех сгенерированных шейдеров.
- Авторам шейдеров не нужно знать backend-specific binding syntax.
- Хорошо подходит для generated variants: skinned, foliage, depth, shadow, id
  и normal variants могут seed/merge известные ресурсы, не протаскивая backend
  numbers в высокоуровневую material system.
- Проще совместимость Vulkan/OpenGL/D3D11, потому что одна Termin policy может
  выдавать placement для разных backend-ов.
- D3D11 MVP можно начать с детерминированной register allocation:
  `frame/pass/material/draw/transient` можно отобразить на явные диапазоны
  `b#`, `t#`, `s#` и `u#`.
- Кэши предсказуемы: bump `layout_schema` инвалидирует artifacts при смене
  ABI.

### Минусы И Риски

- `termin_shaderc` остается не просто compiler wrapper, а еще ABI allocator и
  patcher.
- Placement не является по-настоящему shader-owned. Slang reflection является
  входом, но не финальным источником истины.
- Name/scope inference может превратиться в магическую таблицу, если ресурсы
  не имеют явного `[[TerminScope]]`.
- Имена ресурсов становятся фактическим ABI. Переименование `per_frame` или
  `shadow_block` меняет placement, если explicit scope/name policy это не
  покрывает.
- Multi-set Vulkan или D3D register-space support придется проектировать
  внутри Termin allocator, а не делегировать Slang.
- Тесты должны четко различать "compiler-side canonical placement" и
  запрещенный "runtime fixed binding fallback".

### Что Нужно Валидировать

- Отклонять `unknown` scope для artifact-required migrated Slang resources,
  кроме явно legacy/debug ресурсов.
- Отклонять конфликты duplicate `(backend set/register class, binding)` после
  normalization.
- Версионировать layout ABI явной schema version.
- Проверять тестами, что runtime никогда не биндует отсутствующий ресурс через
  угаданный slot.

## Вариант B: Сохранять Shader-Owned Placement

Slang или authored shader interface владеет placement. `termin_shaderc`
записывает placement из reflection почти напрямую, с минимальной validation и
без Termin slot rewrite.

### Как Работает Runtime

```text
Shader source:
  resource uses Slang/backend placement attributes, or Slang auto-allocation

termin_shaderc:
  compile + reflect
  write reflected placement directly into .layout.json

Runtime:
  ctx.bind_texture("u_input_tex", tex)
  active resource layout resolves "u_input_tex" -> reflected placement

Backend:
  consumes reflected Vulkan binding / OpenGL binding / D3D register
```

### Плюсы

- `termin_shaderc` проще и ближе к прозрачному build tool.
- Меньше правил SPIR-V/HLSL patching.
- Проще сравнивать generated artifacts с native Slang reflection output.
- Advanced shaders могут владеть необычными layouts, не борясь с глобальным
  Termin allocator.
- Backend-specific debugging проще: что объявил shader, то и видит backend.

### Минусы И Риски

- Авторы шейдеров или генераторы должны владеть backend placement contracts.
  Это намного большая нагрузка на authoring.
- Engine pass contracts легче случайно сломать: material может объявить
  `material` с неожиданным binding/register, и reflection это примет, если
  дополнительная validation не поймает проблему.
- Cross-backend consistency сложнее. Vulkan set/binding, OpenGL binding и
  D3D11 `b#/t#/s#/u#` registers не являются одинаковыми понятиями.
- Slang auto-allocation может быть достаточно стабильной для одного target,
  но не является надежным engine ABI между targets и версиями компилятора.
- Generated shader variants должны сохранять или merge-ить placement исходного
  shader-а. Это дает новые failure modes, когда variant добавляет
  `bone_block`, `draw_data`, foliage buffers или transient resources, которые
  конфликтуют с исходным shader-ом.
- D3D11 MVP становится рискованнее: backend не может полагаться на fixed
  engine register ranges, если каждый shader или generated variant не
  объявляет их корректно.

### Что Нужно Валидировать

- Enforce explicit engine resource contracts по имени и kind:
  `per_frame`, `lighting`, `shadow_block`, `material`, draw resources и т.д.
- Отклонять stage-pair merges, где один логический ресурс имеет разный
  reflected placement.
- Отклонять backend placement conflicts, даже если names отличаются.
- Определить, как shader-owned placement выражается для каждого target:
  Vulkan set/binding, OpenGL binding, D3D11 register class и register index.
- Определить, разрешена ли Slang auto-allocation или Termin shaders должны
  явно author-ить placement attributes.

## Вариант C: Hybrid Ownership

Termin владеет placement для engine-reserved resources. Shader-owned placement
разрешен для user/material/transient resources внутри валидируемых диапазонов.

Возможное разделение:

| Resource class | Owner |
|---|---|
| `frame` resources | Termin |
| engine `pass` resources | Termin |
| engine draw resources (`draw_data`, `bone_block`, foliage draw data) | Termin |
| ordinary material constant buffer | Termin or fixed material ABI |
| material textures | Shader-owned or Termin-allocated material range |
| transient pass inputs | Shader-owned or Termin-allocated transient range |
| debug/local resources | Shader-owned with validation |

### Как Работает Runtime

```text
termin_shaderc:
  reflect all resources
  classify by name/scope
  apply Termin placement for engine-owned scopes
  preserve or allocate shader-owned placement for allowed scopes
  validate no overlap between owned ranges
  write one sidecar consumed by runtime

Runtime:
  still binds only by resource name/scope
```

### Плюсы

- Engine-critical resources остаются стабильными.
- Не нужно загонять все transient/material textures в глобальный список
  магических имен.
- D3D11 может зарезервировать предсказуемые register ranges для engine
  resources и одновременно выделить отдельные ranges для material/transient
  resources.
- Меньше случайных collisions между engine resources и user resources.
- Можно постепенно двигаться к более shader-owned placement, не ломая текущий
  material pipeline сразу.

### Минусы И Риски

- Policy сложнее, чем любой чистый вариант.
- Нужна точная документация: у каждого scope должен быть owner и разрешенный
  placement range.
- Если правила неясны, получится две системы плюс набор edge cases.
- Compiler должен сообщать conflicts на языке авторов шейдеров:
  "material texture range overlaps transient range", а не просто
  "binding conflict".
- Tests должны покрывать ownership boundaries, а не только финальные значения
  sidecar.

### Что Нужно Валидировать

- Определить reserved ranges для каждого backend.
- Определить, какие scopes могут нести explicit authored placement.
- Отклонять authored placement внутри engine-reserved ranges, если ресурс не
  является точным reserved engine resource.
- Требовать explicit `[[TerminScope]]` для ресурсов, которые не очевидно
  сгенерированы material parser-ом.
- Добавить sidecar schema versioning для ownership model.

## Последствия Для D3D11

D3D11 делает этот выбор конкретным, потому что у него register classes, а не
Vulkan-style descriptor types в единой координатной системе:

| Resource kind | D3D11 register class |
|---|---|
| constant buffer | `b#` |
| shader resource texture/buffer | `t#` |
| sampler | `s#` |
| unordered access/storage | `u#` |

Один числовой `binding` в `tc_shader_resource_binding` поэтому недостаточен
как conceptual model, если только `kind` ресурса всегда не является частью
backend placement key. Vulkan может использовать `(set, binding)`, потому что
descriptor type живет в layout. D3D11 нужен как минимум
`(stage, register_class, register_index)`, а в будущем, возможно, еще и
register spaces, если проект пойдет к D3D12-style layouts.

Для D3D11 MVP:

- Scope-first является самым низкорисковым путем реализации.
- Shader-owned placement самый гибкий, но требует сильного validation layer
  до использования в editor/runtime.
- Hybrid, вероятно, лучший долгосрочный вариант, если Termin хочет сохранить
  стабильность engine resources и при этом не растить бесконечную глобальную
  slot table.

## Сравнение

| Criterion | Scope-first | Shader-owned | Hybrid |
|---|---|---|---|
| D3D11 MVP risk | Low | High | Medium |
| Shader author burden | Low | High | Medium |
| Compiler complexity | High | Low | High |
| Engine ABI stability | High | Low/Medium | High for reserved scopes |
| Advanced shader flexibility | Medium | High | High in allowed ranges |
| Cross-backend consistency | High | Medium/Low | Medium/High |
| Migration cost from current code | Low | High | Medium |
| Long-term clarity | Medium if documented | High if strictly authored | High if rules stay small |

## Рекомендуемый План Исследования

1. Явно задокументировать текущий normalized sidecar ABI, включая последствия
   D3D register classes.
2. Добавить тесты, доказывающие, что migrated runtime paths bind by name и
   никогда не используют guessed fixed slots.
3. Прототипировать D3D11 sidecar representation до написания полного backend:
   проверить, как `constant_buffer`, `texture`, `sampler`, `storage_buffer` и
   `storage_texture` должны мапиться на D3D register classes.
4. Собрать небольшую shader matrix для трех policies:
   - material shader с `material` + двумя textures;
   - postprocess shader с transient input/depth textures;
   - skinned material variant с `bone_block`;
   - pass shader с `per_frame`, `shadow_block` и `shadow_maps`.
5. Решить, разрешен ли explicit authored backend placement в production Slang
   shaders.
6. Если policy меняется, bump-нуть shader artifact layout schema и
   инвалидировать generated sidecars.

## Предварительная Рекомендация

Не переходить напрямую к fully shader-owned placement до D3D11 MVP. В движке
много generated shader variants и pass-owned resources, а для D3D11 нужен
register-class-aware validation, которого сейчас еще нет.

На следующей фазе лучше оставить scope-first placement как operational policy
и параллельно проектировать D3D11 register model. Вероятная долгосрочная цель:
небольшая hybrid policy:

- engine-reserved scopes сохраняют canonical placement;
- material/transient resources могут стать shader-owned или
  compiler-allocated внутри явных непересекающихся ranges;
- runtime во всех случаях остается строго bind-by-name.

Ключевое требование: сделать compiler-side ownership явным. Скрытая name-based
inference должна со временем сокращаться, а generated Slang resources должны
по возможности иметь `[[TerminScope]]`.
