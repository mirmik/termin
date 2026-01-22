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
