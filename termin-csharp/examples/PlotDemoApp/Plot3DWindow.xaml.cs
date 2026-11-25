using System;
using System.Windows;
using Termin.Native;

namespace PlotDemoApp;

public partial class Plot3DWindow : Window
{
    public Plot3DWindow()
    {
        InitializeComponent();
        Plot.NativeInitialized += (_, _) => Populate();
    }

    private void Populate()
    {
        RetainedChart3D chart = Plot.Chart;
        chart.MsaaSamples = 8;
        chart.SetAxisLabels("X", "Y", "Z");
        chart.SetSurfaceShading(true, 0.35f);
        chart.SetLightDirection(-0.4f, -0.6f, 0.7f);

        const int n = 200;
        var x = new double[n];
        var y = new double[n];
        var z = new double[n];
        for (int i = 0; i < n; i++)
        {
            double t = i * 0.2;
            x[i] = Math.Cos(t);
            y[i] = Math.Sin(t);
            z[i] = t * 0.1;
        }
        chart.Scene.AddLine(x, y, z,
            new LineItemStyle3D(0.1f, 0.55f, 1, thickness: 2));

        var sx = new double[50];
        var sy = new double[50];
        var sz = new double[50];
        var rnd = new Random(42);
        for (int i = 0; i < 50; i++)
        {
            double t = i * 0.8;
            sx[i] = Math.Cos(t) + (rnd.NextDouble() - 0.5) * 0.3;
            sy[i] = Math.Sin(t) + (rnd.NextDouble() - 0.5) * 0.3;
            sz[i] = t * 0.1 + (rnd.NextDouble() - 0.5) * 0.3;
        }
        chart.Scene.AddScatter(sx, sy, sz,
            new ScatterItemStyle3D(1, 0.95f, 0.35f, size: 6));

        const uint rows = 30;
        const uint cols = 30;
        var surfaceX = new double[rows * cols];
        var surfaceY = new double[rows * cols];
        var surfaceZ = new double[rows * cols];
        for (uint row = 0; row < rows; row++)
        {
            for (uint col = 0; col < cols; col++)
            {
                double xv = -2.0 + col * (4.0 / (cols - 1));
                double yv = -2.0 + row * (4.0 / (rows - 1));
                uint index = row * cols + col;
                surfaceX[index] = xv;
                surfaceY[index] = yv;
                surfaceZ[index] = -2.0 + Math.Exp(-(xv * xv + yv * yv) * 0.5);
            }
        }
        chart.Scene.AddSurface(surfaceX, surfaceY, surfaceZ, rows, cols,
            new SurfaceItemStyle3D(
                colorMap: PlotColorMap3D.Viridis,
                surfaceGridVisible: true, surfaceGridRowStep: 5, surfaceGridColumnStep: 5,
                surfaceGridR: 0.05f, surfaceGridG: 0.05f, surfaceGridB: 0.05f,
                surfaceGridA: 0.85f, surfaceGridWidthPx: 1.5f));

        SetIsometricView();
        CameraControls.IsEnabled = true;
    }

    private void SetIsometricView()
    {
        Plot.Chart.Camera.SetIsometric();
        ProjectionLabel.Text = "Orthographic";
    }

    private void OnIsometric(object sender, RoutedEventArgs e) => SetIsometricView();

    private void OnPerspective(object sender, RoutedEventArgs e)
    {
        Chart3DCamera camera = Plot.Chart.Camera;
        camera.State = camera.State.WithProjection(CameraProjection.Perspective);
        camera.Fit();
        ProjectionLabel.Text = "Perspective";
    }

    private void OnFit(object sender, RoutedEventArgs e) => Plot.Chart.Camera.Fit();
}
