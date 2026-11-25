using System.Windows;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public sealed partial class NativeChartDocumentWindow : Window
{
    private readonly NativeDocumentHost _host = new() { ContinuousRendering = false };
    private readonly NativeUiDocument _document;
    private readonly Chart2D _chart;
    private readonly NativeSceneView _chartView;
    private readonly NativeButton _button;
    private readonly NativeLabel _status;
    private readonly ChartLineSeries2D _sine;
    private readonly ChartLineSeries2D _cosine;
    private int _activations;
    private int _presentedFrames;
    private Exception? _renderError;
    private bool _closed;

    public NativeChartDocumentWindow()
    {
        Title = "2D chart in a native UI document";
        Width = 900;
        Height = 620;
        MinWidth = 460;
        MinHeight = 300;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Content = _host;

        string fontPath = App.FindSystemFont();
        GpuHost host = Tgfx2Host.Acquire(fontPath);
        NativeUiDocument? document = null;
        Chart2D? chart = null;
        try
        {
            _document = document = new NativeUiDocument("Native chart document");
            _chart = chart = new Chart2D(host, 1, 1, new PlotRange2D(0, 4 * Math.PI, -1.2, 1.2));
            _chart.TitleText = "Retained Chart2D";
            _chart.XAxisText = "Phase, rad";
            _chart.YAxisText = "Amplitude";
            double[] x = Enumerable.Range(0, 512).Select(i => i * 4 * Math.PI / 511).ToArray();
            _sine = _chart.AddLineSeries("Sine", x, x.Select(Math.Sin).ToArray(),
                style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(0.18f, 0.63f, 1f), thicknessPx: 3));
            _cosine = _chart.AddLineSeries("Cosine", x, x.Select(Math.Cos).ToArray(),
                style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(1f, 0.67f, 0.19f), thicknessPx: 3));
            _cosine.Visible = false;

            var root = new NativeBoxLayout(_document) { Spacing = 6 };
            var toolbar = new NativeBoxLayout(_document, vertical: false) { Spacing = 12 };
            _button = new NativeButton(_document, "Switch signal");
            _status = new NativeLabel(_document, SignalStatus(showCosine: false));
            _chartView = new NativeSceneView(_document, _chart.Scene)
            {
                ShowGrid = false,
                NavigationEnabled = false,
                PointerHandler = OnChartPointer,
            };
            toolbar.AddChild(_button, NativeBoxSizing.Fixed, 148);
            toolbar.AddChild(_status);
            root.AddChild(toolbar, NativeBoxSizing.Fixed, 38);
            root.AddChild(_chartView);
            _document.AddRoot(root.Handle);

            _button.Clicked += OnSwitchSignal;
            _host.LayoutPrepared += OnLayoutPrepared;
            _host.FrameRendered += OnFrameRendered;
            _host.RenderFailed += OnRenderFailed;
            _host.Attach(host, _document, fontPath);
        }
        catch
        {
            DisposeResources(document, chart);
            throw;
        }
    }

    private static string SignalStatus(bool showCosine) =>
        $"Showing {(showCosine ? "cosine" : "sine")}  |  Middle drag to pan  |  Wheel to zoom";

    private void OnSwitchSignal(object? sender, EventArgs e)
    {
        bool showCosine = (++_activations % 2) != 0;
        _sine.Visible = !showCosine;
        _cosine.Visible = showCosine;
        _status.Text = SignalStatus(showCosine);
        _host.RequestRender();
    }

    private void OnLayoutPrepared(object? sender, EventArgs e)
    {
        NativeUiRect bounds = _chartView.Bounds;
        PlotRect2D viewport = _chart.Layout.Viewport;
        if (bounds.Width > 0 && bounds.Height > 0 &&
            (bounds.Width != viewport.Width || bounds.Height != viewport.Height))
        {
            // SceneView uses document units. The document renderer applies the
            // platform density to both the chart and sibling native widgets.
            _chart.Resize(bounds.Width, bounds.Height, pixelScale: 1);
        }
    }

    private bool OnChartPointer(NativeUiPointerEvent pointer)
    {
        ChartInteraction2D interaction = _chart.Interaction;
        switch (pointer.Type)
        {
            case NativeUiPointerEventType.Down:
                return interaction.PointerDown(pointer.X, pointer.Y, pointer.Button);
            case NativeUiPointerEventType.Move:
                return interaction.PointerMove(pointer.X, pointer.Y);
            case NativeUiPointerEventType.Up:
                return interaction.PointerUp(pointer.X, pointer.Y, pointer.Button);
            case NativeUiPointerEventType.Wheel:
                return interaction.Wheel(pointer.X, pointer.Y, pointer.WheelY,
                    xOnly: (pointer.Modifiers & NativeUiModifiers.Control) != 0);
            case NativeUiPointerEventType.Cancel:
                interaction.Cancel();
                return true;
            default:
                return false;
        }
    }

    private void OnFrameRendered(object? sender, EventArgs e) => ++_presentedFrames;

    private void OnRenderFailed(object? sender, NativeDocumentRenderFailedEventArgs e) =>
        _renderError = e.Error;

    protected override void OnClosed(EventArgs e)
    {
        _closed = true;
        _host.LayoutPrepared -= OnLayoutPrepared;
        _host.FrameRendered -= OnFrameRendered;
        _host.RenderFailed -= OnRenderFailed;
        try
        {
            DisposeResources(_document, _chart);
        }
        finally
        {
            base.OnClosed(e);
        }
    }

    private void DisposeResources(NativeUiDocument? document, Chart2D? chart)
    {
        try
        {
            _host.Dispose();
        }
        finally
        {
            try
            {
                document?.Dispose();
            }
            finally
            {
                try
                {
                    chart?.Dispose();
                }
                finally
                {
                    Tgfx2Host.Release();
                }
            }
        }
    }
}
