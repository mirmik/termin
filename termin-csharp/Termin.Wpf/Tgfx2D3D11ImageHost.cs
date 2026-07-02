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
        ReleaseBridge();
    }

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
        _ => 0,
    };

    private void OnMouseDown(object sender, MouseButtonEventArgs e)
    {
        FocusNativeWindow();
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, ToTcbaseButton(e.ChangedButton));
        FramebufferMouseDown?.Invoke(this, args);
        if (args.Handled)
        {
            CaptureMouse();
            e.Handled = true;
        }
    }

    private void OnMouseMove(object sender, MouseEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseMoveEventArgs(point.X, point.Y);
        FramebufferMouseMove?.Invoke(this, args);
        if (args.Handled)
        {
            e.Handled = true;
        }
    }

    private void OnMouseUp(object sender, MouseButtonEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, ToTcbaseButton(e.ChangedButton));
        FramebufferMouseUp?.Invoke(this, args);
        if (args.Handled)
        {
            ReleaseMouseCapture();
            e.Handled = true;
        }
    }

    private void OnMouseWheel(object sender, MouseWheelEventArgs e)
    {
        PointInPixels point = GetMousePoint(e);
        var args = new Tgfx2D3D11MouseWheelEventArgs(point.X, point.Y, e.Delta);
        FramebufferMouseWheel?.Invoke(this, args);
        if (args.Handled)
        {
            e.Handled = true;
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        Trace("dispose");
        ReleaseBridge();
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
