using Termin.Native;

internal static class NativeWidgetBindingChecks
{
    internal static void Run(GpuHost host, string fontPath)
    {
        using var document = new NativeUiDocument("Managed chart widget bindings");
        using var foreign = new NativeUiDocument("Foreign widget document");
        using var chart = new Chart2D(host, 200, 140, new PlotRange2D(0, 3, -1, 2));
        using var renderer = new NativeDocumentRenderer(host, document, fontPath);
        chart.AddLine(new[] { 0.0, 1.0, 2.0, 3.0 }, new[] { 0.0, 1.0, 0.0, 1.0 });

        var root = new NativeBoxLayout(document) { Spacing = 4 };
        var button = new NativeButton(document, "Сменить ряд");
        var label = new NativeLabel(document, "Готово");
        var view = new NativeSceneView(document, chart.Scene) { NavigationEnabled = false, ShowGrid = false };
        var foreignButton = new NativeButton(foreign, "Other document");
        Throws<ArgumentException>(() => root.AddChild(foreignButton));
        Throws<ArgumentException>(() => foreign.ResolveWidget(button.Handle));
        Throws<ArgumentException>(() => document.AddRoot(foreignButton.Handle));
        Require(foreignButton.IsAlive && foreign.RootCount == 0, "Foreign adoption disturbed the source document.");

        var otherBox = new NativeBoxLayout(document);
        otherBox.AddChild(button);
        root.AddChild(button, NativeBoxSizing.Fixed, 30);
        otherBox.Destroy();
        Require(button.IsAlive, "Reparenting left the widget owned by its previous parent.");
        root.AddChild(label, NativeBoxSizing.Fixed, 18);
        root.AddChild(view);
        document.AddRoot(root.Handle);
        Require(document.ResolveWidget(button.Handle).Enabled, "Cannot resolve a live widget.");

        int clicks = 0;
        int cancel = 0;
        EventHandler observer = (_, _) => { ++clicks; label.Text = $"Activation {clicks}"; };
        button.Clicked += observer;
        view.PointerHandler = pointer =>
        {
            if (pointer.Type == NativeUiPointerEventType.Cancel)
            {
                ++cancel;
                return true;
            }
            if (pointer.Type != NativeUiPointerEventType.Down)
                return false;
            Require(pointer.X == 12 && pointer.Y == 13, "Scene input was not transformed out of document coordinates.");
            return true;
        };
        GC.Collect();
        GC.WaitForPendingFinalizers();

        renderer.SetMetrics(400, 400, 2);
        renderer.PrepareLayout();
        var viewBounds = view.Bounds;
        Require(viewBounds.Y == 56 && viewBounds.Width == 200 && viewBounds.Height == 144,
            "Document layout did not expose logical widget bounds before painting.");
        chart.Resize(viewBounds.Width, viewBounds.Height);
        Require(renderer.RenderToTextureHandleId() != 0 && clicks == 0 && cancel == 0,
            "Rendering failed or invoked managed input callbacks.");

        var buttonBounds = button.Bounds;
        renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Down, buttonBounds.X + 10, buttonBounds.Y + 10, 0));
        Require(renderer.HasPointerCapture, "Native button did not capture the pointer.");
        renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Up, buttonBounds.X + 10, buttonBounds.Y + 10, 0));
        Require(clicks == 1 && !renderer.HasPointerCapture, "Native button activation or release was lost.");
        document.Focus(button.Handle);
        renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 13 });
        Require(clicks == 2, "Native keyboard activation was lost after collection.");

        button.Clicked -= observer;
        renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 13 });
        Require(clicks == 2, "Disconnected activation was still delivered.");
        EventHandler destroyFromCallback = (_, _) => button.Destroy();
        button.Clicked += destroyFromCallback;
        Throws<InvalidOperationException>(() => renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 13 }));
        Require(button.IsAlive, "Reentrant activation destroyed its own native widget.");
        button.Clicked -= destroyFromCallback;

        renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Down, viewBounds.X + 12, viewBounds.Y + 13, 2));
        Require(renderer.HasPointerCapture, "Scene input handler did not acquire native capture.");
        renderer.CancelInteraction(NativeUiPointerCancelReason.HostCaptureLost);
        Require(cancel == 1 && !renderer.HasPointerCapture, "Scene capture loss did not reach C# exactly once.");
        view.PointerHandler = null;

        button.Visible = false;
        button.Enabled = false;
        Require(!button.Visible && !button.Enabled, "Managed widget state did not reach native storage.");
        root.RemoveChild(label);
        Require(label.IsAlive, "Removing a child also destroyed it.");
        button.Clicked += observer;
        var oldHandle = button.Handle;
        root.Destroy();
        Require(!button.IsAlive && !view.IsAlive && label.IsAlive && document.RootCount == 0,
            "Recursive disposal did not invalidate the attached widget subtree.");
        Throws<InvalidOperationException>(() => _ = button.Bounds);
        button.Clicked -= observer;
        using var otherChart = new TcVisualScene2D();
        var replacement = new NativeSceneView(document, otherChart);
        Require(replacement.IsAlive && !document.IsAlive(oldHandle), "A stale widget handle resolved to a new widget.");
        replacement.Destroy();
        label.Destroy();
        Require(document.LiveWidgetCount == 0, "Native widget bodies leaked after teardown.");
        Console.WriteLine("NATIVE_WIDGET_BINDINGS_OK layout, state, ownership, activation, input, capture and teardown");
    }

    private static NativeUiPointerEvent Pointer(NativeUiPointerEventType type, float x, float y, int button) =>
        new() { Type = type, X = x, Y = y, Button = button, ClickCount = 1 };

    private static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    private static void Throws<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException($"Expected {typeof(T).Name}.");
    }
}
