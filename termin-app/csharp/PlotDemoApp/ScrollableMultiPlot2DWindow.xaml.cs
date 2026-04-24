using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Threading;

namespace PlotDemoApp;

// 20 stacked panels on a virtual canvas taller than the window, with
// a WPF ScrollBar driving the native view's scroll_offset. Exercises
// virtualisation + MSAA + append in a realistic "Alliance dashboard"
// shape.
public partial class ScrollableMultiPlot2DWindow : Window
{
    private readonly int[] _seriesIdx;

    private readonly DispatcherTimer _timer;
    private readonly Stopwatch _clock = new();
    private readonly Random _rng = new(24601);

    public ScrollableMultiPlot2DWindow()
    {
        InitializeComponent();

        _seriesIdx = new int[20];

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

    // Imitates a mixed-signal telemetry dashboard — the names span a few
    // domains so the demo doesn't look like 20 copies of the same thing.
    private static readonly string[] ChannelNames =
    {
        "bus voltage, V",
        "bus current, A",
        "motor torque, Nm",
        "motor rpm",
        "wheel speed FL, m/s",
        "wheel speed FR, m/s",
        "wheel speed RL, m/s",
        "wheel speed RR, m/s",
        "imu accel x, g",
        "imu accel y, g",
        "imu accel z, g",
        "imu gyro x, °/s",
        "imu gyro y, °/s",
        "imu gyro z, °/s",
        "battery temp, °C",
        "inverter temp, °C",
        "cpu load, %",
        "link rssi, dBm",
        "gps fix quality",
        "heartbeat",
    };

    private void OnNativeReady(object? sender, EventArgs e)
    {
        // Seed each series with one sample; AppendToLine grows them live.
        var seedX = new[] { 0.0 };
        var seedY = new[] { 0.0 };
        for (int i = 0; i < 20; i++)
        {
            // Cycle through hues so stacked panels stay visually distinct.
            float hue = (i * 0.137f) % 1.0f;
            (float r, float g, float b) = HsvToRgb(hue, 0.65f, 1.0f);
            // Add the line FIRST so the engine can colour the title
            // from the first series on the very first render.
            _seriesIdx[i] = Plot.Plot(panel: i, x: seedX, y: seedY,
                                       r: r, g: g, b: b, a: 1.0f,
                                       thickness: 1.5, label: ChannelNames[i]);
            Plot.SetPanelTitle(i, ChannelNames[i]);
            Plot.SetPanelYLabel(i, "");
        }
        Plot.SetXLabel("t, s");

        Plot.SetAutoscroll(true, 10.0);

        _clock.Start();
        _timer.Start();
    }

    private void OnTick(object? sender, EventArgs e)
    {
        double t = _clock.Elapsed.TotalSeconds;

        const int batch = 3;
        var xs = new double[batch];
        for (int i = 0; i < batch; i++) xs[i] = t + i * 0.01;

        // 20 different signals so each panel shows something unique.
        var ys = new double[batch];
        for (int p = 0; p < 20; p++)
        {
            double freq = 0.3 + p * 0.17;
            double phase = p * 0.5;
            for (int i = 0; i < batch; i++)
            {
                double ti = xs[i];
                double baseSig = Math.Sin(ti * freq + phase);
                double noise = (_rng.NextDouble() - 0.5) * 0.15;
                ys[i] = baseSig + noise + p * 0.001;
            }
            Plot.AppendToLine(panel: p, series: _seriesIdx[p], x: xs, y: ys);
        }
    }

    private static (float, float, float) HsvToRgb(float h, float s, float v)
    {
        float c = v * s;
        float hh = h * 6.0f;
        float x = c * (1.0f - Math.Abs(hh % 2.0f - 1.0f));
        float m = v - c;
        float r, g, b;
        if      (hh < 1) { r = c; g = x; b = 0; }
        else if (hh < 2) { r = x; g = c; b = 0; }
        else if (hh < 3) { r = 0; g = c; b = x; }
        else if (hh < 4) { r = 0; g = x; b = c; }
        else if (hh < 5) { r = x; g = 0; b = c; }
        else             { r = c; g = 0; b = x; }
        return (r + m, g + m, b + m);
    }
}
