using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Threading;
using Termin.Native;

namespace PlotDemoApp;

// Three stacked panels share one X axis; each panel is fed by a
// different signal that keeps appending in real time. Autoscroll
// keeps the last 10 seconds on screen.
public partial class MultiPlot2DWindow : Window
{
    private ChartLineSeries2D _sin = null!;
    private ChartLineSeries2D _cos = null!;
    private ChartLineSeries2D _noise = null!;

    private readonly DispatcherTimer _timer;
    private readonly Stopwatch _clock = new();
    private readonly Random _rng = new(12345);

    public MultiPlot2DWindow()
    {
        InitializeComponent();

        _timer = new DispatcherTimer(DispatcherPriority.Render)
        {
            Interval = TimeSpan.FromMilliseconds(30),
        };
        _timer.Tick += OnTick;

        Plot.NativeInitialized += OnNativeReady;
        Closed += (_, _) =>
        {
            _timer.Stop();
            Plot.Dispose();
        };
    }

    private void OnNativeReady(object? sender, EventArgs e)
    {
        Chart2D sinChart = Plot.Chart.Panels[0].Chart;
        Chart2D cosChart = Plot.Chart.Panels[1].Chart;
        Chart2D noiseChart = Plot.Chart.Panels[2].Chart;
        sinChart.TitleText = "sin(t)";
        cosChart.TitleText = "cos(0.7·t)";
        noiseChart.TitleText = "noise";
        sinChart.YAxisText = "amplitude";
        cosChart.YAxisText = "amplitude";
        noiseChart.YAxisText = "value";
        noiseChart.XAxisText = "t, s";

        var seedX = new[] { 0.0 };
        var zero = new[] { 0.0 };
        _sin = sinChart.AddLineSeries("sin", seedX, zero,
            style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(0.3f, 0.8f, 1)),
            showInLegend: false);
        _cos = cosChart.AddLineSeries("cos", seedX, new[] { 1.0 },
            style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(1, 0.6f, 0.2f)),
            showInLegend: false);
        _noise = noiseChart.AddLineSeries("noise", seedX, zero,
            style: new PlotLineSeriesStyle2D(new PlotSrgbColor2D(0.9f, 0.9f, 0.3f)),
            showInLegend: false);

        _clock.Start();
        _timer.Start();
    }

    private void OnTick(object? sender, EventArgs e)
    {
        double t = _clock.Elapsed.TotalSeconds;

        // Batch-append a few samples per tick — exercises the
        // multi-point path as well as single-point.
        const int batch = 3;
        var xs = new double[batch];
        var sinY = new double[batch];
        var cosY = new double[batch];
        var noiseY = new double[batch];
        for (int i = 0; i < batch; i++)
        {
            double ti = t + i * 0.01;
            xs[i] = ti;
            sinY[i]   = Math.Sin(ti);
            cosY[i]   = Math.Cos(ti * 0.7);
            noiseY[i] = (_rng.NextDouble() - 0.5) * 2.0;
        }

        _sin.Append(xs, sinY);
        _cos.Append(xs, cosY);
        _noise.Append(xs, noiseY);
        Plot.UpdateAfterAppend(xs[^1]);
    }
}
