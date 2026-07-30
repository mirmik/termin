using System;
using System.Collections.Generic;
using System.Linq;

namespace Termin.Native;

public sealed class Chart2DTheme
{
    public VisualColor4f BackgroundColor { get; set; } =
        new(0.08f, 0.09f, 0.11f);
    public VisualColor4f PlotBackgroundColor { get; set; } =
        new(0.12f, 0.13f, 0.16f);
    public VisualColor4f ForegroundColor { get; set; } =
        new(0.88f, 0.89f, 0.92f);
    public VisualColor4f AxisColor { get; set; } =
        new(0.65f, 0.67f, 0.72f);
    public PlotGridStyle2D GridStyle { get; set; } =
        new(0.35f, 0.37f, 0.42f, 0.55f);
    public float AxisWidthLogicalPx { get; set; } = 1;
    public float FontSizeLogicalPx { get; set; } = 12;
    public float TitleFontSizeLogicalPx { get; set; } = 16;
    public float TickLengthLogicalPx { get; set; } = 5;
    public float GapLogicalPx { get; set; } = 6;
    public float OuterPaddingLogicalPx { get; set; } = 10;
    public float XTickSpacingLogicalPx { get; set; } = 80;
    public float YTickSpacingLogicalPx { get; set; } = 50;

    public static Chart2DTheme Default => new();
}

public readonly struct ChartLayout2D
{
    public readonly PlotRect2D Viewport;
    public readonly PlotRect2D PlotArea;
    public readonly float PixelScale;

    public ChartLayout2D(
        PlotRect2D viewport,
        PlotRect2D plotArea,
        float pixelScale)
    {
        Viewport = viewport;
        PlotArea = plotArea;
        PixelScale = pixelScale;
    }
}

/// <summary>
/// A named, replaceable chart part. The item body is always native and owned
/// by the chart's visual scene; this slot only owns composition policy.
/// </summary>
public sealed class ChartPart2D<T> where T : GraphicItemRef2D
{
    private readonly TcVisualScene2D _scene;
    private readonly GraphicItemRef2D _parent;
    private readonly long _zOrder;
    private readonly Action<T?> _changed;
    private T? _item;

    internal ChartPart2D(
        TcVisualScene2D scene,
        GraphicItemRef2D parent,
        T item,
        long zOrder,
        Action<T?> changed)
    {
        _scene = scene;
        _parent = parent;
        _item = item;
        _zOrder = zOrder;
        _changed = changed;
        item.ZOrder = zOrder;
    }

    public T? Item
    {
        get
        {
            var item = _item;
            return item is { IsValid: true } ? item : null;
        }
    }

    public void Replace(T replacement)
    {
        if (replacement is null)
            throw new ArgumentNullException(nameof(replacement));
        if (!replacement.IsValid ||
            !replacement.Scene.Equals(_scene.NativeHandle))
            throw new ArgumentException(
                "The replacement must be a valid item from the chart scene.",
                nameof(replacement));

        var previous = Item;
        if (previous?.Handle == replacement.Handle)
            return;
        if (!replacement.SetParent(_parent))
            throw new InvalidOperationException(
                "The replacement could not be adopted by the chart part.");
        replacement.ZOrder = _zOrder;
        _item = replacement;
        _changed(replacement);
        if (previous is not null)
            previous.Destroy();
    }

    public void Remove()
    {
        var previous = Item;
        _item = null;
        _changed(null);
        if (previous is not null)
            previous.Destroy();
    }
}

/// <summary>
/// Managed single-panel chart composition over native retained scene items.
/// Layout and part selection live here; large series data and painting remain
/// in native item bodies.
/// </summary>
public sealed class Chart2D : IDisposable
{
    private readonly GpuHost _host;
    private readonly List<PlotLineSeriesItemRef2D> _lines = new();
    private readonly List<PlotScatterSeriesItemRef2D> _scatters = new();
    private readonly List<TextItemRef2D> _xTickLabels = new();
    private readonly List<TextItemRef2D> _yTickLabels = new();
    private bool _disposed;
    private float _widthPx;
    private float _heightPx;
    private float _pixelScale;
    private PlotRange2D _range;
    private string _title = string.Empty;
    private string _xLabel = string.Empty;
    private string _yLabel = string.Empty;

    public Chart2D(
        GpuHost host,
        float widthPx,
        float heightPx,
        PlotRange2D range,
        string fontUri = "ui://default-font",
        float pixelScale = 1,
        Chart2DTheme? theme = null)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        if (string.IsNullOrWhiteSpace(fontUri))
            throw new ArgumentException(
                "A retained text font URI is required.", nameof(fontUri));
        FontUri = fontUri;
        ValidateViewport(widthPx, heightPx, pixelScale);
        ValidateRange(range);
        _widthPx = widthPx;
        _heightPx = heightPx;
        _pixelScale = pixelScale;
        _range = range;
        Theme = theme ?? Chart2DTheme.Default;

        Scene = new TcVisualScene2D();
        PlotProjectionRef2D? projection = null;
        try
        {
            Root = GroupItemRef2D.Create(Scene);
            PlotArea = GroupItemRef2D.Create(Scene, Root);
            Series = GroupItemRef2D.Create(Scene, PlotArea);
            Annotations = GroupItemRef2D.Create(Scene, PlotArea);
            Chrome = GroupItemRef2D.Create(Scene, Root);
            XTickLabels = GroupItemRef2D.Create(Scene, Chrome);
            YTickLabels = GroupItemRef2D.Create(Scene, Chrome);

            var provisional = new PlotRect2D(0, 0, widthPx, heightPx);
            projection = PlotProjectionRef2D.Create(
                Scene,
                new PlotProjectionDescriptor2D(
                    provisional, provisional, range, provisional, pixelScale));
            Projection = projection;

            Background = new ChartPart2D<RectItemRef2D>(
                Scene,
                Root,
                RectItemRef2D.Create(
                    Scene, ToVisual(provisional),
                    Fill(Theme.BackgroundColor), parent: Root),
                -100,
                _ => ApplyLayout());
            PlotBackground = new ChartPart2D<RectItemRef2D>(
                Scene,
                PlotArea,
                RectItemRef2D.Create(
                    Scene, ToVisual(provisional),
                    Fill(Theme.PlotBackgroundColor), parent: PlotArea),
                0,
                _ => ApplyLayout());
            Grid = new ChartPart2D<PlotGridItemRef2D>(
                Scene,
                PlotArea,
                PlotGridItemRef2D.Create(
                    Scene, Projection, style: Theme.GridStyle,
                    parent: PlotArea),
                10,
                _ => ApplyLayout());
            XAxis = new ChartPart2D<PathItemRef2D>(
                Scene,
                Chrome,
                PathItemRef2D.Create(
                    Scene, LinePath(0, 0, 1, 0),
                    stroke: AxisStroke(), parent: Chrome),
                20,
                _ => ApplyLayout());
            YAxis = new ChartPart2D<PathItemRef2D>(
                Scene,
                Chrome,
                PathItemRef2D.Create(
                    Scene, LinePath(0, 0, 0, 1),
                    stroke: AxisStroke(), parent: Chrome),
                20,
                _ => ApplyLayout());
            Title = CreateTextPart(30, VisualTextAnchor2D.Center);
            XAxisLabel = CreateTextPart(30, VisualTextAnchor2D.Center);
            YAxisLabel = CreateTextPart(30, VisualTextAnchor2D.Center);

            PlotArea.ZOrder = 0;
            Series.ZOrder = 20;
            Annotations.ZOrder = 30;
            Chrome.ZOrder = 40;
            ApplyLayout();
        }
        catch
        {
            projection?.Dispose();
            Scene.Dispose();
            throw;
        }
    }

    public TcVisualScene2D Scene { get; }
    public PlotProjectionRef2D Projection { get; }
    public GroupItemRef2D Root { get; }
    public GroupItemRef2D PlotArea { get; }
    public GroupItemRef2D Series { get; }
    public GroupItemRef2D Annotations { get; }
    public GroupItemRef2D Chrome { get; }
    public GroupItemRef2D XTickLabels { get; }
    public GroupItemRef2D YTickLabels { get; }
    public ChartPart2D<RectItemRef2D> Background { get; }
    public ChartPart2D<RectItemRef2D> PlotBackground { get; }
    public ChartPart2D<PlotGridItemRef2D> Grid { get; }
    public ChartPart2D<PathItemRef2D> XAxis { get; }
    public ChartPart2D<PathItemRef2D> YAxis { get; }
    public ChartPart2D<TextItemRef2D> Title { get; }
    public ChartPart2D<TextItemRef2D> XAxisLabel { get; }
    public ChartPart2D<TextItemRef2D> YAxisLabel { get; }
    public string FontUri { get; }
    public Chart2DTheme Theme { get; private set; }
    public ChartLayout2D Layout { get; private set; }
    public PlotRange2D Range => _range;
    public IReadOnlyList<PlotLineSeriesItemRef2D> Lines => _lines;
    public IReadOnlyList<PlotScatterSeriesItemRef2D> Scatters => _scatters;
    public IReadOnlyList<TextItemRef2D> XTicks => _xTickLabels;
    public IReadOnlyList<TextItemRef2D> YTicks => _yTickLabels;

    public string TitleText
    {
        get => _title;
        set
        {
            ThrowIfDisposed();
            _title = value ?? string.Empty;
            ApplyLayout();
        }
    }

    public string XAxisText
    {
        get => _xLabel;
        set
        {
            ThrowIfDisposed();
            _xLabel = value ?? string.Empty;
            ApplyLayout();
        }
    }

    public string YAxisText
    {
        get => _yLabel;
        set
        {
            ThrowIfDisposed();
            _yLabel = value ?? string.Empty;
            ApplyLayout();
        }
    }

    public PlotLineSeriesItemRef2D AddLine(
        double[] x,
        double[] y,
        double[]? scalar = null,
        PlotLineSeriesStyle2D? style = null)
    {
        ThrowIfDisposed();
        var item = PlotLineSeriesItemRef2D.Create(
            Scene, Projection, x, y, scalar, style, Series);
        _lines.Add(item);
        return item;
    }

    public PlotScatterSeriesItemRef2D AddScatter(
        double[] x,
        double[] y,
        PlotScatterSeriesStyle2D? style = null)
    {
        ThrowIfDisposed();
        var item = PlotScatterSeriesItemRef2D.Create(
            Scene, Projection, x, y, style, Series);
        _scatters.Add(item);
        return item;
    }

    public bool RemoveSeries(GraphicItemRef2D item)
    {
        if (item is null)
            throw new ArgumentNullException(nameof(item));
        ThrowIfDisposed();
        if (!item.Scene.Equals(Scene.NativeHandle))
            return false;

        var removed = item is PlotLineSeriesItemRef2D line &&
                      _lines.Remove(line);
        removed |= item is PlotScatterSeriesItemRef2D scatter &&
                   _scatters.Remove(scatter);
        return removed && (!item.IsValid || item.Destroy());
    }

    public void SetRange(PlotRange2D range)
    {
        ThrowIfDisposed();
        ValidateRange(range);
        _range = range;
        ApplyLayout();
    }

    public void PanBy(double deltaX, double deltaY) =>
        SetRange(new PlotRange2D(
            _range.XMin + deltaX,
            _range.XMax + deltaX,
            _range.YMin + deltaY,
            _range.YMax + deltaY));

    public void ZoomAt(double factor, double centerX, double centerY)
    {
        if (!double.IsFinite(factor) || factor <= 0 ||
            !double.IsFinite(centerX) || !double.IsFinite(centerY))
            throw new ArgumentOutOfRangeException(
                nameof(factor), "Zoom inputs must be finite and positive.");
        SetRange(new PlotRange2D(
            centerX + (_range.XMin - centerX) / factor,
            centerX + (_range.XMax - centerX) / factor,
            centerY + (_range.YMin - centerY) / factor,
            centerY + (_range.YMax - centerY) / factor));
    }

    public void Resize(float widthPx, float heightPx, float pixelScale = 1)
    {
        ThrowIfDisposed();
        ValidateViewport(widthPx, heightPx, pixelScale);
        _widthPx = widthPx;
        _heightPx = heightPx;
        _pixelScale = pixelScale;
        ApplyLayout();
    }

    public void ApplyTheme(Chart2DTheme theme)
    {
        ThrowIfDisposed();
        if (theme is null)
            throw new ArgumentNullException(nameof(theme));
        ValidateTheme(theme);
        Theme = theme;
        ApplyLayout();
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        Projection.Dispose();
        Scene.Dispose();
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private ChartPart2D<TextItemRef2D> CreateTextPart(
        long zOrder,
        VisualTextAnchor2D anchor)
    {
        var item = TextItemRef2D.Create(
            Scene, " ", FontUri, new VisualVec2f(0, 0),
            Theme.FontSizeLogicalPx * _pixelScale,
            Theme.ForegroundColor,
            new VisualBounds2f(0, 0, _widthPx, _heightPx),
            anchor,
            Chrome);
        return new ChartPart2D<TextItemRef2D>(
            Scene, Chrome, item, zOrder, _ => ApplyLayout());
    }

    private void ApplyLayout()
    {
        if (_disposed || !Scene.IsValid)
            return;
        ValidateTheme(Theme);

        var scale = _pixelScale;
        var padding = Theme.OuterPaddingLogicalPx * scale;
        var gap = Theme.GapLogicalPx * scale;
        var tickLength = Theme.TickLengthLogicalPx * scale;
        var tickFontPx = Theme.FontSizeLogicalPx * scale;
        var titleFontPx = Theme.TitleFontSizeLogicalPx * scale;

        var provisionalWidth = Math.Max(1, _widthPx - padding * 2);
        var provisionalHeight = Math.Max(1, _heightPx - padding * 2);
        var xTicks = RetainedPlotLayout2D.MakeAxisTicks(
            _range.XMin, _range.XMax, provisionalWidth,
            Theme.XTickSpacingLogicalPx, scale);
        var yTicks = RetainedPlotLayout2D.MakeAxisTicks(
            _range.YMin, _range.YMax, provisionalHeight,
            Theme.YTickSpacingLogicalPx, scale);

        var tickMetrics = RetainedPlotLayout2D.MeasureText(
            _host, "Mg", Theme.FontSizeLogicalPx, scale);
        var widestY = yTicks.Length == 0
            ? 0
            : yTicks.Max(tick => RetainedPlotLayout2D.MeasureText(
                _host, tick.Label, Theme.FontSizeLogicalPx, scale).Width);
        var titleHeight = string.IsNullOrEmpty(_title)
            ? 0
            : RetainedPlotLayout2D.MeasureText(
                _host, _title, Theme.TitleFontSizeLogicalPx, scale).LineHeight;
        var xLabelHeight = string.IsNullOrEmpty(_xLabel)
            ? 0
            : tickMetrics.LineHeight + gap;
        var yLabelWidth = string.IsNullOrEmpty(_yLabel)
            ? 0
            : RetainedPlotLayout2D.MeasureText(
                _host, _yLabel, Theme.FontSizeLogicalPx, scale).Width + gap;

        var left = padding + yLabelWidth + widestY + tickLength + gap * 2;
        var top = padding + titleHeight + (titleHeight > 0 ? gap : 0);
        var right = padding;
        var bottom = padding + tickLength + gap + tickMetrics.LineHeight +
                     xLabelHeight;
        var plot = new PlotRect2D(
            left,
            top,
            Math.Max(1, _widthPx - left - right),
            Math.Max(1, _heightPx - top - bottom));
        var viewport = new PlotRect2D(0, 0, _widthPx, _heightPx);
        Layout = new ChartLayout2D(viewport, plot, scale);
        Projection.Update(new PlotProjectionDescriptor2D(
            viewport, plot, _range, plot, scale));

        var visualViewport = ToVisual(viewport);
        var visualPlot = ToVisual(plot);
        Root.SetClip(visualViewport);
        PlotArea.SetClip(visualPlot);
        SetRect(Background.Item, visualViewport, Theme.BackgroundColor);
        SetRect(
            PlotBackground.Item, visualPlot, Theme.PlotBackgroundColor);

        var exactXTicks = RetainedPlotLayout2D.MakeAxisTicks(
            _range.XMin, _range.XMax, plot.Width,
            Theme.XTickSpacingLogicalPx, scale);
        var exactYTicks = RetainedPlotLayout2D.MakeAxisTicks(
            _range.YMin, _range.YMax, plot.Height,
            Theme.YTickSpacingLogicalPx, scale);
        var xValues = exactXTicks.Select(tick => tick.Value).ToArray();
        var yValues = exactYTicks.Select(tick => tick.Value).ToArray();
        if (Grid.Item is { } grid)
        {
            grid.Projection = Projection;
            grid.Style = Theme.GridStyle;
            grid.SetTicks(xValues, yValues);
        }

        SetAxisPaths(exactXTicks, exactYTicks, tickLength);
        RebuildTickLabels(exactXTicks, exactYTicks, tickFontPx, tickMetrics);
        SetText(
            Title.Item, _title,
            new VisualVec2f(_widthPx / 2, padding + titleFontPx),
            titleFontPx, VisualTextAnchor2D.Center);
        SetText(
            XAxisLabel.Item, _xLabel,
            new VisualVec2f(
                plot.X + plot.Width / 2,
                _heightPx - padding),
            tickFontPx, VisualTextAnchor2D.Center);
        SetText(
            YAxisLabel.Item, _yLabel,
            new VisualVec2f(padding, plot.Y + plot.Height / 2),
            tickFontPx, VisualTextAnchor2D.Left);
    }

    private void SetAxisPaths(
        PlotAxisTick2D[] xTicks,
        PlotAxisTick2D[] yTicks,
        float tickLength)
    {
        var plot = Layout.PlotArea;
        var xVerbs = new List<VisualPathVerb2D>();
        var xPoints = new List<VisualVec2f>();
        AddLine(xVerbs, xPoints, plot.X, plot.Y + plot.Height,
            plot.X + plot.Width, plot.Y + plot.Height);
        foreach (var tick in xTicks)
        {
            var p = Projection.DataToVisual(
                new PlotPoint2D(tick.Value, _range.YMin));
            AddLine(xVerbs, xPoints, p.X, plot.Y + plot.Height,
                p.X, plot.Y + plot.Height + tickLength);
        }

        var yVerbs = new List<VisualPathVerb2D>();
        var yPoints = new List<VisualVec2f>();
        AddLine(yVerbs, yPoints, plot.X, plot.Y, plot.X, plot.Y + plot.Height);
        foreach (var tick in yTicks)
        {
            var p = Projection.DataToVisual(
                new PlotPoint2D(_range.XMin, tick.Value));
            AddLine(yVerbs, yPoints, plot.X - tickLength, p.Y, plot.X, p.Y);
        }

        XAxis.Item?.Set(
            new VisualPath2D(xVerbs.ToArray(), xPoints.ToArray()),
            stroke: AxisStroke());
        YAxis.Item?.Set(
            new VisualPath2D(yVerbs.ToArray(), yPoints.ToArray()),
            stroke: AxisStroke());
    }

    private void RebuildTickLabels(
        PlotAxisTick2D[] xTicks,
        PlotAxisTick2D[] yTicks,
        float fontSizePx,
        PlotTextMetrics2D metrics)
    {
        DestroyItems(_xTickLabels);
        DestroyItems(_yTickLabels);
        var plot = Layout.PlotArea;
        var bounds = new VisualBounds2f(0, 0, _widthPx, _heightPx);
        var gap = Theme.GapLogicalPx * _pixelScale;
        var tickLength = Theme.TickLengthLogicalPx * _pixelScale;

        foreach (var tick in xTicks)
        {
            var p = Projection.DataToVisual(
                new PlotPoint2D(tick.Value, _range.YMin));
            _xTickLabels.Add(TextItemRef2D.Create(
                Scene, tick.Label, FontUri,
                new VisualVec2f(
                    p.X,
                    plot.Y + plot.Height + tickLength + gap + metrics.Ascent),
                fontSizePx, Theme.ForegroundColor, bounds,
                VisualTextAnchor2D.Center, XTickLabels));
        }
        foreach (var tick in yTicks)
        {
            var p = Projection.DataToVisual(
                new PlotPoint2D(_range.XMin, tick.Value));
            _yTickLabels.Add(TextItemRef2D.Create(
                Scene, tick.Label, FontUri,
                new VisualVec2f(
                    plot.X - tickLength - gap,
                    p.Y + metrics.Ascent * 0.5f),
                fontSizePx, Theme.ForegroundColor, bounds,
                VisualTextAnchor2D.Right, YTickLabels));
        }
    }

    private void SetText(
        TextItemRef2D? item,
        string text,
        VisualVec2f origin,
        float fontSizePx,
        VisualTextAnchor2D anchor)
    {
        if (item is null)
            return;
        item.Set(
            string.IsNullOrEmpty(text) ? " " : text,
            FontUri, origin, fontSizePx, Theme.ForegroundColor,
            new VisualBounds2f(0, 0, _widthPx, _heightPx), anchor);
        item.Visible = !string.IsNullOrEmpty(text);
    }

    private void SetRect(
        RectItemRef2D? item,
        VisualRect2f rect,
        VisualColor4f color) =>
        item?.Set(rect, Fill(color));

    private VisualStrokePaint2D AxisStroke() =>
        new(
            Theme.AxisColor,
            Theme.AxisWidthLogicalPx * _pixelScale,
            cap: VisualStrokeCap2D.Square);

    private static VisualFillPaint2D Fill(VisualColor4f color) => new(color);

    private static VisualRect2f ToVisual(PlotRect2D rect) =>
        new(rect.X, rect.Y, rect.Width, rect.Height);

    private static VisualPath2D LinePath(
        float x0,
        float y0,
        float x1,
        float y1) =>
        new(
            new[]
            {
                VisualPathVerb2D.MoveTo,
                VisualPathVerb2D.LineTo,
            },
            new[]
            {
                new VisualVec2f(x0, y0),
                new VisualVec2f(x1, y1),
            });

    private static void AddLine(
        List<VisualPathVerb2D> verbs,
        List<VisualVec2f> points,
        float x0,
        float y0,
        float x1,
        float y1)
    {
        verbs.Add(VisualPathVerb2D.MoveTo);
        verbs.Add(VisualPathVerb2D.LineTo);
        points.Add(new VisualVec2f(x0, y0));
        points.Add(new VisualVec2f(x1, y1));
    }

    private static void DestroyItems<T>(List<T> items)
        where T : GraphicItemRef2D
    {
        foreach (var item in items)
            if (item.IsValid)
                item.Destroy();
        items.Clear();
    }

    private static void ValidateRange(PlotRange2D range)
    {
        if (!double.IsFinite(range.XMin) ||
            !double.IsFinite(range.XMax) ||
            !double.IsFinite(range.YMin) ||
            !double.IsFinite(range.YMax) ||
            range.XMax <= range.XMin ||
            range.YMax <= range.YMin)
            throw new ArgumentException(
                "Chart range must be finite and non-empty.", nameof(range));
    }

    private static void ValidateViewport(
        float widthPx,
        float heightPx,
        float pixelScale)
    {
        if (!float.IsFinite(widthPx) || widthPx <= 0 ||
            !float.IsFinite(heightPx) || heightPx <= 0 ||
            !float.IsFinite(pixelScale) || pixelScale <= 0)
            throw new ArgumentOutOfRangeException(
                nameof(widthPx),
                "Viewport dimensions and pixel scale must be finite and positive.");
    }

    private static void ValidateTheme(Chart2DTheme theme)
    {
        if (!float.IsFinite(theme.FontSizeLogicalPx) ||
            theme.FontSizeLogicalPx <= 0 ||
            !float.IsFinite(theme.TitleFontSizeLogicalPx) ||
            theme.TitleFontSizeLogicalPx <= 0 ||
            !float.IsFinite(theme.XTickSpacingLogicalPx) ||
            theme.XTickSpacingLogicalPx <= 0 ||
            !float.IsFinite(theme.YTickSpacingLogicalPx) ||
            theme.YTickSpacingLogicalPx <= 0 ||
            !float.IsFinite(theme.AxisWidthLogicalPx) ||
            theme.AxisWidthLogicalPx <= 0 ||
            !float.IsFinite(theme.TickLengthLogicalPx) ||
            theme.TickLengthLogicalPx < 0 ||
            !float.IsFinite(theme.GapLogicalPx) ||
            theme.GapLogicalPx < 0 ||
            !float.IsFinite(theme.OuterPaddingLogicalPx) ||
            theme.OuterPaddingLogicalPx < 0)
            throw new ArgumentException(
                "Chart theme sizes and tick spacing must be finite and positive.",
                nameof(theme));
    }

    private void ThrowIfDisposed()
    {
        if (_disposed || !Scene.IsValid)
            throw new ObjectDisposedException(nameof(Chart2D));
    }
}
