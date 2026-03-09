# Core API

## Widget (базовый класс)

Все виджеты наследуются от `Widget`. Общие поля и методы описаны ниже.

### Иерархия и дерево

| Поле/метод | Описание |
|-----------|----------|
| `name` | Имя виджета (для поиска через `find`) |
| `parent` | Родительский виджет (read-only) |
| `children` | Список дочерних виджетов |
| `add_child(child)` | Добавить дочерний виджет |
| `remove_child(child)` | Удалить дочерний виджет |
| `find(name)` | Найти потомка по имени (первое совпадение) |
| `find_all(name)` | Найти всех потомков по имени |

### Размер и позиция

| Поле | Описание |
|------|----------|
| `preferred_width`, `preferred_height` | Желаемый размер (принимает `px(N)`, `pct(N)`, `ndc(N)`) |
| `x`, `y` | Вычисленная позиция (после layout) |
| `width`, `height` | Вычисленный размер (после layout) |
| `anchor` | Якорь позиционирования |
| `offset_x`, `offset_y` | Смещение от якоря |
| `position_x`, `position_y` | Абсолютная позиция (если задана) |

### Состояние

| Поле | Описание |
|------|----------|
| `visible` | Видимость (`True` по умолчанию) |
| `enabled` | Активность (`True` по умолчанию) |
| `focusable` | Может ли получать фокус |
| `stretch` | Растягиваться в родительском контейнере |
| `clip` | Обрезать содержимое по границам |
| `mouse_transparent` | Пропускать события мыши |

### UX

| Поле | Описание |
|------|----------|
| `tooltip` | Текст подсказки при наведении |
| `cursor` | Имя курсора (`"pointer"`, `"text"`, ...) |
| `context_menu` | Контекстное меню (объект `Menu`) |

### Методы layout и рендеринга

- `compute_size(max_w, max_h)` — вычислить желаемый размер.
- `layout(x, y, w, h)` — расположить виджет и его детей.
- `render(renderer)` — отрисовать виджет.

### Event hooks

- `hit_test(x, y)` — попадает ли точка в виджет.
- `on_mouse_down(event)`, `on_mouse_up(event)`, `on_mouse_move(event)`, `on_mouse_wheel(event)`
- `on_key_down(event)`, `on_text_input(event)`
- `on_focus()`, `on_blur()`

---

## UI

Корневой объект, управляющий деревом виджетов, layout, рендерингом и вводом.

### Основные свойства

| Свойство | Описание |
|----------|----------|
| `root` | Корневой виджет дерева |
| `font` | Шрифт по умолчанию |
| `loader` | UILoader для загрузки из YAML |

### Layout и рендеринг

```python
ui.request_layout()             # пометить layout как dirty
ui.layout(viewport_w, viewport_h)
ui.render(viewport_w, viewport_h)  # layout + отрисовка
```

### Поиск виджетов

```python
widget = ui.find("my_button")
widgets = ui.find_all("item_*")
```

### Shortcuts

```python
ui.add_shortcut("Ctrl+S", on_save)
ui.add_shortcut_from_string("Ctrl+Shift+Z", on_redo)
ui.remove_shortcut("Ctrl+S")
```

### Overlays

```python
ui.show_overlay(widget, modal=False, dismiss_on_outside=True, on_dismiss=callback)
ui.hide_overlay(widget)
```

### Focus

```python
ui.set_focus(widget)   # установить фокус
ui.set_focus(None)     # снять фокус
```

### Input API

```python
ui.mouse_move(x, y)
ui.mouse_down(x, y, button, mods=0)
ui.mouse_up(x, y, button=MouseButton.LEFT, mods=0)
ui.mouse_wheel(dx, dy, x, y)
ui.key_down(key, mods=0)
ui.text_input(text)
```

### Deferred actions

```python
ui.defer(callback)       # выполнить callback после текущего цикла
ui.process_deferred()    # обработать очередь (вызывается автоматически)
```

### Интеграция с окном

| Callback | Описание |
|----------|----------|
| `on_cursor_changed(cursor_name)` | Курсор изменился |
| `create_window(title, w, h)` | Создать дочернее окно (для windowed-диалогов) |
| `close_window()` | Закрыть текущее окно |
| `on_empty()` | Дерево виджетов пустое |

---

## Units

| Функция | Описание | Пример |
|---------|----------|--------|
| `px(x)` | Абсолютные пиксели | `px(120)` |
| `ndc(x)` | Доля от опорного размера (0.0..1.0) | `ndc(0.5)` |
| `pct(x)` | Проценты (`pct(100) == ndc(1.0)`) | `pct(50)` |
| `Value.parse(s)` | Парсинг строки | `"120px"`, `"50%"`, `"0.25ndc"` |

---

## Events

| Класс | Поля |
|-------|------|
| `MouseEvent` | `x`, `y`, `button`, `mods` |
| `MouseWheelEvent` | `dx`, `dy`, `x`, `y` |
| `KeyEvent` | `key`, `mods` |
| `TextEvent` | `text` |

Для `MouseEvent` и `KeyEvent` есть удобные свойства: `.shift`, `.ctrl`, `.alt`.

---

## Theme

```python
theme = Theme.dark()          # встроенная тёмная тема
custom = theme.copy()         # создать копию для модификации
custom.apply_to(root_widget)  # применить к дереву
```

Глобальная переменная: `current_theme`.

Виджеты читают `current_theme` в `__init__`. Если меняете тему после создания виджетов, вызывайте `theme.apply_to(root)` или пересоздавайте дерево.

---

## Loader / Renderer

### UILoader

Загрузка дерева виджетов из YAML:

```python
loader = UILoader()
loader.register_type("MyWidget", MyWidget)
root = loader.load("ui/main.yaml")
root = loader.load_string(yaml_str)
```

### UIRenderer

Low-level рендеринг (используется виджетами внутри `render`):

- `draw_rect(x, y, w, h, color, border_radius=0)`
- `draw_text(text, x, y, color, font_size)`
- `draw_image(image, x, y, w, h, tint=None)`
- `draw_line(x1, y1, x2, y2, color, thickness=1)`
- `measure_text(text, font_size) -> (w, h)`
