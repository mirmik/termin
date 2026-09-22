# tcplot - кастомизация 3D графика (C#)

> `PlotView3D` ниже остаётся legacy facade. Для нового WPF-кода используйте
> `RetainedChart3D`: stable `SurfaceItemRef3D` / `ScatterItemRef3D`, заменяемую
> grid part, `SetData` без замены handle, axis-scale-aware `Camera.Fit()` /
> `Camera.Reset()`, `MsaaSamples` и `RetainedChart3DHost` с обычными WPF
> controls поверх изображения. Полный пример находится в
> `examples/RetainedChart3DWpfExample`.

## Retained API для нового кода

```csharp
using var chart = new RetainedChart3D(host)
{
    MsaaSamples = 4,
};
chart.SetAxisScale(1, 1, 2.5f);

SurfaceItemRef3D surface = chart.Scene.AddSurface(
    x, y, z, rows, columns,
    new SurfaceItemStyle3D(
        colorMap: PlotColorMap3D.Viridis,
        surfaceGridVisible: true,
        surfaceGridRowStep: 8,
        surfaceGridColumnStep: 8,
        surfaceGridR: 0.8f,
        surfaceGridG: 0.9f,
        surfaceGridB: 1.0f,
        surfaceGridA: 0.6f));

// Меняет geometry revision, но сохраняет handle и style.
surface.SetData(nextX, nextY, nextZ, rows, columns);
chart.Camera.Fit();   // сохраняет текущий azimuth/elevation
chart.Camera.Reset(); // также возвращает каноническую ориентацию

// A colorbar is tied to the live surface item and follows its colormap.
chart.ShowColorBar(surface, "amplitude", new ColorBarStyle3D(
    tickCount: 7,
    widthPx: 20,
    textSizePx: 12));
// chart.HideColorBar();
```

`SetData` не двигает камеру автоматически: streaming и смена выбранного кадра
не должны неожиданно сбрасывать пользовательский ракурс. Если новые bounds
нужно вписать, потребитель вызывает `Camera.Fit()` явно.

`RetainedChart3DHost` работает on-demand по умолчанию. Первый attach,
resize/DPI, возврат из `Collapsed` и camera input сами запрашивают кадр. После
изменения данных, стиля, камеры или остальных настроек chart из C# кадр
запрашивает consumer. `SetAxisDisplayOffset`, `SetAxisTickLabel` и
`ClearAxisTickLabels` сами вызывают `RenderInvalidated`, на который подписан
host; для них дополнительный `RequestRender()` не нужен. Уведомление синхронное,
поэтому прикреплённый к WPF график следует изменять на UI-потоке host:

```csharp
ChartHost.Attach(chart);

surface.SetData(nextX, nextY, nextZ, rows, columns);
chart.Camera.Fit();
ChartHost.RequestRender();
```

Для настоящей непрерывной анимации можно установить
`ChartHost.ContinuousRendering = true`. Статические surface-графики не должны
включать этот режим: без mutation host сохраняет последний `D3DImage` и не
выполняет native render/present на каждом WPF composition frame.

## Отображаемые значения осей и colorbar

`SetAxisDisplayOffset(axis, offset)` меняет только числовые подписи по правилу
`displayValue = value + offset`. В декартовом графике доступны `PlotAxis3D.X`,
`Y`, `Z`; в сферическом — `PlotAxis3D.Radius`. Угловые подписи сохраняют градусы.
Colorbar поверхности использует настройки `Z` или `Radius` соответственно.
Отдельного смещения colorbar нет, поэтому его подписи согласованы с осью.

Смещение по умолчанию равно нулю. Геометрия, положения существующих делений,
нормировка цветов, visual scale, камера и исходные координаты остаются прежними.
Это настройка отображения; преобразование физических данных, например из м² в
dBsm, выполняет приложение. Offset не задаёт единицы автоматически: их нужно
указать в названии оси и colorbar.

```csharp
// Приложение уже вычислило radius = max(0, dBsm - floorDbsm).
const double floorDbsm = -40;
chart.SetAxisDisplayOffset(PlotAxis3D.Radius, floorDbsm);
chart.SetAxisLabels("azimuth", "polar", "dBsm");
chart.SetAxisTickLabel(PlotAxis3D.Radius, 0, "≤ −40");
chart.ShowColorBar(surface, "dBsm");

// Радиус 13.0103 отображается как −26.9897 (с точностью форматирования).
double offset = chart.GetAxisDisplayOffset(PlotAxis3D.Radius); // −40

// Удалить одно переопределение или все подписи оси, сохранив offset:
chart.SetAxisTickLabel(PlotAxis3D.Radius, 0, null);
chart.ClearAxisTickLabels(PlotAxis3D.Radius);

// На отдельном декартовом графике, например высоты относительно уровня 100:
cartesianChart.SetAxisDisplayOffset(PlotAxis3D.Z, -100);
```

`SetAxisTickLabel(axis, value, label)` привязывает текст к **исходному** значению,
до прибавления offset. `null` удаляет переопределение, пустая строка скрывает
текст. Значение добавляется к делениям в пределах показанного диапазона, даже
если автоматический выбор делений его пропустил. Например, подпись `≤ −40`
при `value = 0` появляется у нуля радиальной шкалы, но не заменяет нижнюю
границу colorbar поверхности с радиусами `[13, 20]`: ноль вне её диапазона.

Настройки принадлежат графику и сохраняются при `SetRadii`, `SetData`, замене
поверхности или сетки, а также повторном подключении colorbar. Offset и значения
переопределений должны быть конечными; ось чужой координатной системы отклоняется.

Для постоянной поверхности сохраняется настоящий цветовой диапазон `[value, value]`.
Colorbar становится однотонным, с одним числом `value + offset`; цвет берётся
из середины палитры. Это работает и для постоянной сферы: радиус 13.0103 и offset
−40 дают единственную подпись около −26.99 dBsm. Радиальная координатная сетка
при этом продолжает описывать расстояния от центра сферы.

## Сферическая поверхность и координатная сетка

`RetainedChart3D.CreateSpherical(host)` создаёт согласованный сферический график:
поверхности задаются радиусами, координатная сетка состоит из трёх больших
окружностей с угловыми делениями и радиальных шкал. Декартова клетка в этом
режиме не создаётся. Режим доступен через `chart.Coordinates` и не меняется
после создания графика.

Ориентацию угловой системы можно задать при создании. `polarAxis` определяет
направление полярного угла 0, а `zeroLongitude` — направление первого угла 0
в плоскости, перпендикулярной полярной оси. Termin нормализует направления и
ортогонализует `zeroLongitude`; параллельные направления отклоняются. Frame
одинаково применяется к поверхности, опорным окружностям, делениям и подписям,
но не поворачивает камеру и экранные элементы:

```csharp
var frame = new SphericalCoordinateFrame3D(
    polarAxisX: 0, polarAxisY: -1, polarAxisZ: 0,
    zeroLongitudeX: 1, zeroLongitudeY: 0, zeroLongitudeZ: 0);
using var chart = RetainedChart3D.CreateSpherical(host, frame);
```

Для этого frame локальная точка преобразуется как
`x = r sin(θ) cos(φ)`, `y = -r cos(θ)`, `z = r sin(θ) sin(φ)`.
Стандартный overload без frame сохраняет полярную ось `+Z` и нулевое
направление `+X`.

```csharp
using var chart = RetainedChart3D.CreateSpherical(host);
chart.MsaaSamples = 4;

// Столбцы — азимут вокруг +Z, строки — полярный угол от +Z.
// Все входные углы в радианах. Шаг может быть неравномерным.
double[] azimuths = { 0, Math.PI / 2, Math.PI, 3 * Math.PI / 2 };
double[] polarAngles = { 0, Math.PI / 2, Math.PI };
double[] radii = {
    1, 1, 1, 1,         // северный полюс
    1.2, 1.5, 1.1, 1.4, // экватор
    1, 1, 1, 1,         // южный полюс
};

SphericalSurfaceItemRef3D surface = chart.Scene.AddSphericalSurface(
    azimuths, polarAngles, radii,
    closeAzimuth: true,
    style: new SurfaceItemStyle3D(
        colorMap: PlotColorMap3D.Viridis,
        surfaceGridVisible: true,
        surfaceGridRowStep: 1,
        surfaceGridColumnStep: 1));

chart.ShowColorBar(surface, "radius");
chart.Camera.Fit(); // учитывает также сферическую координатную сетку
ChartHost.Attach(chart);

surface.SetRadii(nextRadii); // тот же размер таблицы, те же углы и handle
ChartHost.RequestRender();
```

Индекс радиуса: `row * azimuths.Length + column`. Оба массива углов должны
быть конечными и строго возрастающими; полярные углы лежат в `[0, π]`.
Для `closeAzimuth: true` нужны минимум три азимута с диапазоном меньше `2π`:
конечный дубликат первого столбца передавать не нужно, шов строится автоматически.
Для открытого сектора (`closeAzimuth: false`) нужны минимум два азимута,
диапазон может достигать `2π`. Полярных углов всегда нужно минимум два.
Радиусы конечные и неотрицательные. В строке полюса (`0` или `π`) все радиусы
должны совпадать: разные азимуты описывают одну точку.

Преобразование выполняется в native при изменении данных:
`x = r sin(θ) cos(φ)`, `y = r sin(θ) sin(φ)`, `z = r cos(θ)`.
Поверхностная сетка следует строкам и столбцам угловой таблицы. Colormap и
цветовая шкала используют радиус, а не высоту Z. `SetRadii` сохраняет стиль и
камеру; для подгонки под изменившийся размер явно вызывайте `Camera.Fit()`.
Некорректное обновление отклоняется, предыдущая поверхность сохраняется.

Сферическая поверхность и обычная поверхность имеют общую базу `SurfaceRef3D`
со свойством `Style`; `ShowColorBar` принимает обе. У сферической поверхности
доступен `SetRadii`, у декартовой — `SetData`. Вызов `AddSurface` в сферическом
графике или `AddSphericalSurface` в декартовом отклоняется.

`chart.Parts.Grid`, `Scene.AddGrid` и `Parts.ReplaceGrid` сохраняют обычный
retained API, но геометрия сетки всегда соответствует режиму графика. В
сферическом режиме `GridItemStyle3D.Grid*` задаёт цвета окружностей,
`XAxis*` — азимутальных делений, `YAxis*` — полярных, `ZAxis*` — радиальных
шкал. `LabelsVisible` включает подписи, угловые значения выводятся в градусах.
`SetAxisLabels(azimuth, polar, radius)` переименовывает соответствующие шкалы;
стандартные названия — `azimuth`, `polar`, `r`.

Для работы с данными без GPU допустимо `RetainedChart3D.CreateSpherical()`;
для отображения в WPF передавайте host от `Tgfx2Host.Acquire`.
Сферический вариант примера `examples/RetainedChart3DWpfExample` запускается
с аргументом `--spherical`. Кнопка `Advance wave` обновляет таблицу радиусов
без сброса ракурса. Аргумент `--smoke` проверяет отображение и обновление, после
чего закрывает окно с кодом завершения 0; ошибка возвращает ненулевой код.
Центральная проверка C# API и обоих WPF-режимов: `task test -- --csharp-only`
(после сборки Graphics SDK через
`task build:graphics -- --no-sdl --no-vulkan --no-opengl`). Для WPF-проверки
нужен Windows-сеанс с доступным D3D9Ex/D3DImage; ошибка создания bridge
завершает smoke с ошибкой, даже если offscreen-рендер D3D11 работает.

## Проверка в PlotDemoApp

В сферическом окне `examples/PlotDemoApp` доступны четыре набора: `Radius wave`,
ЭПР с диапазоном −40…+10 dBsm, постоянная ЭПР 0.002 м² и ЭПР с нулевыми радиусами.
Кнопка `Show geometry values` переключает подписи между физическими значениями
и исходными радиусами. При переключении поверхность, цвета и ракурс сохраняются.
`Replace surface + grid` позволяет проверить сохранение offset и переопределения
нулевой подписи при замене обоих объектов; `Advance wave` обновляет данные.

`task test -- --csharp-only` также запускает `PlotDemoApp --smoke-axis-display`.
Этот сценарий проверяет WPF-отображение и смену display-настроек, сохраняя кадры
в `build/logs/plot-demo-*.png`. Постоянная сфера должна оставаться видимой с
единственным значением colorbar около −26.99 dBsm; на наборе с нулевыми радиусами
проверяется подпись `≤ −40 dBsm`.

## Legacy PlotView3D

Справочник по тому, что сейчас доступно из `Termin.Native.PlotView3D` для
3D-графиков в Alliance. Методы ниже - это SWIG C# API, поэтому имена остаются
в `snake_case`.

`PlotView3D` не владеет общим GPU runtime. В WPF-хосте нужно брать shared host
через `Tgfx2Host.Acquire(...)`, создавать `PlotView3D(host)`, а при dispose
вызывать `release_gpu()` и `Tgfx2Host.Release()`. Для показа результата в WPF
потребителю SDK нужна сборка `Termin.Wpf`: в ней лежит
`Tgfx2D3D11ImageHost`.

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
| Interaction | `on_mouse_down`, `on_mouse_move`, `on_mouse_up`, `on_mouse_wheel` | координаты мыши + button/dy | Для WPF/D3D11 host |
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

## WPF/D3D11 host

Старый вывод напрямую в GL framebuffer удален. C# view вызывает
`render_to_texture_handle_id(width, height)`, а показ выполняет platform helper из
`Termin.Wpf`, который принимает tgfx2 texture handle id и композитит его через D3D11 swapchain host. Native window/swapchain plumbing не должен находиться в `PlotView*` или в прикладной модели.

Минимальный render tick:

```csharp
int width = Math.Max(1, RenderHost.FramebufferWidth);
int height = Math.Max(1, RenderHost.FramebufferHeight);
uint colorTex = view.render_to_texture_handle_id(width, height);
RenderHost.Present(colorTex, width, height);
```

Для `Tgfx2D3D11ImageHost` нужно брать именно `FramebufferWidth` и
`FramebufferHeight`. WPF `ActualWidth` / `ActualHeight` измерены в DIPs, а D3D11
swapchain работает в физических пикселях.

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

