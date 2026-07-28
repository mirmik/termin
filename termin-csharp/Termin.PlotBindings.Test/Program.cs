using Termin.Native;

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
