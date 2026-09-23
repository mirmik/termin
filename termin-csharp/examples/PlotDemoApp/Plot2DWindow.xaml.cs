using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace PlotDemoApp;

public partial class Plot2DWindow : Window
{
    private readonly List<Plot2DControl> _smokeHosts = new();
    private DispatcherTimer? _smokeTimer;
    private readonly int _smokeBootstrapSize;
    private readonly int _smokeCycle;
    private bool _smokeResized;
    private readonly List<(int Width, int Height)> _initialSizes = new();

    internal event EventHandler? MultiHostSmokeCompleted;

    public Plot2DWindow(bool multipleHosts = false, int smokeBootstrapSize = 1, int smokeCycle = 1)
    {
        InitializeComponent();
        _smokeBootstrapSize = smokeBootstrapSize;
        _smokeCycle = smokeCycle;
        if (multipleHosts)
        {
            _smokeHosts.Add(Plot);
            var grid = (Grid)Content;
            grid.RowDefinitions.Add(new RowDefinition());
            grid.RowDefinitions.Add(new RowDefinition());
            grid.RowDefinitions.Add(new RowDefinition());
            for (int row = 1; row < 3; ++row)
            {
                int panel = row;
                var extra = new Plot2DControl();
                _smokeHosts.Add(extra);
                Grid.SetRow(extra, panel);
                grid.Children.Add(extra);
                extra.NativeInitialized += (_, _) =>
                {
                    double[] x = new double[400];
                    double[] y = new double[400];
                    for (int i = 0; i < x.Length; ++i)
                    {
                        x[i] = i * 0.001;
                        y[i] = Math.Sin(i * 0.1 + panel);
                    }
                    extra.View.clear();
                    extra.View.plot(x, y, (uint)x.Length, 0.2f, 0.7f, 1f, 1f, 1.5, "I/Q");
                    extra.View.set_title("S_C: I / Q / magnitude");
                    extra.View.set_x_label("t, s");
                    extra.View.set_y_label("model units");
                    extra.View.fit();
                };
            }
            foreach (Plot2DControl host in _smokeHosts)
                host.SmokeBootstrapSize = smokeBootstrapSize;
            _smokeTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(250) };
            _smokeTimer.Tick += CheckMultiHostSmoke;
            Loaded += (_, _) => _smokeTimer.Start();
            Closed += (_, _) =>
            {
                _smokeTimer.Stop();
                foreach (Plot2DControl host in _smokeHosts)
                    host.Dispose();
            };
        }
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

    private void CheckMultiHostSmoke(object? sender, EventArgs e)
    {
        var captures = new List<RenderTargetBitmap>();
        for (int hostIndex = 0; hostIndex < _smokeHosts.Count; ++hostIndex)
        {
            Plot2DControl host = _smokeHosts[hostIndex];
            if (host.ActualWidth < 100 || host.ActualHeight < 100 ||
                !host.HasPresentedCurrentSize)
                return;
            if (_smokeResized &&
                (host.PresentedWidth == _initialSizes[hostIndex].Width ||
                 host.PresentedHeight == _initialSizes[hostIndex].Height))
                return;
            var image = CaptureHost(host);
            if (CountBlueLinePixels(image) < 20)
                return;
            captures.Add(image);
        }
        string? captureDir = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        if (!string.IsNullOrWhiteSpace(captureDir))
        {
            Directory.CreateDirectory(captureDir);
            for (int i = 0; i < captures.Count; ++i)
            {
                var encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(captures[i]));
                using var file = File.Create(Path.Combine(captureDir,
                    $"plot-2d-hosts-{_smokeBootstrapSize}x{_smokeBootstrapSize}-cycle{_smokeCycle}-{(_smokeResized ? "resized" : "initial")}-{i}.png"));
                encoder.Save(file);
            }
        }
        Console.WriteLine($"PLOT_2D_HOSTS_FRAME_OK bootstrap={_smokeBootstrapSize} cycle={_smokeCycle} resized={_smokeResized}");
        if (!_smokeResized)
        {
            foreach (Plot2DControl host in _smokeHosts)
                _initialSizes.Add((host.PresentedWidth, host.PresentedHeight));
            _smokeResized = true;
            Width -= 120;
            Height += 90;
            return;
        }
        _smokeTimer!.Stop();
        MultiHostSmokeCompleted?.Invoke(this, EventArgs.Empty);
    }

    internal void DumpMultiHostSmokeDiagnostics()
    {
        string? captureDir = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        for (int i = 0; i < _smokeHosts.Count; ++i)
        {
            var host = _smokeHosts[i];
            Console.Error.WriteLine($"PLOT_2D_HOST_DIAGNOSTIC cycle={_smokeCycle} resized={_smokeResized} host={i} " +
                $"actual={host.ActualWidth}x{host.ActualHeight} loaded={host.IsLoaded} visible={host.IsVisible} " + host.SmokeRenderDiagnostics);
            if (host.ActualWidth <= 0 || host.ActualHeight <= 0)
                continue;
            var image = CaptureHost(host);
            Console.Error.WriteLine($"PLOT_2D_HOST_DIAGNOSTIC host={i} blueLinePixels={CountBlueLinePixels(image)}");
            if (string.IsNullOrWhiteSpace(captureDir))
                continue;
            Directory.CreateDirectory(captureDir);
            var encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(image));
            using var file = File.Create(Path.Combine(captureDir,
                $"plot-2d-hosts-{_smokeBootstrapSize}x{_smokeBootstrapSize}-cycle{_smokeCycle}-failed-{i}.png"));
            encoder.Save(file);
        }
    }

    private static RenderTargetBitmap CaptureHost(Plot2DControl host)
    {
        var dpi = VisualTreeHelper.GetDpi(host);
        var image = new RenderTargetBitmap(
            (int)Math.Ceiling(host.ActualWidth * dpi.DpiScaleX),
            (int)Math.Ceiling(host.ActualHeight * dpi.DpiScaleY),
            96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
        var visual = new DrawingVisual();
        using (var drawing = visual.RenderOpen())
            drawing.DrawRectangle(new VisualBrush(host), null,
                new Rect(0, 0, host.ActualWidth, host.ActualHeight));
        image.Render(visual);
        return image;
    }

    private static int CountBlueLinePixels(RenderTargetBitmap image)
    {
        byte[] pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
        image.CopyPixels(pixels, image.PixelWidth * 4, 0);
        int blueLinePixels = 0;
        // Inspect the plot interior, excluding the legend and axes so a
        // label/legend alone cannot make a missing series pass.
        for (int y = image.PixelHeight / 5; y < image.PixelHeight * 4 / 5; ++y)
            for (int x = image.PixelWidth / 5; x < image.PixelWidth * 4 / 5; ++x)
            {
                int i = (y * image.PixelWidth + x) * 4;
                if (pixels[i] > pixels[i + 1] + 20 &&
                    pixels[i + 1] > pixels[i + 2] + 30 && pixels[i + 3] == 255)
                    ++blueLinePixels;
            }
        return blueLinePixels;
    }
}
