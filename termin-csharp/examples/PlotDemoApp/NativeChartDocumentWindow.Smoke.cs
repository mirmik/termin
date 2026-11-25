using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Termin.Native;

namespace PlotDemoApp;

public sealed partial class NativeChartDocumentWindow
{
    internal async void StartSmoke()
    {
        var clock = Stopwatch.StartNew();
        try
        {
            BitmapSource initial = await WaitForSignalAsync(clock, afterFrame: 0, showCosine: false);
            Require(ReferenceEquals(_host.Document, _document) && _document.RootCount == 1 &&
                _document.LiveWidgetCount == 5, "Expected the chart and toolbar in one document tree.");
            SaveSmokeCapture(initial, "initial");

            var renderer = _host.Renderer ?? throw new InvalidOperationException("Document renderer is missing.");
            int afterFrame = _presentedFrames;
            ClickNativeButton(renderer);
            Require(_activations == 1 && _cosine.Visible && !_sine.Visible,
                "The native button did not switch the retained series.");
            SaveSmokeCapture(await WaitForSignalAsync(clock, afterFrame, showCosine: true), "clicked");

            renderer.SetFocus(true);
            _document.Focus(_button.Handle);
            Require(renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Down, Key = 32 }) &&
                renderer.DispatchKey(new NativeUiKeyEvent { Type = NativeUiKeyEventType.Up, Key = 32 }) &&
                _activations == 2 && _sine.Visible && !_cosine.Visible,
                "Space did not activate the focused native button.");
            ExerciseChartInput(renderer);

            afterFrame = _presentedFrames;
            Width += 80;
            Height += 50;
            BitmapSource resized = await WaitForSignalAsync(clock, afterFrame, showCosine: false,
                widerThan: initial.PixelWidth);
            Require(resized.PixelHeight > initial.PixelHeight, "The document did not present at the new height.");
            SaveSmokeCapture(resized, "resized");

            int frames = _presentedFrames;
            Close();
            Require(_closed && _host.Document is null && !Tgfx2Host.IsCreated,
                "Closing the chart window did not release the host and its GPU lease.");
            Console.WriteLine($"NATIVE_CHART_DOCUMENT_SMOKE_OK frames={frames} " +
                $"size={initial.PixelWidth}x{initial.PixelHeight}->{resized.PixelWidth}x{resized.PixelHeight} " +
                "one document, native button pointer/keyboard activation, chart pan/zoom/cancel and teardown");
            Application.Current.Shutdown(0);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"NATIVE_CHART_DOCUMENT_SMOKE_FAILED {error}");
            Application.Current.Shutdown(1);
        }
    }

    private void ClickNativeButton(NativeDocumentRenderer renderer)
    {
        NativeUiRect bounds = _button.Bounds;
        float x = bounds.X + bounds.Width / 2;
        float y = bounds.Y + bounds.Height / 2;
        Require(renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Down, x, y, button: 0)) &&
            renderer.HasPointerCapture, "The native button did not capture the pointer.");
        Require(renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Up, x, y, button: 0)) &&
            !renderer.HasPointerCapture, "The native button did not release the pointer.");
    }

    private void ExerciseChartInput(NativeDocumentRenderer renderer)
    {
        NativeUiRect view = _chartView.Bounds;
        PlotRect2D plot = _chart.Layout.PlotArea;
        float x = view.X + plot.X + plot.Width / 2;
        float y = view.Y + plot.Y + plot.Height / 2;
        PlotRange2D beforePan = _chart.Range;
        Require(renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Down, x, y, button: 2)) &&
            renderer.HasPointerCapture, "Middle-button drag did not capture the chart.");
        Require(renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Move, x + 30, y)) &&
            Math.Abs(_chart.Range.XMin - beforePan.XMin) > 1e-4, "Chart pan did not change the data range.");

        renderer.CancelInteraction(NativeUiPointerCancelReason.HostCaptureLost);
        PlotRange2D afterCancel = _chart.Range;
        renderer.DispatchPointer(Pointer(NativeUiPointerEventType.Move, x + 60, y));
        Require(!renderer.HasPointerCapture && _chart.Range.XMin == afterCancel.XMin,
            "A canceled drag kept changing the chart range.");

        var wheel = Pointer(NativeUiPointerEventType.Wheel, x, y);
        wheel.WheelY = 1;
        wheel.Modifiers = NativeUiModifiers.Control;
        Require(renderer.DispatchPointer(wheel) &&
            _chart.Range.XMax - _chart.Range.XMin < afterCancel.XMax - afterCancel.XMin &&
            _chart.Range.YMin == afterCancel.YMin && _chart.Range.YMax == afterCancel.YMax,
            "Ctrl+wheel did not zoom the retained chart's X axis independently.");
    }

    private static NativeUiPointerEvent Pointer(NativeUiPointerEventType type, float x, float y, int button = -1) =>
        new() { Type = type, X = x, Y = y, Button = button, ClickCount = button < 0 ? 0u : 1u };

    private async Task<BitmapSource> WaitForSignalAsync(Stopwatch clock, int afterFrame, bool showCosine,
        int widerThan = 0)
    {
        while (clock.Elapsed < TimeSpan.FromSeconds(20))
        {
            if (_renderError is Exception error)
                throw new InvalidOperationException("Native chart document rendering failed.", error);
            Require(!_closed, "The chart document closed before the smoke completed.");
            if (_presentedFrames > afterFrame && _host.RenderHost.FramebufferWidth > widerThan)
            {
                NativeUiRect view = _chartView.Bounds;
                PlotRect2D viewport = _chart.Layout.Viewport;
                Require(view.Width > 0 && view.Height > 0 && view.Y >= _button.Bounds.Y + _button.Bounds.Height &&
                    viewport.Width == view.Width && viewport.Height == view.Height,
                    "Chart projection does not match the native SceneView layout.");
                DpiScale dpi = VisualTreeHelper.GetDpi(_host);
                var image = new RenderTargetBitmap(_host.RenderHost.FramebufferWidth,
                    _host.RenderHost.FramebufferHeight, dpi.PixelsPerInchX, dpi.PixelsPerInchY, PixelFormats.Pbgra32);
                image.Render(_host);
                if (HasSignalPixels(image, view, dpi, showCosine))
                    return image;
            }
            await Task.Delay(80);
        }
        throw new TimeoutException($"Expected {(showCosine ? "cosine" : "sine")} pixels after frame {afterFrame}, " +
            $"current frame {_presentedFrames}, width greater than {widerThan}.");
    }

    private bool HasSignalPixels(BitmapSource image, NativeUiRect view, DpiScale dpi, bool showCosine)
    {
        PlotRect2D plot = _chart.Layout.PlotArea;
        // Sample the interior to exclude axis labels and the colored legend.
        var rect = new Int32Rect(
            (int)((view.X + plot.X + 0.15f * plot.Width) * dpi.DpiScaleX),
            (int)((view.Y + plot.Y + 0.15f * plot.Height) * dpi.DpiScaleY),
            (int)(0.65f * plot.Width * dpi.DpiScaleX),
            (int)(0.70f * plot.Height * dpi.DpiScaleY));
        if (rect.Width < 1 || rect.Height < 1)
            return false;
        int stride = 4 * rect.Width;
        var pixels = new byte[stride * rect.Height];
        image.CopyPixels(rect, pixels, stride, 0);
        int sine = 0, cosine = 0;
        for (int i = 0; i < pixels.Length; i += 4)
        {
            int b = pixels[i], g = pixels[i + 1], r = pixels[i + 2];
            if (b > g + 25 && g > r + 25)
                ++sine;
            if (r > g + 25 && g > b + 25)
                ++cosine;
        }
        return showCosine ? cosine > 40 && cosine > sine * 3 : sine > 40 && sine > cosine * 3;
    }

    private static void SaveSmokeCapture(BitmapSource image, string stage)
    {
        string? directory = Environment.GetEnvironmentVariable("TERMIN_PLOT_DEMO_CAPTURE_DIR");
        if (string.IsNullOrEmpty(directory))
            return;
        Directory.CreateDirectory(directory);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(image));
        using var file = File.Create(Path.Combine(directory, $"native-chart-document-{stage}.png"));
        encoder.Save(file);
    }

    private static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }
}
