# Layout и контейнеры

## HStack

Горизонтальная раскладка. Дети располагаются в строку слева направо.

| Поле | Описание |
|------|----------|
| `spacing` | Расстояние между детьми (px) |
| `alignment` | Вертикальное выравнивание: `top`, `center`, `bottom` |
| `justify` | Горизонтальное: `start`, `center`, `end` |

`child.stretch = True` — ребёнок растягивается по оставшейся ширине.

## VStack

Вертикальная раскладка. Дети располагаются в столбец сверху вниз.

| Поле | Описание |
|------|----------|
| `spacing` | Расстояние между детьми (px) |
| `alignment` | Горизонтальное выравнивание: `left`, `center`, `right` |
| `justify` | Вертикальное: `start`, `center`, `end` |

`child.stretch = True` — ребёнок растягивается по оставшейся высоте.

## GridLayout

Сетка с явным позиционированием по строкам и столбцам.

```python
grid = GridLayout(columns=3)
grid.add(widget_a, row=0, col=0)
grid.add(widget_b, row=0, col=1, col_span=2)
```

| Поле/метод | Описание |
|-----------|----------|
| `add(child, row, col, row_span=1, col_span=1)` | Разместить виджет |
| `clear()` | Очистить сетку |
| `set_column_stretch(col, stretch)` | Растяжение колонки |
| `set_row_stretch(row, stretch)` | Растяжение строки |
| `row_spacing`, `column_spacing` | Отступы между ячейками |
| `padding` | Внутренний отступ |

## Panel

Контейнер с фоном и паддингом. Основной строительный блок для секций интерфейса.

| Поле | Описание |
|------|----------|
| `padding` | Внутренний отступ |
| `background_color` | Цвет фона |
| `border_radius` | Скругление углов |
| `background_image` | Фоновое изображение |
| `background_tint` | Тонирование фонового изображения |

Дети раскладываются с учётом `anchor` / `offset` / `position_*`.

## ScrollArea

Скроллируемый контейнер. Обычно содержит один ребёнок с большим контентом.

| Поле | Описание |
|------|----------|
| `scroll_x`, `scroll_y` | Текущая позиция скролла |
| `scroll_speed` | Скорость скролла |
| `show_scrollbar` | Показывать полосу прокрутки |
| `scrollbar_width` | Ширина полосы |
| `scrollbar_color`, `scrollbar_hover_color` | Цвета полосы |

Wheel меняет `scroll_y`. Drag по scrollbar поддерживается из коробки.

## GroupBox

Сворачиваемая секция с заголовком.

| Поле | Описание |
|------|----------|
| `title` | Текст заголовка |
| `expanded` | Развёрнута ли секция |
| `title_height` | Высота заголовка |
| `content_padding` | Отступ содержимого |
| `spacing` | Расстояние между детьми |
| `on_toggle(expanded)` | Callback при сворачивании/разворачивании |

## Splitter

Перетаскиваемый разделитель для изменения размера соседней панели.

```python
splitter = Splitter(target=left_panel, side="right")
```

| Поле | Описание |
|------|----------|
| `target` | Виджет, размер которого меняется |
| `side` | Сторона: `left`, `right`, `top`, `bottom` |
| `color`, `hover_color` | Цвета разделителя |
| `bar_width` | Ширина полосы |

При drag меняет `target.preferred_width` или `target.preferred_height`.

## Пример

```python
layout = HStack()
layout.spacing = 8

left = Panel(); left.preferred_width = px(260)
right = Panel(); right.stretch = True

splitter = Splitter(target=left, side="right")
layout.add_child(left)
layout.add_child(splitter)
layout.add_child(right)
```
