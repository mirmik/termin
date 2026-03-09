# Базовые контролы

## Label

Текстовая метка.

| Поле | Описание |
|------|----------|
| `text` | Текст |
| `color` | Цвет текста |
| `font_size` | Размер шрифта |
| `alignment` | Выравнивание: `left`, `center`, `right` |

## Button

Кнопка с текстом и/или иконкой.

| Поле | Описание |
|------|----------|
| `text` | Текст кнопки |
| `icon` | Иконка |
| `checkable` | Может ли быть toggle-кнопкой |
| `checked` | Состояние toggle |
| `on_click()` | Callback при нажатии |
| `background_color`, `hover_color`, `pressed_color` | Цвета состояний |
| `checked_color`, `text_color` | Цвет в checked-состоянии, цвет текста |

## Checkbox

Чекбокс с текстовой меткой.

| Поле | Описание |
|------|----------|
| `text` | Текст рядом с чекбоксом |
| `checked` | Текущее состояние |
| `box_size` | Размер квадрата |
| `font_size` | Размер текста |
| `spacing` | Расстояние между квадратом и текстом |
| `on_changed(checked)` | Callback при изменении |

## IconButton

Кнопка-иконка (без текста).

| Поле | Описание |
|------|----------|
| `icon` | Иконка |
| `active` | Подсвечена ли кнопка |
| `size` | Размер кнопки |
| `font_size` | Размер иконки |
| `tooltip` | Подсказка при наведении |
| `on_click()` | Callback при нажатии |

## Separator

Визуальный разделитель.

| Поле | Описание |
|------|----------|
| `orientation` | `vertical` или `horizontal` |
| `color` | Цвет линии |
| `thickness` | Толщина |
| `margin` | Отступ с краёв |

## ImageWidget

Виджет для отображения изображения.

| Поле | Описание |
|------|----------|
| `image_path` | Путь к изображению |
| `tint` | Тонирование |

Без `preferred_width/height` размер берётся из реальных размеров картинки.

## ProgressBar

Полоса прогресса.

| Поле | Описание |
|------|----------|
| `value` | Прогресс (0.0 .. 1.0) |
| `show_text` | Показывать процент текстом |
| `background_color`, `fill_color`, `text_color` | Цвета |

## FrameTimeGraph

График времени кадра (для отладки производительности).

| Поле/метод | Описание |
|-----------|----------|
| `add_frame(ms)` | Добавить значение кадра |
| `clear()` | Очистить график |
| `max_values` | Максимум значений на графике |

## Пример

```python
row = HStack(); row.spacing = 10

ok = Button(); ok.text = "OK"
ok.on_click = lambda: print("ok")

ch = Checkbox(); ch.text = "Enable"; ch.checked = True
ch.on_changed = lambda v: print("checkbox", v)

pb = ProgressBar(); pb.value = 0.42; pb.show_text = True

row.add_child(ok)
row.add_child(ch)
row.add_child(pb)
```
