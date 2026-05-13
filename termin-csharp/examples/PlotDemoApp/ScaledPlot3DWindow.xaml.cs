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
        Plot.View.set_msaa_samples(8);
        Plot.SetAxisLabels("time, us", "angle, deg", "20log10|S|");
        Plot.SetAxisScale(1_000_000f, 1.0f, 40.0f);
        Plot.SetSurfaceShading(true, 0.42f);
        Plot.SetSurfaceLightDir(-0.4f, -0.6f, 0.7f);

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

        Plot.SurfaceColormap(x, y, z, rows, cols,
                             SurfaceColorMap.Plasma,
                             0f, 0f, 0f, 1f,
                             wireframe: false,
                             label: "scaled-time-surface");
        Plot.SetSurfaceGrid(0, visible: true,
                            rowStep: 8, colStep: 12,
                            0.04f, 0.04f, 0.04f, 0.72f);

        Plot.View.fit_camera();
    }
}
