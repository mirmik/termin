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

TestRetainedVisualSceneFactories();

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
