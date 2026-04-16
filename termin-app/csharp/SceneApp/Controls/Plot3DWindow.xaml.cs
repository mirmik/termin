using System;
using System.Windows;

namespace SceneApp.Controls;

// Launch via: new Plot3DWindow().Show();
// Populates a scatter + surface + helix demo on first render tick so
// the Plot3DControl has its PlotView3D constructed before we touch
// its data API.
public partial class Plot3DWindow : Window
{
    private bool _populated;

    public Plot3DWindow()
    {
        InitializeComponent();
        // Populate after the Plot3DControl has been loaded and its
        // native view constructed. The easiest hook is the first
        // ContentRendered event.
        ContentRendered += (_, _) => PopulateOnce();
    }

    private void PopulateOnce()
    {
        if (_populated) return;
        _populated = true;

        // Helix: N=200 points.
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
        Plot.Plot(x, y, z, 0.2f, 0.6f, 1.0f, 1.0f, thickness: 2.0, label: "helix");

        // Scatter cloud around the helix.
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
        Plot.Scatter(sx, sy, sz, 1.0f, 0.7f, 0.2f, 1.0f, size: 6.0, label: "noise");

        // Surface: 30x30 gaussian-ish bump, offset below the helix so
        // we actually see two things in the same view.
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
        Plot.Surface(X, Y, Z, R, C,
                     0f, 0f, 0f, 1f,           // ignored — engine picks jet
                     wireframe: false,
                     label: "gaussian");

        // Fit camera to the combined extent.
        Plot.View.fit_camera();
    }
}
