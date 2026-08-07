using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

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
    public readonly float TargetX;
    public readonly float TargetY;
    public readonly float TargetZ;
    public readonly float Distance;
    public readonly float Azimuth;
    public readonly float Elevation;
    public readonly float FieldOfViewY;
    public readonly float NearClip;
    public readonly float FarClip;

    public OrbitCameraState3D(
        float targetX,
        float targetY,
        float targetZ,
        float distance,
        float azimuth,
        float elevation,
        float fieldOfViewY,
        float nearClip,
        float farClip)
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

public sealed class SurfaceItemRef3D : PlotItemRef3D
{
    internal SurfaceItemRef3D(
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
        var resolved = style ?? new SurfaceItemStyle3D();
        var handle = RetainedChart3DNative.AddSurface(
            _chart.NativeHandle, x, y, z, rows, columns, ref resolved);
        return new SurfaceItemRef3D(
            _chart, RequireHandle(handle, "surface"));
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
    private readonly GpuHost _host;
    private IntPtr _native;
    private bool _disposed;

    public RetainedChart3D(GpuHost host)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _native = RetainedChart3DNative.Create(
            GpuHost.getCPtr(_host).Handle);
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
        GC.SuppressFinalize(this);
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

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_surface_shading")]
    internal static extern int SetSurfaceShading(
        IntPtr chart, int enabled, float strength);

    [DllImport(Dll, EntryPoint = "tc_retained_chart3d_set_light_direction")]
    internal static extern int SetLightDirection(
        IntPtr chart, float x, float y, float z);

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
