using System;
using System.Windows;

namespace PlotDemoApp;

public partial class Plot2DWindow : Window
{
    public Plot2DWindow()
    {
        InitializeComponent();
        Plot.NativeInitialized += (_, _) =>
        {
            Plot.View.set_title("sine demo");
            Plot.View.set_x_label("t");
            Plot.View.set_y_label("f(t)");

            // High-res sine: 400 points — the whole series hits one
            // draw call in the C++ engine2d, no drag lag.
            const int N = 400;
            var x = new double[N];
            var y = new double[N];
            for (int i = 0; i < N; i++)
            {
                double t = i * 0.05;
                x[i] = t;
                y[i] = Math.Sin(t);
            }
            Plot.Plot(x, y, 0.2f, 0.6f, 1.0f, 1.0f, thickness: 1.5, label: "sin");

            // Secondary: dampened sine.
            var y2 = new double[N];
            for (int i = 0; i < N; i++)
            {
                y2[i] = Math.Sin(x[i]) * Math.Exp(-x[i] * 0.05);
            }
            Plot.Plot(x, y2, 1.0f, 0.5f, 0.1f, 1.0f, thickness: 1.5, label: "damped");

            // Scatter samples from the same function.
            var sx = new double[20];
            var sy = new double[20];
            for (int i = 0; i < 20; i++)
            {
                sx[i] = i * 1.0;
                sy[i] = Math.Sin(sx[i]);
            }
            Plot.Scatter(sx, sy, 0.2f, 0.8f, 0.2f, 1.0f, size: 6.0, label: "samples");
        };
    }
}
