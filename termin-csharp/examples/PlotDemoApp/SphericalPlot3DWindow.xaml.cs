using System;
using System.Windows;
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
    private readonly SphericalSurfaceItemRef3D _surface;
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
    }

    private void OnAdvanceWave(object sender, RoutedEventArgs e)
    {
        _phase += Math.PI / 6;
        _surface.SetRadii(CreateRadii(_phase));
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
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (_closed)
            return;
        _closed = true;
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
