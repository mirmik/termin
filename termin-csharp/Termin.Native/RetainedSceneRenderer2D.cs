using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

[StructLayout(LayoutKind.Sequential)]
public readonly struct RetainedSceneRenderTimings2D
{
    public readonly double PaintMilliseconds;
    public readonly double FreezeMilliseconds;
    /// <summary>
    /// CPU time spent recording and submitting draw commands. This is not a
    /// GPU timestamp measurement.
    /// </summary>
    public readonly double GpuSubmitMilliseconds;
    public readonly double TotalMilliseconds;
}

/// <summary>
/// Renders a borrowed retained visual scene into a tgfx offscreen texture.
/// The GPU host and scene must outlive this object.
/// </summary>
public sealed class RetainedSceneRenderer2D : IDisposable
{
    private readonly GpuHost _host;
    private readonly TcVisualScene2D _scene;
    private IntPtr _native;
    private bool _disposed;

    public RetainedSceneRenderer2D(GpuHost host, TcVisualScene2D scene)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _scene = scene ?? throw new ArgumentNullException(nameof(scene));
        _scene.ThrowIfDisposed();

        _native = RetainedSceneRendererNative.Create(
            GpuHost.getCPtr(_host).Handle,
            _scene.NativeHandle);
        if (_native == IntPtr.Zero)
            throw new InvalidOperationException(
                "Failed to create retained scene renderer. See native log.");
    }

    public TcVisualScene2D Scene => _scene;

    public RetainedSceneRenderTimings2D LastTimings
    {
        get
        {
            ThrowIfDisposed();
            if (RetainedSceneRendererNative.LastTimings(
                    _native, out RetainedSceneRenderTimings2D timings) == 0)
                throw new InvalidOperationException(
                    "Failed to read retained scene render timings.");
            return timings;
        }
    }

    public int MsaaSamples
    {
        get
        {
            ThrowIfDisposed();
            return RetainedSceneRendererNative.MsaaSamples(_native);
        }
        set
        {
            ThrowIfDisposed();
            if (RetainedSceneRendererNative.SetMsaaSamples(
                    _native, value) == 0)
                throw new ArgumentOutOfRangeException(
                    nameof(value),
                    "MSAA samples must be a power of two between 1 and 16.");
        }
    }

    public void SetClearColor(VisualColor4f color)
    {
        ThrowIfDisposed();
        RetainedSceneRendererNative.SetClearColor(
            _native, color.R, color.G, color.B, color.A);
    }

    public uint RenderToTextureHandleId(int width, int height)
    {
        ThrowIfDisposed();
        if (width <= 0)
            throw new ArgumentOutOfRangeException(nameof(width));
        if (height <= 0)
            throw new ArgumentOutOfRangeException(nameof(height));

        uint texture = RetainedSceneRendererNative.Render(
            _native, width, height);
        if (texture == 0)
            throw new InvalidOperationException(
                "Failed to render retained scene. See native log.");
        return texture;
    }

    public void ReleaseGpuResources()
    {
        if (!_disposed && _native != IntPtr.Zero)
            RetainedSceneRendererNative.ReleaseGpu(_native);
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        if (_native != IntPtr.Zero)
            RetainedSceneRendererNative.Destroy(_native);
        _native = IntPtr.Zero;
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private void ThrowIfDisposed()
    {
        if (_disposed || _native == IntPtr.Zero)
            throw new ObjectDisposedException(
                nameof(RetainedSceneRenderer2D));
        _scene.ThrowIfDisposed();
    }
}

internal static class RetainedSceneRendererNative
{
    private const string Dll = "tcplot";

    [DllImport(Dll, EntryPoint = "tc_retained_scene_renderer2d_create")]
    internal static extern IntPtr Create(
        IntPtr gpuHost,
        VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_retained_scene_renderer2d_destroy")]
    internal static extern void Destroy(IntPtr renderer);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_scene_renderer2d_set_clear_color")]
    internal static extern void SetClearColor(
        IntPtr renderer,
        float r,
        float g,
        float b,
        float a);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_scene_renderer2d_set_msaa_samples")]
    internal static extern int SetMsaaSamples(IntPtr renderer, int samples);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_scene_renderer2d_msaa_samples")]
    internal static extern int MsaaSamples(IntPtr renderer);

    [DllImport(Dll, EntryPoint = "tc_retained_scene_renderer2d_render")]
    internal static extern uint Render(
        IntPtr renderer,
        int width,
        int height);

    [DllImport(
        Dll,
        EntryPoint = "tc_retained_scene_renderer2d_last_timings")]
    internal static extern int LastTimings(
        IntPtr renderer,
        out RetainedSceneRenderTimings2D timings);

    [DllImport(Dll, EntryPoint = "tc_retained_scene_renderer2d_release_gpu")]
    internal static extern void ReleaseGpu(IntPtr renderer);
}
