using System;
using System.Windows.Input;
using Termin.Native;

namespace Termin.Wpf;

public sealed class MultiChartNavigatedEventArgs2D : EventArgs
{
    public MultiChartNavigatedEventArgs2D(
        ChartNavigationKind2D kind,
        MultiChartPanel2D panel,
        PlotRange2D range)
    {
        Kind = kind;
        Panel = panel;
        Range = range;
    }

    public ChartNavigationKind2D Kind { get; }
    public MultiChartPanel2D Panel { get; }
    public PlotRange2D Range { get; }
}

/// <summary>
/// One WPF adapter for a native retained multi-chart. Middle drag navigates
/// the hit panel and synchronizes X natively. When virtual scrolling is
/// active, wheel scrolls panels and Ctrl+wheel zooms shared X.
/// </summary>
public sealed class MultiChart2DWpfInteraction : IDisposable
{
    private readonly RetainedScene2DHost _host;
    private readonly MultiChart2D _chart;
    private readonly MultiChart2DGroup? _group;
    private MultiChartPanel2D? _activePanel;
    private bool _disposed;

    public MultiChart2DWpfInteraction(
        RetainedScene2DHost host,
        MultiChart2D chart,
        MultiChart2DGroup? group = null)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _chart = chart ?? throw new ArgumentNullException(nameof(chart));
        if (_host.Scene is null || _host.Scene.Id != _chart.Scene.Id)
            throw new ArgumentException(
                "The multi-chart must belong to the scene attached to the host.",
                nameof(chart));
        if (group is not null && !group.Contains(chart))
            throw new ArgumentException(
                "The coordinated group must contain this multi-chart.",
                nameof(group));
        _group = group;

        _host.RenderHost.FramebufferMouseDown += OnMouseDown;
        _host.RenderHost.FramebufferMouseMove += OnMouseMove;
        _host.RenderHost.FramebufferMouseUp += OnMouseUp;
        _host.RenderHost.FramebufferMouseWheel += OnMouseWheel;
        _host.RenderHost.LostMouseCapture += OnLostMouseCapture;
    }

    public float WheelScrollLogicalPixels { get; set; } = 56;
    public MultiChart2D Chart => _chart;
    public MultiChart2DGroup? Group => _group;

    public event EventHandler<MultiChartNavigatedEventArgs2D>? Navigated;
    public event EventHandler? Scrolled;

    public void Dispose()
    {
        if (_disposed)
            return;
        _host.RenderHost.FramebufferMouseDown -= OnMouseDown;
        _host.RenderHost.FramebufferMouseMove -= OnMouseMove;
        _host.RenderHost.FramebufferMouseUp -= OnMouseUp;
        _host.RenderHost.FramebufferMouseWheel -= OnMouseWheel;
        _host.RenderHost.LostMouseCapture -= OnLostMouseCapture;
        _activePanel?.Chart.Interaction.Cancel();
        _activePanel = null;
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private void OnMouseDown(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        MultiChartPanel2D? panel = HitPanel(e.X, e.Y);
        if (panel is null ||
            !panel.Chart.Interaction.PointerDown(e.X, e.Y, e.Button))
            return;
        _activePanel = panel;
        e.Handled = true;
    }

    private void OnMouseMove(
        object? sender,
        Tgfx2D3D11MouseMoveEventArgs e)
    {
        if (_activePanel is null ||
            !_activePanel.Chart.Interaction.PointerMove(e.X, e.Y))
            return;
        e.Handled = true;
        SynchronizeNavigation(_activePanel, ChartNavigationKind2D.Pan);
    }

    private void OnMouseUp(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_activePanel is null)
            return;
        if (_activePanel.Chart.Interaction.PointerUp(e.X, e.Y, e.Button))
            e.Handled = true;
        _activePanel = null;
    }

    private void OnMouseWheel(
        object? sender,
        Tgfx2D3D11MouseWheelEventArgs e)
    {
        bool control =
            (Keyboard.Modifiers & ModifierKeys.Control) != 0;
        MultiChartSnapshot2D state = _chart.Snapshot;
        float maximumScroll = _group?.MaximumScrollOffset ??
            state.MaximumScrollOffset;
        if (maximumScroll > 0 && !control)
        {
            float steps = e.Delta / 120.0f;
            float offset = state.ScrollOffset -
                steps * WheelScrollLogicalPixels * state.PixelScale;
            if (_group is null)
                _chart.ScrollOffset = offset;
            else
                _group.ScrollOffset = offset;
            e.Handled = true;
            Scrolled?.Invoke(this, EventArgs.Empty);
            return;
        }

        MultiChartPanel2D? panel = HitPanel(e.X, e.Y);
        if (panel is null || !panel.Chart.Interaction.Wheel(
                e.X,
                e.Y,
                e.Delta / 120.0f,
                xOnly: control))
            return;
        e.Handled = true;
        SynchronizeNavigation(panel, ChartNavigationKind2D.Zoom);
    }

    private void OnLostMouseCapture(object sender, MouseEventArgs e)
    {
        _activePanel?.Chart.Interaction.Cancel();
        _activePanel = null;
    }

    private MultiChartPanel2D? HitPanel(float x, float y)
    {
        foreach (MultiChartPanel2D panel in _chart.Panels)
        {
            if (!panel.Chart.Root.IsValid || !panel.Chart.Root.Visible)
                continue;
            PlotRect2D viewport = panel.Chart.Layout.Viewport;
            if (x >= viewport.X && x <= viewport.X + viewport.Width &&
                y >= viewport.Y && y <= viewport.Y + viewport.Height)
                return panel;
        }
        return null;
    }

    private void SynchronizeNavigation(
        MultiChartPanel2D panel,
        ChartNavigationKind2D kind)
    {
        PlotRange2D range = panel.Chart.Range;
        if (_group is null)
            _chart.SetSharedX(range.XMin, range.XMax);
        else
            _group.SetSharedX(range.XMin, range.XMax);
        Navigated?.Invoke(
            this,
            new MultiChartNavigatedEventArgs2D(kind, panel, range));
    }
}
