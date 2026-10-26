using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Termin.Native;

namespace Termin.Wpf;

public sealed class NativeDocumentRenderFailedEventArgs : EventArgs
{
    public NativeDocumentRenderFailedEventArgs(Exception error)
    {
        Error = error;
    }
    public Exception Error
    {
        get;
    }
}

/// <summary>
/// Embeds a complete native UI document through the existing D3D11 D3DImage
/// presenter. Layout, painting, parameter editors and interaction remain native.
/// The attached document and GPU host are borrowed and must outlive this host.
/// </summary>
public sealed class NativeDocumentHost : Grid, IDisposable, INativeDocumentPlatformServices
{
    private readonly Tgfx2D3D11ImageHost _renderHost = new();
    private NativeDocumentRenderer? _renderer;
    private bool _renderingSubscribed;
    private bool _renderRequested = true;
    private bool _continuousRendering = true;
    private bool _disposed;
    private int _width, _height;
    private float _density;

    public NativeDocumentHost()
    {
        ClipToBounds = true;
        Children.Add(_renderHost);
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        IsVisibleChanged += OnIsVisibleChanged;
        _renderHost.PreviewMouseDown += OnMouseDown;
        _renderHost.PreviewMouseUp += OnMouseUp;
        _renderHost.PreviewMouseMove += OnMouseMove;
        _renderHost.PreviewMouseWheel += OnMouseWheel;
        _renderHost.MouseEnter += OnMouseEnter;
        _renderHost.MouseLeave += OnMouseLeave;
        _renderHost.LostMouseCapture += OnLostMouseCapture;
        _renderHost.PreviewKeyDown += OnKeyDown;
        _renderHost.PreviewKeyUp += OnKeyUp;
        _renderHost.PreviewTextInput += OnTextInput;
        _renderHost.GotKeyboardFocus += OnGotKeyboardFocus;
        _renderHost.LostKeyboardFocus += OnLostKeyboardFocus;
    }

    public Tgfx2D3D11ImageHost RenderHost => _renderHost;
    /// <summary>Borrowed renderer; its lifetime is controlled by Attach/Detach.</summary>
    public NativeDocumentRenderer? Renderer => _renderer;
    public NativeUiDocument? Document => _renderer?.Document;
    public bool ContinuousRendering
    {
        get => _continuousRendering;
        set
        {
            VerifyHostAccess();
            _continuousRendering = value;
            RequestRender();
        }
    }
    public event EventHandler<NativeDocumentRenderFailedEventArgs>? RenderFailed;
    public event EventHandler? FrameRendered;

    public void Attach(GpuHost host, NativeUiDocument document, string fontPath)
    {
        VerifyHostAccess();
        Detach();
        _renderer = new NativeDocumentRenderer(host, document, fontPath, this);
        _width = _height = 0;
        _density = 0;
        _renderRequested = true;
        UpdateRenderingSubscription();
    }
    public void Detach()
    {
        VerifyHostAccess();
        UnsubscribeRendering();
        // Release the WPF backbuffer reference before destroying native targets.
        _renderHost.ReleaseNativeResources();
        NativeDocumentRenderer? renderer = _renderer;
        _renderer = null;
        try
        {
            if (renderer is not null)
            {
                try
                {
                    renderer.SetFocus(false);
                }
                finally
                {
                    renderer.Dispose();
                }
            }
        }
        finally
        {
            if (_renderHost.IsMouseCaptured)
                _renderHost.ReleaseMouseCapture();
            _width = _height = 0;
            _density = 0;
            _renderRequested = false;
        }
    }
    /// <summary>Schedules a frame; safe to call from native view callbacks.</summary>
    public void RequestRender()
    {
        VerifyHostAccess();
        _renderRequested = true;
        UpdateRenderingSubscription();
    }
    public void RenderFrame()
    {
        VerifyHostAccess();
        if (_renderer is null)
            return;
        _width = Math.Max(1, _renderHost.FramebufferWidth);
        _height = Math.Max(1, _renderHost.FramebufferHeight);
        _density = (float)VisualTreeHelper.GetDpi(_renderHost).DpiScaleX;
        _renderRequested = false;
        uint texture = _renderer.RenderToTextureHandleId(_width, _height, _density);
        // A temporarily unavailable WPF front buffer will be retried on the
        // next composition frame, without changing native document ownership.
        if (!_renderHost.Present(texture, _width, _height))
            _renderRequested = true;
        FrameRendered?.Invoke(this, EventArgs.Empty);
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        _renderRequested = true;
        UpdateRenderingSubscription();
    }
    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        UnsubscribeRendering();
        if (_renderer is not null)
            _renderer.SetFocus(false);
        if (_renderHost.IsMouseCaptured)
            _renderHost.ReleaseMouseCapture();
        _renderHost.ReleaseNativeResources();
        _renderRequested = true;
    }
    private void OnIsVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (IsVisible)
            _renderRequested = true;
        else if (_renderer is not null)
        {
            _renderer.SetFocus(false);
            if (_renderHost.IsMouseCaptured)
                _renderHost.ReleaseMouseCapture();
        }
        UpdateRenderingSubscription();
    }
    private void UpdateRenderingSubscription()
    {
        bool active = !_disposed && IsLoaded && IsVisible && _renderer is not null;
        if (active && !_renderingSubscribed)
        {
            CompositionTarget.Rendering += OnRendering;
            _renderingSubscribed = true;
        }
        else if (!active)
            UnsubscribeRendering();
    }
    private void UnsubscribeRendering()
    {
        if (!_renderingSubscribed)
            return;
        CompositionTarget.Rendering -= OnRendering;
        _renderingSubscribed = false;
    }
    private void OnRendering(object? sender, EventArgs e)
    {
        if (_renderer is null)
            return;
        try
        {
            if (_continuousRendering || _renderRequested || _renderer.RepaintRequested || MetricsChanged())
                RenderFrame();
        }
        catch (Exception error)
        {
            ReportFailure(error);
        }
    }
    private bool MetricsChanged() => _width != _renderHost.FramebufferWidth || _height != _renderHost.FramebufferHeight ||
        Math.Abs(_density - (float)VisualTreeHelper.GetDpi(_renderHost).DpiScaleX) > 0.0001f;
    private void ReportFailure(Exception error)
    {
        Trace.TraceError($"NativeDocumentHost operation failed: {error}");
        Console.Error.WriteLine($"[Termin.Wpf.NativeDocumentHost] Operation failed: {error}");
        UnsubscribeRendering();
        RenderFailed?.Invoke(this, new NativeDocumentRenderFailedEventArgs(error));
    }
    private void HandleInput(Action input)
    {
        if (_renderer is null)
            return;
        try
        {
            input();
            _renderRequested = true;
        }
        catch (Exception error)
        {
            ReportFailure(error);
        }
    }
    private NativeUiPointerEvent Pointer(NativeUiPointerEventType type, MouseEventArgs e)
    {
        Point point = e.GetPosition(_renderHost);
        return new NativeUiPointerEvent { Type = type, X = (float)point.X, Y = (float)point.Y, Button = -1, Modifiers = Modifiers() };
    }
    private void OnMouseDown(object sender, MouseButtonEventArgs e) => HandleInput(() =>
    {
        _renderHost.FocusNativeWindow();
        NativeUiPointerEvent pointer = Pointer(NativeUiPointerEventType.Down, e);
        pointer.Button = Button(e.ChangedButton);
        pointer.ClickCount = (uint)e.ClickCount;
        e.Handled = _renderer!.DispatchPointer(pointer);
        if (_renderer.HasPointerCapture)
            _renderHost.CaptureMouse();
    });
    private void OnMouseUp(object sender, MouseButtonEventArgs e) => HandleInput(() =>
    {
        NativeUiPointerEvent pointer = Pointer(NativeUiPointerEventType.Up, e);
        pointer.Button = Button(e.ChangedButton);
        pointer.ClickCount = (uint)e.ClickCount;
        e.Handled = _renderer!.DispatchPointer(pointer);
        if (!_renderer.HasPointerCapture && _renderHost.IsMouseCaptured)
            _renderHost.ReleaseMouseCapture();
    });
    private void OnMouseMove(object sender, MouseEventArgs e) => HandleInput(() => e.Handled = _renderer!.DispatchPointer(Pointer(NativeUiPointerEventType.Move, e)));
    private void OnMouseWheel(object sender, MouseWheelEventArgs e) => HandleInput(() =>
    {
        NativeUiPointerEvent pointer = Pointer(NativeUiPointerEventType.Wheel, e);
        pointer.WheelY = e.Delta / 120f;
        e.Handled = _renderer!.DispatchPointer(pointer);
    });
    private void OnMouseEnter(object sender, MouseEventArgs e) => HandleInput(() => _renderer!.DispatchPointer(Pointer(NativeUiPointerEventType.Enter, e)));
    private void OnMouseLeave(object sender, MouseEventArgs e) => HandleInput(() => _renderer!.DispatchPointer(Pointer(NativeUiPointerEventType.Leave, e)));
    private void OnLostMouseCapture(object sender, MouseEventArgs e) => HandleInput(() =>
    {
        if (_renderer!.HasPointerCapture)
            _renderer.CancelInteraction(NativeUiPointerCancelReason.HostCaptureLost);
    });
    private void OnGotKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e) => HandleInput(() => _renderer!.SetFocus(true));
    private void OnLostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e) => HandleInput(() =>
    {
        _renderer!.SetFocus(false);
        if (_renderHost.IsMouseCaptured)
            _renderHost.ReleaseMouseCapture();
    });
    private void OnKeyDown(object sender, KeyEventArgs e) => DispatchKey(e, NativeUiKeyEventType.Down);
    private void OnKeyUp(object sender, KeyEventArgs e) => DispatchKey(e, NativeUiKeyEventType.Up);
    private void DispatchKey(KeyEventArgs e, NativeUiKeyEventType type) => HandleInput(() =>
    {
        Key key = e.Key == Key.System ? e.SystemKey : e.Key;
        e.Handled = _renderer!.DispatchKey(new NativeUiKeyEvent { Type = type, Key = KeyCode(key), Scancode = KeyInterop.VirtualKeyFromKey(key), Modifiers = Modifiers(), Repeat = e.IsRepeat });
    });
    private void OnTextInput(object sender, TextCompositionEventArgs e) => HandleInput(() =>
    {
        if (!string.IsNullOrEmpty(e.Text))
            e.Handled = _renderer!.DispatchText(e.Text);
    });
    private static int Button(MouseButton button) => button switch { MouseButton.Left => 0, MouseButton.Right => 1, MouseButton.Middle => 2, MouseButton.XButton1 => 3, MouseButton.XButton2 => 4, _ => -1 };
    private static NativeUiModifiers Modifiers()
    {
        NativeUiModifiers result = NativeUiModifiers.None;
        if ((Keyboard.Modifiers & ModifierKeys.Shift) != 0)
            result |= NativeUiModifiers.Shift;
        if ((Keyboard.Modifiers & ModifierKeys.Control) != 0)
            result |= NativeUiModifiers.Control;
        if ((Keyboard.Modifiers & ModifierKeys.Alt) != 0)
            result |= NativeUiModifiers.Alt;
        if ((Keyboard.Modifiers & ModifierKeys.Windows) != 0)
            result |= NativeUiModifiers.Super;
        return result;
    }
    private static int KeyCode(Key key)
    {
        if (key >= Key.A && key <= Key.Z)
            return 65 + key - Key.A;
        if (key >= Key.D0 && key <= Key.D9)
            return 48 + key - Key.D0;
        if (key >= Key.NumPad0 && key <= Key.NumPad9)
            return 48 + key - Key.NumPad0;
        if (key >= Key.F1 && key <= Key.F12)
            return 290 + key - Key.F1;
        return key switch
        {
            Key.Tab => 9,
            Key.Enter => 13,
            Key.Space => 32,
            Key.Escape => 256,
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
            _ => -1
        };
    }

    bool INativeDocumentPlatformServices.SetTextInputEnabled(bool enabled)
    {
        InputMethod.SetIsInputMethodEnabled(_renderHost, enabled);
        return true;
    }
    string INativeDocumentPlatformServices.GetClipboardText() => Clipboard.ContainsText() ? Clipboard.GetText() : "";
    bool INativeDocumentPlatformServices.SetClipboardText(string text)
    {
        Clipboard.SetText(text);
        return true;
    }
    bool INativeDocumentPlatformServices.SetCursor(NativeUiCursor cursor)
    {
        _renderHost.Cursor = cursor switch
        {
            NativeUiCursor.Text => Cursors.IBeam,
            NativeUiCursor.Hand => Cursors.Hand,
            NativeUiCursor.Crosshair => Cursors.Cross,
            NativeUiCursor.Move => Cursors.SizeAll,
            NativeUiCursor.ResizeHorizontal => Cursors.SizeWE,
            NativeUiCursor.ResizeVertical => Cursors.SizeNS,
            NativeUiCursor.ResizeNwse => Cursors.SizeNWSE,
            NativeUiCursor.ResizeNesw => Cursors.SizeNESW,
            NativeUiCursor.Inherit => null,
            _ => Cursors.Arrow
        };
        return true;
    }
    private void VerifyHostAccess()
    {
        Dispatcher.VerifyAccess();
        if (_disposed)
            throw new ObjectDisposedException(nameof(NativeDocumentHost));
    }
    public void Dispose()
    {
        if (_disposed)
            return;
        VerifyHostAccess();
        Detach();
        Loaded -= OnLoaded;
        Unloaded -= OnUnloaded;
        IsVisibleChanged -= OnIsVisibleChanged;
        _renderHost.PreviewMouseDown -= OnMouseDown;
        _renderHost.PreviewMouseUp -= OnMouseUp;
        _renderHost.PreviewMouseMove -= OnMouseMove;
        _renderHost.PreviewMouseWheel -= OnMouseWheel;
        _renderHost.MouseEnter -= OnMouseEnter;
        _renderHost.MouseLeave -= OnMouseLeave;
        _renderHost.LostMouseCapture -= OnLostMouseCapture;
        _renderHost.PreviewKeyDown -= OnKeyDown;
        _renderHost.PreviewKeyUp -= OnKeyUp;
        _renderHost.PreviewTextInput -= OnTextInput;
        _renderHost.GotKeyboardFocus -= OnGotKeyboardFocus;
        _renderHost.LostKeyboardFocus -= OnLostKeyboardFocus;
        _renderHost.Dispose();
        _disposed = true;
        GC.SuppressFinalize(this);
    }
}
