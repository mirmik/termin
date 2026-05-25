using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using OpenTK.Wpf;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

// Thin WPF host for a tcplot PlotView3D. Tgfx2Host owns the shared
// tgfx2 runtime; PlotView3D owns only its offscreen target and plot
// engine. This class only:
//   - renders PlotView3D into a tgfx2 texture and hands it to the WPF presenter,
//   - translates WPF mouse events into engine calls.
public partial class Plot3DControl : UserControl, IDisposable
{
    private PlotView3D? _view;
    private Tgfx2GlWpfTexturePresenter? _presenter;
    private bool _initialized;
    private bool _disposed;
    private bool _hostLeaseHeld;

    public Plot3DControl()
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

    public PlotView3D View
    {
        get
        {
            if (_view == null)
            {
                throw new InvalidOperationException(
                    "Plot3DControl: native view not initialised yet");
            }
            return _view;
        }
    }

    public bool IsNativeInitialized => _initialized;

    public event EventHandler? NativeInitialized;

    public void Plot(double[] x, double[] y, double[] z,
                     float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                     double thickness = 1.5, string label = "")
    {
        View.plot(x, y, z, (uint)x.Length, r, g, b, a, thickness, label);
    }

    public void Scatter(double[] x, double[] y, double[] z,
                        float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                        double size = 4.0, string label = "")
    {
        View.scatter(x, y, z, (uint)x.Length, r, g, b, a, size, label);
    }

    public void Surface(double[] X, double[] Y, double[] Z,
                        uint rows, uint cols,
                        float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                        bool wireframe = false, string label = "")
    {
        View.surface(X, Y, Z, rows, cols, r, g, b, a, wireframe, label);
    }

    public void SurfaceColormap(double[] X, double[] Y, double[] Z,
                                uint rows, uint cols,
                                SurfaceColorMap colormap,
                                float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                                bool wireframe = false, string label = "")
    {
        View.surface_colormap(X, Y, Z, rows, cols, colormap,
                              r, g, b, a, wireframe, label);
    }

    public bool SetSurfaceGrid(int surfaceIndex, bool visible,
                               uint rowStep, uint colStep,
                               float r = 0.05f, float g = 0.05f,
                               float b = 0.05f, float a = 1f,
                               float widthPx = 1.5f)
    {
        return View.set_surface_grid(surfaceIndex, visible,
                                     rowStep, colStep,
                                     r, g, b, a,
                                     widthPx);
    }

    public void SetAxisScale(float x, float y, float z)
    {
        View.set_axis_scale(x, y, z);
    }

    public void SetAxisLabels(string x, string y, string z)
    {
        View.set_axis_labels(x, y, z);
    }

    public void SetSurfaceShading(bool enabled, float strength = 0.35f)
    {
        View.set_surface_shading(enabled, strength);
    }

    public void SetSurfaceLightDir(float x, float y, float z)
    {
        View.set_surface_light_dir(x, y, z);
    }

    private void InitializeNative()
    {
        if (_initialized) return;

        TerminCore.InitFull();

        var ttfPath = FindSystemFont()
            ?? throw new InvalidOperationException(
                "No system TTF font found for Plot3DControl.");

        var host = Tgfx2Host.Acquire(ttfPath);
        try
        {
            _view = new PlotView3D(host);
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

    internal static string? FindSystemFont()
    {
        if (OperatingSystem.IsWindows())
        {
            var fontsDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "Fonts");
            foreach (var name in new[] { "segoeui.ttf", "arial.ttf", "tahoma.ttf" })
            {
                var p = Path.Combine(fontsDir, name);
                if (File.Exists(p)) return p;
            }
        }
        else
        {
            foreach (var p in new[] {
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            })
            {
                if (File.Exists(p)) return p;
            }
        }
        return null;
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

    // MouseButton int values match tcbase::MouseButton: LEFT=0, RIGHT=1, MIDDLE=2.
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

    ~Plot3DControl() { Dispose(); }
}
