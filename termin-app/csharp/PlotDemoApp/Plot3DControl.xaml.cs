using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;

namespace PlotDemoApp;

// Thin WPF host for a tcplot PlotView3D. The native side owns the
// OpenGL offscreen FBO, the tgfx2 render context, the font atlas,
// and the plot engine; this class only:
//   - boots the GL context (tc_opengl_init) once per process,
//   - forwards the Render tick by calling PlotView3D.render(w, h, fb_id),
//   - translates WPF mouse events into engine calls.
public partial class Plot3DControl : UserControl, IDisposable
{
    private static bool _openglBooted;

    private PlotView3D? _view;
    private bool _initialized;
    private bool _disposed;

    public Plot3DControl()
    {
        InitializeComponent();

        var settings = new GLWpfControlSettings
        {
            MajorVersion = 4,
            MinorVersion = 5,
        };
        GlControl.Start(settings);
        GlControl.Render += OnGlRender;

        Loaded   += (_, _) => InitializeNative();
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

    private void InitializeNative()
    {
        if (_initialized) return;

        TerminCore.InitFull();

        if (!_openglBooted)
        {
            if (!termin.tc_opengl_init())
            {
                throw new InvalidOperationException("tc_opengl_init() failed");
            }
            _openglBooted = true;
        }

        var ttfPath = FindSystemFont()
            ?? throw new InvalidOperationException(
                "No system TTF font found for Plot3DControl.");

        _view = new PlotView3D(ttfPath);
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
        if (!_initialized || _view == null) return;

        var w = Math.Max(1, (int)GlControl.ActualWidth);
        var h = Math.Max(1, (int)GlControl.ActualHeight);

        GL.GetInteger(GetPName.DrawFramebufferBinding, out int dstFbo);
        _view.render(w, h, (uint)dstFbo);
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

        _initialized = false;
        GC.SuppressFinalize(this);
    }

    ~Plot3DControl() { Dispose(); }
}
