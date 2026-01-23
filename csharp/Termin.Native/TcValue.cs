using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Value type enum matching tc_value_type in C.
/// </summary>
public enum TcValueType : int
{
    Nil = 0,
    Bool = 1,
    Int = 2,
    Float = 3,
    Double = 4,
    String = 5,
    Vec3 = 6,
    Quat = 7,
    List = 8,
    Dict = 9,
}

/// <summary>
/// Vec3 matching tc_vec3 in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcVec3
{
    public double X, Y, Z;

    public TcVec3(double x, double y, double z)
    {
        X = x;
        Y = y;
        Z = z;
    }
}

/// <summary>
/// Quat matching tc_quat in C.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct TcQuat
{
    public double X, Y, Z, W;

    public TcQuat(double x, double y, double z, double w)
    {
        X = x;
        Y = y;
        Z = z;
        W = w;
    }
}

/// <summary>
/// Tagged union value type matching tc_value in C.
/// Used for field inspection and serialization.
/// </summary>
[StructLayout(LayoutKind.Explicit, Size = 40)]
public struct TcValue
{
    [FieldOffset(0)]
    public TcValueType Type;

    // Union data starts at offset 8 (alignment)
    [FieldOffset(8)]
    public byte BoolValue;

    [FieldOffset(8)]
    public long IntValue;

    [FieldOffset(8)]
    public float FloatValue;

    [FieldOffset(8)]
    public double DoubleValue;

    [FieldOffset(8)]
    public IntPtr StringPtr;

    [FieldOffset(8)]
    public TcVec3 Vec3Value;

    [FieldOffset(8)]
    public TcQuat QuatValue;

    // List and Dict are complex - use IntPtr for now
    [FieldOffset(8)]
    public IntPtr ListPtr;

    [FieldOffset(8)]
    public IntPtr DictPtr;

    /// <summary>
    /// Get string value (copies from native memory).
    /// </summary>
    public string? GetString()
    {
        if (Type != TcValueType.String || StringPtr == IntPtr.Zero)
            return null;
        return Marshal.PtrToStringUTF8(StringPtr);
    }

    /// <summary>
    /// Get bool value.
    /// </summary>
    public bool GetBool() => Type == TcValueType.Bool && BoolValue != 0;

    /// <summary>
    /// Get int value.
    /// </summary>
    public long GetInt() => Type == TcValueType.Int ? IntValue : 0;

    /// <summary>
    /// Get float value.
    /// </summary>
    public float GetFloat() => Type == TcValueType.Float ? FloatValue : 0f;

    /// <summary>
    /// Get double value.
    /// </summary>
    public double GetDouble() => Type == TcValueType.Double ? DoubleValue : 0.0;
}
