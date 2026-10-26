using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Runtime.InteropServices;

namespace Termin.Native;

public enum NativeGraphValueKind
{
    Nil, Boolean, Integer, Float, Number, Text, List, Dictionary
}

/// <summary>A deep managed copy of a native graph value. Container contents are immutable.</summary>
public sealed class NativeGraphValue
{
    private readonly object? _value;
    public NativeGraphValueKind Kind { get; }
    private NativeGraphValue(NativeGraphValueKind kind, object? value)
    {
        Kind = kind;
        _value = value;
    }
    public static NativeGraphValue Nil { get; } = new(NativeGraphValueKind.Nil, null);
    public static NativeGraphValue Boolean(bool value) => new(NativeGraphValueKind.Boolean, value);
    public static NativeGraphValue Integer(long value) => new(NativeGraphValueKind.Integer, value);
    public static NativeGraphValue Number(double value) => new(NativeGraphValueKind.Number, value);
    public static NativeGraphValue FloatingPoint(float value) => new(NativeGraphValueKind.Float, value);
    public static NativeGraphValue Text(string value) => new(NativeGraphValueKind.Text, CheckedText(value));
    public static NativeGraphValue List(IEnumerable<NativeGraphValue> values)
    {
        if (values == null) throw new ArgumentNullException(nameof(values));
        var copy = new List<NativeGraphValue>();
        foreach (var value in values) copy.Add(value ?? throw new ArgumentException("A value cannot be null.", nameof(values)));
        return new(NativeGraphValueKind.List, copy.AsReadOnly());
    }
    public static NativeGraphValue Dictionary(IEnumerable<KeyValuePair<string, NativeGraphValue>> values)
    {
        if (values == null) throw new ArgumentNullException(nameof(values));
        var copy = new Dictionary<string, NativeGraphValue>(StringComparer.Ordinal);
        foreach (var pair in values)
            copy.Add(CheckedText(pair.Key), pair.Value ?? throw new ArgumentException("A value cannot be null.", nameof(values)));
        return new(NativeGraphValueKind.Dictionary, new ReadOnlyDictionary<string, NativeGraphValue>(copy));
    }
    public bool AsBoolean() => Read<bool>(NativeGraphValueKind.Boolean);
    public long AsInteger() => Read<long>(NativeGraphValueKind.Integer);
    public double AsNumber() => Kind == NativeGraphValueKind.Float ? (float)_value! : Read<double>(NativeGraphValueKind.Number);
    public string AsText() => Read<string>(NativeGraphValueKind.Text);
    public IReadOnlyList<NativeGraphValue> AsList() => Read<IReadOnlyList<NativeGraphValue>>(NativeGraphValueKind.List);
    public IReadOnlyDictionary<string, NativeGraphValue> AsDictionary() => Read<IReadOnlyDictionary<string, NativeGraphValue>>(NativeGraphValueKind.Dictionary);
    public override string ToString() => Kind switch
    {
        NativeGraphValueKind.Nil => "null",
        NativeGraphValueKind.Boolean => AsBoolean() ? "true" : "false",
        NativeGraphValueKind.Integer => AsInteger().ToString(CultureInfo.InvariantCulture),
        NativeGraphValueKind.Float => ((float)_value!).ToString("R", CultureInfo.InvariantCulture),
        NativeGraphValueKind.Number => AsNumber().ToString("R", CultureInfo.InvariantCulture),
        NativeGraphValueKind.Text => AsText(),
        NativeGraphValueKind.List => $"List[{AsList().Count}]",
        NativeGraphValueKind.Dictionary => $"Dictionary[{AsDictionary().Count}]",
        _ => throw new InvalidOperationException($"Unsupported graph value kind {Kind}.")
    };
    private T Read<T>(NativeGraphValueKind expected) => Kind == expected ? (T)_value! : throw new InvalidOperationException($"Expected {expected}, received {Kind}.");
    internal static string CheckedText(string value)
    {
        if (value == null) throw new ArgumentNullException(nameof(value));
        if (value.IndexOf('\0') >= 0) throw new ArgumentException("Native UTF-8 strings cannot contain NUL.", nameof(value));
        return value;
    }
    internal static NativeGraphValue CopyFromNative(IntPtr value) => NativeGraphValueInterop.Decode(Marshal.PtrToStructure<NativeGraphValueInterop.RawValue>(value));
}

internal static class NativeGraphValueInterop
{
    // tc_value is 32 bytes on the supported 64-bit Graphics SDK ABI.
    [StructLayout(LayoutKind.Explicit, Size = 32)]
    internal struct RawValue
    {
        [FieldOffset(0)] public int Type;
        [FieldOffset(8)] public byte Boolean;
        [FieldOffset(8)] public long Integer;
        [FieldOffset(8)] public float Float;
        [FieldOffset(8)] public double Number;
        [FieldOffset(8)] public IntPtr Items;
        [FieldOffset(16)] public UIntPtr Count;
        [FieldOffset(24)] public UIntPtr Capacity;
    }
    [StructLayout(LayoutKind.Sequential)] private struct DictEntry { public IntPtr Key, Value; }
    internal static NativeGraphValue Decode(RawValue value)
    {
        switch (value.Type)
        {
            case 0: return NativeGraphValue.Nil;
            case 1: return NativeGraphValue.Boolean(value.Boolean != 0);
            case 2: return NativeGraphValue.Integer(value.Integer);
            case 3: return NativeGraphValue.FloatingPoint(value.Float);
            case 4: return NativeGraphValue.Number(value.Number);
            case 5: return NativeGraphValue.Text(Marshal.PtrToStringUTF8(value.Items) ?? "");
            case 6:
                var list = new List<NativeGraphValue>();
                for (int i = 0, count = checked((int)value.Count.ToUInt64()); i < count; ++i)
                    list.Add(NativeGraphValue.CopyFromNative(IntPtr.Add(value.Items, checked(i * 32))));
                return NativeGraphValue.List(list);
            case 7:
                var dict = new Dictionary<string, NativeGraphValue>(StringComparer.Ordinal);
                for (int i = 0, count = checked((int)value.Count.ToUInt64()); i < count; ++i)
                {
                    var entry = Marshal.PtrToStructure<DictEntry>(IntPtr.Add(value.Items, checked(i * Marshal.SizeOf<DictEntry>())));
                    dict.Add(Marshal.PtrToStringUTF8(entry.Key) ?? throw new InvalidOperationException("Native dictionary has a null key."), NativeGraphValue.CopyFromNative(entry.Value));
                }
                return NativeGraphValue.Dictionary(dict);
            default: throw new InvalidOperationException($"Unsupported native value type {value.Type}.");
        }
    }
    internal static RawValue Encode(NativeGraphValue value)
    {
        if (IntPtr.Size != 8) throw new PlatformNotSupportedException("Native graph bindings require a 64-bit process.");
        if (value == null) throw new ArgumentNullException(nameof(value));
        switch (value.Kind)
        {
            case NativeGraphValueKind.Nil: return default;
            case NativeGraphValueKind.Boolean: return new RawValue { Type = 1, Boolean = (byte)(value.AsBoolean() ? 1 : 0) };
            case NativeGraphValueKind.Integer: return new RawValue { Type = 2, Integer = value.AsInteger() };
            case NativeGraphValueKind.Float: return new RawValue { Type = 3, Float = (float)value.AsNumber() };
            case NativeGraphValueKind.Number: return new RawValue { Type = 4, Number = value.AsNumber() };
            case NativeGraphValueKind.Text: return ValueString(value.AsText());
            case NativeGraphValueKind.List:
                var list = new RawValue { Type = 6 };
                try
                {
                    foreach (var item in value.AsList()) ListPush(ref list, Encode(item));
                    return list;
                }
                catch
                {
                    Free(ref list);
                    throw;
                }
            case NativeGraphValueKind.Dictionary:
                var dict = new RawValue { Type = 7 };
                try
                {
                    foreach (var pair in value.AsDictionary()) DictSet(ref dict, pair.Key, Encode(pair.Value));
                    return dict;
                }
                catch
                {
                    Free(ref dict);
                    throw;
                }
            default: throw new ArgumentOutOfRangeException(nameof(value));
        }
    }
    [DllImport("termin_base", EntryPoint = "tc_value_string", CallingConvention = CallingConvention.Cdecl)] private static extern RawValue ValueString([MarshalAs(UnmanagedType.LPUTF8Str)] string value);
    [DllImport("termin_base", EntryPoint = "tc_value_list_push", CallingConvention = CallingConvention.Cdecl)] private static extern void ListPush(ref RawValue list, RawValue item);
    [DllImport("termin_base", EntryPoint = "tc_value_dict_set", CallingConvention = CallingConvention.Cdecl)] private static extern void DictSet(ref RawValue dict, [MarshalAs(UnmanagedType.LPUTF8Str)] string key, RawValue item);
    [DllImport("termin_base", EntryPoint = "tc_value_free", CallingConvention = CallingConvention.Cdecl)] internal static extern void Free(ref RawValue value);
}
