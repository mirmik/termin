using System;
using System.Windows;
using Termin.Native;

namespace PlotDemoApp;

public partial class Plot3DWindow : Window
{
    public Plot3DWindow()
    {
        InitializeComponent();
        // Populate once the Plot3DControl's native view is ready.
        Plot.NativeInitialized += (_, _) => Populate();
    }

    private void Populate()
    {
        Plot.View.set_msaa_samples(8);
        Plot.SetAxisLabels("X", "Y", "Z");
        Plot.SetSurfaceShading(true, 0.35f);
        Plot.SetSurfaceLightDir(-0.4f, -0.6f, 0.7f);

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
        Plot.Plot(x, y, z, 0.1f, 0.55f, 1.0f, 1.0f, thickness: 2.0, label: "helix");

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
        Plot.Scatter(sx, sy, sz, 1.0f, 0.95f, 0.35f, 1.0f, size: 6.0, label: "noise");

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
        Plot.SurfaceColormap(surfaceX, surfaceY, surfaceZ, rows, cols,
                             SurfaceColorMap.Viridis,
                             0f, 0f, 0f, 1f,
                             wireframe: false,
                             label: "gaussian");
        Plot.SetSurfaceGrid(0, visible: true,
                            rowStep: 5, colStep: 5,
                            0.05f, 0.05f, 0.05f, 0.85f);

        Plot.View.fit_camera();
    }
}
