using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Termin.Native;
using Termin.Wpf;

namespace AllianceStreamingChartsExample;

public partial class MainWindow : Window
{
    private sealed class StreamPanel
    {
        private const int CompactAt = 6_000;
        private const int RetainAfterCompact = 3_000;

        private readonly Func<double, double> _primarySignal;
        private readonly Func<double, double> _secondarySignal;
        private readonly List<double> _x = new() { 0 };
        private readonly List<double> _primary = new();
        private readonly List<double> _secondary = new();
        private readonly double[] _appendX = new double[1];
        private readonly double[] _appendPrimary = new double[1];
        private readonly double[] _appendSecondary = new double[1];

        public StreamPanel(
            Chart2D chart,
            Func<double, double> primarySignal,
            Func<double, double> secondarySignal,
            PlotSrgbColor2D primaryColor,
            PlotSrgbColor2D secondaryColor)
        {
            Chart = chart;
            _primarySignal = primarySignal;
            _secondarySignal = secondarySignal;
            _primary.Add(primarySignal(0));
            _secondary.Add(secondarySignal(0));
            Primary = chart.AddLineSeries(
                "primary",
                _x.ToArray(),
                _primary.ToArray(),
                style: new PlotLineSeriesStyle2D(
                    primaryColor,
                    thicknessPx: 1.8f),
                showInLegend: false);
            Secondary = chart.AddLineSeries(
                "secondary",
                _x.ToArray(),
                _secondary.ToArray(),
                style: new PlotLineSeriesStyle2D(
                    secondaryColor,
                    thicknessPx: 1.25f,
                    lineStyle: PlotLineStyle2D.Dash,
                    dashPx: 6,
                    gapPx: 4),
                showInLegend: false);
        }

        public Chart2D Chart { get; }
        public ChartLineSeries2D Primary { get; }
        public ChartLineSeries2D Secondary { get; }
        public int PointCount => _x.Count;

        public void Append(double time)
        {
            double primary = _primarySignal(time);
            double secondary = _secondarySignal(time);
            _x.Add(time);
            _primary.Add(primary);
            _secondary.Add(secondary);
            _appendX[0] = time;
            _appendPrimary[0] = primary;
            _appendSecondary[0] = secondary;
            Primary.Append(_appendX, _appendPrimary);
            Secondary.Append(_appendX, _appendSecondary);

            if (_x.Count >= CompactAt)
                Compact();
        }

        public void Reset()
        {
            _x.Clear();
            _primary.Clear();
            _secondary.Clear();
            _x.Add(0);
            _primary.Add(_primarySignal(0));
            _secondary.Add(_secondarySignal(0));
            Primary.SetData(_x.ToArray(), _primary.ToArray());
            Secondary.SetData(_x.ToArray(), _secondary.ToArray());
        }

        private void Compact()
        {
            int removeCount = _x.Count - RetainAfterCompact;
            _x.RemoveRange(0, removeCount);
            _primary.RemoveRange(0, removeCount);
            _secondary.RemoveRange(0, removeCount);
            Primary.SetData(_x.ToArray(), _primary.ToArray());
            Secondary.SetData(_x.ToArray(), _secondary.ToArray());
        }
    }

    private const double WindowSeconds = 20;
    private const int PanelsPerColumn = 15;
    private readonly GpuHost _gpuHost;
    private readonly MultiChart2D _leftChart;
    private readonly MultiChart2D _rightChart;
    private readonly MultiChart2DGroup _chartGroup;
    private readonly StreamPanel[] _panels;
    private readonly RectItemRef2D _pauseAnchor;
    private readonly RectItemRef2D _resetAnchor;
    private readonly RectItemRef2D _followAnchor;
    private readonly Button _pauseButton;
    private readonly Button _resetButton;
    private readonly Button _followButton;
    private readonly MultiChart2DWpfInteraction _leftInteraction;
    private readonly MultiChart2DWpfInteraction _rightInteraction;
    private readonly DispatcherTimer _timer;
    private bool _paused;
    private bool _followLatest = true;
    private bool _synchronizingScrollBar;
    private bool _closed;
    private double _time;
    private long _appendDurationTicks;
    private long _rangeDurationTicks;
    private int _updateSamples;
    private double _renderPaintMilliseconds;
    private double _renderFreezeMilliseconds;
    private double _renderSubmitMilliseconds;
    private double _renderNativeOtherMilliseconds;
    private double _renderPresentMilliseconds;
    private double _renderPortalMilliseconds;
    private double _renderTotalMilliseconds;
    private int _renderSamples;

    public MainWindow()
    {
        InitializeComponent();

        _gpuHost = Tgfx2Host.Acquire(FindFont(), BackendType.D3D11);
        MultiChart2D? leftChart = null;
        MultiChart2D? rightChart = null;
        MultiChart2DWpfInteraction? leftInteraction = null;
        MultiChart2DWpfInteraction? rightInteraction = null;
        var panels = new List<StreamPanel>();
        try
        {
            Chart2DTheme theme = CreatePanelTheme();
            leftChart = new MultiChart2D(
                _gpuHost,
                800,
                720,
                panelCount: PanelsPerColumn,
                initialRange: new PlotRange2D(0, WindowSeconds, -1, 1),
                panelHeight: 190,
                panelGap: 5,
                theme: theme);
            rightChart = new MultiChart2D(
                _gpuHost,
                800,
                720,
                panelCount: PanelsPerColumn,
                initialRange: new PlotRange2D(0, WindowSeconds, -1, 1),
                panelHeight: 190,
                panelGap: 5,
                theme: theme);
            _leftChart = leftChart;
            _rightChart = rightChart;
            _chartGroup = new MultiChart2DGroup(_leftChart, _rightChart);
            ValidateNativeMultiChartContract(_chartGroup);

            for (int index = 0; index < PanelsPerColumn; ++index)
            {
                panels.Add(CreateSyntheticPanel(_leftChart, 0, index));
                panels.Add(CreateSyntheticPanel(_rightChart, 1, index));
            }
            _panels = panels.ToArray();
            _leftChart.Panels[^1].Chart.XAxisText = "time, s";
            _rightChart.Panels[^1].Chart.XAxisText = "time, s";

            _pauseAnchor = CreatePortalAnchor(_leftChart.Scene);
            _resetAnchor = CreatePortalAnchor(_leftChart.Scene);
            _followAnchor = CreatePortalAnchor(_leftChart.Scene);
            _pauseButton = CreateToolbarButton("Pause");
            _resetButton = CreateToolbarButton("Reset");
            _followButton = CreateToolbarButton("Stop following");
            _pauseButton.Click += OnPauseClick;
            _resetButton.Click += OnResetClick;
            _followButton.Click += OnFollowClick;

            LeftSceneHost.FramebufferChanged += OnFramebufferChanged;
            RightSceneHost.FramebufferChanged += OnFramebufferChanged;
            LeftSceneHost.RenderFailed += OnRenderFailed;
            RightSceneHost.RenderFailed += OnRenderFailed;
            LeftSceneHost.FrameRendered += OnFrameRendered;
            RightSceneHost.FrameRendered += OnFrameRendered;
            LeftSceneHost.MsaaSamples = 2;
            RightSceneHost.MsaaSamples = 2;
            LeftSceneHost.ContinuousRendering = false;
            RightSceneHost.ContinuousRendering = false;
            LeftSceneHost.Attach(_gpuHost, _leftChart.Scene);
            RightSceneHost.Attach(_gpuHost, _rightChart.Scene);
            leftInteraction = new MultiChart2DWpfInteraction(
                LeftSceneHost, _leftChart, _chartGroup);
            rightInteraction = new MultiChart2DWpfInteraction(
                RightSceneHost, _rightChart, _chartGroup);
            _leftInteraction = leftInteraction;
            _rightInteraction = rightInteraction;
            _leftInteraction.Navigated += OnChartNavigated;
            _rightInteraction.Navigated += OnChartNavigated;
            _leftInteraction.Scrolled += OnChartScrolled;
            _rightInteraction.Scrolled += OnChartScrolled;
            PanelScrollBar.ValueChanged += OnPanelScrollBarValueChanged;
            LeftSceneHost.AddPortal(_pauseAnchor, _pauseButton);
            LeftSceneHost.AddPortal(_resetAnchor, _resetButton);
            LeftSceneHost.AddPortal(_followAnchor, _followButton);

            _timer = new DispatcherTimer(
                TimeSpan.FromMilliseconds(40),
                DispatcherPriority.Render,
                OnTimerTick,
                Dispatcher);
            _timer.Start();
        }
        catch
        {
            try
            {
                rightInteraction?.Dispose();
                leftInteraction?.Dispose();
            }
            finally
            {
                try
                {
                    try
                    {
                        RightSceneHost.Dispose();
                    }
                    finally
                    {
                        LeftSceneHost.Dispose();
                    }
                }
                finally
                {
                    try
                    {
                        try
                        {
                            rightChart?.Dispose();
                        }
                        finally
                        {
                            leftChart?.Dispose();
                        }
                    }
                    finally
                    {
                        Tgfx2Host.Release();
                    }
                }
            }
            throw;
        }

        Closed += OnClosed;
    }

    private StreamPanel CreatePanel(
        MultiChart2D owner,
        int index,
        string title,
        string yAxis,
        double yMinimum,
        double yMaximum,
        Func<double, double> primarySignal,
        Func<double, double> secondarySignal,
        PlotSrgbColor2D primaryColor,
        PlotSrgbColor2D secondaryColor)
    {
        Chart2D chart = owner.Panels[index].Chart;
        chart.SetRange(new PlotRange2D(
            0, WindowSeconds, yMinimum, yMaximum));
        chart.TitleText = title;
        chart.YAxisText = yAxis;
        chart.Grid.Item!.Opacity = 0.48f;
        return new StreamPanel(
            chart,
            primarySignal,
            secondarySignal,
            primaryColor,
            secondaryColor);
    }

    private StreamPanel CreateSyntheticPanel(
        MultiChart2D owner,
        int column,
        int index)
    {
        (string name, string unit, double center, double amplitude,
            double minimum, double maximum) = (index % 5) switch
        {
            0 => ("Pressure", "kPa", 20.0 + index, 5.0, 8.0, 42.0),
            1 => ("Temperature", "°C", 58.0 + index, 14.0, 28.0, 96.0),
            2 => ("Drive speed", "rpm", 1100.0 + index * 25.0,
                320.0, 450.0, 1900.0),
            3 => ("Tracking error", "mm", 0.0, 0.9, -1.8, 1.8),
            _ => ("Bus voltage", "V", 24.0 + index * 0.1,
                3.2, 15.0, 34.0),
        };
        double phase = column * 0.73 + index * 0.19;
        double speed = 0.19 + index * 0.055;
        string columnName = column == 0 ? "A" : "B";
        return CreatePanel(
            owner,
            index,
            $"{columnName}{index + 1:00} · {name}",
            unit,
            minimum,
            maximum,
            t => center + amplitude * (
                0.78 * Math.Sin(t * speed + phase) +
                0.22 * Math.Sin(t * (speed * 4.3) - phase * 0.4)),
            t => center + amplitude * 0.72 *
                Math.Sin(t * speed + phase + 0.68),
            PrimaryColor(index),
            SecondaryColor(index));
    }

    private static PlotSrgbColor2D PrimaryColor(int index) => (index % 5) switch
    {
        0 => new PlotSrgbColor2D(0.20f, 0.72f, 1.0f),
        1 => new PlotSrgbColor2D(1.0f, 0.45f, 0.20f),
        2 => new PlotSrgbColor2D(0.72f, 0.48f, 1.0f),
        3 => new PlotSrgbColor2D(0.32f, 0.90f, 0.46f),
        _ => new PlotSrgbColor2D(1.0f, 0.78f, 0.24f),
    };

    private static PlotSrgbColor2D SecondaryColor(int index) =>
        (index % 5) switch
        {
            0 => new PlotSrgbColor2D(0.35f, 0.95f, 0.70f),
            1 => new PlotSrgbColor2D(1.0f, 0.78f, 0.24f),
            2 => new PlotSrgbColor2D(0.95f, 0.45f, 0.82f),
            3 => new PlotSrgbColor2D(1.0f, 0.34f, 0.35f),
            _ => new PlotSrgbColor2D(0.50f, 0.82f, 1.0f),
        };

    private static RectItemRef2D CreatePortalAnchor(TcVisualScene2D scene)
    {
        var anchor = RectItemRef2D.Create(
            scene,
            new VisualRect2f(0, 0, 1, 1),
            new VisualFillPaint2D(new VisualSrgbColor(0, 0, 0, 0)));
        anchor.ZOrder = 1_000;
        return anchor;
    }

    private static Button CreateToolbarButton(string text) => new()
    {
        Content = text,
        Padding = new Thickness(10, 2, 10, 2),
        Foreground = Brushes.White,
        Background = new SolidColorBrush(Color.FromRgb(42, 91, 140)),
        BorderBrush = new SolidColorBrush(Color.FromRgb(111, 190, 255)),
    };

    private void OnFramebufferChanged(
        object? sender,
        RetainedSceneFramebufferChangedEventArgs e)
    {
        float scale = e.PixelScale;
        float margin = 6 * scale;
        float toolbarHeight = 44 * scale;
        float panelGap = 5 * scale;
        float contentTop = toolbarHeight;
        float available = Math.Max(
            4, e.Height - contentTop - margin);
        MultiChart2D chart = ReferenceEquals(sender, LeftSceneHost)
            ? _leftChart
            : _rightChart;
        chart.SetViewport(
            new VisualRect2f(
                margin,
                contentTop,
                Math.Max(1, e.Width - margin * 2),
                available),
            scale);
        _chartGroup.SetPanelLayout(190 * scale, panelGap);
        UpdatePanelScrollBar();
        RequestBothRenders();

        if (!ReferenceEquals(sender, LeftSceneHost))
            return;

        float buttonWidth = 116 * scale;
        float buttonHeight = 32 * scale;
        float right = e.Width - margin;
        SetAnchor(
            _resetAnchor,
            right - buttonWidth,
            margin,
            buttonWidth,
            buttonHeight);
        SetAnchor(
            _pauseAnchor,
            right - buttonWidth * 2 - margin,
            margin,
            buttonWidth,
            buttonHeight);
        SetAnchor(
            _followAnchor,
            right - buttonWidth * 3 - margin * 2,
            margin,
            buttonWidth,
            buttonHeight);
    }

    private void OnTimerTick(object? sender, EventArgs e)
    {
        if (_paused)
            return;

        _time += 0.04;
        long appendStarted = Stopwatch.GetTimestamp();
        foreach (StreamPanel panel in _panels)
            panel.Append(_time);
        _appendDurationTicks +=
            Stopwatch.GetTimestamp() - appendStarted;

        long rangeStarted = Stopwatch.GetTimestamp();
        if (_followLatest)
            SnapToLatest();
        _rangeDurationTicks += Stopwatch.GetTimestamp() - rangeStarted;
        RequestBothRenders();

        ++_updateSamples;
        if (_updateSamples >= 25)
        {
            double averageAppendMs = _appendDurationTicks * 1000.0 /
                Stopwatch.Frequency / _updateSamples;
            double averageRangeMs = _rangeDurationTicks * 1000.0 /
                Stopwatch.Frequency / _updateSamples;
            int renderSamples = Math.Max(1, _renderSamples);
            double averageRenderTotal =
                _renderTotalMilliseconds / renderSamples;
            StatusText.Text =
                $"2×{PanelsPerColumn}, {_panels.Length * 2} native series, " +
                $"{_panels[0].PointCount} points/series; " +
                $"append {averageAppendMs:F2} + X {averageRangeMs:F2} ms/tick; " +
                $"t = {_time:F1} s, " +
                $"{(_followLatest ? "following latest" : "manual navigation")}.\n" +
                $"render/host avg ({_renderSamples}): " +
                $"paint {_renderPaintMilliseconds / renderSamples:F2}, " +
                $"freeze {_renderFreezeMilliseconds / renderSamples:F2}, " +
                $"submit* {_renderSubmitMilliseconds / renderSamples:F2}, " +
                $"native-other {_renderNativeOtherMilliseconds / renderSamples:F2}, " +
                $"present {_renderPresentMilliseconds / renderSamples:F2}, " +
                $"portals {_renderPortalMilliseconds / renderSamples:F2}, " +
                $"total {averageRenderTotal:F2} ms; " +
                $"pair≈{averageRenderTotal * 2:F2} ms. " +
                $"*CPU command submission, not GPU timestamp.";
            _appendDurationTicks = 0;
            _rangeDurationTicks = 0;
            _updateSamples = 0;
            ResetRenderTelemetry();
        }
    }

    private void OnFrameRendered(
        object? sender,
        RetainedSceneFrameRenderedEventArgs e)
    {
        _renderPaintMilliseconds += e.Native.PaintMilliseconds;
        _renderFreezeMilliseconds += e.Native.FreezeMilliseconds;
        _renderSubmitMilliseconds += e.Native.GpuSubmitMilliseconds;
        _renderNativeOtherMilliseconds += Math.Max(
            0,
            e.NativeCallMilliseconds - e.Native.PaintMilliseconds -
            e.Native.FreezeMilliseconds - e.Native.GpuSubmitMilliseconds);
        _renderPresentMilliseconds += e.PresentMilliseconds;
        _renderPortalMilliseconds += e.PortalMilliseconds;
        _renderTotalMilliseconds += e.TotalMilliseconds;
        ++_renderSamples;
    }

    private void ResetRenderTelemetry()
    {
        _renderPaintMilliseconds = 0;
        _renderFreezeMilliseconds = 0;
        _renderSubmitMilliseconds = 0;
        _renderNativeOtherMilliseconds = 0;
        _renderPresentMilliseconds = 0;
        _renderPortalMilliseconds = 0;
        _renderTotalMilliseconds = 0;
        _renderSamples = 0;
    }

    private void OnPauseClick(object sender, RoutedEventArgs e)
    {
        _paused = !_paused;
        _pauseButton.Content = _paused ? "Resume" : "Pause";
        StatusText.Text = _paused
            ? $"Paused in C# at t = {_time:F1} s."
            : $"Resumed in C# at t = {_time:F1} s.";
    }

    private void OnResetClick(object sender, RoutedEventArgs e)
    {
        _time = 0;
        foreach (StreamPanel panel in _panels)
            panel.Reset();
        _chartGroup.SetSharedX(0, WindowSeconds);
        RequestBothRenders();
        _followLatest = true;
        UpdateFollowButton();
        StatusText.Text = "All native series were reset by the C# callback.";
    }

    private void OnFollowClick(object sender, RoutedEventArgs e)
    {
        _followLatest = !_followLatest;
        if (_followLatest)
            SnapToLatest();
        RequestBothRenders();
        UpdateFollowButton();
        StatusText.Text = _followLatest
            ? "Shared X returned to the live window."
            : "Follow mode disabled; the visible X range is now stable.";
    }

    private void OnChartNavigated(
        object? sender,
        MultiChartNavigatedEventArgs2D e)
    {
        _followLatest = false;
        RequestBothRenders();
        UpdateFollowButton();
        StatusText.Text =
            $"{e.Kind}: shared X updated; selected panel keeps its own Y.";
    }

    private void OnChartScrolled(object? sender, EventArgs e)
    {
        RequestBothRenders();
        UpdatePanelScrollBar();
    }

    private void OnPanelScrollBarValueChanged(
        object sender,
        RoutedPropertyChangedEventArgs<double> e)
    {
        if (_synchronizingScrollBar)
            return;
        _chartGroup.ScrollOffset = (float)e.NewValue;
        RequestBothRenders();
        UpdatePanelScrollBar();
    }

    private void UpdatePanelScrollBar()
    {
        MultiChartSnapshot2D state = _leftChart.Snapshot;
        _synchronizingScrollBar = true;
        try
        {
            PanelScrollBar.Maximum = _chartGroup.MaximumScrollOffset;
            PanelScrollBar.ViewportSize = state.Viewport.Height;
            PanelScrollBar.LargeChange = Math.Max(
                1, state.Viewport.Height * 0.8);
            PanelScrollBar.Value = _chartGroup.ScrollOffset;
            PanelScrollBar.IsEnabled = _chartGroup.MaximumScrollOffset > 0;
        }
        finally
        {
            _synchronizingScrollBar = false;
        }
    }

    private void SnapToLatest()
    {
        double xMaximum = Math.Max(WindowSeconds, _time);
        _chartGroup.SetSharedX(xMaximum - WindowSeconds, xMaximum);
    }

    private void UpdateFollowButton()
    {
        _followButton.Content = _followLatest
            ? "Stop following"
            : "Follow latest";
    }

    private void RequestBothRenders()
    {
        LeftSceneHost.RequestRender();
        RightSceneHost.RequestRender();
    }

    private void OnRenderFailed(
        object? sender,
        RetainedSceneRenderFailedEventArgs e)
    {
        _timer.Stop();
        string column = ReferenceEquals(sender, LeftSceneHost)
            ? "left"
            : "right";
        StatusText.Text =
            $"Rendering stopped in the {column} column: {e.Error.Message}";
        StatusText.Foreground = Brushes.OrangeRed;
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (_closed)
            return;
        _closed = true;
        _timer.Stop();
        _pauseButton.Click -= OnPauseClick;
        _resetButton.Click -= OnResetClick;
        _followButton.Click -= OnFollowClick;
        _leftInteraction.Navigated -= OnChartNavigated;
        _rightInteraction.Navigated -= OnChartNavigated;
        _leftInteraction.Scrolled -= OnChartScrolled;
        _rightInteraction.Scrolled -= OnChartScrolled;
        _rightInteraction.Dispose();
        _leftInteraction.Dispose();
        PanelScrollBar.ValueChanged -= OnPanelScrollBarValueChanged;
        LeftSceneHost.FramebufferChanged -= OnFramebufferChanged;
        RightSceneHost.FramebufferChanged -= OnFramebufferChanged;
        LeftSceneHost.RenderFailed -= OnRenderFailed;
        RightSceneHost.RenderFailed -= OnRenderFailed;
        LeftSceneHost.FrameRendered -= OnFrameRendered;
        RightSceneHost.FrameRendered -= OnFrameRendered;
        try
        {
            try
            {
                RightSceneHost.Dispose();
            }
            finally
            {
                LeftSceneHost.Dispose();
            }
        }
        finally
        {
            try
            {
                try
                {
                    _rightChart.Dispose();
                }
                finally
                {
                    _leftChart.Dispose();
                }
            }
            finally
            {
                Tgfx2Host.Release();
            }
        }
    }

    private static void SetAnchor(
        RectItemRef2D anchor,
        float x,
        float y,
        float width,
        float height)
    {
        anchor.Set(
            new VisualRect2f(x, y, width, height),
            new VisualFillPaint2D(new VisualSrgbColor(0, 0, 0, 0)));
    }

    private static Chart2DTheme CreatePanelTheme() => new()
    {
        BackgroundColor = new VisualSrgbColor(0.075f, 0.08f, 0.095f),
        PlotBackgroundColor = new VisualSrgbColor(0.105f, 0.115f, 0.14f),
        ForegroundColor = new VisualSrgbColor(0.86f, 0.88f, 0.92f),
        AxisColor = new VisualSrgbColor(0.54f, 0.58f, 0.66f),
        GridStyle = new PlotGridStyle2D(0.30f, 0.34f, 0.42f, 0.62f),
        AxisWidthLogicalPx = 1,
        FontSizeLogicalPx = 10,
        TitleFontSizeLogicalPx = 12,
        TickLengthLogicalPx = 3,
        GapLogicalPx = 2,
        OuterPaddingLogicalPx = 4,
        XTickSpacingLogicalPx = 110,
        YTickSpacingLogicalPx = 48,
    };

    private static void ValidateNativeMultiChartContract(
        MultiChart2DGroup group)
    {
        MultiChart2D left = group.Charts[0];
        MultiChart2D right = group.Charts[1];
        MultiChartPanel2D stableLeft = left.Panels[0];
        MultiChartPanel2D stableRight = right.Panels[0];
        group.SetPanelCount(PanelsPerColumn + 2);
        MultiChartPanel2D removedLeft = left.Panels[^1];
        MultiChartPanel2D removedRight = right.Panels[^1];
        group.SetPanelCount(PanelsPerColumn);
        if (!ReferenceEquals(stableLeft, left.Panels[0]) ||
            !ReferenceEquals(stableRight, right.Panels[0]) ||
            !stableLeft.IsValid || !stableRight.IsValid ||
            removedLeft.IsValid || removedRight.IsValid)
            throw new InvalidOperationException(
                "Coordinated native panel handle smoke check failed.");

        MultiChartSnapshot2D leftState = left.Snapshot;
        MultiChartSnapshot2D rightState = right.Snapshot;
        if (leftState.PanelCount != PanelsPerColumn ||
            rightState.PanelCount != PanelsPerColumn ||
            group.MaximumScrollOffset <= 0)
            throw new InvalidOperationException(
                "Coordinated virtual extent smoke check failed.");
        group.ScrollOffset = group.MaximumScrollOffset;
        if (left.Snapshot.ScrollOffset <= 0 ||
            left.Snapshot.ScrollOffset != right.Snapshot.ScrollOffset)
            throw new InvalidOperationException(
                "Coordinated scroll smoke check failed.");
        group.ScrollOffset = 0;
    }

    private static string FindFont()
    {
        string windows = Environment.GetFolderPath(
            Environment.SpecialFolder.Windows);
        string[] candidates =
        {
            Path.Combine(
                AppContext.BaseDirectory,
                "share", "termin", "fonts", "DroidSans.ttf"),
            Path.Combine(windows, "Fonts", "segoeui.ttf"),
            Path.Combine(windows, "Fonts", "arial.ttf"),
        };
        return candidates.FirstOrDefault(File.Exists)
            ?? throw new FileNotFoundException(
                "No usable TTF font was found for the streaming chart example.");
    }
}
