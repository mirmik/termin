# Быстрый старт

Минимальный рабочий поток:

1. Создать `UI(graphics)`.
2. Собрать дерево виджетов.
3. Назначить `ui.root`.
4. Прокинуть события из платформы.
5. Рендерить `ui.render(viewport_w, viewport_h)` каждый кадр.

## Минимальный пример

```python
from tgfx import OpenGLGraphicsBackend
from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label, Button
from tcgui.widgets.containers import Panel, VStack
from tcgui.widgets.units import pct, px

# Инициализация графики
graphics = OpenGLGraphicsBackend.get_instance()
graphics.ensure_ready()

# Дерево виджетов
root = Panel()
root.preferred_width = pct(100)
root.preferred_height = pct(100)
root.padding = 24

stack = VStack()
stack.spacing = 12

label = Label()
label.text = "Hello tcgui"

button = Button()
button.text = "Click"
button.preferred_width = px(120)
button.on_click = lambda: print("clicked")

stack.add_child(label)
stack.add_child(button)
root.add_child(stack)

# Создание UI
ui = UI(graphics)
ui.root = root

# В цикле кадра:
# ui.render(width, height)
```

## События, которые нужно прокинуть из платформы

| Метод | Описание |
|-------|----------|
| `ui.mouse_move(x, y)` | Движение мыши |
| `ui.mouse_down(x, y, button, mods=0)` | Нажатие кнопки мыши |
| `ui.mouse_up(x, y, button, mods=0)` | Отпускание кнопки мыши |
| `ui.mouse_wheel(dx, dy, x, y)` | Прокрутка колеса |
| `ui.key_down(key, mods=0)` | Нажатие клавиши |
| `ui.text_input(text)` | Текстовый ввод (символы) |

Полный пример SDL-интеграции: `examples/sdl_hello.py`.

## Что дальше

- [Core API](core-api.md) — Widget, UI, Units, Events, Theme.
- [Layout и контейнеры](widgets-layout.md) — как раскладывать виджеты.
- [Базовые контролы](widgets-basic.md) — кнопки, чекбоксы, лейблы.
