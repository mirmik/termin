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

    // Optional explicit TTF path. Null → auto-pick via
    // Plot3DControl.FindSystemFont (segoeui on Windows). Handy when
    // you want to pin the font regardless of the host OS's defaults.
    public string? FontPath { get; set; }

    // Fixed panel height for virtualised scrolling. 0 (default) keeps
    // the classic "divide render height evenly" behaviour. Set once
    // before data starts flowing; changing later requires re-layout
    // which happens on the next render() anyway.
    public static readonly DependencyProperty PanelHeightProperty =
        DependencyProperty.Register(
            nameof(PanelHeight), typeof(double), typeof(MultiPlot2DControl),
            new PropertyMetadata(0.0, OnPanelHeightChanged));
    public double PanelHeight
    {
        get => (double)GetValue(PanelHeightProperty);
        set => SetValue(PanelHeightProperty, value);
    }
    private static void OnPanelHeightChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var self = (MultiPlot2DControl)d;
        if (self._view != null)
        {
            self._view.set_panel_height((float)(double)e.NewValue);
            self.UpdateMaxScroll();
        }
    }

    // Virtual scroll offset in pixels. Bind this to a WPF ScrollBar.Value.
    public static readonly DependencyProperty ScrollOffsetProperty =
        DependencyProperty.Register(
            nameof(ScrollOffset), typeof(double), typeof(MultiPlot2DControl),
            new PropertyMetadata(0.0, OnScrollOffsetChanged));
    public double ScrollOffset
    {
        get => (double)GetValue(ScrollOffsetProperty);
        set => SetValue(ScrollOffsetProperty, value);
    }
    private static void OnScrollOffsetChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var self = (MultiPlot2DControl)d;
        self._view?.set_scroll_offset((float)(double)e.NewValue);
    }

    // Read-only: the max scroll offset, updated whenever the control's
    // height or panel layout changes. Binds naturally to ScrollBar.Maximum.
    private static readonly DependencyPropertyKey MaxScrollPropertyKey =
        DependencyProperty.RegisterReadOnly(
            nameof(MaxScroll), typeof(double), typeof(MultiPlot2DControl),
            new PropertyMetadata(0.0));
    public static readonly DependencyProperty MaxScrollProperty =
        MaxScrollPropertyKey.DependencyProperty;
    public double MaxScroll => (double)GetValue(MaxScrollProperty);

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

        string ttfPath;
        if (!string.IsNullOrEmpty(FontPath) && File.Exists(FontPath))
        {
            ttfPath = FontPath;
        }
        else
        {
            ttfPath = Plot3DControl.FindSystemFont()
                ?? throw new InvalidOperationException(
                    "No system TTF font found for MultiPlot2DControl.");
        }
        System.Diagnostics.Debug.WriteLine(
            $"MultiPlot2DControl: loading font {ttfPath}");

        _view = new PlotView2DMulti(ttfPath, PanelCount);
        _view.set_msaa_samples(_msaaSamples);
        if (PanelHeight > 0)
        {
            _view.set_panel_height((float)PanelHeight);
            _view.set_scroll_offset((float)ScrollOffset);
            UpdateMaxScroll();
        }
        SizeChanged += (_, _) => UpdateMaxScroll();
        _initialized = true;
        NativeInitialized?.Invoke(this, EventArgs.Empty);
    }

    private void OnGlRender(TimeSpan delta)
    {
        if (!_initialized || _view == null) return;

        var w = Math.Max(1, (int)GlControl.ActualWidth);
        var h = Math.Max(1, (int)GlControl.ActualHeight);

        // Apply coalesced pan from the latest MouseMove before rendering.
        if (_hasPendingPan && _dragging)
        {
            _view.on_mouse_move(_pendingPanX, _pendingPanY);
            _hasPendingPan = false;
        }

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

    // Pan coalesced to render tick. Sending a native on_mouse_move per
    // WPF MouseMove amplifies input-routing cost through the visual
    // tree (WPF tunnels/bubbles each event through the whole parent
    // chain even with MouseCapture). We record the latest position on
    // each event and apply it exactly once per OnGlRender frame —
    // this cuts frame_dt roughly in half in a deep WPF window.
    private float _pendingPanX;
    private float _pendingPanY;
    private bool  _hasPendingPan;

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
        _pendingPanX = (float)p.X;
        _pendingPanY = (float)p.Y;
        _hasPendingPan = true;
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
        // In virtualised/scrollable mode, plain wheel scrolls the list
        // and Ctrl+wheel zooms the X axis — matches the ubiquitous
        // "document vs. content" mousewheel convention. Classic (non-
        // virtualised) mode still zooms unconditionally.
        bool scrollable = PanelHeight > 0 && MaxScroll > 0;
        bool wantZoom = !scrollable
            || (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control;
        if (wantZoom)
        {
            var p = e.GetPosition(GlControl);
            float dy = e.Delta > 0 ? 1f : -1f;
            // Ctrl held → zoom X only (shared-X dashboard convention).
            // Plain wheel in non-scrollable mode zooms both axes as before.
            bool ctrl = (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control;
            if (ctrl)
                _view.on_mouse_wheel_x((float)p.X, (float)p.Y, dy);
            else
                _view.on_mouse_wheel((float)p.X, (float)p.Y, dy);
        }
        else
        {
            // One wheel notch ≈ one third of a panel. Tuned so flicking
            // the wheel moves the viewport at a readable pace instead
            // of teleporting by whole panels per tick.
            double step = Math.Max(PanelHeight * 0.33, 24.0);
            double delta = -Math.Sign(e.Delta) * step;
            double next = ScrollOffset + delta;
            if (next < 0) next = 0;
            if (next > MaxScroll) next = MaxScroll;
            ScrollOffset = next;
        }
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

    // Recompute max scroll from the current native total_virtual_height
    // and the control's actual on-screen height. Called on resize and
    // whenever PanelHeight changes.
    private void UpdateMaxScroll()
    {
        if (_view == null) return;
        double total = _view.total_virtual_height();
        double visible = Math.Max(1.0, ActualHeight);
        double max = Math.Max(0.0, total - visible);
        SetValue(MaxScrollPropertyKey, max);
        if (ScrollOffset > max) ScrollOffset = max;
    }
}
