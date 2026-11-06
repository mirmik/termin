using Termin.Native;
using System.Runtime.InteropServices;

static void TestVisualTextDescriptorLayout()
{
    // Must match tc_visual_text_desc2d, including its optional trailing fields.
    // A shorter descriptor lets native code read arbitrary coverage gamma.
    var descriptor = typeof(TextItemRef2D).Assembly.GetType(
        "Termin.Native.VisualSceneNative+TextDesc", throwOnError: true)!;
    int gammaFlagOffset = 2 * IntPtr.Size + 48;
    if (Marshal.OffsetOf(descriptor, "HasCoverageGamma").ToInt32() != gammaFlagOffset ||
        Marshal.OffsetOf(descriptor, "CoverageGamma").ToInt32() != gammaFlagOffset + 4 ||
        Marshal.SizeOf(descriptor) != gammaFlagOffset + 8)
        throw new InvalidOperationException("Visual text descriptor does not match the native ABI.");
}

static void TestPlotViewsAfterShaderArtifactChange(GpuHost host)
{
    const string artifactRootVariable = "TERMIN_SHADER_ARTIFACT_ROOT";
    ShaderRuntime.ConfigureFromAssemblyDirectory();
    string originalRoot = Environment.GetEnvironmentVariable(artifactRootVariable)
        ?? throw new InvalidOperationException("Shader artifact root was not configured.");
    double[] x = { 0, 1, 2, 3 };
    double[] y = { 0, 1, -1, 0 };
    double[] z = { 0, 0.5, 1, 2 };

    void Populate2D(PlotView2D view)
    {
        view.plot(x, y, (uint)x.Length, 0.2f, 0.6f, 1, 1, 2, "solid");
        view.plot(x, z, (uint)x.Length, 1, 0.5f, 0.2f, 1, 2, "dashed");
        if (!view.set_line_style(1, LineStyle.Dash))
            throw new InvalidOperationException("Failed to configure the dashed regression series.");
        view.scatter(x, y, (uint)x.Length, 0.2f, 1, 0.2f, 1, 7, "scatter");
        view.fit();
    }

    void Populate3D(PlotView3D view)
    {
        view.plot(x, y, z, (uint)x.Length, 0.2f, 0.6f, 1, 1, 2, "line");
        view.scatter(x, y, z, (uint)x.Length, 0.2f, 1, 0.2f, 1, 7, "scatter");
        view.surface(new[] { 0.0, 1.0, 0.0, 1.0 },
            new[] { 0.0, 0.0, 1.0, 1.0 }, z,
            2, 2, 0.2f, 0.5f, 0.8f, 1, false, "surface before first framebuffer");
        view.fit_camera();
    }

    using var first = new PlotView2D(host);
    using var second = new PlotView2D(host);
    using var original3D = new PlotView3D(host);
    Populate2D(first);
    Populate2D(second);
    Populate3D(original3D);
    if (original3D.render_to_texture_handle_id(1, 1) == 0)
        throw new InvalidOperationException("3D surface bootstrap at 1x1 failed.");
    if (first.render_to_texture_handle_id(640, 480) == 0 ||
        second.render_to_texture_handle_id(640, 480) == 0 ||
        original3D.render_to_texture_handle_id(640, 480) == 0)
        throw new InvalidOperationException("Initial shared-device plot render failed.");

    try
    {
        // Different resolver setting, same installed artifacts. A newly
        // rendered view retires the device's old cached shader handles before
        // the existing renderers get their next frame.
        Environment.SetEnvironmentVariable(artifactRootVariable,
            originalRoot + Path.DirectorySeparatorChar + ".");
        ShaderRuntime.ConfigureFromAssemblyDirectory();
        using var fresh = new PlotView2D(host);
        using var fresh3D = new PlotView3D(host);
        Populate2D(fresh);
        Populate3D(fresh3D);
        if (fresh3D.render_to_texture_handle_id(2, 2) == 0)
            throw new InvalidOperationException("3D surface bootstrap at 2x2 failed.");
        if (fresh.render_to_texture_handle_id(640, 480) == 0 ||
            fresh3D.render_to_texture_handle_id(640, 480) == 0)
            throw new InvalidOperationException("Fresh plot render after shader reconfiguration failed.");
        if (first.render_to_texture_handle_id(640, 480) == 0 ||
            second.render_to_texture_handle_id(640, 480) == 0 ||
            original3D.render_to_texture_handle_id(640, 480) == 0)
            throw new InvalidOperationException("Existing plot render after shader reconfiguration failed.");
    }
    finally
    {
        Environment.SetEnvironmentVariable(artifactRootVariable, originalRoot);
        ShaderRuntime.ConfigureFromAssemblyDirectory();
    }
    Console.WriteLine("PLOT_SHADER_RECONFIGURE_OK existing 2D solid/dashed/scatter and 3D surface plots rendered after tiny bootstrap, resize and shared-device invalidation");
}

static void TestRetainedVisualSceneFactories()
{
    var scene = new TcVisualScene2D();
    using var otherScene = new TcVisualScene2D();
    var group = GroupItemRef2D.Create(scene);
    var fill = new VisualFillPaint2D(
        new VisualSrgbColor(0.2f, 0.3f, 0.4f));
    var stroke = new VisualStrokePaint2D(
        new VisualSrgbColor(1, 1, 1),
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
        new VisualSrgbColor(1, 1, 1),
        new VisualBounds2f(0, 0, 80, 20),
        parent: group);
    var image = ImageItemRef2D.Create(
        scene,
        "asset://plot-icon",
        new VisualRect2f(0, 0, 16, 16),
        new VisualRect2f(0, 0, 1, 1),
        new VisualSrgbColor(1, 1, 1),
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
        new PlotSrgbColor2D(1, 0, 0),
        thicknessPx: 3,
        lineStyle: PlotLineStyle2D.Dash);
    scatter.Style = new PlotScatterSeriesStyle2D(
        new PlotSrgbColor2D(0, 1, 0),
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

static void TestRetainedHeatmapItems()
{
    var scene = new TcVisualScene2D();
    using var otherScene = new TcVisualScene2D();
    var bounds = new PlotRange2D(-2, 4, 10, 14);
    var descriptor = new PlotProjectionDescriptor2D(
        new PlotRect2D(0, 0, 200, 100), new PlotRect2D(0, 0, 200, 100),
        bounds, new PlotRect2D(0, 0, 200, 100));
    using var projection = PlotProjectionRef2D.Create(scene, descriptor);
    using var otherProjection = PlotProjectionRef2D.Create(otherScene, descriptor);
    var values = new[] { 1.0, 2.0, 3.0, 4.0, double.NaN, 6.0 };
    var heatmap = PlotHeatmapItemRef2D.Create(scene, projection, values, 2, 3, bounds);
    values[0] = 99;
    var initial = heatmap.Snapshot;
    var data = heatmap.CopyData();
    if (initial.Rows != 2 || initial.Columns != 3 || initial.ScalarMin != 1 ||
        initial.ScalarMax != 6 || data[0] != 1 || !double.IsNaN(data[4]) ||
        !heatmap.Style.AutoRange || heatmap.Style.ColorMap != PlotColorMap2D.Viridis ||
        heatmap.Style.Interpolation != PlotHeatmapInterpolation2D.Nearest)
        throw new InvalidOperationException("Heatmap grid copy, auto range or style ABI failed.");

    if (!heatmap.TrySample(-1, 11, out var first) || first.Row != 0 || first.Column != 0 ||
        first.Value != 1 || !heatmap.TrySample(4, 14, out var last) ||
        last.Row != 1 || last.Column != 2 || last.Value != 6 ||
        !heatmap.TrySample(1, 13, out var missing) || !double.IsNaN(missing.Value) ||
        heatmap.TrySample(-3, 11, out _))
        throw new InvalidOperationException("Heatmap row orientation, edge or missing-cell sampling failed.");

    heatmap.Style = new PlotHeatmapStyle2D(
        PlotColorMap2D.CoolWarm, colorMapReversed: true, autoRange: false,
        scalarMin: -10, scalarMax: 10, interpolation: PlotHeatmapInterpolation2D.Bilinear);
    if (heatmap.Style.AutoRange || !heatmap.Style.ColorMapReversed ||
        heatmap.Style.ColorMap != PlotColorMap2D.CoolWarm ||
        heatmap.Snapshot.ScalarMin != -10 || heatmap.Snapshot.ScalarMax != 10 ||
        heatmap.Style.Interpolation != PlotHeatmapInterpolation2D.Bilinear)
        throw new InvalidOperationException("Heatmap fixed color range/style ABI failed.");
    if (!heatmap.TrySample(-0.1, 11.9, out var original) || original.Value != 1 ||
        !heatmap.TrySample(1, 13, out var originalMissing) || !double.IsNaN(originalMissing.Value))
        throw new InvalidOperationException("Bilinear rendering changed original cell sampling.");
    var beforeInvalidInterpolation = heatmap.Snapshot;
    RequireThrows<InvalidOperationException>(
        () => heatmap.Style = new PlotHeatmapStyle2D(
            interpolation: (PlotHeatmapInterpolation2D)2),
        "Heatmap accepted an unknown interpolation mode.");
    if (heatmap.Snapshot.Revision != beforeInvalidInterpolation.Revision ||
        heatmap.Style.Interpolation != PlotHeatmapInterpolation2D.Bilinear ||
        heatmap.Style.ColorMap != PlotColorMap2D.CoolWarm)
        throw new InvalidOperationException("Rejected interpolation mutation changed live style.");

    RequireThrows<ArgumentException>(
        () => heatmap.SetData(new[] { 0.0 }, 2, 3, bounds),
        "Heatmap accepted a mismatched matrix size.");
    RequireThrows<InvalidOperationException>(
        () => heatmap.SetData(new[] { double.PositiveInfinity }, 1, 1, bounds),
        "Heatmap accepted infinity.");
    RequireThrows<InvalidOperationException>(
        () => heatmap.Style = new PlotHeatmapStyle2D(autoRange: false, scalarMin: 2, scalarMax: 1),
        "Heatmap accepted a reversed scalar range.");
    if (heatmap.CopyData()[0] != 1 || heatmap.Snapshot.ScalarMin != -10)
        throw new InvalidOperationException("Rejected heatmap mutations changed live data/style.");

    RequireThrows<InvalidOperationException>(
        () => heatmap.Projection = otherProjection,
        "Heatmap accepted a foreign projection.");
    var rect = RectItemRef2D.Create(scene, new VisualRect2f(0, 0, 1, 1),
        new VisualFillPaint2D(new VisualSrgbColor(1, 1, 1)));
    RequireThrows<InvalidCastException>(
        () => PlotHeatmapItemRef2D.Cast(rect), "Heatmap accepted a wrong-type cast.");
    if (PlotHeatmapItemRef2D.Cast(heatmap).Handle != heatmap.Handle)
        throw new InvalidOperationException("Heatmap typed cast changed native identity.");

    heatmap.SetData(new[] { 5.0 }, 1, 1, bounds);
    heatmap.Style = PlotHeatmapStyle2D.Default;
    if (heatmap.Snapshot.Revision <= initial.Revision || heatmap.Snapshot.Rows != 1 ||
        !heatmap.TrySample(0, 12, out var single) || single.Value != 5)
        throw new InvalidOperationException("Heatmap replacement with a single cell failed.");
    scene.Dispose();
    if (heatmap.IsValid)
        throw new InvalidOperationException("Scene teardown left a heatmap handle alive.");
    RequireThrows<InvalidOperationException>(
        () => { _ = heatmap.Snapshot; }, "A stale heatmap returned a snapshot.");
    Console.WriteLine("RETAINED_HEATMAP_ITEMS_OK");
}

static void TestManagedHeatmapChartComposition(GpuHost host)
{
    using var chart = new Chart2D(host, 800, 500, new PlotRange2D(0, 1, 0, 1));
    var bounds = new PlotRange2D(-2, 4, 10, 14);
    var heatmap = chart.AddHeatmapSeries("field", new[] { 1.0, 2.0, 3.0, 4.0 }, 2, 2, bounds);
    var item = heatmap.Item;
    if (heatmap.Kind != ChartSeriesKind2D.Heatmap || heatmap.ShowInLegend ||
        heatmap.Name != "field" || heatmap.DataBounds?.XMin != -2 ||
        item.Parent?.Handle != chart.PlotArea.Handle ||
        item.ZOrder >= chart.Grid.Item!.ZOrder)
        throw new InvalidOperationException("Heatmap chart identity, data bounds or layer order failed.");
    chart.Fit(0);
    if (chart.Range.XMin != -2 || chart.Range.XMax != 4 ||
        chart.Range.YMin != 10 || chart.Range.YMax != 14)
        throw new InvalidOperationException("Chart Fit ignored heatmap outer cell bounds.");
    var line = chart.AddLineSeries("overlay", new[] { -2.0, 4.0 }, new[] { 10.0, 14.0 });
    heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Plasma, autoRange: false,
        scalarMin: 0, scalarMax: 10, interpolation: PlotHeatmapInterpolation2D.Bilinear);
    heatmap.Name = "updated field";
    heatmap.ShowInLegend = true;
    chart.Resize(640, 480, 1.25f);
    chart.PanBy(1, -1);
    if (heatmap.Style.ColorMap != PlotColorMap2D.Plasma ||
        heatmap.Style.Interpolation != PlotHeatmapInterpolation2D.Bilinear || heatmap.Name != "updated field" ||
        !heatmap.ShowInLegend || !heatmap.IsValid || heatmap.Item.Handle != item.Handle ||
        !heatmap.TrySample(4, 14, out var sample) || sample.Value != 4)
        throw new InvalidOperationException("Heatmap semantic mutations or compact chart updates failed.");
    heatmap.SetData(new[] { 5.0 }, 1, 1, new PlotRange2D(20, 22, 30, 32));
    line.Visible = false;
    chart.Fit(0);
    if (chart.Range.XMin != 20 || chart.Range.YMin != 30)
        throw new InvalidOperationException("Chart Fit ignored replaced heatmap data bounds.");
    if (!chart.RemoveSeries(heatmap) || heatmap.IsValid || item.IsValid)
        throw new InvalidOperationException("Heatmap series removal left native state alive.");
    Console.WriteLine("RETAINED_HEATMAP_CHART_OK");
}

static void TestManagedChartComposition(GpuHost host)
{
    TestManagedHeatmapChartComposition(host);
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
        BackgroundColor = new VisualSrgbColor(0.02f, 0.03f, 0.05f),
        PlotBackgroundColor = new VisualSrgbColor(0.06f, 0.08f, 0.12f),
        AxisColor = new VisualSrgbColor(0.8f, 0.82f, 0.9f),
        GridStyle = new PlotGridStyle2D(0.3f, 0.4f, 0.55f, 0.5f),
    });

    var currentGrid = chart.Grid.Item;
    if (line.Handle != lineHandle ||
        scatter.Handle != scatterHandle ||
        !chart.Projection.Handle.Equals(projectionHandle) ||
        !line.IsValid || !scatter.IsValid ||
        currentGrid is null ||
        !currentGrid.Snapshot.Projection.Equals(projectionHandle) ||
        chart.XTickLabels.ChildCount == 0 ||
        chart.YTickLabels.ChildCount == 0)
        throw new InvalidOperationException(
            "Compact chart updates did not preserve retained native parts.");

    var oldPlotBackground = chart.PlotBackground.Item ??
        throw new InvalidOperationException("Default plot background is absent.");
    var replacement = RectItemRef2D.Create(
        chart.Scene,
        new VisualRect2f(0, 0, 1, 1),
        new VisualFillPaint2D(new VisualSrgbColor(0.1f, 0.14f, 0.2f)));
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

static void RequireThrows<TException>(Action action, string message)
    where TException : Exception
{
    try
    {
        action();
    }
    catch (TException)
    {
        return;
    }
    throw new InvalidOperationException(message);
}

static void TestSphericalChart(GpuHost host)
{
    var defaultSurface = new SurfaceItemStyle3D();
    var defaultGrid = new GridItemStyle3D();
    var defaultColorBar = new ColorBarStyle3D();
    var defaultScatter = new ScatterItemStyle3D();
    if (defaultSurface.ColorA != 1 || defaultSurface.ColorMap != PlotColorMap3D.Viridis ||
        !defaultGrid.LabelsVisible || defaultGrid.GridA != 1 ||
        defaultColorBar.TickCount != 5 || defaultScatter.Size <= 0)
        throw new InvalidOperationException(
            "Default 3D styles must be visible and usable across the managed/native boundary.");
    using var chart = RetainedChart3D.CreateSpherical(host);
    using var orientedChart = RetainedChart3D.CreateSpherical(
        host,
        new SphericalCoordinateFrame3D(
            polarAxisX: 0,
            polarAxisY: -1,
            polarAxisZ: 0,
            zeroLongitudeX: 1,
            zeroLongitudeY: 0,
            zeroLongitudeZ: 0));
    using var cartesian = new RetainedChart3D(host);
    if (chart.Coordinates != PlotCoordinateSystem3D.Spherical ||
        chart.Parts.Grid is null || chart.Scene.Count != 1)
        throw new InvalidOperationException(
            "Spherical construction must include its coordinate grid.");

    double[] azimuths = { 0, Math.PI / 2, Math.PI, 3 * Math.PI / 2 };
    double[] polarAngles = { 0, Math.PI / 2, Math.PI };
    double[] radii = { 2, 2, 2, 2, 3, 4, 5, 6, 2, 2, 2, 2 };
    var orientedSurface = orientedChart.Scene.AddSphericalSurface(
        azimuths, polarAngles, radii,
        style: new SurfaceItemStyle3D(surfaceGridVisible: true));
    orientedChart.SetAxisLabels("angle phi", "polar angle theta", "radius");
    orientedChart.Camera.Fit();
    _ = orientedChart.RenderToTextureHandleId(480, 360);
    if (!orientedSurface.IsValid)
        throw new InvalidOperationException(
            "Oriented spherical construction did not retain its surface.");
    var surface = chart.Scene.AddSphericalSurface(
        azimuths, polarAngles, radii,
        style: new SurfaceItemStyle3D(
            colorMap: PlotColorMap3D.Plasma, surfaceGridVisible: true));
    chart.ShowColorBar(surface, "radius");
    chart.Camera.Fit();
    var fitted = chart.Camera.State;
    if (fitted.TargetX != 0 || fitted.TargetY != 0 || fitted.TargetZ != 0 ||
        fitted.Distance <= 6 || !double.IsFinite(fitted.FarClip))
        throw new InvalidOperationException(
            "Spherical camera must fit the full reference circles around the origin.");
    var camera = new OrbitCameraState3D(
        0.125, -0.375, 0.625, fitted.Distance,
        0.73123456789, 0.41345678901, fitted.FieldOfViewY,
        fitted.NearClip, fitted.FarClip);
    chart.Camera.State = camera;
    if (!chart.Camera.State.Equals(camera))
        throw new InvalidOperationException(
            "Camera doubles must round trip across the native ABI.");

    chart.MsaaSamples = 1;
    _ = chart.RenderToTextureHandleId(480, 360);
    var handle = surface.Handle;
    var before = surface.Snapshot;
    surface.SetRadii(radii.Select(radius => radius * 1.25).ToArray());
    var after = surface.Snapshot;
    if (surface.Handle != handle || !surface.IsValid ||
        after.GeometryRevision == before.GeometryRevision ||
        after.StyleRevision != before.StyleRevision ||
        surface.Style.ColorMap != PlotColorMap3D.Plasma ||
        !chart.Camera.State.Equals(camera))
        throw new InvalidOperationException(
            "Radius updates must preserve surface identity, style and camera.");
    _ = chart.RenderToTextureHandleId(480, 360);
    var beforeInvalid = surface.Snapshot;
    RequireThrows<ArgumentException>(
        () => surface.SetRadii(new[] { 1.0 }),
        "A radius array with the wrong dimensions was accepted.");
    var negativeRadii = (double[])radii.Clone();
    negativeRadii[4] = -1;
    RequireThrows<ArgumentException>(
        () => surface.SetRadii(negativeRadii),
        "Negative radii were accepted.");
    var invalidRadii = (double[])radii.Clone();
    invalidRadii[4] = double.NaN;
    RequireThrows<ArgumentException>(
        () => surface.SetRadii(invalidRadii),
        "Nonfinite radii were accepted.");
    if (!surface.Snapshot.Equals(beforeInvalid))
        throw new InvalidOperationException(
            "Rejected managed radius updates changed the native item.");

    var xyz = new[] { 0.0, 1.0, 2.0, 3.0 };
    RequireThrows<InvalidOperationException>(
        () => chart.Scene.AddSurface(xyz, xyz, xyz, 2, 2),
        "A spherical chart accepted a Cartesian surface.");
    RequireThrows<InvalidOperationException>(
        () => cartesian.Scene.AddSphericalSurface(azimuths, polarAngles, radii),
        "A Cartesian chart accepted a spherical surface.");

    var oldGrid = chart.Parts.Grid!;
    var replacementGrid = chart.Scene.AddGrid();
    chart.Parts.ReplaceGrid(replacementGrid);
    if (chart.Parts.Grid?.Handle != replacementGrid.Handle)
        throw new InvalidOperationException(
            "Replacing the spherical coordinate grid failed.");
    oldGrid.Destroy();
    _ = chart.RenderToTextureHandleId(480, 360);
    chart.Dispose();
    if (surface.IsValid || replacementGrid.IsValid)
        throw new InvalidOperationException(
            "Spherical chart disposal must invalidate its retained parts.");
}

static void TestAxisDisplaySettings(GpuHost host)
{
    using var cartesian = new RetainedChart3D(host);
    PlotAxis3D[] cartesianAxes = { PlotAxis3D.X, PlotAxis3D.Y, PlotAxis3D.Z };
    foreach (var axis in cartesianAxes)
        if (cartesian.GetAxisDisplayOffset(axis) != 0)
            throw new InvalidOperationException("Axis display offsets must default to zero.");

    double[] offsets = { 100.25, -20.5, -40.0 };
    for (int i = 0; i < cartesianAxes.Length; ++i)
        cartesian.SetAxisDisplayOffset(cartesianAxes[i], offsets[i]);
    for (int i = 0; i < cartesianAxes.Length; ++i)
        if (cartesian.GetAxisDisplayOffset(cartesianAxes[i]) != offsets[i])
            throw new InvalidOperationException("Cartesian display offsets must be independent.");

    var plane = cartesian.Scene.AddSurface(
        new[] { 0.0, 1.0, 0.0, 1.0 },
        new[] { 0.0, 0.0, 1.0, 1.0 },
        new[] { 13.01, 13.01, 13.01, 13.01 }, 2, 2);
    cartesian.ShowColorBar(plane, "dBsm");
    cartesian.Camera.Fit();
    _ = cartesian.RenderToTextureHandleId(480, 360);
    var planeBefore = plane.Snapshot;
    var planeCamera = cartesian.Camera.State;
    cartesian.SetAxisDisplayOffset(PlotAxis3D.Z, -30);
    _ = cartesian.RenderToTextureHandleId(480, 360);
    if (!plane.Snapshot.Equals(planeBefore) || !cartesian.Camera.State.Equals(planeCamera))
        throw new InvalidOperationException(
            "Cartesian display changes must preserve surface revisions and camera.");

    using var spherical = RetainedChart3D.CreateSpherical(host);
    if (spherical.GetAxisDisplayOffset(PlotAxis3D.Radius) != 0)
        throw new InvalidOperationException("Radial display offset must default to zero.");
    int invalidations = 0;
    spherical.RenderInvalidated += (sender, _) =>
    {
        if (!ReferenceEquals(sender, spherical))
            throw new InvalidOperationException("Render invalidation sender must identify its chart.");
        ++invalidations;
    };

    // Configure before data or colorbar exists: the display mapping belongs to the chart.
    spherical.SetAxisDisplayOffset(PlotAxis3D.Radius, -40);
    spherical.SetAxisTickLabel(PlotAxis3D.Radius, 0, "\u2264 \u221240 dBsm");
    if (invalidations != 2)
        throw new InvalidOperationException("Display changes must request a new render.");

    double[] azimuths = { 0, Math.PI / 2, Math.PI, 3 * Math.PI / 2 };
    double[] polarAngles = { 0, Math.PI / 2, Math.PI };
    var radii = Enumerable.Repeat(13.01, azimuths.Length * polarAngles.Length).ToArray();
    var sphere = spherical.Scene.AddSphericalSurface(azimuths, polarAngles, radii);
    spherical.ShowColorBar(sphere, "dBsm");
    spherical.Camera.Fit();
    _ = spherical.RenderToTextureHandleId(480, 360);
    var sphereBefore = sphere.Snapshot;
    var sphereCamera = spherical.Camera.State;
    var sphereHandle = sphere.Handle;
    spherical.SetAxisDisplayOffset(PlotAxis3D.Radius, -30);
    spherical.SetAxisTickLabel(PlotAxis3D.Radius, 13.01, "constant sphere");
    _ = spherical.RenderToTextureHandleId(480, 360);
    if (sphere.Handle != sphereHandle || !sphere.Snapshot.Equals(sphereBefore) ||
        !spherical.Camera.State.Equals(sphereCamera))
        throw new InvalidOperationException(
            "Radial display changes must preserve surface identity, revisions and camera.");

    var invalidationsBeforeRejected = invalidations;
    foreach (double invalid in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity })
    {
        RequireThrows<ArgumentOutOfRangeException>(
            () => spherical.SetAxisDisplayOffset(PlotAxis3D.Radius, invalid),
            "A nonfinite display offset was accepted.");
        RequireThrows<ArgumentOutOfRangeException>(
            () => spherical.SetAxisTickLabel(PlotAxis3D.Radius, invalid, "invalid"),
            "A nonfinite tick-label position was accepted.");
    }
    foreach (var invalidAxis in new[] { PlotAxis3D.X, PlotAxis3D.Y, PlotAxis3D.Z, (PlotAxis3D)999 })
    {
        RequireThrows<ArgumentOutOfRangeException>(
            () => spherical.SetAxisDisplayOffset(invalidAxis, 1),
            "A spherical chart accepted an incompatible display axis.");
        RequireThrows<ArgumentOutOfRangeException>(
            () => spherical.GetAxisDisplayOffset(invalidAxis),
            "A spherical chart read an incompatible display axis.");
        RequireThrows<ArgumentOutOfRangeException>(
            () => spherical.SetAxisTickLabel(invalidAxis, 0, "invalid"),
            "A spherical chart accepted an incompatible tick-label axis.");
    }
    RequireThrows<ArgumentOutOfRangeException>(
        () => cartesian.SetAxisDisplayOffset(PlotAxis3D.Radius, 1),
        "A Cartesian chart accepted a radial display offset.");
    if (invalidations != invalidationsBeforeRejected ||
        spherical.GetAxisDisplayOffset(PlotAxis3D.Radius) != -30 ||
        !sphere.Snapshot.Equals(sphereBefore) || !spherical.Camera.State.Equals(sphereCamera))
        throw new InvalidOperationException("Rejected display changes mutated chart state or requested rendering.");

    // Exercise constant-to-varying data, detached colorbar, grid replacement and a new surface.
    var varyingRadii = (double[])radii.Clone();
    for (int column = 0; column < azimuths.Length; ++column)
        varyingRadii[azimuths.Length + column] += column + 1;
    sphere.SetRadii(varyingRadii);
    spherical.HideColorBar();
    var oldGrid = spherical.Parts.Grid!;
    spherical.Parts.ReplaceGrid(spherical.Scene.AddGrid());
    oldGrid.Destroy();
    sphere.Destroy();
    var replacement = spherical.Scene.AddSphericalSurface(azimuths, polarAngles, radii);
    spherical.ShowColorBar(replacement, "dBsm");
    _ = spherical.RenderToTextureHandleId(480, 360);
    if (spherical.GetAxisDisplayOffset(PlotAxis3D.Radius) != -30 ||
        !spherical.Camera.State.Equals(sphereCamera))
        throw new InvalidOperationException("Replacing chart data or parts reset the display mapping or camera.");

    int beforeClear = invalidations;
    spherical.SetAxisTickLabel(PlotAxis3D.Radius, 13.01, null);
    spherical.ClearAxisTickLabels(PlotAxis3D.Radius);
    if (invalidations != beforeClear + 2)
        throw new InvalidOperationException("Removing label overrides must request rendering.");
    spherical.Dispose();
    RequireThrows<ObjectDisposedException>(
        () => spherical.SetAxisDisplayOffset(PlotAxis3D.Radius, 0),
        "A disposed chart accepted a display setting.");
    RequireThrows<ObjectDisposedException>(
        () => spherical.GetAxisDisplayOffset(PlotAxis3D.Radius),
        "A disposed chart returned a display setting.");
}

static void TestChart3DBackgroundColor(GpuHost host)
{
    foreach (bool spherical in new[] { false, true })
    {
        using var chart = spherical
            ? RetainedChart3D.CreateSpherical(host)
            : new RetainedChart3D(host);
        if (!chart.BackgroundColor.Equals(new VisualSrgbColor(0.08f, 0.09f, 0.11f, 1)))
            throw new InvalidOperationException("Chart3D must preserve the default background color.");

        var item = chart.Scene.AddScatter(
            new[] { -1.0, 1.0 }, new[] { -2.0, 2.0 }, new[] { -3.0, 3.0 });
        chart.Camera.Fit();
        _ = chart.RenderToTextureHandleId(480, 360);
        var camera = chart.Camera.State;
        var itemBefore = item.Snapshot;
        int invalidations = 0;
        chart.RenderInvalidated += (sender, _) =>
        {
            if (!ReferenceEquals(sender, chart))
                throw new InvalidOperationException("Background invalidation must identify its chart.");
            ++invalidations;
        };

        var color = new VisualSrgbColor(0.125f, 0.375f, 0.625f, 0.875f);
        chart.BackgroundColor = color;
        if (!chart.BackgroundColor.Equals(color) || invalidations != 1)
            throw new InvalidOperationException("RGBA background must round trip and request rendering.");
        _ = chart.RenderToTextureHandleId(480, 360);
        if (!chart.Camera.State.Equals(camera) || !item.Snapshot.Equals(itemBefore))
            throw new InvalidOperationException("Background changes must preserve camera and item revisions.");

        foreach (float invalid in new[]
                 { float.NaN, float.PositiveInfinity, float.NegativeInfinity, -0.01f, 1.01f })
        {
            foreach (var invalidColor in new[]
            {
                new VisualSrgbColor(invalid, color.G, color.B, color.A),
                new VisualSrgbColor(color.R, invalid, color.B, color.A),
                new VisualSrgbColor(color.R, color.G, invalid, color.A),
                new VisualSrgbColor(color.R, color.G, color.B, invalid),
            })
                RequireThrows<ArgumentOutOfRangeException>(
                    () => chart.BackgroundColor = invalidColor,
                    "A nonfinite or out-of-range background component was accepted.");
        }
        if (!chart.BackgroundColor.Equals(color) || invalidations != 1 ||
            !chart.Camera.State.Equals(camera) || !item.Snapshot.Equals(itemBefore))
            throw new InvalidOperationException("Rejected backgrounds changed chart state or requested rendering.");

        item.Destroy();
        chart.Scene.AddScatter(
            new[] { -1.0, 1.0 }, new[] { -2.0, 2.0 }, new[] { -3.0, 3.0 });
        var oldGrid = chart.Parts.Grid;
        chart.Parts.ReplaceGrid(chart.Scene.AddGrid());
        oldGrid?.Destroy();
        _ = chart.RenderToTextureHandleId(480, 360);
        if (!chart.BackgroundColor.Equals(color) || !chart.Camera.State.Equals(camera))
            throw new InvalidOperationException("Replacing chart items reset its background or camera.");

        int beforeBoundaryColors = invalidations;
        foreach (var boundaryColor in new[]
                 { new VisualSrgbColor(0, 1, 0, 1), new VisualSrgbColor(1, 0, 1, 0) })
        {
            chart.BackgroundColor = boundaryColor;
            if (!chart.BackgroundColor.Equals(boundaryColor))
                throw new InvalidOperationException("Background components must accept both interval endpoints.");
        }
        if (invalidations != beforeBoundaryColors + 2)
            throw new InvalidOperationException("Each successful background update must request rendering.");

        chart.Dispose();
        RequireThrows<ObjectDisposedException>(
            () => { _ = chart.BackgroundColor; },
            "A disposed chart returned its background.");
        RequireThrows<ObjectDisposedException>(
            () => chart.BackgroundColor = color,
            "A disposed chart accepted a background update.");
    }
}

static void TestChart3DCamera(GpuHost host)
{
    if (Marshal.OffsetOf<OrbitCameraState3D>(nameof(OrbitCameraState3D.ProjectionType)).ToInt32() != 72 ||
        Marshal.OffsetOf<OrbitCameraState3D>(nameof(OrbitCameraState3D.OrthoSize)).ToInt32() != 80 ||
        Marshal.SizeOf<OrbitCameraState3D>() != 88)
        throw new InvalidOperationException("OrbitCameraState3D does not match the native camera ABI.");

    foreach (bool spherical in new[] { false, true })
    {
        using var chart = spherical ? RetainedChart3D.CreateSpherical(host) : new RetainedChart3D(host);
        chart.Scene.AddScatter(new[] { -1.0, 1.0 }, new[] { -2.0, 2.0 }, new[] { -3.0, 3.0 });
        chart.Camera.Fit();
        var initial = chart.Camera.State;
        if (initial.ProjectionType != CameraProjection.Perspective || initial.OrthoSize <= 0)
            throw new InvalidOperationException("Chart3D default camera projection is invalid.");
        int invalidations = 0;
        chart.RenderInvalidated += (_, _) => ++invalidations;

        var requested = initial.WithProjection(CameraProjection.Orthographic, 7.25);
        chart.Camera.State = requested;
        if (!chart.Camera.State.Equals(requested) || invalidations != 1)
            throw new InvalidOperationException("Orthographic camera state must round trip and request rendering.");
        _ = chart.RenderToTextureHandleId(480, 360);
        if (!chart.Wheel(240, 180, 1))
            throw new InvalidOperationException("Orthographic camera rejected the zoom gesture.");
        var zoomed = chart.Camera.State;
        if (zoomed.OrthoSize >= requested.OrthoSize || zoomed.Distance != requested.Distance)
            throw new InvalidOperationException("Orthographic zoom must change frame size while preserving distance.");

        int beforeRejected = invalidations;
        foreach (double size in new[] { 0.0, -1.0, double.NaN, double.PositiveInfinity })
            RequireThrows<InvalidOperationException>(
                () => chart.Camera.State = zoomed.WithProjection(CameraProjection.Orthographic, size),
                "An invalid orthographic size was accepted.");
        RequireThrows<InvalidOperationException>(
            () => chart.Camera.State = zoomed.WithProjection((CameraProjection)999),
            "An unknown camera projection was accepted.");
        if (!chart.Camera.State.Equals(zoomed) || invalidations != beforeRejected)
            throw new InvalidOperationException("A rejected camera state changed the camera or requested rendering.");

        chart.Camera.SetIsometric();
        var isometric = chart.Camera.State;
        if (isometric.ProjectionType != CameraProjection.Orthographic ||
            Math.Abs(isometric.Azimuth - Math.PI / 4) > 1e-12 ||
            Math.Abs(isometric.Elevation - Math.Asin(1 / Math.Sqrt(3))) > 1e-12 ||
            invalidations != beforeRejected + 1)
            throw new InvalidOperationException("The isometric camera preset is incorrect.");
        chart.Camera.Fit();
        if (chart.Camera.State.ProjectionType != CameraProjection.Orthographic ||
            chart.Camera.State.Azimuth != isometric.Azimuth ||
            chart.Camera.State.Elevation != isometric.Elevation || invalidations != beforeRejected + 2)
            throw new InvalidOperationException("Fit must preserve projection and viewing direction and request rendering.");
        _ = chart.RenderToTextureHandleId(360, 480);
        chart.Camera.Reset();
        if (chart.Camera.State.ProjectionType != CameraProjection.Perspective ||
            invalidations != beforeRejected + 3)
            throw new InvalidOperationException("Reset must restore perspective and request rendering.");
    }

    using var legacy = new PlotView3D(host);
    legacy.scatter(new[] { -1.0, 1.0 }, new[] { -2.0, 2.0 }, new[] { -3.0, 3.0 }, 2,
        1, 0.5f, 0.2f, 1, 5, "camera bindings");
    using var camera = legacy.camera();
    camera.projection_type = CameraProjection.Orthographic;
    camera.ortho_size = 8;
    if (camera.projection_type != CameraProjection.Orthographic || camera.ortho_size != 8)
        throw new InvalidOperationException("Legacy orthographic camera fields did not round trip.");
    camera.set_isometric();
    legacy.fit_camera();
    if (camera.projection_type != CameraProjection.Orthographic ||
        Math.Abs(camera.elevation - Math.Asin(1 / Math.Sqrt(3))) > 1e-12 ||
        legacy.render_to_texture_handle_id(480, 360) == 0)
        throw new InvalidOperationException("Legacy isometric camera binding failed.");
    Console.WriteLine("CHART3D_CAMERA_OK ABI, round-trip, isometric preset, zoom, fit, reset and render invalidation");
}

TestVisualTextDescriptorLayout();
TestRetainedVisualSceneFactories();
TestRetainedPlotItems();
TestRetainedHeatmapItems();

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

var shareDir = Environment.GetEnvironmentVariable(
    "TERMIN_CSHARP_SDK_SHARE_DIR");
if (string.IsNullOrWhiteSpace(shareDir))
    throw new InvalidOperationException(
        "TERMIN_CSHARP_SDK_SHARE_DIR is required");
var fontPath = Path.Combine(shareDir, "fonts", "DroidSans.ttf");
if (!File.Exists(fontPath))
    throw new FileNotFoundException("SDK test font is missing", fontPath);

if (!OperatingSystem.IsWindows())
{
    using var host = new GpuHost(fontPath, BackendType.Vulkan);
    TestManagedChartComposition(host);
    TestSphericalChart(host);
    TestAxisDisplaySettings(host);
    TestChart3DBackgroundColor(host);
    TestChart3DCamera(host);
}
else
{
    using var host = new GpuHost(fontPath, BackendType.D3D11);
    TestPlotViewsAfterShaderArtifactChange(host);
    TestManagedChartComposition(host);
    TestSphericalChart(host);
    TestAxisDisplaySettings(host);
    TestChart3DBackgroundColor(host);
    TestChart3DCamera(host);
    using (var firstFrameView = new PlotView2D(host))
    using (var secondFrameView = new PlotView2D(host))
    using (var thirdFrameView = new PlotView2D(host))
    {
        PlotView2D[] views = { firstFrameView, secondFrameView, thirdFrameView };
        double[] x = { 0.0, 1.0, 2.0 };
        double[] y = { 0.0, 1.0, 0.0 };
        foreach (PlotView2D frameView in views)
        {
            frameView.set_msaa_samples(4);
            frameView.clear();
            frameView.plot(x, y, (uint)x.Length, 1f, 0f, 0f, 1f, 1.5, "first frame");
            frameView.set_title("S_C: I / Q / magnitude");
            frameView.set_x_label("t, s");
            frameView.set_y_label("model units");
            frameView.fit();
        }
        foreach (PlotView2D frameView in views)
        {
            if (frameView.render_to_texture_handle_id(1, 1) == 0)
                throw new InvalidOperationException("PlotView2D failed to render first-frame 1x1 texture.");
        }
        foreach (PlotView2D frameView in views)
        {
            if (frameView.render_to_texture_handle_id(640, 480) == 0)
                throw new InvalidOperationException("PlotView2D failed to render resized texture.");
        }
    }
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

Console.WriteLine("Retained plots, Chart3D display settings and background, spherical Chart3D and annotation bindings passed.");
