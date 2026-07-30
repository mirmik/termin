using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

[StructLayout(LayoutKind.Sequential)]
internal readonly struct VisualSceneNativeHandle
{
    internal readonly uint Index;
    internal readonly uint Generation;

    internal bool IsValid => Index != uint.MaxValue;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct GraphicItemHandle2D : IEquatable<GraphicItemHandle2D>
{
    public readonly ulong SceneId;
    public readonly uint Index;
    public readonly uint Generation;

    public bool IsValid =>
        SceneId != 0 && Index != uint.MaxValue && Generation != 0;

    public bool Equals(GraphicItemHandle2D other) =>
        SceneId == other.SceneId &&
        Index == other.Index &&
        Generation == other.Generation;

    public override bool Equals(object? obj) =>
        obj is GraphicItemHandle2D other && Equals(other);

    public override int GetHashCode() =>
        HashCode.Combine(SceneId, Index, Generation);

    public static bool operator ==(
        GraphicItemHandle2D left,
        GraphicItemHandle2D right) => left.Equals(right);

    public static bool operator !=(
        GraphicItemHandle2D left,
        GraphicItemHandle2D right) => !left.Equals(right);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualVec2f
{
    public readonly float X;
    public readonly float Y;

    public VisualVec2f(float x, float y)
    {
        X = x;
        Y = y;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualRect2f
{
    public readonly float X;
    public readonly float Y;
    public readonly float Width;
    public readonly float Height;

    public VisualRect2f(float x, float y, float width, float height)
    {
        X = x;
        Y = y;
        Width = width;
        Height = height;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualBounds2f
{
    public readonly float X0;
    public readonly float Y0;
    public readonly float X1;
    public readonly float Y1;

    public VisualBounds2f(float x0, float y0, float x1, float y1)
    {
        X0 = x0;
        Y0 = y0;
        X1 = x1;
        Y1 = y1;
    }
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualAffine2f
{
    public readonly float M00;
    public readonly float M01;
    public readonly float M10;
    public readonly float M11;
    public readonly float Tx;
    public readonly float Ty;

    public VisualAffine2f(
        float m00,
        float m01,
        float m10,
        float m11,
        float tx,
        float ty)
    {
        M00 = m00;
        M01 = m01;
        M10 = m10;
        M11 = m11;
        Tx = tx;
        Ty = ty;
    }

    public static VisualAffine2f Identity =>
        new(1, 0, 0, 1, 0, 0);

    public static VisualAffine2f Translation(float x, float y) =>
        new(1, 0, 0, 1, x, y);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualColor4f
{
    public readonly float R;
    public readonly float G;
    public readonly float B;
    public readonly float A;

    public VisualColor4f(float r, float g, float b, float a = 1)
    {
        R = r;
        G = g;
        B = b;
        A = a;
    }
}

public enum VisualFillRule2D
{
    NonZero,
    EvenOdd,
}

public enum VisualPathVerb2D
{
    MoveTo,
    LineTo,
    QuadraticTo,
    CubicTo,
    Close,
}

public enum VisualStrokeJoin2D
{
    Miter,
    Round,
    Bevel,
}

public enum VisualStrokeCap2D
{
    Butt,
    Round,
    Square,
}

public enum VisualTextAnchor2D
{
    Left,
    Center,
    Right,
}

public enum VisualTextureSampling2D
{
    Linear,
    Nearest,
}

public sealed class VisualPath2D
{
    public VisualPathVerb2D[] Verbs { get; }
    public VisualVec2f[] Points { get; }

    public VisualPath2D(
        VisualPathVerb2D[] verbs,
        VisualVec2f[] points)
    {
        Verbs = verbs ?? throw new ArgumentNullException(nameof(verbs));
        Points = points ?? throw new ArgumentNullException(nameof(points));
    }

    public static VisualPath2D Rectangle(VisualRect2f rect) =>
        new(
            new[]
            {
                VisualPathVerb2D.MoveTo,
                VisualPathVerb2D.LineTo,
                VisualPathVerb2D.LineTo,
                VisualPathVerb2D.LineTo,
                VisualPathVerb2D.Close,
            },
            new[]
            {
                new VisualVec2f(rect.X, rect.Y),
                new VisualVec2f(rect.X + rect.Width, rect.Y),
                new VisualVec2f(
                    rect.X + rect.Width,
                    rect.Y + rect.Height),
                new VisualVec2f(rect.X, rect.Y + rect.Height),
            });
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct VisualFillPaint2D
{
    public readonly VisualColor4f Color;
    public readonly VisualFillRule2D Rule;

    public VisualFillPaint2D(
        VisualColor4f color,
        VisualFillRule2D rule = VisualFillRule2D.NonZero)
    {
        Color = color;
        Rule = rule;
    }
}

public sealed class VisualStrokePaint2D
{
    public VisualColor4f Color { get; }
    public float Width { get; }
    public VisualStrokeJoin2D Join { get; }
    public VisualStrokeCap2D Cap { get; }
    public float MiterLimit { get; }
    public float[] DashPattern { get; }
    public float DashOffset { get; }

    public VisualStrokePaint2D(
        VisualColor4f color,
        float width = 1,
        VisualStrokeJoin2D join = VisualStrokeJoin2D.Miter,
        VisualStrokeCap2D cap = VisualStrokeCap2D.Butt,
        float miterLimit = 4,
        float[]? dashPattern = null,
        float dashOffset = 0)
    {
        Color = color;
        Width = width;
        Join = join;
        Cap = cap;
        MiterLimit = miterLimit;
        DashPattern = dashPattern ?? Array.Empty<float>();
        DashOffset = dashOffset;
    }
}

public sealed class TcVisualScene2D : IDisposable
{
    private VisualSceneNativeHandle _handle;
    private bool _disposed;

    public TcVisualScene2D()
    {
        _handle = VisualSceneNative.CreateScene();
        if (!_handle.IsValid)
            throw new InvalidOperationException(
                "Failed to create TcVisualScene2D.");
    }

    internal VisualSceneNativeHandle NativeHandle => _handle;
    public bool IsValid =>
        !_disposed && VisualSceneNative.SceneIsValid(_handle);

    public ulong Id
    {
        get
        {
            ThrowIfDisposed();
            return VisualSceneNative.SceneId(_handle);
        }
    }

    public nuint Count
    {
        get
        {
            ThrowIfDisposed();
            return VisualSceneNative.SceneItemCount(_handle);
        }
    }

    public void Clear()
    {
        ThrowIfDisposed();
        VisualSceneNative.SceneClear(_handle);
    }

    public GraphicItemRef2D ItemAt(nuint index)
    {
        ThrowIfDisposed();
        var handle = VisualSceneNative.SceneItemAt(_handle, index);
        if (!handle.IsValid)
            throw new ArgumentOutOfRangeException(nameof(index));
        return new GraphicItemRef2D(_handle, handle);
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        VisualSceneNative.DestroyScene(_handle);
        _disposed = true;
        _handle = default;
        GC.SuppressFinalize(this);
    }

    internal void ThrowIfDisposed()
    {
        if (_disposed || !VisualSceneNative.SceneIsValid(_handle))
            throw new ObjectDisposedException(nameof(TcVisualScene2D));
    }
}

public class GraphicItemRef2D
{
    internal readonly VisualSceneNativeHandle Scene;
    public GraphicItemHandle2D Handle { get; }

    internal GraphicItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle)
    {
        Scene = scene;
        Handle = handle;
    }

    public bool IsValid =>
        VisualSceneNative.ItemIsValid(Scene, Handle);

    public string TypeName
    {
        get
        {
            ThrowIfStale();
            var pointer = VisualSceneNative.ItemTypeName(Scene, Handle);
            return Marshal.PtrToStringUTF8(pointer) ?? string.Empty;
        }
    }

    public VisualAffine2f Transform
    {
        get
        {
            Require(VisualSceneNative.ItemGetTransform(
                Scene, Handle, out var value));
            return value;
        }
        set => Require(VisualSceneNative.ItemSetTransform(
            Scene, Handle, value));
    }

    public bool Visible
    {
        get
        {
            Require(VisualSceneNative.ItemGetVisible(
                Scene, Handle, out var value));
            return value;
        }
        set => Require(VisualSceneNative.ItemSetVisible(
            Scene, Handle, value));
    }

    public bool Enabled
    {
        get
        {
            Require(VisualSceneNative.ItemGetEnabled(
                Scene, Handle, out var value));
            return value;
        }
        set => Require(VisualSceneNative.ItemSetEnabled(
            Scene, Handle, value));
    }

    public float Opacity
    {
        get
        {
            Require(VisualSceneNative.ItemGetOpacity(
                Scene, Handle, out var value));
            return value;
        }
        set => Require(VisualSceneNative.ItemSetOpacity(
            Scene, Handle, value));
    }

    public long ZOrder
    {
        get
        {
            Require(VisualSceneNative.ItemGetZOrder(
                Scene, Handle, out var value));
            return value;
        }
        set => Require(VisualSceneNative.ItemSetZOrder(
            Scene, Handle, value));
    }

    public nuint ChildCount
    {
        get
        {
            ThrowIfStale();
            return VisualSceneNative.ItemChildCount(Scene, Handle);
        }
    }

    public GraphicItemRef2D? Parent
    {
        get
        {
            ThrowIfStale();
            var parent = VisualSceneNative.ItemParent(Scene, Handle);
            return parent.IsValid
                ? new GraphicItemRef2D(Scene, parent)
                : null;
        }
    }

    public GraphicItemRef2D ChildAt(nuint index)
    {
        ThrowIfStale();
        var child = VisualSceneNative.ItemChildAt(Scene, Handle, index);
        if (!child.IsValid)
            throw new ArgumentOutOfRangeException(nameof(index));
        return new GraphicItemRef2D(Scene, child);
    }

    public bool SetParent(GraphicItemRef2D? parent)
    {
        ThrowIfStale();
        var parentHandle = parent?.Handle ?? default;
        var index = parent?.ChildCount ?? 0;
        return VisualSceneNative.ItemSetParent(
            Scene, Handle, parentHandle, index);
    }

    public bool InsertInto(GraphicItemRef2D parent, nuint index)
    {
        if (parent is null)
            throw new ArgumentNullException(nameof(parent));
        ThrowIfStale();
        return VisualSceneNative.ItemSetParent(
            Scene, Handle, parent.Handle, index);
    }

    public void SetClip(VisualRect2f rect) =>
        Require(VisualSceneNative.ItemSetClipRect(
            Scene, Handle, rect));

    public void SetClip(
        VisualPath2D path,
        VisualFillRule2D rule = VisualFillRule2D.NonZero) =>
        Require(VisualSceneNative.ItemSetClipPath(
            Scene, Handle, path, rule));

    public void ClearClip() =>
        Require(VisualSceneNative.ItemClearClip(Scene, Handle));

    public bool TryGetLocalBounds(out VisualBounds2f bounds) =>
        VisualSceneNative.ItemGetLocalBounds(
            Scene, Handle, out bounds);

    public bool TryGetWorldBounds(out VisualBounds2f bounds) =>
        VisualSceneNative.ItemGetWorldBounds(
            Scene, Handle, out bounds);

    public bool Destroy()
    {
        ThrowIfStale();
        return VisualSceneNative.SceneDestroyItem(Scene, Handle);
    }

    internal void ThrowIfStale()
    {
        if (!IsValid)
            throw new InvalidOperationException(
                "GraphicItemRef2D is stale or belongs to a destroyed scene.");
    }

    internal void Require(bool result)
    {
        if (!result)
            throw new InvalidOperationException(
                "Graphic item operation was rejected.");
    }

    internal static void RequireType(
        GraphicItemRef2D item,
        string expected)
    {
        if (item is null)
            throw new ArgumentNullException(nameof(item));
        item.ThrowIfStale();
        if (!VisualSceneNative.ItemIsType(
                item.Scene, item.Handle, expected))
            throw new InvalidCastException(
                $"Graphic item is '{item.TypeName}', expected '{expected}'.");
    }
}

public sealed class GroupItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.Group2D";

    private GroupItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static GroupItemRef2D Create(
        TcVisualScene2D scene,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var handle = VisualSceneNative.CreateGroup(
            scene.NativeHandle, parent?.Handle ?? default);
        return new GroupItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public static GroupItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new GroupItemRef2D(item.Scene, item.Handle);
    }
}

public sealed class RectItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.Rect2D";

    private RectItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static RectItemRef2D Create(
        TcVisualScene2D scene,
        VisualRect2f rect,
        VisualFillPaint2D fill,
        VisualStrokePaint2D? stroke = null,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var handle = VisualSceneNative.CreateRect(
            scene.NativeHandle, parent?.Handle ?? default,
            rect, fill, stroke);
        return new RectItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public void Set(
        VisualRect2f rect,
        VisualFillPaint2D fill,
        VisualStrokePaint2D? stroke = null) =>
        Require(VisualSceneNative.SetRect(
            Scene, Handle, rect, fill, stroke));

    public static RectItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new RectItemRef2D(item.Scene, item.Handle);
    }
}

public sealed class PathItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.Path2D";

    private PathItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static PathItemRef2D Create(
        TcVisualScene2D scene,
        VisualPath2D path,
        VisualFillPaint2D? fill = null,
        VisualStrokePaint2D? stroke = null,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var handle = VisualSceneNative.CreatePath(
            scene.NativeHandle, parent?.Handle ?? default,
            path, fill, stroke);
        return new PathItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public void Set(
        VisualPath2D path,
        VisualFillPaint2D? fill = null,
        VisualStrokePaint2D? stroke = null) =>
        Require(VisualSceneNative.SetPath(
            Scene, Handle, path, fill, stroke));

    public static PathItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new PathItemRef2D(item.Scene, item.Handle);
    }
}

public sealed class TextItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.Text2D";

    private TextItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static TextItemRef2D Create(
        TcVisualScene2D scene,
        string text,
        string fontUri,
        VisualVec2f origin,
        float sizePx,
        VisualColor4f color,
        VisualBounds2f layoutBounds,
        VisualTextAnchor2D anchor = VisualTextAnchor2D.Left,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var desc = new VisualSceneNative.TextDesc(
            text, fontUri, origin, sizePx, color, anchor, layoutBounds);
        var handle = VisualSceneNative.CreateText(
            scene.NativeHandle, parent?.Handle ?? default, ref desc);
        return new TextItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public void Set(
        string text,
        string fontUri,
        VisualVec2f origin,
        float sizePx,
        VisualColor4f color,
        VisualBounds2f layoutBounds,
        VisualTextAnchor2D anchor = VisualTextAnchor2D.Left)
    {
        var desc = new VisualSceneNative.TextDesc(
            text, fontUri, origin, sizePx, color, anchor, layoutBounds);
        Require(VisualSceneNative.SetText(
            Scene, Handle, ref desc));
    }

    public static TextItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new TextItemRef2D(item.Scene, item.Handle);
    }
}

public sealed class ImageItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.Image2D";

    private ImageItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static ImageItemRef2D Create(
        TcVisualScene2D scene,
        string imageUri,
        VisualRect2f rect,
        VisualRect2f uv,
        VisualColor4f tint,
        VisualTextureSampling2D sampling =
            VisualTextureSampling2D.Linear,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var desc = new VisualSceneNative.ImageDesc(
            imageUri, rect, uv, tint, sampling);
        var handle = VisualSceneNative.CreateImage(
            scene.NativeHandle, parent?.Handle ?? default, ref desc);
        return new ImageItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public void Set(
        string imageUri,
        VisualRect2f rect,
        VisualRect2f uv,
        VisualColor4f tint,
        VisualTextureSampling2D sampling =
            VisualTextureSampling2D.Linear)
    {
        var desc = new VisualSceneNative.ImageDesc(
            imageUri, rect, uv, tint, sampling);
        Require(VisualSceneNative.SetImage(
            Scene, Handle, ref desc));
    }

    public static ImageItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new ImageItemRef2D(item.Scene, item.Handle);
    }
}

public sealed class HitRegionItemRef2D : GraphicItemRef2D
{
    private const string NativeType = "termin.visual.HitRegion2D";

    private HitRegionItemRef2D(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D handle) : base(scene, handle) {}

    public static HitRegionItemRef2D Create(
        TcVisualScene2D scene,
        VisualPath2D path,
        VisualFillRule2D rule = VisualFillRule2D.NonZero,
        GraphicItemRef2D? parent = null)
    {
        scene.ThrowIfDisposed();
        var handle = VisualSceneNative.CreateHitRegion(
            scene.NativeHandle, parent?.Handle ?? default, path, rule);
        return new HitRegionItemRef2D(
            scene.NativeHandle,
            VisualSceneNative.RequireHandle(handle));
    }

    public void Set(
        VisualPath2D path,
        VisualFillRule2D rule = VisualFillRule2D.NonZero) =>
        Require(VisualSceneNative.SetHitRegion(
            Scene, Handle, path, rule));

    public static HitRegionItemRef2D Cast(GraphicItemRef2D item)
    {
        RequireType(item, NativeType);
        return new HitRegionItemRef2D(item.Scene, item.Handle);
    }
}

internal static unsafe class VisualSceneNative
{
    private const string Dll = "termin_visual_scene";

    [StructLayout(LayoutKind.Sequential)]
    internal readonly struct NativePathView
    {
        internal readonly VisualPathVerb2D* Verbs;
        internal readonly nuint VerbCount;
        internal readonly VisualVec2f* Points;
        internal readonly nuint PointCount;

        internal NativePathView(
            VisualPathVerb2D* verbs,
            nuint verbCount,
            VisualVec2f* points,
            nuint pointCount)
        {
            Verbs = verbs;
            VerbCount = verbCount;
            Points = points;
            PointCount = pointCount;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    internal readonly struct NativeStroke
    {
        internal readonly VisualColor4f Color;
        internal readonly float Width;
        internal readonly VisualStrokeJoin2D Join;
        internal readonly VisualStrokeCap2D Cap;
        internal readonly float MiterLimit;
        internal readonly float* DashPattern;
        internal readonly nuint DashCount;
        internal readonly float DashOffset;

        internal NativeStroke(VisualStrokePaint2D value, float* dash)
        {
            Color = value.Color;
            Width = value.Width;
            Join = value.Join;
            Cap = value.Cap;
            MiterLimit = value.MiterLimit;
            DashPattern = dash;
            DashCount = (nuint)value.DashPattern.Length;
            DashOffset = value.DashOffset;
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    internal struct TextDesc
    {
        [MarshalAs(UnmanagedType.LPUTF8Str)]
        internal string Text;
        [MarshalAs(UnmanagedType.LPUTF8Str)]
        internal string FontUri;
        internal VisualVec2f Origin;
        internal float SizePx;
        internal VisualColor4f Color;
        internal VisualTextAnchor2D Anchor;
        internal VisualBounds2f LayoutBounds;

        internal TextDesc(
            string text,
            string fontUri,
            VisualVec2f origin,
            float sizePx,
            VisualColor4f color,
            VisualTextAnchor2D anchor,
            VisualBounds2f layoutBounds)
        {
            Text = text;
            FontUri = fontUri;
            Origin = origin;
            SizePx = sizePx;
            Color = color;
            Anchor = anchor;
            LayoutBounds = layoutBounds;
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    internal struct ImageDesc
    {
        [MarshalAs(UnmanagedType.LPUTF8Str)]
        internal string ImageUri;
        internal VisualRect2f Rect;
        internal VisualRect2f Uv;
        internal VisualColor4f Tint;
        internal VisualTextureSampling2D Sampling;

        internal ImageDesc(
            string imageUri,
            VisualRect2f rect,
            VisualRect2f uv,
            VisualColor4f tint,
            VisualTextureSampling2D sampling)
        {
            ImageUri = imageUri;
            Rect = rect;
            Uv = uv;
            Tint = tint;
            Sampling = sampling;
        }
    }

    [DllImport(Dll, EntryPoint = "tc_visual_scene_create")]
    internal static extern VisualSceneNativeHandle CreateScene();

    [DllImport(Dll, EntryPoint = "tc_visual_scene_destroy")]
    internal static extern void DestroyScene(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_is_valid")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SceneIsValid(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_id")]
    internal static extern ulong SceneId(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_count")]
    internal static extern nuint SceneItemCount(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_copy_item_handles")]
    private static extern nuint SceneCopyItemHandles(
        VisualSceneNativeHandle scene,
        [Out] GraphicItemHandle2D[]? handles,
        nuint capacity);

    internal static GraphicItemHandle2D SceneItemAt(
        VisualSceneNativeHandle scene,
        nuint index)
    {
        var count = SceneCopyItemHandles(scene, null, 0);
        if (index >= count)
            return default;
        var handles = new GraphicItemHandle2D[(int)count];
        SceneCopyItemHandles(scene, handles, count);
        return handles[(int)index];
    }

    [DllImport(Dll, EntryPoint = "tc_visual_scene_destroy_item")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SceneDestroyItem(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_clear")]
    internal static extern void SceneClear(VisualSceneNativeHandle scene);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_is_valid")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemIsValid(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_type_name")]
    internal static extern IntPtr ItemTypeName(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(
        Dll,
        EntryPoint = "tc_visual_scene_item_is_type",
        CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemIsType(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string typeName);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_transform")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetTransform(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out VisualAffine2f transform);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_transform")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetTransform(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualAffine2f transform);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_visible")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetVisible(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [MarshalAs(UnmanagedType.I1)] out bool visible);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_visible")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetVisible(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [MarshalAs(UnmanagedType.I1)] bool visible);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_enabled")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetEnabled(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [MarshalAs(UnmanagedType.I1)] out bool enabled);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_enabled")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetEnabled(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        [MarshalAs(UnmanagedType.I1)] bool enabled);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_opacity")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetOpacity(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out float opacity);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_opacity")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetOpacity(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        float opacity);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_z_order")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetZOrder(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out long zOrder);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_z_order")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetZOrder(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        long zOrder);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_parent")]
    internal static extern GraphicItemHandle2D ItemParent(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_child_count")]
    internal static extern nuint ItemChildCount(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_child_at")]
    internal static extern GraphicItemHandle2D ItemChildAt(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        nuint index);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_parent")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetParent(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        GraphicItemHandle2D parent,
        nuint index);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_local_bounds")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetLocalBounds(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out VisualBounds2f bounds);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_get_world_bounds")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemGetWorldBounds(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        out VisualBounds2f bounds);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_clip_rect")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemSetClipRect(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualRect2f rect);

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_set_clip_path")]
    [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool ItemSetClipPathNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        NativePathView path,
        VisualFillRule2D rule);

    internal static bool ItemSetClipPath(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualPath2D path,
        VisualFillRule2D rule)
    {
        fixed (VisualPathVerb2D* verbs = path.Verbs)
        fixed (VisualVec2f* points = path.Points)
        {
            return ItemSetClipPathNative(
                scene, item,
                new NativePathView(
                    verbs, (nuint)path.Verbs.Length,
                    points, (nuint)path.Points.Length),
                rule);
        }
    }

    [DllImport(Dll, EntryPoint = "tc_visual_scene_item_clear_clip")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool ItemClearClip(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item);

    [DllImport(Dll, EntryPoint = "tc_visual_group_item2d_create")]
    internal static extern GraphicItemHandle2D CreateGroup(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent);

    [DllImport(Dll, EntryPoint = "tc_visual_rect_item2d_create")]
    private static extern GraphicItemHandle2D CreateRectNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        VisualRect2f rect,
        VisualFillPaint2D fill,
        NativeStroke* stroke);

    [DllImport(Dll, EntryPoint = "tc_visual_rect_item2d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SetRectNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualRect2f rect,
        VisualFillPaint2D fill,
        NativeStroke* stroke);

    internal static GraphicItemHandle2D CreateRect(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        VisualRect2f rect,
        VisualFillPaint2D fill,
        VisualStrokePaint2D? stroke)
    {
        fixed (float* dash = stroke?.DashPattern)
        {
            var native = stroke is null
                ? default : new NativeStroke(stroke, dash);
            return CreateRectNative(
                scene, parent, rect, fill,
                stroke is null ? null : &native);
        }
    }

    internal static bool SetRect(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualRect2f rect,
        VisualFillPaint2D fill,
        VisualStrokePaint2D? stroke)
    {
        fixed (float* dash = stroke?.DashPattern)
        {
            var native = stroke is null
                ? default : new NativeStroke(stroke, dash);
            return SetRectNative(
                scene, item, rect, fill,
                stroke is null ? null : &native);
        }
    }

    [DllImport(Dll, EntryPoint = "tc_visual_path_item2d_create")]
    private static extern GraphicItemHandle2D CreatePathNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        NativePathView path,
        VisualFillPaint2D* fill,
        NativeStroke* stroke);

    [DllImport(Dll, EntryPoint = "tc_visual_path_item2d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SetPathNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        NativePathView path,
        VisualFillPaint2D* fill,
        NativeStroke* stroke);

    internal static GraphicItemHandle2D CreatePath(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        VisualPath2D path,
        VisualFillPaint2D? fill,
        VisualStrokePaint2D? stroke)
    {
        fixed (VisualPathVerb2D* verbs = path.Verbs)
        fixed (VisualVec2f* points = path.Points)
        fixed (float* dash = stroke?.DashPattern)
        {
            var nativePath = new NativePathView(
                verbs, (nuint)path.Verbs.Length,
                points, (nuint)path.Points.Length);
            var nativeFill = fill.GetValueOrDefault();
            var nativeStroke = stroke is null
                ? default : new NativeStroke(stroke, dash);
            return CreatePathNative(
                scene, parent, nativePath,
                fill.HasValue ? &nativeFill : null,
                stroke is null ? null : &nativeStroke);
        }
    }

    internal static bool SetPath(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualPath2D path,
        VisualFillPaint2D? fill,
        VisualStrokePaint2D? stroke)
    {
        fixed (VisualPathVerb2D* verbs = path.Verbs)
        fixed (VisualVec2f* points = path.Points)
        fixed (float* dash = stroke?.DashPattern)
        {
            var nativePath = new NativePathView(
                verbs, (nuint)path.Verbs.Length,
                points, (nuint)path.Points.Length);
            var nativeFill = fill.GetValueOrDefault();
            var nativeStroke = stroke is null
                ? default : new NativeStroke(stroke, dash);
            return SetPathNative(
                scene, item, nativePath,
                fill.HasValue ? &nativeFill : null,
                stroke is null ? null : &nativeStroke);
        }
    }

    [DllImport(Dll, EntryPoint = "tc_visual_text_item2d_create")]
    internal static extern GraphicItemHandle2D CreateText(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        ref TextDesc desc);

    [DllImport(Dll, EntryPoint = "tc_visual_text_item2d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetText(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        ref TextDesc desc);

    [DllImport(Dll, EntryPoint = "tc_visual_image_item2d_create")]
    internal static extern GraphicItemHandle2D CreateImage(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        ref ImageDesc desc);

    [DllImport(Dll, EntryPoint = "tc_visual_image_item2d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetImage(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        ref ImageDesc desc);

    [DllImport(Dll, EntryPoint = "tc_visual_hit_region_item2d_create")]
    private static extern GraphicItemHandle2D CreateHitRegionNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        NativePathView path,
        VisualFillRule2D rule);

    [DllImport(Dll, EntryPoint = "tc_visual_hit_region_item2d_set")]
    [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SetHitRegionNative(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        NativePathView path,
        VisualFillRule2D rule);

    internal static GraphicItemHandle2D CreateHitRegion(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D parent,
        VisualPath2D path,
        VisualFillRule2D rule)
    {
        fixed (VisualPathVerb2D* verbs = path.Verbs)
        fixed (VisualVec2f* points = path.Points)
        {
            return CreateHitRegionNative(
                scene, parent,
                new NativePathView(
                    verbs, (nuint)path.Verbs.Length,
                    points, (nuint)path.Points.Length),
                rule);
        }
    }

    internal static bool SetHitRegion(
        VisualSceneNativeHandle scene,
        GraphicItemHandle2D item,
        VisualPath2D path,
        VisualFillRule2D rule)
    {
        fixed (VisualPathVerb2D* verbs = path.Verbs)
        fixed (VisualVec2f* points = path.Points)
        {
            return SetHitRegionNative(
                scene, item,
                new NativePathView(
                    verbs, (nuint)path.Verbs.Length,
                    points, (nuint)path.Points.Length),
                rule);
        }
    }

    internal static GraphicItemHandle2D RequireHandle(
        GraphicItemHandle2D handle)
    {
        if (!handle.IsValid)
            throw new InvalidOperationException(
                "Native graphic item factory rejected the item.");
        return handle;
    }
}
