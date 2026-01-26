using System.Windows;
using System.Windows.Input;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;
using Termin.WpfTest.Input;

namespace Termin.WpfTest;

/// <summary>
/// Backend для OpenTK GLWpfControl.
/// 
/// Инкапсулирует:
/// - Получение событий ввода от WPF и трансляцию в наши типы
/// - Блит из FBO пайплайна в FBO окна WPF
/// - Управление размером и aspect ratio
/// 
/// Аналог BackendWindow из Python (sdl_embedded.py, glfw.py).
/// </summary>
public class GlWpfBackend
{
    private readonly GLWpfControl _control;
    
    // Последняя позиция курсора для вычисления delta
    private double _lastMouseX;
    private double _lastMouseY;
    private bool _hasMousePos;
    
    // Текущие модификаторы (обновляются при каждом событии)
    private KeyModifiers _currentModifiers;

    // События ввода
    public event Action<MouseButtonEvent>? OnMouseButton;
    public event Action<MouseMoveEvent>? OnMouseMove;
    public event Action<ScrollEvent>? OnScroll;
    public event Action<KeyEvent>? OnKey;

    /// <summary>Ширина framebuffer в пикселях.</summary>
    public int FramebufferWidth => (int)_control.ActualWidth;

    /// <summary>Высота framebuffer в пикселях.</summary>
    public int FramebufferHeight => (int)_control.ActualHeight;

    /// <summary>Aspect ratio (width / height).</summary>
    public double AspectRatio => FramebufferWidth / (double)FramebufferHeight;

    public GlWpfBackend(GLWpfControl control)
    {
        _control = control;

        // Подписываемся на WPF события
        _control.MouseDown += OnWpfMouseDown;
        _control.MouseUp += OnWpfMouseUp;
        _control.MouseMove += OnWpfMouseMove;
        _control.MouseWheel += OnWpfMouseWheel;
        _control.KeyDown += OnWpfKeyDown;
        _control.KeyUp += OnWpfKeyUp;

        // Для получения событий клавиатуры контрол должен иметь фокус
        _control.Focusable = true;
        _control.MouseDown += (_, _) => _control.Focus();
    }

    #region WPF Event Handlers

    private void OnWpfMouseDown(object sender, MouseButtonEventArgs e)
    {
        var pos = e.GetPosition(_control);
        var button = TranslateMouseButton(e.ChangedButton);
        _currentModifiers = GetCurrentModifiers();

        var evt = new MouseButtonEvent(
            pos.X, pos.Y,
            button,
            InputAction.Press,
            _currentModifiers
        );
        OnMouseButton?.Invoke(evt);
    }

    private void OnWpfMouseUp(object sender, MouseButtonEventArgs e)
    {
        var pos = e.GetPosition(_control);
        var button = TranslateMouseButton(e.ChangedButton);
        _currentModifiers = GetCurrentModifiers();

        var evt = new MouseButtonEvent(
            pos.X, pos.Y,
            button,
            InputAction.Release,
            _currentModifiers
        );
        OnMouseButton?.Invoke(evt);
    }

    private void OnWpfMouseMove(object sender, System.Windows.Input.MouseEventArgs e)
    {
        var pos = e.GetPosition(_control);
        
        double deltaX = 0;
        double deltaY = 0;
        
        if (_hasMousePos)
        {
            deltaX = pos.X - _lastMouseX;
            deltaY = pos.Y - _lastMouseY;
        }
        
        _lastMouseX = pos.X;
        _lastMouseY = pos.Y;
        _hasMousePos = true;

        var evt = new MouseMoveEvent(pos.X, pos.Y, deltaX, deltaY);
        OnMouseMove?.Invoke(evt);
    }

    private void OnWpfMouseWheel(object sender, MouseWheelEventArgs e)
    {
        var pos = e.GetPosition(_control);
        _currentModifiers = GetCurrentModifiers();

        // WPF Delta: 120 = одна "ступенька" колеса
        // Нормализуем к единицам как в GLFW/SDL
        double offsetY = e.Delta / 120.0;

        var evt = new ScrollEvent(
            pos.X, pos.Y,
            0.0,  // offsetX (горизонтальный скролл не поддерживается стандартным WPF)
            offsetY,
            _currentModifiers
        );
        OnScroll?.Invoke(evt);
    }

    private void OnWpfKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        _currentModifiers = GetCurrentModifiers();
        var key = TranslateKey(e.Key);

        // WPF не различает Press и Repeat напрямую, используем IsRepeat
        var action = e.IsRepeat ? InputAction.Repeat : InputAction.Press;

        var evt = new KeyEvent(
            key,
            KeyInterop.VirtualKeyFromKey(e.Key),  // Используем VK как scancode
            action,
            _currentModifiers
        );
        OnKey?.Invoke(evt);
    }

    private void OnWpfKeyUp(object sender, System.Windows.Input.KeyEventArgs e)
    {
        _currentModifiers = GetCurrentModifiers();
        var key = TranslateKey(e.Key);

        var evt = new KeyEvent(
            key,
            KeyInterop.VirtualKeyFromKey(e.Key),
            InputAction.Release,
            _currentModifiers
        );
        OnKey?.Invoke(evt);
    }

    #endregion

    #region Translation Helpers

    private static Input.MouseButton TranslateMouseButton(System.Windows.Input.MouseButton wpfButton)
    {
        return wpfButton switch
        {
            System.Windows.Input.MouseButton.Left => Input.MouseButton.Left,
            System.Windows.Input.MouseButton.Right => Input.MouseButton.Right,
            System.Windows.Input.MouseButton.Middle => Input.MouseButton.Middle,
            System.Windows.Input.MouseButton.XButton1 => Input.MouseButton.Button4,
            System.Windows.Input.MouseButton.XButton2 => Input.MouseButton.Button5,
            _ => Input.MouseButton.Left,
        };
    }

    private static KeyModifiers GetCurrentModifiers()
    {
        var mods = KeyModifiers.None;
        
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftShift) || 
            Keyboard.IsKeyDown(System.Windows.Input.Key.RightShift))
            mods |= KeyModifiers.Shift;
            
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftCtrl) || 
            Keyboard.IsKeyDown(System.Windows.Input.Key.RightCtrl))
            mods |= KeyModifiers.Control;
            
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LeftAlt) || 
            Keyboard.IsKeyDown(System.Windows.Input.Key.RightAlt))
            mods |= KeyModifiers.Alt;
            
        if (Keyboard.IsKeyDown(System.Windows.Input.Key.LWin) || 
            Keyboard.IsKeyDown(System.Windows.Input.Key.RWin))
            mods |= KeyModifiers.Super;

        return mods;
    }

    private static Input.Key TranslateKey(System.Windows.Input.Key wpfKey)
    {
        // Буквы A-Z
        if (wpfKey >= System.Windows.Input.Key.A && wpfKey <= System.Windows.Input.Key.Z)
        {
            return (Input.Key)(65 + (wpfKey - System.Windows.Input.Key.A));
        }

        // Цифры 0-9
        if (wpfKey >= System.Windows.Input.Key.D0 && wpfKey <= System.Windows.Input.Key.D9)
        {
            return (Input.Key)(48 + (wpfKey - System.Windows.Input.Key.D0));
        }

        // Numpad 0-9
        if (wpfKey >= System.Windows.Input.Key.NumPad0 && wpfKey <= System.Windows.Input.Key.NumPad9)
        {
            return (Input.Key)(320 + (wpfKey - System.Windows.Input.Key.NumPad0));
        }

        // Function keys F1-F12
        if (wpfKey >= System.Windows.Input.Key.F1 && wpfKey <= System.Windows.Input.Key.F12)
        {
            return (Input.Key)(290 + (wpfKey - System.Windows.Input.Key.F1));
        }

        // Специальные клавиши
        return wpfKey switch
        {
            System.Windows.Input.Key.Space => Input.Key.Space,
            System.Windows.Input.Key.Escape => Input.Key.Escape,
            System.Windows.Input.Key.Enter => Input.Key.Enter,
            System.Windows.Input.Key.Tab => Input.Key.Tab,
            System.Windows.Input.Key.Back => Input.Key.Backspace,
            System.Windows.Input.Key.Insert => Input.Key.Insert,
            System.Windows.Input.Key.Delete => Input.Key.Delete,
            System.Windows.Input.Key.Right => Input.Key.Right,
            System.Windows.Input.Key.Left => Input.Key.Left,
            System.Windows.Input.Key.Down => Input.Key.Down,
            System.Windows.Input.Key.Up => Input.Key.Up,
            System.Windows.Input.Key.PageUp => Input.Key.PageUp,
            System.Windows.Input.Key.PageDown => Input.Key.PageDown,
            System.Windows.Input.Key.Home => Input.Key.Home,
            System.Windows.Input.Key.End => Input.Key.End,
            System.Windows.Input.Key.CapsLock => Input.Key.CapsLockKey,
            System.Windows.Input.Key.LeftShift => Input.Key.LeftShift,
            System.Windows.Input.Key.RightShift => Input.Key.RightShift,
            System.Windows.Input.Key.LeftCtrl => Input.Key.LeftControl,
            System.Windows.Input.Key.RightCtrl => Input.Key.RightControl,
            System.Windows.Input.Key.LeftAlt => Input.Key.LeftAlt,
            System.Windows.Input.Key.RightAlt => Input.Key.RightAlt,
            System.Windows.Input.Key.LWin => Input.Key.LeftSuper,
            System.Windows.Input.Key.RWin => Input.Key.RightSuper,
            _ => Input.Key.Unknown,
        };
    }

    #endregion

    #region Rendering

    /// <summary>
    /// Блитит содержимое FBO пайплайна в FBO окна WPF.
    /// 
    /// Вызывается после render_to_screen() для копирования результата
    /// из color FBO пайплайна в framebuffer WPF контрола.
    /// </summary>
    /// <param name="pipeline">RenderPipeline с FBO pool.</param>
    /// <param name="resourceName">Имя ресурса FBO (обычно "color").</param>
    /// <param name="wpfFboId">ID WPF framebuffer (получить до вызова render_to_screen).</param>
    public void BlitFromPipeline(RenderPipeline pipeline, string resourceName, int wpfFboId)
    {
        var fbo = pipeline.get_fbo(resourceName);
        if (fbo == null)
        {
            Console.WriteLine($"[Backend] FBO '{resourceName}' not found in pipeline");
            return;
        }

        int srcFboId = (int)fbo.get_fbo_id();
        int srcWidth = fbo.get_width();
        int srcHeight = fbo.get_height();
        int dstWidth = FramebufferWidth;
        int dstHeight = FramebufferHeight;

        // Биндим source FBO для чтения, destination для записи
        GL.BindFramebuffer(FramebufferTarget.ReadFramebuffer, srcFboId);
        GL.BindFramebuffer(FramebufferTarget.DrawFramebuffer, wpfFboId);

        // Копируем color buffer
        GL.BlitFramebuffer(
            0, 0, srcWidth, srcHeight,
            0, 0, dstWidth, dstHeight,
            ClearBufferMask.ColorBufferBit,
            BlitFramebufferFilter.Nearest
        );

        // Восстанавливаем биндинг
        GL.BindFramebuffer(FramebufferTarget.Framebuffer, wpfFboId);
    }

    /// <summary>
    /// Получает текущий FBO ID от WPF контрола.
    /// Вызывать ДО render_to_screen(), т.к. пайплайн меняет биндинг.
    /// </summary>
    public int GetCurrentFboId()
    {
        GL.GetInteger(GetPName.FramebufferBinding, out int fboId);
        return fboId;
    }

    #endregion

    /// <summary>
    /// Отписывается от событий WPF.
    /// </summary>
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
