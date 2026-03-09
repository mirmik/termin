# termin-gui

Python UI-фреймворк на виджетах для движка **Termin**.

Immediate-mode рендеринг через OpenGL, retained-mode дерево виджетов.
Используется как основной UI для редактора и инструментов Termin.

## Возможности

- **Layout-контейнеры** — `HStack`, `VStack`, `GridLayout`, `Panel`, `ScrollArea`, `GroupBox`, `Splitter`.
- **Базовые контролы** — `Button`, `Label`, `Checkbox`, `Slider`, `SpinBox`, `ComboBox`, `TextInput`, `TextArea`.
- **Данные и навигация** — `TreeWidget`, `TableWidget`, `ListWidget`, `TabView`, `MenuBar`, `ToolBar`.
- **Диалоги** — `Dialog`, `MessageBox`, `ColorDialog`, file dialogs, input dialogs.
- **Canvas и 3D** — `Canvas` (zoom/pan для изображений), `Viewport3D` (FBO-рендер 3D-сцены).
- **Темы** — встроенная тёмная тема, кастомизация через `Theme`.

## Быстрый старт

```python
from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label, Button
from tcgui.widgets.containers import Panel, VStack
from tcgui.widgets.units import pct, px

root = Panel()
root.preferred_width = pct(100)
root.preferred_height = pct(100)

stack = VStack()
stack.spacing = 12
stack.add_child(Label(text="Hello tcgui"))

btn = Button()
btn.text = "Click"
btn.on_click = lambda: print("clicked")
stack.add_child(btn)

root.add_child(stack)

ui = UI(graphics)
ui.root = root
```

## Документация

Документация собирается через MkDocs (GitHub Pages).

- Исходники: [`docs/`](docs/)
- Конфигурация: [`mkdocs.yml`](mkdocs.yml)

Локальный просмотр:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## Структура

```
python/tcgui/
  widgets/       # Все виджеты: basic, containers, input, dialogs, ...
  widgets/ui.py  # Корневой класс UI
examples/        # Примеры использования (sdl_hello.py и др.)
docs/            # Документация (MkDocs)
```
