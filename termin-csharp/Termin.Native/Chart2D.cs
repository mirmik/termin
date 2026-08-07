using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

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

    internal Chart2DNative.Theme ToNative() => new(this);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct ChartLayout2D
{
    public readonly PlotRect2D Viewport;
    public readonly PlotRect2D PlotArea;
    public readonly float PixelScale;
    public readonly ulong Revision;

    internal ChartLayout2D(Chart2DNative.Layout value)
    {
        Viewport = value.Viewport;
        PlotArea = value.PlotArea;
        PixelScale = value.PixelScale;
        Revision = value.Revision;
    }
}

internal enum ChartPartKind2D
{
    Root,
    Background,
    PlotArea,
    PlotBackground,
    Grid,
    SeriesRoot,
    AnnotationsRoot,
    ChromeRoot,
    XAxisRoot,
    YAxisRoot,
    XAxis,
    YAxis,
    XTickLabelsRoot,
    YTickLabelsRoot,
    Title,
    XAxisLabel,
    YAxisLabel,
    LegendRoot,
    OverlayRoot,
}

/// <summary>
/// A named native chart slot. The item body belongs to the chart's public
/// visual scene; this wrapper carries no layout or ownership policy.
/// </summary>
public sealed class ChartPart2D<T> where T : GraphicItemRef2D
{
    private readonly Chart2D _chart;
    private readonly ChartPartKind2D _kind;
    private readonly Func<GraphicItemRef2D, T> _cast;

    internal ChartPart2D(
        Chart2D chart,
        ChartPartKind2D kind,
        Func<GraphicItemRef2D, T> cast)
    {
        _chart = chart;
        _kind = kind;
        _cast = cast;
    }

    public T? Item
    {
        get
        {
            GraphicItemHandle2D handle = _chart.GetPartHandle(_kind);
            return handle.IsValid
                ? _cast(new GraphicItemRef2D(
                    _chart.Scene.NativeHandle, handle))
                : null;
        }
    }

    public void Replace(T replacement)
    {
        if (replacement is null)
            throw new ArgumentNullException(nameof(replacement));
        _chart.ReplacePart(_kind, replacement);
    }

    public void Remove() => _chart.RemovePart(_kind);
}

/// <summary>
/// Thin managed projection of tcplot's native open retained chart composer.
/// Layout, ticks, text measurement, projection synchronization and standard
/// part topology live in tcplot. Scene items remain directly customizable.
/// </summary>
public sealed class Chart2D : IDisposable
{
    private readonly GpuHost _host;
    private readonly List<PlotLineSeriesItemRef2D> _lines = new();
    private readonly List<PlotScatterSeriesItemRef2D> _scatters = new();
    private readonly bool _disposeSceneView;
    private IntPtr _native;
    private bool _disposed;
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
        : this(
            host,
            null,
            new VisualRect2f(0, 0, widthPx, heightPx),
            range,
            fontUri,
            pixelScale,
            theme,
            borrowedMarker: false)
    {
    }

    /// <summary>
    /// Adds one native chart subtree to a caller-owned scene. This is the
    /// composition seam used while RetainedMultiChart2D is being introduced.
    /// </summary>
    public Chart2D(
        GpuHost host,
        TcVisualScene2D scene,
        VisualRect2f viewport,
        PlotRange2D range,
        string fontUri = "ui://default-font",
        float pixelScale = 1,
        Chart2DTheme? theme = null)
        : this(
            host,
            scene ?? throw new ArgumentNullException(nameof(scene)),
            viewport,
            range,
            fontUri,
            pixelScale,
            theme,
            borrowedMarker: true)
    {
    }

    private Chart2D(
        GpuHost host,
        TcVisualScene2D? borrowedScene,
        VisualRect2f viewport,
        PlotRange2D range,
        string fontUri,
        float pixelScale,
        Chart2DTheme? theme,
        bool borrowedMarker)
    {
        if (host is null)
            throw new ArgumentNullException(nameof(host));
        _host = host;
        if (string.IsNullOrWhiteSpace(fontUri))
            throw new ArgumentException(
                "A retained text font URI is required.", nameof(fontUri));
        borrowedScene?.ThrowIfDisposed();

        Theme = theme ?? Chart2DTheme.Default;
        Chart2DNative.Theme nativeTheme = Theme.ToNative();
        var nativeViewport = new PlotRect2D(
            viewport.X, viewport.Y, viewport.Width, viewport.Height);
        IntPtr hostPointer = GpuHost.getCPtr(host).Handle;
        _native = borrowedScene is null
            ? Chart2DNative.Create(
                hostPointer,
                nativeViewport,
                range,
                fontUri,
                pixelScale,
                ref nativeTheme)
            : Chart2DNative.CreateInScene(
                hostPointer,
                borrowedScene.NativeHandle,
                nativeViewport,
                range,
                fontUri,
                pixelScale,
                ref nativeTheme);
        if (_native == IntPtr.Zero)
            throw new InvalidOperationException(
                "Failed to create native RetainedChart2D. See native log.");

        try
        {
            VisualSceneNativeHandle sceneHandle =
                Chart2DNative.Scene(_native);
            Scene = borrowedScene ?? TcVisualScene2D.Borrow(sceneHandle);
            _disposeSceneView = borrowedScene is null;
            Projection = PlotProjectionRef2D.Borrow(
                Chart2DNative.Projection(_native));
            FontUri = fontUri;

            Root = GetGroup(ChartPartKind2D.Root);
            PlotArea = GetGroup(ChartPartKind2D.PlotArea);
            Series = GetGroup(ChartPartKind2D.SeriesRoot);
            Annotations = GetGroup(ChartPartKind2D.AnnotationsRoot);
            Chrome = GetGroup(ChartPartKind2D.ChromeRoot);
            XAxisRoot = GetGroup(ChartPartKind2D.XAxisRoot);
            YAxisRoot = GetGroup(ChartPartKind2D.YAxisRoot);
            XTickLabels = GetGroup(ChartPartKind2D.XTickLabelsRoot);
            YTickLabels = GetGroup(ChartPartKind2D.YTickLabelsRoot);
            Legend = GetGroup(ChartPartKind2D.LegendRoot);
            Overlay = GetGroup(ChartPartKind2D.OverlayRoot);

            Background = Part(
                ChartPartKind2D.Background, RectItemRef2D.Cast);
            PlotBackground = Part(
                ChartPartKind2D.PlotBackground, RectItemRef2D.Cast);
            Grid = Part(
                ChartPartKind2D.Grid, PlotGridItemRef2D.Cast);
            XAxis = Part(
                ChartPartKind2D.XAxis, PathItemRef2D.Cast);
            YAxis = Part(
                ChartPartKind2D.YAxis, PathItemRef2D.Cast);
            Title = Part(
                ChartPartKind2D.Title, TextItemRef2D.Cast);
            XAxisLabel = Part(
                ChartPartKind2D.XAxisLabel, TextItemRef2D.Cast);
            YAxisLabel = Part(
                ChartPartKind2D.YAxisLabel, TextItemRef2D.Cast);
        }
        catch
        {
            Chart2DNative.Destroy(_native);
            _native = IntPtr.Zero;
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
    public GroupItemRef2D XAxisRoot { get; }
    public GroupItemRef2D YAxisRoot { get; }
    public GroupItemRef2D XTickLabels { get; }
    public GroupItemRef2D YTickLabels { get; }
    public GroupItemRef2D Legend { get; }
    public GroupItemRef2D Overlay { get; }
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
    public IReadOnlyList<PlotLineSeriesItemRef2D> Lines => _lines;
    public IReadOnlyList<PlotScatterSeriesItemRef2D> Scatters => _scatters;

    public ChartLayout2D Layout
    {
        get
        {
            ThrowIfDisposed();
            if (!Chart2DNative.GetLayout(_native, out var value))
                throw new InvalidOperationException(
                    "Failed to snapshot native chart layout.");
            return new ChartLayout2D(value);
        }
    }

    public PlotRange2D Range
    {
        get
        {
            ThrowIfDisposed();
            if (!Chart2DNative.GetRange(_native, out var value))
                throw new InvalidOperationException(
                    "Failed to snapshot native chart range.");
            return value;
        }
    }

    public string TitleText
    {
        get => _title;
        set
        {
            ThrowIfDisposed();
            string resolved = value ?? string.Empty;
            Require(Chart2DNative.SetTitle(_native, resolved));
            _title = resolved;
        }
    }

    public string XAxisText
    {
        get => _xLabel;
        set
        {
            ThrowIfDisposed();
            string resolved = value ?? string.Empty;
            Require(Chart2DNative.SetXAxisLabel(_native, resolved));
            _xLabel = resolved;
        }
    }

    public string YAxisText
    {
        get => _yLabel;
        set
        {
            ThrowIfDisposed();
            string resolved = value ?? string.Empty;
            Require(Chart2DNative.SetYAxisLabel(_native, resolved));
            _yLabel = resolved;
        }
    }

    public PlotLineSeriesItemRef2D AddLine(
        double[] x,
        double[] y,
        double[]? scalar = null,
        PlotLineSeriesStyle2D? style = null)
    {
        ValidateLineData(x, y, scalar);
        ThrowIfDisposed();
        GraphicItemHandle2D handle = Chart2DNative.AddLine(
            _native,
            x,
            y,
            scalar,
            (nuint)x.Length,
            style ?? PlotLineSeriesStyle2D.Default);
        var item = PlotLineSeriesItemRef2D.Cast(
            new GraphicItemRef2D(Scene.NativeHandle, RequireHandle(handle)));
        _lines.Add(item);
        return item;
    }

    public PlotScatterSeriesItemRef2D AddScatter(
        double[] x,
        double[] y,
        PlotScatterSeriesStyle2D? style = null)
    {
        if (x is null || y is null)
            throw new ArgumentNullException(x is null ? nameof(x) : nameof(y));
        if (x.Length != y.Length)
            throw new ArgumentException("Series arrays must have equal lengths.");
        ThrowIfDisposed();
        GraphicItemHandle2D handle = Chart2DNative.AddScatter(
            _native,
            x,
            y,
            (nuint)x.Length,
            style ?? PlotScatterSeriesStyle2D.Default);
        var item = PlotScatterSeriesItemRef2D.Cast(
            new GraphicItemRef2D(Scene.NativeHandle, RequireHandle(handle)));
        _scatters.Add(item);
        return item;
    }

    public bool RemoveSeries(GraphicItemRef2D item)
    {
        if (item is null)
            throw new ArgumentNullException(nameof(item));
        ThrowIfDisposed();
        if (!item.Scene.Equals(Scene.NativeHandle) ||
            !Chart2DNative.RemoveSeries(_native, item.Handle))
            return false;
        _lines.RemoveAll(line => line.Handle.Equals(item.Handle));
        _scatters.RemoveAll(scatter => scatter.Handle.Equals(item.Handle));
        return true;
    }

    public void SetRange(PlotRange2D range)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.SetRange(_native, range));
    }

    public void Fit(double paddingFraction = 0.05)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.Fit(_native, paddingFraction));
    }

    public void FitX(double paddingFraction = 0.05)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.FitX(_native, paddingFraction));
    }

    public void FitY(double paddingFraction = 0.05)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.FitY(_native, paddingFraction));
    }

    public void PanBy(double deltaX, double deltaY)
    {
        PlotRange2D range = Range;
        SetRange(new PlotRange2D(
            range.XMin + deltaX,
            range.XMax + deltaX,
            range.YMin + deltaY,
            range.YMax + deltaY));
    }

    public void ZoomAt(double factor, double centerX, double centerY)
    {
        if (!double.IsFinite(factor) || factor <= 0 ||
            !double.IsFinite(centerX) || !double.IsFinite(centerY))
            throw new ArgumentOutOfRangeException(
                nameof(factor), "Zoom inputs must be finite and positive.");
        PlotRange2D range = Range;
        SetRange(new PlotRange2D(
            centerX + (range.XMin - centerX) / factor,
            centerX + (range.XMax - centerX) / factor,
            centerY + (range.YMin - centerY) / factor,
            centerY + (range.YMax - centerY) / factor));
    }

    public void Resize(float widthPx, float heightPx, float pixelScale = 1)
    {
        PlotRect2D viewport = Layout.Viewport;
        SetViewport(
            new VisualRect2f(viewport.X, viewport.Y, widthPx, heightPx),
            pixelScale);
    }

    public void SetViewport(VisualRect2f viewport, float pixelScale = 1)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.SetViewport(
            _native,
            new PlotRect2D(
                viewport.X, viewport.Y, viewport.Width, viewport.Height),
            pixelScale));
    }

    public void ApplyTheme(Chart2DTheme theme)
    {
        if (theme is null)
            throw new ArgumentNullException(nameof(theme));
        ThrowIfDisposed();
        Chart2DNative.Theme value = theme.ToNative();
        Require(Chart2DNative.SetTheme(_native, ref value));
        Theme = theme;
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        if (_native != IntPtr.Zero)
            Chart2DNative.Destroy(_native);
        _native = IntPtr.Zero;
        Projection.Dispose();
        if (_disposeSceneView)
            Scene.Dispose();
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    internal GraphicItemHandle2D GetPartHandle(ChartPartKind2D kind)
    {
        ThrowIfDisposed();
        return Chart2DNative.PartHandle(_native, kind);
    }

    internal void ReplacePart(
        ChartPartKind2D kind,
        GraphicItemRef2D replacement)
    {
        ThrowIfDisposed();
        replacement.ThrowIfStale();
        if (!replacement.Scene.Equals(Scene.NativeHandle))
            throw new ArgumentException(
                "Replacement must belong to the chart scene.",
                nameof(replacement));
        Require(Chart2DNative.ReplacePart(
            _native, kind, replacement.Handle));
    }

    internal void RemovePart(ChartPartKind2D kind)
    {
        ThrowIfDisposed();
        Require(Chart2DNative.RemovePart(_native, kind));
    }

    private GroupItemRef2D GetGroup(ChartPartKind2D kind) =>
        GroupItemRef2D.Cast(new GraphicItemRef2D(
            Scene.NativeHandle,
            RequireHandle(Chart2DNative.PartHandle(_native, kind))));

    private ChartPart2D<T> Part<T>(
        ChartPartKind2D kind,
        Func<GraphicItemRef2D, T> cast)
        where T : GraphicItemRef2D => new(this, kind, cast);

    private static GraphicItemHandle2D RequireHandle(
        GraphicItemHandle2D handle) => handle.IsValid
        ? handle
        : throw new InvalidOperationException(
            "Native chart returned an invalid item handle.");

    private static void Require(bool success)
    {
        if (!success)
            throw new InvalidOperationException(
                "Native RetainedChart2D operation was rejected. See native log.");
    }

    private static void ValidateLineData(
        double[] x,
        double[] y,
        double[]? scalar)
    {
        if (x is null || y is null)
            throw new ArgumentNullException(x is null ? nameof(x) : nameof(y));
        if (x.Length != y.Length ||
            (scalar is not null && scalar.Length != x.Length))
            throw new ArgumentException("Series arrays must have equal lengths.");
    }

    private void ThrowIfDisposed()
    {
        if (_disposed || _native == IntPtr.Zero)
            throw new ObjectDisposedException(nameof(Chart2D));
    }
}

internal static class Chart2DNative
{
    private const string Dll = "tcplot";

    [StructLayout(LayoutKind.Sequential)]
    internal readonly struct Theme
    {
        internal readonly VisualColor4f BackgroundColor;
        internal readonly VisualColor4f PlotBackgroundColor;
        internal readonly VisualColor4f ForegroundColor;
        internal readonly VisualColor4f AxisColor;
        internal readonly PlotGridStyle2D GridStyle;
        internal readonly float AxisWidthLogicalPx;
        internal readonly float FontSizeLogicalPx;
        internal readonly float TitleFontSizeLogicalPx;
        internal readonly float TickLengthLogicalPx;
        internal readonly float GapLogicalPx;
        internal readonly float OuterPaddingLogicalPx;
        internal readonly float XTickSpacingLogicalPx;
        internal readonly float YTickSpacingLogicalPx;

        internal Theme(Chart2DTheme value)
        {
            BackgroundColor = value.BackgroundColor;
            PlotBackgroundColor = value.PlotBackgroundColor;
            ForegroundColor = value.ForegroundColor;
            AxisColor = value.AxisColor;
            GridStyle = value.GridStyle;
            AxisWidthLogicalPx = value.AxisWidthLogicalPx;
            FontSizeLogicalPx = value.FontSizeLogicalPx;
            TitleFontSizeLogicalPx = value.TitleFontSizeLogicalPx;
            TickLengthLogicalPx = value.TickLengthLogicalPx;
            GapLogicalPx = value.GapLogicalPx;
            OuterPaddingLogicalPx = value.OuterPaddingLogicalPx;
            XTickSpacingLogicalPx = value.XTickSpacingLogicalPx;
            YTickSpacingLogicalPx = value.YTickSpacingLogicalPx;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    internal readonly struct Layout
    {
        internal readonly PlotRect2D Viewport;
        internal readonly PlotRect2D PlotArea;
        internal readonly float PixelScale;
        internal readonly ulong Revision;
    }

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_create")]
    internal static extern IntPtr Create(
        IntPtr gpuHost,
        PlotRect2D viewport,
        PlotRange2D range,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string fontUri,
        float pixelScale,
        ref Theme theme);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_create_in_scene")]
    internal static extern IntPtr CreateInScene(
        IntPtr gpuHost,
        VisualSceneNativeHandle scene,
        PlotRect2D viewport,
        PlotRange2D range,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string fontUri,
        float pixelScale,
        ref Theme theme);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_destroy")]
    internal static extern void Destroy(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_scene")]
    internal static extern VisualSceneNativeHandle Scene(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_projection")]
    internal static extern PlotProjectionHandle2D Projection(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_part_handle")]
    internal static extern GraphicItemHandle2D PartHandle(
        IntPtr chart,
        ChartPartKind2D part);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_layout")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GetLayout(IntPtr chart, out Layout layout);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_range")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GetRange(
        IntPtr chart,
        out PlotRange2D range);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_viewport")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetViewport(
        IntPtr chart,
        PlotRect2D viewport,
        float pixelScale);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_range")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetRange(IntPtr chart, PlotRange2D range);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_fit")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool Fit(IntPtr chart, double paddingFraction);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_fit_x")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool FitX(IntPtr chart, double paddingFraction);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_fit_y")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool FitY(IntPtr chart, double paddingFraction);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_theme")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetTheme(IntPtr chart, ref Theme theme);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_title")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetTitle(
        IntPtr chart,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string value);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_x_axis_label")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetXAxisLabel(
        IntPtr chart,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string value);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_set_y_axis_label")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetYAxisLabel(
        IntPtr chart,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string value);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_replace_part")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ReplacePart(
        IntPtr chart,
        ChartPartKind2D part,
        GraphicItemHandle2D replacement);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_remove_part")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool RemovePart(
        IntPtr chart,
        ChartPartKind2D part);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_add_line")]
    internal static extern GraphicItemHandle2D AddLine(
        IntPtr chart,
        double[] x,
        double[] y,
        double[]? scalar,
        nuint count,
        PlotLineSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_add_scatter")]
    internal static extern GraphicItemHandle2D AddScatter(
        IntPtr chart,
        double[] x,
        double[] y,
        nuint count,
        PlotScatterSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart2d_remove_series")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool RemoveSeries(
        IntPtr chart,
        GraphicItemHandle2D series);
}
