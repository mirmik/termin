using System;
using System.Linq;
using System.Windows;
using Termin.Native;

namespace PlotDemoApp;

public partial class RoutePlot2DWindow : Window
{
    public RoutePlot2DWindow()
    {
        InitializeComponent();
        Plot.NativeInitialized += (_, _) =>
        {
            const int n = 520;
            var trueX = new double[n];
            var trueY = new double[n];
            var trueZ = new double[n];
            var navX = new double[n];
            var navY = new double[n];

            for (int i = 0; i < n; ++i)
            {
                double t = i / 32.0;
                trueX[i] = t * 120.0;
                trueY[i] = 700.0 * Math.Sin(t * 0.34) + 140.0 * Math.Cos(t * 0.11);
                trueZ[i] = 420.0 + 170.0 * Math.Sin(t * 0.48) + i * 0.9;

                navX[i] = trueX[i] + 28.0 * Math.Sin(t * 1.8);
                navY[i] = trueY[i] + 55.0 * Math.Cos(t * 1.2);
            }

            double zMin = trueZ.Min();
            double zMax = trueZ.Max();

            Plot.View.set_title("Route visualization");
            Plot.View.set_x_label("X, m");
            Plot.View.set_y_label("Y, m");

            Plot.PlotColormap(trueX, trueY, trueZ, SurfaceColorMap.Viridis,
                zMin, zMax, thickness: 3.0, label: "true trajectory by Z",
                colormapReversed: true);

            Plot.Plot(navX, navY,
                0.0f, 0.47f, 0.83f, 1.0f,
                thickness: 2.0,
                label: "navigation");
            Plot.SetLineStyle(1, LineStyle.Dash, dashPx: 12.0f, gapPx: 7.0f);

            Plot.Scatter(new[] { trueX[0] }, new[] { trueY[0] },
                0.0f, 1.0f, 0.0f, 1.0f,
                size: 12.0,
                label: "start");
            Plot.Scatter(new[] { trueX[^1] }, new[] { trueY[^1] },
                1.0f, 0.0f, 0.0f, 1.0f,
                size: 12.0,
                label: "finish");
        };
    }
}
