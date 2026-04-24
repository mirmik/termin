using System;
using System.Windows;

namespace PlotDemoApp;

public partial class Plot3DWindow : Window
{
    public Plot3DWindow()
    {
        InitializeComponent();
        // Populate once the Plot3DControl's native view is ready. The
        // control fires NativeInitialized after tc_opengl_init +
        // PlotView3D construction complete.
        Plot.NativeInitialized += (_, _) => Populate();
    }

    private void Populate()
    {
        // MSAA setting is per-view; default (4) is set by the C++
        // side. Override here to taste — e.g. `Plot.View.set_msaa_samples(2)`.
        Plot.View.set_msaa_samples(8);

        // Helix: 200 points along (cos t, sin t, 0.1 t).
        const int N = 200;
        var x = new double[N];
        var y = new double[N];
        var z = new double[N];
        for (int i = 0; i < N; i++)
        {
            double t = i * 0.2;
            x[i] = Math.Cos(t);
            y[i] = Math.Sin(t);
            z[i] = t * 0.1;
        }
        // Lighter cyan than the default blue so the helix stands out
        // against the brightened grid under MSAA.
        Plot.Plot(x, y, z, 0.1f, 0.55f, 1.0f, 1.0f, thickness: 2.0, label: "helix");

        // Noisy scatter around the helix.
        var sx = new double[50];
        var sy = new double[50];
        var sz = new double[50];
        var rnd = new Random(42);
        for (int i = 0; i < 50; i++)
        {
            double t = i * 0.8;
            sx[i] = Math.Cos(t) + (rnd.NextDouble() - 0.5) * 0.3;
            sy[i] = Math.Sin(t) + (rnd.NextDouble() - 0.5) * 0.3;
            sz[i] = t * 0.1      + (rnd.NextDouble() - 0.5) * 0.3;
        }
        // Saturated yellow for the scatter markers; thin cross-lines
        // need the extra brightness to read clearly under MSAA.
        Plot.Scatter(sx, sy, sz, 1.0f, 0.95f, 0.35f, 1.0f, size: 6.0, label: "noise");

        // Gaussian bump on a 30x30 grid, placed below the helix.
        const uint R = 30, C = 30;
        var X = new double[R * C];
        var Y = new double[R * C];
        var Z = new double[R * C];
        for (uint j = 0; j < R; j++)
        {
            for (uint i = 0; i < C; i++)
            {
                double xv = -2.0 + i * (4.0 / (C - 1));
                double yv = -2.0 + j * (4.0 / (R - 1));
                X[j * C + i] = xv;
                Y[j * C + i] = yv;
                Z[j * C + i] = -2.0 + Math.Exp(-(xv * xv + yv * yv) * 0.5);
            }
        }
        // Color tuple is ignored by the engine when surface picks the
        // jet colormap from normalised Z; any value works.
        Plot.Surface(X, Y, Z, R, C,
                     0f, 0f, 0f, 1f,
                     wireframe: false,
                     label: "gaussian");

        Plot.View.fit_camera();
    }
}
