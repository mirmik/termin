using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace Termin.Native;

internal static class NativeNodeGraphInterop
{
    private const string Library = "termin_nodegraph_core";
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal delegate bool Validator(IntPtr userdata, IntPtr proposal);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void Deleter(IntPtr userdata);
    [StructLayout(LayoutKind.Sequential)]
    internal struct Proposal
    {
        internal UIntPtr StructSize;
        internal IntPtr SourceNodeId, SourceSocket, SourceType;
        internal IntPtr DestinationNodeId, DestinationSocket, DestinationType;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct SocketDescriptor
    {
        internal UIntPtr StructSize;
        internal IntPtr Name, SocketType;
        internal byte Multi;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct NodeDescriptor
    {
        internal UIntPtr StructSize;
        internal IntPtr Id, Kind, Title;
        internal float X, Y, Width, Height;
        internal IntPtr Inputs;
        internal UIntPtr InputCount;
        internal IntPtr Outputs;
        internal UIntPtr OutputCount;
        internal IntPtr Parameters, Data;
    }
    internal sealed class Arena : IDisposable
    {
        private readonly List<IntPtr> _allocations = new();
        private readonly List<IntPtr> _values = new();
        internal IntPtr Text(string text)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(NativeGraphValue.CheckedText(text) + "\0");
            IntPtr pointer = Marshal.AllocHGlobal(bytes.Length);
            _allocations.Add(pointer);
            Marshal.Copy(bytes, 0, pointer, bytes.Length);
            return pointer;
        }
        internal SocketDescriptor Socket(NativeSocketDescriptor socket)
        {
            if (socket == null) throw new ArgumentNullException(nameof(socket));
            return new SocketDescriptor
            {
                StructSize = (UIntPtr)Marshal.SizeOf<SocketDescriptor>(),
                Name = Text(socket.Name),
                SocketType = Text(socket.SocketType),
                Multi = (byte)(socket.Multi ? 1 : 0)
            };
        }
        internal IntPtr Sockets(IReadOnlyList<NativeSocketDescriptor> sockets)
        {
            if (sockets == null) throw new ArgumentNullException(nameof(sockets));
            if (sockets.Count == 0) return IntPtr.Zero;
            int stride = Marshal.SizeOf<SocketDescriptor>();
            IntPtr pointer = Marshal.AllocHGlobal(checked(stride * sockets.Count));
            _allocations.Add(pointer);
            for (int i = 0; i < sockets.Count; ++i) Marshal.StructureToPtr(Socket(sockets[i]), IntPtr.Add(pointer, checked(i * stride)), false);
            return pointer;
        }
        internal IntPtr Value(NativeGraphValue value)
        {
            IntPtr pointer = Marshal.AllocHGlobal(32);
            _allocations.Add(pointer);
            var raw = NativeGraphValueInterop.Encode(value);
            Marshal.StructureToPtr(raw, pointer, false);
            _values.Add(pointer);
            return pointer;
        }
        public void Dispose()
        {
            foreach (var pointer in _values)
            {
                var value = Marshal.PtrToStructure<NativeGraphValueInterop.RawValue>(pointer);
                NativeGraphValueInterop.Free(ref value);
            }
            foreach (var pointer in _allocations) Marshal.FreeHGlobal(pointer);
            _values.Clear();
            _allocations.Clear();
        }
    }
    [DllImport(Library, EntryPoint = "tc_nodegraph_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeGraphHandle Create();
    [DllImport(Library, EntryPoint = "tc_nodegraph_create_with_validator", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeGraphHandle CreateWithValidator(Validator validator, IntPtr userdata, Deleter deleter);
    [DllImport(Library, EntryPoint = "tc_nodegraph_destroy", CallingConvention = CallingConvention.Cdecl)] internal static extern void Destroy(NativeGraphHandle graph);
    [DllImport(Library, EntryPoint = "tc_nodegraph_id", CallingConvention = CallingConvention.Cdecl)] internal static extern ulong Id(NativeGraphHandle graph);
    [DllImport(Library, EntryPoint = "tc_nodegraph_revision", CallingConvention = CallingConvention.Cdecl)] internal static extern ulong Revision(NativeGraphHandle graph);
    [DllImport(Library, EntryPoint = "tc_nodegraph_node_count", CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr NodeCount(NativeGraphHandle graph);
    [DllImport(Library, EntryPoint = "tc_nodegraph_edge_count", CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr EdgeCount(NativeGraphHandle graph);
    [DllImport(Library, EntryPoint = "tc_nodegraph_copy_last_error", CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr CopyError(NativeGraphHandle graph, IntPtr buffer, UIntPtr capacity);
    [DllImport(Library, EntryPoint = "tc_nodegraph_find_node", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool FindNode(NativeGraphHandle graph, [MarshalAs(UnmanagedType.LPUTF8Str)] string id, out NativeNodeHandle node);
    [DllImport(Library, EntryPoint = "tc_nodegraph_create_node", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult CreateNode(NativeGraphHandle graph, ref NodeDescriptor descriptor, out NativeNodeHandle node);
    [DllImport(Library, EntryPoint = "tc_nodegraph_remove_node", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult RemoveNode(NativeGraphHandle graph, NativeNodeHandle node);
    [DllImport(Library, EntryPoint = "tc_nodegraph_move_node", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult MoveNode(NativeGraphHandle graph, NativeNodeHandle node, float x, float y);
    [DllImport(Library, EntryPoint = "tc_nodegraph_add_input", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult AddInput(NativeGraphHandle graph, NativeNodeHandle node, ref SocketDescriptor socket);
    [DllImport(Library, EntryPoint = "tc_nodegraph_add_output", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult AddOutput(NativeGraphHandle graph, NativeNodeHandle node, ref SocketDescriptor socket);
    [DllImport(Library, EntryPoint = "tc_nodegraph_set_node_param", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult SetParameter(NativeGraphHandle graph, NativeNodeHandle node, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, ref NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_set_node_data", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult SetNodeData(NativeGraphHandle graph, NativeNodeHandle node, ref NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_set_data", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult SetData(NativeGraphHandle graph, ref NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_connect", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult Connect(NativeGraphHandle graph, NativeNodeHandle source, [MarshalAs(UnmanagedType.LPUTF8Str)] string sourceSocket, NativeNodeHandle destination, [MarshalAs(UnmanagedType.LPUTF8Str)] string destinationSocket, [MarshalAs(UnmanagedType.LPUTF8Str)] string? edgeId, out NativeEdgeHandle edge);
    [DllImport(Library, EntryPoint = "tc_nodegraph_remove_edge", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult RemoveEdge(NativeGraphHandle graph, NativeEdgeHandle edge);
    [DllImport(Library, EntryPoint = "tc_nodegraph_copy_node_value", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult CopyNode(NativeGraphHandle graph, NativeNodeHandle node, out NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_copy_edge_value", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult CopyEdge(NativeGraphHandle graph, NativeEdgeHandle edge, out NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_serialize", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult Serialize(NativeGraphHandle graph, out NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_replace", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult Replace(NativeGraphHandle graph, ref NativeGraphValueInterop.RawValue value);
    [DllImport(Library, EntryPoint = "tc_nodegraph_copy_json", CallingConvention = CallingConvention.Cdecl)] internal static extern UIntPtr CopyJson(NativeGraphHandle graph, int indent, IntPtr buffer, UIntPtr capacity);
    [DllImport(Library, EntryPoint = "tc_nodegraph_replace_json", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeNodeGraphResult ReplaceJson(NativeGraphHandle graph, [MarshalAs(UnmanagedType.LPUTF8Str)] string json);
}
