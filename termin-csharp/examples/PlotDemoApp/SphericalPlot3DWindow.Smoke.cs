using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Termin.Native;

namespace PlotDemoApp;

public partial class SphericalPlot3DWindow
{
    private DispatcherTimer? _smokeTimer;
    private DateTime _smokeDeadline;
    private int _smokeStage;
    private byte[]? _smokeBaseline;
    private OrbitCameraState3D _smokeCamera;
    private PlotItemSnapshot3D _smokeSurface;

    internal void StartDisplaySmoke()
    {
        _showPhysicalValues = false;
        SelectDataset(2);
        // Keep the colorbar visible for the redraw assertion, but hide radial
        // text over the sphere so the interior comparison can be exact.
        _chart.Parts.Grid!.Style = new GridItemStyle3D(labelsVisible: false);
        _smokeDeadline = DateTime.UtcNow.AddSeconds(30);
        _smokeTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _smokeTimer.Tick += OnDisplaySmokeTick;
        _smokeTimer.Start();
    }

    private void OnDisplaySmokeTick(object? sender, EventArgs e)
    {
        try
        {
            if (DateTime.UtcNow > _smokeDeadline)
                throw new TimeoutException($"PlotDemoApp display smoke timed out at stage {_smokeStage}.");
            if (ChartHost.ActualWidth < 2 || ChartHost.ActualHeight < 2)
                return;

            // Capture the WPF presentation, never force RenderFrame: this smoke
            // also verifies that display setters wake an idle on-demand host.
            var image = CaptureChart();
            byte[] pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
            image.CopyPixels(pixels, image.PixelWidth * 4, 0);
            if (_smokeStage == 0)
            {
                if (CountSurfacePixels(pixels, image.PixelWidth, image.PixelHeight) < 1500)
                    return;
                SaveCapture(image, "constant-radius");
                _smokeBaseline = pixels;
                _smokeCamera = _chart.Camera.State;
                _smokeSurface = _surface.Snapshot;
                // Deliberately the only mutation, with no RequestRender call.
                _chart.SetAxisDisplayOffset(PlotAxis3D.Radius, DisplayFloor);
            }
            else if (_smokeStage == 1)
            {
                int differences = CountDifferences(_smokeBaseline!, pixels);
                if (differences < 40)
                    return;
                RequireStableSurface();
                RequireStableSurfaceColors(_smokeBaseline!, pixels, image.PixelWidth, image.PixelHeight);
                SaveCapture(image, "constant-offset");
                Console.WriteLine($"PLOT_DISPLAY_OFFSET_OK changedPixels={differences}");
                _showPhysicalValues = true;
                _chart.Parts.Grid!.Style = new GridItemStyle3D();
                SelectDataset(2);
            }
            else if (_smokeStage == 2)
            {
                RequireVisibleSurface(pixels, image);
                SaveCapture(image, "constant-dbsm");
                SelectDataset(3);
            }
            else if (_smokeStage == 3)
            {
                RequireVisibleSurface(pixels, image);
                SaveCapture(image, "zero-boundary-dbsm");
                _smokeCamera = _chart.Camera.State;
                _smokeBaseline = pixels;
                OnReplaceSurface(this, new RoutedEventArgs());
            }
            else if (_smokeStage == 4)
            {
                RequireVisibleSurface(pixels, image);
                if (!_smokeCamera.Equals(_chart.Camera.State) ||
                    _chart.GetAxisDisplayOffset(PlotAxis3D.Radius) != DisplayFloor)
                    throw new InvalidOperationException("Replacement lost camera or axis display settings.");
                if (CountDifferences(_smokeBaseline!, pixels) != 0)
                    throw new InvalidOperationException("Equivalent surface/grid/colorbar replacement changed the image.");
                SaveCapture(image, "replacement-dbsm");
                OnAdvanceWave(this, new RoutedEventArgs());
            }
            else if (_smokeStage == 5)
            {
                RequireVisibleSurface(pixels, image);
                if (!_smokeCamera.Equals(_chart.Camera.State) ||
                    _chart.GetAxisDisplayOffset(PlotAxis3D.Radius) != DisplayFloor)
                    throw new InvalidOperationException("SetRadii lost camera or axis display settings.");
                SaveCapture(image, "updated-dbsm");
                Console.WriteLine("PLOT_DEMO_AXIS_DISPLAY_SMOKE_OK constant, offset, zero boundary, replacement, SetRadii");
                _smokeBaseline = pixels;
                _smokeSurface = _surface.Snapshot;
                OnToggleBackground(this, new RoutedEventArgs());
            }
            else if (_smokeStage == 6)
            {
                if (CountBackgroundPixels(pixels, BlueBackground) < image.PixelWidth * image.PixelHeight / 5)
                {
                    int sample = (20 * image.PixelWidth + 20) * 4;
                    Console.WriteLine($"PLOT_BACKGROUND_WAIT observedRGBA={pixels[sample + 2]},{pixels[sample + 1]},{pixels[sample]},{pixels[sample + 3]}");
                    SaveCapture(image, "background-observed");
                    return;
                }
                RequireStableSurface();
                RequireVisibleSurface(pixels, image);
                SaveCapture(image, "blue-background");
                OnToggleBackground(this, new RoutedEventArgs());
            }
            else
            {
                if (CountDifferences(_smokeBaseline!, pixels) != 0)
                    return;
                RequireStableSurface();
                SaveCapture(image, "restored-background");
                Console.WriteLine("PLOT_DEMO_BACKGROUND_SMOKE_OK live change, sRGB output pixels, stable surface and camera, restored frame");
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

    private RenderTargetBitmap CaptureChart()
    {
        DpiScale dpi = VisualTreeHelper.GetDpi(ChartHost);
        var image = new RenderTargetBitmap(
            (int)Math.Ceiling(ChartHost.ActualWidth * dpi.DpiScaleX),
            (int)Math.Ceiling(ChartHost.ActualHeight * dpi.DpiScaleY),
            96 * dpi.DpiScaleX, 96 * dpi.DpiScaleY, PixelFormats.Pbgra32);
        image.Render(ChartHost);
        return image;
    }

    private static void SaveCapture(BitmapSource image, string name)
    {
        string? directory = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        if (string.IsNullOrWhiteSpace(directory))
            return;
        Directory.CreateDirectory(directory);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        using var stream = File.Create(Path.Combine(directory, $"plot-demo-{name}.png"));
        encoder.Save(stream);
    }

    private void RequireStableSurface()
    {
        var current = _surface.Snapshot;
        if (!_smokeCamera.Equals(_chart.Camera.State) ||
            current.GeometryRevision != _smokeSurface.GeometryRevision ||
            current.StyleRevision != _smokeSurface.StyleRevision)
            throw new InvalidOperationException("Display offset changed surface geometry, style or camera.");
    }

    private static int CountDifferences(byte[] before, byte[] after)
    {
        if (before.Length != after.Length)
            throw new InvalidOperationException("Framebuffer changed size during the smoke.");
        int count = 0;
        for (int i = 0; i < before.Length; i += 4)
            if (before[i] != after[i] || before[i + 1] != after[i + 1] || before[i + 2] != after[i + 2])
                ++count;
        return count;
    }

    private static int CountBackgroundPixels(byte[] pixels, VisualSrgbColor color)
    {
        int red = (int)Math.Round(color.R * 255), green = (int)Math.Round(color.G * 255),
            blue = (int)Math.Round(color.B * 255);
        int count = 0;
        for (int i = 0; i < pixels.Length; i += 4)
            if (Math.Abs(pixels[i] - blue) <= 2 && Math.Abs(pixels[i + 1] - green) <= 2 &&
                Math.Abs(pixels[i + 2] - red) <= 2 && pixels[i + 3] == 255)
                ++count;
        return count;
    }

    private static bool IsSurfacePixel(byte[] pixels, int i) =>
        pixels[i + 2] > 75 && pixels[i + 2] - pixels[i + 1] > 35 && pixels[i] > 35;

    private static int CountSurfacePixels(byte[] pixels, int width, int height)
    {
        int count = 0;
        // Exclude the colorbar and outer axis labels; a blank native area or
        // just colored reference circles must not satisfy this check.
        for (int y = height / 4; y < height * 3 / 4; ++y)
            for (int x = width / 4; x < width * 2 / 3; ++x)
                if (IsSurfacePixel(pixels, (y * width + x) * 4))
                    ++count;
        return count;
    }

    private static void RequireVisibleSurface(byte[] pixels, BitmapSource image)
    {
        int count = CountSurfacePixels(pixels, image.PixelWidth, image.PixelHeight);
        if (count < 1500)
            throw new InvalidOperationException($"WPF frame has no visible surface: only {count} colored interior pixels.");
        Console.WriteLine($"PLOT_DEMO_VISIBLE_SURFACE pixels={count}");
    }

    private static void RequireStableSurfaceColors(byte[] before, byte[] after, int width, int height)
    {
        int sampled = 0, changed = 0;
        for (int y = height / 4; y < height * 3 / 4; ++y)
            for (int x = width / 4; x < width * 2 / 3; ++x)
            {
                int i = (y * width + x) * 4;
                if (!IsSurfacePixel(before, i))
                    continue;
                ++sampled;
                if (before[i] != after[i] || before[i + 1] != after[i + 1] || before[i + 2] != after[i + 2])
                    ++changed;
            }
        if (sampled < 1500 || changed != 0)
            throw new InvalidOperationException($"Offset changed surface colors: {changed}/{sampled} pixels.");
    }

    private void FailSmoke(Exception error)
    {
        Console.Error.WriteLine($"PLOT_DEMO_AXIS_DISPLAY_SMOKE_FAILED {error}");
        Environment.ExitCode = 1;
        _smokeTimer?.Stop();
        Close();
    }
}
