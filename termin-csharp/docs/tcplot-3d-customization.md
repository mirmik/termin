# tcplot - кастомизация 3D графика (C# / `PlotView3D`)

Справочник по тому, что сейчас доступно из `Termin.Native.PlotView3D` для
3D-графиков в Alliance. Методы ниже - это SWIG C# API, поэтому имена остаются
в `snake_case`.

`PlotView3D` не владеет общим GPU runtime. В WPF-хосте нужно брать shared host
через `Tgfx2Host.Acquire(...)`, создавать `PlotView3D(host)`, а при dispose
вызывать `release_gpu()` и `Tgfx2Host.Release()`.

---

## Сводная таблица

| Область | Метод / тип | Параметры | Комментарий |
|---|---|---|---|
| Линия | `plot` | x, y, z, n, r, g, b, a, thickness, label | 3D polyline |
| Точки | `scatter` | x, y, z, n, r, g, b, a, size, label | Маркеры в 3D |
| Поверхность | `surface` | X, Y, Z, rows, cols, r, g, b, a, wireframe, label | Дефолтная схема `Jet` для заполненной поверхности |
| Поверхность с colormap | `surface_colormap` | X, Y, Z, rows, cols, colormap, r, g, b, a, wireframe, label | Основной способ задавать цветовую схему surface |
| Colormap поверхности | `SurfaceColorMap` | `Jet`, `Viridis`, `Plasma`, `Grayscale`, `CoolWarm`, `Solid` | Enum из `Termin.Native` |
| Смена colormap | `set_surface_colormap` | surface_idx, colormap | Меняет уже добавленную surface-серию |
| Инверсия colormap | `colormap_reversed` / `set_surface_colormap_reversed` | bool или surface_idx+bool | Меняет направление шкалы; например инвертированный `Jet` |
| Смена цвета surface | `set_surface_color` | surface_idx, r, g, b, a | RGB нужен для `Solid`; alpha работает для всех схем |
| Data grid поверх surface | `set_surface_grid` | surface_idx, visible, row_step, col_step, r, g, b, a, width_px | Shader-side сетка по данным без полного wireframe |
| Очистка данных | `clear` | - | Удаляет все серии |
| Подписи осей | `set_axis_labels` | x_label, y_label, z_label | Рисуются около положительных концов осей |
| Подпись X/Y/Z | `set_x_label` / `set_y_label` / `set_z_label` | label | Можно менять по отдельности |
| Заголовок | `set_title` | title | Хранится в данных; 3D C# view сейчас не рисует title overlay сам |
| Камера | `fit_camera` | - | Подогнать камеру под текущие данные |
| Масштаб осей | `set_axis_scale` | x, y, z | Nonuniform visual scale без изменения данных |
| Масштаб Z | `set_z_scale` / `get_z_scale` | scale | Совместимый короткий путь для вертикального масштаба |
| Рельефное shading | `set_surface_shading` | enabled, strength | Shader-side hillshade для читаемости ландшафта |
| Направление света | `set_surface_light_dir` | x, y, z | Направление нормализуется внутри |
| MSAA | `set_msaa_samples` / `msaa_samples` | samples | Обычно 1, 2, 4, 8 |
| Interaction | `on_mouse_down`, `on_mouse_move`, `on_mouse_up`, `on_mouse_wheel` | координаты мыши + button/dy | Для WPF/OpenTK host |
| Picking | `pick` | mx, my, out x/y/z/screen_dist | Поиск ближайшей точки/маркера |
| GPU cleanup | `release_gpu` | - | Вызывать перед dispose/потерей GL контекста |

Все цвета принимаются как `float` в диапазоне `0..1`.

---

## Поверхности и цветовые схемы

Главное правило: цвета colormap не пишутся в mesh. Для заполненных surface
раскраска считается в shader по нормализованной координате Z. Это важно:
запекание цветов в вершины mesh давало артефакты на поверхности.

```csharp
using Termin.Native;

View.surface_colormap(
    X, Y, Z,
    rows, cols,
    SurfaceColorMap.Viridis,
    0f, 0f, 0f, 1f,
    wireframe: false,
    label: "surface",
    colormap_reversed: false);
```

Для `Jet`, `Viridis`, `Plasma`, `Grayscale`, `CoolWarm` RGB из цветового
кортежа не используется. Alpha используется и задает прозрачность surface.

Для `Solid` RGB используется напрямую:

```csharp
View.surface_colormap(
    X, Y, Z,
    rows, cols,
    SurfaceColorMap.Solid,
    0.1f, 0.55f, 1.0f, 0.85f,
    wireframe: false,
    label: "solid surface");
```

Старый `surface(...)` оставлен как короткий путь и использует `Jet`.

Для инвертированной шкалы передайте `colormap_reversed: true`. Например, инвертированный `Jet`:

```csharp
View.surface_colormap(
    X, Y, Z,
    rows, cols,
    SurfaceColorMap.Jet,
    0f, 0f, 0f, 1f,
    wireframe: false,
    label: "surface",
    colormap_reversed: true);
```

---

## Wireframe

Wireframe-режим строит линейную сетку по тем же X/Y/Z данным:

```csharp
View.surface(
    X, Y, Z,
    rows, cols,
    0f, 0f, 0f, 1f,
    wireframe: true,
    label: "mesh");
```

Для wireframe используется переданный цвет линии. Colormap к wireframe не
применяется.

Полный wireframe быстро чернит плотные surfaces, потому что рисует ребра всех
треугольников. Для рабочих графиков обычно лучше использовать `set_surface_grid`
из следующего раздела.

---

## Data grid поверх surface

`set_surface_grid` включает разреженную сетку по данным. В отличие от полного
wireframe, она выбирает каждый N-й ряд/столбец, но выбранную линию проводит по
всем точкам этой строки/колонки. Поэтому ландшафт читается, а плотная surface
не превращается в черную заливку.

```csharp
View.surface_colormap(X, Y, Z, rows, cols,
                      SurfaceColorMap.Viridis,
                      0f, 0f, 0f, 1f,
                      wireframe: false,
                      label: "surface");

bool ok = View.set_surface_grid(
    surface_idx: 0,
    visible: true,
    row_step: 8,
    col_step: 8,
    r: 0.05f, g: 0.05f, b: 0.05f, a: 0.85f,
    width_px: 2.0f);
```

`row_step` и `col_step` меньше 1 автоматически зажимаются до 1. Первая и
последняя строка/колонка всегда включаются, чтобы у поверхности был контур.
Метод возвращает `false`, если `surface_idx` вне диапазона.

Сетка рисуется прямо в fragment shader основного surface pass по
интерполированным индексам строки/колонки. Поэтому она проходит тот же depth
test, что и surface, не требует отдельного line mesh и поддерживает толщину
`width_px` в экранных пикселях. Это намеренно не triangle wireframe и не меняет
исходные X/Y/Z данные поверхности.

---

## Рельефное shading

Для surface доступен простой shader-side hillshade. Это не PBR и не объекты
света: normal считается во fragment shader через derivatives от scaled
позиции, а цвет colormap слегка умножается на мягкий коэффициент освещения.

```csharp
View.set_surface_shading(true, strength: 0.35f);
View.set_surface_light_dir(-0.4f, -0.6f, 0.7f);
```

`strength` зажимается в диапазон `0..1`. Практичный диапазон для графиков:
`0.2..0.45`. Больше может начать искажать восприятие colormap.

Shading учитывает `set_axis_scale`, поэтому рельеф соответствует видимой форме,
а не сырым единицам данных.

---

## Смена стиля после добавления surface

Индексы surface идут в порядке добавления surface-серий, начиная с 0.
`set_surface_colormap` и `set_surface_color` возвращают `false`, если индекс
вне диапазона.

```csharp
bool ok = View.set_surface_colormap(0, SurfaceColorMap.CoolWarm);
if (!ok)
{
    // В приложении лучше залогировать ситуацию: surface с таким индексом нет.
}

View.set_surface_color(0, 0.2f, 0.8f, 0.3f, 1f);
View.set_surface_colormap(0, SurfaceColorMap.Solid);
View.set_surface_colormap_reversed(0, true);
```

После смены стиля engine помечает данные dirty и перестроит GPU mesh при
следующем render.

---

## Камера, масштаб и MSAA

После наполнения графика обычно нужно вызвать `fit_camera()`:

```csharp
View.set_axis_scale(1.0f, 1.0e6f, 5.0f);
View.set_msaa_samples(8);

// add plot/scatter/surface...

View.fit_camera();
```

`set_axis_scale` меняет только визуальный масштаб осей. Исходные X/Y/Z данные
не меняются, picking возвращает исходные координаты. Это удобно, когда одна
ось задана в микросекундах/секундах или в другой размерности и график визуально
схлопывается в плоскость.

Пример: если время в секундах имеет диапазон порядка микросекунд, можно
растянуть временную ось только для отображения:

```csharp
View.set_axis_scale(1.0e6f, 1.0f, 1.0f); // X: seconds -> microseconds visually
View.fit_camera();
```

`set_z_scale` оставлен для совместимости и меняет только Z-компонент scale.

---

## Подписи осей

Названия осей рисуются через `Text3DRenderer` рядом с положительными концами
осей. Позиции считаются с учетом `set_axis_scale`, сами тексты остаются в
единицах исходных данных.

```csharp
View.set_axis_labels("Time, us", "Frequency, Hz", "Amplitude");

// Или по отдельности:
View.set_x_label("Time, us");
View.set_y_label("Frequency, Hz");
View.set_z_label("Amplitude");
```

Числовые tick labels продолжают показывать исходные значения данных, а не
умноженные на visual scale значения.

`set_msaa_samples` задается на view. Практичные значения: `1`, `2`, `4`, `8`.
Чем выше значение, тем дороже рендер.

---

## WPF/OpenTK host

Старый вывод напрямую в GL framebuffer удален. C# view вызывает
`render_to_texture_id(width, height)`, а показ выполняет platform helper из
`Termin.Wpf`, который принимает tgfx2 texture handle id и композитит его через
interop/present слой. GL plumbing не должен находиться в `PlotView*` или в
прикладных controls.

Mouse events надо пробросить в view:

```csharp
view.on_mouse_down((float)p.X, (float)p.Y, button);
view.on_mouse_move((float)p.X, (float)p.Y);
view.on_mouse_up((float)p.X, (float)p.Y, button);
view.on_mouse_wheel((float)p.X, (float)p.Y, dy);
```

Коды button совпадают с `tcbase::MouseButton`:

| Кнопка | Значение |
|---|---:|
| Left | 0 |
| Right | 1 |
| Middle | 2 |

При уничтожении контрола:

```csharp
view.release_gpu();
view.Dispose();
Tgfx2Host.Release();
```

---

## Picking

`pick` возвращает `true`, если удалось найти ближайшую точку/маркер:

```csharp
if (View.pick(mx, my,
              out double x,
              out double y,
              out double z,
              out double screenDistPx))
{
    // x/y/z - координаты найденной точки, screenDistPx - расстояние в пикселях.
}
```

Picking сейчас стоит рассматривать как инструмент для точек/маркеров. Для
полноценного выбора треугольника surface публичного API пока нет.

---

## Чего нет в публичном API

- Отдельных цветов фона, сетки, осей и подписей для `PlotView3D`, как у 2D API.
- Легенды и рендера `label` для 3D-серий.
- Кастомных пользовательских colormap через массив control points.
- Настройки материала surface: lighting, specular, нормали, shading mode.
- Отдельного API для толщины wireframe-линий.
- Публичного API для выбора/подсветки отдельных surface-треугольников.

Если это понадобится в Alliance, править надо не только C# слой, но и
`tcplot`/shader-side часть.
