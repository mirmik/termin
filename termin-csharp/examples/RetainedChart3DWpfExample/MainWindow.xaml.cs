using System;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace RetainedChart3DWpfExample;

public partial class MainWindow : Window
{
    private const uint SurfaceRows = 72;
    private const uint SurfaceColumns = 84;
    private readonly GpuHost _gpuHost;
    private readonly RetainedChart3D _chart;
    private readonly SurfaceItemRef3D _surface;
    private readonly ScatterItemRef3D _scatter;
    private readonly GridItemRef3D _customGrid;
    private readonly TextBlock _title;
    private readonly Button _dataButton;
    private readonly Button _wireframeButton;
    private readonly Button _shadingButton;
    private readonly Button _resetCameraButton;
    private bool _wireframe;
    private bool _shading = true;
    private bool _closed;
    private double _surfacePhase;

    public MainWindow()
    {
        InitializeComponent();

        _gpuHost = Tgfx2Host.Acquire(FindFont(), BackendType.D3D11);
        RetainedChart3D? chart = null;
        try
        {
            chart = new RetainedChart3D(_gpuHost);
            _chart = chart;
            _chart.MsaaSamples = 4;
            _chart.SetAxisScale(1, 1, 1.25f);
            _chart.SetAxisLabels("phase x", "phase y", "amplitude");
            _chart.SetSurfaceShading(true, 0.42f);
            _chart.SetLightDirection(-0.45f, -0.55f, 0.72f);

            (double[] x, double[] y, double[] z) =
                CreateSurface(_surfacePhase);
            _surface = _chart.Scene.AddSurface(
                x, y, z, SurfaceRows, SurfaceColumns,
                new SurfaceItemStyle3D(
                    colorMap: PlotColorMap3D.Viridis,
                    surfaceGridVisible: true,
                    surfaceGridRowStep: 8,
                    surfaceGridColumnStep: 8,
                    surfaceGridWidthPx: 1.1f,
                    surfaceGridR: 0.78f,
                    surfaceGridG: 0.88f,
                    surfaceGridB: 0.92f,
                    surfaceGridA: 0.58f));

            (double[] sx, double[] sy, double[] sz) = CreateScatter();
            _scatter = _chart.Scene.AddScatter(
                sx, sy, sz,
                new ScatterItemStyle3D(
                    colorR: 1.0f,
                    colorG: 0.26f,
                    colorB: 0.16f,
                    size: 5));

            // The standard grid remains alive, but the named chart part now
            // points at this independently retained custom grid item.
            _customGrid = _chart.Scene.AddGrid(
                new GridItemStyle3D(
                    gridR: 0.18f,
                    gridG: 0.52f,
                    gridB: 0.62f,
                    gridA: 0.82f,
                    xAxisR: 1.0f,
                    xAxisG: 0.35f,
                    xAxisB: 0.22f,
                    yAxisR: 0.32f,
                    yAxisG: 0.95f,
                    yAxisB: 0.48f,
                    zAxisR: 0.40f,
                    zAxisG: 0.58f,
                    zAxisB: 1.0f));
            _chart.Parts.ReplaceGrid(_customGrid);
            _chart.Camera.Reset();

            _title = new TextBlock
            {
                Text = "Retained surface + scatter · custom grid from C#",
                Foreground = Brushes.White,
                FontSize = 17,
                FontWeight = FontWeights.SemiBold,
                Padding = new Thickness(8, 4, 8, 4),
                Background = new SolidColorBrush(Color.FromArgb(150, 20, 24, 31)),
            };
            _dataButton = CreateButton("Advance wave");
            _wireframeButton = CreateButton("Wireframe");
            _shadingButton = CreateButton("Shading: on");
            _resetCameraButton = CreateButton("Reset camera");
            _dataButton.Click += OnDataClick;
            _wireframeButton.Click += OnWireframeClick;
            _shadingButton.Click += OnShadingClick;
            _resetCameraButton.Click += OnResetCameraClick;

            ChartHost.Attach(_chart);
            ChartHost.ContinuousRendering = false;
            ChartHost.AddPortal(_title, new Rect(12, 10, 390, 36));
            ChartHost.AddPortal(_dataButton, new Rect(496, 10, 116, 34));
            ChartHost.AddPortal(_wireframeButton, new Rect(620, 10, 116, 34));
            ChartHost.AddPortal(_shadingButton, new Rect(744, 10, 116, 34));
            ChartHost.AddPortal(_resetCameraButton, new Rect(868, 10, 128, 34));
            ChartHost.FramebufferChanged += OnFramebufferChanged;
            ChartHost.RenderFailed += OnRenderFailed;
        }
        catch
        {
            ChartHost.Dispose();
            chart?.Dispose();
            Tgfx2Host.Release();
            throw;
        }

        Closed += OnClosed;
    }

    private void OnFramebufferChanged(
        object? sender,
        RetainedSceneFramebufferChangedEventArgs e)
    {
        double width = e.Width / e.PixelScale;
        const double gap = 8;
        const double dataWidth = 116;
        const double wireWidth = 112;
        const double shadingWidth = 116;
        const double resetWidth = 124;
        const double right = 12;
        double resetX = width - right - resetWidth;
        double shadingX = resetX - gap - shadingWidth;
        double wireX = shadingX - gap - wireWidth;
        double dataX = wireX - gap - dataWidth;
        ChartHost.SetPortalBounds(
            _dataButton, new Rect(dataX, 10, dataWidth, 34));
        ChartHost.SetPortalBounds(
            _wireframeButton, new Rect(wireX, 10, wireWidth, 34));
        ChartHost.SetPortalBounds(
            _shadingButton, new Rect(shadingX, 10, shadingWidth, 34));
        ChartHost.SetPortalBounds(
            _resetCameraButton, new Rect(resetX, 10, resetWidth, 34));
        ChartHost.SetPortalBounds(
            _title,
            new Rect(12, 10, Math.Max(180, dataX - 24), 36));
    }

    private void OnDataClick(object sender, RoutedEventArgs e)
    {
        _surfacePhase += 0.45;
        (double[] x, double[] y, double[] z) =
            CreateSurface(_surfacePhase);
        _surface.SetData(x, y, z, SurfaceRows, SurfaceColumns);
        _chart.Camera.Fit();
        ChartHost.RequestRender();
        ReportCallback("Surface data changed in C# without replacing its handle");
    }

    private void OnWireframeClick(object sender, RoutedEventArgs e)
    {
        _wireframe = !_wireframe;
        SurfaceItemStyle3D style = _surface.Style;
        _surface.Style = new SurfaceItemStyle3D(
            style.ColorR,
            style.ColorG,
            style.ColorB,
            style.ColorA,
            style.ColorMap,
            style.ColorMapReversed,
            _wireframe,
            style.SurfaceGridVisible,
            style.SurfaceGridRowStep,
            style.SurfaceGridColumnStep,
            style.SurfaceGridWidthPx,
            style.SurfaceGridR,
            style.SurfaceGridG,
            style.SurfaceGridB,
            style.SurfaceGridA);
        _wireframeButton.Content = _wireframe ? "Filled surface" : "Wireframe";
        ChartHost.RequestRender();
        ReportCallback("Surface style changed in C#");
    }

    private void OnShadingClick(object sender, RoutedEventArgs e)
    {
        _shading = !_shading;
        _chart.SetSurfaceShading(_shading, 0.42f);
        _shadingButton.Content = _shading ? "Shading: on" : "Shading: off";
        ChartHost.RequestRender();
        ReportCallback("Shader policy changed in C#");
    }

    private void OnResetCameraClick(object sender, RoutedEventArgs e)
    {
        _chart.Camera.Reset();
        ChartHost.RequestRender();
        ReportCallback("Camera reset in C#");
    }

    private void ReportCallback(string action)
    {
        PlotItemSnapshot3D surface = _surface.Snapshot;
        PlotItemSnapshot3D scatter = _scatter.Snapshot;
        StatusText.Text =
            $"{action}; scene {_chart.Scene.Id}, {_chart.Scene.Count} items; " +
            $"surface rev {surface.GeometryRevision}/{surface.StyleRevision}/gpu {surface.GpuRevision}, " +
            $"scatter gpu {scatter.GpuRevision}.";
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
        _dataButton.Click -= OnDataClick;
        _wireframeButton.Click -= OnWireframeClick;
        _shadingButton.Click -= OnShadingClick;
        _resetCameraButton.Click -= OnResetCameraClick;
        ChartHost.FramebufferChanged -= OnFramebufferChanged;
        ChartHost.RenderFailed -= OnRenderFailed;
        try
        {
            ChartHost.Dispose();
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

    private static Button CreateButton(string text) => new()
    {
        Content = text,
        Padding = new Thickness(8, 2, 8, 2),
        Foreground = Brushes.White,
        Background = new SolidColorBrush(Color.FromRgb(42, 91, 140)),
        BorderBrush = new SolidColorBrush(Color.FromRgb(111, 190, 255)),
    };

    private static (double[] X, double[] Y, double[] Z) CreateSurface(
        double phase)
    {
        int count = checked((int)(SurfaceRows * SurfaceColumns));
        var x = new double[count];
        var y = new double[count];
        var z = new double[count];
        for (uint row = 0; row < SurfaceRows; ++row)
        {
            double py = -3.2 + 6.4 * row / (SurfaceRows - 1);
            for (uint column = 0; column < SurfaceColumns; ++column)
            {
                double px = -4.0 + 8.0 * column / (SurfaceColumns - 1);
                int index = checked((int)(row * SurfaceColumns + column));
                double radius = Math.Sqrt(px * px + py * py);
                x[index] = px;
                y[index] = py;
                z[index] =
                    1.35 * Math.Sin(radius * 1.8 + phase) *
                    Math.Exp(-radius * 0.22) +
                    0.18 * px - 0.08 * py;
            }
        }
        return (x, y, z);
    }

    private static (double[] X, double[] Y, double[] Z) CreateScatter()
    {
        const int count = 46;
        var x = new double[count];
        var y = new double[count];
        var z = new double[count];
        for (int index = 0; index < count; ++index)
        {
            double angle = index * Math.PI * 2 / count;
            double radius = 1.0 + 2.1 * index / (count - 1);
            x[index] = radius * Math.Cos(angle);
            y[index] = radius * Math.Sin(angle);
            z[index] = 1.6 + 0.18 * Math.Sin(angle * 4);
        }
        return (x, y, z);
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
                "No usable TTF font was found for RetainedChart3D example.");
    }
}
