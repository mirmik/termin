# tcplot — кастомизация графиков (C# / `PlotView2DMulti`)

Справочник по основным runtime-настройкам `Termin.Native.PlotView2DMulti` без пересборки нативной части. Методы ниже — обычные snake_case из SWIG-обёртки; styling-вызовы применяются ко всем панелям сразу (broadcast-семантика).

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
| Линия по scalar-цвету | `plot_colormap` / `add_line_colormap` | x, y, scalar, n, colormap, min, max, thickness, label | Для маршрутов: XY-линия, цвет кодирует третью величину |
| Инверсия colormap | `colormap_reversed` / `set_line_colormap_reversed` | bool или panel_idx+series_idx+bool | Меняет направление шкалы; например инвертированный `Jet` |
| Пунктир / точки | `set_line_style` | series_idx или panel_idx+series_idx, `LineStyle`, dash_px, gap_px | Длина штриха и пробела задаётся в экранных пикселях |
| Маркеры-точки | `scatter` / `add_scatter` | x, y, n, r, g, b, a, size, label | Scatter рисуется кругами; удобно для старт/финиш |
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

### Маршрут: цвет по высоте, пунктир и круглые маркеры

Для одиночного графика (`PlotView2D`) можно построить XY-маршрут и закодировать
высоту/скорость/ошибку отдельным scalar-массивом той же длины:

```csharp
View.plot_colormap(x, y, z, (uint)x.Length,
    SurfaceColorMap.Viridis,
    zMin, zMax,
    thickness: 3.0,
    label: "True trajectory",
    colormap_reversed: false);

View.plot(navX, navY, (uint)navX.Length,
    0.0f, 0.47f, 0.83f, 1.0f,
    thickness: 2.0,
    label: "Navigation");
View.set_line_style(1, LineStyle.Dash, dash_px: 10.0f, gap_px: 6.0f);

View.scatter(new[] { x[0] }, new[] { y[0] }, 1,
    0.0f, 1.0f, 0.0f, 1.0f,
    size: 10.0,
    label: "Start");
View.scatter(new[] { x[^1] }, new[] { y[^1] }, 1,
    1.0f, 0.0f, 0.0f, 1.0f,
    size: 10.0,
    label: "Finish");
```

В `PlotView2DMulti` те же операции называются `add_line_colormap`,
`add_scatter` и `set_line_style(panel_idx, series_idx, ...)`.

Для инвертированной шкалы можно передать `colormap_reversed: true` при создании серии.
Например, инвертированный Jet для высоты:

```csharp
View.plot_colormap(x, y, z, (uint)x.Length,
    SurfaceColorMap.Jet,
    zMin, zMax,
    thickness: 3.0,
    label: "Altitude",
    colormap_reversed: true);
```

У уже добавленной серии направление шкалы меняется без пересоздания данных:

```csharp
View.set_line_colormap_reversed(series_idx: 0, reversed: true);
// PlotView2DMulti:
View.set_line_colormap_reversed(panel_idx: 0, series_idx: 0, reversed: true);
```

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

## WPF/D3D11 host

Старый вывод напрямую в GL framebuffer через `render(width, height, dst_gl_fbo)`
удален из текущего C# API. `PlotView2D` и `PlotView2DMulti` рендерят в tgfx2
texture handle через `render_to_texture_handle_id(width, height)`, а показ выполняет
platform host `Termin.Wpf.Tgfx2D3D11SwapchainHost`.

Минимальный render tick:

```csharp
int width = Math.Max(1, RenderHost.FramebufferWidth);
int height = Math.Max(1, RenderHost.FramebufferHeight);
uint colorTex = View.render_to_texture_handle_id(width, height);
RenderHost.Present(colorTex, width, height);
```

Для `Tgfx2D3D11SwapchainHost` важно использовать `FramebufferWidth` и
`FramebufferHeight`, а не WPF `ActualWidth` / `ActualHeight`: WPF размеры заданы
в DIPs, а native swapchain работает в физических пикселях. После render tick
передавайте tgfx2 texture handle в `RenderHost.Present(...)`.

Перед освобождением shared `Tgfx2Host` потребитель должен уничтожить swapchain
через `RenderHost.ReleaseNativeResources()`. Иначе `HwndHost` может удалить
native swapchain уже после уничтожения D3D11 device.

---

## Чего **нет** в публичном API (на будущее)

Если понадобится — это всё не прокинуто наружу, нужны правки в `termin-csharp/termin.i`:

- Отдельный размер тиковых цифр (сейчас жёстко `label_px - 2`).
- Легенда с лейблами серий (label у серии есть, но нигде не рендерится).
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

