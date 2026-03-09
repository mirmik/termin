# Ввод и редактирование

## TextInput (однострочный)

Однострочное текстовое поле ввода.

| Поле | Описание |
|------|----------|
| `text` | Текущий текст |
| `placeholder` | Текст-подсказка (при пустом поле) |
| `cursor_pos` | Позиция курсора |
| `read_only` | Только чтение |
| `on_changed(text)` | Callback при изменении текста |
| `on_submit(text)` | Callback при нажатии Enter |

Поддерживаемые клавиши: `Left/Right/Home/End`, `Backspace`, `Delete`, `Enter`.

## TextArea (многострочный)

Многострочное текстовое поле.

| Поле | Описание |
|------|----------|
| `text` | Текущий текст (property) |
| `placeholder` | Текст-подсказка |
| `max_lines` | Максимум строк |
| `read_only` | Только чтение |
| `word_wrap` | Перенос по словам |
| `line_height` | Высота строки |
| `show_scrollbar`, `scrollbar_width` | Полоса прокрутки |
| `on_changed(text)` | Callback при изменении |

Поддерживает multiline-редактирование, scroll wheel, cursor navigation.

## Slider

Ползунок для выбора числового значения.

| Поле | Описание |
|------|----------|
| `value` | Текущее значение |
| `min_value`, `max_value` | Диапазон |
| `step` | Шаг (`0` = continuous) |
| `on_changed(value)` | Callback при изменении |

## SpinBox

Числовое поле с кнопками +/-.

| Поле | Описание |
|------|----------|
| `value` | Текущее значение |
| `min_value`, `max_value` | Диапазон |
| `step` | Шаг изменения |
| `decimals` | Количество десятичных знаков |
| `on_changed(value)` | Callback при изменении |

## SliderEdit

Составной виджет: `Slider` + `SpinBox` с общей моделью значения.

| Поле | Описание |
|------|----------|
| `value`, `min_value`, `max_value`, `step`, `decimals` | Как у Slider/SpinBox |
| `spacing` | Расстояние между slider и spinbox |
| `spinbox_width` | Ширина SpinBox |
| `on_changed(value)` | Callback при изменении |

## ComboBox

Выпадающий список.

| Поле/метод | Описание |
|-----------|----------|
| `items` | Список элементов |
| `selected_index` | Индекс выбранного |
| `selected_text` | Текст выбранного (read-only) |
| `placeholder` | Текст при отсутствии выбора |
| `add_item(text)` | Добавить элемент |
| `clear()` | Очистить список |
| `item_count` | Количество элементов |
| `item_text(index)` | Текст элемента по индексу |
| `on_changed(index, text)` | Callback при выборе |

## Пример

```python
inp = TextInput()
inp.placeholder = "Name"
inp.on_submit = lambda text: print("submit", text)

slider = Slider()
slider.min_value = 0
slider.max_value = 100
slider.step = 5
slider.on_changed = lambda v: print(int(v))

combo = ComboBox()
combo.items = ["Draft", "Ready", "Archived"]
combo.selected_index = 0
combo.on_changed = lambda i, t: print(i, t)
```
