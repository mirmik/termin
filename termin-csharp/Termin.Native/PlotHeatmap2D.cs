using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

public enum PlotHeatmapInterpolation2D
{
    Nearest = 0,
    Bilinear = 1,
}

/// <summary>Palette and scalar normalization for a uniformly sampled heatmap.</summary>
[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotHeatmapStyle2D
{
    public readonly PlotColorMap2D ColorMap;
    [MarshalAs(UnmanagedType.I1)]
    public readonly bool ColorMapReversed;
    [MarshalAs(UnmanagedType.I1)]
    public readonly bool AutoRange;
    public readonly double ScalarMin;
    public readonly double ScalarMax;
    public readonly PlotHeatmapInterpolation2D Interpolation;

    public PlotHeatmapStyle2D() : this(PlotColorMap2D.Viridis) {}

    public PlotHeatmapStyle2D(
        PlotColorMap2D colorMap = PlotColorMap2D.Viridis,
        bool colorMapReversed = false,
        bool autoRange = true,
        double scalarMin = 0,
        double scalarMax = 1,
        PlotHeatmapInterpolation2D interpolation = PlotHeatmapInterpolation2D.Nearest)
    {
        ColorMap = colorMap;
        ColorMapReversed = colorMapReversed;
        AutoRange = autoRange;
        ScalarMin = scalarMin;
        ScalarMax = scalarMax;
        Interpolation = interpolation;
    }

    public static PlotHeatmapStyle2D Default => new(PlotColorMap2D.Viridis);
}

/// <summary>Detached grid state; ScalarMin/ScalarMax are the effective color range.</summary>
[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotHeatmapSnapshot2D
{
    public readonly PlotProjectionHandle2D Projection;
    public readonly uint Rows;
    public readonly uint Columns;
    public readonly PlotRange2D Bounds;
    public readonly double ScalarMin;
    public readonly double ScalarMax;
    public readonly ulong Revision;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotHeatmapSample2D
{
    public readonly uint Row;
    public readonly uint Column;
    public readonly double Value;
}

/// <summary>
/// Native retained heatmap. Bounds are outer cell edges; row zero is at YMin,
/// column zero at XMin. Values are copied in row-major order. NaN cells are
/// transparent. Rendering defaults to nearest cells; bilinear interpolation
/// can be enabled through Style without changing the stored values.
/// </summary>
public sealed class PlotHeatmapItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "tcplot.PlotHeatmapItem2D";

    private PlotHeatmapItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static PlotHeatmapItemRef2D Create(
        TcVisualScene2D scene,
        PlotProjectionRef2D projection,
        double[] values,
        uint rows,
        uint columns,
        PlotRange2D bounds,
        PlotHeatmapStyle2D? style = null,
        GraphicItemRef2D? parent = null)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        scene.ThrowIfDisposed();
        if (projection is null)
            throw new ArgumentNullException(nameof(projection));
        projection.ThrowIfStale();
        ValidateData(values, rows, columns);
        var handle = PlotHeatmapNative.Create(
            scene.NativeHandle, projection.Handle, values, (nuint)values.Length,
            rows, columns, bounds, style ?? PlotHeatmapStyle2D.Default);
        var item = new PlotHeatmapItemRef2D(
            scene.NativeHandle, RetainedPlotNative.RequireHandle(handle));
        PlotLineSeriesItemRef2D.AdoptParentOrRollback(item, parent);
        return item;
    }

    public PlotProjectionRef2D Projection
    {
        get => PlotProjectionRef2D.Borrow(Snapshot.Projection);
        set
        {
            if (value is null)
                throw new ArgumentNullException(nameof(value));
            value.ThrowIfStale();
            Require(PlotHeatmapNative.SetProjection(Scene, Handle, value.Handle));
        }
    }

    public PlotHeatmapStyle2D Style
    {
        get
        {
            Require(PlotHeatmapNative.Snapshot(Scene, Handle, out _, out var style));
            return style;
        }
        set => Require(PlotHeatmapNative.SetStyle(Scene, Handle, value));
    }

    public PlotHeatmapSnapshot2D Snapshot
    {
        get
        {
            Require(PlotHeatmapNative.Snapshot(Scene, Handle, out var snapshot, out _));
            return snapshot;
        }
    }

    public void SetData(double[] values, uint rows, uint columns, PlotRange2D bounds)
    {
        ValidateData(values, rows, columns);
        Require(PlotHeatmapNative.SetData(
            Scene, Handle, values, (nuint)values.Length, rows, columns, bounds));
    }

    public double[] CopyData()
    {
        var snapshot = Snapshot;
        var count = checked((int)((ulong)snapshot.Rows * snapshot.Columns));
        var values = new double[count];
        if (PlotHeatmapNative.CopyData(Scene, Handle, values, (nuint)count) != (nuint)count)
            throw new InvalidOperationException("Failed to copy native heatmap data.");
        return values;
    }

    /// <summary>
    /// Samples an original cell in data coordinates, independently of the visual
    /// interpolation mode. Maximum outer edges belong to the
    /// last cell. Returns false outside the grid; transparent cells return NaN.
    /// </summary>
    public bool TrySample(double dataX, double dataY, out PlotHeatmapSample2D sample)
    {
        ThrowIfStale();
        return PlotHeatmapNative.Sample(Scene, Handle, dataX, dataY, out sample);
    }

    public static PlotHeatmapItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new PlotHeatmapItemRef2D(item.Scene, item.Handle);
    }

    internal static void ValidateData(double[] values, uint rows, uint columns)
    {
        if (values is null)
            throw new ArgumentNullException(nameof(values));
        if (rows == 0 || columns == 0 || (ulong)rows * columns != (ulong)values.LongLength)
            throw new ArgumentException("Heatmap dimensions must be positive and match the value count.");
    }
}

internal static class PlotHeatmapNative
{
    private const string Dll = "tcplot";

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_create")]
    internal static extern GraphicItemHandle2D Create(
        VisualSceneNativeHandle scene, PlotProjectionHandle2D projection,
        double[] values, nuint count, uint rows, uint columns,
        PlotRange2D bounds, PlotHeatmapStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_set_projection")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetProjection(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item,
        PlotProjectionHandle2D projection);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_set_data")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetData(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item,
        double[] values, nuint count, uint rows, uint columns, PlotRange2D bounds);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_set_style")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetStyle(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item, PlotHeatmapStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool Snapshot(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item,
        out PlotHeatmapSnapshot2D snapshot, out PlotHeatmapStyle2D style);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_copy_data")]
    internal static extern nuint CopyData(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item,
        [Out] double[] values, nuint capacity);

    [DllImport(Dll, EntryPoint = "tc_plot_heatmap_item2d_sample")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool Sample(
        VisualSceneNativeHandle scene, GraphicItemHandle2D item,
        double dataX, double dataY, out PlotHeatmapSample2D sample);
}
