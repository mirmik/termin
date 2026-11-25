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

            Chart2D chart = Plot.Chart;
            chart.TitleText = "Route visualization";
            chart.XAxisText = "X, m";
            chart.YAxisText = "Y, m";

            chart.AddLineSeries("true trajectory by Z", trueX, trueY, trueZ,
                new PlotLineSeriesStyle2D(new PlotSrgbColor2D(1, 1, 1),
                    thicknessPx: 3, colorMap: PlotColorMap2D.Viridis,
                    colorMapReversed: true, scalarMin: zMin, scalarMax: zMax));

            chart.AddLineSeries("navigation", navX, navY,
                style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(0, 0.47f, 0.83f),
                    thicknessPx: 2, lineStyle: PlotLineStyle2D.Dash, dashPx: 12, gapPx: 7));

            chart.AddScatterSeries("start", new[] { trueX[0] }, new[] { trueY[0] },
                new PlotScatterSeriesStyle2D(new PlotSrgbColor2D(0, 1, 0), diameterPx: 12));
            chart.AddScatterSeries("finish", new[] { trueX[^1] }, new[] { trueY[^1] },
                new PlotScatterSeriesStyle2D(new PlotSrgbColor2D(1, 0, 0), diameterPx: 12));
            chart.Fit();
        };
    }
}
