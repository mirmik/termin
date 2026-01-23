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
