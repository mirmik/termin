using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Entity ID with generational index (matches tc_entity_id in C).
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcEntityId
{
    public uint Index;
    public uint Generation;

    public static readonly TcEntityId Invalid = new() { Index = 0xFFFFFFFF, Generation = 0 };

    public bool IsValid => Index != 0xFFFFFFFF;

    public override string ToString() => $"Entity({Index}:{Generation})";
}

/// <summary>
/// Mesh handle matching tc_mesh_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcMeshHandle
{
    public uint Index;
    public uint Generation;
}

/// <summary>
/// Shader handle matching tc_shader_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcShaderHandle
{
    public uint Index;
    public uint Generation;
}

/// <summary>
/// Material handle matching tc_material_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcMaterialHandle
{
    public uint Index;
    public uint Generation;
}

/// <summary>
/// Viewport handle matching tc_viewport_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcViewportHandle
{
    public uint Index;
    public uint Generation;

    public static readonly TcViewportHandle Invalid = new() { Index = 0xFFFFFFFF, Generation = 0 };

    public bool IsValid => Index != 0xFFFFFFFF;

    public override string ToString() => $"Viewport({Index}:{Generation})";
}

/// <summary>
/// Scene handle matching tc_scene_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcSceneHandle
{
    public uint Index;
    public uint Generation;

    public static readonly TcSceneHandle Invalid = new() { Index = 0xFFFFFFFF, Generation = 0 };

    public bool IsValid => Index != 0xFFFFFFFF;

    public override string ToString() => $"Scene({Index}:{Generation})";
}

/// <summary>
/// Pipeline handle matching tc_pipeline_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcPipelineHandle
{
    public uint Index;
    public uint Generation;

    public static readonly TcPipelineHandle Invalid = new() { Index = 0xFFFFFFFF, Generation = 0 };

    public bool IsValid => Index != 0xFFFFFFFF;

    public override string ToString() => $"Pipeline({Index}:{Generation})";

    /// <summary>
    /// Convert from SWIG-generated tc_pipeline_handle class.
    /// </summary>
    public static TcPipelineHandle FromSwig(tc_pipeline_handle swigHandle)
    {
        if (swigHandle == null) return Invalid;
        return new TcPipelineHandle { Index = swigHandle.index, Generation = swigHandle.generation };
    }

    /// <summary>
    /// Implicit conversion from SWIG type.
    /// </summary>
    public static implicit operator TcPipelineHandle(tc_pipeline_handle swigHandle) => FromSwig(swigHandle);
}

/// <summary>
/// Entity pool handle matching tc_entity_pool_handle in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcEntityPoolHandle
{
    public uint Index;
    public uint Generation;

    public static readonly TcEntityPoolHandle Invalid = new() { Index = 0xFFFFFFFF, Generation = 0 };

    public bool IsValid => Index != 0xFFFFFFFF;

    public override string ToString() => $"EntityPool({Index}:{Generation})";
}

/// <summary>
/// Attribute type matching tc_attrib_type in C.
/// </summary>
public enum TcAttribType : byte
{
    Float32 = 0,
    Int32 = 1,
    Uint32 = 2,
    Int16 = 3,
    Uint16 = 4,
    Int8 = 5,
    Uint8 = 6,
}

/// <summary>
/// Vertex attribute matching tc_vertex_attrib in C.
/// </summary>
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
public unsafe struct TcVertexAttrib
{
    public fixed byte Name[32];
    public byte Size;
    public byte Type;
    public byte Location;
    public byte Pad;
    public ushort Offset;
}

/// <summary>
/// Vertex layout matching tc_vertex_layout in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public unsafe struct TcVertexLayout
{
    public ushort Stride;
    public byte AttribCount;
    public byte Pad;
    public fixed byte Attribs[8 * 38]; // 8 attributes * sizeof(TcVertexAttrib)
}
