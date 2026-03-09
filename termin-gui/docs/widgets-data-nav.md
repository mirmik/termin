# Данные и навигация

## ListWidget

Список элементов с выделением.

| Поле/метод | Описание |
|-----------|----------|
| `set_items(items)` | Задать список (`list[dict]`) |
| `items` | Текущие элементы |
| `selected_item` | Выделенный элемент |
| `selected_index` | Индекс выделенного |
| `on_select(index, item)` | Callback при выделении |
| `on_activate(index, item)` | Callback при double click |
| `on_context_menu(index, item, x, y)` | Callback при правом клике |

Формат `item`: `{"text": ..., "subtitle": ..., "data": ...}`.

## TableWidget

Таблица с колонками, выделением и drag-resize заголовков.

| Поле/метод | Описание |
|-----------|----------|
| `set_columns(columns)` | Задать колонки (`list[TableColumn]`) |
| `set_rows(rows, data=None)` | Задать строки |
| `selected_data` | Данные выделенной строки |
| `selected_index` | Индекс выделенной строки |
| `on_select(index, data)` | Callback при выделении |
| `on_activate(index, data)` | Callback при double click |

`TableColumn(header, width=0, min_width=40)` — `width=0` означает stretch-колонку.

## TreeWidget / TreeNode

Дерево с раскрывающимися узлами, drag-and-drop и контекстным меню.

**TreeNode:**

| Поле/метод | Описание |
|-----------|----------|
| `content` | Отображаемый текст |
| `subnodes` | Дочерние узлы |
| `expanded` | Развёрнут ли узел |
| `data` | Произвольные данные |
| `has_subnodes` | Показывать стрелку раскрытия |
| `add_node(node)`, `remove_node(node)` | Управление детьми |
| `toggle()` | Переключить expanded |

**TreeWidget:**

| Поле/метод | Описание |
|-----------|----------|
| `add_root(node)`, `remove_root(node)`, `clear()` | Управление корнями |
| `selected_node` | Выделенный узел |
| `draggable` | Включить drag-and-drop |
| `row_height`, `indent_size` | Настройки отображения |
| `on_select(node)` | Callback при выделении |
| `on_activate(node)` | Callback при double click |
| `on_expand(node)`, `on_collapse(node)` | Callback при раскрытии/сворачивании |
| `on_drop(dragged, target, position)` | Callback при drop |
| `on_context_menu(node_or_none, x, y)` | Callback при правом клике |

`position` в `on_drop`: `"above"`, `"below"`, `"inside"`, `"root"`.

## Tabs

**TabBar** — полоса вкладок:

| Поле | Описание |
|------|----------|
| `tabs` | Список вкладок |
| `selected_index` | Индекс активной |
| `on_changed(index)` | Callback при переключении |

**TabView** — вкладки с контентом:

| Поле/метод | Описание |
|-----------|----------|
| `add_tab(title, content)` | Добавить вкладку |
| `remove_tab(index)` | Удалить вкладку |
| `selected_index` | Индекс активной (property) |
| `tab_position` | Положение: `top`, `bottom` |

## Menu / MenuBar

**MenuItem:**

```python
MenuItem(label, icon=None, shortcut=None, enabled=True, separator=False, on_click=None)
MenuItem.sep()  # разделитель
```

**Menu:**

| Поле/метод | Описание |
|-----------|----------|
| `items` | Список MenuItem |
| `add_item(item)` | Добавить пункт |
| `show(ui, x, y)` | Показать меню |

**MenuBar:**

| Метод | Описание |
|-------|----------|
| `add_menu(label, menu)` | Добавить меню в bar |
| `register_shortcuts(ui)` | Зарегистрировать shortcut всех пунктов |

## ToolBar / StatusBar

**ToolBar:**

| Метод | Описание |
|-------|----------|
| `add_action(...)` | Добавить кнопку действия |
| `add_separator()` | Добавить разделитель |
| `add_item(item)` | Добавить произвольный элемент |

**StatusBar:**

| Поле/метод | Описание |
|-----------|----------|
| `text` / `set_text(text)` | Текст статусной строки |
| `show_message(text, timeout_ms=3000)` | Временное сообщение |

## Пример

```python
menu = Menu()
menu.items = [
    MenuItem("Open", shortcut="Ctrl+O", on_click=lambda: print("open")),
    MenuItem.sep(),
    MenuItem("Quit", shortcut="Ctrl+Q", on_click=lambda: print("quit")),
]

bar = MenuBar()
bar.add_menu("File", menu)
bar.register_shortcuts(ui)
```
