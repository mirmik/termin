# Canvas и Viewport3D

## Canvas

Zoom/pan виджет для отображения RGBA numpy-изображений с overlay-слоем.

### Данные

| Метод | Описание |
|-------|----------|
| `set_image(np_rgba_or_none)` | Установить основное изображение |
| `set_overlay(np_rgba_or_none)` | Установить overlay (копирование) |
| `set_overlay_ref(np_rgba_or_none)` | Установить overlay (по ссылке) |
| `mark_overlay_dirty(x0, y0, x1, y1)` | Пометить область overlay для обновления |

### Навигация

| Поле/метод | Описание |
|-----------|----------|
| `zoom` | Текущий масштаб (property) |
| `set_zoom(value, anchor_wx, anchor_wy)` | Установить масштаб с якорем |
| `fit_in_view()` | Вписать изображение в виджет |
| `center_on(ix, iy)` | Центрировать на точке изображения |
| `widget_to_image(wx, wy)` | Координаты виджета -> изображения |
| `image_to_widget(ix, iy)` | Координаты изображения -> виджета |
| `min_zoom`, `max_zoom`, `zoom_factor` | Ограничения масштаба |

### Callbacks

| Callback | Описание |
|----------|----------|
| `on_canvas_mouse_down(ix, iy, button, mods)` | Клик (в координатах изображения) |
| `on_canvas_mouse_move(ix, iy)` | Движение мыши |
| `on_canvas_mouse_up(ix, iy)` | Отпускание кнопки |
| `on_zoom_changed(zoom)` | Изменение масштаба |
| `on_render_overlay(canvas, renderer)` | Отрисовка поверх канваса |

### Управление

- Middle mouse drag = pan
- Wheel = zoom (вокруг курсора)

## Viewport3D

Виджет для отображения FBO-сцены из `termin`. Пересылает input в 3D input manager.

| Поле/метод | Описание |
|-----------|----------|
| `set_surface(surface, display=None)` | Подключить FBO-поверхность |
| `on_before_resize(new_w, new_h)` | Callback перед resize |

Особенности:

- Получает цветовую текстуру FBO и blit-ит её в область виджета.
- При resize вызывает `surface.resize(new_w, new_h)`.
- Обрабатывает `on_mouse_*`, `on_key_down`, `on_key_up` как прокси в native input.

## Пример Canvas

```python
canvas = Canvas()
canvas.set_image(image_rgba)
canvas.fit_in_view()

canvas.on_canvas_mouse_down = lambda ix, iy, btn, mods: print(ix, iy)
canvas.on_zoom_changed = lambda z: print("zoom", z)
```
