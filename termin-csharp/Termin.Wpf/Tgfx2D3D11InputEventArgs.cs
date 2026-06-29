using System;

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