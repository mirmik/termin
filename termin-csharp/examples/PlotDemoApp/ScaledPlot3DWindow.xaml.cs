using System;
using System.Windows;
using Termin.Native;

namespace PlotDemoApp;

public partial class ScaledPlot3DWindow : Window
{
    public ScaledPlot3DWindow()
    {
        InitializeComponent();
        Plot.NativeInitialized += (_, _) => Populate();
    }

    private void Populate()
    {
        RetainedChart3D chart = Plot.Chart;
        chart.MsaaSamples = 8;
        chart.SetAxisLabels("time, s", "angle, deg", "20log10|S|");
        chart.SetAxisScale(1_000_000f, 1, 40);
        chart.SetSurfaceShading(true, 0.42f);
        chart.SetLightDirection(-0.4f, -0.6f, 0.7f);

        const uint rows = 72;
        const uint cols = 96;
        var x = new double[rows * cols];
        var y = new double[rows * cols];
        var z = new double[rows * cols];

        for (uint row = 0; row < rows; row++)
        {
            for (uint col = 0; col < cols; col++)
            {
                double timeSeconds = col * 500e-6 / (cols - 1);
                double angleDegrees = -45.0 + row * 90.0 / (rows - 1);
                double pulse = Math.Exp(-Math.Pow((timeSeconds - 310e-6) / 38e-6, 2.0));
                double lobe = Math.Exp(-Math.Pow((angleDegrees - 12.0) / 13.0, 2.0));
                double ridge = 0.35 * Math.Exp(-Math.Pow((timeSeconds - 155e-6) / 82e-6, 2.0))
                             * Math.Exp(-Math.Pow((angleDegrees + 24.0) / 8.0, 2.0));
                double ripple = 0.06 * Math.Sin(timeSeconds * 2.0 * Math.PI / 42e-6)
                              * Math.Cos(angleDegrees * Math.PI / 18.0);
                uint index = row * cols + col;
                x[index] = timeSeconds;
                y[index] = angleDegrees;
                z[index] = 0.08 + 1.8 * pulse * lobe + ridge + ripple;
            }
        }

        chart.Scene.AddSurface(x, y, z, rows, cols,
            new SurfaceItemStyle3D(
                colorMap: PlotColorMap3D.Plasma,
                surfaceGridVisible: true, surfaceGridRowStep: 8, surfaceGridColumnStep: 12,
                surfaceGridR: 0.04f, surfaceGridG: 0.04f, surfaceGridB: 0.04f,
                surfaceGridA: 0.72f, surfaceGridWidthPx: 2.5f));

        chart.Camera.Fit();
    }
}
