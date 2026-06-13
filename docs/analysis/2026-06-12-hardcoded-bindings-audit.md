# Аудит: захардкоженные binding-слоты и обходные хаки bind-by-name

**Дата:** 2026-06-12  
**Цель:** оценить, сколько в коде осталось жёстко заданных binding-слотов, layout-предположений и хаков, обходящих новую bind-by-name политику.

## Контекст

Система использует dual-path binding:
- **Layout-only (name-based)** — для Slang-шейдеров и GLSL с `tc_shader_resource_binding` metadata. Ресурсы биндятся по имени через `tc_shader_find_resource_binding()`.
- **Legacy fallback (index-based)** — для GLSL-шейдеров без layout metadata. Фоллбэк на захардкоженные числовые индексы.

Решение, какой путь использовать, определяется в `shader_binding_policy.hpp`:
- `shader_uses_layout_only_bindings()` — true, если shader имеет layout metadata И не GLSL
- `shader_allows_legacy_resource_fallback()` — инверсия

Legacy fallback **не мёртвый код** — это активный compatibility layer для GLSL-пайплайна.

---

## 1. Карта захардкоженных слотов (legacy ABI)

В `tc_shader.h` зафиксированы константы, которые используются как fallback для GLSL-шейдеров без layout metadata:

| Слот | Назначение | Где используется |
|------|-----------|-----------------|
| `0` | Lighting UBO | `lighting_ubo.hpp`, GLSL-инъекция |
| `1` | Material UBO | `material_ubo_apply.hpp`, `tc_material.h`, `shader_parser.cpp` |
| `2` | Per-frame UBO | `frame_uniforms.hpp`, `shader_parser.cpp` |
| `3` | Shadow Block | `shader_parser.cpp` |
| `4-7` | Material textures 0-3 | `tc_material_binding_slots.hpp` legacy fallback |
| `8` | Shadow maps (резерв) | `tc_material_binding_slots.hpp` |
| `14` | Push constants (GL emulation) | `i_command_list.hpp`, все builtin GLSL |
| `16` | Bone matrices (skinning) | `shader_skinning.cpp`, `skinned_mesh_renderer.cpp` |
| `24` | Draw data | `color_pass.cpp` |
| `25` | Draw storage | — |

Эти константы — не просто legacy-код, а **активный fallback-путь**, который работает параллельно с bind-by-name.

---

## 2. Критическая проблема: SkinnedMeshRenderer обходит bind-by-name полностью

**Файл:** `termin-app/cpp/termin/render/skinned_mesh_renderer.cpp:127`

```cpp
ctx2.bind_uniform_buffer_ring(BONE_BLOCK_BINDING,  // 16, захардкожен
                               staging.data(),
                               staging.size());
```

Рендерер скinned-мешей **никогда** не пытается резолвить binding по имени. Он всегда использует `bind_uniform_buffer_ring(16, ...)` — прямой index-based вызов. При этом:

- Шейдер skinning инжектируется через regex (`shader_skinning.cpp`), который вставляет `layout(std140, binding = 16)` в GLSL-источник
- Для Slang-шейдеров эта инъекция не будет работать корректно, так как Slang не использует `layout(binding = N)`
- Кэширование скinned-вариантов (`s_skinned_shader_cache`) не проверяет, соответствует ли binding 16 реальной политике layout

**Вердикт:** это самый яркий пример обхода системы. Рендерер должен использовать `ctx.bind_uniform("bone_block", ...)` или хотя бы резолвить слот через `tc_shader_find_resource_binding()`.

---

## 3. Legacy `material_texture_binding_for_index()`

Функция, которая мапит индекс текстуры в binding-слот (с пропуском слота 8), теперь централизована для shader compiler,
parser и runtime fallback в `termin-graphics/include/tgfx/resources/tc_material_binding_slots.hpp`.

| Файл | Контекст |
|------|----------|
| `termin-graphics/include/tgfx/resources/tc_material_binding_slots.hpp` | Legacy compile-time/runtime fallback contract |

Оставшийся хвост: новые Slang paths должны постепенно перестать авторить legacy numeric slots там, где bind-by-name/reflection уже достаточно.

---

## 4. Двойной путь биндинга в каждом render pass

Каждый биндинг-хелпер (`bind_lighting_ubo_for_shader`, `bind_shadow_block_for_shader`, `bind_shadow_maps_for_shader`, `apply_material_phase_ubo`) имеет два пути:

```cpp
if (rb) {
    ctx.bind_uniform(rb->name, ...);        // ← bind-by-name
} else if (!shader_uses_layout_only_bindings(shader)) {
    ctx.bind_uniform_buffer_ring(fallback, ...);  // ← legacy index
}
```

Проблема в том, что **GLSL с layout metadata может использовать оба пути**. Функция `shader_allows_legacy_resource_fallback()` возвращает `true` для GLSL с layout, потому что `shader_uses_layout_only_bindings()` исключает GLSL явно. Это означает:

- GLSL-шейдер с layout metadata → может биндиться и по имени и по индексу (зависит от того, нашёлся ли ресурс)
- Slang-шейдер с layout → только по имени (legacy путь заблокирован)
- Любой шейдер без layout → только по индексу

Двойной путь для GLSL-с-layout создаёт риск рассинхронизации: ресурс может быть найден по имени в одном месте и не найден в другом.

---

## 5. Тихий фейл символического биндинга

**Файл:** `render_context.cpp:832-835`

```cpp
const tc_shader_resource_binding* rb =
    tc_shader_find_resource_binding(active_shader_layout_, sb.name.c_str());
if (!rb) {
    tc_log(TC_LOG_WARN, "symbolic binding '%.*s' not found in shader '%s'", ...);
    continue;  // ← молча дропает биндинг
}
```

Если кто-то забыл вызвать `ctx2->use_shader_resource_layout(shader)` после `bind_shader()`, все символические биндинги будут тихо отброшены. Рендер продолжится с пустыми дескрипторами, что приведёт к артефактам, которые крайне сложно отлаживать. Warn-лог тонет в потоке и не останавливает выполнение.

---

## 6. Flat descriptor set — все ресурсы в set 0

Несмотря на то, что система уже имеет scope-разделение (`Frame`, `Pass`, `Material`, `Draw`, `Transient`), Vulkan-бэкенд flattens всё в set 0:

```cpp
// material_ubo_apply.cpp:47
static uint32_t material_ubo_set_for_shader(const tc_shader* shader) {
    (void)shader;
    return 0;
}
```

Это означает, что **каждый draw обновляет весь descriptor set**, даже если изменился только material UBO. Для сцен с тысячами draw-вызовов это `vkUpdateDescriptorSets` на каждый draw вместо обновления только dirty scope.

---

## 7. Ring UBO overflow — молча возвращает неверное смещение

**Файл:** `vulkan_render_device.cpp:1271-1285`

При переполнении слота (8 MB):
```cpp
if (offset_in_slot + padded > ring_ubo_slot_size_) {
    // лог + возврат base (0)
}
```

Все последующие draw-вызовы в этом фрейме получат смещение 0 и будут читать чужие данные. Рендер не крашнется, но будет рисовать артефакты.

---

## 8. Regex-инъекция на hot path

`shader_skinning.cpp` использует `std::regex` для инъекции skinning-кода в vertex shader при первом draw каждого скinned-меша. Для больших шейдеров это может быть заметно в профайлере. Кэш помогает, но первая компиляция каждого меша будет с пиком latency.

---

## 9. Slang-шейдеры без `[[TerminScope]]`

Из 38 Slang-шейдеров (не считая prelude):
- **37** имеют `[[TerminScope]]` на всех ресурсах ✓
- **1** (`termin-engine-debug-triangle.slang`) — тривиальный шейдер без ресурсов
- **1** (`termin-engine-fsq.vert.slang`) — fullscreen quad vertex, тоже без ресурсов

Позиция со scope-ами хорошая. Все ресурсные шейдеры аннотированы.

---

## 10. Push constants — двойной путь (Vulkan vs GL)

Для legacy GLSL-шейдеров push constants эмулируются как UBO на binding 14. В `color_pass.cpp`:

```cpp
if (shader_uses_layout_only_bindings(raw_shader)) {
    bind_draw_data_for_shader(...);  // ← layout path
} else {
    ctx2->set_push_constants(&push, sizeof(push));  // ← legacy
    if (tc_shader_get_language(raw_shader) != TC_SHADER_LANGUAGE_GLSL) {
        bind_draw_data_for_shader(...);  // ← дублирует для non-GLSL без layout
    }
}
```

Три ветки для одного действия. Логика `non-layout Slang + push constants + bind_draw_data` выглядит как результат постепенной миграции, где каждый новый кейс добавлялся отдельным условием.

---

## Приоритеты по исправлению

| Приоритет | Проблема | Файл |
|-----------|----------|------|
| 🔴 Высокий | SkinnedMeshRenderer обходит bind-by-name | `skinned_mesh_renderer.cpp` |
| 🔴 Высокий | Ring UBO overflow — silent corruption | `vulkan_render_device.cpp` |
| 🟡 Средний | Тихий фейл символического биндинга | `render_context.cpp` |
| 🟡 Средний | Flat descriptor set (set 0) — производительность | `material_ubo_apply.cpp`, Vulkan backend |
| 🟡 Средний | Legacy material texture slot fallback ещё нужен старым путям | `tc_material_binding_slots.hpp`, `shader_parser.cpp`, `termin_shaderc.cpp` |
| 🟢 Низкий | Двойной путь push constants | `color_pass.cpp` |
| 🟢 Низкий | Regex инъекция skinning на hot path | `shader_skinning.cpp` |
| 🟢 Низкий | GLSL с layout может использовать оба пути биндинга | `shader_binding_policy.hpp` |

Самый критичный — `SkinnedMeshRenderer`. Он работает в обход всей системы и станет точкой отказа, когда legacy-путь будет выключен.
