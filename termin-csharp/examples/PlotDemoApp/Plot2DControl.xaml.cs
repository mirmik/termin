using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public partial class Plot2DControl : UserControl, IDisposable
{
    private Chart2D? _chart;
    private Chart2DWpfInteraction? _interaction;
    private bool _hostLeaseHeld;
    private bool _disposed;
    private bool _smokeBootstrapPresented;
    private int _frameWidth;
    private int _frameHeight;

    internal int SmokeBootstrapSize { get; set; }
    internal bool HasPresentedCurrentSize =>
        _smokeBootstrapPresented &&
        PresentedWidth == SceneHost.RenderHost.FramebufferWidth &&
        PresentedHeight == SceneHost.RenderHost.FramebufferHeight &&
        PresentedFramesAtSize >= 2;
    internal int PresentedWidth { get; private set; }
    internal int PresentedHeight { get; private set; }
    internal int PresentedFramesAtSize { get; private set; }
    internal string SmokeRenderDiagnostics =>
        $"framebuffer={_frameWidth}x{_frameHeight} " +
        $"presented={PresentedWidth}x{PresentedHeight} framesAtSize={PresentedFramesAtSize} " +
        $"bootstrapPresented={_smokeBootstrapPresented} disposed={_disposed}";

    public Plot2DControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    public Chart2D Chart => _chart ??
        throw new InvalidOperationException("The retained 2D chart is not initialized.");

    public event EventHandler? NativeInitialized;

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Loaded -= OnLoaded;
        GpuHost host = Tgfx2Host.Acquire(App.FindSystemFont());
        _hostLeaseHeld = true;
        try
        {
            _chart = new Chart2D(host, 1, 1, new PlotRange2D(0, 1, -1, 1));
            SceneHost.FramebufferChanged += OnFramebufferChanged;
            SceneHost.RenderFailed += App.LogRenderFailure;
            if (SmokeBootstrapSize > 0)
            {
                DpiScale dpi = VisualTreeHelper.GetDpi(this);
                // Framebuffer dimensions are rounded up to physical pixels.
                Width = (SmokeBootstrapSize - 0.25) / dpi.DpiScaleX;
                Height = (SmokeBootstrapSize - 0.25) / dpi.DpiScaleY;
                SceneHost.ContinuousRendering = true;
                SceneHost.FrameRendered += OnSmokeFrameRendered;
            }
            SceneHost.Attach(host, _chart.Scene);
            _interaction = new Chart2DWpfInteraction(SceneHost, _chart);
            NativeInitialized?.Invoke(this, EventArgs.Empty);
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    private void OnFramebufferChanged(
        object? sender, RetainedSceneFramebufferChangedEventArgs e)
    {
        _frameWidth = e.Width;
        _frameHeight = e.Height;
        Chart.Resize(e.Width, e.Height, e.PixelScale);
    }

    private void OnSmokeFrameRendered(
        object? sender, RetainedSceneFrameRenderedEventArgs e)
    {
        PresentedFramesAtSize = PresentedWidth == _frameWidth && PresentedHeight == _frameHeight
            ? PresentedFramesAtSize + 1 : 1;
        PresentedWidth = _frameWidth;
        PresentedHeight = _frameHeight;
        if (_smokeBootstrapPresented ||
            PresentedWidth != SmokeBootstrapSize || PresentedHeight != SmokeBootstrapSize)
            return;

        _smokeBootstrapPresented = true;
        Console.WriteLine($"PLOT_2D_HOST_BOOTSTRAP {PresentedWidth}x{PresentedHeight}");
        ClearValue(WidthProperty);
        ClearValue(HeightProperty);
    }

    private void OnUnloaded(object sender, RoutedEventArgs e) => Dispose();

    public void Dispose()
    {
        if (_disposed)
            return;
        Dispatcher.VerifyAccess();
        _disposed = true;
        Loaded -= OnLoaded;
        Unloaded -= OnUnloaded;
        _interaction?.Dispose();
        SceneHost.Dispose();
        _chart?.Dispose();
        _chart = null;
        if (_hostLeaseHeld)
        {
            Tgfx2Host.Release();
            _hostLeaseHeld = false;
        }
    }
}
