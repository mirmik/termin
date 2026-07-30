using Termin.Native;

static void TestRetainedVisualSceneFactories()
{
    var scene = new TcVisualScene2D();
    using var otherScene = new TcVisualScene2D();
    var group = GroupItemRef2D.Create(scene);
    var fill = new VisualFillPaint2D(
        new VisualColor4f(0.2f, 0.3f, 0.4f));
    var stroke = new VisualStrokePaint2D(
        new VisualColor4f(1, 1, 1),
        2,
        dashPattern: new[] { 4.0f, 2.0f });
    var rect = RectItemRef2D.Create(
        scene,
        new VisualRect2f(0, 0, 100, 50),
        fill,
        stroke,
        group);

    if (scene.Count != 2 || group.ChildCount != 1 ||
        rect.Parent?.Handle != group.Handle)
        throw new InvalidOperationException(
            "Retained visual-scene topology is incorrect.");

    rect.Transform = VisualAffine2f.Translation(10, 20);
    rect.Visible = false;
    rect.Enabled = false;
    rect.Opacity = 0.5f;
    rect.ZOrder = 7;
    rect.SetClip(new VisualRect2f(0, 0, 80, 40));
    if (rect.Transform.Tx != 10 || rect.Visible ||
        rect.Enabled || rect.Opacity != 0.5f || rect.ZOrder != 7)
        throw new InvalidOperationException(
            "Common GraphicItemRef2D mutation failed.");

    var triangle = new VisualPath2D(
        new[]
        {
            VisualPathVerb2D.MoveTo,
            VisualPathVerb2D.LineTo,
            VisualPathVerb2D.LineTo,
            VisualPathVerb2D.Close,
        },
        new[]
        {
            new VisualVec2f(0, 0),
            new VisualVec2f(20, 0),
            new VisualVec2f(10, 10),
        });
    var path = PathItemRef2D.Create(
        scene, triangle, fill, stroke, group);
    var text = TextItemRef2D.Create(
        scene,
        "axis",
        "ui://default-font",
        new VisualVec2f(0, 12),
        12,
        new VisualColor4f(1, 1, 1),
        new VisualBounds2f(0, 0, 80, 20),
        parent: group);
    var image = ImageItemRef2D.Create(
        scene,
        "asset://plot-icon",
        new VisualRect2f(0, 0, 16, 16),
        new VisualRect2f(0, 0, 1, 1),
        new VisualColor4f(1, 1, 1),
        parent: group);
    var hit = HitRegionItemRef2D.Create(
        scene, triangle, parent: group);
    if (!path.IsValid || !text.IsValid ||
        !image.IsValid || !hit.IsValid)
        throw new InvalidOperationException(
            "A typed built-in factory returned a stale handle.");

    try
    {
        _ = RectItemRef2D.Cast(path);
        throw new InvalidOperationException(
            "Wrong-type GraphicItem cast succeeded.");
    }
    catch (InvalidCastException)
    {
    }

    var foreignParent = GroupItemRef2D.Create(otherScene);
    if (rect.SetParent(foreignParent))
        throw new InvalidOperationException(
            "Cross-scene reparenting succeeded.");

    var stale = rect;
    if (!rect.Destroy() || stale.IsValid)
        throw new InvalidOperationException(
            "Explicit item destruction did not invalidate its wrapper.");

    var sceneOwned = path;
    scene.Dispose();
    if (sceneOwned.IsValid)
        throw new InvalidOperationException(
            "Scene teardown did not invalidate item wrappers.");
}

static void TestRetainedPlotItems()
{
    var scene = new TcVisualScene2D();
    using var otherScene = new TcVisualScene2D();
    var descriptor = new PlotProjectionDescriptor2D(
        new PlotRect2D(0, 0, 120, 100),
        new PlotRect2D(10, 10, 100, 80),
        new PlotRange2D(0, 10, 0, 10),
        new PlotRect2D(10, 10, 100, 80));
    using var projection = PlotProjectionRef2D.Create(scene, descriptor);
    using var otherProjection =
        PlotProjectionRef2D.Create(otherScene, descriptor);
    var root = GroupItemRef2D.Create(scene);

    var xTicks = RetainedPlotLayout2D.MakeAxisTicks(
        0, 10, 100, 40);
    var yTicks = RetainedPlotLayout2D.MakeAxisTicks(
        0, 10, 80, 40);
    var grid = PlotGridItemRef2D.Create(
        scene,
        projection,
        xTicks.Select(tick => tick.Value).ToArray(),
        yTicks.Select(tick => tick.Value).ToArray(),
        parent: root);
    var line = PlotLineSeriesItemRef2D.Create(
        scene,
        projection,
        new[] { 0.0, 5.0, 10.0 },
        new[] { 0.0, 5.0, 10.0 },
        new[] { 0.0, 0.5, 1.0 },
        parent: root);
    var scatter = PlotScatterSeriesItemRef2D.Create(
        scene,
        projection,
        new[] { 2.0, 8.0 },
        new[] { 8.0, 2.0 },
        parent: root);

    if (root.ChildCount != 3 ||
        line.Snapshot.PointCount != 3 ||
        scatter.Snapshot.PointCount != 2 ||
        grid.Snapshot.XTickCount != (nuint)xTicks.Length)
        throw new InvalidOperationException(
            "Retained plot item creation or topology failed.");

    line.Append(new[] { 9.0 }, new[] { 1.0 }, new[] { 0.9 });
    var lineData = line.CopyData();
    if (lineData.X.Length != 4 ||
        lineData.Scalar is null ||
        lineData.Scalar[3] != 0.9)
        throw new InvalidOperationException(
            "Retained line data mutation/copy failed.");

    var visual = projection.DataToVisual(new PlotPoint2D(5, 5));
    var roundTrip = projection.VisualToData(visual);
    if (Math.Abs(roundTrip.X - 5) > 1e-6 ||
        Math.Abs(roundTrip.Y - 5) > 1e-6 ||
        !line.TryNearest(visual.X, visual.Y, 1, out var nearest) ||
        nearest.Index != 1)
        throw new InvalidOperationException(
            "Projection or native nearest-point query failed.");

    line.Style = new PlotLineSeriesStyle2D(
        new PlotColor2D(1, 0, 0),
        thicknessPx: 3,
        lineStyle: PlotLineStyle2D.Dash);
    scatter.Style = new PlotScatterSeriesStyle2D(
        new PlotColor2D(0, 1, 0),
        diameterPx: 7);
    grid.Style = new PlotGridStyle2D(0.2f, 0.2f, 0.2f, widthPx: 2);
    if (line.Style.ThicknessPx != 3 ||
        scatter.Style.DiameterPx != 7 ||
        grid.Style.WidthPx != 2)
        throw new InvalidOperationException(
            "Retained plot style mutation failed.");

    try
    {
        _ = PlotGridItemRef2D.Cast(line);
        throw new InvalidOperationException(
            "Wrong-type retained plot cast succeeded.");
    }
    catch (InvalidCastException)
    {
    }

    try
    {
        line.Projection = otherProjection;
        throw new InvalidOperationException(
            "Cross-scene plot projection was accepted.");
    }
    catch (InvalidOperationException)
    {
    }

    var fitted = RetainedPlotLayout2D.FitRange(
        new PlotRange2D(0, 10, -5, 5));
    if (Math.Abs(fitted.XMin + 0.5) > 1e-6 ||
        xTicks.Length == 0 ||
        string.IsNullOrEmpty(xTicks[0].Label))
        throw new InvalidOperationException(
            "Native retained plot layout utilities failed.");

    var sceneOwned = line;
    scene.Dispose();
    if (sceneOwned.IsValid || projection.IsValid)
        throw new InvalidOperationException(
            "Scene teardown did not stale retained plot handles.");
}

static void TestManagedChartComposition(GpuHost host)
{
    using var chart = new Chart2D(
        host,
        800,
        500,
        new PlotRange2D(0, 10, -1, 1));
    chart.TitleText = "Retained chart";
    chart.XAxisText = "time";
    chart.YAxisText = "value";

    var line = chart.AddLine(
        new[] { 0.0, 5.0, 10.0 },
        new[] { 0.0, 1.0, 0.0 });
    var scatter = chart.AddScatter(
        new[] { 2.5, 7.5 },
        new[] { -0.5, 0.5 });
    var lineHandle = line.Handle;
    var scatterHandle = scatter.Handle;
    var projectionHandle = chart.Projection.Handle;

    chart.Resize(1000, 600, 1.25f);
    chart.PanBy(2, 0.25);
    chart.ZoomAt(2, 7, 0.25);
    chart.ApplyTheme(new Chart2DTheme
    {
        BackgroundColor = new VisualColor4f(0.02f, 0.03f, 0.05f),
        PlotBackgroundColor = new VisualColor4f(0.06f, 0.08f, 0.12f),
        AxisColor = new VisualColor4f(0.8f, 0.82f, 0.9f),
        GridStyle = new PlotGridStyle2D(0.3f, 0.4f, 0.55f, 0.5f),
    });

    var currentGrid = chart.Grid.Item;
    if (line.Handle != lineHandle ||
        scatter.Handle != scatterHandle ||
        !chart.Projection.Handle.Equals(projectionHandle) ||
        !line.IsValid || !scatter.IsValid ||
        currentGrid is null ||
        !currentGrid.Snapshot.Projection.Equals(projectionHandle) ||
        chart.XTicks.Count == 0 || chart.YTicks.Count == 0)
        throw new InvalidOperationException(
            "Compact chart updates did not preserve retained native parts.");

    var oldPlotBackground = chart.PlotBackground.Item ??
        throw new InvalidOperationException("Default plot background is absent.");
    var replacement = RectItemRef2D.Create(
        chart.Scene,
        new VisualRect2f(0, 0, 1, 1),
        new VisualFillPaint2D(new VisualColor4f(0.1f, 0.14f, 0.2f)));
    chart.PlotBackground.Replace(replacement);
    if (oldPlotBackground.IsValid ||
        chart.PlotBackground.Item?.Handle != replacement.Handle ||
        replacement.Parent?.Handle != chart.PlotArea.Handle)
        throw new InvalidOperationException(
            "A standard managed chart part was not replaced correctly.");

    chart.Title.Remove();
    chart.Resize(900, 550);
    if (chart.Title.Item is not null || !line.IsValid)
        throw new InvalidOperationException(
            "Removing a standard chart part broke later layout.");

    if (!chart.RemoveSeries(scatter) || scatter.IsValid ||
        chart.Scatters.Count != 0)
        throw new InvalidOperationException(
            "Managed series removal did not destroy its native item.");
}

TestRetainedVisualSceneFactories();
TestRetainedPlotItems();

// This test is deliberately GPU-independent. It verifies the detached values
// at runtime and compiles every PlotView2D annotation operation used by a
// managed host. Native interaction semantics are covered by tcplot tests.
using var stale = new PlotAnnotationHandle();
if (stale.valid())
    throw new InvalidOperationException("A default annotation handle is valid");

using var snapshot = new PlotDataMarkerBindingSnapshot2D();
if (snapshot.available)
    throw new InvalidOperationException("A default marker snapshot is available");

using var action = new PlotAnnotationActionPoll2D();
if (action.available)
    throw new InvalidOperationException("A default annotation action is available");

static void CompilePlotAnnotationSurface(
    PlotView2D view,
    PlotAnnotationHandle handle)
{
    using var created = view.create_data_marker(1.0, 2.0, "managed marker");
    _ = view.update_data_marker(created, 3.0, 4.0, "updated");
    using var marker = view.data_marker_snapshot(created);
    using var action = view.take_annotation_action();
    _ = view.destroy_annotation(handle);
}

if (OperatingSystem.IsWindows())
{
    var shareDir = Environment.GetEnvironmentVariable(
        "TERMIN_CSHARP_SDK_SHARE_DIR");
    if (string.IsNullOrWhiteSpace(shareDir))
        throw new InvalidOperationException(
            "TERMIN_CSHARP_SDK_SHARE_DIR is required");
    var fontPath = Path.Combine(shareDir, "fonts", "DroidSans.ttf");
    if (!File.Exists(fontPath))
        throw new FileNotFoundException("SDK test font is missing", fontPath);

    using var host = new GpuHost(fontPath, BackendType.D3D11);
    TestManagedChartComposition(host);
    using var view = new PlotView2D(host);
    using var otherView = new PlotView2D(host);
    view.set_view(0.0, 10.0, 0.0, 10.0);

    using var marker = view.create_data_marker(5.0, 5.0, "managed marker");
    if (!marker.valid())
        throw new InvalidOperationException("Marker creation failed");
    if (!view.update_data_marker(marker, 5.0, 5.0, "updated"))
        throw new InvalidOperationException("Marker update failed");
    using (var current = view.data_marker_snapshot(marker))
    {
        if (!current.available || current.text != "updated")
            throw new InvalidOperationException("Marker snapshot is incorrect");
    }
    if (otherView.update_data_marker(marker, 1.0, 1.0, "foreign"))
        throw new InvalidOperationException("Cross-view handle was accepted");

    _ = view.render_to_texture_id(400, 300);
    if (!view.on_mouse_down(230.5f, 146.0f, 0))
        throw new InvalidOperationException("Marker did not consume pointer down");
    view.on_mouse_up(230.5f, 146.0f, 0);
    using (var activated = view.take_annotation_action())
    {
        if (!activated.available || activated.action != "activate")
            throw new InvalidOperationException("Marker action was not delivered");
    }

    if (!view.destroy_annotation(marker))
        throw new InvalidOperationException("Marker destruction failed");
    if (view.update_data_marker(marker, 1.0, 1.0, "stale"))
        throw new InvalidOperationException("Stale marker update succeeded");
    using var staleSnapshot = view.data_marker_snapshot(marker);
    if (staleSnapshot.available || view.destroy_annotation(marker))
        throw new InvalidOperationException("Stale marker handle was accepted");
}

Console.WriteLine("Plot annotation bindings passed.");
