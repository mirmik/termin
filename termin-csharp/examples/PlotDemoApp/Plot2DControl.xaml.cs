using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using OpenTK.Wpf;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public partial class Plot2DControl : UserControl, IDisposable
{
    private PlotView2D? _view;
    private Tgfx2GlWpfTexturePresenter? _presenter;
    private bool _initialized;
    private bool _disposed;
    private bool _hostLeaseHeld;

    public Plot2DControl()
    {
        InitializeComponent();

        var settings = GlWpfSharedContext.CreateSettings();
        GlControl.Start(settings);
        GlWpfSharedContext.CaptureIfFirst(GlControl);
        GlControl.Render += OnGlRender;

        Unloaded += (_, _) => Dispose();

        GlControl.MouseDown  += OnMouseDownGl;
        GlControl.MouseMove  += OnMouseMoveGl;
        GlControl.MouseUp    += OnMouseUpGl;
        GlControl.MouseWheel += OnMouseWheelGl;
        GlControl.Focusable = true;
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
            _presenter = new Tgfx2GlWpfTexturePresenter();
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

    private void OnGlRender(TimeSpan delta)
    {
        if (!_initialized)
        {
            InitializeNative();
        }
        if (!_initialized || _view == null) return;

        var w = Math.Max(1, GlControl.FrameBufferWidth);
        var h = Math.Max(1, GlControl.FrameBufferHeight);
        uint colorTex = _view.render_to_texture_id(w, h);
        _presenter?.Present(colorTex, w, h, GlControl.Framebuffer);
    }

    private static int ToTcbaseButton(System.Windows.Input.MouseButton b) => b switch
    {
        System.Windows.Input.MouseButton.Left   => 0,
        System.Windows.Input.MouseButton.Right  => 1,
        System.Windows.Input.MouseButton.Middle => 2,
        _ => 0,
    };

    private void OnMouseDownGl(object sender, MouseButtonEventArgs e)
    {
        if (_view == null) return;
        GlControl.Focus();
        var p = e.GetPosition(GlControl);
        _view.on_mouse_down((float)p.X, (float)p.Y, ToTcbaseButton(e.ChangedButton));
        e.Handled = true;
    }

    private void OnMouseMoveGl(object sender, MouseEventArgs e)
    {
        if (_view == null) return;
        var p = e.GetPosition(GlControl);
        _view.on_mouse_move((float)p.X, (float)p.Y);
    }

    private void OnMouseUpGl(object sender, MouseButtonEventArgs e)
    {
        if (_view == null) return;
        var p = e.GetPosition(GlControl);
        _view.on_mouse_up((float)p.X, (float)p.Y, ToTcbaseButton(e.ChangedButton));
        e.Handled = true;
    }

    private void OnMouseWheelGl(object sender, MouseWheelEventArgs e)
    {
        if (_view == null) return;
        var p = e.GetPosition(GlControl);
        _view.on_mouse_wheel((float)p.X, (float)p.Y, e.Delta > 0 ? 1f : -1f);
        e.Handled = true;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        _view?.release_gpu();
        _view?.Dispose();
        _view = null;
        _presenter?.Dispose();
        _presenter = null;
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
