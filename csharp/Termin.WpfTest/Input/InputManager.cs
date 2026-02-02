namespace Termin.WpfTest.Input;

/// <summary>
/// Простой InputManager для обработки событий ввода.
/// 
/// Получает события от Backend и роутит их в scene (когда будет dispatch).
/// Сейчас просто логирует события для отладки.
/// </summary>
public class InputManager
{
    private readonly GlWpfBackend _backend;
    
    // TODO: Tracking for delta computation (currently unused)
    // private double _lastCursorX;
    // private double _lastCursorY;
    // private bool _hasCursorPos;

    // Логирование
    public bool LogMouseButton { get; set; } = true;
    public bool LogMouseMove { get; set; } = false;  // Слишком много событий
    public bool LogScroll { get; set; } = true;
    public bool LogKey { get; set; } = true;

    public InputManager(GlWpfBackend backend)
    {
        _backend = backend;

        // Подписываемся на события backend
        _backend.OnMouseButton += HandleMouseButton;
        _backend.OnMouseMove += HandleMouseMove;
        _backend.OnScroll += HandleScroll;
        _backend.OnKey += HandleKey;
    }

    private void HandleMouseButton(MouseButtonEvent evt)
    {
        if (LogMouseButton)
        {
            Console.WriteLine($"[Input] {evt}");
        }

        // TODO: dispatch to scene components
        // viewport?.Scene?.DispatchMouseButton(evt);
    }

    private void HandleMouseMove(MouseMoveEvent evt)
    {
        if (LogMouseMove)
        {
            Console.WriteLine($"[Input] {evt}");
        }

        // TODO: dispatch to scene components
    }

    private void HandleScroll(ScrollEvent evt)
    {
        if (LogScroll)
        {
            Console.WriteLine($"[Input] {evt}");
        }

        // TODO: dispatch to scene components
    }

    private void HandleKey(KeyEvent evt)
    {
        if (LogKey)
        {
            Console.WriteLine($"[Input] {evt}");
        }

        // TODO: dispatch to scene components
    }

    /// <summary>
    /// Отписывается от событий backend.
    /// </summary>
    public void Dispose()
    {
        _backend.OnMouseButton -= HandleMouseButton;
        _backend.OnMouseMove -= HandleMouseMove;
        _backend.OnScroll -= HandleScroll;
        _backend.OnKey -= HandleKey;
    }
}
