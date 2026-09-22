using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

public enum PlotCoordinateSystem3D
{
    Cartesian,
    Spherical,
}

/// <summary>A numeric display axis: X/Y/Z for Cartesian charts, Radius for spherical charts.</summary>
public enum PlotAxis3D
{
    X = 0,
    Y = 1,
    Z = 2,
    Radius = 3,
}

public enum PlotItemKind3D : uint
{
    Invalid = 0,
    Surface = 1,
    Scatter = 2,
    Grid = 3,
}

public enum PlotColorMap3D : uint
{
    Jet = 0,
    Viridis = 1,
    Plasma = 2,
    Grayscale = 3,
    CoolWarm = 4,
    Solid = 5,
}

/// <summary>
/// Defines the orientation of a spherical chart's angular coordinates.
/// The polar axis is the direction of polar angle zero. The zero-longitude
/// direction is projected onto the plane normal to that axis and normalized.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public readonly struct SphericalCoordinateFrame3D
{
    public readonly double PolarAxisX;
    public readonly double PolarAxisY;
    public readonly double PolarAxisZ;
    public readonly double ZeroLongitudeX;
    public readonly double ZeroLongitudeY;
    public readonly double ZeroLongitudeZ;

    public SphericalCoordinateFrame3D(
        double polarAxisX,
        double polarAxisY,
        double polarAxisZ,
        double zeroLongitudeX,
        double zeroLongitudeY,
        double zeroLongitudeZ)
    {
        PolarAxisX = polarAxisX;
        PolarAxisY = polarAxisY;
        PolarAxisZ = polarAxisZ;
        ZeroLongitudeX = zeroLongitudeX;
        ZeroLongitudeY = zeroLongitudeY;
        ZeroLongitudeZ = zeroLongitudeZ;
    }

    public static SphericalCoordinateFrame3D Standard => new(
        polarAxisX: 0,
        polarAxisY: 0,
        polarAxisZ: 1,
        zeroLongitudeX: 1,
        zeroLongitudeY: 0,
        zeroLongitudeZ: 0);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotItemHandle3D : IEquatable<PlotItemHandle3D>
{
    public readonly ulong SceneId;
    public readonly uint Index;
    public readonly uint Generation;

    public bool IsValid => SceneId != 0 && Generation != 0;

    public bool Equals(PlotItemHandle3D other) =>
        SceneId == other.SceneId &&
        Index == other.Index &&
        Generation == other.Generation;

    public override bool Equals(object? obj) =>
        obj is PlotItemHandle3D other && Equals(other);

    public override int GetHashCode() =>
        HashCode.Combine(SceneId, Index, Generation);

    public static bool operator ==(
        PlotItemHandle3D left,
        PlotItemHandle3D right) => left.Equals(right);

    public static bool operator !=(
        PlotItemHandle3D left,
        PlotItemHandle3D right) => !left.Equals(right);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct SurfaceItemStyle3D
{
    public SurfaceItemStyle3D() : this(colorR: 1) {}

    public readonly float ColorR;
    public readonly float ColorG;
    public readonly float ColorB;
    public readonly float ColorA;
    public readonly PlotColorMap3D ColorMap;
    private readonly uint _colorMapReversed;
    private readonly uint _wireframe;
    private readonly uint _surfaceGridVisible;
    public readonly uint SurfaceGridRowStep;
    public readonly uint SurfaceGridColumnStep;
    public readonly float SurfaceGridWidthPx;
    public readonly float SurfaceGridR;
    public readonly float SurfaceGridG;
    public readonly float SurfaceGridB;
    public readonly float SurfaceGridA;

    public SurfaceItemStyle3D(
        float colorR = 1,
        float colorG = 1,
        float colorB = 1,
        float colorA = 1,
        PlotColorMap3D colorMap = PlotColorMap3D.Viridis,
        bool colorMapReversed = false,
        bool wireframe = false,
        bool surfaceGridVisible = false,
        uint surfaceGridRowStep = 8,
        uint surfaceGridColumnStep = 8,
        float surfaceGridWidthPx = 1.25f,
        float surfaceGridR = 0.04f,
        float surfaceGridG = 0.04f,
        float surfaceGridB = 0.04f,
        float surfaceGridA = 1)
    {
        ColorR = colorR;
        ColorG = colorG;
        ColorB = colorB;
        ColorA = colorA;
        ColorMap = colorMap;
        _colorMapReversed = colorMapReversed ? 1u : 0u;
        _wireframe = wireframe ? 1u : 0u;
        _surfaceGridVisible = surfaceGridVisible ? 1u : 0u;
        SurfaceGridRowStep = surfaceGridRowStep;
        SurfaceGridColumnStep = surfaceGridColumnStep;
        SurfaceGridWidthPx = surfaceGridWidthPx;
        SurfaceGridR = surfaceGridR;
        SurfaceGridG = surfaceGridG;
        SurfaceGridB = surfaceGridB;
        SurfaceGridA = surfaceGridA;
    }

    public bool ColorMapReversed => _colorMapReversed != 0;
    public bool Wireframe => _wireframe != 0;
    public bool SurfaceGridVisible => _surfaceGridVisible != 0;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct ScatterItemStyle3D
{
    public ScatterItemStyle3D() : this(colorR: 1) {}

    public readonly float ColorR;
    public readonly float ColorG;
    public readonly float ColorB;
    public readonly float ColorA;
    public readonly float Size;

    public ScatterItemStyle3D(
        float colorR = 1,
        float colorG = 0.35f,
        float colorB = 0.15f,
        float colorA = 1,
        float size = 4)
    {
        ColorR = colorR;
        ColorG = colorG;
        ColorB = colorB;
        ColorA = colorA;
        Size = size;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct GridItemStyle3D
{
    public GridItemStyle3D() : this(labelsVisible: true) {}

    public readonly float GridR;
    public readonly float GridG;
    public readonly float GridB;
    public readonly float GridA;
    public readonly float XAxisR;
    public readonly float XAxisG;
    public readonly float XAxisB;
    public readonly float YAxisR;
    public readonly float YAxisG;
    public readonly float YAxisB;
    public readonly float ZAxisR;
    public readonly float ZAxisG;
    public readonly float ZAxisB;
    private readonly uint _labelsVisible;

    public GridItemStyle3D(
        float gridR = 0.42f,
        float gridG = 0.45f,
        float gridB = 0.52f,
        float gridA = 1,
        float xAxisR = 0.95f,
        float xAxisG = 0.24f,
        float xAxisB = 0.22f,
        float yAxisR = 0.25f,
        float yAxisG = 0.86f,
        float yAxisB = 0.38f,
        float zAxisR = 0.28f,
        float zAxisG = 0.48f,
        float zAxisB = 1,
        bool labelsVisible = true)
    {
        GridR = gridR;
        GridG = gridG;
        GridB = gridB;
        GridA = gridA;
        XAxisR = xAxisR;
        XAxisG = xAxisG;
        XAxisB = xAxisB;
        YAxisR = yAxisR;
        YAxisG = yAxisG;
        YAxisB = yAxisB;
        ZAxisR = zAxisR;
        ZAxisG = zAxisG;
        ZAxisB = zAxisB;
        _labelsVisible = labelsVisible ? 1u : 0u;
    }

    public bool LabelsVisible => _labelsVisible != 0;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct ColorBarStyle3D
{
    public ColorBarStyle3D() : this(tickCount: 5) {}

    public readonly uint TickCount;
    public readonly float WidthPx;
    public readonly float HeightRatio;
    public readonly float MarginRightPx;
    public readonly float TextGapPx;
    public readonly float TextSizePx;
    public readonly float LabelR;
    public readonly float LabelG;
    public readonly float LabelB;
    public readonly float LabelA;
    public readonly float BorderR;
    public readonly float BorderG;
    public readonly float BorderB;
    public readonly float BorderA;

    public ColorBarStyle3D(
        uint tickCount = 5,
        float widthPx = 18,
        float heightRatio = 0.62f,
        float marginRightPx = 18,
        float textGapPx = 8,
        float textSizePx = 13,
        float labelR = 0.8f,
        float labelG = 0.8f,
        float labelB = 0.8f,
        float labelA = 1,
        float borderR = 0.42f,
        float borderG = 0.45f,
        float borderB = 0.52f,
        float borderA = 1)
    {
        TickCount = tickCount;
        WidthPx = widthPx;
        HeightRatio = heightRatio;
        MarginRightPx = marginRightPx;
        TextGapPx = textGapPx;
        TextSizePx = textSizePx;
        LabelR = labelR;
        LabelG = labelG;
        LabelB = labelB;
        LabelA = labelA;
        BorderR = borderR;
        BorderG = borderG;
        BorderB = borderB;
        BorderA = borderA;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct PlotItemSnapshot3D
{
    public readonly PlotItemKind3D Kind;
    public readonly ulong GeometryRevision;
    public readonly ulong StyleRevision;
    public readonly ulong GpuRevision;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct OrbitCameraState3D
{
    public readonly double TargetX;
    public readonly double TargetY;
    public readonly double TargetZ;
    public readonly double Distance;
    public readonly double Azimuth;
    public readonly double Elevation;
    public readonly double FieldOfViewY;
    public readonly double NearClip;
    public readonly double FarClip;

    public OrbitCameraState3D(
        double targetX,
        double targetY,
        double targetZ,
        double distance,
        double azimuth,
        double elevation,
        double fieldOfViewY,
        double nearClip,
        double farClip)
    {
        TargetX = targetX;
        TargetY = targetY;
        TargetZ = targetZ;
        Distance = distance;
        Azimuth = azimuth;
        Elevation = elevation;
        FieldOfViewY = fieldOfViewY;
        NearClip = nearClip;
        FarClip = farClip;
    }
}

public abstract class PlotItemRef3D
{
    private readonly RetainedChart3D _chart;

    internal PlotItemRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle)
    {
        _chart = chart;
        Handle = handle;
    }

    internal RetainedChart3D Chart => _chart;
    public PlotItemHandle3D Handle { get; }
    public bool IsValid =>
        !_chart.IsDisposed &&
        RetainedChart3DNative.ItemIsValid(_chart.NativeHandle, Handle) != 0;

    public PlotItemSnapshot3D Snapshot
    {
        get
        {
            ThrowIfStale();
            if (RetainedChart3DNative.ItemSnapshot(
                    _chart.NativeHandle, Handle, out var snapshot) == 0)
                throw new InvalidOperationException(
                    "Failed to snapshot retained 3D item.");
            return snapshot;
        }
    }

    public bool Destroy()
    {
        ThrowIfStale();
        return RetainedChart3DNative.DestroyItem(
            _chart.NativeHandle, Handle) != 0;
    }

    internal void ThrowIfStale()
    {
        if (!IsValid)
            throw new InvalidOperationException(
                "Retained 3D item is stale or its chart was destroyed.");
    }
}

public abstract class SurfaceRef3D : PlotItemRef3D
{
    internal SurfaceRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle) : base(chart, handle) {}

    public SurfaceItemStyle3D Style
    {
        get
        {
            ThrowIfStale();
            if (RetainedChart3DNative.SurfaceGetStyle(
                    Chart.NativeHandle, Handle, out var style) == 0)
                throw new InvalidOperationException(
                    "Failed to read retained surface style.");
            return style;
        }
        set
        {
            ThrowIfStale();
            if (RetainedChart3DNative.SurfaceSetStyle(
                    Chart.NativeHandle, Handle, ref value) == 0)
                throw new InvalidOperationException(
                    "Failed to update retained surface style. See native log.");
        }
    }

}

public sealed class SurfaceItemRef3D : SurfaceRef3D
{
    internal SurfaceItemRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle) : base(chart, handle) {}

    public void SetData(
        double[] x,
        double[] y,
        double[] z,
        uint rows,
        uint columns)
    {
        PlotScene3D.ValidateSurface(x, y, z, rows, columns);
        ThrowIfStale();
        if (RetainedChart3DNative.SurfaceSetData(
                Chart.NativeHandle,
                Handle,
                x,
                y,
                z,
                rows,
                columns) == 0)
            throw new InvalidOperationException(
                "Failed to update retained surface data. See native log.");
    }
}

public sealed class SphericalSurfaceItemRef3D : SurfaceRef3D
{
    private readonly int _radiusCount;

    internal SphericalSurfaceItemRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle,
        int radiusCount) : base(chart, handle)
    {
        _radiusCount = radiusCount;
    }

    /// <summary>Updates radii in row-major order without changing angles, style, handle or camera.</summary>
    public void SetRadii(double[] radii)
    {
        PlotScene3D.ValidateRadii(radii, _radiusCount);
        ThrowIfStale();
        if (RetainedChart3DNative.SphericalSurfaceSetRadii(
                Chart.NativeHandle, Handle, radii, (nuint)radii.Length) == 0)
            throw new InvalidOperationException(
                "Failed to update retained spherical radii. See native log.");
    }
}

public sealed class ScatterItemRef3D : PlotItemRef3D
{
    internal ScatterItemRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle) : base(chart, handle) {}

    public ScatterItemStyle3D Style
    {
        get
        {
            ThrowIfStale();
            if (RetainedChart3DNative.ScatterGetStyle(
                    Chart.NativeHandle, Handle, out var style) == 0)
                throw new InvalidOperationException(
                    "Failed to read retained scatter style.");
            return style;
        }
        set
        {
            ThrowIfStale();
            if (RetainedChart3DNative.ScatterSetStyle(
                    Chart.NativeHandle, Handle, ref value) == 0)
                throw new InvalidOperationException(
                    "Failed to update retained scatter style. See native log.");
        }
    }

    public void SetData(double[] x, double[] y, double[] z)
    {
        PlotScene3D.ValidateEqualArrays(x, y, z);
        if (x.Length == 0)
            throw new ArgumentException("Scatter data must not be empty.");
        ThrowIfStale();
        if (RetainedChart3DNative.ScatterSetData(
                Chart.NativeHandle,
                Handle,
                x,
                y,
                z,
                (nuint)x.Length) == 0)
            throw new InvalidOperationException(
                "Failed to update retained scatter data. See native log.");
    }
}

public sealed class GridItemRef3D : PlotItemRef3D
{
    internal GridItemRef3D(
        RetainedChart3D chart,
        PlotItemHandle3D handle) : base(chart, handle) {}

    public GridItemStyle3D Style
    {
        get
        {
            ThrowIfStale();
            if (RetainedChart3DNative.GridGetStyle(
                    Chart.NativeHandle, Handle, out var style) == 0)
                throw new InvalidOperationException(
                    "Failed to read retained grid style.");
            return style;
        }
        set
        {
            ThrowIfStale();
            if (RetainedChart3DNative.GridSetStyle(
                    Chart.NativeHandle, Handle, ref value) == 0)
                throw new InvalidOperationException(
                    "Failed to update retained grid style. See native log.");
        }
    }
}

public sealed class PlotScene3D
{
    private readonly RetainedChart3D _chart;

    internal PlotScene3D(RetainedChart3D chart)
    {
        _chart = chart;
    }

    public ulong Id
    {
        get
        {
            _chart.ThrowIfDisposed();
            return RetainedChart3DNative.SceneId(_chart.NativeHandle);
        }
    }

    public nuint Count
    {
        get
        {
            _chart.ThrowIfDisposed();
            return RetainedChart3DNative.ItemCount(_chart.NativeHandle);
        }
    }

    public SurfaceItemRef3D AddSurface(
        double[] x,
        double[] y,
        double[] z,
        uint rows,
        uint columns,
        SurfaceItemStyle3D? style = null)
    {
        ValidateSurface(x, y, z, rows, columns);
        _chart.ThrowIfDisposed();
        if (_chart.Coordinates != PlotCoordinateSystem3D.Cartesian)
            throw new InvalidOperationException(
                "Use AddSphericalSurface for a spherical chart.");
        var resolved = style ?? new SurfaceItemStyle3D();
        var handle = RetainedChart3DNative.AddSurface(
            _chart.NativeHandle, x, y, z, rows, columns, ref resolved);
        return new SurfaceItemRef3D(
            _chart, RequireHandle(handle, "surface"));
    }

    /// <summary>
    /// Adds r(azimuth, polar angle). Angles are radians: azimuth around +Z,
    /// polar angle from +Z. Radii use row * azimuths.Length + column indexing.
    /// Closed azimuth axes omit the duplicated full-turn endpoint.
    /// </summary>
    public SphericalSurfaceItemRef3D AddSphericalSurface(
        double[] azimuths,
        double[] polarAngles,
        double[] radii,
        bool closeAzimuth = true,
        SurfaceItemStyle3D? style = null)
    {
        if (azimuths is null)
            throw new ArgumentNullException(nameof(azimuths));
        if (polarAngles is null)
            throw new ArgumentNullException(nameof(polarAngles));
        if (azimuths.Length < (closeAzimuth ? 3 : 2) || polarAngles.Length < 2)
            throw new ArgumentException(
                "Spherical data needs at least two polar angles and two azimuths (three when closed).");
        ValidateRadii(radii, checked(azimuths.Length * polarAngles.Length));
        _chart.ThrowIfDisposed();
        if (_chart.Coordinates != PlotCoordinateSystem3D.Spherical)
            throw new InvalidOperationException(
                "Create a spherical chart with RetainedChart3D.CreateSpherical first.");
        var resolved = style ?? new SurfaceItemStyle3D();
        var handle = RetainedChart3DNative.AddSphericalSurface(
            _chart.NativeHandle, azimuths, (uint)azimuths.Length,
            polarAngles, (uint)polarAngles.Length, radii,
            closeAzimuth ? 1 : 0, ref resolved);
        return new SphericalSurfaceItemRef3D(
            _chart, RequireHandle(handle, "spherical surface"), radii.Length);
    }

    public ScatterItemRef3D AddScatter(
        double[] x,
        double[] y,
        double[] z,
        ScatterItemStyle3D? style = null)
    {
        ValidateEqualArrays(x, y, z);
        if (x.Length == 0)
            throw new ArgumentException("Scatter data must not be empty.");
        _chart.ThrowIfDisposed();
        var resolved = style ?? new ScatterItemStyle3D();
        var handle = RetainedChart3DNative.AddScatter(
            _chart.NativeHandle, x, y, z, (nuint)x.Length, ref resolved);
        return new ScatterItemRef3D(
            _chart, RequireHandle(handle, "scatter"));
    }

    public GridItemRef3D AddGrid(GridItemStyle3D? style = null)
    {
        _chart.ThrowIfDisposed();
        var resolved = style ?? new GridItemStyle3D();
        var handle = RetainedChart3DNative.AddGrid(
            _chart.NativeHandle, ref resolved);
        return new GridItemRef3D(
            _chart, RequireHandle(handle, "grid"));
    }

    private static PlotItemHandle3D RequireHandle(
        PlotItemHandle3D handle,
        string kind) => handle.IsValid
        ? handle
        : throw new InvalidOperationException(
            $"Failed to create retained {kind}. See native log.");

    internal static void ValidateSurface(
        double[] x,
        double[] y,
        double[] z,
        uint rows,
        uint columns)
    {
        ValidateEqualArrays(x, y, z);
        if (rows < 2 || columns < 2 ||
            (ulong)rows * columns != (ulong)x.Length)
            throw new ArgumentException(
                "Surface arrays must describe a rectangular grid of at least 2x2.");
    }

    internal static void ValidateRadii(double[] radii, int expectedCount)
    {
        if (radii is null)
            throw new ArgumentNullException(nameof(radii));
        if (radii.Length != expectedCount)
            throw new ArgumentException(
                "Radius count must equal polar-angle count times azimuth count.", nameof(radii));
        foreach (double radius in radii)
            if (double.IsNaN(radius) || double.IsInfinity(radius) || radius < 0)
                throw new ArgumentException(
                    "Radii must be finite and nonnegative.", nameof(radii));
    }

    internal static void ValidateEqualArrays(
        double[] x,
        double[] y,
        double[] z)
    {
        if (x is null)
            throw new ArgumentNullException(nameof(x));
        if (y is null)
            throw new ArgumentNullException(nameof(y));
        if (z is null)
            throw new ArgumentNullException(nameof(z));
        if (x.Length != y.Length || x.Length != z.Length)
            throw new ArgumentException(
                "Retained 3D item arrays must have equal lengths.");
    }
}

public sealed class Chart3DParts
{
    private readonly RetainedChart3D _chart;

    internal Chart3DParts(RetainedChart3D chart)
    {
        _chart = chart;
    }

    public GridItemRef3D? Grid
    {
        get
        {
            _chart.ThrowIfDisposed();
            var handle = RetainedChart3DNative.GridPart(
                _chart.NativeHandle);
            return handle.IsValid
                ? new GridItemRef3D(_chart, handle)
                : null;
        }
    }

    public void ReplaceGrid(GridItemRef3D replacement)
    {
        if (replacement is null)
            throw new ArgumentNullException(nameof(replacement));
        _chart.ThrowIfDisposed();
        replacement.ThrowIfStale();
        if (!ReferenceEquals(replacement.Chart, _chart))
            throw new ArgumentException(
                "Replacement grid belongs to another Chart3D.",
                nameof(replacement));
        if (RetainedChart3DNative.SetGridPart(
                _chart.NativeHandle, replacement.Handle) == 0)
            throw new InvalidOperationException(
                "Failed to replace Chart3D grid part.");
    }

    public void RemoveGrid()
    {
        _chart.ThrowIfDisposed();
        if (RetainedChart3DNative.SetGridPart(
                _chart.NativeHandle, default) == 0)
            throw new InvalidOperationException(
                "Failed to remove Chart3D grid part.");
    }
}

public sealed class Chart3DCamera
{
    private readonly RetainedChart3D _chart;

    internal Chart3DCamera(RetainedChart3D chart)
    {
        _chart = chart;
    }

    public OrbitCameraState3D State
    {
        get
        {
            _chart.ThrowIfDisposed();
            if (RetainedChart3DNative.GetCamera(
                    _chart.NativeHandle, out var state) == 0)
                throw new InvalidOperationException(
                    "Failed to read Chart3D camera.");
            return state;
        }
        set
        {
            _chart.ThrowIfDisposed();
            if (RetainedChart3DNative.SetCamera(
                    _chart.NativeHandle, ref value) == 0)
                throw new InvalidOperationException(
                    "Failed to update Chart3D camera. See native log.");
        }
    }

    public void Reset()
    {
        _chart.ThrowIfDisposed();
        RetainedChart3DNative.ResetCamera(_chart.NativeHandle);
    }

    public void Fit()
    {
        _chart.ThrowIfDisposed();
        RetainedChart3DNative.FitCamera(_chart.NativeHandle);
    }
}

public sealed class RetainedChart3D : IDisposable
{
    private readonly GpuHost? _host;
    private IntPtr _native;
    private bool _disposed;

    public RetainedChart3D(GpuHost host)
        : this(host ?? throw new ArgumentNullException(nameof(host)),
            PlotCoordinateSystem3D.Cartesian) {}

    /// <summary>Creates a chart with spherical reference circles, angular labels and radial scales.</summary>
    public static RetainedChart3D CreateSpherical(GpuHost? host = null) =>
        new(host, PlotCoordinateSystem3D.Spherical, null);

    /// <summary>
    /// Creates a spherical chart in an oriented angular frame. The frame applies
    /// consistently to spherical surfaces, reference geometry and angular labels.
    /// </summary>
    public static RetainedChart3D CreateSpherical(
        GpuHost? host,
        SphericalCoordinateFrame3D frame) =>
        new(host, PlotCoordinateSystem3D.Spherical, frame);

    private RetainedChart3D(
        GpuHost? host,
        PlotCoordinateSystem3D coordinates,
        SphericalCoordinateFrame3D? sphericalFrame = null)
    {
        _host = host;
        Coordinates = coordinates;
        IntPtr nativeHost = host is null ? IntPtr.Zero : GpuHost.getCPtr(host).Handle;
        if (coordinates == PlotCoordinateSystem3D.Spherical && sphericalFrame is { } frame)
            _native = RetainedChart3DNative.CreateSphericalWithFrame(nativeHost, ref frame);
        else
            _native = coordinates == PlotCoordinateSystem3D.Spherical
                ? RetainedChart3DNative.CreateSpherical(nativeHost)
                : RetainedChart3DNative.Create(nativeHost);
        if (_native == IntPtr.Zero)
            throw new InvalidOperationException(
                "Failed to create RetainedChart3D. See native log.");
        Scene = new PlotScene3D(this);
        Parts = new Chart3DParts(this);
        Camera = new Chart3DCamera(this);
    }

    internal IntPtr NativeHandle => _native;
    internal bool IsDisposed => _disposed;
    public PlotScene3D Scene { get; }
    public Chart3DParts Parts { get; }
    public Chart3DCamera Camera { get; }
    public PlotCoordinateSystem3D Coordinates { get; }

    /// <summary>
    /// Raised synchronously after a successful axis display offset or tick-label mutation.
    /// Other chart mutations still require an explicit render request from the consumer.
    /// When attached to a WPF host, mutate the chart on the host's UI thread.
    /// </summary>
    public event EventHandler? RenderInvalidated;

    public int MsaaSamples
    {
        get
        {
            ThrowIfDisposed();
            return RetainedChart3DNative.MsaaSamples(_native);
        }
        set
        {
            ThrowIfDisposed();
            if (RetainedChart3DNative.SetMsaaSamples(_native, value) == 0)
                throw new ArgumentOutOfRangeException(
                    nameof(value),
                    "MSAA samples must be a power of two between 1 and 16.");
        }
    }

    public void SetAxisLabels(string x, string y, string z)
    {
        ThrowIfDisposed();
        RetainedChart3DNative.SetAxisLabels(
            _native, x ?? string.Empty, y ?? string.Empty, z ?? string.Empty);
    }

    /// <summary>
    /// Displays value + offset without changing geometry, ticks, colors or camera.
    /// The Z or Radius offset also applies to the surface colorbar.
    /// </summary>
    public void SetAxisDisplayOffset(PlotAxis3D axis, double offset)
    {
        ThrowIfDisposed();
        ValidateDisplayAxis(axis);
        ValidateFinite(offset, nameof(offset));
        if (RetainedChart3DNative.SetAxisDisplayOffset(_native, axis, offset) == 0)
            throw new InvalidOperationException(
                "Failed to update axis display offset. See native log.");
        RenderInvalidated?.Invoke(this, EventArgs.Empty);
    }

    public double GetAxisDisplayOffset(PlotAxis3D axis)
    {
        ThrowIfDisposed();
        ValidateDisplayAxis(axis);
        if (RetainedChart3DNative.GetAxisDisplayOffset(_native, axis, out var offset) == 0)
            throw new InvalidOperationException(
                "Failed to read axis display offset. See native log.");
        return offset;
    }

    /// <summary>
    /// Overrides a tick at an original (unshifted) coordinate in the displayed range.
    /// Z and Radius overrides also apply to the surface colorbar. Null removes an
    /// override; an empty string hides its text. Settings belong to the chart.
    /// </summary>
    public void SetAxisTickLabel(PlotAxis3D axis, double value, string? label)
    {
        ThrowIfDisposed();
        ValidateDisplayAxis(axis);
        ValidateFinite(value, nameof(value));
        if (RetainedChart3DNative.SetAxisTickLabel(_native, axis, value, label) == 0)
            throw new InvalidOperationException(
                "Failed to update axis tick label. See native log.");
        RenderInvalidated?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>Removes all explicit tick labels for this axis, preserving its display offset.</summary>
    public void ClearAxisTickLabels(PlotAxis3D axis)
    {
        ThrowIfDisposed();
        ValidateDisplayAxis(axis);
        if (RetainedChart3DNative.ClearAxisTickLabels(_native, axis) == 0)
            throw new InvalidOperationException(
                "Failed to clear axis tick labels. See native log.");
        RenderInvalidated?.Invoke(this, EventArgs.Empty);
    }

    public void SetSurfaceShading(bool enabled, float strength = 0.38f)
    {
        ThrowIfDisposed();
        if (RetainedChart3DNative.SetSurfaceShading(
                _native, enabled ? 1 : 0, strength) == 0)
            throw new ArgumentOutOfRangeException(
                nameof(strength),
                "Shading strength must be finite.");
    }

    public void SetLightDirection(float x, float y, float z)
    {
        ThrowIfDisposed();
        if (RetainedChart3DNative.SetLightDirection(_native, x, y, z) == 0)
            throw new ArgumentException(
                "Light direction must be finite and non-zero.");
    }

    public void ShowColorBar(
        SurfaceRef3D surface,
        string label = "",
        ColorBarStyle3D? style = null)
    {
        ThrowIfDisposed();
        if (surface is null)
            throw new ArgumentNullException(nameof(surface));
        if (!ReferenceEquals(surface.Chart, this))
            throw new ArgumentException(
                "Surface belongs to another Chart3D.", nameof(surface));
        surface.ThrowIfStale();
        var resolved = style ?? new ColorBarStyle3D();
        if (RetainedChart3DNative.SetColorBar(
                _native,
                surface.Handle,
                label ?? string.Empty,
                ref resolved) == 0)
            throw new InvalidOperationException(
                "Failed to show Chart3D colorbar. See native log.");
    }

    public void HideColorBar()
    {
        ThrowIfDisposed();
        RetainedChart3DNative.ClearColorBar(_native);
    }

    public void SetAxisScale(float x, float y, float z)
    {
        ThrowIfDisposed();
        if (RetainedChart3DNative.SetAxisScale(_native, x, y, z) == 0)
            throw new ArgumentOutOfRangeException(
                nameof(x),
                "Axis scales must be finite and positive.");
    }

    public uint RenderToTextureHandleId(int width, int height)
    {
        ThrowIfDisposed();
        uint texture = RetainedChart3DNative.Render(_native, width, height);
        if (texture == 0)
            throw new InvalidOperationException(
                "Failed to render RetainedChart3D. See native log.");
        return texture;
    }

    public bool PointerDown(float x, float y, int button)
    {
        ThrowIfDisposed();
        return RetainedChart3DNative.PointerDown(
            _native, x, y, button) != 0;
    }

    public void PointerMove(float x, float y)
    {
        ThrowIfDisposed();
        RetainedChart3DNative.PointerMove(_native, x, y);
    }

    public void PointerUp(float x, float y, int button)
    {
        ThrowIfDisposed();
        RetainedChart3DNative.PointerUp(_native, x, y, button);
    }

    public bool Wheel(float x, float y, float delta)
    {
        ThrowIfDisposed();
        return RetainedChart3DNative.Wheel(_native, x, y, delta) != 0;
    }

    public void ReleaseGpuResources()
    {
        if (!_disposed && _native != IntPtr.Zero)
            RetainedChart3DNative.ReleaseGpu(_native);
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        if (_native != IntPtr.Zero)
            RetainedChart3DNative.Destroy(_native);
        _native = IntPtr.Zero;
        _disposed = true;
        RenderInvalidated = null;
        GC.SuppressFinalize(this);
    }

    private void ValidateDisplayAxis(PlotAxis3D axis)
    {
        bool valid = Coordinates == PlotCoordinateSystem3D.Spherical
            ? axis == PlotAxis3D.Radius
            : axis == PlotAxis3D.X || axis == PlotAxis3D.Y || axis == PlotAxis3D.Z;
        if (!valid)
            throw new ArgumentOutOfRangeException(nameof(axis),
                "Use X/Y/Z for Cartesian charts or Radius for spherical charts.");
    }

    private static void ValidateFinite(double value, string parameterName)
    {
        if (double.IsNaN(value) || double.IsInfinity(value))
            throw new ArgumentOutOfRangeException(parameterName, "Value must be finite.");
    }

    internal void ThrowIfDisposed()
    {
        if (_disposed || _native == IntPtr.Zero)
            throw new ObjectDisposedException(nameof(RetainedChart3D));
    }
}

internal static class RetainedChart3DNative
{
    private const string Dll = "tcplot";

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_create")]
    internal static extern IntPtr Create(IntPtr gpuHost);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_create_spherical")]
    internal static extern IntPtr CreateSpherical(IntPtr gpuHost);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_create_spherical_with_frame")]
    internal static extern IntPtr CreateSphericalWithFrame(
        IntPtr gpuHost,
        ref SphericalCoordinateFrame3D frame);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_destroy")]
    internal static extern void Destroy(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_scene_id")]
    internal static extern ulong SceneId(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_item_count")]
    internal static extern nuint ItemCount(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_item_is_valid")]
    internal static extern int ItemIsValid(
        IntPtr chart, PlotItemHandle3D item);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_item_snapshot")]
    internal static extern int ItemSnapshot(
        IntPtr chart,
        PlotItemHandle3D item,
        out PlotItemSnapshot3D snapshot);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_destroy_item")]
    internal static extern int DestroyItem(
        IntPtr chart, PlotItemHandle3D item);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_add_surface")]
    internal static extern PlotItemHandle3D AddSurface(
        IntPtr chart,
        [In] double[] x,
        [In] double[] y,
        [In] double[] z,
        uint rows,
        uint columns,
        ref SurfaceItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_add_spherical_surface")]
    internal static extern PlotItemHandle3D AddSphericalSurface(
        IntPtr chart,
        [In] double[] azimuths,
        uint columns,
        [In] double[] polarAngles,
        uint rows,
        [In] double[] radii,
        int closeAzimuth,
        ref SurfaceItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_spherical_surface_set_radii")]
    internal static extern int SphericalSurfaceSetRadii(
        IntPtr chart,
        PlotItemHandle3D surface,
        [In] double[] radii,
        nuint count);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_surface_set_data")]
    internal static extern int SurfaceSetData(
        IntPtr chart,
        PlotItemHandle3D surface,
        [In] double[] x,
        [In] double[] y,
        [In] double[] z,
        uint rows,
        uint columns);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_surface_set_style")]
    internal static extern int SurfaceSetStyle(
        IntPtr chart,
        PlotItemHandle3D surface,
        ref SurfaceItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_surface_get_style")]
    internal static extern int SurfaceGetStyle(
        IntPtr chart,
        PlotItemHandle3D surface,
        out SurfaceItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_add_scatter")]
    internal static extern PlotItemHandle3D AddScatter(
        IntPtr chart,
        [In] double[] x,
        [In] double[] y,
        [In] double[] z,
        nuint count,
        ref ScatterItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_scatter_set_data")]
    internal static extern int ScatterSetData(
        IntPtr chart,
        PlotItemHandle3D scatter,
        [In] double[] x,
        [In] double[] y,
        [In] double[] z,
        nuint count);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_scatter_set_style")]
    internal static extern int ScatterSetStyle(
        IntPtr chart,
        PlotItemHandle3D scatter,
        ref ScatterItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_scatter_get_style")]
    internal static extern int ScatterGetStyle(
        IntPtr chart,
        PlotItemHandle3D scatter,
        out ScatterItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_add_grid")]
    internal static extern PlotItemHandle3D AddGrid(
        IntPtr chart,
        ref GridItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_grid_set_style")]
    internal static extern int GridSetStyle(
        IntPtr chart,
        PlotItemHandle3D grid,
        ref GridItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_grid_get_style")]
    internal static extern int GridGetStyle(
        IntPtr chart,
        PlotItemHandle3D grid,
        out GridItemStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_grid_part")]
    internal static extern PlotItemHandle3D GridPart(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_grid_part")]
    internal static extern int SetGridPart(
        IntPtr chart,
        PlotItemHandle3D grid);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_chart3d_set_axis_labels",
        CharSet = CharSet.Ansi)]
    internal static extern void SetAxisLabels(
        IntPtr chart,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string x,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string y,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string z);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_axis_display_offset")]
    internal static extern int SetAxisDisplayOffset(
        IntPtr chart, PlotAxis3D axis, double offset);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_get_axis_display_offset")]
    internal static extern int GetAxisDisplayOffset(
        IntPtr chart, PlotAxis3D axis, out double offset);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_axis_tick_label")]
    internal static extern int SetAxisTickLabel(
        IntPtr chart, PlotAxis3D axis, double value,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string? label);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_clear_axis_tick_labels")]
    internal static extern int ClearAxisTickLabels(IntPtr chart, PlotAxis3D axis);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_surface_shading")]
    internal static extern int SetSurfaceShading(
        IntPtr chart, int enabled, float strength);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_light_direction")]
    internal static extern int SetLightDirection(
        IntPtr chart, float x, float y, float z);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_chart3d_set_colorbar",
        CharSet = CharSet.Ansi)]
    internal static extern int SetColorBar(
        IntPtr chart,
        PlotItemHandle3D surface,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string label,
        ref ColorBarStyle3D style);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_clear_colorbar")]
    internal static extern void ClearColorBar(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_axis_scale")]
    internal static extern int SetAxisScale(
        IntPtr chart, float x, float y, float z);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_msaa_samples")]
    internal static extern int SetMsaaSamples(IntPtr chart, int samples);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_msaa_samples")]
    internal static extern int MsaaSamples(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_get_camera")]
    internal static extern int GetCamera(
        IntPtr chart, out OrbitCameraState3D state);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_camera")]
    internal static extern int SetCamera(
        IntPtr chart, ref OrbitCameraState3D state);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_reset_camera")]
    internal static extern void ResetCamera(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_fit_camera")]
    internal static extern void FitCamera(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_pointer_down")]
    internal static extern int PointerDown(
        IntPtr chart, float x, float y, int button);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_pointer_move")]
    internal static extern void PointerMove(
        IntPtr chart, float x, float y);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_pointer_up")]
    internal static extern void PointerUp(
        IntPtr chart, float x, float y, int button);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_wheel")]
    internal static extern int Wheel(
        IntPtr chart, float x, float y, float delta);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_render")]
    internal static extern uint Render(
        IntPtr chart, int width, int height);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_release_gpu")]
    internal static extern void ReleaseGpu(IntPtr chart);
}
