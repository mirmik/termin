using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Termin.Native;

namespace PlotDemoApp;

public sealed partial class Heatmap2DWindow
{
    private DispatcherTimer? _smokeTimer;
    private DateTime _smokeDeadline;
    private int _smokeStage;
    private int _smokeFramesBeforeMutation;
    private int _smokeInitialWidth;
    private int _smokeGradientWidth;

    internal void StartHeatmapSmoke()
    {
        _smokeStage = -1;
        _smokeDeadline = DateTime.UtcNow.AddSeconds(30);
        _smokeTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(400) };
        _smokeTimer.Tick += OnSmokeTick;
        _smokeTimer.Start();
    }

    private void SetSmokeStyle(bool reversed, bool autoRange)
    {
        _heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Grayscale,
            colorMapReversed: reversed, autoRange: autoRange, scalarMin: 0, scalarMax: 1);
        UpdateScale();
        _smokeFramesBeforeMutation = _renderedFrames;
        _host.RequestRender();
    }

    private void OnSmokeTick(object? sender, EventArgs e)
    {
        try
        {
            if (DateTime.UtcNow > _smokeDeadline)
                throw new TimeoutException($"Heatmap smoke timed out at stage {_smokeStage}.");
            if (_renderedFrames <= _smokeFramesBeforeMutation || _host.ActualWidth < 2)
                return;
            if (_smokeStage == -1)
            {
                if (!MatchesLegendInk(CaptureHeatmap(), "initial"))
                    return;
                var dpi = VisualTreeHelper.GetDpi(this);
                var preview = new RenderTargetBitmap(
                    (int)Math.Ceiling(ActualWidth * dpi.DpiScaleX),
                    (int)Math.Ceiling(ActualHeight * dpi.DpiScaleY),
                    96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
                preview.Render(this);
                SaveHeatmapCapture(preview, "example");
                _chart.Grid.Item!.Visible = false;
                _heatmap.SetData(new[] { 0.0, 0.25, 0.5, double.NaN }, 2, 2, Bounds);
                SetSmokeStyle(reversed: false, autoRange: false);
                _smokeStage = 0;
                return;
            }
            var image = CaptureHeatmap();
            if (_smokeStage == 3 && !MatchesLegendInk(image, "resized"))
                return;
            int[] gray = _smokeStage switch
            {
                0 => new[] { 0, 64, 128, -1 },
                1 => new[] { 255, 191, 128, -1 },
                2 or 3 => new[] { 255, 191, 128, 0 },
                4 or 5 => new[] { 0, 85, 170, 255 },
                _ => new[] { 51, 102, 153, 204 },
            };
            if (_smokeStage == 9 || _smokeStage == 10)
            {
                if (!MatchesDarkGradient(image))
                    return;
                if (_smokeStage == 10 && image.PixelWidth == _smokeGradientWidth)
                    throw new InvalidOperationException("Dark-gradient resize did not resize the framebuffer.");
            }
            else if (_smokeStage <= 8)
            {
                if (!MatchesCells(image, gray))
                    return;
                if (_smokeStage >= 7 && !MatchesInterpolationPixel(image, _smokeStage == 7 ? 94 : 51))
                    return;
            }
            SaveHeatmapCapture(image, $"stage-{_smokeStage}");
            Console.WriteLine($"HEATMAP_SMOKE_STAGE_OK {_smokeStage} size={image.PixelWidth}x{image.PixelHeight}");

            if (_smokeStage == 0)
            {
                _smokeInitialWidth = image.PixelWidth;
                SetSmokeStyle(reversed: true, autoRange: false);
            }
            else if (_smokeStage == 1)
            {
                _heatmap.SetData(new[] { 0.0, 0.25, 0.5, 1.0 }, 2, 2, Bounds);
                UpdateScale();
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else if (_smokeStage == 2)
            {
                _smokeFramesBeforeMutation = _renderedFrames;
                Width += 100;
                Height += 50;
                _chart.Fit(0);
                _host.RequestRender();
            }
            else if (_smokeStage == 3)
            {
                if (image.PixelWidth == _smokeInitialWidth)
                    throw new InvalidOperationException("Heatmap resize did not resize the framebuffer.");
                _heatmap.SetData(new[] { 10.0, 20.0, 30.0, 40.0 }, 2, 2, Bounds);
                SetSmokeStyle(reversed: false, autoRange: true);
                var range = _heatmap.Item.Snapshot;
                if (range.ScalarMin != 10 || range.ScalarMax != 40)
                    throw new InvalidOperationException("Heatmap automatic color range did not update.");
            }
            else if (_smokeStage == 4)
            {
                var before = _chart.Projection.DataToVisual(new PlotPoint2D(-2, -1.5));
                _chart.PanBy(0.1, 0.1);
                _chart.ZoomAt(0.9, 0, 0);
                var after = _chart.Projection.DataToVisual(new PlotPoint2D(-2, -1.5));
                if (Math.Abs(before.X - after.X) < 1 && Math.Abs(before.Y - after.Y) < 1)
                    throw new InvalidOperationException("Pan/zoom did not change the heatmap projection.");
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else if (_smokeStage == 5)
            {
                // Style-only range change: the scalar matrix stays untouched.
                _heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Grayscale,
                    autoRange: false, scalarMin: 0, scalarMax: 50);
                UpdateScale();
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else if (_smokeStage == 6 || _smokeStage == 7)
            {
                // Change only visual sampling; preserve the matrix and scalar range.
                _heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Grayscale,
                    autoRange: false, scalarMin: 0, scalarMax: 50,
                    interpolation: _smokeStage == 6
                        ? PlotHeatmapInterpolation2D.Bilinear : PlotHeatmapInterpolation2D.Nearest);
                if (!_heatmap.TrySample(-1, -0.6, out var cell) || cell.Value != 10)
                    throw new InvalidOperationException("Visual interpolation changed the original cell query.");
                UpdateScale();
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else if (_smokeStage == 8)
            {
                // A dark sRGB ramp has many visible output levels but occupies
                // only two linear UNorm8 levels. Quantization before the final
                // sRGB encode therefore causes severe banding.
                foreach (var series in _chart.SemanticSeries)
                    if (series.Kind != ChartSeriesKind2D.Heatmap)
                        series.Visible = false;
                _heatmap.SetData(new[] { 0.0, 16.0 / 255, 0.0, 16.0 / 255 }, 2, 2, Bounds);
                _heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Grayscale,
                    autoRange: false, scalarMin: 0, scalarMax: 1,
                    interpolation: PlotHeatmapInterpolation2D.Bilinear);
                _chart.Fit(0);
                if (_host.MsaaSamples != 4)
                    throw new InvalidOperationException("Dark-gradient regression requires the default 4x MSAA path.");
                UpdateScale();
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else if (_smokeStage == 9)
            {
                SaveHeatmapCapture(image, "dark-gradient");
                _smokeGradientWidth = image.PixelWidth;
                _smokeFramesBeforeMutation = _renderedFrames;
                Width -= 113;
                Height += 47;
                _chart.Fit(0);
                _host.RequestRender();
            }
            else if (_smokeStage == 10)
            {
                SaveHeatmapCapture(image, "dark-gradient-resized");
                // Reproduce the purple Viridis region from the reported
                // banding example, retaining the full-resolution scalar field.
                _heatmap.SetData(MakeValues(), Rows, Columns, Bounds);
                _heatmap.Style = new PlotHeatmapStyle2D(PlotColorMap2D.Viridis,
                    interpolation: PlotHeatmapInterpolation2D.Bilinear);
                _chart.SetRange(new PlotRange2D(-1.79, -1.48, -1.11, -0.875));
                UpdateScale();
                _smokeFramesBeforeMutation = _renderedFrames;
                _host.RequestRender();
            }
            else
            {
                SaveHeatmapCapture(image, "viridis-zoom");
                Console.WriteLine("HEATMAP_SMOKE_OK orientation, grayscale pixels, NaN transparency, reversal, data replacement, resize, fit, automatic range, pan/zoom, style-only fixed range, bilinear pixels, nearest restoration, original cell sampling, dark-gradient precision with 4x MSAA and resize");
                _smokeTimer!.Stop();
                Close();
                return;
            }
            ++_smokeStage;
        }
        catch (Exception error)
        {
            FailSmoke(error);
        }
    }

    private RenderTargetBitmap CaptureHeatmap()
    {
        DpiScale dpi = VisualTreeHelper.GetDpi(_host);
        var image = new RenderTargetBitmap(
            (int)Math.Ceiling(_host.ActualWidth * dpi.DpiScaleX),
            (int)Math.Ceiling(_host.ActualHeight * dpi.DpiScaleY),
            96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
        var visual = new DrawingVisual();
        using (var drawing = visual.RenderOpen())
            drawing.DrawRectangle(new VisualBrush(_host), null, new Rect(0, 0, _host.ActualWidth, _host.ActualHeight));
        image.Render(visual);
        return image;
    }

    private bool MatchesCells(BitmapSource image, int[] expected)
    {
        byte[] pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
        image.CopyPixels(pixels, image.PixelWidth * 4, 0);
        for (int row = 0; row < 2; ++row)
        for (int column = 0; column < 2; ++column)
        {
            var pixel = _chart.Projection.DataToVisual(new PlotPoint2D(-2 + column * 4, -1.5 + row * 3));
            int offset = ((int)pixel.Y * image.PixelWidth + (int)pixel.X) * 4;
            int value = expected[row * 2 + column];
            var background = _chart.Theme.PlotBackgroundColor;
            int red = value < 0 ? (int)Math.Round(background.R * 255) : value;
            int green = value < 0 ? (int)Math.Round(background.G * 255) : value;
            int blue = value < 0 ? (int)Math.Round(background.B * 255) : value;
            if (Math.Abs(pixels[offset + 2] - red) > 4 ||
                Math.Abs(pixels[offset + 1] - green) > 4 || Math.Abs(pixels[offset] - blue) > 4)
            {
                Console.WriteLine($"HEATMAP_SMOKE_WAIT stage={_smokeStage} row={row} column={column} " +
                    $"expected={red},{green},{blue} actual={pixels[offset + 2]},{pixels[offset + 1]},{pixels[offset]}");
                return false;
            }
        }
        return true;
    }

    private bool MatchesInterpolationPixel(BitmapSource image, int expected)
    {
        // Between four cell centers: fx=0.25, fy=0.30 gives scalar 18.5.
        // With [0,50] grayscale this is 94/255; nearest gives 10 -> 51/255.
        var point = _chart.Projection.DataToVisual(new PlotPoint2D(-1, -0.6));
        var pixels = new byte[4];
        image.CopyPixels(new Int32Rect((int)point.X, (int)point.Y, 1, 1), pixels, 4, 0);
        if (Math.Abs(pixels[0] - expected) <= 4 &&
            Math.Abs(pixels[1] - expected) <= 4 && Math.Abs(pixels[2] - expected) <= 4)
            return true;
        Console.WriteLine($"HEATMAP_SMOKE_WAIT stage={_smokeStage} interpolation expected={expected} " +
            $"actual={pixels[2]},{pixels[1]},{pixels[0]}");
        return false;
    }

    private bool MatchesDarkGradient(BitmapSource image)
    {
        // Check physical pixel centers against their actual data coordinates,
        // so DPI and a resized plot rectangle do not change the expected ramp.
        var left = _chart.Projection.DataToVisual(new PlotPoint2D(-2, -1.5));
        var right = _chart.Projection.DataToVisual(new PlotPoint2D(2, -1.5));
        int first = (int)Math.Ceiling(left.X) + 2;
        int last = (int)Math.Floor(right.X) - 2;
        int y = (int)left.Y;
        if (last - first < 64)
            throw new InvalidOperationException("Dark-gradient strip is too small to verify precision.");
        var pixels = new byte[(last - first + 1) * 4];
        image.CopyPixels(new Int32Rect(first, y, last - first + 1, 1), pixels, pixels.Length, 0);
        var levels = new HashSet<byte>();
        for (int x = first; x <= last; ++x)
        {
            var data = _chart.Projection.VisualToData(new PlotVisualPoint2D(x + 0.5f, y + 0.5f));
            double weight = Math.Clamp((data.X + 2) / 4, 0, 1);
            int expected = (int)Math.Round(weight * 16);
            int offset = (x - first) * 4;
            for (int channel = 0; channel < 3; ++channel)
                if (Math.Abs(pixels[offset + channel] - expected) > 1)
                {
                    Console.WriteLine($"HEATMAP_SMOKE_WAIT stage={_smokeStage} dark-gradient " +
                        $"x={x} expected={expected} actual={pixels[offset + 2]},{pixels[offset + 1]},{pixels[offset]}");
                    return false;
                }
            levels.Add(pixels[offset + 2]);
        }
        if (levels.Count < 15)
        {
            Console.WriteLine($"HEATMAP_SMOKE_WAIT stage={_smokeStage} dark-gradient " +
                $"expected>=15 distinct output levels actual={levels.Count}");
            return false;
        }
        Console.WriteLine($"HEATMAP_DARK_GRADIENT_OK stage={_smokeStage} " +
            $"levels={levels.Count} samples={last - first + 1} maxError<=1 msaa={_host.MsaaSamples}");
        return true;
    }

    private static void SaveHeatmapCapture(BitmapSource image, string name)
    {
        string? directory = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        if (string.IsNullOrWhiteSpace(directory))
            return;
        Directory.CreateDirectory(directory);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        using var stream = File.Create(Path.Combine(directory, $"heatmap-{name}.png"));
        encoder.Save(stream);
    }

    private void FailSmoke(Exception error)
    {
        if (_closed)
            return;
        Console.Error.WriteLine($"HEATMAP_SMOKE_FAILED {error}");
        Environment.ExitCode = 1;
        _smokeTimer?.Stop();
        Close();
    }
}
