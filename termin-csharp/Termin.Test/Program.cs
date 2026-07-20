using Termin.Native;
using System.Runtime.InteropServices;

Console.WriteLine("Testing SWIG bindings...");

// Test Vec3
var v1 = new Vec3(1.0, 2.0, 3.0);
var v2 = new Vec3(4.0, 5.0, 6.0);

Console.WriteLine($"v1 = ({v1.x}, {v1.y}, {v1.z})");
Console.WriteLine($"v2 = ({v2.x}, {v2.y}, {v2.z})");

var v3 = v1.Add(v2);
Console.WriteLine($"v1 + v2 = ({v3.x}, {v3.y}, {v3.z})");

Console.WriteLine($"v1.norm() = {v1.norm()}");
Console.WriteLine($"v1.dot(v2) = {v1.dot(v2)}");

// Test Quat
var q = Quat.identity();
Console.WriteLine($"identity quaternion = ({q.x}, {q.y}, {q.z}, {q.w})");

var axis = Vec3.unit_z();
var q2 = Quat.from_axis_angle(axis, Math.PI / 2.0);
Console.WriteLine($"90 deg rotation around Z = ({q2.x:F4}, {q2.y:F4}, {q2.z:F4}, {q2.w:F4})");

// Test Camera
var camera = Camera.perspective_deg(60.0, 16.0 / 9.0);
Console.WriteLine($"Camera projection_type = {camera.projection_type}");
Console.WriteLine($"Camera fov_y = {camera.fov_y}");
Console.WriteLine($"Camera aspect = {camera.aspect}");
Console.WriteLine($"Camera near = {camera.near}");
Console.WriteLine($"Camera far = {camera.far}");

var projMatrix = camera.projection_matrix();
Console.WriteLine("Projection matrix created successfully");

// Test view matrix
var eye = new Vec3(0, -5, 2);
var target = new Vec3(0, 0, 0);
var viewMatrix = Camera.view_matrix_look_at(eye, target);
Console.WriteLine("View matrix created successfully");

// Test TcValue ABI and dict helpers used by ComponentRef asset field setters.
if (Marshal.SizeOf<TcValue>() != 32)
    throw new InvalidOperationException($"TcValue ABI size mismatch: {Marshal.SizeOf<TcValue>()}");

var dict = TerminCore.ValueDictNew();
try
{
    if (dict.Type != TcValueType.Dict)
        throw new InvalidOperationException($"Expected TcValueType.Dict, got {dict.Type}");
    TerminCore.ValueDictSet(ref dict, "uuid", TerminCore.ValueString("test-uuid"));
    TerminCore.ValueDictSet(ref dict, "name", TerminCore.ValueString("test-name"));
}
finally
{
    TerminCore.ValueFree(ref dict);
}

// Test managed tc_render_surface ownership transfer.
var unownedSurface = new ManagedRenderSurfaceProbe();
unownedSurface.Dispose();
if (unownedSurface.DestroyCount != 1)
    throw new InvalidOperationException("Unowned render surface was not destroyed exactly once");

TerminCore.DisplayPoolInit();
try
{
    var transferredSurface = new ManagedRenderSurfaceProbe();
    var display = TerminCore.DisplayNew("csharp-surface-ownership", transferredSurface.SurfacePtr);
    if (!display.IsValid)
        throw new InvalidOperationException("Failed to create display for managed render surface");
    transferredSurface.MarkTransferred();
    transferredSurface.Dispose();
    if (transferredSurface.DestroyCount != 0)
        throw new InvalidOperationException("Transferred surface was destroyed by its managed wrapper");
    if (!TerminCore.DisplayResize(display, 320, 180))
        throw new InvalidOperationException("Display did not route resize to the managed surface");
    TerminCore.DisplayGetSize(display, out var displayWidth, out var displayHeight);
    if (displayWidth != 320 || displayHeight != 180)
        throw new InvalidOperationException($"Unexpected resized display size: {displayWidth}x{displayHeight}");
    if (!TerminCore.DisplayFree(display))
        throw new InvalidOperationException("Failed to destroy display-owned managed surface");
    if (transferredSurface.DestroyCount != 1)
        throw new InvalidOperationException("Display-owned managed surface was not destroyed exactly once");
}
finally
{
    TerminCore.DisplayPoolShutdown();
}

Console.WriteLine("\nAll tests passed!");

sealed class ManagedRenderSurfaceProbe : IDisposable
{
    private IntPtr _surfacePtr;
    private GCHandle _selfHandle;
    private bool _transferred;
    private bool _disposed;
    private int _width = 64;
    private int _height = 64;
    private readonly TerminCore.RenderSurfaceGetSizeDelegate _getSize;
    private readonly TerminCore.RenderSurfaceResizeDelegate _resize;
    private readonly TerminCore.RenderSurfaceGetColorTextureIdDelegate _getColorTextureId;
    private readonly TerminCore.RenderSurfaceGetGraphicsDomainKeyDelegate _getGraphicsDomainKey;
    private readonly TerminCore.RenderSurfaceDestroyDelegate _destroy;
    private TerminCore.RenderSurfaceVTable _vtable;

    public IntPtr SurfacePtr => _transferred ? IntPtr.Zero : _surfacePtr;
    public int DestroyCount { get; private set; }

    public ManagedRenderSurfaceProbe()
    {
        _selfHandle = GCHandle.Alloc(this);
        _getSize = GetSize;
        _resize = Resize;
        _getColorTextureId = _ => 0;
        _getGraphicsDomainKey = _ => 0;
        _destroy = Destroy;
        _vtable = new TerminCore.RenderSurfaceVTable
        {
            get_size = Marshal.GetFunctionPointerForDelegate(_getSize),
            resize = Marshal.GetFunctionPointerForDelegate(_resize),
            get_color_texture_id = Marshal.GetFunctionPointerForDelegate(_getColorTextureId),
            get_graphics_domain_key = Marshal.GetFunctionPointerForDelegate(_getGraphicsDomainKey),
            destroy = Marshal.GetFunctionPointerForDelegate(_destroy),
        };
        _surfacePtr = TerminCore.RenderSurfaceNewExternal(
            GCHandle.ToIntPtr(_selfHandle),
            ref _vtable,
            (nuint)Marshal.SizeOf<TerminCore.RenderSurfaceVTable>(),
            2);
        if (_surfacePtr == IntPtr.Zero)
        {
            _selfHandle.Free();
            throw new InvalidOperationException("Failed to create managed render surface probe");
        }
    }

    private static ManagedRenderSurfaceProbe? Self(IntPtr surface)
    {
        if (surface == IntPtr.Zero) return null;
        var body = Marshal.ReadIntPtr(surface, IntPtr.Size);
        return body == IntPtr.Zero
            ? null
            : GCHandle.FromIntPtr(body).Target as ManagedRenderSurfaceProbe;
    }

    private static void GetSize(IntPtr surface, out int width, out int height)
    {
        var self = Self(surface);
        width = self?._width ?? 0;
        height = self?._height ?? 0;
    }

    private static bool Resize(IntPtr surface, int width, int height)
    {
        var self = Self(surface);
        if (self is null || width <= 0 || height <= 0) return false;
        self._width = width;
        self._height = height;
        return true;
    }

    private static void Destroy(IntPtr surface)
    {
        var self = Self(surface);
        if (self is null) return;
        self.DestroyCount++;
        self._surfacePtr = IntPtr.Zero;
        self._transferred = true;
        self._disposed = true;
        if (self._selfHandle.IsAllocated) self._selfHandle.Free();
    }

    public void MarkTransferred()
    {
        if (_surfacePtr == IntPtr.Zero)
            throw new ObjectDisposedException(nameof(ManagedRenderSurfaceProbe));
        _transferred = true;
    }

    public void Dispose()
    {
        if (_disposed) return;
        if (_surfacePtr != IntPtr.Zero && !_transferred)
        {
            if (!TerminCore.RenderSurfaceDeleteUnowned(_surfacePtr)) return;
            _surfacePtr = IntPtr.Zero;
        }
        _disposed = true;
        GC.SuppressFinalize(this);
    }
}
