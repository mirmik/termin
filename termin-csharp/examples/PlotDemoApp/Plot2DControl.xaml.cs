using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public partial class Plot2DControl : UserControl, IDisposable
{
    private PlotView2D? _view;
    private bool _renderingSubscribed;
    private bool _initialized;
    private bool _disposed;
    private bool _hostLeaseHeld;

    public Plot2DControl()
    {
        InitializeComponent();

        CompositionTarget.Rendering += OnRender;
        _renderingSubscribed = true;

        Unloaded += (_, _) => Dispose();

        RenderHost.FramebufferMouseDown  += OnFramebufferMouseDown;
        RenderHost.FramebufferMouseMove  += OnFramebufferMouseMove;
        RenderHost.FramebufferMouseUp    += OnFramebufferMouseUp;
        RenderHost.FramebufferMouseWheel += OnFramebufferMouseWheel;
        RenderHost.Focusable = true;
    }

    public PlotView2D View
    {
        get
        {
            if (_view == null)
            {
                throw new InvalidOperationException(
                    "Plot2DControl: native view not initialised yet");
            }
            return _view;
        }
    }

    public bool IsNativeInitialized => _initialized;
    public event EventHandler? NativeInitialized;

    public void Plot(double[] x, double[] y,
                     float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                     double thickness = 1.5, string label = "")
    {
        View.plot(x, y, (uint)x.Length, r, g, b, a, thickness, label);
    }

    public void PlotColormap(double[] x, double[] y, double[] scalar,
                             SurfaceColorMap colormap = SurfaceColorMap.Jet,
                             double scalarMin = 0.0, double scalarMax = 1.0,
                             double thickness = 1.5, string label = "",
                             bool colormapReversed = false)
    {
        View.plot_colormap(x, y, scalar, (uint)x.Length, colormap,
            scalarMin, scalarMax, thickness, label, colormapReversed);
    }

    public void Scatter(double[] x, double[] y,
                        float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                        double size = 4.0, string label = "")
    {
        View.scatter(x, y, (uint)x.Length, r, g, b, a, size, label);
    }

    public void SetLineStyle(int series, LineStyle style,
                             float dashPx = 8.0f, float gapPx = 5.0f)
    {
        View.set_line_style(series, style, dashPx, gapPx);
    }

    private void InitializeNative()
    {
        if (_initialized) return;

        TerminCore.InitFull();

        var ttfPath = Plot3DControl.FindSystemFont()
            ?? throw new InvalidOperationException(
                "No system TTF font found for Plot2DControl.");

        var host = Tgfx2Host.Acquire(ttfPath);
        try
        {
            _view = new PlotView2D(host);
            _hostLeaseHeld = true;
        }
        catch
        {
            Tgfx2Host.Release();
            throw;
        }
        _initialized = true;
        NativeInitialized?.Invoke(this, EventArgs.Empty);
    }

    private void OnRender(object? sender, EventArgs e)
    {
        if (!_initialized)
        {
            InitializeNative();
        }
        if (!_initialized || _view == null) return;

        var w = Math.Max(1, RenderHost.FramebufferWidth);
        var h = Math.Max(1, RenderHost.FramebufferHeight);
        uint colorTex = _view.render_to_texture_handle_id(w, h);
        _ = RenderHost.Present(colorTex, w, h);
    }

    private void OnFramebufferMouseDown(object? sender, Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_view == null) return;
        RenderHost.FocusNativeWindow();
        _view.on_mouse_down(e.X, e.Y, e.Button);
        e.Handled = true;
    }

    private void OnFramebufferMouseMove(object? sender, Tgfx2D3D11MouseMoveEventArgs e)
    {
        if (_view == null) return;
        _view.on_mouse_move(e.X, e.Y);
    }

    private void OnFramebufferMouseUp(object? sender, Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_view == null) return;
        _view.on_mouse_up(e.X, e.Y, e.Button);
        e.Handled = true;
    }

    private void OnFramebufferMouseWheel(object? sender, Tgfx2D3D11MouseWheelEventArgs e)
    {
        if (_view == null) return;
        _view.on_mouse_wheel(e.X, e.Y, e.Delta > 0 ? 1f : -1f);
        e.Handled = true;
    }
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        if (_renderingSubscribed)
        {
            CompositionTarget.Rendering -= OnRender;
            _renderingSubscribed = false;
        }

        RenderHost.ReleaseNativeResources();

        _view?.release_gpu();
        _view?.Dispose();
        _view = null;
        if (_hostLeaseHeld)
        {
            Tgfx2Host.Release();
            _hostLeaseHeld = false;
        }
        _initialized = false;
        GC.SuppressFinalize(this);
    }

    ~Plot2DControl() { Dispose(); }
}
