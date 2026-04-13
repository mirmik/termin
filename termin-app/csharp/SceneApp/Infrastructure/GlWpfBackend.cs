using System.Windows;
using System.Windows.Input;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;
using WpfInput = SceneApp.Input;

namespace SceneApp.Infrastructure;

public class GlWpfBackend
{
    private readonly GLWpfControl _control;
    private double _lastMouseX;
    private double _lastMouseY;
    private bool _hasMousePos;
    private WpfInput.KeyModifiers _currentModifiers;

    public event Action<WpfInput.MouseButtonEvent>? OnMouseButton;
    public event Action<WpfInput.MouseMoveEvent>? OnMouseMove;
    public event Action<WpfInput.ScrollEvent>? OnScroll;
    public event Action<WpfInput.KeyEvent>? OnKey;

    public int FramebufferWidth => (int)_control.ActualWidth;
    public int FramebufferHeight => (int)_control.ActualHeight;
    public double AspectRatio => FramebufferWidth / (double)FramebufferHeight;

    public GlWpfBackend(GLWpfControl control)
    {
        _control = control;
        _control.MouseDown += OnWpfMouseDown;
        _control.MouseUp += OnWpfMouseUp;
        _control.MouseMove += OnWpfMouseMove;
        _control.MouseWheel += OnWpfMouseWheel;
        _control.KeyDown += OnWpfKeyDown;
        _control.KeyUp += OnWpfKeyUp;
        _control.Focusable = true;
        _control.MouseDown += (_, _) => _control.Focus();
    }

    private void OnWpfMouseDown(object sender, MouseButtonEventArgs e)
    {
        var pos = e.GetPosition(_control);
        var button = TranslateMouseButton(e.ChangedButton);
        _currentModifiers = GetCurrentModifiers();
        var evt = new WpfInput.MouseButtonEvent(pos.X, pos.Y, button, WpfInput.InputAction.Press, _currentModifiers);
        OnMouseButton?.Invoke(evt);
    }

    private void OnWpfMouseUp(object sender, MouseButtonEventArgs e)
    {
        var pos = e.GetPosition(_control);
        var button = TranslateMouseButton(e.ChangedButton);
        _currentModifiers = GetCurrentModifiers();
        var evt = new WpfInput.MouseButtonEvent(pos.X, pos.Y, button, WpfInput.InputAction.Release, _currentModifiers);
        OnMouseButton?.Invoke(evt);
    }

    private void OnWpfMouseMove(object sender, System.Windows.Input.MouseEventArgs e)
    {
        var pos = e.GetPosition(_control);
        double deltaX = 0, deltaY = 0;
        if (_hasMousePos)
        {
            deltaX = pos.X - _lastMouseX;
            deltaY = pos.Y - _lastMouseY;
        }
        _lastMouseX = pos.X;
        _lastMouseY = pos.Y;
        _hasMousePos = true;
        var evt = new WpfInput.MouseMoveEvent(pos.X, pos.Y, deltaX, deltaY);
        OnMouseMove?.Invoke(evt);
    }

    private void OnWpfMouseWheel(object sender, MouseWheelEventArgs e)
    {
        var pos = e.GetPosition(_control);
        _currentModifiers = GetCurrentModifiers();
        double offsetY = e.Delta / 120.0;
        var evt = new WpfInput.ScrollEvent(pos.X, pos.Y, 0.0, offsetY, _currentModifiers);
        OnScroll?.Invoke(evt);
    }

    private void OnWpfKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        _currentModifiers = GetCurrentModifiers();
        var key = TranslateKey(e.Key);
        var action = e.IsRepeat ? WpfInput.InputAction.Repeat : WpfInput.InputAction.Press;
        var evt = new WpfInput.KeyEvent(key, KeyInterop.VirtualKeyFromKey(e.Key), action, _currentModifiers);
        OnKey?.Invoke(evt);
    }

    private void OnWpfKeyUp(object sender, System.Windows.Input.KeyEventArgs e)
    {
        _currentModifiers = GetCurrentModifiers();
        var key = TranslateKey(e.Key);
        var evt = new WpfInput.KeyEvent(key, KeyInterop.VirtualKeyFromKey(e.Key), WpfInput.InputAction.Release, _currentModifiers);
        OnKey?.Invoke(evt);
    }

    private static WpfInput.MouseButton TranslateMouseButton(System.Windows.Input.MouseButton wpfButton) => wpfButton switch
    {
        System.Windows.Input.MouseButton.Left => WpfInput.MouseButton.Left,
        System.Windows.Input.MouseButton.Right => WpfInput.MouseButton.Right,
        System.Windows.Input.MouseButton.Middle => WpfInput.MouseButton.Middle,
        System.Windows.Input.MouseButton.XButton1 => WpfInput.MouseButton.Button4,
        System.Windows.Input.MouseButton.XButton2 => WpfInput.MouseButton.Button5,
        _ => WpfInput.MouseButton.Left,
    };

    private static WpfInput.KeyModifiers GetCurrentModifiers()
    {
        var mods = WpfInput.KeyModifiers.None;
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftShift) || Keyboard.IsKeyDown(System.Windows.Input.Key.RightShift))
            mods |= WpfInput.KeyModifiers.Shift;
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftCtrl) || Keyboard.IsKeyDown(System.Windows.Input.Key.RightCtrl))
            mods |= WpfInput.KeyModifiers.Control;
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftAlt) || Keyboard.IsKeyDown(System.Windows.Input.Key.RightAlt))
            mods |= WpfInput.KeyModifiers.Alt;
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LWin) || Keyboard.IsKeyDown(System.Windows.Input.Key.RWin))
            mods |= WpfInput.KeyModifiers.Super;
        return mods;
    }

    private static WpfInput.Key TranslateKey(System.Windows.Input.Key wpfKey)
    {
        if (wpfKey >= System.Windows.Input.Key.A && wpfKey <= System.Windows.Input.Key.Z)
            return (WpfInput.Key)(65 + (wpfKey - System.Windows.Input.Key.A));
        if (wpfKey >= System.Windows.Input.Key.D0 && wpfKey <= System.Windows.Input.Key.D9)
            return (WpfInput.Key)(48 + (wpfKey - System.Windows.Input.Key.D0));
        if (wpfKey >= System.Windows.Input.Key.NumPad0 && wpfKey <= System.Windows.Input.Key.NumPad9)
            return (WpfInput.Key)(320 + (wpfKey - System.Windows.Input.Key.NumPad0));
        if (wpfKey >= System.Windows.Input.Key.F1 && wpfKey <= System.Windows.Input.Key.F12)
            return (WpfInput.Key)(290 + (wpfKey - System.Windows.Input.Key.F1));
        return wpfKey switch
        {
            System.Windows.Input.Key.Space => WpfInput.Key.Space,
            System.Windows.Input.Key.Escape => WpfInput.Key.Escape,
            System.Windows.Input.Key.Enter => WpfInput.Key.Enter,
            System.Windows.Input.Key.Tab => WpfInput.Key.Tab,
            System.Windows.Input.Key.Back => WpfInput.Key.Backspace,
            System.Windows.Input.Key.Insert => WpfInput.Key.Insert,
            System.Windows.Input.Key.Delete => WpfInput.Key.Delete,
            System.Windows.Input.Key.Right => WpfInput.Key.Right,
            System.Windows.Input.Key.Left => WpfInput.Key.Left,
            System.Windows.Input.Key.Down => WpfInput.Key.Down,
            System.Windows.Input.Key.Up => WpfInput.Key.Up,
            System.Windows.Input.Key.PageUp => WpfInput.Key.PageUp,
            System.Windows.Input.Key.PageDown => WpfInput.Key.PageDown,
            System.Windows.Input.Key.Home => WpfInput.Key.Home,
            System.Windows.Input.Key.End => WpfInput.Key.End,
            System.Windows.Input.Key.CapsLock => WpfInput.Key.CapsLockKey,
            System.Windows.Input.Key.LeftShift => WpfInput.Key.LeftShift,
            System.Windows.Input.Key.RightShift => WpfInput.Key.RightShift,
            System.Windows.Input.Key.LeftCtrl => WpfInput.Key.LeftControl,
            System.Windows.Input.Key.RightCtrl => WpfInput.Key.RightControl,
            System.Windows.Input.Key.LeftAlt => WpfInput.Key.LeftAlt,
            System.Windows.Input.Key.RightAlt => WpfInput.Key.RightAlt,
            System.Windows.Input.Key.LWin => WpfInput.Key.LeftSuper,
            System.Windows.Input.Key.RWin => WpfInput.Key.RightSuper,
            _ => WpfInput.Key.Unknown,
        };
    }

    public void BlitFromPipeline(RenderPipeline pipeline, string resourceName, int wpfFboId)
    {
        var fbo = pipeline.get_fbo(resourceName);
        if (fbo == null) return;
        int srcFboId = (int)fbo.get_fbo_id();
        int srcWidth = fbo.get_width();
        int srcHeight = fbo.get_height();
        int dstWidth = FramebufferWidth;
        int dstHeight = FramebufferHeight;
        GL.BindFramebuffer(FramebufferTarget.ReadFramebuffer, srcFboId);
        GL.BindFramebuffer(FramebufferTarget.DrawFramebuffer, wpfFboId);
        GL.BlitFramebuffer(0, 0, srcWidth, srcHeight, 0, 0, dstWidth, dstHeight, ClearBufferMask.ColorBufferBit, BlitFramebufferFilter.Nearest);
        GL.BindFramebuffer(FramebufferTarget.Framebuffer, wpfFboId);
    }

    public int GetCurrentFboId()
    {
        GL.GetInteger(GetPName.FramebufferBinding, out int fboId);
        return fboId;
    }

    public void Dispose()
    {
        _control.MouseDown -= OnWpfMouseDown;
        _control.MouseUp -= OnWpfMouseUp;
        _control.MouseMove -= OnWpfMouseMove;
        _control.MouseWheel -= OnWpfMouseWheel;
        _control.KeyDown -= OnWpfKeyDown;
        _control.KeyUp -= OnWpfKeyUp;
    }
}
