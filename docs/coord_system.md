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

## 4. Texture memory / sampling

Любая render target текстура:

- Vulkan memory: row 0 = визуальный верх содержимого (native).
- OpenGL memory: row 0 = визуальный **низ** содержимого (bottom-up
  legacy, неизменно даже с `glClipControl`).

Это единственная точка, где backends реально расходятся: `glClipControl`
не правит это, потому что memory layout определяется FBO, а не
rasterization-трансформацией.

Семплирование `texture(sampler, vec2(u, v))`:

- Vulkan: `v = 0` → верх содержимого.
- OpenGL: `v = 0` → низ содержимого (из-за bottom-up memory). Чтобы
  попасть в «верх», надо сэмплировать `1 - v`.

Практическое правило для компонентов, которые выбирают UV:

- **Texture из CPU** (шрифты, загруженные картинки, upload из numpy) —
  row 0 = top of image by convention. Семплирование `v=0` на Vulkan
  отдаёт top, на OpenGL — bottom. Если компоненту нужен «визуальный
  top при `v=0`», он обязан инвертировать V сам на OpenGL.
- **Rendered RT** (FBO / offscreen color attachment) — семплирование
  тех же координат сдвинуто по той же причине.

API контракт: любой композитор / семплинг должен спрашивать у
`Tgfx2Context.backend` и решать, нужен ли `flip_v`. Один хелпер —
`needs_sampling_flip = (ctx.backend == "opengl")`, и дальше всё через
него.

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
- `glClipControl(GL_LOWER_LEFT)` где-то в коде — баг.
- `VkViewport.height < 0` — баг (GL-style Y-flip trick удалён).
- `(y + h) - framebuffer_h` в пользовательском коде (ручной Y-flip в API слое) — баг. Backend должен сам разобраться.
- Отсутствие `flip_v` при семплировании rendered RT на OpenGL —
  будет давать перевёрнутую картинку.
- `uv.y` хардкод без учёта backend-а при сэмплинге rendered texture —
  баг.
