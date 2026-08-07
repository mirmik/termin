using Termin.Native;

var sdkRoot = args.Length == 1
    ? Path.GetFullPath(args[0])
    : Path.GetFullPath(Path.Combine(
        AppContext.BaseDirectory,
        "..", "..", "..", "..", "..", "..", "sdk"));
var fontPath = Path.Combine(
    sdkRoot, "share", "termin", "fonts", "DroidSans.ttf");
if (!File.Exists(fontPath))
    throw new FileNotFoundException(
        "Pass the Termin SDK root as the only argument.", fontPath);

var backend = OperatingSystem.IsWindows()
    ? BackendType.D3D11
    : BackendType.Vulkan;
using var host = new GpuHost(fontPath, backend);
using var chart = new Chart2D(
    host,
    960,
    540,
    new PlotRange2D(0, 2 * Math.PI, -1.2, 1.2));
chart.TitleText = "Retained sine";
chart.XAxisText = "x";
chart.YAxisText = "sin(x)";

var x = Enumerable.Range(0, 100_000)
    .Select(index => index * 2 * Math.PI / 99_999)
    .ToArray();
chart.AddLine(
    x,
    x.Select(Math.Sin).ToArray(),
    style: new PlotLineSeriesStyle2D(
        new PlotColor2D(0.25f, 0.75f, 1),
        thicknessPx: 2));
chart.Fit();

// Customization goes through the public retained scene: the replacement is an
// ordinary native Rect2D item, and no chart-specific paint API is required.
var customPlotBackground = RectItemRef2D.Create(
    chart.Scene,
    new VisualRect2f(0, 0, 1, 1),
    new VisualFillPaint2D(new VisualColor4f(0.03f, 0.07f, 0.12f)));
chart.PlotBackground.Replace(customPlotBackground);

var fitted = chart.Range;
Console.WriteLine(
    $"Scene {chart.Scene.Id}: {chart.Scene.Count} native items, " +
    $"{chart.Lines[0].Snapshot.PointCount} native line points, " +
    $"fitted range x=[{fitted.XMin:F3}, {fitted.XMax:F3}], " +
    $"y=[{fitted.YMin:F3}, {fitted.YMax:F3}].");
