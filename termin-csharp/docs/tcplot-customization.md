# tcplot — кастомизация 2D-графиков из C#

## Chart2D и MultiChart2D

В WPF графики собираются через `Chart2D` и
`MultiChart2D`. Компоновка, тики, проекция, общая X-ось и виртуальный скролл
принадлежат tcplot, но собранная `TcVisualScene2D` и именованные части чарта
остаются доступны C#-потребителю для кастомизации.

```csharp
using var chart = new Chart2D(
    host, 1, 1, new PlotRange2D(0, 1, -1, 1));
ChartLineSeries2D signal = chart.AddLineSeries(
    "signal", x, y,
    style: new PlotLineSeriesStyle2D(
        new PlotSrgbColor2D(0.2f, 0.8f, 1.0f), thicknessPx: 1.5f));

sceneHost.Attach(host, chart.Scene);
using var interaction = new Chart2DWpfInteraction(sceneHost, chart);

// Стандартные части не спрятаны за facade.
chart.TitleText = "Receiver signal";
chart.Title.Item!.Visible = true;
chart.ApplyTheme(theme);
sceneHost.AddPortal(button, new Rect(12, 12, 110, 30));
sceneHost.RequestRender();
```

Для набора панелей создаётся один `MultiChart2D`; его `Panels` возвращает
заимствованные `Chart2D`, а `MultiChart2DWpfInteraction` синхронизирует X и
переключает колесо между навигацией и виртуальным скроллом. Оба WPF-хоста
рендерят on-demand по `RequestRender()` и автоматически реагируют на resize,
DPI и пользовательскую навигацию.

## Две шкалы Y

На одном `Chart2D` линейные серии могут использовать разные шкалы Y при общей
оси X. Шкалу серии задаёт первый аргумент `AddLineSeries`. Вызов без этого
аргумента использует левую шкалу. Правая появляется при назначении ей серии
или при установке её диапазона или подписи.

```csharp
double[] x = { 0, 1, 2 };
using var chart = new Chart2D(host, 960, 540, new PlotRange2D(0, 2, -60, 0));
chart.YAxisText = "Amplitude [dB]";
chart.SetYAxisRange(ChartYAxis2D.Right, -180, 180);
chart.RightYAxisText = "Phase [°]";
chart.AddLineSeries("Amplitude", x, new[] { -55.0, -30.0, -10.0 });
chart.AddLineSeries(ChartYAxis2D.Right, "Phase", x, new[] { 120.0, 0.0, -140.0 });
```

`Range` и `Projection` читают общий X и левый Y. Диапазон конкретной шкалы
возвращает `GetYAxisRange`, а `series.Item.Projection` переводит координаты
этой серии в пиксели. `Fit` подбирает общий X по всем видимым сериям и каждый
Y по видимым сериям этой шкалы. В двухосевом режиме шкала без видимых данных
сохраняет заданный диапазон. Горизонтальные линии сетки идут по левой шкале.
Перетаскивание и обычное колесо меняют обе шкалы относительно положения
курсора, Ctrl+колесо меняет общий X. У программных `PanBy` и `ZoomAt`
координаты Y по-прежнему относятся к левой шкале.

Интерактивный пример с кнопкой Fit находится в
`examples/RetainedChartWpfExample`.

## Тепловая карта на равномерной сетке

`Chart2D.AddHeatmapSeries` добавляет native retained heatmap под сеткой,
линиями, точками и аннотациями. Поддерживается равномерная прямоугольная
сетка, в том числе одна строка, один столбец или одна ячейка.

```csharp
double[] values = { 1, 2, 3, 4, double.NaN, 6 };
ChartHeatmapSeries2D heatmap = chart.AddHeatmapSeries(
    "temperature", values, rows: 2, columns: 3,
    bounds: new PlotRange2D(0, 30, 0, 20));
chart.Fit(0);

// Фиксированная шкала позволяет сравнивать несколько кадров/панелей.
heatmap.Style = new PlotHeatmapStyle2D(
    PlotColorMap2D.Viridis, autoRange: false, scalarMin: 0, scalarMax: 10,
    interpolation: PlotHeatmapInterpolation2D.Bilinear);
if (heatmap.TrySample(5, 5, out PlotHeatmapSample2D cell))
    Console.WriteLine($"row={cell.Row}, column={cell.Column}, value={cell.Value}");
sceneHost.RequestRender();
```

`values[row * columns + column]` хранит значения по строкам. Нулевая строка
расположена у `YMin`, нулевой столбец — у `XMin`; `bounds` задаёт **внешние
границы ячеек**, а не центры крайних отсчётов. Максимальные границы при
`TrySample` относятся к последней ячейке. За пределами карты возвращается
`false`; у прозрачной ячейки возвращается `true` и `Value = NaN`.

`NaN` рисуется прозрачно и не участвует в автоматическом выборе цветового
диапазона. Бесконечности отклоняются. По умолчанию ячейки рисуются через
`PlotHeatmapInterpolation2D.Nearest`. Необязательный `Bilinear` плавно
интерполирует скалярные значения между центрами ячеек до применения палитры.
Веса соседей с `NaN` исключаются из расчёта значения; сумма весов существующих
соседей задаёт покрытие, поэтому границы пропусков становятся полупрозрачными.
`TrySample` при любом режиме возвращает исходное значение ячейки, а не
интерполированное значение изображения. Режим можно менять без замены матрицы.
По умолчанию используется `Viridis` и автоматическая шкала;
эффективные границы доступны в `heatmap.Item.Snapshot.ScalarMin/ScalarMax`.
`ColorMapReversed` разворачивает палитру. `SetData(values, rows, columns,
bounds)` заменяет матрицу и пространственные границы; данные копируются в
native item. `Fit()` учитывает актуальные границы видимых heatmap-серий.

`PlotHeatmapItemRef2D.Create` позволяет использовать тот же item напрямую
в `TcVisualScene2D` с общей `PlotProjectionRef2D`. Pan/zoom/resize меняют
компактную проекцию; повторная передача матрицы не нужна. Доступны обычные
операции retained item: `Visible`, `Opacity`, `ZOrder`, clipping и lifetime
сцены. `chart.RemoveSeries(heatmap)` уничтожает native item.

Интерактивный пример находится в `examples/PlotDemoApp/Heatmap2DWindow`:
карта, линия поверх неё, смена палитры, диапазона, интерполяции и данных, чтение ячейки
под курсором и отдельная цветовая шкала, нарисованная тем же heatmap item.

## Стили и аннотации

Применяйте `Chart2DTheme` через `chart.ApplyTheme(theme)`. Для общего стиля
панелей используйте `multiChart.ApplyTheme(theme)`. Видимость сетки, подписей
и других частей задаётся через их `Item.Visible`. Размеры шрифта, осей и
отступов в теме задаются в логических пикселях.

Для цветного XY-маршрута передайте отдельное скалярное значение на каждую
точку. Толщина и штрих задаются в `PlotLineSeriesStyle2D`.

```csharp
ChartLineSeries2D route = chart.AddLineSeries(
    "speed", x, y, speed,
    new PlotLineSeriesStyle2D(
        new PlotSrgbColor2D(1, 1, 1),
        thicknessPx: 2.5f,
        colorMap: PlotColorMap2D.Viridis,
        scalarMin: 0,
        scalarMax: 30));
chart.Fit();
sceneHost.RequestRender();
```

Размещайте собственные графические элементы в `chart.Annotations`.
Используйте `chart.Projection` для перевода координат данных в пиксели и
`chart.Scene` для маршрутизации событий этих элементов. WPF-контролы можно
привязать к элементам сцены через порталы.

Профили SDK `full` и `plot-d3d11` предоставляют один и тот же retained API.
Примеры XY-маршрута с цветовой шкалой, набора панелей и тепловой карты
доступны в `examples/PlotDemoApp`.

## График и виджеты в одном native-документе

Откройте **Open 2D chart with native UI controls** в меню `PlotDemoApp`.
`NativeChartDocumentWindow` собирает общий `NativeUiDocument` из
`NativeBoxLayout`, `NativeButton`, `NativeLabel` и `NativeSceneView`.
Добавьте `root.Handle` в документ через `AddRoot`, затем подключите документ
к `NativeDocumentHost`. Native-дерево управляет layout, фокусом и захватом
мыши, а один WPF-хост выводит весь документ через D3D11.

`NativeSceneView` заимствует `chart.Scene`. В `LayoutPrepared` берите
логические размеры из `view.Bounds` и передавайте их в `chart.Resize` с
`pixelScale: 1`. Плотность экрана применяет renderer документа. Для
панорамирования и масштабирования отключите `NavigationEnabled` у виджета
и передайте события `PointerHandler` в `chart.Interaction`. Координаты
события локальны для сцены. Обрабатывайте `Cancel`, чтобы сбросить drag при
потере захвата.

`NativeButton.Clicked` срабатывает при активации мышью или клавиатурой.
Обработчик может изменить данные или видимость серии, обновить `NativeLabel`
и вызвать `host.RequestRender()`. Изменение дерева, повторную отправку ввода
и закрытие окна планируйте после возврата из обработчика. Документ владеет
виджетами, в том числе снятыми с layout. При закрытии освободите WPF-хост,
затем документ, график и GPU-хост в этом порядке.

Чтобы добавить новый тип виджета в C#, используйте ту же схему. Экспортируйте
фабрику, которая регистрирует существующий native-виджет в документе и
возвращает `tc_widget_ref`. Специфичные для типа C-функции проверяют тип при
разрешении этого дескриптора. В C# обёртка наследует `NativeWidgetRef`, а
native-подписка освобождает свой контекст при отключении или уничтожении
виджета.

Проверку WPF/D3D11 можно запустить отдельно на Windows:

```powershell
dotnet run --project termin-csharp/examples/PlotDemoApp/PlotDemoApp.csproj -- --smoke-native-chart-document
```
