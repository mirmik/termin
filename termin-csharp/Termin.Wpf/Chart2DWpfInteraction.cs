using System;
using System.Windows.Input;
using Termin.Native;

namespace Termin.Wpf;

public enum ChartNavigationKind2D
{
    Pan,
    Zoom,
}

public sealed class ChartNavigatedEventArgs2D : EventArgs
{
    public ChartNavigatedEventArgs2D(
        ChartNavigationKind2D kind,
        PlotRange2D range)
    {
        Kind = kind;
        Range = range;
    }

    public ChartNavigationKind2D Kind { get; }
    public PlotRange2D Range { get; }
}

/// <summary>
/// WPF input adapter for tcplot's frontend-neutral ChartInteraction2D.
/// The scene host remains generic; this adapter can be attached once per
/// chart, including several chart subtrees in one retained scene.
/// </summary>
public sealed class Chart2DWpfInteraction : IDisposable
{
    private readonly RetainedScene2DHost _host;
    private readonly Chart2D _chart;
    private bool _disposed;

    public Chart2DWpfInteraction(
        RetainedScene2DHost host,
        Chart2D chart)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _chart = chart ?? throw new ArgumentNullException(nameof(chart));
        if (_host.Scene is null || _host.Scene.Id != _chart.Scene.Id)
            throw new ArgumentException(
                "The chart must belong to the scene attached to the host.",
                nameof(chart));

        _host.RenderHost.FramebufferMouseDown += OnMouseDown;
        _host.RenderHost.FramebufferMouseMove += OnMouseMove;
        _host.RenderHost.FramebufferMouseUp += OnMouseUp;
        _host.RenderHost.FramebufferMouseWheel += OnMouseWheel;
        _host.RenderHost.LostMouseCapture += OnLostMouseCapture;
    }

    public bool ControlWheelZoomsXOnly { get; set; } = true;
    public Chart2D Chart => _chart;

    public event EventHandler<ChartNavigatedEventArgs2D>? Navigated;

    public void Dispose()
    {
        if (_disposed)
            return;
        _host.RenderHost.FramebufferMouseDown -= OnMouseDown;
        _host.RenderHost.FramebufferMouseMove -= OnMouseMove;
        _host.RenderHost.FramebufferMouseUp -= OnMouseUp;
        _host.RenderHost.FramebufferMouseWheel -= OnMouseWheel;
        _host.RenderHost.LostMouseCapture -= OnLostMouseCapture;
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private void OnMouseDown(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_chart.Interaction.PointerDown(e.X, e.Y, e.Button))
            e.Handled = true;
    }

    private void OnMouseMove(
        object? sender,
        Tgfx2D3D11MouseMoveEventArgs e)
    {
        if (!_chart.Interaction.PointerMove(e.X, e.Y))
            return;
        e.Handled = true;
        RaiseNavigated(ChartNavigationKind2D.Pan);
    }

    private void OnMouseUp(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_chart.Interaction.PointerUp(e.X, e.Y, e.Button))
            e.Handled = true;
    }

    private void OnMouseWheel(
        object? sender,
        Tgfx2D3D11MouseWheelEventArgs e)
    {
        bool xOnly = ControlWheelZoomsXOnly &&
            (Keyboard.Modifiers & ModifierKeys.Control) != 0;
        if (!_chart.Interaction.Wheel(
                e.X, e.Y, e.Delta / 120.0f, xOnly))
            return;
        e.Handled = true;
        RaiseNavigated(ChartNavigationKind2D.Zoom);
    }

    private void OnLostMouseCapture(object sender, MouseEventArgs e)
    {
        _chart.Interaction.Cancel();
    }

    private void RaiseNavigated(ChartNavigationKind2D kind)
    {
        Navigated?.Invoke(
            this,
            new ChartNavigatedEventArgs2D(kind, _chart.Range));
    }
}
