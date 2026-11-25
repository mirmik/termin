using System;
using System.Numerics;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>A drawing command with local 3D anchors, dimensions in DIPs, and straight sRGB color packed as 0xRRGGBBAA.</summary>
[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualAnnotation3D
{
    private readonly uint _kind;
    private readonly uint _rgba;
    private readonly Vector3 _a, _b, _c, _d;
    private readonly float _widthDip, _radiusDip, _headDip;

    private VisualAnnotation3D(uint kind, uint rgba, Vector3 a, Vector3 b = default,
        Vector3 c = default, Vector3 d = default, float width = 0, float radius = 0, float head = 0)
    {
        _kind = kind;
        _rgba = rgba;
        _a = a;
        _b = b;
        _c = c;
        _d = d;
        _widthDip = width;
        _radiusDip = radius;
        _headDip = head;
    }

    public static VisualAnnotation3D Line(Vector3 a, Vector3 b, uint rgba, float widthDip) =>
        new(0, rgba, a, b, width: widthDip);

    public static VisualAnnotation3D Arrow(Vector3 a, Vector3 b, uint rgba, float widthDip, float headDip) =>
        new(1, rgba, a, b, width: widthDip, head: headDip);

    public static VisualAnnotation3D Disc(Vector3 center, uint rgba, float radiusDip) =>
        new(2, rgba, center, radius: radiusDip);

    public static VisualAnnotation3D Ring(Vector3 center, uint rgba, float radiusDip, float widthDip) =>
        new(3, rgba, center, width: widthDip, radius: radiusDip);

    public static VisualAnnotation3D Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, uint rgba) =>
        new(4, rgba, a, b, c, d);
}

[StructLayout(LayoutKind.Sequential)]
internal readonly struct AnnotationItemHandle
{
    internal readonly ulong SceneId;
    internal readonly uint Index;
    internal readonly uint Generation;
}

/// <summary>Ordered VisualScene3D annotations. Create, edit, paint and dispose on the rendering thread.</summary>
public sealed class VisualAnnotationScene : IDisposable
{
    private readonly VisualSceneNativeHandle _scene;
    private readonly VisualAnnotationBatch _first;
    private bool _disposed;

    public VisualAnnotationScene()
    {
        _scene = AnnotationNative.CreateScene();
        if (!_scene.IsValid)
            throw new InvalidOperationException("Could not create the visual annotation scene.");
        try
        {
            _first = CreateBatch();
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    internal VisualSceneNativeHandle Handle => _disposed
        ? throw new ObjectDisposedException(nameof(VisualAnnotationScene)) : _scene;

    /// <summary>Append a retained batch in paint order. Its lifetime is tied to this scene.</summary>
    public VisualAnnotationBatch CreateBatch()
    {
        var item = AnnotationNative.CreateItem(Handle);
        if (item.SceneId == 0)
            throw new InvalidOperationException("Could not create the annotation item.");
        return new VisualAnnotationBatch(this, item);
    }

    /// <summary>Replace the first batch. Additional batches retain their contents and order.</summary>
    public void SetCommands(ReadOnlySpan<VisualAnnotation3D> commands) => _first.SetCommands(commands);

    /// <summary>Borrow the scene for a framegraph pass. Keep it alive while rendering with the pass.</summary>
    public void Bind(AnnotationPass pass, float pixelsPerDip)
    {
        if (pass == null)
            throw new ArgumentNullException(nameof(pass));
        if (!(pixelsPerDip > 0) || float.IsInfinity(pixelsPerDip))
            throw new ArgumentOutOfRangeException(nameof(pixelsPerDip));
        var scene = Handle;
        if (!pass.set_scene(scene.Index, scene.Generation, pixelsPerDip))
            throw new InvalidOperationException("Could not bind the annotation scene to the render pass.");
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        AnnotationNative.DestroyScene(_scene);
        _disposed = true;
    }
}

public sealed class VisualAnnotationBatch
{
    private readonly VisualAnnotationScene _scene;
    private readonly AnnotationItemHandle _item;

    internal VisualAnnotationBatch(VisualAnnotationScene scene, AnnotationItemHandle item)
    {
        _scene = scene;
        _item = item;
    }

    /// <summary>Replace this batch atomically. The native scene copies the commands.</summary>
    public unsafe void SetCommands(ReadOnlySpan<VisualAnnotation3D> commands)
    {
        fixed (VisualAnnotation3D* first = commands)
        {
            if (!AnnotationNative.SetCommands(_scene.Handle, _item, first, (nuint)commands.Length))
                throw new InvalidOperationException("Could not update the annotation batch. See the native log.");
        }
    }
}

internal static class AnnotationNative
{
    private const string Dll = "termin_visual_scene";

    [DllImport(Dll, EntryPoint = "tc_visual_scene3d_create")]
    internal static extern VisualSceneNativeHandle CreateScene();

    [DllImport(Dll, EntryPoint = "tc_visual_scene3d_destroy")]
    internal static extern void DestroyScene(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_annotation_item3d_create")]
    internal static extern AnnotationItemHandle CreateItem(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_annotation_item3d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern unsafe bool SetCommands(VisualSceneNativeHandle scene, AnnotationItemHandle item,
        VisualAnnotation3D* commands, nuint count);
}
