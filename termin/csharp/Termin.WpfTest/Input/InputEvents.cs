namespace Termin.WpfTest.Input;

/// <summary>
/// Событие нажатия/отпускания кнопки мыши.
/// </summary>
public readonly struct MouseButtonEvent
{
    /// <summary>Позиция X курсора в пикселях окна.</summary>
    public readonly double X;
    
    /// <summary>Позиция Y курсора в пикселях окна.</summary>
    public readonly double Y;
    
    /// <summary>Кнопка мыши.</summary>
    public readonly MouseButton Button;
    
    /// <summary>Действие (Press/Release).</summary>
    public readonly InputAction Action;
    
    /// <summary>Модификаторы клавиатуры.</summary>
    public readonly KeyModifiers Modifiers;

    public MouseButtonEvent(double x, double y, MouseButton button, InputAction action, KeyModifiers modifiers)
    {
        X = x;
        Y = y;
        Button = button;
        Action = action;
        Modifiers = modifiers;
    }

    public override string ToString() =>
        $"MouseButton({Button} {Action} at ({X:F1}, {Y:F1}), mods={Modifiers})";
}

/// <summary>
/// Событие движения мыши.
/// </summary>
public readonly struct MouseMoveEvent
{
    /// <summary>Текущая позиция X курсора.</summary>
    public readonly double X;
    
    /// <summary>Текущая позиция Y курсора.</summary>
    public readonly double Y;
    
    /// <summary>Смещение по X с предыдущего события.</summary>
    public readonly double DeltaX;
    
    /// <summary>Смещение по Y с предыдущего события.</summary>
    public readonly double DeltaY;

    public MouseMoveEvent(double x, double y, double deltaX, double deltaY)
    {
        X = x;
        Y = y;
        DeltaX = deltaX;
        DeltaY = deltaY;
    }

    public override string ToString() =>
        $"MouseMove(({X:F1}, {Y:F1}), delta=({DeltaX:F1}, {DeltaY:F1}))";
}

/// <summary>
/// Событие прокрутки колеса мыши.
/// </summary>
public readonly struct ScrollEvent
{
    /// <summary>Позиция X курсора.</summary>
    public readonly double X;
    
    /// <summary>Позиция Y курсора.</summary>
    public readonly double Y;
    
    /// <summary>Смещение по горизонтали (обычно 0).</summary>
    public readonly double OffsetX;
    
    /// <summary>Смещение по вертикали (положительное = вверх).</summary>
    public readonly double OffsetY;
    
    /// <summary>Модификаторы клавиатуры.</summary>
    public readonly KeyModifiers Modifiers;

    public ScrollEvent(double x, double y, double offsetX, double offsetY, KeyModifiers modifiers)
    {
        X = x;
        Y = y;
        OffsetX = offsetX;
        OffsetY = offsetY;
        Modifiers = modifiers;
    }

    public override string ToString() =>
        $"Scroll(offset=({OffsetX:F2}, {OffsetY:F2}) at ({X:F1}, {Y:F1}), mods={Modifiers})";
}

/// <summary>
/// Событие нажатия/отпускания клавиши.
/// </summary>
public readonly struct KeyEvent
{
    /// <summary>Код клавиши.</summary>
    public readonly Key Key;
    
    /// <summary>Скан-код (платформенно-зависимый).</summary>
    public readonly int ScanCode;
    
    /// <summary>Действие (Press/Release/Repeat).</summary>
    public readonly InputAction Action;
    
    /// <summary>Модификаторы клавиатуры.</summary>
    public readonly KeyModifiers Modifiers;

    public KeyEvent(Key key, int scanCode, InputAction action, KeyModifiers modifiers)
    {
        Key = key;
        ScanCode = scanCode;
        Action = action;
        Modifiers = modifiers;
    }

    public override string ToString() =>
        $"Key({Key} {Action}, mods={Modifiers})";
}
