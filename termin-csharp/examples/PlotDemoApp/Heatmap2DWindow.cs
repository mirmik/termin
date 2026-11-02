using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public sealed partial class Heatmap2DWindow : Window
{
    private const uint Rows = 180;
    private const uint Columns = 240;
    private static readonly PlotRange2D Bounds = new(-4, 4, -3, 3);
    private readonly RetainedScene2DHost _host = new() { ContinuousRendering = false };
    private readonly RetainedScene2DHost _scaleHost = new() { ContinuousRendering = false };
    private readonly TextBlock _status = new() { Margin = new Thickness(12, 5, 12, 8) };
    private readonly TextBlock _maximum = new() { HorizontalAlignment = HorizontalAlignment.Center };
    private readonly TextBlock _minimum = new() { HorizontalAlignment = HorizontalAlignment.Center };
    private readonly ComboBox _palette = new() { Width = 110, Margin = new Thickness(5, 0, 12, 0) };
    private readonly CheckBox _reversed = new() { Content = "Reverse", Foreground = Brushes.White, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) };
    private readonly CheckBox _autoRange = new() { Content = "Auto range", Foreground = Brushes.White, IsChecked = true, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) };
    private readonly CheckBox _bilinear = new() { Content = "Bilinear", Foreground = Brushes.White, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) };
    private readonly GpuHost _gpu;
    private Chart2D _chart = null!;
    private ChartHeatmapSeries2D _heatmap = null!;
    private TcVisualScene2D _scaleScene = null!;
    private PlotProjectionRef2D _scaleProjection = null!;
    private PlotHeatmapItemRef2D _scale = null!;
    private Chart2DWpfInteraction? _interaction;
    private int _dataset;
    private bool _ready;
    private bool _closed;
    private int _renderedFrames;

    public Heatmap2DWindow()
    {
        Title = "Heatmap — uniform grid + retained line";
        Width = 1100;
        Height = 730;
        MinWidth = 720;
        MinHeight = 480;
        Background = new SolidColorBrush(Color.FromRgb(24, 24, 32));
        Foreground = Brushes.White;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        BuildControls();

        string font = Plot3DControl.FindSystemFont()
            ?? throw new InvalidOperationException("No system TTF font for the heatmap demo.");
        _gpu = Tgfx2Host.Acquire(font, BackendType.D3D11);
        try
        {
            _chart = new Chart2D(_gpu, 900, 550, Bounds);
            _chart.TitleText = "Uniform grid • NaN hole • line overlay";
            _chart.XAxisText = "X";
            _chart.YAxisText = "Y";
            _heatmap = _chart.AddHeatmapSeries("Field", MakeValues(), Rows, Columns, Bounds);

            var x = Enumerable.Range(0, 400).Select(i => -4 + 8.0 * i / 399).ToArray();
            _chart.AddLineSeries("Probe path", x, x.Select(v => 0.9 * Math.Sin(v * 1.4)).ToArray(),
                style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(1, 1, 1), thicknessPx: 2.5f));

            // The scale is another native scalar heatmap. It shares the real
            // palette/range semantics instead of duplicating palette math in WPF.
            _scaleScene = new TcVisualScene2D();
            var rect = new PlotRect2D(0, 0, 30, 350);
            _scaleProjection = PlotProjectionRef2D.Create(_scaleScene,
                new PlotProjectionDescriptor2D(rect, rect, new PlotRange2D(0, 1, 0, 1), rect));
            _scale = PlotHeatmapItemRef2D.Create(_scaleScene, _scaleProjection,
                new double[256], 256, 1, new PlotRange2D(0, 1, 0, 1));
            _host.FramebufferChanged += (_, e) => _chart.Resize(e.Width, e.Height, e.PixelScale);
            _scaleHost.FramebufferChanged += (_, e) =>
            {
                var area = new PlotRect2D(0, 0, e.Width, e.Height);
                _scaleProjection.Update(new PlotProjectionDescriptor2D(area, area,
                    new PlotRange2D(0, 1, 0, 1), area, e.PixelScale));
            };
            _host.RenderFailed += OnRenderFailed;
            _scaleHost.RenderFailed += OnRenderFailed;
            _host.FrameRendered += (_, _) => ++_renderedFrames;
            _host.Attach(_gpu, _chart.Scene);
            _scaleHost.Attach(_gpu, _scaleScene);
            _interaction = new Chart2DWpfInteraction(_host, _chart);
            _host.RenderHost.FramebufferMouseMove += OnMouseMove;
            _ready = true;
            UpdateStyle();
            _status.Text = "Middle-drag: pan · Wheel: zoom · Ctrl+wheel: X only · Hover: cell value · Missing cells are transparent";
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"HEATMAP_DEMO_INIT_FAILED {error}");
            DisposeNative();
            throw;
        }
        Closed += (_, _) => DisposeNative();
    }

    private void BuildControls()
    {
        var root = new DockPanel();
        var toolbar = new WrapPanel { Margin = new Thickness(12, 10, 12, 6) };
        toolbar.Children.Add(new TextBlock { Text = "Palette", VerticalAlignment = VerticalAlignment.Center });
        foreach (var map in new[] { PlotColorMap2D.Viridis, PlotColorMap2D.Plasma,
                     PlotColorMap2D.Jet, PlotColorMap2D.Grayscale, PlotColorMap2D.CoolWarm })
            _palette.Items.Add(map);
        _palette.SelectedIndex = 0;
        _palette.SelectionChanged += (_, _) => UpdateStyle();
        _reversed.Checked += (_, _) => UpdateStyle();
        _reversed.Unchecked += (_, _) => UpdateStyle();
        _autoRange.Checked += (_, _) => UpdateStyle();
        _autoRange.Unchecked += (_, _) => UpdateStyle();
        _bilinear.Checked += (_, _) => UpdateStyle();
        _bilinear.Unchecked += (_, _) => UpdateStyle();
        toolbar.Children.Add(_palette);
        toolbar.Children.Add(_reversed);
        toolbar.Children.Add(_autoRange);
        toolbar.Children.Add(_bilinear);
        toolbar.Children.Add(new TextBlock { Text = "Fixed: −1 … 1", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 14, 0) });
        var regenerate = new Button { Content = "New field", Padding = new Thickness(9, 4, 9, 4), Margin = new Thickness(0, 0, 8, 0) };
        regenerate.Click += (_, _) =>
        {
            ++_dataset;
            _heatmap.SetData(MakeValues(), Rows, Columns, Bounds);
            UpdateScale();
            _host.RequestRender();
        };
        toolbar.Children.Add(regenerate);
        var fit = new Button { Content = "Fit", Padding = new Thickness(9, 4, 9, 4) };
        fit.Click += (_, _) =>
        {
            _chart.Fit(0);
            _host.RequestRender();
        };
        toolbar.Children.Add(fit);
        DockPanel.SetDock(toolbar, Dock.Top);
        root.Children.Add(toolbar);
        DockPanel.SetDock(_status, Dock.Bottom);
        root.Children.Add(_status);

        var plots = new Grid();
        plots.ColumnDefinitions.Add(new ColumnDefinition());
        plots.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(88) });
        plots.Children.Add(_host);
        var scalePanel = new Grid { Margin = new Thickness(8, 48, 16, 65) };
        scalePanel.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        scalePanel.RowDefinitions.Add(new RowDefinition());
        scalePanel.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        scalePanel.Children.Add(_maximum);
        var border = new Border { BorderThickness = new Thickness(1), BorderBrush = Brushes.Gray,
            Margin = new Thickness(16, 6, 16, 6), Child = _scaleHost };
        Grid.SetRow(border, 1);
        scalePanel.Children.Add(border);
        Grid.SetRow(_minimum, 2);
        scalePanel.Children.Add(_minimum);
        Grid.SetColumn(scalePanel, 1);
        plots.Children.Add(scalePanel);
        root.Children.Add(plots);
        Content = root;
    }

    private double[] MakeValues()
    {
        var values = new double[Rows * Columns];
        double phase = _dataset * 0.7;
        for (uint row = 0; row < Rows; ++row)
        for (uint column = 0; column < Columns; ++column)
        {
            double x = Bounds.XMin + (column + 0.5) * (Bounds.XMax - Bounds.XMin) / Columns;
            double y = Bounds.YMin + (row + 0.5) * (Bounds.YMax - Bounds.YMin) / Rows;
            double peak = Math.Exp(-((x - Math.Sin(phase)) * (x - Math.Sin(phase)) + (y - 0.8) * (y - 0.8)));
            double trough = Math.Exp(-((x + 1.7) * (x + 1.7) + (y + 0.9) * (y + 0.9)) * 1.5);
            values[row * Columns + column] = (x - 2.1) * (x - 2.1) + (y + 1.6) * (y + 1.6) < 0.26
                ? double.NaN
                : 1.3 * peak - trough + 0.25 * Math.Sin(x * 2 + phase) * Math.Cos(y * 2.2);
        }
        return values;
    }

    private void UpdateStyle()
    {
        if (!_ready)
            return;
        _heatmap.Style = new PlotHeatmapStyle2D((PlotColorMap2D)_palette.SelectedItem,
            colorMapReversed: _reversed.IsChecked == true, autoRange: _autoRange.IsChecked == true,
            scalarMin: -1, scalarMax: 1,
            interpolation: _bilinear.IsChecked == true
                ? PlotHeatmapInterpolation2D.Bilinear : PlotHeatmapInterpolation2D.Nearest);
        UpdateScale();
        _host.RequestRender();
    }

    private void UpdateScale()
    {
        var snapshot = _heatmap.Item.Snapshot;
        var values = Enumerable.Range(0, 256)
            .Select(i => snapshot.ScalarMin + (snapshot.ScalarMax - snapshot.ScalarMin) * i / 255.0).ToArray();
        _scale.SetData(values, 256, 1, new PlotRange2D(0, 1, 0, 1));
        var style = _heatmap.Style;
        _scale.Style = new PlotHeatmapStyle2D(style.ColorMap, style.ColorMapReversed,
            autoRange: false, scalarMin: snapshot.ScalarMin, scalarMax: snapshot.ScalarMax,
            interpolation: PlotHeatmapInterpolation2D.Bilinear);
        _maximum.Text = snapshot.ScalarMax.ToString("G4");
        _minimum.Text = snapshot.ScalarMin.ToString("G4");
        _scaleHost.RequestRender();
    }

    private void OnMouseMove(object? sender, Tgfx2D3D11MouseMoveEventArgs e)
    {
        var point = _chart.Projection.VisualToData(new PlotVisualPoint2D(e.X, e.Y));
        if (!_heatmap.Item.TrySample(point.X, point.Y, out var sample))
            return;
        string value = double.IsNaN(sample.Value) ? "missing (NaN)" : sample.Value.ToString("G6");
        _status.Text = $"Row {sample.Row}, column {sample.Column} · X {point.X:F3}, Y {point.Y:F3} · Value {value}";
    }

    private void OnRenderFailed(object? sender, RetainedSceneRenderFailedEventArgs e)
    {
        Console.Error.WriteLine($"HEATMAP_DEMO_RENDER_FAILED {e.Error}");
        _status.Text = $"Rendering failed: {e.Error.Message}";
        _status.Foreground = Brushes.OrangeRed;
        if (_smokeTimer is not null)
            FailSmoke(e.Error);
    }

    private void DisposeNative()
    {
        if (_closed)
            return;
        _closed = true;
        _smokeTimer?.Stop();
        _interaction?.Dispose();
        _host.Dispose();
        _scaleHost.Dispose();
        _scaleProjection?.Dispose();
        _scaleScene?.Dispose();
        _chart?.Dispose();
        Tgfx2Host.Release();
    }
}
