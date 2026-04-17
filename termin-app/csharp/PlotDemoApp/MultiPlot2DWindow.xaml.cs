using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Threading;

namespace PlotDemoApp;

// Smoke test for PlotView2DMulti + engine2d persistent VBO path.
// Three stacked panels share one X axis; each panel is fed by a
// different signal that keeps appending in real time. Autoscroll
// keeps the last 10 seconds on screen.
public partial class MultiPlot2DWindow : Window
{
    private int _sinIdx;
    private int _cosIdx;
    private int _noiseIdx;

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
        Plot.SetPanelTitle(0, "sin(t)");
        Plot.SetPanelTitle(1, "cos(0.7·t)");
        Plot.SetPanelTitle(2, "noise");
        Plot.SetPanelYLabel(0, "amplitude");
        Plot.SetPanelYLabel(1, "amplitude");
        Plot.SetPanelYLabel(2, "value");
        Plot.SetXLabel("t, s");

        // Seed each series with one point; AppendToLine grows them live.
        _sinIdx   = Plot.Plot(panel: 0, x: new[] { 0.0 }, y: new[] { 0.0 },
                              r: 0.3f, g: 0.8f, b: 1.0f, a: 1.0f,
                              thickness: 1.5, label: "sin");
        _cosIdx   = Plot.Plot(panel: 1, x: new[] { 0.0 }, y: new[] { 1.0 },
                              r: 1.0f, g: 0.6f, b: 0.2f, a: 1.0f,
                              thickness: 1.5, label: "cos");
        _noiseIdx = Plot.Plot(panel: 2, x: new[] { 0.0 }, y: new[] { 0.0 },
                              r: 0.9f, g: 0.9f, b: 0.3f, a: 1.0f,
                              thickness: 1.5, label: "noise");

        Plot.SetAutoscroll(true, 10.0);

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

        Plot.AppendToLine(panel: 0, series: _sinIdx,   x: xs, y: sinY);
        Plot.AppendToLine(panel: 1, series: _cosIdx,   x: xs, y: cosY);
        Plot.AppendToLine(panel: 2, series: _noiseIdx, x: xs, y: noiseY);
    }
}
