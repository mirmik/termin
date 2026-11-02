using System.Windows.Media.Imaging;
using Termin.Native;

namespace PlotDemoApp;

public sealed partial class Heatmap2DWindow
{
    private bool MatchesLegendInk(BitmapSource image, string phase)
    {
        // Scene geometry locates the legend; actual WPF pixels determine the
        // text ink bounds. This deliberately avoids trusting text layout bounds
        // or reproducing native text-origin/ascent calculations.
        GraphicItemRef2D? background = null;
        var swatches = new List<VisualBounds2f>();
        for (nuint index = 0; index < _chart.Legend.ChildCount; ++index)
        {
            var child = _chart.Legend.ChildAt(index);
            if (!child.Visible)
                continue;
            if (child.TypeName == "termin.visual.Rect2D")
                background = child;
            else if (child.TypeName == "termin.visual.Group2D")
            {
                bool hasLabel = false;
                VisualBounds2f? swatch = null;
                for (nuint partIndex = 0; partIndex < child.ChildCount; ++partIndex)
                {
                    var part = child.ChildAt(partIndex);
                    if (!part.Visible)
                        continue;
                    if (part.TypeName == "termin.visual.Text2D")
                        hasLabel = true;
                    else if (part.TypeName == "termin.visual.Path2D" &&
                             part.TryGetWorldBounds(out var bounds))
                        swatch = bounds;
                }
                if (hasLabel && swatch.HasValue)
                    swatches.Add(swatch.Value);
            }
        }
        if (background is null || !background.TryGetWorldBounds(out var box) || swatches.Count != 1)
            throw new InvalidOperationException("Legend pixel smoke requires one visible legend entry and its background.");

        var pixels = new byte[image.PixelWidth * image.PixelHeight * 4];
        image.CopyPixels(pixels, image.PixelWidth * 4, 0);
        float fontSize = _chart.Theme.FontSizeLogicalPx * _chart.Layout.PixelScale;
        var line = swatches[0];
        double center = (line.Y0 + line.Y1) * 0.5;
        int left = Math.Max(0, (int)Math.Ceiling(line.X1 +
            _chart.Theme.GapLogicalPx * _chart.Layout.PixelScale * 0.5));
        int right = Math.Min(image.PixelWidth - 1, (int)Math.Ceiling(box.X1 + fontSize));
        int top = Math.Max(0, (int)Math.Floor(center - 2 * fontSize));
        int bottom = Math.Min(image.PixelHeight - 1, (int)Math.Ceiling(center + 2 * fontSize));
        int inkLeft = image.PixelWidth, inkRight = -1, inkTop = image.PixelHeight, inkBottom = -1;
        for (int y = top; y <= bottom; ++y)
        for (int x = left; x <= right; ++x)
        {
            int offset = (y * image.PixelWidth + x) * 4;
            if (pixels[offset] < 180 || pixels[offset + 1] < 180 || pixels[offset + 2] < 180)
                continue;
            inkLeft = Math.Min(inkLeft, x);
            inkRight = Math.Max(inkRight, x);
            inkTop = Math.Min(inkTop, y);
            inkBottom = Math.Max(inkBottom, y);
        }
        double inkCenter = (inkTop + inkBottom + 1) * 0.5;
        double tolerance = Math.Max(2, fontSize * 0.2);
        if (inkRight < inkLeft || Math.Abs(inkCenter - center) > tolerance ||
            inkLeft < box.X0 || inkRight + 1 > box.X1 || inkTop < box.Y0 || inkBottom + 1 > box.Y1)
        {
            Console.WriteLine($"HEATMAP_LEGEND_WAIT phase={phase} ink=" +
                $"{inkLeft},{inkTop}..{inkRight + 1},{inkBottom + 1} " +
                $"swatchCenter={center:F2} legend={box.X0:F2},{box.Y0:F2}..{box.X1:F2},{box.Y1:F2}");
            return false;
        }
        SaveHeatmapCapture(image, $"legend-{phase}");
        Console.WriteLine($"HEATMAP_LEGEND_INK_OK phase={phase} " +
            $"inkCenter={inkCenter:F2} swatchCenter={center:F2} insideBackground=true");
        return true;
    }
}
