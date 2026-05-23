# Анализ поддержки OpenGL бэкенда в tgfx2

Дата: 2026-05-23

## Архитектура tgfx2

tgfx2 — двухбэкендный графический слой с абстрактным `IRenderDevice`. OpenGL и Vulkan реализованы параллельно, переключение через `TERMIN_BACKEND` переменную окружения. По умолчанию — Vulkan.

### Расположение кода

- **Заголовки**: `termin-graphics/include/tgfx2/` (29 файлов)
- **Исходники**: `termin-graphics/src/tgfx2/` (20 файлов)
- **OpenGL**: `opengl/opengl_render_device.cpp` (1215 строк), `opengl_command_list.cpp`
- **Vulkan**: `vulkan/vulkan_render_device.cpp` (3045 строк), `vulkan_command_list.cpp`, `vulkan_swapchain.cpp`, `vulkan_shader_compiler.cpp`

### Проекты, использующие tgfx2

| Проект | Бэкенд | Примечание |
|--------|--------|------------|
| termin-render-passes | tgfx2-only | Все пассы требуют `ctx.ctx2` |
| termin-engine | tgfx2 device + textures | RenderingManager |
| termin-display | оба бэкенда | BackendWindow через tgfx2 |
| termin-app | tgfx2 | gizmos, ground grid, collider gizmo |
| termin-android | **Vulkan-only** | Нет desktop OpenGL на Android |
| tcplot | tgfx2 2D/3D engines | GPU host |
| termin-gui (tcgui) | tgfx2 | Python виджеты |
| diffusion-editor | tgfx2 via tgfx native | Python editor |
| C# биндинги | **OpenGL-only** | Рекомендация: `--no-sdl --no-vulkan` |

## Критические проблемы

### 1. Наследие OpenGL в абстрактном интерфейсе

Удалено из `IRenderDevice`:

- `blit_to_external_target(uintptr_t)` — `uintptr_t` это `GLuint` FBO, на Vulkan нет аналога
- `clear_external_target(uintptr_t)` — аналогично
- `native_texture_handle()` — возвращает `GLuint`, на Vulkan отсутствует
- `last_gl_error()` — backend-specific diagnostic

Presentation теперь идёт через `TextureHandle` (`blit_to_texture` / `clear_texture`).
Surfaces, которые не отдают tgfx2 color target, считаются немигрированными и логируют ошибку вместо raw-FBO fallback.

### 2. Push constants эмулируются по-разному

| | OpenGL | Vulkan |
|--|--------|--------|
| Механизм | UBO ring (binding 14, 256KB) | Нативные `vkCmdPushConstants` |
| C++ API | `push_constants_write()` | `ring_ubo_write()` (другой API) |
| Шейдеры | `#ifdef VULKAN` в GLSL | layout push_constant vs UBO |

Данные передаются через один C++ struct, но механизм и вызовы отличаются. Шейдеры содержат `#ifdef VULKAN` для выбора пути между push_constant и UBO.

### 3. Transient vertex buffer

OpenGL имеет stream VBO ring для immediate draw. Vulkan реализует
double-buffered mapped vertex ring: один слот может читаться GPU, второй
заполняется CPU на следующем кадре. `RenderContext2::draw_immediate_*`
использует общий API `transient_vertex_write()` / `transient_vertex_buffer()`.

### 4. Readback текстур

OpenGL реализует:
- `read_texture_rgba_float` через FBO + `glReadPixels`
- `read_texture_depth_float` через FBO + `glReadPixels`

Vulkan реализует синхронный full-texture readback через staging buffer +
`vkCmdCopyImageToBuffer`. Color path конвертирует поддержанные форматы в
RGBA float на CPU, depth path поддерживает `D32F`.

### 5. FBO cache — только OpenGL

OpenGL кэширует `GLuint` по pass key. Vulkan не имеет аналога (VkFramebuffer кэшируется отдельно).

### 6. Асинхронные readback — только Vulkan

Vulkan имеет `request_pixel_rgba8`/`poll_pixel_rgba8` (async через staging buffer + fence). OpenGL не имеет этого.

## Сводная таблица функциональности

| Функциональность | OpenGL | Vulkan |
|-----------------|--------|--------|
| `upload_texture_region` | Полная (`glTexSubImage2D`) | Есть (`vkCmdCopyBufferToImage` через staging buffer) |
| `read_texture_rgba_float` | Есть | Есть (staging + CPU convert) |
| `read_texture_depth_float` | Есть | Есть для `D32F` |
| Raw external FBO present | Удалён из tgfx2 API | Не поддерживается |
| Raw native texture handle | Удалён из tgfx2 API | Удалён из tgfx2 API |
| Push constants ring | Полная (UBO ring, 256KB) | Ring UBO, **другой API** |
| Transient vertex ring | Полная (stream VBO ring) | Есть (mapped double-buffered VBO ring) |
| FBO cache | Есть | **Нет** |
| Shader compilation | `glCreateShader` + `glCompileShader` | Требует **shaderc** (GLSL→SPIR-V) |
| `last_gl_error` | Удалён из tgfx2 API | Удалён из tgfx2 API |
| Swapchain / Present | Нет (SDL/GLFW surface) | `VulkanSwapchain` с acquire/present |
| Асинхронные readback | **Нет** | Есть (`request_pixel_rgba8`) |
| Deferred destroy | `glDelete*` сразу | Fence-based pending destroy |
| Descriptor pools | Нет (GL state machine) | Double-buffered, сброс каждый фрейм |
| Image layout transitions | Нет (implicit) | Explicit `transition_image_layout()` |

## TODO и незавершённые функции

| Файл | Описание |
|------|----------|
| `include/tgfx2/i_command_list.hpp:22` | Shader compilation from source на Vulkan — "not implemented yet, Vulkan backend TBD" |

## Зависимости

| Бэкенд | Зависимости |
|--------|------------|
| OpenGL | **glad** (GL loader), **GLEW** (опционально) |
| Vulkan | **Vulkan SDK**, **VMA** (Vulkan Memory Allocator), **shaderc** (опционально, но без него нужна предкомпиляция SPIR-V) |

## Сборка

- `TERMIN_ENABLE_OPENGL` / `TGFX2_ENABLE_OPENGL` — контролирует `TGFX2_HAS_OPENGL`
- `TERMIN_ENABLE_VULKAN` / `TGFX2_ENABLE_VULKAN` — контролирует `TGFX2_HAS_VULKAN` (OFF на Android)
- `TGFX2_ENABLE_SHADERC` — runtime GLSL→SPIR-V (OFF на Android)
- Скрипты поддерживают `--no-opengl` и `--no-vulkan`
- Android: Vulkan-only, C#: OpenGL-only (рекомендация)

## Итоговая оценка

**OpenGL бэкенд всё ещё имеет больше legacy interop-поверхности** внутри concrete backend-а, но raw GL FBO/native handle операции больше не являются частью `IRenderDevice`. Vulkan более объёмный по коду (3045 vs 1215 строк), но имеет незавершённые области:

1. Без shaderc Vulkan не может компилировать шейдеры из GLSL-источника

API несимметричен — OpenGL-специфичные методы в `IRenderDevice` создают путаницу. Шейдеры зависят от `#ifdef VULKAN`, что усложняет поддержку.

## Обновление 2026-05-23

- Vulkan `upload_texture_region` реализован через staging buffer и `vkCmdCopyBufferToImage` с `imageOffset`/`imageExtent`.
- `tgfx2_vulkan_smoke` теперь явно компилируется с `TGFX2_HAS_VULKAN`; раньше при включённом Vulkan target мог собираться как skip-тест из-за приватного compile define библиотеки.
- Smoke-тест расширен проверкой частичной загрузки RGBA8-региона и синхронизирован после immediate copy перед CPU readback.
- Vulkan upload/render-pass exit больше не переводит несэмплируемые image в `SHADER_READ_ONLY_OPTIMAL`; это убирает validation error для render targets, созданных только как `ColorAttachment | CopySrc`.
- Vulkan `read_texture_rgba_float` и `read_texture_depth_float` добавлены в backend; smoke-тест проверяет full RGBA8 readback и full D32F depth readback.
- Vulkan transient vertex ring добавлен; smoke-тест рисует треугольник через `transient_vertex_write()` / `transient_vertex_buffer()`.
- Raw external FBO/native texture handle helpers удалены из `IRenderDevice` и Python tgfx2 bindings. Legacy present paths теперь требуют surface `TextureHandle`; при отсутствии target-а логируется ошибка вместо fallback в raw FBO.
