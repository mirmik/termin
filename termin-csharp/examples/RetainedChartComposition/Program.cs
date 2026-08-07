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
ChartLineSeries2D sine = chart.AddLineSeries(
    "sin(x)",
    x,
    x.Select(Math.Sin).ToArray(),
    style: new PlotLineSeriesStyle2D(
        new PlotColor2D(0.25f, 0.75f, 1),
        thicknessPx: 2));
if (sine.Name != "sin(x)" || !sine.Visible || !sine.ShowInLegend ||
    sine.DataBounds is not PlotRange2D bounds ||
    bounds.XMin != x[0] || bounds.XMax != x[^1])
    throw new InvalidOperationException(
        "Native semantic chart series smoke check failed.");
sine.Visible = false;
if (sine.Item.Visible)
    throw new InvalidOperationException(
        "Semantic series visibility did not reach the scene item.");
sine.Visible = true;
chart.Fit();

// Customization goes through the public retained scene: the replacement is an
// ordinary native Rect2D item, and no chart-specific paint API is required.
var customPlotBackground = RectItemRef2D.Create(
    chart.Scene,
    new VisualRect2f(0, 0, 1, 1),
    new VisualFillPaint2D(new VisualColor4f(0.03f, 0.07f, 0.12f)));
chart.PlotBackground.Replace(customPlotBackground);

PlotRect2D plotArea = chart.Layout.PlotArea;
float centerX = plotArea.X + plotArea.Width * 0.5f;
float centerY = plotArea.Y + plotArea.Height * 0.5f;
double spanBeforeZoom = chart.Range.XMax - chart.Range.XMin;
PlotRange2D beforeZoom = chart.Range;
if (!chart.Interaction.Wheel(centerX, centerY, 1, xOnly: true) ||
    chart.Range.XMax - chart.Range.XMin >= spanBeforeZoom ||
    chart.Range.YMin != beforeZoom.YMin ||
    chart.Range.YMax != beforeZoom.YMax)
    throw new InvalidOperationException(
        "Native cursor-anchored X-only chart zoom smoke check failed.");
if (!chart.Interaction.Wheel(centerX, centerY, -1))
    throw new InvalidOperationException(
        "Native two-axis chart zoom smoke check failed.");
if (!chart.Interaction.PointerDown(centerX, centerY, button: 2) ||
    !chart.Interaction.PointerMove(centerX + 12, centerY + 8) ||
    !chart.Interaction.PointerUp(centerX + 12, centerY + 8, button: 2))
    throw new InvalidOperationException(
        "Native middle-button chart pan smoke check failed.");
chart.Fit();

var fitted = chart.Range;
const int multiPanelCount = 15;
using var multi = new MultiChart2D(
    host,
    640,
    480,
    panelCount: multiPanelCount,
    initialRange: new PlotRange2D(0, 10, -1, 1),
    panelHeight: 160,
    panelGap: 4);
MultiChartPanel2D stablePanel = multi.Panels[0];
multi.SetPanelCount(multiPanelCount + 2);
MultiChartPanel2D removedPanel = multi.Panels[^1];
multi.SetPanelCount(multiPanelCount);
if (!ReferenceEquals(stablePanel, multi.Panels[0]) ||
    !stablePanel.IsValid || removedPanel.IsValid)
    throw new InvalidOperationException(
        "Native multi-chart generation handle smoke check failed.");
MultiChartSnapshot2D multiState = multi.Snapshot;
if (multiState.PanelCount != multiPanelCount ||
    multiState.MaximumScrollOffset <= 0 ||
    multi.Panels[^1].Chart.Root.Visible)
    throw new InvalidOperationException(
        "Native multi-chart initial virtualization smoke check failed.");
multi.SetSharedX(20, 30);
multi.ScrollOffset = multiState.MaximumScrollOffset;
PlotRange2D revealedRange = multi.Panels[^1].Chart.Range;
if (!multi.Panels[^1].Chart.Root.Visible ||
    revealedRange.XMin != 20 || revealedRange.XMax != 30)
    throw new InvalidOperationException(
        "Native multi-chart deferred shared-X smoke check failed.");
using var peerMulti = new MultiChart2D(
    host,
    640,
    480,
    panelCount: multiPanelCount,
    initialRange: new PlotRange2D(0, 10, -2, 2),
    panelHeight: 160,
    panelGap: 4);
var multiGroup = new MultiChart2DGroup(multi, peerMulti);
multiGroup.SetPanelCount(multiPanelCount + 1);
multiGroup.SetPanelCount(multiPanelCount);
multiGroup.SetSharedX(40, 50);
multiGroup.ScrollOffset = multiGroup.MaximumScrollOffset;
if (multi.Panels.Count != multiPanelCount ||
    peerMulti.Panels.Count != multiPanelCount ||
    multi.Panels[^1].Chart.Range.XMin != 40 ||
    peerMulti.Panels[^1].Chart.Range.XMax != 50 ||
    multi.Snapshot.ScrollOffset != peerMulti.Snapshot.ScrollOffset)
    throw new InvalidOperationException(
        "Coordinated native multi-chart group smoke check failed.");

double[] multiX = { 40, 45, 50 };
for (int index = 0; index < multiPanelCount; ++index)
{
    Chart2D leftPanel = multi.Panels[index].Chart;
    Chart2D rightPanel = peerMulti.Panels[index].Chart;
    leftPanel.SetRange(new PlotRange2D(40, 50, -2, 2));
    rightPanel.SetRange(new PlotRange2D(40, 50, -3, 3));
    leftPanel.AddLineSeries(
        $"left-{index}",
        multiX,
        new[] { -1.0, index / 15.0, 1.0 },
        showInLegend: false);
    rightPanel.AddLineSeries(
        $"right-{index}",
        multiX,
        new[] { 1.5, -index / 10.0, -1.5 },
        showInLegend: false);
}

using var multiRenderer = new RetainedSceneRenderer2D(host, multi.Scene);
using var peerMultiRenderer = new RetainedSceneRenderer2D(
    host, peerMulti.Scene);
multiGroup.ScrollOffset = 0;
uint multiTopTexture = multiRenderer.RenderToTextureHandleId(640, 480);
uint peerTopTexture = peerMultiRenderer.RenderToTextureHandleId(640, 480);
multiGroup.ScrollOffset = multiGroup.MaximumScrollOffset;
uint multiBottomTexture = multiRenderer.RenderToTextureHandleId(640, 480);
uint peerBottomTexture = peerMultiRenderer.RenderToTextureHandleId(640, 480);
if (multiTopTexture == 0 || peerTopTexture == 0 ||
    multiBottomTexture == 0 || peerBottomTexture == 0)
    throw new InvalidOperationException(
        "Native 2x15 multi-chart retained render smoke check failed.");

Console.WriteLine(FormattableString.Invariant(
    $"Scene {chart.Scene.Id}: {chart.Scene.Count} native items, {sine.Item.Snapshot.PointCount} native line points, semantic series and legend OK, fitted range x=[{fitted.XMin:F3}, {fitted.XMax:F3}], y=[{fitted.YMin:F3}, {fitted.YMax:F3}]; pan/zoom OK. Multi scenes {multi.Scene.Id}/{peerMulti.Scene.Id}: 2x{multiPanelCount} stable panels, coordinated reconfigure, virtual scroll, deferred shared X and top/bottom retained D3D render OK."));
