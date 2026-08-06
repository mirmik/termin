using System;
using System.Collections.Generic;
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

        public StreamPanel(
            Chart2D chart,
            Func<double, double> primarySignal,
            Func<double, double> secondarySignal,
            PlotColor2D primaryColor,
            PlotColor2D secondaryColor)
        {
            Chart = chart;
            _primarySignal = primarySignal;
            _secondarySignal = secondarySignal;
            _primary.Add(primarySignal(0));
            _secondary.Add(secondarySignal(0));
            Primary = chart.AddLine(
                _x.ToArray(),
                _primary.ToArray(),
                style: new PlotLineSeriesStyle2D(
                    primaryColor,
                    thicknessPx: 1.8f));
            Secondary = chart.AddLine(
                _x.ToArray(),
                _secondary.ToArray(),
                style: new PlotLineSeriesStyle2D(
                    secondaryColor,
                    thicknessPx: 1.25f,
                    lineStyle: PlotLineStyle2D.Dash,
                    dashPx: 6,
                    gapPx: 4));
        }

        public Chart2D Chart { get; }
        public PlotLineSeriesItemRef2D Primary { get; }
        public PlotLineSeriesItemRef2D Secondary { get; }

        public void Append(double time)
        {
            double primary = _primarySignal(time);
            double secondary = _secondarySignal(time);
            _x.Add(time);
            _primary.Add(primary);
            _secondary.Add(secondary);
            Primary.Append(new[] { time }, new[] { primary });
            Secondary.Append(new[] { time }, new[] { secondary });

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
    private readonly GpuHost _gpuHost;
    private readonly TcVisualScene2D _scene;
    private readonly StreamPanel[] _panels;
    private readonly RectItemRef2D _pauseAnchor;
    private readonly RectItemRef2D _resetAnchor;
    private readonly Button _pauseButton;
    private readonly Button _resetButton;
    private readonly DispatcherTimer _timer;
    private bool _paused;
    private bool _closed;
    private double _time;

    public MainWindow()
    {
        InitializeComponent();

        _gpuHost = Tgfx2Host.Acquire(FindFont(), BackendType.D3D11);
        _scene = new TcVisualScene2D();
        var panels = new List<StreamPanel>();
        try
        {
            panels.Add(CreatePanel(
                "Pressure A / B", "kPa", 10, 30,
                t => 20 + 4.2 * Math.Sin(t * 0.82),
                t => 19 + 2.6 * Math.Sin(t * 0.82 + 1.15),
                new PlotColor2D(0.20f, 0.72f, 1.0f),
                new PlotColor2D(0.35f, 0.95f, 0.70f)));
            panels.Add(CreatePanel(
                "Temperature inlet / outlet", "°C", 35, 90,
                t => 62 + 13 * Math.Sin(t * 0.24),
                t => 55 + 9 * Math.Sin(t * 0.24 - 0.7),
                new PlotColor2D(1.0f, 0.45f, 0.20f),
                new PlotColor2D(1.0f, 0.78f, 0.24f)));
            panels.Add(CreatePanel(
                "Drive speed / command", "rpm", 600, 1800,
                t => 1200 + 280 * Math.Sin(t * 0.55) + 65 * Math.Sin(t * 2.4),
                t => 1230 + 240 * Math.Sin(t * 0.55 + 0.18),
                new PlotColor2D(0.72f, 0.48f, 1.0f),
                new PlotColor2D(0.95f, 0.45f, 0.82f)));
            panels.Add(CreatePanel(
                "Tracking error X / Y", "mm", -1.6, 1.6,
                t => 0.72 * Math.Sin(t * 1.35) + 0.18 * Math.Sin(t * 4.7),
                t => 0.58 * Math.Cos(t * 1.1) - 0.12 * Math.Sin(t * 5.2),
                new PlotColor2D(0.32f, 0.90f, 0.46f),
                new PlotColor2D(1.0f, 0.34f, 0.35f)));
            _panels = panels.ToArray();
            _panels[^1].Chart.XAxisText = "time, s";

            _pauseAnchor = CreatePortalAnchor();
            _resetAnchor = CreatePortalAnchor();
            _pauseButton = CreateToolbarButton("Pause");
            _resetButton = CreateToolbarButton("Reset");
            _pauseButton.Click += OnPauseClick;
            _resetButton.Click += OnResetClick;

            SceneHost.FramebufferChanged += OnFramebufferChanged;
            SceneHost.RenderFailed += OnRenderFailed;
            SceneHost.Attach(_gpuHost, _scene);
            SceneHost.AddPortal(_pauseAnchor, _pauseButton);
            SceneHost.AddPortal(_resetAnchor, _resetButton);

            _timer = new DispatcherTimer(
                TimeSpan.FromMilliseconds(40),
                DispatcherPriority.Render,
                OnTimerTick,
                Dispatcher);
            _timer.Start();
        }
        catch
        {
            SceneHost.Dispose();
            foreach (StreamPanel panel in panels)
                panel.Chart.Dispose();
            _scene.Dispose();
            Tgfx2Host.Release();
            throw;
        }

        Closed += OnClosed;
    }

    private StreamPanel CreatePanel(
        string title,
        string yAxis,
        double yMinimum,
        double yMaximum,
        Func<double, double> primarySignal,
        Func<double, double> secondarySignal,
        PlotColor2D primaryColor,
        PlotColor2D secondaryColor)
    {
        var chart = new Chart2D(
            _gpuHost,
            _scene,
            new VisualRect2f(0, 0, 800, 180),
            new PlotRange2D(0, WindowSeconds, yMinimum, yMaximum),
            theme: CreatePanelTheme());
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

    private RectItemRef2D CreatePortalAnchor()
    {
        var anchor = RectItemRef2D.Create(
            _scene,
            new VisualRect2f(0, 0, 1, 1),
            new VisualFillPaint2D(new VisualColor4f(0, 0, 0, 0)));
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
            4,
            e.Height - contentTop - margin - panelGap * (_panels.Length - 1));
        float panelHeight = available / _panels.Length;

        for (int index = 0; index < _panels.Length; ++index)
        {
            _panels[index].Chart.SetViewport(
                new VisualRect2f(
                    margin,
                    contentTop + index * (panelHeight + panelGap),
                    Math.Max(1, e.Width - margin * 2),
                    panelHeight),
                scale);
        }

        float buttonWidth = 94 * scale;
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
    }

    private void OnTimerTick(object? sender, EventArgs e)
    {
        if (_paused)
            return;

        _time += 0.04;
        foreach (StreamPanel panel in _panels)
            panel.Append(_time);

        double xMaximum = Math.Max(WindowSeconds, _time);
        double xMinimum = xMaximum - WindowSeconds;
        foreach (StreamPanel panel in _panels)
        {
            PlotRange2D range = panel.Chart.Range;
            panel.Chart.SetRange(new PlotRange2D(
                xMinimum,
                xMaximum,
                range.YMin,
                range.YMax));
        }

        StatusText.Text =
            $"Streaming {_panels.Length * 2} series in one scene; " +
            $"t = {_time:F1} s, retained items = {_scene.Count}.";
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
        {
            panel.Reset();
            PlotRange2D range = panel.Chart.Range;
            panel.Chart.SetRange(new PlotRange2D(
                0,
                WindowSeconds,
                range.YMin,
                range.YMax));
        }
        StatusText.Text = "All native series were reset by the C# callback.";
    }

    private void OnRenderFailed(
        object? sender,
        RetainedSceneRenderFailedEventArgs e)
    {
        _timer.Stop();
        StatusText.Text = $"Rendering stopped: {e.Error.Message}";
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
        SceneHost.FramebufferChanged -= OnFramebufferChanged;
        SceneHost.RenderFailed -= OnRenderFailed;
        try
        {
            SceneHost.Dispose();
        }
        finally
        {
            try
            {
                foreach (StreamPanel panel in _panels)
                    panel.Chart.Dispose();
                _scene.Dispose();
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
            new VisualFillPaint2D(new VisualColor4f(0, 0, 0, 0)));
    }

    private static Chart2DTheme CreatePanelTheme() => new()
    {
        BackgroundColor = new VisualColor4f(0.075f, 0.08f, 0.095f),
        PlotBackgroundColor = new VisualColor4f(0.105f, 0.115f, 0.14f),
        ForegroundColor = new VisualColor4f(0.86f, 0.88f, 0.92f),
        AxisColor = new VisualColor4f(0.54f, 0.58f, 0.66f),
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
