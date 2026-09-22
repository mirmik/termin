using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

public partial class SphericalPlot3DWindow : Window
{
    private const uint PolarCount = 61;
    private const uint AzimuthCount = 96;

    private readonly GpuHost _gpuHost;
    private readonly RetainedChart3D _chart;
    private SphericalSurfaceItemRef3D _surface;
    private const double DisplayFloor = -40;
    private static readonly double ConstantRadius = 10 * Math.Log10(0.002) - DisplayFloor;
    private bool _initialized;
    private bool _showPhysicalValues = true;
    private int _dataset;
    private bool _wireframe;
    private bool _closed;
    private double _phase;

    public SphericalPlot3DWindow()
    {
        InitializeComponent();

        string fontPath = Plot3DControl.FindSystemFont()
            ?? throw new InvalidOperationException(
                "No system TTF font found for the spherical plot demo.");
        _gpuHost = Tgfx2Host.Acquire(fontPath, BackendType.D3D11);
        RetainedChart3D? chart = null;
        try
        {
            chart = RetainedChart3D.CreateSpherical(_gpuHost);
            _chart = chart;
            _chart.MsaaSamples = 4;
            _chart.SetAxisLabels("azimuth", "polar", "radius");
            _chart.SetSurfaceShading(true, 0.42f);
            _chart.SetLightDirection(-0.45f, -0.55f, 0.72f);

            double[] azimuths = CreateAzimuths();
            double[] polarAngles = CreatePolarAngles();
            _surface = _chart.Scene.AddSphericalSurface(
                azimuths,
                polarAngles,
                CreateRadii(_phase),
                closeAzimuth: true,
                style: CreateSurfaceStyle(wireframe: false));
            _chart.ShowColorBar(
                _surface,
                "radius",
                new ColorBarStyle3D(tickCount: 7, widthPx: 20, textSizePx: 12));
            _chart.Camera.Fit();

            ChartHost.Attach(_chart);
            ChartHost.ContinuousRendering = false;
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
        _initialized = true;
        UpdateDisplay();
    }

    private void OnDatasetChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_initialized)
            return;
        SelectDataset(DatasetBox.SelectedIndex);
    }

    private void SelectDataset(int dataset)
    {
        _dataset = dataset;
        _surface.SetRadii(CreateDatasetRadii());
        UpdateDisplay();
        _chart.Camera.Fit();
        ChartHost.RequestRender();
        StatusText.Text = dataset switch
        {
            0 => "Radius wave. Offset = 0; values equal geometry radii.",
            1 => "ЭПР in dBsm: radius = value + 40. Negative, zero and positive displayed values.",
            2 => "ЭПР = 0.002 m² → −26.9897 dBsm; radius = 13.0103. Colorbar has one true value.",
            _ => "≤ −40 dBsm: включая 0 м² / −∞ dBsm. The custom label belongs only to radius 0.",
        };
    }

    private double[] CreateDatasetRadii()
    {
        if (_dataset == 0)
            return CreateRadii(_phase);
        if (_dataset == 2)
        {
            var constant = new double[checked((int)(PolarCount * AzimuthCount))];
            Array.Fill(constant, ConstantRadius);
            return constant;
        }
        var values = new double[checked((int)(PolarCount * AzimuthCount))];
        for (uint row = 0; row < PolarCount; ++row)
        {
            double polar = Math.PI * row / (PolarCount - 1);
            for (uint column = 0; column < AzimuthCount; ++column)
            {
                double azimuth = 2 * Math.PI * column / AzimuthCount;
                double wave = row == 0 || row == PolarCount - 1 ? 0
                    : Math.Pow(Math.Sin(polar), 2) * Math.Cos(2 * azimuth + _phase);
                double radius = 25 * (1 + wave);
                values[row * AzimuthCount + column] = _dataset == 3 && radius < 7 ? 0 : radius;
            }
        }
        return values;
    }

    private void UpdateDisplay()
    {
        bool physical = _dataset != 0 && _showPhysicalValues;
        _chart.SetAxisLabels("azimuth", "polar", physical ? "dBsm" : "radius");
        _chart.ShowColorBar(_surface, physical ? "ЭПР, dBsm" : "radius",
            new ColorBarStyle3D(tickCount: 7, widthPx: 20, textSizePx: 14));
        _chart.SetAxisTickLabel(PlotAxis3D.Radius, 0,
            physical && _dataset == 3 ? "≤ −40 dBsm" : null);
        _chart.SetAxisDisplayOffset(PlotAxis3D.Radius, physical ? DisplayFloor : 0);
        OffsetButton.Content = physical ? "Show geometry values" : "Show physical values";
    }

    private void OnToggleOffset(object sender, RoutedEventArgs e)
    {
        _showPhysicalValues = !_showPhysicalValues;
        UpdateDisplay();
        StatusText.Text = "Only displayed values changed; surface colors, geometry and camera stay fixed.";
    }

    private void OnReplaceSurface(object sender, RoutedEventArgs e)
    {
        _surface.Destroy();
        _surface = _chart.Scene.AddSphericalSurface(CreateAzimuths(), CreatePolarAngles(),
            CreateDatasetRadii(), closeAzimuth: true, style: CreateSurfaceStyle(_wireframe));
        GridItemRef3D? previousGrid = _chart.Parts.Grid;
        _chart.Parts.ReplaceGrid(_chart.Scene.AddGrid());
        previousGrid?.Destroy();
        _chart.HideColorBar();
        _chart.ShowColorBar(_surface, _showPhysicalValues && _dataset != 0 ? "ЭПР, dBsm" : "radius",
            new ColorBarStyle3D(tickCount: 7, widthPx: 20, textSizePx: 14));
        ChartHost.RequestRender();
        StatusText.Text = "Surface, grid and colorbar replaced; display settings and camera preserved.";
    }

    private void OnAdvanceWave(object sender, RoutedEventArgs e)
    {
        _phase += Math.PI / 6;
        _surface.SetRadii(CreateDatasetRadii());
        ChartHost.RequestRender();
        PlotItemSnapshot3D snapshot = _surface.Snapshot;
        StatusText.Text =
            $"Radius table updated in place; geometry revision {snapshot.GeometryRevision}.";
    }

    private void OnToggleWireframe(object sender, RoutedEventArgs e)
    {
        _wireframe = !_wireframe;
        _surface.Style = CreateSurfaceStyle(_wireframe);
        WireframeButton.Content = _wireframe ? "Filled surface" : "Wireframe";
        ChartHost.RequestRender();
        StatusText.Text = _wireframe
            ? "Wireframe rendering enabled."
            : "Filled surface rendering enabled.";
    }

    private void OnFitCamera(object sender, RoutedEventArgs e)
    {
        _chart.Camera.Fit();
        ChartHost.RequestRender();
        StatusText.Text = "Camera fitted to the spherical grid and surface.";
    }

    private void OnRenderFailed(
        object? sender,
        RetainedSceneRenderFailedEventArgs e)
    {
        StatusText.Text = $"Rendering stopped: {e.Error.Message}";
        StatusText.Foreground = Brushes.OrangeRed;
        Console.Error.WriteLine($"SPHERICAL_PLOT_RENDER_FAILED {e.Error}");
        if (_smokeTimer is not null)
            FailSmoke(e.Error);
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (_closed)
            return;
        _closed = true;
        _smokeTimer?.Stop();
        Closed -= OnClosed;
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

    private static double[] CreateAzimuths()
    {
        var values = new double[AzimuthCount];
        for (uint column = 0; column < AzimuthCount; ++column)
            values[column] = 2 * Math.PI * column / AzimuthCount;
        return values;
    }

    private static double[] CreatePolarAngles()
    {
        var values = new double[PolarCount];
        for (uint row = 0; row < PolarCount; ++row)
            values[row] = Math.PI * row / (PolarCount - 1);
        return values;
    }

    private static double[] CreateRadii(double phase)
    {
        var radii = new double[checked((int)(PolarCount * AzimuthCount))];
        for (uint row = 0; row < PolarCount; ++row)
        {
            double polar = Math.PI * row / (PolarCount - 1);
            double sinPolar = Math.Sin(polar);
            for (uint column = 0; column < AzimuthCount; ++column)
            {
                double azimuth = 2 * Math.PI * column / AzimuthCount;
                double azimuthLobes = row == 0 || row == PolarCount - 1
                    ? 0
                    : 0.36 * sinPolar * sinPolar * Math.Cos(3 * azimuth + phase);
                double polarLobes = 0.18 * Math.Cos(2 * polar - phase * 0.35);
                radii[row * AzimuthCount + column] =
                    1.35 + azimuthLobes + polarLobes;
            }
        }
        return radii;
    }

    private static SurfaceItemStyle3D CreateSurfaceStyle(bool wireframe) => new(
        colorMap: PlotColorMap3D.Plasma,
        wireframe: wireframe,
        surfaceGridVisible: true,
        surfaceGridRowStep: 6,
        surfaceGridColumnStep: 8,
        surfaceGridWidthPx: 1.2f,
        surfaceGridR: 0.82f,
        surfaceGridG: 0.88f,
        surfaceGridB: 0.96f,
        surfaceGridA: 0.55f);
}
