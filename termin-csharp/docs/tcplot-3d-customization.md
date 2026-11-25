# tcplot - кастомизация 3D графика (C#)

В WPF используйте `RetainedChart3D` и `RetainedChart3DHost`. Пример с
поверхностью, точками и обычными WPF-контролами поверх графика находится в
`examples/RetainedChart3DWpfExample`.

## Серии, камера и WPF-хост

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
chart.Camera.Fit();   // сохраняет текущий azimuth/elevation и тип проекции
chart.Camera.Reset(); // возвращает каноническую ориентацию и перспективу

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
изменения данных, стиля или остальных настроек chart из C# кадр
запрашивает consumer. Изменения `Camera.State`, `Camera.Fit()`, `Camera.Reset()`,
`Camera.SetIsometric()`, `BackgroundColor`, `SetAxisDisplayOffset`, `SetAxisTickLabel`
и `ClearAxisTickLabels` сами вызывают `RenderInvalidated`, на который подписан
host; для них дополнительный `RequestRender()` не нужен. Уведомление синхронное,
поэтому прикреплённый к WPF график следует изменять на UI-потоке host:

```csharp
ChartHost.Attach(chart);

surface.SetData(nextX, nextY, nextZ, rows, columns);
chart.Camera.Fit();
// Fit уже запросил кадр; после отдельного SetData вызовите ChartHost.RequestRender().
```

Для настоящей непрерывной анимации можно установить
`ChartHost.ContinuousRendering = true`. Статические surface-графики не должны
включать этот режим: без mutation host сохраняет последний `D3DImage` и не
выполняет native render/present на каждом WPF composition frame.

Для 3D-траекторий используйте `chart.Scene.AddLine(x, y, z, style)`.
`LineItemRef3D.SetData` и `Style` меняют точки и оформление с сохранением handle.

## Проекция камеры и изометрия

У камер графиков и игрового сегмента единое соглашение: `+X` — вправо,
`+Y` — вперёд, `+Z` — вверх. Матрицы проекции и view используют общую математику
движка. По умолчанию график показывает перспективу.

```csharp
// Ортографическая проекция сохраняет размер объектов независимо от глубины.
var camera = chart.Camera.State;
chart.Camera.State = camera.WithProjection(CameraProjection.Orthographic, orthoSize: 4);

// Точный изометрический ракурс и вписывание текущих данных:
chart.Camera.SetIsometric();

// Вернуться к перспективе, сохранив положение и направление камеры:
chart.Camera.State = chart.Camera.State.WithProjection(CameraProjection.Perspective);
chart.Camera.Fit();
```

`OrthoSize` — половина высоты видимой области в мировых единицах после
визуального масштабирования осей. Полная ширина равна `2 * OrthoSize * aspect`.
Размер должен быть конечным и положительным. Колесо в ортографии меняет
`OrthoSize`, сохраняя `Distance`; в перспективе меняет расстояние до target.
Pan работает в обеих проекциях. `Fit()` сохраняет выбранную проекцию и углы,
учитывает масштаб осей и пропорции последнего render viewport. До первого
рендера используется квадратный viewport.

`SetIsometric()` выбирает ортографию, азимут `π/4` и elevation
`asin(1/√3)` (примерно `35.2643897°`), затем вписывает данные. Для равных
проекций единичных осей их визуальные масштабы также должны быть одинаковыми.
Обычное вращение мышью остаётся доступным после выбора preset.
`Reset()` возвращает перспективу, азимут `45°` и elevation `30°`, затем
вписывает данные. Углы в `OrbitCameraState3D` задаются в радианах.

Изменения состояния камеры сами вызывают `RenderInvalidated`, поэтому
прикреплённый `RetainedChart3DHost` перерисует кадр без отдельного
`RequestRender()`. В WPF-примере есть кнопки переключения проекции и изометрии;
его `--smoke` проверяет обе проекции, zoom, pan, reset и resize.

Состояние native камеры расширено полями проекции: C#-сборку и native
библиотеки нужно обновлять вместе.

## Цвет фона

`RetainedChart3D.BackgroundColor` задаёт цвет очистки всего кадра для декартовых
и сферических графиков. Используется `VisualSrgbColor`: RGB передаются в sRGB,
без ручной линеаризации, а все четыре компонента RGBA должны быть конечными
и лежать в `[0, 1]`. Значение по умолчанию — `(0.08, 0.09, 0.11, 1)`.

```csharp
chart.BackgroundColor = new VisualSrgbColor(0.08f, 0.18f, 0.32f);
VisualSrgbColor currentBackground = chart.BackgroundColor;
// Прикреплённый RetainedChart3DHost перерисует кадр автоматически.
```

Настройка принадлежит графику и сохраняется при обновлении данных, замене
поверхности или сетки и освобождении GPU-ресурсов. Смена фона не изменяет
геометрию, цвета объектов, деления или камеру. Некорректный цвет отклоняется
целиком, предыдущий фон сохраняется.

Alpha сохраняется в render target, но текущий WPF/D3DImage bridge не выполняет
необходимую для прозрачного композитинга операцию premultiply RGB. Для показа
через `RetainedChart3DHost` используйте непрозрачный фон (`A = 1`); поддержка
полупрозрачного фона WPF этим свойством не обеспечивается.

В Python соответствует свойство `chart.background_color` с типом
`tcplot.SrgbColor`, как у остальных цветовых настроек tcplot.

WPF/D3DImage bridge преобразует линейный RGB в sRGB при записи в общую текстуру
вывода. Native render target остаётся линейным; компенсация цвета на стороне
приложения не требуется.

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
Кнопка `Blue background` / `Dark background` меняет фон уже показанного графика
без изменения ракурса и поверхности.

`task test -- --csharp-only` также запускает `PlotDemoApp --smoke-axis-display`.
Этот сценарий проверяет WPF-отображение и смену display-настроек, сохраняя кадры
в `build/logs/plot-demo-*.png`. Постоянная сфера должна оставаться видимой с
единственным значением colorbar около −26.99 dBsm; на наборе с нулевыми радиусами
проверяется подпись `≤ −40 dBsm`.
Тот же smoke проверяет смену фона по sRGB-пикселям WPF-вывода,
сохранение геометрии и камеры,
а также точное восстановление изображения после возврата исходного фона.

Дополнительный `PlotDemoApp --smoke-color-presentation`, включённый в ту же
test-задачу, сравнивает реальные WPF-пиксели `Chart2D`, декартового и сферического
`RetainedChart3D` с заданными sRGB-цветами. Проверяются цветной и серый фон,
белый, чёрный, изменение размера и пересоздание графиков. Кадры сохраняются
в `build/logs/plot-color-*.png`.
