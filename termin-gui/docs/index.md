# termin-gui

`termin-gui` — Python UI-фреймворк на виджетах для движка Termin.

Immediate-mode рендеринг через OpenGL, retained-mode дерево виджетов.
Документация отражает текущую реализацию в `python/tcgui/widgets/*` и примеры из `examples/*`.

## Рекомендуемый маршрут

| #  | Раздел | Описание |
|----|--------|----------|
| 1  | [Быстрый старт](getting-started.md) | Минимальный пример: UI, дерево виджетов, рендер |
| 2  | [Core API](core-api.md) | Widget, UI, Units, Events, Theme, Loader |
| 3  | [Layout и контейнеры](widgets-layout.md) | HStack, VStack, GridLayout, Panel, ScrollArea, Splitter |
| 4  | [Базовые контролы](widgets-basic.md) | Button, Label, Checkbox, ProgressBar и др. |
| 5  | [Ввод и редактирование](widgets-input.md) | TextInput, Slider, SpinBox, ComboBox |
| 6  | [Данные и навигация](widgets-data-nav.md) | TreeWidget, TableWidget, Tabs, MenuBar |
| 7  | [Диалоги и overlay](widgets-dialogs.md) | Dialog, MessageBox, file dialogs |
| 8  | [Canvas и Viewport3D](widgets-canvas-viewport.md) | 2D-канвас и 3D-viewport |

## Пакетные точки входа

```python
from tcgui import *                          # полный публичный API
from tcgui.widgets.basic import ...          # базовые контролы
from tcgui.widgets.containers import ...     # контейнеры
```

## Что считать публичным API

- Классы и функции, экспортируемые через `tcgui.widgets.__all__`.
- Публичные поля и callbacks, используемые в примерах.
- Публичные методы (без `_` в начале), доступные для прикладного кода.
