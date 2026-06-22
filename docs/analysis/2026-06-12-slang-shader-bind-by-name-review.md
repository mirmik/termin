# Ревью: Slang шейдеры и bind-by-name механика

**Дата:** 2026-06-12
**Автор:** Qwen Code
**Статус:** Активная миграция в процессе

---

## Содержание

1. [Архитектура](#1-архитектура)
2. [Пайплайн компиляции шейдеров](#2-пайплайн-компиляции-шейдеров)
3. [Система сквопов и полиси биндинга](#3-система-сквопов-и-полиси-биндинга)
4. [Критические проблемы](#4-критические-проблемы)
5. [Архитектурные риски](#5-архитектурные-риски)
6. [Замечания по качеству кода](#6-замечания-по-качеству-кода)
7. [Статус миграции GLSL → Slang](#7-статус-миграции-glsl--slang)
8. [Рекомендации по приоритизации](#8-рекомендации-по-приоритизации)

---

## 1. Архитектура

### 1.1 Общая схема

```
Shader Source (.slang)
    │
    ▼
termin_shaderc (compile-time)
    ├── slangc → SPIR-V + JSON reflection
    ├── infer_resource_bindings_from_slang_reflection()
    ├── apply_slang_vulkan_scope_layout_policy()
    ├── filter_slang_vulkan_resources_for_spirv()
    ├── patch_slang_vulkan_spirv_bindings()
    └── write_resource_layout_sidecar() → .layout.json
    │
    ▼
Runtime (.spv + .layout.json)
    ├── tc_shader_bridge::apply_shader_resource_layout_sidecar()
    │   ├── parse_shader_resource_layout_sidecar()
    │   ├── merge_shader_resource_binding()
    │   └── tc_shader_set_resource_layout() [sorts by name, binary search]
    │
    ▼
RenderContext2 (symbolic binding)
    ├── use_shader_resource_layout(shader)
    ├── bind_uniform("per_frame", buffer)  → SymbolicBinding
    ├── bind_texture("albedo", tex, samp)  → SymbolicBinding
    └── flush_resource_set()
        ├── tc_shader_find_resource_binding() [binary search]
        ├── resolve SymbolicBinding → ResourceBinding (set, binding, kind)
        └── device.create_resource_set() → VkDescriptorSet
```

### 1.2 Ключевые файлы

| Файл | Роль |
|------|------|
| `tools/termin_shaderc.cpp` (1632 стр.) | Компилятор шейдеров, Slang reflection, SPIR-V patching |
| `src/resources/tc_shader_registry.c` (1226 стр.) | C-регистр шейдеров, layout management, bsearch |
| `src/tgfx2/tc_shader_bridge.cpp` (1214 стр.) | Runtime загрузка .layout.json, merge, dev-compile |
| `src/tgfx2/render_context.cpp` (1266 стр.) | Символьное разрешение, flush, descriptor set |
| `src/tgfx2/render_context.hpp` (400 стр.) | SymbolicBinding, ResourceScope, pending buckets |
| `src/tgfx2/vulkan/vulkan_render_device.cpp` (4264 стр.) | SPIR-V reflection, ring UBO, per-pipeline layout |
| `src/tgfx2/opengl/opengl_command_list.cpp` | OpenGL бэкенд (без descriptor sets) |

### 1.3 Данные

**`tc_shader_resource_binding`** (C struct):
```c
typedef struct tc_shader_resource_binding {
    char name[64];           // имя ресурса
    uint32_t kind;           // CONSTANT_BUFFER=1, TEXTURE=2, SAMPLER=3, STORAGE_BUFFER=4, STORAGE_TEXTURE=5
    uint32_t scope;          // UNKNOWN=0, FRAME=1, PASS=2, MATERIAL=3, DRAW=4, TRANSIENT=5
    uint32_t set;            // Vulkan descriptor set (сейчас всегда 0)
    uint32_t binding;        // Vulkan/OpenGL binding slot
    uint32_t stage_mask;     // VERTEX, FRAGMENT, GEOMETRY, COMPUTE
    uint32_t size;           // bytes для буферов, 0 для текстур/сэмплеров
    tc_shader_resource_field* fields;  // per-field layout для constant buffers
    uint32_t field_count;
} tc_shader_resource_binding;
```

**`SymbolicBinding`** (C++ struct в RenderContext2):
```cpp
struct SymbolicBinding {
    std::string name;
    enum class Kind { Uniform, StorageBuffer, Texture } kind;  // ← ПРОБЛЕМА: нет Sampler, StorageTexture
    BufferHandle buffer;
    TextureHandle texture;
    SamplerHandle sampler;
    uint64_t offset = 0;
    uint64_t range = 0;
};
```

---

## 2. Пайплайн компиляции шейдеров

### 2.1 Build-time

- `termin_shaderc` собирается как standalone executable
- Условие: `TGFX2_ENABLE_VULKAN AND TGFX2_ENABLE_SHADERC AND NOT ANDROID`
- **Slang на Android не компилируется build-time** — нет пути компиляции
- Шейдеры копируются в build tree через `copy_directory`
- Автоматическая компиляция Slang в CMake **отсутствует** — вызывается вручную или через CI

### 2.2 Runtime dev-compile

- `tgfx2_load_or_compile_shader_artifact_for_backend()` (tc_shader_bridge.cpp:1054)
- Если `TERMIN_SHADER_DEV_COMPILE` включён и артефакт устарел/отсутствует:
  - Вызывает `termin_shaderc compile` как subprocess
  - Для Slang: добавляет `-I <root>` для каждого builtin shader root
- Записывает `.meta` файлы для проверки свежести

### 2.3 Ключевое ограничение

**Slang не имеет runtime fallback.** В отличие от GLSL, у которого есть `compile_glsl_to_spirv()` с disk cache (`~/.cache/termin/tgfx2/spirv/`), Slang шейдеры с `TC_SHADER_ARTIFACT_REQUIRED` падают с ошибкой, если pre-compiled артефакт отсутствует.

### 2.4 Два пути компиляции в `termin_shaderc`

**GLSL → SPIR-V:**
- Google shaderc library напрямую
- `compile_glsl_to_vulkan()` (line 1411)
- `SetAutoMapLocations(true)`, `SetAutoBindUniforms(true)`
- `#define VULKAN 100` для условной компиляции

**Slang → SPIR-V:**
- `slangc` как subprocess
- `compile_slang()` (line 1460)
- Генерирует reflection JSON (`-reflection-json`)
- Применяет scope layout policy
- Патчит SPIR-V decorations
- Пишет `.layout.json` sidecar

---

## 3. Система сквопов и полиси биндинга

### 3.1 Атрибут `[[TerminScope("scope")]]`

Определён в `termin_prelude.slang`:
```hlsl
[__AttributeUsage(_AttributeTargets.Var)]
public struct TerminScopeAttribute { string value; }
```

Валидные значения: `frame`, `pass`, `material`, `draw`, `transient`

### 3.2 Name-based inference (fallback)

Если `[[TerminScope]]` отсутствует, `infer_resource_scope()` использует паттерны:

| Имя | Scope |
|-----|-------|
| `per_frame`, `u_per_frame` | frame |
| `material` | material |
| `draw`, `draw_data`, `u_draw`, `u_push`, `pc` | draw |
| `lighting`, `lighting_ubo`, содержит `shadow` | pass |
| `u_params` | pass |
| `u_input`, `u_texture`, `u_color`, `u_depth_tex`, `u_tex`... | transient |
| содержит `albedo`, `normal`, `metallic`, `roughness`... | material |
| начинается с `u_` | unknown |
| всё остальное | unknown |

**Проблема:** name-based inference — это хрупкая магическая таблица. Добавление нового шейдера с нестандартным именем ресурса приведёт к `scope=unknown`, что означает fallback binding и потенциальный конфликт.

### 3.3 Retired fixed-slot remap

The fixed scope-to-slot remap described in the original review has been
removed. Slang artifacts now keep Slang-reflected placement in the sidecar, and
runtime code binds by resource name/scope instead of rewriting artifacts into a
global Termin numeric ABI.

### 3.4 Legacy shared policy

`apply_slang_vulkan_shared_layout_policy()` (line 867) — flatten everything to set 0 без scope-based assignment. Существует для обратной совместимости со старыми артефактами/тестами.

---

## 4. Критические проблемы

### 4.1 [CRITICAL] Нарушение инварианта сортировки в `tc_shader_registry.c`

**Файл:** `src/resources/tc_shader_registry.c`

`tc_shader_find_resource_binding()` использует бинарный поиск через `tc_shader_find_resource_binding_index_sorted()` (line 938). Массив сортируется в `tc_shader_set_resource_layout()` (line 1182):

```c
if (count > 1) {
    qsort(copy, count, sizeof(tc_shader_resource_binding), tc_shader_resource_binding_compare);
}
```

Но `tc_shader_upsert_resource_binding()` (line 953) и `tc_shader_remove_resource_binding()` (line 984) **ломают сортировку**:

- `upsert`: использует линейный поиск для lookup, **append** для вставки (добавляет в конец, не по сортированному индексу)
- `remove`: использует **swap-and-pop** (меняет найденный элемент с последним)

**Сценарий проявления:**
1. `tc_shader_set_resource_layout()` → массив отсортирован
2. `tc_shader_set_material_ubo_layout()` → вызывает `upsert`/`remove` → массив несортирован
3. `tc_shader_find_resource_binding("per_frame")` → бинарный поиск возвращает NULL или неверный элемент

**Текущий call order безопасен:** `set_material_ubo_layout()` вызывается до `tc_shader_ensure_tgfx2()`, после чего sidecar layout полностью заменяет массив. Но это **латентный баг** — любая динамическая мутация после применения sidecar сломает поиск.

**Фикс:** `upsert` должен вставлять по отсортированному индексу (или пересортировать после вставки); `remove` должен сдвигать элементы, а не swap-and-pop.

### 4.2 [CRITICAL] `SymbolicBinding::Kind` не покрывает все типы ресурсов

**Файл:** `src/tgfx2/render_context.hpp:68`

```cpp
enum class Kind { Uniform, StorageBuffer, Texture };
```

Отсутствуют:
- **Sampler** (standalone `SamplerState`)
- **StorageTexture** (`RWTexture`)

`tc_shader_resource_binding` поддерживает:
- `TC_SHADER_RESOURCE_CONSTANT_BUFFER` (1)
- `TC_SHADER_RESOURCE_TEXTURE` (2)
- `TC_SHADER_RESOURCE_SAMPLER` (3)
- `TC_SHADER_RESOURCE_STORAGE_BUFFER` (4)
- `TC_SHADER_RESOURCE_STORAGE_TEXTURE` (5)

В `flush_resource_set()` (render_context.cpp:856) switch по `sb.kind` обрабатывает только 3 кейса. Если шейдер объявит standalone sampler или storage texture, символьный биндинг **тихо провалится** — ресурс не привяжется, draw использует старое значение из descriptor slot.

**Фикс:** Добавить `Sampler` и `StorageTexture` в `SymbolicBinding::Kind`, добавить методы `bind_sampler(name, sampler)` и `bind_storage_texture(name, texture)`.

### 4.3 [CRITICAL] Ring UBO overflow — молчаливая коррумпация данных

**Файл:** `src/tgfx2/vulkan/vulkan_render_device.cpp:1276-1295`

```cpp
uint64_t offset_in_slot =
    ring_ubo_heads_[slot].fetch_add(padded, std::memory_order_relaxed);

if (offset_in_slot + padded > ring_ubo_slot_size_) {
    static std::atomic_bool s_warned = false;
    if (!s_warned) {
        tc_log(TC_LOG_ERROR, "[RingUBO] slot %u overflow: ...");
        s_warned = true;
    }
    return static_cast<uint32_t>(base);  // ← возвращает offset 0, перезаписывает данные
}
```

**Проблемы:**
1. При overflow функция возвращает `base` (начало слота), что означает **перезапись** данных, записанных ранее в этот же слот
2. Логирование через локальный флаг скрывает повторные overflow-события; флаг должен быть потокобезопасным и не должен использовать thread-local состояние
3. Нет механизма восстановления — последующие draw-коллы используют повреждённые UBO

**Размер слота:** 8 MB (6 слотов × 8 MB = 48 MB total). При ~10 KB UBO на draw и 1600 worst-case draws/frame нужно ~16 MB, так что слот в 8 MB **тесен**.

**Рекомендация:** Либо увеличить размер слота, либо при overflow аллоцировать temporary buffer (fallback), либо abort с понятной ошибкой.

### 4.4 [CRITICAL] `begin_pass()` очищает все бакеты включая Frame scope

**Файл:** `src/tgfx2/render_context.cpp:179`

```cpp
void RenderContext2::begin_pass() {
    // ...
    clear_pending_binding_buckets();  // ← очищает ВСЕ бакеты
    // ...
}
```

`clear_pending_binding_buckets()` сбрасывает все `pending_binding_buckets_`, включая Frame scope. Это противоречит семантике Frame scope (привязать один раз на кадр, валидно для всех пассов).

Камерный UBO и другие frame-scoped ресурсы нужно перепривязывать каждый пасс, что:
- Увеличивает количество bind-операций
- Делает scope бесполезным для оптимизации dirty tracking

**Фикс:** В `begin_pass()` очищать только Draw и Transient buckets. Frame и Pass buckets очищать в `begin_pass()` и `begin_frame()` соответственно.

---

## 5. Архитектурные риски

### 5.1 [HIGH] SPIR-V reflection жёстко привязан к set=0

**Файл:** `src/tgfx2/vulkan/vulkan_render_device.cpp:288`

```cpp
if (words[3] != 0) {
    tc_log(TC_LOG_ERROR,
           "VulkanRenderDevice: SPIR-V decoration DescriptorSet=%u != 0 "
           "on target %u; only set=0 is supported",
           words[3], target_id);
}
```

Это hard error для любого non-zero descriptor set. Текущая политика назначает все биндинги на set=0, но:
- `get_or_create_descriptor_set_layout()` строит **один** `VkDescriptorSetLayout`
- Нет поддержки multiple sets в per-pipeline layout builder
- Если scope-based policy когда-нибудь перейдёт на multi-set, это сломается

### 5.2 [HIGH] `bind_uniform_data()` не валидирует размер

**Файл:** `src/tgfx2/render_context.cpp:645`

Функция проверяет `rb->kind` но **не сравнивает** переданный `size` с `rb->size`. Если caller передаёт больше байт, чем объявлено в UBO шейдера:
- Ring UBO write пройдёт без валидации
- Oversized write может перекрыть следующую аллокацию в том же слоте
- Коррумпация данных будет проявляться как артефакты рендера в следующем draw

**Фикс:** Добавить `if (size > rb->size)` с warn/error.

### 5.3 [HIGH] `std::memory_order_relaxed` в ring UBO

**Файл:** `src/tgfx2/vulkan/vulkan_render_device.cpp:1276`

```cpp
uint64_t offset_in_slot =
    ring_ubo_heads_[slot].fetch_add(padded, std::memory_order_relaxed);
```

Комментарий говорит "relaxed ordering is sufficient", но это не доказано. При многопоточной записе (parallel pass recording):
- Reordering `memcpy` до завершения `fetch_add`
- На 32-битных платформах — torn reads для 64-битных atomics

**Рекомендация:** Использовать `std::memory_order_acq_rel` или документировать инвариант, при котором relaxed безопасен (например, "все записи из одного потока").

### 5.4 [HIGH] Смешанные API без депрекейшн

**Файл:** `src/tgfx2/render_context.hpp:250-275`

Одновременно доступны:
- Числовой: `bind_uniform_buffer(binding, buffer, offset, range, set)`, `bind_storage_buffer(...)`, `bind_sampled_texture(...)`
- Символьный: `bind_uniform(name, buffer, ...)`, `bind_storage_buffer(name, buffer, ...)`, `bind_texture(name, texture, sampler)`

Нет маркеров депрекейшна, нет гайдлайнов. Новый код может миксовать оба API, получая проблемы с порядком биндинга и непредсказуемым состоянием descriptor set.

### 5.5 [MEDIUM] Символьные биндинги всегда в Unknown scope

**Файл:** `src/tgfx2/render_context.cpp:600`

Все символьные биндинги попадают в `ResourceScope::Unknown` bucket. Scope определяется только при resolution (из shader layout). Это значит:
- Scope bucketing — пост-фактум организационная деталь, не pre-resolution оптимизация
- Dirty tracking по scope не работает
- Инкрементальные обновления descriptor set невозможны

### 5.6 [MEDIUM] `ResourceSetDesc` flattening теряет scope

Backend получает flat `ResourceSetDesc` с всеми биндингами в одном векторе. Scope buckets существуют только на стороне RenderContext. Это означает:
- Scope-based оптимизации (dirty tracking per scope, incremental descriptor updates) теряются на границе с backend
- Backend не может оптимизировать пересоздание descriptor set на основе изменённого scope

---

## 6. Замечания по качеству кода

### 6.1 Дублирование name-based inference

Name-based scope inference (`infer_resource_scope()` в `termin_shaderc.cpp:168`) дублирует логику, которая должна быть в shader source через `[[TerminScope]]`. Текущее покрытие:

| Шейдер | Scoped? |
|--------|---------|
| `termin-engine-depth.slang` | ✅ Да |
| `termin-engine-depth-only.slang` | ✅ Да |
| `termin-engine-normal.slang` | ✅ Да |
| `termin-engine-shadow.slang` | ✅ Да |
| `termin-engine-id.slang` | ❌ Нет (rely on name heuristic) |
| `termin-engine-immediate.slang` | ❌ Нет |
| `termin-engine-text2d.slang` | ❌ Нет |
| Все post-processing шейдеры | ❌ Нет |

**Около 20 из 30 Slang шейдеров не имеют явных `[[TerminScope]]` атрибутов.** Это делает систему зависимой от хрупкой магической таблицы имён.

### 6.2 Две версии scope attribute

`slang_scope_attribute_from_parameter()` поддерживает и `TerminScope`, и `Scope` (legacy). Дублирование naming convention может привести к путанице. Рекомендуется депрекейтить `Scope`.

### 6.3 `tc_shader_upsert_resource_binding()` — запутанная двойная запись

**Файл:** `src/resources/tc_shader_registry.c:937-943`

```c
shader->resource_bindings[shader->resource_binding_count] = *binding;
shader->resource_bindings[shader->resource_binding_count]
    .name[TC_SHADER_RESOURCE_NAME_MAX - 1] = '\0';
shader->resource_binding_count = new_count;
```

Вторая строка записывает в тот же индекс, что и первая (до инкремента). Технически корректно (null-терминирует имя), но структура запутанная и error-prone.

### 6.4 `std::malloc`/`std::free` в C++ bridge

**Файл:** `src/tgfx2/tc_shader_bridge.cpp:595`

C++ bridge аллоцирует fields через `std::malloc`, а C registry освобождает через `free()`. Работает на одной платформе, но может быть проблемой при DLL boundary на Windows с разными CRT.

### 6.5 OpenGL игнорирует `dynamic_offsets`

**Файл:** `src/tgfx2/opengl/opengl_command_list.cpp:287`

`bind_resource_set()` принимает `dynamic_offsets`, но не использует их. OpenGL использует `glBindBufferRange` с baked-in offsets. API вводит в заблуждение — сигнатура `ICommandList::bind_resource_set()` включает `dynamic_offsets` для обоих бэкендов.

### 6.6 SPIR-V patching — хрупкий парсинг бинарного формата

**Файл:** `tools/termin_shaderc.cpp:1030-1165`

`patch_slang_vulkan_spirv_bindings()` парсит SPIR-V бинарный формат вручную:
- Ищет `OpName` (opcode 5) для name → ID mapping
- Патчит `OpDecorate` (opcode 71) для Binding (33) и DescriptorSet (34)

Это работает, но:
- Нет валидации, что SPIR-V модуль корректен после patching
- `spirv-val` не вызывается после patching
- Если slangc изменит формат reflection или SPIR-V output, patching может сломаться

### 6.7 Нет тестов на символьный bind-by-name путь

- `test_render_context2.cpp` — использует numeric binding или без биндингов
- `test_per_pipeline_layout.cpp` — numeric binding path
- `tests_shader_resource_layout.cpp` — только data structure (set_resource_layout, find_resource_binding)

Отсутствует integration test: `bind_shader() → use_shader_resource_layout() → bind_uniform(name) → draw() → verify GPU state`.

---

## 7. Статус миграции GLSL → Slang

### 7.1 Slang шейдеры (30 файлов)

**Полностью scoped (4):**
- `termin-engine-depth.slang`
- `termin-engine-depth-only.slang`
- `termin-engine-normal.slang`
- `termin-engine-shadow.slang`

**Unscoped Slang (~26):**
- `termin-engine-id.slang`
- `termin-engine-immediate.slang`
- `termin-engine-text2d.slang`, `termin-engine-text2d-sdf.slang`
- `termin-engine-text3d.slang`
- `termin-engine-canvas2d-solid.slang`, `termin-engine-canvas2d-texture.slang`
- Все post-processing шейдеры (bloom, tonemap, grayscale, highlight, fsq)
- Foliage vertex shaders

**Shared libraries (2):**
- `termin_lighting.slang` (scoped `pass`)
- `termin_shadows.slang` (scoped `pass`)

### 7.2 Оставшиеся GLSL шейдеры (~22 в catalog)

- `termin-engine-depth-material`
- `termin-engine-gizmo-mask`
- `termin-engine-ground-grid`
- `termin-engine-line-default`
- `termin-engine-navmesh-debug`
- `termin-engine-off-mesh-link-debug`
- `termin-engine-pick-material`
- `termin-engine-screen-line` (+ cap, join, round-join)
- `termin-engine-shadow-material`
- `termin-engine-voxel-display`, `termin-engine-voxelizer-line`
- `termin-engine-world-line` (+ lit, cap, join, round-join)
- `termin-engine-world-tube-line` (+ lit, cap)

**GLSL паттерн** (legacy):
```glsl
#ifdef VULKAN
layout(push_constant) uniform PushBlock { ... } pc;
#else
layout(binding=14, std140) uniform PushBlock { ... } pc;
#endif
```
Slang устраняет эту необходимость, абстрагируя backend-specific детали.

### 7.3 Два тира Slang

1. **Tier 1 — Fully scoped:** Используют `[[TerminScope]]`, import `termin_prelude.slang`, shared libraries. Полностью используют bind-by-name.
2. **Tier 2 — Unscoped:** Нет prelude import, нет `TerminScope`. Используют legacy naming conventions (`u_per_frame`, `u_push`, `material`). Зависят от name-based heuristics.

Рекомендуется довести все Slang шейдеры до Tier 1.

---

## 8. Рекомендации по приоритизации

### Immediate (исправить сейчас)

1. **Fix sorted invariant** в `tc_shader_upsert_resource_binding()` и `tc_shader_remove_resource_binding()` — латентный баг, который гарантированно проявится при динамических изменениях
2. **Добавить `Sampler` и `StorageTexture`** в `SymbolicBinding::Kind` — дыра в покрытии, которая не даст привязать standalone sampler
3. **Fix ring UBO overflow** — либо увеличить размер слота (16 MB), либо добавить fallback на temporary buffer
4. **Fix `begin_pass()` scope clearing** — Frame scope должен пережить `begin_pass()`

### Short-term (следующий спринт)

5. **Добавить валидацию размера** в `bind_uniform_data()` — `size <= rb->size`
6. **Добавить интеграционные тесты** для символьного bind-by-name пути
7. **Депрекейтить numeric API** — добавить `[[deprecated]]` на `bind_uniform_buffer()`, `bind_storage_buffer()`, `bind_sampled_texture()`
8. **Довести все Slang шейдеры до Tier 1** — добавить `[[TerminScope]]` атрибуты на все unscoped шейдеры

### Medium-term

9. **Поддержка multi-set layout** — подготовить `get_or_create_descriptor_set_layout()` для нескольких descriptor sets
10. **Scope-based dirty tracking** — использовать scope buckets для инкрементальных обновлений descriptor set
11. **`spirv-val` после patching** — добавить валидацию SPIR-V после `patch_slang_vulkan_spirv_bindings()`
12. **Миграция оставшихся GLSL шейдеров** в Slang

---

## Приложение A: retired binding constants

The old fixed binding constants were removed. Current code should get backend
placement from `tc_shader_resource_binding` metadata or shader sidecars.

## Приложение B: Полный список `.slang` файлов

```
termin-graphics/resources/builtin_shaders/
├── termin_prelude.slang              # Library (TerminScope attribute definition)
├── termin_lighting.slang             # Shared library (pass scope)
├── termin_shadows.slang              # Shared library (pass scope)
├── termin-engine-depth.slang         # Full VS+FS (scoped)
├── termin-engine-depth-only.slang    # Full (scoped)
├── termin-engine-normal.slang        # Full (scoped)
├── termin-engine-shadow.slang        # Full (scoped)
├── termin-engine-id.slang            # Full (unscoped)
├── termin-engine-present-blit.slang  # Full (unscoped)
├── termin-engine-immediate.slang     # Full (unscoped)
├── termin-engine-solid-primitive.slang # Full (unscoped)
├── termin-engine-debug-triangle.slang  # Full (unscoped)
├── termin-runtime-default-color.slang  # Full (unscoped)
├── termin-engine-fsq.vert.slang      # Vertex only (unscoped)
├── termin-engine-foliage-instanced.vert.slang # Vertex (unscoped)
├── termin-engine-foliage-shadow.vert.slang    # Vertex (unscoped)
├── termin-engine-text2d.slang        # Full (unscoped)
├── termin-engine-text2d-sdf.slang    # Full (unscoped)
├── termin-engine-text3d.slang        # Full (unscoped)
├── termin-engine-canvas2d-solid.slang # Full (unscoped)
├── termin-engine-canvas2d-texture.slang # Full (unscoped)
├── termin-engine-bloom-bright.frag.slang     # Fragment (unscoped)
├── termin-engine-bloom-composite.frag.slang  # Fragment (unscoped)
├── termin-engine-bloom-downsample.frag.slang # Fragment (unscoped)
├── termin-engine-bloom-upsample.frag.slang   # Fragment (unscoped)
├── termin-engine-color-to-depth.frag.slang   # Fragment (unscoped)
├── termin-engine-depth-to-color.frag.slang   # Fragment (unscoped)
├── termin-engine-grayscale.frag.slang        # Fragment (unscoped)
├── termin-engine-highlight.frag.slang        # Fragment (unscoped)
└── termin-engine-tonemap.frag.slang          # Fragment (unscoped)

termin-app/termin/resources/stdlib/slang/
├── runtime_default_color.vert.slang
└── runtime_default_color.frag.slang
```
