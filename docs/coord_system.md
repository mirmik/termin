# Coordinate systems in termin-env

Единая схема осей и единиц в движке. Все слои (C++ и Python) следуют
ей; любой backend (OpenGL / Vulkan) **обязан** выдать этому API такое же
поведение. Никаких «за исключением GL» или «на Vulkan по-другому» в
API слое быть не должно — только внутри backend-адаптеров.

## 1. Pixel / window space (Y+ down, origin top-left)

Используется везде, где речь идёт о пикселях на экране или о пикселях
текстуры:

- `Widget.x / y / width / height`
- `UIRenderer.draw_rect / draw_text / begin_clip`
- `ctx.set_viewport(x, y, w, h)`
- `ctx.set_scissor(x, y, w, h)`
- SDL mouse events
- Framebuffer memory address space, как его видит прикладной код

Ориентация:

- `(0, 0)` — **верхний левый** угол.
- `x` растёт **вправо**.
- `y` растёт **вниз**.

Никаких «y+ up» не бывает. Любое место, где pixel Y идёт вверх, —
баг.

## 2. Clip space (Y+ down, Z ∈ [0, 1])

Это то, что вершинный шейдер выдаёт в `gl_Position.xy / gl_Position.w`.
Используется единая Vulkan-native конвенция:

- `x = -1` — левый край viewport,
- `x = +1` — правый.
- `y = -1` — **верхний** край viewport,
- `y = +1` — **нижний**.
- `z = 0`  — near plane,
- `z = 1`  — far plane.

Любая проекционная матрица (`Mat44::perspective`, `Mat44::orthographic`,
`build_shadow_projection_matrix`, `build_ortho_pixel_to_ndc` в UI / Text2D
/ tcplot) **обязана** давать clip с этими свойствами. `(0, 0)`
пиксель ↔ `(-1, -1)` в clip.

Как backend это обеспечивает:

- **Vulkan** — нативное поведение: viewport `(y, height)` без
  отрицательной высоты, Z нормирован в `[0, 1]`. Никаких `VK_EXT_depth_clip_control`.
- **OpenGL** — вызывает `glClipControl(GL_UPPER_LEFT, GL_ZERO_TO_ONE)`
  один раз при создании устройства. После этого vertex output интерпретируется
  точно как в Vulkan.

## 3. Window-coordinate parameters (viewport / scissor)

Оба API (`set_viewport`, `set_scissor`) принимают **top-left origin**
пиксели (см. §1). Т.е. `y = 0` — верхний ряд.

Backend-адаптеры:

- **Vulkan** — `VkViewport.y = y, height = +h`; `VkRect2D.offset = (x, y)`.
  Без трюков.
- **OpenGL** — `glClipControl(GL_UPPER_LEFT)` меняет clip→window mapping
  (см. §2), но **не** трогает origin `glViewport` / `glScissor`. Эти
  функции продолжают ожидать bottom-left origin в window coordinates.
  Поэтому OpenGL backend вручную пересчитывает:
  ```
  gl_y = fb_height - (y + height)
  ```
  где `fb_height` — высота текущего render target (читается в
  `begin_render_pass` и кешируется в command list-е).

Как следствие: вызовы `set_viewport` / `set_scissor` в API слое
всегда передают один и тот же `(x, y, w, h)` на оба backend-а. Никаких
if-branch по backend-у в пользовательском коде.

## 3a. Scissor isolation between render passes

Vulkan хранит scissor/viewport как часть command buffer — `begin_pass`
поднимает чистый набор, закрытие pass очищает. В OpenGL это **глобальное
состояние**, переживающее pass'ы и кадры. Если один pass (например
`Canvas.begin_clip` в UI compose) оставил scissor включённым на
виджет-прямоугольнике, следующий pass (например GPU compositor) откроет
FBO и сделает `glClear` + draw, обрезанные тем же старым rect'ом.

Поэтому `OpenGLCommandList::begin_render_pass` перед `glClear`
вызывает `glDisable(GL_SCISSOR_TEST)` — гарантирует, что каждый pass
стартует с чистым scissor'ом. Вызов `set_scissor` внутри pass-а
включает scissor заново, если нужно.

Бага-признак: «на OpenGL canvas обрезан сверху/снизу, на Vulkan всё
ок» — почти наверняка scissor leaked с предыдущего pass-а.

## 4. Texture memory / sampling

Контракт API: **`v = 0` — визуальный верх содержимого на обоих
backends**. Никакого `flip_v` снаружи бэкенда. Пользовательские
шейдеры и Python API (`UIRenderer.draw_texture`, `Viewport3D`,
`framegraph_debugger`, tcplot и т.д.) пишут Vulkan-style sampling и
получают одинаковую картинку.

Вулкан: memory row 0 — это натурально «визуальный верх» (как для
rendered, так и для uploaded текстур), и `texture(sam, vec2(u, 0))`
сэмплирует именно его. Никаких трюков в бэкенде не нужно.

OpenGL: нативный memory layout — bottom-up (row 0 = визуальный низ,
legacy OpenGL-invariant, не управляется `glClipControl`). Чтобы
API-контракт выглядел одинаково с Vulkan, `OpenGLRenderDevice`
применяет **два симметричных преобразования**, которые гасят друг
друга при парном upload+sample:

1. **Upload** (`upload_texture`, `upload_texture_region`) — CPU Y-flip
   строк перед `glTexSubImage2D`. Пользователь подаёт row 0 = top,
   в GL-памяти строка-верх оказывается на row `h-1`. Для region upload
   вдобавок пересчитывается `y` top-left → bottom-left.
2. **Sampling** — `OpenGLRenderDevice::create_shader` после общего
   preprocess инжектит GLSL overlay: перегрузки `_tgfx_gl_tex(...)` для
   sampler2D / sampler2DShadow и `#define texture _tgfx_gl_tex` /
   `#define texelFetch _tgfx_gl_texel`. В итоге любой `texture(s, uv)`
   превращается в `texture(s, vec2(uv.x, 1.0 - uv.y))`. Для прочих
   семплеров (sampler3D, samplerCube) — pass-through.

Для rendered RT на OpenGL: при rendering с `glClipControl(GL_UPPER_LEFT)`
«визуальный верх» оказывается в memory row `h-1` — и sampling-шейдерная
инверсия попадает прямиком туда. Симметрия с uploaded путём полная.

Как следствие: никакой `backend == "opengl"` проверки в юзер-коде. Если
где-то появляется такой branch — это регрессия, её место — внутри
`OpenGLRenderDevice` / `shader_preprocess` (или расширение overlay).

## 5. Projection matrices (scene cameras)

Для камер (perspective / orthographic, `termin-base/geom/mat44.hpp`):

- Конвенция координат наблюдателя (view-space): camera-up = `+Z`,
  camera-forward = `+Y`, camera-right = `+X`. **Это не меняется.**
- Projection кодирует: view-up `+Z` → clip `-Y` (потому что clip Y+
  идёт вниз, см. §2); forward `+Y` → clip `+Z` в `[0, 1]`.

Shadow-камера (`shadow_camera.cpp`) — отдельная конвенция (camera looks
along `-Z`, стандарт graphics), но projection в clip приводит к тем же
`-Y = top`, `Z ∈ [0, 1]`.

## 6. Пан / zoom в pixel space (tcplot, viewports)

Pan «cursor-follows-data»: drag мышью → точка под курсором остаётся
на месте. Math:

```
pixel_x = pa_x + (data_x - x_min) / span_x * pa_w        # growing x_data → growing pixel_x
pixel_y = pa_y + (y_max - data_y) / span_y * pa_h        # growing y_data → shrinking pixel_y
```

Соответственно:

```
dx_data = -dx_pixel / pa_w * span_x       # mouse right = data x increases from left edge
dy_data = +dy_pixel / pa_h * span_y       # mouse down  = data y increases (y goes down visually)
```

## 7. Что считать багом

- Проекция, кодирующая view-up в clip `+Y`, — баг.
- `glClipControl(GL_LOWER_LEFT)` или `GL_NEGATIVE_ONE_TO_ONE` где-то в
  коде — баг.
- `VkViewport.height < 0` — баг (GL-style Y-flip trick удалён).
- `(y + h) - framebuffer_h` в пользовательском коде (ручной Y-flip в API слое) — баг. Backend должен сам разобраться.
- Любой `if ctx.backend == "opengl"` / `if backend == "vulkan"` вне
  самого OpenGLRenderDevice / VulkanRenderDevice — баг. API
  одинаковый, backend сам разбирается.
- `flip_v=True` где-либо снаружи backend'а — баг.
- `uv.y = 1 - v` в пользовательских шейдерах как подхват OpenGL — баг.
  Это делает shader_preprocess внутри OpenGLRenderDevice.
- OpenGL `begin_render_pass` без `glDisable(GL_SCISSOR_TEST)` —
  утечка scissor state между pass'ами.
- NDC cube corner с `z = -1` (см. `compute_frustum_corners`) — баг;
  near plane теперь `z = 0`, `z = 1` остаётся far.
