using System;
using System.Diagnostics;
using System.IO;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Media.Imaging;
using Avalonia.Platform;

namespace AvaloniaPositioner;

internal sealed partial class PositionerWindow
{
    internal async Task VerifySmokeAsync()
    {
        await WaitForAsync(ViewportHasFrame, "the first frame");
        var initial = CaptureFrame("initial");
        Vector3 beforeTurn = _scene!.CarriageWorldPosition;
        Require(new Vector2(beforeTurn.X, beforeTurn.Y).Length() > 0.1f, "The carriage needs an offset from the turntable axis.");

        SetPose(90, 0);
        DrawFrame();
        Vector3 afterTurn = _scene.CarriageWorldPosition;
        Require(Vector3.Distance(afterTurn, new Vector3(-beforeTurn.Y, beforeTurn.X, beforeTurn.Z)) < 0.02f,
            $"The carriage did not inherit the parent's 90° turn. World position changed from {beforeTurn} to {afterTurn}.");
        var turned = CaptureFrame("azimuth");
        Require(turned.Hash != initial.Hash && Math.Abs(turned.CarriageX - initial.CarriageX) > 3,
            "The parent's turn did not move the Avalonia-rendered carriage.");

        const float lift = 1.0f;
        SetPose(90, lift);
        DrawFrame();
        Vector3 liftedPosition = _scene.CarriageWorldPosition;
        Require(Vector3.Distance(liftedPosition, afterTurn + new Vector3(0, 0, lift)) < 0.02f,
            $"The carriage did not rise in place. World position changed from {afterTurn} to {liftedPosition}.");
        var lifted = CaptureFrame("lift");
        Require(lifted.Hash != turned.Hash && lifted.CarriageY < turned.CarriageY - 3,
            "The carriage lift did not move the Avalonia-rendered carriage upward.");

        SetCamera(DefaultOrbit + 65, DefaultElevation + 8, DefaultDistance + 0.4);
        DrawFrame();
        var orbited = CaptureFrame("camera");
        Require(orbited.Hash != lifted.Hash && _scene.CarriageWorldPosition == liftedPosition,
            "The camera did not change the frame while leaving the model in place.");

        PixelSize beforeResize = _bitmap!.PixelSize;
        Width += 64;
        Height += 48;
        await WaitForAsync(
            () => ViewportHasFrame() && _bitmap!.PixelSize.Width > beforeResize.Width && _bitmap.PixelSize.Height > beforeResize.Height,
            "a resized framebuffer");
        var resized = CaptureFrame("resize");
        Console.WriteLine($"AVALONIA_POSITIONER_RESIZED {beforeResize.Width}x{beforeResize.Height} -> {resized.Size.Width}x{resized.Size.Height}");

        await MeasureScanAsync();
    }

    internal async Task VerifyReopenedAsync()
    {
        await WaitForAsync(ViewportHasFrame, "the reopened window's first frame");
        CaptureFrame("reopened");
    }

    internal void VerifyClosed() =>
        Require(_scene is null && _bitmap is null && _viewport.Source is null && !_timer.IsEnabled,
            "Closing the viewport left its scene, bitmap or scan timer alive.");

    private bool ViewportHasFrame() => _bitmap is not null && _viewport.Bounds.Width > 0 && _viewport.Bounds.Height > 0;

    private async Task WaitForAsync(Func<bool> condition, string description)
    {
        var clock = Stopwatch.StartNew();
        while (true)
        {
            if (_renderError is not null)
                throw new InvalidOperationException($"Positioner rendering failed while waiting for {description}.", _renderError);
            if (condition())
                return;
            if (clock.Elapsed > TimeSpan.FromSeconds(10))
                throw new TimeoutException($"Timed out waiting for {description}.");
            await Task.Delay(15);
        }
    }

    private FrameSample CaptureFrame(string stage)
    {
        var size = _bitmap!.PixelSize;
        var dpi = new Avalonia.Vector(96 * _bitmapScale, 96 * _bitmapScale);
        using var screenshot = new RenderTargetBitmap(size, dpi);
        screenshot.Render(_viewport);
        using var pixels = new WriteableBitmap(size, dpi, PixelFormat.Bgra8888, AlphaFormat.Opaque);
        using var buffer = pixels.Lock();
        screenshot.CopyPixels(buffer, AlphaFormat.Opaque);
        byte[] data = new byte[checked(buffer.RowBytes * size.Height)];
        Marshal.Copy(buffer.Address, data, 0, data.Length);

        int amber = 0;
        int carriage = 0;
        double xSum = 0;
        double ySum = 0;
        ulong hash = 14695981039346656037UL;
        for (int y = 0; y < size.Height; y++)
        {
            int row = y * buffer.RowBytes;
            for (int x = 0; x < size.Width; x++)
            {
                int offset = row + x * 4;
                int b = data[offset];
                int g = data[offset + 1];
                int r = data[offset + 2];
                hash = unchecked((hash ^ (uint)((r << 16) | (g << 8) | b)) * 1099511628211UL);
                if (r > 85 && r - g > 12 && g - b > 10)
                    amber++;
                if (b > 85 && b - r > 25 && g - r > 18)
                {
                    carriage++;
                    xSum += x;
                    ySum += y;
                }
            }
        }

        string? captureDirectory = Environment.GetEnvironmentVariable("TERMIN_POSITIONER_CAPTURE_DIR");
        if (!string.IsNullOrWhiteSpace(captureDirectory))
        {
            Directory.CreateDirectory(captureDirectory);
            screenshot.Save(Path.Combine(captureDirectory, $"positioner-{stage}.png"));
        }
        Require(amber >= 30 && carriage >= 30,
            $"Avalonia stage {stage} lacks visible turntable or carriage pixels. Amber={amber}, blue={carriage}.");
        Console.WriteLine(FormattableString.Invariant(
            $"AVALONIA_POSITIONER_PIXELS {stage} {size.Width}x{size.Height} amber={amber} blue={carriage} carriage=({xSum / carriage:F1},{ySum / carriage:F1})"));
        return new FrameSample(size, hash, xSum / carriage, ySum / carriage);
    }

    private async Task MeasureScanAsync()
    {
        const int count = 32;
        var samples = new double[count];
        var clock = Stopwatch.StartNew();
        for (int i = 0; i < samples.Length; i++)
        {
            var wait = i * ScanInterval - clock.Elapsed;
            if (wait > TimeSpan.Zero)
                await Task.Delay(wait);
            SetPose(70 + 6 * i, 0.8 * (1 - Math.Cos(i * 0.24)));
            long start = Stopwatch.GetTimestamp();
            DrawFrame();
            samples[i] = Stopwatch.GetElapsedTime(start).TotalMilliseconds;
        }
        Array.Sort(samples);
        Console.WriteLine(FormattableString.Invariant(
            $"AVALONIA_POSITIONER_SCAN {count} frames target_ms={ScanInterval.TotalMilliseconds:F1} frame_p50_ms={samples[count / 2]:F2} frame_p95_ms={samples[(int)Math.Ceiling(count * 0.95) - 1]:F2}"));
    }

    private static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    private readonly record struct FrameSample(PixelSize Size, ulong Hash, double CarriageX, double CarriageY);
}
