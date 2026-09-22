using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Termin.Native;
using Termin.Wpf;

namespace PlotDemoApp;

// Exercise the real native -> D3DImage -> WPF pixel path, including bridge recreation.
internal sealed class ColorPresentationSmokeWindow : Window
{
    private static readonly VisualSrgbColor[] Colors =
    {
        new(0.3f, 0.4f, 0.6f), new(0.5f, 0.5f, 0.5f),
        new(1, 1, 1), new(0, 0, 0), new(0.3f, 0.4f, 0.6f), new(0.3f, 0.4f, 0.6f),
    };
    private static readonly string[] Stages = { "blue", "gray", "white", "black", "resized", "recreated" };
    private static readonly VisualSrgbColor LineColor = new(0.8f, 0.2f, 0.4f);
    private static readonly VisualSrgbColor ScatterColor = new(0.2f, 0.7f, 0.3f);
    private readonly GpuHost _gpu;
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly DateTime _deadline = DateTime.UtcNow.AddSeconds(40);
    private Chart2D? _chart2D;
    private RetainedChart3D? _cartesian;
    private RetainedChart3D? _spherical;
    private RetainedScene2DHost? _host2D;
    private RetainedChart3DHost? _cartesianHost;
    private RetainedChart3DHost? _sphericalHost;
    private int _stage;
    private int _initialWidth;
    private bool _closed;

    internal ColorPresentationSmokeWindow()
    {
        Title = "WPF color presentation regression";
        Width = 960;
        Height = 360;
        Background = Brushes.Magenta;
        string font = Plot3DControl.FindSystemFont()
            ?? throw new InvalidOperationException("No system TTF font for color presentation smoke.");
        _gpu = Tgfx2Host.Acquire(font, BackendType.D3D11);
        try
        {
            CreateCharts();
            ApplyColor(Colors[0]);
        }
        catch
        {
            DisposeCharts();
            Tgfx2Host.Release();
            throw;
        }
        _timer.Tick += OnTick;
        Loaded += (_, _) => _timer.Start();
        Closed += (_, _) =>
        {
            _closed = true;
            _timer.Stop();
            DisposeCharts();
            Tgfx2Host.Release();
        };
    }

    private void CreateCharts()
    {
        var panel = new Grid();
        for (int i = 0; i < 3; ++i)
            panel.ColumnDefinitions.Add(new ColumnDefinition());
        _chart2D = new Chart2D(_gpu, 320, 320, new PlotRange2D(0, 1, 0, 1));
        _chart2D.AddLine(new[] { 0.2, 0.8 }, new[] { 0.35, 0.35 },
            style: new PlotLineSeriesStyle2D(
                new PlotSrgbColor2D(LineColor.R, LineColor.G, LineColor.B), thicknessPx: 10,
                lineStyle: PlotLineStyle2D.Dash));
        _chart2D.AddScatter(new[] { 0.5 }, new[] { 0.7 },
            style: new PlotScatterSeriesStyle2D(
                new PlotSrgbColor2D(ScatterColor.R, ScatterColor.G, ScatterColor.B), diameterPx: 24));
        _host2D = new RetainedScene2DHost { ContinuousRendering = false };
        _host2D.FramebufferChanged += (_, e) => _chart2D.Resize(e.Width, e.Height, e.PixelScale);
        _host2D.RenderFailed += OnRenderFailed;
        _host2D.Attach(_gpu, _chart2D.Scene);
        _cartesian = new RetainedChart3D(_gpu);
        _spherical = RetainedChart3D.CreateSpherical(_gpu);
        var cartesianGrid = _cartesian.Parts.Grid;
        var sphericalGrid = _spherical.Parts.Grid;
        _cartesian.Parts.RemoveGrid();
        _spherical.Parts.RemoveGrid();
        cartesianGrid?.Destroy();
        sphericalGrid?.Destroy();
        _cartesianHost = new RetainedChart3DHost();
        _sphericalHost = new RetainedChart3DHost();
        _cartesianHost.RenderFailed += OnRenderFailed;
        _sphericalHost.RenderFailed += OnRenderFailed;
        _cartesianHost.Attach(_cartesian);
        _sphericalHost.Attach(_spherical);
        FrameworkElement[] hosts = { _host2D, _cartesianHost, _sphericalHost };
        for (int i = 0; i < hosts.Length; ++i)
        {
            Grid.SetColumn(hosts[i], i);
            panel.Children.Add(hosts[i]);
        }
        Content = panel;
    }

    private void ApplyColor(VisualSrgbColor color)
    {
        _chart2D!.ApplyTheme(new Chart2DTheme { BackgroundColor = color, PlotBackgroundColor = color });
        _host2D!.RequestRender();
        _cartesian!.BackgroundColor = color;
        _spherical!.BackgroundColor = color;
    }

    private void OnTick(object? sender, EventArgs e)
    {
        try
        {
            if (DateTime.UtcNow > _deadline)
                throw new TimeoutException($"Color presentation timed out at {Stages[_stage]}.");
            FrameworkElement[] hosts = { _host2D!, _cartesianHost!, _sphericalHost! };
            string[] modes = { "2d", "cartesian", "spherical" };
            var captures = new RenderTargetBitmap[hosts.Length];
            for (int i = 0; i < hosts.Length; ++i)
            {
                if (hosts[i].ActualWidth < 2 || hosts[i].ActualHeight < 2)
                    return;
                captures[i] = Capture(hosts[i]);
                if (!Matches(captures[i], Colors[_stage], modes[i]))
                    return;
                if (i == 0 && !MatchesSeries(captures[i]))
                    return;
            }
            if (_stage == 0)
                _initialWidth = captures[0].PixelWidth;
            if (_stage == 4 && captures[0].PixelWidth == _initialWidth)
                throw new InvalidOperationException("Resize did not recreate the presentation target.");
            for (int i = 0; i < captures.Length; ++i)
                Save(captures[i], $"{modes[i]}-{Stages[_stage]}");
            Console.WriteLine($"PLOT_COLOR_PRESENTATION_STAGE_OK {Stages[_stage]}");
            if (++_stage == Colors.Length)
            {
                Console.WriteLine("PLOT_COLOR_PRESENTATION_SMOKE_OK 2D, Cartesian, spherical; sRGB, gray, white, black, resize, recreation");
                Close();
                return;
            }
            if (_stage == 4)
            {
                Width += 90;
                Height += 40;
            }
            if (_stage == 5)
            {
                DisposeCharts();
                CreateCharts();
            }
            ApplyColor(Colors[_stage]);
        }
        catch (Exception error)
        {
            Fail(error);
        }
    }

    private static RenderTargetBitmap Capture(FrameworkElement host)
    {
        var dpi = VisualTreeHelper.GetDpi(host);
        var image = new RenderTargetBitmap(
            (int)Math.Ceiling(host.ActualWidth * dpi.DpiScaleX),
            (int)Math.Ceiling(host.ActualHeight * dpi.DpiScaleY),
            96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
        // Capture each column in local coordinates: Render(host) retains its
        // arranged offset and clips the second/third host outside this bitmap.
        var visual = new DrawingVisual();
        using (var drawing = visual.RenderOpen())
            drawing.DrawRectangle(new VisualBrush(host), null,
                new Rect(0, 0, host.ActualWidth, host.ActualHeight));
        image.Render(visual);
        return image;
    }

    private bool Matches(BitmapSource image, VisualSrgbColor color, string mode)
    {
        byte[] pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
        image.CopyPixels(pixels, image.PixelWidth * 4, 0);
        int red = (int)Math.Round(color.R * 255), green = (int)Math.Round(color.G * 255);
        int blue = (int)Math.Round(color.B * 255), matches = 0;
        // A linear UNorm intermediate introduces quantization before display encoding.
        const int tolerance = 2;
        for (int i = 0; i < pixels.Length; i += 4)
            if (Math.Abs(pixels[i] - blue) <= tolerance && Math.Abs(pixels[i + 1] - green) <= tolerance &&
                Math.Abs(pixels[i + 2] - red) <= tolerance && pixels[i + 3] == 255)
                ++matches;
        if (matches >= image.PixelWidth * image.PixelHeight * 0.8)
            return true;
        int center = ((image.PixelHeight / 2) * image.PixelWidth + image.PixelWidth / 2) * 4;
        Console.WriteLine($"PLOT_COLOR_PRESENTATION_WAIT {mode}/{Stages[_stage]} expectedRGB={red},{green},{blue} " +
            $"actualRGBA={pixels[center + 2]},{pixels[center + 1]},{pixels[center]},{pixels[center + 3]} matchingPixels={matches}");
        Save(image, $"{mode}-{Stages[_stage]}-observed");
        return false;
    }

    private bool MatchesSeries(BitmapSource image)
    {
        byte[] pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
        image.CopyPixels(pixels, image.PixelWidth * 4, 0);
        int linePixels = CountOpaqueColor(pixels, LineColor);
        int scatterPixels = CountOpaqueColor(pixels, ScatterColor);
        if (linePixels >= 200 && scatterPixels >= 100)
        {
            Console.WriteLine($"PLOT_COLOR_SERIES_OK {Stages[_stage]} linePixels={linePixels} scatterPixels={scatterPixels}");
            return true;
        }
        Console.WriteLine($"PLOT_COLOR_SERIES_WAIT {Stages[_stage]} lineRGB=204,51,102 pixels={linePixels}; " +
            $"scatterRGB=51,178,76 pixels={scatterPixels}");
        Save(image, $"2d-{Stages[_stage]}-series-observed");
        return false;
    }

    private static int CountOpaqueColor(byte[] pixels, VisualSrgbColor color)
    {
        int red = (int)Math.Round(color.R * 255), green = (int)Math.Round(color.G * 255);
        int blue = (int)Math.Round(color.B * 255), count = 0;
        // Count the fully covered interiors, excluding antialiasing edges.
        for (int i = 0; i < pixels.Length; i += 4)
            if (Math.Abs(pixels[i] - blue) <= 3 && Math.Abs(pixels[i + 1] - green) <= 3 &&
                Math.Abs(pixels[i + 2] - red) <= 3 && pixels[i + 3] == 255)
                ++count;
        return count;
    }

    private static void Save(BitmapSource image, string name)
    {
        string? directory = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        if (string.IsNullOrWhiteSpace(directory))
            return;
        Directory.CreateDirectory(directory);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        using var file = File.Create(Path.Combine(directory, $"plot-color-{name}.png"));
        encoder.Save(file);
    }

    private void OnRenderFailed(object? sender, RetainedSceneRenderFailedEventArgs e) => Fail(e.Error);

    private void Fail(Exception error)
    {
        if (_closed)
            return;
        Console.Error.WriteLine($"PLOT_COLOR_PRESENTATION_SMOKE_FAILED {error}");
        Environment.ExitCode = 1;
        _timer.Stop();
        Close();
    }

    private void DisposeCharts()
    {
        Content = null;
        _host2D?.Dispose();
        _cartesianHost?.Dispose();
        _sphericalHost?.Dispose();
        _chart2D?.Dispose();
        _cartesian?.Dispose();
        _spherical?.Dispose();
    }
}
