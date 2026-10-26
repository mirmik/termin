using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace Termin.Native;

[StructLayout(LayoutKind.Sequential)]
internal struct NativeGraphHandle
{
    internal uint Index, Generation;
    internal bool IsInvalid => Index == uint.MaxValue || Generation == 0;
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct NativeNodeHandle : IEquatable<NativeNodeHandle>
{
    public readonly ulong GraphId;
    public readonly uint Index, Generation;
    public NativeNodeHandle(ulong graphId, uint index, uint generation)
    {
        GraphId = graphId;
        Index = index;
        Generation = generation;
    }
    public bool Equals(NativeNodeHandle other) => GraphId == other.GraphId && Index == other.Index && Generation == other.Generation;
    public override bool Equals(object? other) => other is NativeNodeHandle handle && Equals(handle);
    public override int GetHashCode() => HashCode.Combine(GraphId, Index, Generation);
}

[StructLayout(LayoutKind.Sequential)]
public readonly struct NativeEdgeHandle
{
    public readonly ulong GraphId;
    public readonly uint Index, Generation;
}

public sealed class NativeSocketDescriptor
{
    public string Name { get; }
    public string SocketType { get; }
    public bool Multi { get; }
    public NativeSocketDescriptor(string name, string socketType = "any", bool multi = false)
    {
        Name = NativeGraphValue.CheckedText(name);
        SocketType = NativeGraphValue.CheckedText(socketType);
        Multi = multi;
    }
}

public sealed class NativeNodeDescriptor
{
    public string Id { get; set; } = "";
    public string Kind { get; set; } = "";
    public string Title { get; set; } = "";
    public float X { get; set; }
    public float Y { get; set; }
    public float Width { get; set; } = 190;
    public float Height { get; set; } = 120;
    public IReadOnlyList<NativeSocketDescriptor> Inputs { get; set; } = Array.Empty<NativeSocketDescriptor>();
    public IReadOnlyList<NativeSocketDescriptor> Outputs { get; set; } = Array.Empty<NativeSocketDescriptor>();
    public IReadOnlyDictionary<string, NativeGraphValue> Parameters { get; set; } = new Dictionary<string, NativeGraphValue>();
    public IReadOnlyDictionary<string, NativeGraphValue> Data { get; set; } = new Dictionary<string, NativeGraphValue>();
}

public sealed class NativeConnectionProposal
{
    public string SourceNodeId { get; }
    public string SourceSocket { get; }
    public string SourceType { get; }
    public string DestinationNodeId { get; }
    public string DestinationSocket { get; }
    public string DestinationType { get; }
    internal NativeConnectionProposal(string sourceNodeId, string sourceSocket, string sourceType, string destinationNodeId, string destinationSocket, string destinationType)
    {
        SourceNodeId = sourceNodeId;
        SourceSocket = sourceSocket;
        SourceType = sourceType;
        DestinationNodeId = destinationNodeId;
        DestinationSocket = destinationSocket;
        DestinationType = destinationType;
    }
}

public enum NativeNodeGraphResult
{
    Ok, InvalidArgument, InvalidHandle, DuplicateId, InvalidId, NodeNotFound, EdgeNotFound,
    GroupNotFound, SocketNotFound, DuplicateSocket, SelfLink, TypeMismatch, CardinalityViolation,
    InvalidValue, InternalError
}

public sealed class NativeNodeGraphException : InvalidOperationException
{
    public NativeNodeGraphResult Result { get; }
    internal NativeNodeGraphException(NativeNodeGraphResult result, string message) : base(message) { Result = result; }
}

/// <summary>
/// Owns a native authoring graph. Access and disposal belong to the creating UI thread.
/// Worker threads can consume the immutable values returned by GetSnapshot().
/// </summary>
public sealed class NativeNodeGraph : IDisposable
{
    private NativeGraphHandle _handle;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly ValidatorState? _validator;
    private int _views;
    public bool IsDisposed { get; private set; }
    internal NativeGraphHandle Handle
    {
        get
        {
            VerifyAccess();
            return _handle;
        }
    }

    private sealed class ValidatorState
    {
        internal readonly Func<NativeConnectionProposal, bool> Validator;
        internal bool InCallback;
        internal Exception? Error;
        internal ValidatorState(Func<NativeConnectionProposal, bool> validator) { Validator = validator; }
    }
    private static readonly NativeNodeGraphInterop.Validator ValidateCallback = Validate;
    private static readonly NativeNodeGraphInterop.Deleter ReleaseCallback = ReleaseValidator;
    // The C ABI serializes access to every graph with one nonrecursive mutex.
    // Reading a different graph from a validator would also deadlock.
    private static readonly ConcurrentDictionary<int, byte> ValidatorThreads = new();

    public NativeNodeGraph(Func<NativeConnectionProposal, bool>? validator = null)
    {
        if (ValidatorThreads.ContainsKey(Environment.CurrentManagedThreadId))
            throw new InvalidOperationException("A connection validator must not create native graphs recursively.");
        if (IntPtr.Size != 8) throw new PlatformNotSupportedException("Native graph bindings require a 64-bit process.");
        NativeRuntimeSearchPath.Configure();
        if (validator == null) _handle = NativeNodeGraphInterop.Create();
        else
        {
            _validator = new ValidatorState(validator);
            var root = GCHandle.Alloc(_validator);
            try
            {
                _handle = NativeNodeGraphInterop.CreateWithValidator(ValidateCallback, GCHandle.ToIntPtr(root), ReleaseCallback);
            }
            catch
            {
                root.Free();
                throw;
            }
            // The native validator owns root from this point, including when a view leases the graph.
        }
        if (_handle.IsInvalid) throw new InvalidOperationException("Native nodegraph creation failed; see native log.");
    }

    private static bool Validate(IntPtr userdata, IntPtr proposal)
    {
        var state = (ValidatorState)GCHandle.FromIntPtr(userdata).Target!;
        try
        {
            state.InCallback = true;
            ValidatorThreads[Environment.CurrentManagedThreadId] = 0;
            var value = Marshal.PtrToStructure<NativeNodeGraphInterop.Proposal>(proposal);
            string Text(IntPtr pointer) => Marshal.PtrToStringUTF8(pointer) ?? "";
            return state.Validator(new NativeConnectionProposal(Text(value.SourceNodeId), Text(value.SourceSocket), Text(value.SourceType), Text(value.DestinationNodeId), Text(value.DestinationSocket), Text(value.DestinationType)));
        }
        catch (Exception error)
        {
            state.Error = error;
            Console.Error.WriteLine($"[Termin.Native.NativeNodeGraph] Connection validator failed: {error}");
            return false;
        }
        finally
        {
            state.InCallback = false;
            ValidatorThreads.TryRemove(Environment.CurrentManagedThreadId, out _);
        }
    }
    private static void ReleaseValidator(IntPtr userdata)
    {
        try { GCHandle.FromIntPtr(userdata).Free(); }
        catch (Exception error) { Console.Error.WriteLine($"[Termin.Native.NativeNodeGraph] Validator release failed: {error}"); }
    }
    internal void VerifyAccess()
    {
        if (IsDisposed) throw new ObjectDisposedException(nameof(NativeNodeGraph));
        if (Environment.CurrentManagedThreadId != _thread) throw new InvalidOperationException("Native graph access requires its owning UI thread.");
        if (_validator?.InCallback == true || ValidatorThreads.ContainsKey(Environment.CurrentManagedThreadId))
            throw new InvalidOperationException("A connection validator must not access native graphs recursively.");
    }
    internal void AcquireView()
    {
        VerifyAccess();
        checked { ++_views; }
    }

    internal void ReleaseView()
    {
        VerifyAccess();
        if (_views <= 0) throw new InvalidOperationException("Unbalanced graph view lease.");
        --_views;
    }
    internal void ThrowPendingCallbackException()
    {
        if (_validator?.Error is Exception error)
        {
            _validator.Error = null;
            throw new InvalidOperationException("Managed connection validator failed; the native connection was rejected.", error);
        }
    }
    private void Check(NativeNodeGraphResult result)
    {
        ThrowPendingCallbackException();
        if (result == NativeNodeGraphResult.Ok) return;
        string message = CopyString((buffer, size) => NativeNodeGraphInterop.CopyError(_handle, buffer, size));
        if (message.Length == 0) message = $"Native nodegraph operation failed: {result}.";
        Console.Error.WriteLine($"[Termin.Native.NativeNodeGraph] {message}");
        throw new NativeNodeGraphException(result, message);
    }
    public ulong Id
    {
        get { VerifyAccess(); return NativeNodeGraphInterop.Id(_handle); }
    }

    public ulong Revision
    {
        get { VerifyAccess(); return NativeNodeGraphInterop.Revision(_handle); }
    }

    public int NodeCount
    {
        get { VerifyAccess(); return checked((int)NativeNodeGraphInterop.NodeCount(_handle).ToUInt64()); }
    }

    public int EdgeCount
    {
        get { VerifyAccess(); return checked((int)NativeNodeGraphInterop.EdgeCount(_handle).ToUInt64()); }
    }
    public NativeNodeHandle CreateNode(NativeNodeDescriptor descriptor)
    {
        VerifyAccess();
        if (descriptor == null) throw new ArgumentNullException(nameof(descriptor));
        using var arena = new NativeNodeGraphInterop.Arena();
        var raw = new NativeNodeGraphInterop.NodeDescriptor
        {
            StructSize = (UIntPtr)Marshal.SizeOf<NativeNodeGraphInterop.NodeDescriptor>(),
            Id = arena.Text(descriptor.Id),
            Kind = arena.Text(descriptor.Kind),
            Title = arena.Text(descriptor.Title),
            X = descriptor.X,
            Y = descriptor.Y,
            Width = descriptor.Width,
            Height = descriptor.Height,
            Inputs = arena.Sockets(descriptor.Inputs),
            InputCount = (UIntPtr)descriptor.Inputs.Count,
            Outputs = arena.Sockets(descriptor.Outputs),
            OutputCount = (UIntPtr)descriptor.Outputs.Count,
            Parameters = arena.Value(NativeGraphValue.Dictionary(descriptor.Parameters)),
            Data = arena.Value(NativeGraphValue.Dictionary(descriptor.Data))
        };
        Check(NativeNodeGraphInterop.CreateNode(_handle, ref raw, out var node));
        return node;
    }
    public NativeNodeHandle FindNode(string id)
    {
        if (!TryFindNode(id, out var node)) throw new KeyNotFoundException($"Native graph node '{id}' was not found.");
        return node;
    }
    public bool TryFindNode(string id, out NativeNodeHandle node)
    {
        VerifyAccess();
        return NativeNodeGraphInterop.FindNode(_handle, NativeGraphValue.CheckedText(id), out node);
    }
    public string GetNodeId(NativeNodeHandle node) => GetNodeSnapshot(node).AsDictionary()["id"].AsText();
    public void RemoveNode(NativeNodeHandle node)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.RemoveNode(_handle, node));
    }

    public void MoveNode(NativeNodeHandle node, float x, float y)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.MoveNode(_handle, node, x, y));
    }
    public void AddInput(NativeNodeHandle node, NativeSocketDescriptor socket) => AddSocket(node, socket, false);
    public void AddOutput(NativeNodeHandle node, NativeSocketDescriptor socket) => AddSocket(node, socket, true);
    private void AddSocket(NativeNodeHandle node, NativeSocketDescriptor socket, bool output)
    {
        VerifyAccess();
        using var arena = new NativeNodeGraphInterop.Arena();
        var raw = arena.Socket(socket);
        Check(output ? NativeNodeGraphInterop.AddOutput(_handle, node, ref raw) : NativeNodeGraphInterop.AddInput(_handle, node, ref raw));
    }
    public void SetParameter(NativeNodeHandle node, string name, NativeGraphValue value)
    {
        VerifyAccess();
        var raw = NativeGraphValueInterop.Encode(value);
        try { Check(NativeNodeGraphInterop.SetParameter(_handle, node, NativeGraphValue.CheckedText(name), ref raw)); }
        finally { NativeGraphValueInterop.Free(ref raw); }
    }
    public void SetNodeData(NativeNodeHandle node, IReadOnlyDictionary<string, NativeGraphValue> data)
    {
        VerifyAccess();
        var raw = NativeGraphValueInterop.Encode(NativeGraphValue.Dictionary(data));
        try { Check(NativeNodeGraphInterop.SetNodeData(_handle, node, ref raw)); }
        finally { NativeGraphValueInterop.Free(ref raw); }
    }
    public void SetData(IReadOnlyDictionary<string, NativeGraphValue> data)
    {
        VerifyAccess();
        var raw = NativeGraphValueInterop.Encode(NativeGraphValue.Dictionary(data));
        try { Check(NativeNodeGraphInterop.SetData(_handle, ref raw)); }
        finally { NativeGraphValueInterop.Free(ref raw); }
    }
    public NativeEdgeHandle Connect(NativeNodeHandle source, string sourceSocket, NativeNodeHandle destination, string destinationSocket, string? edgeId = null)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.Connect(_handle, source, NativeGraphValue.CheckedText(sourceSocket), destination, NativeGraphValue.CheckedText(destinationSocket), edgeId == null ? null : NativeGraphValue.CheckedText(edgeId), out var edge));
        return edge;
    }
    public void RemoveEdge(NativeEdgeHandle edge)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.RemoveEdge(_handle, edge));
    }
    public NativeGraphValue GetNodeSnapshot(NativeNodeHandle node)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.CopyNode(_handle, node, out var value));
        try { return NativeGraphValueInterop.Decode(value); } finally { NativeGraphValueInterop.Free(ref value); }
    }
    public NativeGraphValue GetEdgeSnapshot(NativeEdgeHandle edge)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.CopyEdge(_handle, edge, out var value));
        try { return NativeGraphValueInterop.Decode(value); } finally { NativeGraphValueInterop.Free(ref value); }
    }
    public NativeGraphValue GetSnapshot()
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.Serialize(_handle, out var value));
        try { return NativeGraphValueInterop.Decode(value); } finally { NativeGraphValueInterop.Free(ref value); }
    }
    public void Replace(NativeGraphValue snapshot)
    {
        VerifyAccess();
        var raw = NativeGraphValueInterop.Encode(snapshot);
        try { Check(NativeNodeGraphInterop.Replace(_handle, ref raw)); } finally { NativeGraphValueInterop.Free(ref raw); }
    }
    /// <summary>Native JSON interchange. Use GetSnapshot()/Replace() for exact typed numeric snapshots.</summary>
    public string ToJson(int indent = -1)
    {
        VerifyAccess();
        return CopyString((buffer, size) => NativeNodeGraphInterop.CopyJson(_handle, indent, buffer, size));
    }

    public void ReplaceJson(string json)
    {
        VerifyAccess();
        Check(NativeNodeGraphInterop.ReplaceJson(_handle, NativeGraphValue.CheckedText(json)));
    }
    internal static string CopyString(Func<IntPtr, UIntPtr, UIntPtr> copy)
    {
        int size = checked((int)copy(IntPtr.Zero, UIntPtr.Zero).ToUInt64());
        if (size == 0) return "";
        IntPtr buffer = Marshal.AllocHGlobal(size);
        try
        {
            if (copy(buffer, (UIntPtr)size).ToUInt64() > (ulong)size) throw new InvalidOperationException("Native string changed while copying.");
            return Marshal.PtrToStringUTF8(buffer) ?? "";
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }
    public void Dispose()
    {
        if (IsDisposed) return;
        VerifyAccess();
        if (_views != 0) throw new InvalidOperationException("Dispose native graph views before disposing their graph.");
        NativeNodeGraphInterop.Destroy(_handle);
        IsDisposed = true;
        _handle = default;
        GC.SuppressFinalize(this);
    }
    ~NativeNodeGraph()
    {
        if (!IsDisposed && !_handle.IsInvalid)
        {
            try { NativeNodeGraphInterop.Destroy(_handle); }
            catch (Exception error) { Console.Error.WriteLine($"[Termin.Native.NativeNodeGraph] Finalizer release failed: {error}"); }
        }
    }
}
