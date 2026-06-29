using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Termin.Native;

namespace Termin.Wpf;

public sealed class Tgfx2D3D11MouseButtonEventArgs : EventArgs
{
    public Tgfx2D3D11MouseButtonEventArgs(float x, float y, int button)
    {
        X = x;
        Y = y;
        Button = button;
    }

    public float X { get; }
    public float Y { get; }
    public int Button { get; }
    public bool Handled { get; set; }
}

public sealed class Tgfx2D3D11MouseMoveEventArgs : EventArgs
{
    public Tgfx2D3D11MouseMoveEventArgs(float x, float y)
    {
        X = x;
        Y = y;
    }

    public float X { get; }
    public float Y { get; }
    public bool Handled { get; set; }
}

public sealed class Tgfx2D3D11MouseWheelEventArgs : EventArgs
{
    public Tgfx2D3D11MouseWheelEventArgs(float x, float y, int delta)
    {
        X = x;
        Y = y;
        Delta = delta;
    }

    public float X { get; }
    public float Y { get; }
    public int Delta { get; }
    public bool Handled { get; set; }
}

public sealed class Tgfx2D3D11SwapchainHost : HwndHost
{
    private const int WS_CHILD = 0x40000000;
    private const int WS_VISIBLE = 0x10000000;
    private const int WS_CLIPSIBLINGS = 0x04000000;
    private const int WS_CLIPCHILDREN = 0x02000000;
    private const int SWP_NOZORDER = 0x0004;
    private const int SWP_NOACTIVATE = 0x0010;

    private const int WM_MOUSEMOVE = 0x0200;
    private const int WM_LBUTTONDOWN = 0x0201;
    private const int WM_LBUTTONUP = 0x0202;
    private const int WM_RBUTTONDOWN = 0x0204;
    private const int WM_RBUTTONUP = 0x0205;
    private const int WM_MBUTTONDOWN = 0x0207;
    private const int WM_MBUTTONUP = 0x0208;
    private const int WM_MOUSEWHEEL = 0x020A;

    private IntPtr _hwnd;
    private IntPtr _swapchain;
    private int _framebufferWidth;
    private int _framebufferHeight;
    private bool _disposed;

    public event EventHandler<Tgfx2D3D11MouseButtonEventArgs>? FramebufferMouseDown;
    public event EventHandler<Tgfx2D3D11MouseButtonEventArgs>? FramebufferMouseUp;
    public event EventHandler<Tgfx2D3D11MouseMoveEventArgs>? FramebufferMouseMove;
    public event EventHandler<Tgfx2D3D11MouseWheelEventArgs>? FramebufferMouseWheel;

    public int FramebufferWidth => GetFramebufferSize().Width;
    public int FramebufferHeight => GetFramebufferSize().Height;

    public void FocusNativeWindow()
    {
        if (_hwnd != IntPtr.Zero)
        {
            SetFocus(_hwnd);
        }
    }

    public bool Present(uint sourceTextureHandle, int width, int height, uint syncInterval = 1)
    {
        if (sourceTextureHandle == 0 || width <= 0 || height <= 0)
        {
            return false;
        }

        EnsureSwapchain(width, height);
        if (_swapchain == IntPtr.Zero)
        {
            return false;
        }

        return TerminCore.Tgfx2PresentD3D11Swapchain(
            _swapchain,
            sourceTextureHandle,
            syncInterval) != 0;
    }

    protected override HandleRef BuildWindowCore(HandleRef hwndParent)
    {
        SizeInPixels size = GetFramebufferSize();
        _hwnd = CreateWindowEx(
            0,
            "Static",
            string.Empty,
            WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
            0,
            0,
            size.Width,
            size.Height,
            hwndParent.Handle,
            IntPtr.Zero,
            Marshal.GetHINSTANCE(typeof(Tgfx2D3D11SwapchainHost).Module),
            IntPtr.Zero);

        if (_hwnd == IntPtr.Zero)
        {
            throw new InvalidOperationException(
                $"Tgfx2D3D11SwapchainHost: CreateWindowEx failed, Win32 error {Marshal.GetLastWin32Error()}.");
        }

        return new HandleRef(this, _hwnd);
    }

    protected override void DestroyWindowCore(HandleRef hwnd)
    {
        ReleaseSwapchain();
        if (hwnd.Handle != IntPtr.Zero)
        {
            DestroyWindow(hwnd.Handle);
        }
        _hwnd = IntPtr.Zero;
    }

    protected override IntPtr WndProc(
        IntPtr hwnd,
        int msg,
        IntPtr wParam,
        IntPtr lParam,
        ref bool handled)
    {
        switch (msg)
        {
            case WM_LBUTTONDOWN:
                handled = RaiseMouseDown(lParam, 0);
                SetCapture(hwnd);
                break;
            case WM_RBUTTONDOWN:
                handled = RaiseMouseDown(lParam, 1);
                SetCapture(hwnd);
                break;
            case WM_MBUTTONDOWN:
                handled = RaiseMouseDown(lParam, 2);
                SetCapture(hwnd);
                break;
            case WM_MOUSEMOVE:
                handled = RaiseMouseMove(lParam);
                break;
            case WM_LBUTTONUP:
                handled = RaiseMouseUp(lParam, 0);
                ReleaseCapture();
                break;
            case WM_RBUTTONUP:
                handled = RaiseMouseUp(lParam, 1);
                ReleaseCapture();
                break;
            case WM_MBUTTONUP:
                handled = RaiseMouseUp(lParam, 2);
                ReleaseCapture();
                break;
            case WM_MOUSEWHEEL:
                handled = RaiseMouseWheel(wParam, lParam);
                break;
        }

        return IntPtr.Zero;
    }

    protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
    {
        base.OnRenderSizeChanged(sizeInfo);
        ResizeChildWindow();
        ResizeSwapchainToCurrentFramebuffer();
    }

    protected override void Dispose(bool disposing)
    {
        if (_disposed)
        {
            base.Dispose(disposing);
            return;
        }

        _disposed = true;
        ReleaseSwapchain();
        base.Dispose(disposing);
    }

    private bool RaiseMouseDown(IntPtr lParam, int button)
    {
        PointInPixels point = PointFromClientLParam(lParam);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, button);
        FramebufferMouseDown?.Invoke(this, args);
        return args.Handled;
    }

    private bool RaiseMouseUp(IntPtr lParam, int button)
    {
        PointInPixels point = PointFromClientLParam(lParam);
        var args = new Tgfx2D3D11MouseButtonEventArgs(point.X, point.Y, button);
        FramebufferMouseUp?.Invoke(this, args);
        return args.Handled;
    }

    private bool RaiseMouseMove(IntPtr lParam)
    {
        PointInPixels point = PointFromClientLParam(lParam);
        var args = new Tgfx2D3D11MouseMoveEventArgs(point.X, point.Y);
        FramebufferMouseMove?.Invoke(this, args);
        return args.Handled;
    }

    private bool RaiseMouseWheel(IntPtr wParam, IntPtr lParam)
    {
        var screen = new NativePoint
        {
            X = SignedLowWord(lParam),
            Y = SignedHighWord(lParam),
        };
        ScreenToClient(_hwnd, ref screen);
        int delta = SignedHighWord(wParam);
        var args = new Tgfx2D3D11MouseWheelEventArgs(screen.X, screen.Y, delta);
        FramebufferMouseWheel?.Invoke(this, args);
        return args.Handled;
    }

    private void EnsureSwapchain(int width, int height)
    {
        ResizeChildWindow(width, height);

        if (_swapchain == IntPtr.Zero)
        {
            if (_hwnd == IntPtr.Zero)
            {
                return;
            }

            _swapchain = TerminCore.Tgfx2CreateD3D11Swapchain(
                _hwnd,
                (uint)width,
                (uint)height);
            if (_swapchain == IntPtr.Zero)
            {
                throw new InvalidOperationException(
                    "Tgfx2D3D11SwapchainHost: failed to create D3D11 swapchain. See native log for details.");
            }

            _framebufferWidth = width;
            _framebufferHeight = height;
            return;
        }

        if (_framebufferWidth == width && _framebufferHeight == height)
        {
            return;
        }

        if (TerminCore.Tgfx2ResizeD3D11Swapchain(
                _swapchain,
                (uint)width,
                (uint)height) == 0)
        {
            throw new InvalidOperationException(
                "Tgfx2D3D11SwapchainHost: failed to resize D3D11 swapchain. See native log for details.");
        }

        _framebufferWidth = width;
        _framebufferHeight = height;
    }

    private void ResizeSwapchainToCurrentFramebuffer()
    {
        if (_swapchain == IntPtr.Zero)
        {
            return;
        }

        SizeInPixels size = GetFramebufferSize();
        if (size.Width == _framebufferWidth && size.Height == _framebufferHeight)
        {
            return;
        }

        if (TerminCore.Tgfx2ResizeD3D11Swapchain(
                _swapchain,
                (uint)size.Width,
                (uint)size.Height) != 0)
        {
            _framebufferWidth = size.Width;
            _framebufferHeight = size.Height;
        }
    }

    private void ReleaseSwapchain()
    {
        if (_swapchain != IntPtr.Zero)
        {
            TerminCore.Tgfx2DestroyD3D11Swapchain(_swapchain);
            _swapchain = IntPtr.Zero;
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

    private void ResizeChildWindow()
    {
        SizeInPixels size = GetFramebufferSize();
        ResizeChildWindow(size.Width, size.Height);
    }

    private void ResizeChildWindow(int width, int height)
    {
        if (_hwnd == IntPtr.Zero)
        {
            return;
        }

        SetWindowPos(
            _hwnd,
            IntPtr.Zero,
            0,
            0,
            width,
            height,
            SWP_NOZORDER | SWP_NOACTIVATE);
    }

    private static PointInPixels PointFromClientLParam(IntPtr lParam)
        => new(SignedLowWord(lParam), SignedHighWord(lParam));

    private static short SignedLowWord(IntPtr value)
        => unchecked((short)((long)value & 0xffff));

    private static short SignedHighWord(IntPtr value)
        => unchecked((short)(((long)value >> 16) & 0xffff));

    private readonly record struct SizeInPixels(int Width, int Height);
    private readonly record struct PointInPixels(float X, float Y);

    [StructLayout(LayoutKind.Sequential)]
    private struct NativePoint
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateWindowEx(
        int dwExStyle,
        string lpClassName,
        string lpWindowName,
        int dwStyle,
        int x,
        int y,
        int nWidth,
        int nHeight,
        IntPtr hWndParent,
        IntPtr hMenu,
        IntPtr hInstance,
        IntPtr lpParam);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyWindow(IntPtr hwnd);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetWindowPos(
        IntPtr hwnd,
        IntPtr hwndInsertAfter,
        int x,
        int y,
        int cx,
        int cy,
        int flags);

    [DllImport("user32.dll")]
    private static extern IntPtr SetFocus(IntPtr hwnd);

    [DllImport("user32.dll")]
    private static extern IntPtr SetCapture(IntPtr hwnd);

    [DllImport("user32.dll")]
    private static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    private static extern bool ScreenToClient(IntPtr hwnd, ref NativePoint point);
}