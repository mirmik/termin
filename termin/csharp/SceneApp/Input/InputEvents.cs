namespace SceneApp.Input;

public readonly struct MouseButtonEvent
{
    public readonly double X;
    public readonly double Y;
    public readonly MouseButton Button;
    public readonly InputAction Action;
    public readonly KeyModifiers Modifiers;

    public MouseButtonEvent(double x, double y, MouseButton button, InputAction action, KeyModifiers modifiers)
    {
        X = x;
        Y = y;
        Button = button;
        Action = action;
        Modifiers = modifiers;
    }
}

public readonly struct MouseMoveEvent
{
    public readonly double X;
    public readonly double Y;
    public readonly double DeltaX;
    public readonly double DeltaY;

    public MouseMoveEvent(double x, double y, double deltaX, double deltaY)
    {
        X = x;
        Y = y;
        DeltaX = deltaX;
        DeltaY = deltaY;
    }
}

public readonly struct ScrollEvent
{
    public readonly double X;
    public readonly double Y;
    public readonly double OffsetX;
    public readonly double OffsetY;
    public readonly KeyModifiers Modifiers;

    public ScrollEvent(double x, double y, double offsetX, double offsetY, KeyModifiers modifiers)
    {
        X = x;
        Y = y;
        OffsetX = offsetX;
        OffsetY = offsetY;
        Modifiers = modifiers;
    }
}

public readonly struct KeyEvent
{
    public readonly Key Key;
    public readonly int ScanCode;
    public readonly InputAction Action;
    public readonly KeyModifiers Modifiers;

    public KeyEvent(Key key, int scanCode, InputAction action, KeyModifiers modifiers)
    {
        Key = key;
        ScanCode = scanCode;
        Action = action;
        Modifiers = modifiers;
    }
}
