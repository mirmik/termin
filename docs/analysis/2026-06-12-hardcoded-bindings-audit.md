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
| `16` | Bone matrices (skinning legacy fallback) | `skinned_mesh_renderer.cpp` |
| `24` | Draw data | `color_pass.cpp` |
| `25` | Draw storage | — |

Эти константы — не просто legacy-код, а **активный fallback-путь**, который работает параллельно с bind-by-name.

---

## 2. SkinnedMeshRenderer: Slang path uses bind-by-name, legacy fallback remains

**Файл:** `termin-components/termin-components-render/src/skinned_mesh_renderer.cpp`

Рендерер скinned-мешей теперь сначала ищет `bone_block` / `BoneBlock` в resource reflection и
биндит UBO по имени. Это покрывает Slang-template variants, где `TerminBoneBlock` описан в
`termin-engine-skinned-common.slang` и попадает в shaderc sidecar layout.

Остался fallback на `TC_SHADER_RESOURCE_BINDING_BONE_BLOCK` для non-layout legacy shaders. Layout-only shaders без `bone_block`
считаются ошибкой и логируются.

**Вердикт:** главный обход системы закрыт для актуального Slang material path. Оставшийся slot fallback можно удалить после
окончательного выключения legacy GLSL renderer paths.

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

## 8. Skinned variants

Regex-инъекция skinning-кода удалена из C++ и Python paths. `shader_skinning.cpp` создаёт только Slang-template variants
для material/shadow/depth/pick/normal фаз через общий `get_material_vertex_variant()` helper в material pipeline.
Старые GLSL shaders больше не получают auto-skinning variant и должны мигрировать на Slang material pipeline.

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
| 🔴 Высокий | Ring UBO overflow — silent corruption | `vulkan_render_device.cpp` |
| 🟡 Средний | Тихий фейл символического биндинга | `render_context.cpp` |
| 🟡 Средний | Flat descriptor set (set 0) — производительность | `material_ubo_apply.cpp`, Vulkan backend |
| 🟡 Средний | Legacy material texture slot fallback ещё нужен старым путям | `tc_material_binding_slots.hpp`, `shader_parser.cpp`, `termin_shaderc.cpp` |
| 🟡 Средний | BoneBlock slot fallback ещё нужен legacy non-layout shaders | `skinned_mesh_renderer.cpp` |
| 🟢 Низкий | Двойной путь push constants | `color_pass.cpp` |
| 🟢 Низкий | GLSL с layout может использовать оба пути биндинга | `shader_binding_policy.hpp` |

Самый критичный оставшийся риск — silent corruption при overflow ring UBO. Skinned path теперь следует reflection-first
модели для актуальных Slang shaders, но legacy fallback ещё стоит убрать после отключения старых GLSL путей.
