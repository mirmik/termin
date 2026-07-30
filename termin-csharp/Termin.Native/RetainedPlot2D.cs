using System;
using System.Runtime.InteropServices;
using System.Text;

namespace Termin.Native;

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotProjectionHandle2D :
    IEquatable<PlotProjectionHandle2D>
{
    public readonly ulong SceneId;
    public readonly uint Index;
    public readonly uint Generation;

    public bool IsValid =>
        SceneId != 0 && Index != uint.MaxValue && Generation != 0;

    public bool Equals(PlotProjectionHandle2D other) =>
        SceneId == other.SceneId &&
        Index == other.Index &&
        Generation == other.Generation;

    public override bool Equals(object? obj) =>
        obj is PlotProjectionHandle2D other && Equals(other);

    public override int GetHashCode() =>
        HashCode.Combine(SceneId, Index, Generation);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotRect2D
{
    public readonly float X;
    public readonly float Y;
    public readonly float Width;
    public readonly float Height;

    public PlotRect2D(float x, float y, float width, float height)
    {
        X = x;
        Y = y;
        Width = width;
        Height = height;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotRange2D
{
    public readonly double XMin;
    public readonly double XMax;
    public readonly double YMin;
    public readonly double YMax;

    public PlotRange2D(
        double xMin,
        double xMax,
        double yMin,
        double yMax)
    {
        XMin = xMin;
        XMax = xMax;
        YMin = yMin;
        YMax = yMax;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotProjectionDescriptor2D
{
    public readonly PlotRect2D Viewport;
    public readonly PlotRect2D PlotArea;
    public readonly PlotRange2D Range;
    public readonly PlotRect2D ClipRect;
    public readonly float PixelScale;

    public PlotProjectionDescriptor2D(
        PlotRect2D viewport,
        PlotRect2D plotArea,
        PlotRange2D range,
        PlotRect2D clipRect,
        float pixelScale = 1)
    {
        Viewport = viewport;
        PlotArea = plotArea;
        Range = range;
        ClipRect = clipRect;
        PixelScale = pixelScale;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotProjectionState2D
{
    public readonly PlotProjectionDescriptor2D Projection;
    public readonly ulong Revision;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotPoint2D
{
    public readonly double X;
    public readonly double Y;

    public PlotPoint2D(double x, double y)
    {
        X = x;
        Y = y;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotVisualPoint2D
{
    public readonly float X;
    public readonly float Y;

    public PlotVisualPoint2D(float x, float y)
    {
        X = x;
        Y = y;
    }
}

public sealed class PlotProjectionRef2D : IDisposable
{
    private PlotProjectionHandle2D _handle;
    private readonly bool _ownsHandle;
    private bool _disposed;

    private PlotProjectionRef2D(
        PlotProjectionHandle2D handle,
        bool ownsHandle)
    {
        _handle = handle;
        _ownsHandle = ownsHandle;
    }

    public PlotProjectionHandle2D Handle => _handle;
    public bool IsValid =>
        !_disposed && RetainedPlotNative.ProjectionIsValid(_handle);

    public PlotProjectionState2D State
    {
        get
        {
            ThrowIfStale();
            if (!RetainedPlotNative.ProjectionSnapshot(
                    _handle, out var state))
                throw new InvalidOperationException(
                    "Failed to snapshot PlotProjection2D.");
            return state;
        }
    }

    public static PlotProjectionRef2D Create(
        TcVisualScene2D scene,
        PlotProjectionDescriptor2D descriptor)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        scene.ThrowIfDisposed();
        var handle = RetainedPlotNative.ProjectionCreate(
            scene.NativeHandle, ref descriptor);
        if (!handle.IsValid)
            throw new InvalidOperationException(
                "Failed to create PlotProjection2D.");
        return new PlotProjectionRef2D(handle, true);
    }

    internal static PlotProjectionRef2D Borrow(
        PlotProjectionHandle2D handle) =>
        new(handle, false);

    public void Update(PlotProjectionDescriptor2D descriptor)
    {
        ThrowIfStale();
        if (!RetainedPlotNative.ProjectionUpdate(
                _handle, ref descriptor))
            throw new InvalidOperationException(
                "PlotProjection2D update was rejected.");
    }

    public PlotVisualPoint2D DataToVisual(PlotPoint2D point)
    {
        var state = State;
        if (!RetainedPlotNative.DataToVisual(
                ref state, point, out var result))
            throw new InvalidOperationException(
                "Data-to-visual projection failed.");
        return result;
    }

    public PlotPoint2D VisualToData(PlotVisualPoint2D point)
    {
        var state = State;
        if (!RetainedPlotNative.VisualToData(
                ref state, point, out var result))
            throw new InvalidOperationException(
                "Visual-to-data projection failed.");
        return result;
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        if (_ownsHandle && _handle.IsValid)
            RetainedPlotNative.ProjectionDestroy(_handle);
        _handle = default;
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    internal void ThrowIfStale()
    {
        if (!IsValid)
            throw new InvalidOperationException(
                "PlotProjectionRef2D is stale.");
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotColor2D
{
    public readonly float R;
    public readonly float G;
    public readonly float B;
    public readonly float A;

    public PlotColor2D(float r, float g, float b, float a = 1)
    {
        R = r;
        G = g;
        B = b;
        A = a;
    }
}

public enum PlotLineStyle2D
{
    Solid,
    Dash,
    Dot,
}

public enum PlotColorMap2D
{
    Jet,
    Viridis,
    Plasma,
    Grayscale,
    CoolWarm,
    Solid,
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotLineSeriesStyle2D
{
    public readonly PlotColor2D Color;
    public readonly float ThicknessPx;
    public readonly PlotLineStyle2D LineStyle;
    public readonly float DashPx;
    public readonly float GapPx;
    public readonly PlotColorMap2D ColorMap;
    [MarshalAs(UnmanagedType.I1)]
    public readonly bool ColorMapReversed;
    public readonly double ScalarMin;
    public readonly double ScalarMax;

    public PlotLineSeriesStyle2D(
        PlotColor2D color,
        float thicknessPx = 1.5f,
        PlotLineStyle2D lineStyle = PlotLineStyle2D.Solid,
        float dashPx = 8,
        float gapPx = 5,
        PlotColorMap2D colorMap = PlotColorMap2D.Solid,
        bool colorMapReversed = false,
        double scalarMin = 0,
        double scalarMax = 1)
    {
        Color = color;
        ThicknessPx = thicknessPx;
        LineStyle = lineStyle;
        DashPx = dashPx;
        GapPx = gapPx;
        ColorMap = colorMap;
        ColorMapReversed = colorMapReversed;
        ScalarMin = scalarMin;
        ScalarMax = scalarMax;
    }

    public static PlotLineSeriesStyle2D Default =>
        new(new PlotColor2D(0.2f, 0.55f, 1));
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotScatterSeriesStyle2D
{
    public readonly PlotColor2D Color;
    public readonly float DiameterPx;

    public PlotScatterSeriesStyle2D(
        PlotColor2D color,
        float diameterPx = 4)
    {
        Color = color;
        DiameterPx = diameterPx;
    }

    public static PlotScatterSeriesStyle2D Default =>
        new(new PlotColor2D(1, 0.45f, 0.15f));
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotSeriesSnapshot2D
{
    public readonly PlotProjectionHandle2D Projection;
    public readonly nuint PointCount;
    [MarshalAs(UnmanagedType.I1)]
    public readonly bool HasScalar;
    public readonly ulong Revision;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotNearestPoint2D
{
    public readonly nuint Index;
    public readonly double DataX;
    public readonly double DataY;
    public readonly float PixelX;
    public readonly float PixelY;
    public readonly float DistancePx;
}

public sealed class PlotLineSeriesItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "tcplot.PlotLineSeriesItem2D";

    private PlotLineSeriesItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static PlotLineSeriesItemRef2D Create(
        TcVisualScene2D scene,
        PlotProjectionRef2D projection,
        double[] x,
        double[] y,
        double[]? scalar = null,
        PlotLineSeriesStyle2D? style = null,
        GraphicItemRef2D? parent = null)
    {
        ValidateSeriesArguments(scene, projection, x, y, scalar);
        var handle = RetainedPlotNative.LineCreate(
            scene.NativeHandle, projection.Handle, x, y, scalar,
            (nuint)x.Length, style ?? PlotLineSeriesStyle2D.Default);
        var result = new PlotLineSeriesItemRef2D(
            scene.NativeHandle,
            RetainedPlotNative.RequireHandle(handle));
        AdoptParentOrRollback(result, parent);
        return result;
    }

    public PlotProjectionRef2D Projection
    {
        get => PlotProjectionRef2D.Borrow(Snapshot.Projection);
        set
        {
            if (value is null)
                throw new ArgumentNullException(nameof(value));
            value.ThrowIfStale();
            Require(RetainedPlotNative.LineSetProjection(
                Scene, Handle, value.Handle));
        }
    }

    public PlotLineSeriesStyle2D Style
    {
        get
        {
            Require(RetainedPlotNative.LineSnapshot(
                Scene, Handle, out _, out var style));
            return style;
        }
        set => Require(RetainedPlotNative.LineSetStyle(
            Scene, Handle, value));
    }

    public PlotSeriesSnapshot2D Snapshot
    {
        get
        {
            Require(RetainedPlotNative.LineSnapshot(
                Scene, Handle, out var snapshot, out _));
            return snapshot;
        }
    }

    public void SetData(double[] x, double[] y, double[]? scalar = null)
    {
        ValidateArrays(x, y, scalar);
        Require(RetainedPlotNative.LineSetData(
            Scene, Handle, x, y, scalar, (nuint)x.Length));
    }

    public void Append(double[] x, double[] y, double[]? scalar = null)
    {
        ValidateArrays(x, y, scalar);
        Require(RetainedPlotNative.LineAppend(
            Scene, Handle, x, y, scalar, (nuint)x.Length));
    }

    public (double[] X, double[] Y, double[]? Scalar) CopyData()
    {
        var snapshot = Snapshot;
        var count = checked((int)snapshot.PointCount);
        var x = new double[count];
        var y = new double[count];
        var scalar = snapshot.HasScalar ? new double[count] : null;
        var copied = RetainedPlotNative.LineCopyData(
            Scene, Handle, x, y, scalar, snapshot.PointCount);
        if (copied != snapshot.PointCount)
            throw new InvalidOperationException(
                "Failed to copy line series data.");
        return (x, y, scalar);
    }

    public bool TryNearest(
        float pixelX,
        float pixelY,
        float maxDistancePx,
        out PlotNearestPoint2D point) =>
        RetainedPlotNative.LineNearest(
            Scene, Handle, pixelX, pixelY, maxDistancePx, out point);

    public static PlotLineSeriesItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new PlotLineSeriesItemRef2D(item.Scene, item.Handle);
    }

    private static void ValidateSeriesArguments(
        TcVisualScene2D scene,
        PlotProjectionRef2D projection,
        double[] x,
        double[] y,
        double[]? scalar)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        scene.ThrowIfDisposed();
        if (projection is null)
            throw new ArgumentNullException(nameof(projection));
        projection.ThrowIfStale();
        ValidateArrays(x, y, scalar);
    }

    private static void ValidateArrays(
        double[] x,
        double[] y,
        double[]? scalar)
    {
        if (x is null)
            throw new ArgumentNullException(nameof(x));
        if (y is null)
            throw new ArgumentNullException(nameof(y));
        if (x.Length != y.Length ||
            (scalar is not null && scalar.Length != x.Length))
            throw new ArgumentException(
                "Series arrays must have equal lengths.");
    }

    internal static void AdoptParentOrRollback(
        GraphicItemRef2D item,
        GraphicItemRef2D? parent)
    {
        if (parent is null)
            return;
        if (item.SetParent(parent))
            return;
        item.Destroy();
        throw new InvalidOperationException(
            "The requested plot item parent was rejected.");
    }
}

public sealed class PlotScatterSeriesItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "tcplot.PlotScatterSeriesItem2D";

    private PlotScatterSeriesItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static PlotScatterSeriesItemRef2D Create(
        TcVisualScene2D scene,
        PlotProjectionRef2D projection,
        double[] x,
        double[] y,
        PlotScatterSeriesStyle2D? style = null,
        GraphicItemRef2D? parent = null)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        scene.ThrowIfDisposed();
        if (projection is null)
            throw new ArgumentNullException(nameof(projection));
        projection.ThrowIfStale();
        if (x is null || y is null)
            throw new ArgumentNullException(
                x is null ? nameof(x) : nameof(y));
        if (x.Length != y.Length)
            throw new ArgumentException(
                "Series arrays must have equal lengths.");
        var handle = RetainedPlotNative.ScatterCreate(
            scene.NativeHandle, projection.Handle, x, y,
            (nuint)x.Length, style ?? PlotScatterSeriesStyle2D.Default);
        var result = new PlotScatterSeriesItemRef2D(
            scene.NativeHandle,
            RetainedPlotNative.RequireHandle(handle));
        PlotLineSeriesItemRef2D.AdoptParentOrRollback(result, parent);
        return result;
    }

    public PlotProjectionRef2D Projection
    {
        get => PlotProjectionRef2D.Borrow(Snapshot.Projection);
        set
        {
            if (value is null)
                throw new ArgumentNullException(nameof(value));
            value.ThrowIfStale();
            Require(RetainedPlotNative.ScatterSetProjection(
                Scene, Handle, value.Handle));
        }
    }

    public PlotScatterSeriesStyle2D Style
    {
        get
        {
            Require(RetainedPlotNative.ScatterSnapshot(
                Scene, Handle, out _, out var style));
            return style;
        }
        set => Require(RetainedPlotNative.ScatterSetStyle(
            Scene, Handle, value));
    }

    public PlotSeriesSnapshot2D Snapshot
    {
        get
        {
            Require(RetainedPlotNative.ScatterSnapshot(
                Scene, Handle, out var snapshot, out _));
            return snapshot;
        }
    }

    public void SetData(double[] x, double[] y)
    {
        if (x is null || y is null)
            throw new ArgumentNullException(
                x is null ? nameof(x) : nameof(y));
        if (x.Length != y.Length)
            throw new ArgumentException(
                "Series arrays must have equal lengths.");
        Require(RetainedPlotNative.ScatterSetData(
            Scene, Handle, x, y, (nuint)x.Length));
    }

    public (double[] X, double[] Y) CopyData()
    {
        var count = Snapshot.PointCount;
        var x = new double[checked((int)count)];
        var y = new double[checked((int)count)];
        if (RetainedPlotNative.ScatterCopyData(
                Scene, Handle, x, y, count) != count)
            throw new InvalidOperationException(
                "Failed to copy scatter series data.");
        return (x, y);
    }

    public bool TryNearest(
        float pixelX,
        float pixelY,
        float maxDistancePx,
        out PlotNearestPoint2D point) =>
        RetainedPlotNative.ScatterNearest(
            Scene, Handle, pixelX, pixelY, maxDistancePx, out point);

    public static PlotScatterSeriesItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new PlotScatterSeriesItemRef2D(item.Scene, item.Handle);
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotGridStyle2D
{
    public readonly float R;
    public readonly float G;
    public readonly float B;
    public readonly float A;
    public readonly float WidthPx;

    public PlotGridStyle2D(
        float r,
        float g,
        float b,
        float a = 1,
        float widthPx = 1)
    {
        R = r;
        G = g;
        B = b;
        A = a;
        WidthPx = widthPx;
    }

    public static PlotGridStyle2D Default =>
        new(0.3f, 0.3f, 0.3f, 1, 1);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotGridSnapshot2D
{
    public readonly PlotProjectionHandle2D Projection;
    public readonly PlotGridStyle2D Style;
    public readonly nuint XTickCount;
    public readonly nuint YTickCount;
    public readonly ulong Revision;
}

public sealed class PlotGridItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "tcplot.PlotGridItem2D";

    private PlotGridItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static PlotGridItemRef2D Create(
        TcVisualScene2D scene,
        PlotProjectionRef2D projection,
        double[]? xTicks = null,
        double[]? yTicks = null,
        PlotGridStyle2D? style = null,
        GraphicItemRef2D? parent = null)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        scene.ThrowIfDisposed();
        if (projection is null)
            throw new ArgumentNullException(nameof(projection));
        projection.ThrowIfStale();
        xTicks ??= Array.Empty<double>();
        yTicks ??= Array.Empty<double>();
        var handle = RetainedPlotNative.GridCreate(
            scene.NativeHandle, projection.Handle,
            xTicks, (nuint)xTicks.Length, yTicks, (nuint)yTicks.Length,
            style ?? PlotGridStyle2D.Default);
        var result = new PlotGridItemRef2D(
            scene.NativeHandle,
            RetainedPlotNative.RequireHandle(handle));
        PlotLineSeriesItemRef2D.AdoptParentOrRollback(result, parent);
        return result;
    }

    public PlotGridSnapshot2D Snapshot
    {
        get
        {
            Require(RetainedPlotNative.GridSnapshot(
                Scene, Handle, out var snapshot));
            return snapshot;
        }
    }

    public PlotProjectionRef2D Projection
    {
        get => PlotProjectionRef2D.Borrow(Snapshot.Projection);
        set
        {
            if (value is null)
                throw new ArgumentNullException(nameof(value));
            value.ThrowIfStale();
            Require(RetainedPlotNative.GridSetProjection(
                Scene, Handle, value.Handle));
        }
    }

    public PlotGridStyle2D Style
    {
        get => Snapshot.Style;
        set => Require(RetainedPlotNative.GridSetStyle(
            Scene, Handle, value));
    }

    public void SetTicks(double[] xTicks, double[] yTicks)
    {
        if (xTicks is null)
            throw new ArgumentNullException(nameof(xTicks));
        if (yTicks is null)
            throw new ArgumentNullException(nameof(yTicks));
        Require(RetainedPlotNative.GridSetTicks(
            Scene, Handle, xTicks, (nuint)xTicks.Length,
            yTicks, (nuint)yTicks.Length));
    }

    public (double[] X, double[] Y) CopyTicks()
    {
        var snapshot = Snapshot;
        var x = new double[checked((int)snapshot.XTickCount)];
        var y = new double[checked((int)snapshot.YTickCount)];
        var total = snapshot.XTickCount + snapshot.YTickCount;
        if (RetainedPlotNative.GridCopyTicks(
                Scene, Handle, x, snapshot.XTickCount,
                y, snapshot.YTickCount) != total)
            throw new InvalidOperationException(
                "Failed to copy plot grid ticks.");
        return (x, y);
    }

    public static PlotGridItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new PlotGridItemRef2D(item.Scene, item.Handle);
    }
}

public readonly struct PlotAxisTick2D
{
    public double Value { get; }
    public string Label { get; }

    public PlotAxisTick2D(double value, string label)
    {
        Value = value;
        Label = label;
    }
}

public readonly struct PlotTextMetrics2D
{
    public readonly float Width;
    public readonly float Height;
    public readonly float Ascent;
    public readonly float Descent;
    public readonly float LineHeight;

    public PlotTextMetrics2D(
        float width,
        float height,
        float ascent,
        float descent,
        float lineHeight)
    {
        Width = width;
        Height = height;
        Ascent = ascent;
        Descent = descent;
        LineHeight = lineHeight;
    }
}

public static class RetainedPlotLayout2D
{
    public static PlotRange2D FitRange(
        PlotRange2D bounds,
        double paddingFraction = 0.05)
    {
        if (!RetainedPlotNative.FitRange(
                bounds, paddingFraction, out var result))
            throw new ArgumentException(
                "Plot range or padding is invalid.");
        return result;
    }

    public static PlotAxisTick2D[] MakeAxisTicks(
        double minimum,
        double maximum,
        float extentPx,
        float spacingLogicalPx,
        float pixelScale = 1,
        int minimumTickCount = 3)
    {
        var desc = new RetainedPlotNative.AxisTicksDescriptor(
            minimum, maximum, extentPx, spacingLogicalPx,
            pixelScale, minimumTickCount);
        var count = RetainedPlotNative.AxisTicksCopy(
            ref desc, null, 0);
        if (count == 0)
            throw new ArgumentException(
                "Axis tick input is invalid.");
        var values = new double[checked((int)count)];
        if (RetainedPlotNative.AxisTicksCopy(
                ref desc, values, count) != count)
            throw new InvalidOperationException(
                "Failed to copy native axis ticks.");
        var result = new PlotAxisTick2D[values.Length];
        for (var index = 0; index < values.Length; ++index)
            result[index] = new PlotAxisTick2D(
                values[index],
                RetainedPlotNative.FormatTick(values[index]));
        return result;
    }

    public static PlotTextMetrics2D MeasureText(
        GpuHost host,
        string text,
        float fontSizeLogicalPx,
        float pixelScale = 1)
    {
        if (host is null)
            throw new ArgumentNullException(nameof(host));
        if (!host.measure_plot_text_2d(
                text, fontSizeLogicalPx, pixelScale,
                out var width, out var height, out var ascent,
                out var descent, out var lineHeight))
            throw new InvalidOperationException(
                "Native plot text measurement failed.");
        return new PlotTextMetrics2D(
            width, height, ascent, descent, lineHeight);
    }
}

internal static class RetainedPlotNative
{
    private const string Dll = "tcplot";

    [StructLayout(LayoutKind.Sequential)]
    internal readonly struct AxisTicksDescriptor
    {
        internal readonly double Minimum;
        internal readonly double Maximum;
        internal readonly float ExtentPx;
        internal readonly float SpacingLogicalPx;
        internal readonly float PixelScale;
        internal readonly int MinimumTickCount;

        internal AxisTicksDescriptor(
            double minimum,
            double maximum,
            float extentPx,
            float spacingLogicalPx,
            float pixelScale,
            int minimumTickCount)
        {
            Minimum = minimum;
            Maximum = maximum;
            ExtentPx = extentPx;
            SpacingLogicalPx = spacingLogicalPx;
            PixelScale = pixelScale;
            MinimumTickCount = minimumTickCount;
        }
    }

    internal static GraphicItemHandle2D RequireHandle(
        GraphicItemHandle2D handle) =>
        handle.IsValid
            ? handle
            : throw new InvalidOperationException(
                "Native retained plot item creation failed.");

    [DllImport(Dll, EntryPoint = "tc_plot_projection2d_create")]
    internal static extern PlotProjectionHandle2D ProjectionCreate(
        VisualSceneNativeHandle scene,
        ref PlotProjectionDescriptor2D descriptor);

    [DllImport(Dll, EntryPoint = "tc_plot_projection2d_destroy")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ProjectionDestroy(
        PlotProjectionHandle2D projection);

    [DllImport(Dll, EntryPoint = "tc_plot_projection2d_is_valid")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ProjectionIsValid(
        PlotProjectionHandle2D projection);

    [DllImport(Dll, EntryPoint = "tc_plot_projection2d_update")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ProjectionUpdate(
        PlotProjectionHandle2D projection,
        ref PlotProjectionDescriptor2D descriptor);

    [DllImport(Dll, EntryPoint = "tc_plot_projection2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ProjectionSnapshot(
        PlotProjectionHandle2D projection,
        out PlotProjectionState2D state);

    [DllImport(
        Dll,
        EntryPoint = "tc_plot_projection_state2d_data_to_visual")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool DataToVisual(
        ref PlotProjectionState2D state,
        PlotPoint2D point,
        out PlotVisualPoint2D result);

    [DllImport(
        Dll,
        EntryPoint = "tc_plot_projection_state2d_visual_to_data")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool VisualToData(
        ref PlotProjectionState2D state,
        PlotVisualPoint2D point,
        out PlotPoint2D result);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_create")]
    internal static extern GraphicItemHandle2D LineCreate(
        VisualSceneNativeHandle scene,
        PlotProjectionHandle2D projection,
        [In] double[] x,
        [In] double[] y,
        [In] double[]? scalar,
        nuint pointCount,
        PlotLineSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_create")]
    internal static extern GraphicItemHandle2D ScatterCreate(
        VisualSceneNativeHandle scene,
        PlotProjectionHandle2D projection,
        [In] double[] x,
        [In] double[] y,
        nuint pointCount,
        PlotScatterSeriesStyle2D style);

    [DllImport(
        Dll,
        EntryPoint = "tc_plot_line_series_item2d_set_projection")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineSetProjection(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotProjectionHandle2D projection);

    [DllImport(
        Dll,
        EntryPoint = "tc_plot_scatter_series_item2d_set_projection")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ScatterSetProjection(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotProjectionHandle2D projection);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_set_data")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineSetData(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [In] double[] x,
        [In] double[] y,
        [In] double[]? scalar,
        nuint pointCount);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_append")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineAppend(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [In] double[] x,
        [In] double[] y,
        [In] double[]? scalar,
        nuint pointCount);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_set_data")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ScatterSetData(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [In] double[] x,
        [In] double[] y,
        nuint pointCount);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_set_style")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineSetStyle(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotLineSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_set_style")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ScatterSetStyle(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotScatterSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineSnapshot(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out PlotSeriesSnapshot2D snapshot,
        out PlotLineSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ScatterSnapshot(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out PlotSeriesSnapshot2D snapshot,
        out PlotScatterSeriesStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_copy_data")]
    internal static extern nuint LineCopyData(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [Out] double[] x,
        [Out] double[] y,
        [Out] double[]? scalar,
        nuint capacity);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_copy_data")]
    internal static extern nuint ScatterCopyData(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [Out] double[] x,
        [Out] double[] y,
        nuint capacity);

    [DllImport(Dll, EntryPoint = "tc_plot_line_series_item2d_nearest")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool LineNearest(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        float pixelX,
        float pixelY,
        float maxDistancePx,
        out PlotNearestPoint2D point);

    [DllImport(Dll, EntryPoint = "tc_plot_scatter_series_item2d_nearest")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ScatterNearest(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        float pixelX,
        float pixelY,
        float maxDistancePx,
        out PlotNearestPoint2D point);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_create")]
    internal static extern GraphicItemHandle2D GridCreate(
        VisualSceneNativeHandle scene,
        PlotProjectionHandle2D projection,
        [In] double[] xTicks,
        nuint xTickCount,
        [In] double[] yTicks,
        nuint yTickCount,
        PlotGridStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_set_projection")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GridSetProjection(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotProjectionHandle2D projection);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_set_ticks")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GridSetTicks(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [In] double[] xTicks,
        nuint xTickCount,
        [In] double[] yTicks,
        nuint yTickCount);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_set_style")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GridSetStyle(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        PlotGridStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GridSnapshot(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out PlotGridSnapshot2D snapshot);

    [DllImport(Dll, EntryPoint = "tc_plot_grid_item2d_copy_ticks")]
    internal static extern nuint GridCopyTicks(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [Out] double[] xTicks,
        nuint xCapacity,
        [Out] double[] yTicks,
        nuint yCapacity);

    [DllImport(Dll, EntryPoint = "tc_plot_fit_range2d")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool FitRange(
        PlotRange2D bounds,
        double paddingFraction,
        out PlotRange2D result);

    [DllImport(Dll, EntryPoint = "tc_plot_axis_ticks2d_copy")]
    internal static extern nuint AxisTicksCopy(
        ref AxisTicksDescriptor descriptor,
        [Out] double[]? values,
        nuint capacity);

    [DllImport(Dll, EntryPoint = "tc_plot_format_tick2d")]
    private static extern nuint FormatTickNative(
        double value,
        [Out] byte[]? utf8,
        nuint capacity);

    internal static string FormatTick(double value)
    {
        var required = FormatTickNative(value, null, 0);
        if (required == 0)
            throw new InvalidOperationException(
                "Native tick formatting failed.");
        var utf8 = new byte[checked((int)required)];
        if (FormatTickNative(value, utf8, required) != required)
            throw new InvalidOperationException(
                "Native tick formatting failed.");
        return Encoding.UTF8.GetString(utf8, 0, utf8.Length - 1);
    }
}
