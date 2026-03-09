# Диалоги и overlay

## Overlay API (через UI)

```python
ui.show_overlay(widget, modal=False, dismiss_on_outside=True, on_dismiss=None)
ui.hide_overlay(widget)
```

Этим механизмом пользуются `Menu`, `ComboBox`, `Dialog`, file dialogs.

## Dialog

Базовый диалог с заголовком, содержимым и кнопками.

| Поле | Описание |
|------|----------|
| `title` | Заголовок |
| `content` | Виджет содержимого |
| `buttons` | Список кнопок |
| `default_button` | Кнопка по умолчанию (Enter) |
| `cancel_button` | Кнопка отмены (Escape) |
| `on_result` | Callback с результатом |
| `min_width` | Минимальная ширина |

Методы: `show(ui, windowed=False)`, `close()`.

Режимы:

- **Overlay** (`windowed=False`) — центрируется внутри текущего UI.
- **Windowed** (`windowed=True`) — использует `ui.create_window`, если задан.

## MessageBox

Готовые фабрики для типичных диалогов:

| Метод | Назначение |
|-------|-----------|
| `MessageBox.info(...)` | Информационное сообщение |
| `MessageBox.warning(...)` | Предупреждение |
| `MessageBox.error(...)` | Ошибка |
| `MessageBox.question(...)` | Вопрос с вариантами ответа |

Пресеты кнопок: `Buttons.OK`, `Buttons.OK_CANCEL`, `Buttons.YES_NO`, `Buttons.YES_NO_CANCEL`.

## Input Dialog

```python
show_input_dialog(ui, title, message, default="", on_result=callback)
```

Callback получает `str` при OK, `None` при Cancel.

## ColorDialog

```python
ColorDialog.pick_color(ui, initial=(r, g, b, a), show_alpha=True, on_result=callback)
```

Callback получает `(r, g, b, a)` или `None`.

## File dialogs

| Функция | Описание |
|---------|----------|
| `show_open_file_dialog(ui, on_result, ...)` | Открыть файл |
| `show_save_file_dialog(ui, on_result, ...)` | Сохранить файл |
| `show_open_directory_dialog(ui, on_result, ...)` | Выбрать директорию |

Общие параметры: `title`, `directory`, `filter_str`, `filetypes`, `windowed`.

`on_result` всегда получает `path: str | None`.

Формат фильтра: `"Images | *.png *.jpg;;All files | *.*"`

Helper: `parse_filter_string(filter_str)`.

## Пример

```python
from tcgui.widgets.message_box import MessageBox
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog

MessageBox.question(
    ui,
    "Confirm",
    "Delete selected item?",
    on_result=lambda btn: print("result", btn),
)

show_open_file_dialog(
    ui,
    on_result=lambda path: print("picked", path),
    filter_str="Images | *.png *.jpg;;All files | *.*",
)
```
