using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;

namespace PlotDemoApp;

// WPF host for tcplot's PlotView2DMulti. Owns the GL surface,
// constructs the native view on first Loaded, forwards WPF mouse
// events, and exposes thin Plot/AppendToLine helpers to the window.
public partial class MultiPlot2DControl : UserControl, IDisposable
{
    private static bool _openglBooted;

    private PlotView2DMulti? _view;
    private bool _initialized;
    private bool _disposed;

    // Set this before the control is first loaded. Changing it later
    // has no effect.
    public int PanelCount { get; set; } = 3;

    // MSAA sample count for the shared offscreen attachment (1 / 2 / 4 / 8).
    // If set after the native view is initialised, the change is
    // propagated immediately; ensure_offscreen_ will reallocate on the
    // next render.
    private int _msaaSamples = 4;
    public int MsaaSamples
    {
        get => _msaaSamples;
        set
        {
            _msaaSamples = Math.Max(1, value);
            if (_view != null) _view.set_msaa_samples(_msaaSamples);
        }
    }

    public event EventHandler? NativeInitialized;

    public PlotView2DMulti View
    {
        get
        {
            if (_view == null)
            {
                throw new InvalidOperationException(
                    "MultiPlot2DControl: native view not initialised yet");
            }
            return _view;
        }
    }

    public bool IsNativeInitialized => _initialized;

    public MultiPlot2DControl()
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

    public int Plot(int panel,
                    double[] x, double[] y,
                    float r = 1f, float g = 1f, float b = 1f, float a = 1f,
                    double thickness = 1.5, string label = "")
    {
        return View.add_line(panel, x, y, (uint)x.Length,
                             r, g, b, a, thickness, label);
    }

    public void AppendToLine(int panel, int series,
                              double[] x, double[] y)
    {
        View.append_to_line(panel, series, x, y, (uint)x.Length);
    }

    public void SetAutoscroll(bool on, double window)
        => View.set_autoscroll(on, window);

    public void SetPanelTitle(int panel, string title)
        => View.set_panel_title(panel, title);

    public void SetPanelYLabel(int panel, string label)
        => View.set_panel_y_label(panel, label);

    public void SetXLabel(string label)
        => View.set_x_label(label);

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

        var ttfPath = Plot3DControl.FindSystemFont()
            ?? throw new InvalidOperationException(
                "No system TTF font found for MultiPlot2DControl.");

        _view = new PlotView2DMulti(ttfPath, PanelCount);
        _view.set_msaa_samples(_msaaSamples);
        _initialized = true;
        NativeInitialized?.Invoke(this, EventArgs.Empty);
    }

    private void OnGlRender(TimeSpan delta)
    {
        if (!_initialized || _view == null) return;

        var w = Math.Max(1, (int)GlControl.ActualWidth);
        var h = Math.Max(1, (int)GlControl.ActualHeight);

        GL.GetInteger(GetPName.DrawFramebufferBinding, out int dstFbo);
        _view.render(w, h, (uint)dstFbo);
    }

    private static int ToTcbaseButton(System.Windows.Input.MouseButton b) => b switch
    {
        System.Windows.Input.MouseButton.Left   => 0,
        System.Windows.Input.MouseButton.Right  => 1,
        System.Windows.Input.MouseButton.Middle => 2,
        _ => 0,
    };

    // WPF MouseMove fires at the mouse's polling rate (often 500–1000 Hz
    // on gaming mice). Every event that crosses into native code costs a
    // P/Invoke + SWIG marshalling round-trip on the UI thread; when
    // hovering without a drag we have nothing useful to do there, so
    // skip the round-trip entirely. _dragging tracks whether a button
    // that the native engine cares about (middle, for pan) is held.
    private bool _dragging;

    private void OnMouseDownGl(object sender, MouseButtonEventArgs e)
    {
        if (_view == null) return;
        GlControl.Focus();
        var p = e.GetPosition(GlControl);
        _view.on_mouse_down((float)p.X, (float)p.Y, ToTcbaseButton(e.ChangedButton));
        if (e.ChangedButton == System.Windows.Input.MouseButton.Middle) {
            _dragging = true;
            GlControl.CaptureMouse();
        }
        e.Handled = true;
    }

    private void OnMouseMoveGl(object sender, MouseEventArgs e)
    {
        if (_view == null || !_dragging) return;
        var p = e.GetPosition(GlControl);
        _view.on_mouse_move((float)p.X, (float)p.Y);
    }

    private void OnMouseUpGl(object sender, MouseButtonEventArgs e)
    {
        if (_view == null) return;
        var p = e.GetPosition(GlControl);
        _view.on_mouse_up((float)p.X, (float)p.Y, ToTcbaseButton(e.ChangedButton));
        if (e.ChangedButton == System.Windows.Input.MouseButton.Middle) {
            _dragging = false;
            GlControl.ReleaseMouseCapture();
        }
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

    ~MultiPlot2DControl() { Dispose(); }
}
