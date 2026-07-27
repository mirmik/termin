using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using Termin.Native;

namespace Termin.Wpf;

public sealed class Tgfx2D3D11ImageHost : Image, IDisposable
{
    private readonly D3DImage _image = new();
    private IntPtr _bridge;
    private int _framebufferWidth;
    private int _framebufferHeight;
    private bool _backBufferSet;
    private bool _disposed;
    private ulong _presentCount;
#if !TERMIN_CSHARP_PLOT_ONLY
    private TcDisplayHandle _display = TcDisplayHandle.Invalid;
#endif

    public Tgfx2D3D11ImageHost()
    {
        Source = _image;
        Stretch = Stretch.Fill;
        Focusable = true;
        IsHitTestVisible = true;
        SnapsToDevicePixels = true;

        MouseDown += OnMouseDown;
        MouseMove += OnMouseMove;
        MouseUp += OnMouseUp;
        MouseWheel += OnMouseWheel;
        KeyDown += OnKeyDown;
        KeyUp += OnKeyUp;
        TextInput += OnTextInput;
        Trace("constructed");
    }

    public event EventHandler<Tgfx2D3D11MouseButtonEventArgs>? FramebufferMouseDown;
    public event EventHandler<Tgfx2D3D11MouseButtonEventArgs>? FramebufferMouseUp;
    public event EventHandler<Tgfx2D3D11MouseMoveEventArgs>? FramebufferMouseMove;
    public event EventHandler<Tgfx2D3D11MouseWheelEventArgs>? FramebufferMouseWheel;

    public int FramebufferWidth => GetFramebufferSize().Width;
    public int FramebufferHeight => GetFramebufferSize().Height;

    public void FocusNativeWindow()
    {
        Focus();
        Keyboard.Focus(this);
    }

    public void ReleaseNativeResources()
    {
#if !TERMIN_CSHARP_PLOT_ONLY
        UnbindDisplay();
#endif
        ReleaseBridge();
    }

#if !TERMIN_CSHARP_PLOT_ONLY
    /// <summary>
    /// Binds a non-owning display handle. The display owner must unbind or
    /// dispose this host before destroying the display.
    /// </summary>
    public void BindDisplay(TcDisplayHandle display)
    {
        ThrowIfDisposed();
        if (!display.IsValid || !TerminCore.DisplayAlive(display))
        {
            throw new ArgumentException("Display handle is not alive.", nameof(display));
        }
        nuint domain = TerminCore.Tgfx2GetGraphicsDomainKey();
        if (domain == 0
            || !TerminCore.DisplayValidateOutput(display, domain, out uint texture)
            || texture == 0)
        {
            throw new InvalidOperationException(
                "The display output does not belong to the active graphics domain. " +
                "See the native log.");
        }

        _display = display;
        PrepareDisplay();
        Trace($"bound display={display}");
    }

    public void UnbindDisplay()
    {
        if (_display.IsValid)
        {
            Trace($"unbound display={_display}");
            _display = TcDisplayHandle.Invalid;
        }
    }

    /// <summary>Resizes the bound display to the WPF framebuffer in pixels.</summary>
    public void PrepareDisplay()
    {
        ThrowIfDisposed();
        if (!_display.IsValid || !TerminCore.DisplayAlive(_display))
        {
            throw new InvalidOperationException("No live display is bound.");
        }

        SizeInPixels size = GetFramebufferSize();
        TerminCore.DisplayGetSize(_display, out int width, out int height);
        if ((width != size.Width || height != size.Height)
            && !TerminCore.DisplayResize(_display, size.Width, size.Height))
        {
            throw new InvalidOperationException(
                $"Failed to resize display to {size.Width}x{size.Height}. See the native log.");
        }
    }

    /// <summary>Presents the color texture of the bound display.</summary>
    public bool PresentDisplay(uint syncInterval = 1)
    {
        PrepareDisplay();
        TerminCore.DisplayGetSize(_display, out int width, out int height);
        uint texture = TerminCore.DisplayGetColorTextureId(_display);
        if (texture == 0)
        {
            Trace($"bound display returned a null color texture display={_display}");
            return false;
        }
        return Present(texture, width, height, syncInterval);
    }
#endif

    public bool Present(uint sourceTextureHandle, int width, int height, uint syncInterval = 1)
    {
        _ = syncInterval;
        ++_presentCount;
        if (_disposed || sourceTextureHandle == 0 || width <= 0 || height <= 0)
        {
            Trace($"present skipped invalid disposed={_disposed} src={sourceTextureHandle} size={width}x{height}");
            return false;
        }
        if (!_image.IsFrontBufferAvailable)
        {
            Trace($"present skipped front-buffer-unavailable src={sourceTextureHandle} size={width}x{height}");
            return false;
        }

        EnsureBridge(width, height);
        if (_bridge == IntPtr.Zero)
        {
            return false;
        }

        _image.Lock();
        try
        {
            if (TerminCore.Tgfx2PresentD3D11D3DImageBridge(_bridge, sourceTextureHandle) == 0)
            {
                Trace($"native present failed frame={_presentCount} bridge=0x{_bridge.ToInt64():X} src={sourceTextureHandle} size={width}x{height}");
                return false;
            }

            _image.AddDirtyRect(new Int32Rect(0, 0, width, height));
            if (TraceEnabled && (_presentCount <= 8 || (_presentCount % 120) == 0))
            {
                Trace($"present ok frame={_presentCount} bridge=0x{_bridge.ToInt64():X} src={sourceTextureHandle} size={width}x{height}");
            }
            return true;
        }
        finally
        {
            _image.Unlock();
        }
    }

    protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
    {
        base.OnRenderSizeChanged(sizeInfo);
#if !TERMIN_CSHARP_PLOT_ONLY
        if (_display.IsValid && TerminCore.DisplayAlive(_display))
        {
            PrepareDisplay();
        }
#endif
        if (_bridge == IntPtr.Zero)
        {
            return;
        }

        SizeInPixels size = GetFramebufferSize();
        if (size.Width == _framebufferWidth && size.Height == _framebufferHeight)
        {
            return;
        }

        ResizeBridge(size.Width, size.Height);
    }

    protected override void OnVisualParentChanged(DependencyObject oldParent)
    {
        base.OnVisualParentChanged(oldParent);
        if (VisualParent == null)
        {
            ReleaseBridge();
        }
    }

    private void EnsureBridge(int width, int height)
    {
        if (_bridge == IntPtr.Zero)
        {
            Trace($"creating bridge size={width}x{height}");
            _bridge = TerminCore.Tgfx2CreateD3D11D3DImageBridge((uint)width, (uint)height);
            if (_bridge == IntPtr.Zero)
            {
                throw new InvalidOperationException(
                    "Tgfx2D3D11ImageHost: failed to create D3DImage bridge. See native log for details.");
            }

            _framebufferWidth = width;
            _framebufferHeight = height;
            Trace($"bridge created ptr=0x{_bridge.ToInt64():X} size={width}x{height}");
            SetBackBufferFromBridge();
            return;
        }

        if (_framebufferWidth == width && _framebufferHeight == height)
        {
            return;
        }

        ResizeBridge(width, height);
    }

    private void ResizeBridge(int width, int height)
    {
        if (_bridge == IntPtr.Zero)
        {
            return;
        }

        Trace($"resizing bridge ptr=0x{_bridge.ToInt64():X} from={_framebufferWidth}x{_framebufferHeight} to={width}x{height}");
        ClearBackBuffer();
        if (TerminCore.Tgfx2ResizeD3D11D3DImageBridge(_bridge, (uint)width, (uint)height) == 0)
        {
            throw new InvalidOperationException(
                "Tgfx2D3D11ImageHost: failed to resize D3DImage bridge. See native log for details.");
        }

        _framebufferWidth = width;
        _framebufferHeight = height;
        SetBackBufferFromBridge();
    }

    private void SetBackBufferFromBridge()
    {
        IntPtr surface = TerminCore.Tgfx2GetD3D11D3DImageSurface(_bridge);
        if (surface == IntPtr.Zero)
        {
            throw new InvalidOperationException(
                "Tgfx2D3D11ImageHost: D3DImage bridge returned a null D3D9 surface.");
        }

        _image.Lock();
        try
        {
            _image.SetBackBuffer(D3DResourceType.IDirect3DSurface9, surface);
            _backBufferSet = true;
            Trace($"set backbuffer bridge=0x{_bridge.ToInt64():X} surface=0x{surface.ToInt64():X} size={_framebufferWidth}x{_framebufferHeight}");
        }
        finally
        {
            _image.Unlock();
        }
    }

    private void ClearBackBuffer()
    {
        if (!_backBufferSet)
        {
            return;
        }

        _image.Lock();
        try
        {
            _image.SetBackBuffer(D3DResourceType.IDirect3DSurface9, IntPtr.Zero);
            _backBufferSet = false;
            Trace($"clear backbuffer bridge=0x{_bridge.ToInt64():X}");
        }
        finally
        {
            _image.Unlock();
        }
    }

    private void ReleaseBridge()
    {
        ClearBackBuffer();
        if (_bridge != IntPtr.Zero)
        {
            Trace($"destroy bridge ptr=0x{_bridge.ToInt64():X}");
            TerminCore.Tgfx2DestroyD3D11D3DImageBridge(_bridge);
            _bridge = IntPtr.Zero;
        }
        _framebufferWidth = 0;
        _framebufferHeight = 0;
    }

    private SizeInPixels GetFramebufferSize()
    {
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        int width = Math.Max(1, (int)Math.Ceiling(RenderSize.Width * dpi.DpiScaleX));
        int height = Math.Max(1, (int)Math.Ceiling(RenderSize.Height * dpi.DpiScaleY));
        return new SizeInPixels(width, height);
    }

    private PointInPixels GetMousePoint(MouseEventArgs e)
    {
        Point p = e.GetPosition(this);
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        return new PointInPixels(
            (float)(p.X * dpi.DpiScaleX),
            (float)(p.Y * dpi.DpiScaleY));
    }

    private static int ToTcbaseButton(System.Windows.Input.MouseButton button) => button switch
    {
        System.Windows.Input.MouseButton.Left => 0,
        System.Windows.Input.MouseButton.Right => 1,
        System.Windows.Input.MouseButton.Middle => 2,
        System.Windows.Input.MouseButton.XButton1 => 3,
        System.Windows.Input.MouseButton.XButton2 => 4,
        _ => -1,
    };

    private void OnMouseDown(object sender, MouseButtonEventArgs e)
    {
        FocusNativeWindow();
        PointInPixels point = GetMousePoint(e);
        int button = ToTcbaseButton(e.ChangedButton);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, button);
        bool dispatched = false;
#if !TERMIN_CSHARP_PLOT_ONLY
        dispatched = button >= 0 && _display.IsValid
            && TerminCore.DisplayDispatchPointerButton(
                _display, point.X, point.Y, button, 1, GetModifiers(), (uint)e.ClickCount);
#endif
        FramebufferMouseDown?.Invoke(this, args);
        if (dispatched || args.Handled)
        {
            CaptureMouse();
            e.Handled = true;
        }
    }

    private void OnMouseMove(object sender, MouseEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseMoveEventArgs(point.X, point.Y);
        bool dispatched = false;
#if !TERMIN_CSHARP_PLOT_ONLY
        dispatched = _display.IsValid
            && TerminCore.DisplayDispatchPointerMove(_display, point.X, point.Y);
#endif
        FramebufferMouseMove?.Invoke(this, args);
        if (dispatched || args.Handled)
        {
            e.Handled = true;
        }
    }

    private void OnMouseUp(object sender, MouseButtonEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        int button = ToTcbaseButton(e.ChangedButton);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, button);
        bool dispatched = false;
#if !TERMIN_CSHARP_PLOT_ONLY
        dispatched = button >= 0 && _display.IsValid
            && TerminCore.DisplayDispatchPointerButton(
                _display, point.X, point.Y, button, 0, GetModifiers(), (uint)e.ClickCount);
#endif
        FramebufferMouseUp?.Invoke(this, args);
        if (dispatched || args.Handled)
        {
            ReleaseMouseCapture();
            e.Handled = true;
        }
    }

    private void OnMouseWheel(object sender, MouseWheelEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseWheelEventArgs(point.X, point.Y, e.Delta);
        bool dispatched = false;
#if !TERMIN_CSHARP_PLOT_ONLY
        dispatched = _display.IsValid
            && TerminCore.DisplayDispatchWheel(
                _display, point.X, point.Y, 0.0, e.Delta / 120.0, GetModifiers());
#endif
        FramebufferMouseWheel?.Invoke(this, args);
        if (dispatched || args.Handled)
        {
            e.Handled = true;
        }
    }

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
#if !TERMIN_CSHARP_PLOT_ONLY
        if (!_display.IsValid)
        {
            return;
        }
        int key = ToTcbaseKey(e.Key);
        e.Handled = TerminCore.DisplayDispatchKey(
            _display,
            key,
            KeyInterop.VirtualKeyFromKey(e.Key),
            e.IsRepeat ? 2 : 1,
            GetModifiers());
#endif
    }

    private void OnKeyUp(object sender, KeyEventArgs e)
    {
#if !TERMIN_CSHARP_PLOT_ONLY
        if (!_display.IsValid)
        {
            return;
        }
        e.Handled = TerminCore.DisplayDispatchKey(
            _display,
            ToTcbaseKey(e.Key),
            KeyInterop.VirtualKeyFromKey(e.Key),
            0,
            GetModifiers());
#endif
    }

    private void OnTextInput(object sender, TextCompositionEventArgs e)
    {
#if !TERMIN_CSHARP_PLOT_ONLY
        if (!_display.IsValid || string.IsNullOrEmpty(e.Text))
        {
            return;
        }

        bool dispatched = false;
        for (int i = 0; i < e.Text.Length; ++i)
        {
            uint codepoint;
            if (char.IsHighSurrogate(e.Text[i])
                && i + 1 < e.Text.Length
                && char.IsLowSurrogate(e.Text[i + 1]))
            {
                codepoint = (uint)char.ConvertToUtf32(e.Text[i], e.Text[++i]);
            }
            else if (!char.IsSurrogate(e.Text[i]))
            {
                codepoint = e.Text[i];
            }
            else
            {
                continue;
            }
            dispatched |= TerminCore.DisplayDispatchText(_display, codepoint);
        }
        e.Handled = dispatched;
#endif
    }

    private static int GetModifiers()
    {
        int mods = 0;
        if ((Keyboard.Modifiers & ModifierKeys.Shift) != 0) mods |= 0x0001;
        if ((Keyboard.Modifiers & ModifierKeys.Control) != 0) mods |= 0x0002;
        if ((Keyboard.Modifiers & ModifierKeys.Alt) != 0) mods |= 0x0004;
        if (Keyboard.IsKeyDown(Key.LWin) || Keyboard.IsKeyDown(Key.RWin)) mods |= 0x0008;
        if (Keyboard.IsKeyToggled(Key.CapsLock)) mods |= 0x0010;
        if (Keyboard.IsKeyToggled(Key.NumLock)) mods |= 0x0020;
        return mods;
    }

    private static int ToTcbaseKey(Key key)
    {
        if (key >= Key.A && key <= Key.Z) return 65 + key - Key.A;
        if (key >= Key.D0 && key <= Key.D9) return 48 + key - Key.D0;
        if (key >= Key.NumPad0 && key <= Key.NumPad9) return 320 + key - Key.NumPad0;
        if (key >= Key.F1 && key <= Key.F12) return 290 + key - Key.F1;

        return key switch
        {
            Key.Space => 32,
            Key.Escape => 256,
            Key.Enter => 257,
            Key.Tab => 258,
            Key.Back => 259,
            Key.Insert => 260,
            Key.Delete => 261,
            Key.Right => 262,
            Key.Left => 263,
            Key.Down => 264,
            Key.Up => 265,
            Key.PageUp => 266,
            Key.PageDown => 267,
            Key.Home => 268,
            Key.End => 269,
            Key.CapsLock => 280,
            Key.Scroll => 281,
            Key.NumLock => 282,
            Key.PrintScreen => 283,
            Key.Pause => 284,
            Key.Multiply => 332,
            Key.Subtract => 333,
            Key.Add => 334,
            Key.Decimal => 330,
            Key.Divide => 331,
            Key.LeftShift => 340,
            Key.LeftCtrl => 341,
            Key.LeftAlt => 342,
            Key.LWin => 343,
            Key.RightShift => 344,
            Key.RightCtrl => 345,
            Key.RightAlt => 346,
            Key.RWin => 347,
            Key.Apps => 348,
            _ => -1,
        };
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        Trace("dispose");
#if !TERMIN_CSHARP_PLOT_ONLY
        UnbindDisplay();
#endif
        ReleaseBridge();
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(Tgfx2D3D11ImageHost));
        }
    }

    private static bool TraceEnabled =>
        !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("TERMIN_WPF_PLOT_TRACE"));

    private void Trace(string message)
    {
        if (!TraceEnabled)
        {
            return;
        }

        string name = string.IsNullOrEmpty(Name) ? GetType().Name : Name;
        Console.Error.WriteLine($"[Termin.Wpf.D3DImageHost:{GetHashCode():X8}:{name}] {message}");
    }

    private readonly struct SizeInPixels
    {
        public SizeInPixels(int width, int height)
        {
            Width = width;
            Height = height;
        }

        public int Width { get; }
        public int Height { get; }
    }

    private readonly struct PointInPixels
    {
        public PointInPixels(float x, float y)
        {
            X = x;
            Y = y;
        }

        public float X { get; }
        public float Y { get; }
    }
}
