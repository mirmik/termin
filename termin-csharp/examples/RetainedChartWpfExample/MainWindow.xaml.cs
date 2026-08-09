using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace RetainedChartWpfExample;

public partial class MainWindow : Window
{
    private readonly GpuHost _gpuHost;
    private readonly Chart2D _chart;
    private readonly RectItemRef2D _buttonAnchor;
    private readonly Button _themeButton;
    private Chart2DWpfInteraction? _interaction;
    private bool _alternateTheme;
    private bool _closed;

    public MainWindow()
    {
        InitializeComponent();

        _gpuHost = Tgfx2Host.Acquire(FindFont(), BackendType.D3D11);
        Chart2D? chart = null;
        try
        {
            chart = CreateChart(_gpuHost);
            _chart = chart;

            // Direct C# access to the native retained scene: replace a chart
            // part and add a new item which is not known to Chart2D.
            var customPlotBackground = RectItemRef2D.Create(
                _chart.Scene,
                new VisualRect2f(0, 0, 1, 1),
                new VisualFillPaint2D(
                    _chart.Theme.PlotBackgroundColor));
            _chart.PlotBackground.Replace(customPlotBackground);
            _chart.Grid.Item!.Opacity = 0.55f;

            _buttonAnchor = RectItemRef2D.Create(
                _chart.Scene,
                new VisualRect2f(0, 0, 1, 1),
                new VisualFillPaint2D(
                    new VisualSrgbColor(0, 0, 0, 0)),
                parent: _chart.Chrome);
            _buttonAnchor.ZOrder = 100;

            _themeButton = new Button
            {
                Content = "Switch C# theme",
                Padding = new Thickness(8, 2, 8, 2),
                Foreground = Brushes.White,
                Background = new SolidColorBrush(
                    Color.FromRgb(42, 91, 140)),
                BorderBrush = new SolidColorBrush(
                    Color.FromRgb(111, 190, 255)),
            };
            _themeButton.Click += OnThemeButtonClick;

            SceneHost.FramebufferChanged += OnFramebufferChanged;
            SceneHost.RenderFailed += OnRenderFailed;
            SceneHost.Attach(_gpuHost, _chart.Scene);
            _interaction = new Chart2DWpfInteraction(SceneHost, _chart);
            _interaction.Navigated += OnChartNavigated;
            SceneHost.AddPortal(_buttonAnchor, _themeButton);
        }
        catch
        {
            _interaction?.Dispose();
            _interaction = null;
            SceneHost.Dispose();
            chart?.Dispose();
            Tgfx2Host.Release();
            throw;
        }

        Closed += OnClosed;
    }

    private static Chart2D CreateChart(GpuHost host)
    {
        const int pointCount = 20_000;
        double[] x = Enumerable.Range(0, pointCount)
            .Select(index => index * 4 * Math.PI / (pointCount - 1))
            .ToArray();

        var chart = new Chart2D(
            host,
            960,
            540,
            new PlotRange2D(0, 4 * Math.PI, -1.35, 1.35));
        chart.TitleText = "C# retained chart + WPF portal";
        chart.XAxisText = "phase";
        chart.YAxisText = "signal";
        chart.AddLineSeries(
            "sin(x)",
            x,
            x.Select(value => Math.Sin(value)).ToArray(),
            style: new PlotLineSeriesStyle2D(
                new PlotSrgbColor2D(0.20f, 0.72f, 1.0f),
                thicknessPx: 2.2f));
        chart.AddLineSeries(
            "0.45 cos(2.3x)",
            x,
            x.Select(value => 0.45 * Math.Cos(2.3 * value)).ToArray(),
            style: new PlotLineSeriesStyle2D(
                new PlotSrgbColor2D(1.0f, 0.48f, 0.22f),
                thicknessPx: 1.5f,
                lineStyle: PlotLineStyle2D.Dash));
        return chart;
    }

    private void OnFramebufferChanged(
        object? sender,
        RetainedSceneFramebufferChangedEventArgs e)
    {
        _chart.Resize(e.Width, e.Height, e.PixelScale);

        float width = 142 * e.PixelScale;
        float height = 38 * e.PixelScale;
        float margin = 12 * e.PixelScale;
        _buttonAnchor.Set(
            new VisualRect2f(
                e.Width - width - margin,
                e.Height - height - margin,
                width,
                height),
            new VisualFillPaint2D(
                new VisualSrgbColor(0, 0, 0, 0)));
    }

    private void OnThemeButtonClick(object sender, RoutedEventArgs e)
    {
        _alternateTheme = !_alternateTheme;
        _chart.ApplyTheme(_alternateTheme
            ? CreateWarmTheme()
            : Chart2DTheme.Default);
        _chart.Grid.Item!.Opacity = _alternateTheme ? 0.32f : 0.55f;
        StatusText.Text =
            $"C# Click handler ran at {DateTime.Now:T}; " +
            $"scene {_chart.Scene.Id} has {_chart.Scene.Count} native items.";
    }

    private void OnChartNavigated(
        object? sender,
        ChartNavigatedEventArgs2D e)
    {
        StatusText.Text =
            $"{e.Kind}: middle-drag pans, wheel zooms, " +
            $"Ctrl+wheel zooms X only.";
    }

    private void OnRenderFailed(
        object? sender,
        RetainedSceneRenderFailedEventArgs e)
    {
        StatusText.Text = $"Rendering stopped: {e.Error.Message}";
        StatusText.Foreground = Brushes.OrangeRed;
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (_closed)
            return;
        _closed = true;
        _themeButton.Click -= OnThemeButtonClick;
        if (_interaction is not null)
        {
            _interaction.Navigated -= OnChartNavigated;
            _interaction.Dispose();
            _interaction = null;
        }
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
                _chart.Dispose();
            }
            finally
            {
                Tgfx2Host.Release();
            }
        }
    }

    private static Chart2DTheme CreateWarmTheme() => new()
    {
        BackgroundColor = new VisualSrgbColor(0.10f, 0.06f, 0.055f),
        PlotBackgroundColor = new VisualSrgbColor(0.16f, 0.085f, 0.065f),
        ForegroundColor = new VisualSrgbColor(1.0f, 0.89f, 0.76f),
        AxisColor = new VisualSrgbColor(0.93f, 0.60f, 0.36f),
        GridStyle = new PlotGridStyle2D(0.70f, 0.34f, 0.22f, 0.55f),
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
                "No usable TTF font was found for the retained chart example.");
    }
}
