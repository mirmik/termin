# План: tc_texture_sync_to_cpu() — двусторонняя синхронизация текстур

**Дата:** 2026-05-08  
**Статус:** Implemented

## Проблема

GPU-first текстуры (рендер-таргеты, промежуточные буферы) не имеют CPU-копии пикселей.  
Флаг `TC_TEXTURE_STORAGE_GPU_ONLY` семантически неверен — он говорит "нет CPU данных",  
а на самом деле означает "истина на GPU, синхронизация GPU→CPU возможна по запросу".

Превью текстур в material inspector не работает для GPU-first текстур (render-to-texture цепочки).

## Решение

Ввести `tc_texture_sync_to_cpu()` — метод синхронизации, который:
- Для CPU-first текстур: no-op (данные уже на CPU)
- Для GPU-first текстур: readback GPU image → заполнить `tex->data`

Переименовать enum, чтобы отразить семантику **источника истины**, а не наличия данных.

---

## Этапы реализации

### 1. Переименование enum

**Файлы:** `termin-graphics/include/tgfx/resources/tc_texture.h` и все места использования (~10 файлов)

```c
// Было:
typedef enum tc_texture_storage_kind {
    TC_TEXTURE_STORAGE_CPU_PIXELS = 0,
    TC_TEXTURE_STORAGE_GPU_ONLY   = 1,
} tc_texture_storage_kind;

// Стало:
typedef enum tc_texture_storage_kind {
    TC_TEXTURE_STORAGE_CPU_FIRST = 0,  // source of truth is tex->data
    TC_TEXTURE_STORAGE_GPU_FIRST = 1,  // source of truth is GPU image
} tc_texture_storage_kind;
```

- `tc_texture_is_gpu_only()` → `tc_texture_is_gpu_first()`
- Обновить комментарии: флаг означает **источник истины + направление синхронизации**
- Места изменений: `tc_texture.h`, `tc_texture_registry.c`, `tgfx_resource_gpu.c`, `tc_render_target.c`, `vulkan_render_device.cpp`, `tgfx2_gpu_ops.cpp`, `tc_render_target.h` (комментарий), doc-файлы

### 2. Callback в tgfx_gpu_ops vtable

**Файл:** `termin-graphics/include/tgfx/tgfx_gpu_ops.h`

```c
// Readback: download GPU image into tex->data for the texture at pool_index.
// Backend allocates tex->data if NULL. Returns true on success.
bool (*texture_sync_to_cpu)(uint32_t pool_index);
```

- По-умолчанию `NULL` (бэкенд не поддерживает readback)
- `pool_index` — из `tc_texture->header.pool_index`, бэкенд по нему находит GPU handle

### 3. Реализация readback в tgfx2

**Файл:** `tgfx2_gpu_ops.cpp`

Обёртка над существующими методами `IRenderDevice`:
- `read_texture_rgba_float()` — для color текстур
- `read_texture_depth_float()` — для depth текстур

Логика:
1. `g_texture_map[gl_id]` → найти `TextureHandle` по pool_index
2. Вызвать соответствующий readback метод
3. Конвертировать результат (RGBA float32 / depth float32) в формат текстуры
4. Записать в `tex->data` (выделить память если нужно)

**Файлы:** `tgfx2/vulkan/vulkan_render_device.cpp`, `tgfx2/opengl/opengl_render_device.cpp`

Оба бэкенда уже имеют readback. Нужно добавить маппинг `pool_index → TextureHandle`  
(Vulkan уже имеет `tc_texture_cache_`, OpenGL — `g_texture_map`).

### 4. Реализация readback для legacy GPU ops

**Файл:** `tgfx_resource_gpu.c`

Legacy GL: `glReadPixels` через FBO bind (аналогично tgfx2 OpenGL).  
gl_id берётся из `tc_gpu_context` slot по pool_index.

### 5. C-функция tc_texture_sync_to_cpu()

**Файлы:** `tc_texture.h` (декларация) + `tc_texture_registry.c` (реализация)

```c
// Sync GPU-first texture to CPU. No-op for CPU-first.
// Returns true on success (or if already CPU-first).
TGFX_API bool tc_texture_sync_to_cpu(tc_texture* tex);
```

Логика:
- `storage_kind == CPU_FIRST` → `return true`
- `storage_kind == GPU_FIRST` → `ops->texture_sync_to_cpu(tex->header.pool_index)`
- При успехе `tex->data` заполнена, `tex->width/height/channels` уже верны

### 6. Python binding

**Файл:** `termin-graphics/python/bindings/texture_bindings.cpp`

```cpp
.def("sync_to_cpu", [](TcTexture& self) -> bool {
    tc_texture* t = self.get();
    if (!t) return false;
    return tc_texture_sync_to_cpu(t);
}, "Sync GPU-first texture to CPU. No-op for CPU-first textures.")
```

После `tex.sync_to_cpu()` свойство `.data` вернёт numpy array.

### 7. Обновление превью текстур

**tcgui** — `termin-app/termin/editor_tcgui/material_inspector.py`

`_TextureEditor._resolve_preview_image`: если `tex._image_data` пустое,  
попробовать `tex.sync_to_cpu()` и взять данные заново.

**Qt** — `termin-app/termin/editor/material_inspector.py`

`TextureSelector._update_preview`: если `texture.get_preview_pixmap()` вернул `None`,  
fallback на `sync_to_cpu()` → создать QPixmap из numpy array.

### 8. Build & тест

- `./build-sdk.sh`
- Проверить что render target текстуры показывают превью в material inspector
- Проверить что CPU-first текстуры не деградируют (no-op путь)

---

## Семантика после изменений

| Флаг | Источник истины | tex->data | sync_to_cpu() делает |
|---|---|---|---|
| `CPU_FIRST` | CPU (`tex->data`) | Заполнена | no-op, return true |
| `GPU_FIRST` | GPU image | Может быть NULL | readback → заполнить data |

`GPU_FIRST` текстура после `sync_to_cpu()` остаётся `GPU_FIRST` — флаг не меняется.  
Повторный вызов делает свежий readback (не кэширует результат между кадрами).

---

## Отклонения от плана при реализации

1. **Callback signature**: вместо `bool (*)(uint32_t pool_index)` используется `bool (*)(tc_texture* tex)` — колбэку нужен доступ к формату, размерам и полю `data` текстуры для аллокации и записи.

2. **Legacy path (шаг 4)**: отдельная реализация в `tgfx_resource_gpu.c` не потребовалась — обе ветки (legacy GL и tgfx2 OpenGL) идут через `tgfx_gpu_ops` vtable, callback реализован в `tgfx2_gpu_ops.cpp`.

3. **Python preview (шаг 7)**: вместо правок в `material_inspector.py`, `sync_to_cpu()` добавлен в свойство `Texture._image_data` и метод `Texture.get_preview_pixmap()` — это прозрачно чинит превью для всех потребителей (tcgui, Qt, texture_inspector).

4. **Формат данных**: для float16 текстур (RGBA16F/RGB16F) данные хранятся как float32 (4 байта на канал), а не packed float16 — для совместимости с Python numpy.
