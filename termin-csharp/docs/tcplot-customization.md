# tcplot — кастомизация графиков (C# / `PlotView2DMulti`)

Справочник по тому, что можно менять в рантайме через `Termin.Native.PlotView2DMulti` без пересборки нативной части. Все методы — обычные snake_case из SWIG-обёртки; при вызове применяются ко всем панелям сразу (broadcast-семантика).

---

## Сводная таблица

| Область | Метод | Параметры | Комментарий |
|---|---|---|---|
| Фон контрола | `set_bg_color` | r, g, b, a | За margin-зоной (весь контрол, не plot area) |
| Фон plot area | `set_plot_bg_color` | r, g, b, a | Прямоугольник, где рисуется сам график |
| Цвет сетки | `set_grid_color` | r, g, b, a | Линии grid и `show_grid` в PlotEngine2D |
| Цвет осей | `set_axis_color` | r, g, b, a | Рамка plot area + рисочки тиков |
| Цвет подписей | `set_label_color` | r, g, b, a | Тиковые цифры, x/y-label, дефолт заголовка |
| Цвет заголовка | `set_title_color` / `clear_title_color` | r, g, b, a | Override. Без вызова = `label_color` |
| Цвет серии | `set_line_color` | panel_idx, series_idx, r, g, b, a | Смена цвета уже добавленной линии |
| Размер шрифтов | `set_font_size` | label_px, title_px | Подписи осей и заголовок |
| Отступ заголовка | `set_title_pad` | pad (px) | Зазор между низом заголовка и верхом plot area |
| Отступы панели | `set_panel_margins` | left, right, top, bottom (px) | Обрамление plot area внутри панели |
| Подпись X | `set_x_label` | текст | Общая для всех панелей |
| Подпись Y | `set_panel_y_label` | panel_idx, текст | Per-panel |
| Заголовок панели | `set_panel_title` | panel_idx, текст | Per-panel |

Все цветовые методы принимают `float` в диапазоне `0..1` (premultiplied alpha не требуется; блендинг стандартный).

---

## Типовые сценарии

### Фоны и цвета — смена темы одним блоком

```csharp
// Dark theme
View.set_bg_color(0.12f, 0.12f, 0.14f, 1f);
View.set_plot_bg_color(0.16f, 0.16f, 0.18f, 1f);
View.set_grid_color(0.25f, 0.25f, 0.28f, 1f);
View.set_axis_color(0.55f, 0.55f, 0.58f, 1f);
View.set_label_color(0.85f, 0.85f, 0.88f, 1f);
View.set_title_color(1f, 1f, 1f, 1f);
```

```csharp
// Light theme
View.set_bg_color(0.98f, 0.98f, 0.98f, 1f);
View.set_plot_bg_color(1f, 1f, 1f, 1f);
View.set_grid_color(0.88f, 0.88f, 0.88f, 1f);
View.set_axis_color(0.35f, 0.35f, 0.35f, 1f);
View.set_label_color(0.15f, 0.15f, 0.15f, 1f);
View.clear_title_color();   // вернуться к label_color
```

### Цвет серии: перекрашивание без пересоздания

Раньше, чтобы перекрасить уже добавленную линию, нужно было `clear()` и `add_line` заново — теряли данные и GPU-буфер. Теперь:

```csharp
// Подсветить канал S красным при срабатывании триггера:
View.set_line_color(panel_idx: 0, series_idx: 0, 1f, 0.2f, 0.2f, 1f);

// Вернуть дефолтный синий:
View.set_line_color(0, 0, 0.2f, 0.6f, 1f, 1f);
```

`panel_idx` — индекс панели (0..N), `series_idx` — индекс серии внутри панели в порядке `add_line`. Индексы вне диапазона — тихий no-op.

### Шрифты и отступы

```csharp
View.set_font_size(label_px: 13f, title_px: 18f);  // всё во всех панелях
View.set_title_pad(4f);                             // зазор под заголовком
View.set_panel_margins(left: 70, right: 15, top: 40, bottom: 50);
```

Маржи — целочисленные пиксели, задают место для тиков/подписей/заголовка внутри панели. Если заголовок не влезает в `top` — обрезается сверху; бампните `top` до `line_height(title_px) + title_pad + 2`.

### Подписи осей

```csharp
View.set_x_label("Time, ms");
View.set_panel_title(0, "Сигнал S");
View.set_panel_y_label(0, "В");
View.set_panel_title(1, "FFT: Сигнал S");
View.set_panel_y_label(1, "В²/Гц");
```

X-подпись одна на весь `PlotView2DMulti` (общая ось X между панелями). Заголовок и Y-подпись — per-panel.

---

## Чего **нет** в публичном API (на будущее)

Если понадобится — это всё не прокинуто наружу, нужны правки в `termin-csharp/termin.i`:

- Отдельный размер тиковых цифр (сейчас жёстко `label_px - 2`).
- Легенда с лейблами серий (label у серии есть, но нигде не рендерится).
- Dash / dotted стили линий.
- Log-шкалы по Y.
- Per-panel разные цвета сетки/осей (сейчас broadcast на все).
- Toggle видимости рамки plot area (сейчас всегда рисуется).

---

## Дефолты (откуда стартуем)

Из `tcplot::styles` (`tcplot/src/styles.cpp`). Если нужны точные RGB — подсмотреть там. В двух словах:

- `bg_color`, `plot_bg_color` — тёмно-серые (под «dashboard» тему).
- `grid_color` — полупрозрачная серая.
- `axis_color`, `label_color` — светло-серые.
- `font_size = 15`, `title_font_size = 22`, `title_pad = 4`.
- `margin_left/right/top/bottom = 76/15/44/52`.

Любой из этих дефолтов перекрывается соответствующим `set_*` сразу после создания `PlotView2DMulti`.
