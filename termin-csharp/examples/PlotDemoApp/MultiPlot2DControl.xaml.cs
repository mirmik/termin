using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public partial class MultiPlot2DControl : UserControl, IDisposable
{
    private const double WindowSeconds = 10;
    private MultiChart2D? _chart;
    private MultiChart2DWpfInteraction? _interaction;
    private bool _hostLeaseHeld;
    private bool _disposed;
    private bool _followLatest = true;
    private double _latestX;
    private bool _synchronizingScrollBar;

    public int PanelCount { get; set; } = 3;
    public double PanelHeight { get; set; }

    public static readonly DependencyProperty ScrollOffsetProperty =
        DependencyProperty.Register(
            nameof(ScrollOffset), typeof(double), typeof(MultiPlot2DControl),
            new PropertyMetadata(0.0, OnScrollOffsetChanged));

    public double ScrollOffset
    {
        get => (double)GetValue(ScrollOffsetProperty);
        set => SetValue(ScrollOffsetProperty, value);
    }

    private static readonly DependencyPropertyKey MaxScrollPropertyKey =
        DependencyProperty.RegisterReadOnly(
            nameof(MaxScroll), typeof(double), typeof(MultiPlot2DControl),
            new PropertyMetadata(0.0));

    public static readonly DependencyProperty MaxScrollProperty =
        MaxScrollPropertyKey.DependencyProperty;

    public double MaxScroll => (double)GetValue(MaxScrollProperty);

    public MultiChart2D Chart => _chart ??
        throw new InvalidOperationException("The retained multi-chart is not initialized.");

    public event EventHandler? NativeInitialized;

    public MultiPlot2DControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    internal void UpdateAfterAppend(double latestX)
    {
        if (_followLatest)
        {
            _latestX = latestX;
            Chart.SetSharedX(latestX - WindowSeconds, latestX);
        }
        SceneHost.RequestRender();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Loaded -= OnLoaded;
        GpuHost host = Tgfx2Host.Acquire(App.FindSystemFont());
        _hostLeaseHeld = true;
        try
        {
            float pixelScale = (float)VisualTreeHelper.GetDpi(this).DpiScaleX;
            _chart = new MultiChart2D(
                host, SceneHost.RenderHost.FramebufferWidth, SceneHost.RenderHost.FramebufferHeight,
                PanelCount, new PlotRange2D(-WindowSeconds, 0, -1.15, 1.15),
                panelHeight: (float)PanelHeight * pixelScale, pixelScale: pixelScale);

            SceneHost.FramebufferChanged += OnFramebufferChanged;
            SceneHost.RenderFailed += App.LogRenderFailure;
            SceneHost.Attach(host, _chart.Scene);
            _interaction = new MultiChart2DWpfInteraction(SceneHost, _chart);
            _interaction.Navigated += OnNavigated;
            _interaction.Scrolled += (_, _) => SynchronizeScrollBar();
            NativeInitialized?.Invoke(this, EventArgs.Empty);
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    private void OnFramebufferChanged(
        object? sender, RetainedSceneFramebufferChangedEventArgs e)
    {
        Chart.Resize(e.Width, e.Height, e.PixelScale);
        Chart.SetPanelLayout((float)PanelHeight * e.PixelScale);
        SynchronizeScrollBar();
    }

    private void OnNavigated(object? sender, MultiChartNavigatedEventArgs2D e)
    {
        if (Math.Abs(e.Range.XMin - (_latestX - WindowSeconds)) > 1e-12 ||
            Math.Abs(e.Range.XMax - _latestX) > 1e-12)
            _followLatest = false;
    }

    private static void OnScrollOffsetChanged(
        DependencyObject sender, DependencyPropertyChangedEventArgs e)
    {
        var control = (MultiPlot2DControl)sender;
        if (control._chart is null || control._synchronizingScrollBar)
            return;

        float scale = control._chart.Snapshot.PixelScale;
        control._chart.ScrollOffset = (float)(double)e.NewValue * scale;
        control.SceneHost.RequestRender();
    }

    private void SynchronizeScrollBar()
    {
        MultiChartSnapshot2D snapshot = Chart.Snapshot;
        _synchronizingScrollBar = true;
        try
        {
            SetValue(MaxScrollPropertyKey, (double)snapshot.MaximumScrollOffset / snapshot.PixelScale);
            SetCurrentValue(ScrollOffsetProperty, (double)snapshot.ScrollOffset / snapshot.PixelScale);
        }
        finally
        {
            _synchronizingScrollBar = false;
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e) => Dispose();

    public void Dispose()
    {
        if (_disposed)
            return;
        Dispatcher.VerifyAccess();
        _disposed = true;
        Loaded -= OnLoaded;
        Unloaded -= OnUnloaded;
        _interaction?.Dispose();
        SceneHost.Dispose();
        _chart?.Dispose();
        _chart = null;
        if (_hostLeaseHeld)
        {
            Tgfx2Host.Release();
            _hostLeaseHeld = false;
        }
    }
}
