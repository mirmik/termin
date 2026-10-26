using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Termin.Native;

public enum NativeNodeGraphParameterEditorKind
{
    Automatic, Boolean, Enumeration, Integer, FloatingPoint, Text
}
public sealed class NativeNodeGraphParameterChoice
{
    public NativeNodeGraphParameterChoice(string value, string label)
    {
        Value = value;
        Label = label;
    }
    public string Value
    {
        get;
    }
    public string Label
    {
        get;
    }
}
public sealed class NativeNodeGraphParameterEditor
{
    public string? Label
    {
        get; set;
    }
    public NativeNodeGraphParameterEditorKind Kind
    {
        get; set;
    }
    public double Minimum { get; set; } = -1e9;
    public double Maximum { get; set; } = 1e9;
    public double Step { get; set; } = 1;
    public int Decimals { get; set; } = 3;
    public IReadOnlyList<NativeNodeGraphParameterChoice> Choices { get; set; } = Array.Empty<NativeNodeGraphParameterChoice>();
}
public sealed class NativeNodeGraphParameterContext
{
    internal NativeNodeGraphParameterContext(string nodeId, string parameterId, NativeGraphValue value)
    {
        NodeId = nodeId;
        ParameterId = parameterId;
        Value = value;
    }
    public string NodeId
    {
        get;
    }
    public string ParameterId
    {
        get;
    }
    public NativeGraphValue Value
    {
        get;
    }
}
public sealed class NativeNodeGraphChangedEventArgs : EventArgs
{
    internal NativeNodeGraphChangedEventArgs(ulong revision)
    {
        Revision = revision;
    }
    public ulong Revision
    {
        get;
    }
}
public sealed class NativeNodeGraphParameterChangedEventArgs : EventArgs
{
    internal NativeNodeGraphParameterChangedEventArgs(string nodeId, string parameterId, NativeGraphValue value)
    {
        NodeId = nodeId;
        ParameterId = parameterId;
        Value = value;
    }
    public string NodeId
    {
        get;
    }
    public string ParameterId
    {
        get;
    }
    public NativeGraphValue Value
    {
        get;
    }
}
public enum NativeNodeGraphSemanticKind
{
    None, Node, Group, Edge, Socket
}
public sealed class NativeNodeGraphContextRequestedEventArgs : EventArgs
{
    internal NativeNodeGraphContextRequestedEventArgs(float x, float y, NativeNodeGraphSemanticKind kind, string? nodeId, string? socketId, bool output)
    {
        WorldX = x;
        WorldY = y;
        Kind = kind;
        NodeId = nodeId;
        SocketId = socketId;
        SocketIsOutput = output;
    }
    public float WorldX
    {
        get;
    }
    public float WorldY
    {
        get;
    }
    public NativeNodeGraphSemanticKind Kind
    {
        get;
    }
    public string? NodeId
    {
        get;
    }
    public string? SocketId
    {
        get;
    }
    public bool SocketIsOutput
    {
        get;
    }
}

/// <summary>
/// Owns the complete native nodegraph view and its widgets. Document and graph
/// are borrowed; dispose this view before them. All methods run on their UI thread.
/// </summary>
public sealed class NativeNodeGraphView : IDisposable
{
    private static long _nextToken;
    private static readonly ConcurrentDictionary<IntPtr, NativeNodeGraphView> Live = new();
    private static readonly NativeNodeGraphViewInterop.PresentParameter Presenter = PresentParameter;
    private static readonly NativeNodeGraphViewInterop.DestroyUserdata DestroyUserdata = ReleaseUserdata;
    private static readonly NativeNodeGraphViewInterop.RequestRender RenderCallback = RequestRenderCallback;
    private static readonly NativeNodeGraphViewInterop.GraphChanged ChangedCallback = GraphChangedCallback;
    private static readonly NativeNodeGraphViewInterop.ParameterChanged ParameterCallback = ParameterChangedCallback;
    private static readonly NativeNodeGraphViewInterop.ContextRequested ContextCallback = ContextRequestedCallback;
    private readonly NativeUiDocument _document;
    private readonly NativeNodeGraph _graph;
    private readonly Func<NativeNodeGraphParameterContext, NativeNodeGraphParameterEditor?>? _presenter;
    private readonly Dictionary<string, DescriptorMemory> _descriptorMemory = new();
    private readonly IntPtr _token;
    private NativeUiHandle _handle;
    private bool _disposed;
    private int _callbackDepth;

    public NativeNodeGraphView(NativeUiDocument document, NativeNodeGraph graph,
        Func<NativeNodeGraphParameterContext, NativeNodeGraphParameterEditor?>? parameterPresenter = null)
    {
        _document = document ?? throw new ArgumentNullException(nameof(document));
        _graph = graph ?? throw new ArgumentNullException(nameof(graph));
        _presenter = parameterPresenter;
        _document.AcquireBorrower();
        try
        {
            _graph.AcquireView();
        }
        catch
        {
            _document.ReleaseBorrower();
            throw;
        }
        _token = new IntPtr(Interlocked.Increment(ref _nextToken));
        Live[_token] = this;
        try
        {
            var config = new NativeNodeGraphViewInterop.Config
            {
                StructSize = (nuint)Marshal.SizeOf<NativeNodeGraphViewInterop.Config>(),
                Userdata = _token,
                DestroyUserdata = DestroyUserdata,
                PresentParameter = Presenter,
                RequestRender = RenderCallback,
                GraphChanged = ChangedCallback,
                ParameterChanged = ParameterCallback,
                ContextRequested = ContextCallback
            };
            _handle = NativeNodeGraphViewInterop.Create(_document.Handle, _graph.Handle, ref config);
            if (!_handle.IsValid)
                throw new InvalidOperationException("Failed to create native nodegraph view. See native log.");
            ThrowIfCallbackFailed();
            _document.RegisterCallbackCheck(ThrowIfCallbackFailed);
        }
        catch
        {
            if (_handle.IsValid)
                NativeNodeGraphViewInterop.Destroy(_handle);
            Live.TryRemove(_token, out _);
            FreeDescriptors();
            _graph.ReleaseView();
            _document.ReleaseBorrower();
            _disposed = true;
            throw;
        }
    }

    public NativeWidgetHandle RootWidget
    {
        get
        {
            VerifyAccess();
            return new NativeWidgetHandle(NativeNodeGraphViewInterop.Root(_handle), _document);
        }
    }
    public NativeUiDocument Document => _document;
    public NativeNodeGraph Graph => _graph;
    /// <summary>The last managed callback failure, copied and logged without crossing the C ABI.</summary>
    public Exception? LastCallbackError
    {
        get; private set;
    }
    public event EventHandler? RequestRender;
    public event EventHandler<NativeNodeGraphChangedEventArgs>? GraphChanged;
    public event EventHandler<NativeNodeGraphParameterChangedEventArgs>? ParameterChanged;
    public event EventHandler<NativeNodeGraphContextRequestedEventArgs>? ContextRequested;

    public void Rebuild()
    {
        VerifyAccess();
        FreeDescriptors();
        Check(NativeNodeGraphViewInterop.Rebuild(_handle), "rebuild");
        ThrowIfCallbackFailed();
    }
    /// <returns>True when a changed graph required a rebuild.</returns>
    public bool Sync()
    {
        VerifyAccess();
        Check(NativeNodeGraphViewInterop.SyncChecked(_handle, out bool changed), "sync");
        ThrowIfCallbackFailed();
        return changed;
    }
    public void SetViewport(float zoom, float offsetX, float offsetY)
    {
        VerifyAccess();
        Check(NativeNodeGraphViewInterop.SetViewport(_handle, zoom, offsetX, offsetY), "set viewport");
        ThrowIfCallbackFailed();
    }
    public NativeWidgetHandle GetParameterWidget(NativeNodeHandle node, string parameterId)
    {
        VerifyAccess();
        if (parameterId is null)
            throw new ArgumentNullException(nameof(parameterId));
        return new NativeWidgetHandle(NativeNodeGraphViewInterop.ParameterWidget(_handle, node, parameterId), _document);
    }
    public void ThrowIfCallbackFailed()
    {
        _graph.ThrowPendingCallbackException();
        if (LastCallbackError is Exception error)
        {
            LastCallbackError = null;
            throw new InvalidOperationException("A managed native-nodegraph callback failed. See error log.", error);
        }
    }
    private void VerifyAccess()
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(NativeNodeGraphView));
        _document.VerifyAccess();
        _graph.VerifyAccess();
        if (_callbackDepth != 0)
            throw new InvalidOperationException("Do not reenter or dispose the native nodegraph view from its callback.");
    }
    private void Check(bool success, string operation)
    {
        if (success)
            return;
        nuint size = NativeNodeGraphViewInterop.CopyError(_handle, IntPtr.Zero, 0);
        string message = "";
        if (size != 0)
        {
            IntPtr buffer = Marshal.AllocHGlobal(checked((int)size));
            try
            {
                NativeNodeGraphViewInterop.CopyError(_handle, buffer, size);
                message = Marshal.PtrToStringUTF8(buffer) ?? "";
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        throw new InvalidOperationException($"Native nodegraph view failed to {operation}: {message}. See native log.");
    }
    public void Dispose()
    {
        if (_disposed)
            return;
        VerifyAccess();
        NativeNodeGraphViewInterop.Destroy(_handle);
        Live.TryRemove(_token, out _);
        _document.UnregisterCallbackCheck(ThrowIfCallbackFailed);
        FreeDescriptors();
        _graph.ReleaseView();
        _document.ReleaseBorrower();
        _disposed = true;
        GC.SuppressFinalize(this);
    }
    private void FreeDescriptors()
    {
        foreach (DescriptorMemory memory in _descriptorMemory.Values)
            memory.Dispose();
        _descriptorMemory.Clear();
    }
    private void RunCallback(Action action)
    {
        ++_callbackDepth;
        try
        {
            action();
        }
        catch (Exception error)
        {
            LastCallbackError = error;
            Console.Error.WriteLine($"[Termin.Native.NodeGraphView] Managed callback failed: {error}");
        }
        finally
        {
            --_callbackDepth;
        }
    }
    private static void ReleaseUserdata(IntPtr token)
    {
        Live.TryRemove(token, out _);
    }
    private static void RequestRenderCallback(IntPtr token)
    {
        if (Live.TryGetValue(token, out var view))
            view.RunCallback(() => view.RequestRender?.Invoke(view, EventArgs.Empty));
    }
    private static void GraphChangedCallback(IntPtr token, ulong revision)
    {
        if (Live.TryGetValue(token, out var view))
            view.RunCallback(() => view.GraphChanged?.Invoke(view, new NativeNodeGraphChangedEventArgs(revision)));
    }
    private static void ParameterChangedCallback(IntPtr token, NativeNodeHandle node, IntPtr name, IntPtr value)
    {
        if (Live.TryGetValue(token, out var view))
            view.RunCallback(() => view.ParameterChanged?.Invoke(view,
            new NativeNodeGraphParameterChangedEventArgs(view._graph.GetNodeId(node), Marshal.PtrToStringUTF8(name) ?? "", NativeGraphValue.CopyFromNative(value))));
    }
    private static void ContextRequestedCallback(IntPtr token, float x, float y, IntPtr semantic)
    {
        if (!Live.TryGetValue(token, out var view))
            return;
        view.RunCallback(() =>
        {
            var hit = semantic == IntPtr.Zero ? default : Marshal.PtrToStructure<NativeNodeGraphViewInterop.Semantic>(semantic);
            string? node = hit.Node.GraphId != 0 && hit.Node.Generation != 0 ? view._graph.GetNodeId(hit.Node) : null;
            view.ContextRequested?.Invoke(view, new NativeNodeGraphContextRequestedEventArgs(x, y, hit.Kind, node,
                hit.SocketName == IntPtr.Zero ? null : Marshal.PtrToStringUTF8(hit.SocketName), hit.SocketIsOutput != 0));
        });
    }
    private static bool PresentParameter(IntPtr token, NativeNodeHandle node, IntPtr name, IntPtr value, ref NativeNodeGraphViewInterop.Editor descriptor)
    {
        if (!Live.TryGetValue(token, out var view) || view._presenter is null)
            return false;
        bool result = false;
        NativeNodeGraphViewInterop.Editor encoded = default;
        view.RunCallback(() =>
        {
            string parameterId = Marshal.PtrToStringUTF8(name) ?? "";
            string nodeId = view._graph.GetNodeId(node);
            NativeNodeGraphParameterEditor? editor = view._presenter(new NativeNodeGraphParameterContext(nodeId, parameterId, NativeGraphValue.CopyFromNative(value)));
            if (editor is null)
                return;
            var memory = new DescriptorMemory(parameterId, editor);
            string key = nodeId + "\0" + parameterId;
            if (view._descriptorMemory.TryGetValue(key, out var previous))
                previous.Dispose();
            view._descriptorMemory[key] = memory;
            encoded = memory.Descriptor;
            result = true;
        });
        if (result)
            descriptor = encoded;
        return result;
    }
    // Native code copies descriptors immediately after the callback returns.
    // Retain each allocation until its next presentation or view teardown.
    private sealed class DescriptorMemory : IDisposable
    {
        private readonly List<IntPtr> _allocations = new();
        internal NativeNodeGraphViewInterop.Editor Descriptor;
        internal DescriptorMemory(string parameterId, NativeNodeGraphParameterEditor editor)
        {
            try
            {
                if (double.IsNaN(editor.Minimum) || double.IsInfinity(editor.Minimum) ||
                    double.IsNaN(editor.Maximum) || double.IsInfinity(editor.Maximum) || editor.Minimum > editor.Maximum ||
                    !(editor.Step > 0) || double.IsInfinity(editor.Step) || editor.Decimals < 0 || editor.Decimals > 15 ||
                    !Enum.IsDefined(typeof(NativeNodeGraphParameterEditorKind), editor.Kind))
                    throw new ArgumentException("Native parameter editor requires a valid kind, finite bounds, positive finite step and 0-15 decimals.");
                Descriptor = new NativeNodeGraphViewInterop.Editor
                {
                    StructSize = (nuint)Marshal.SizeOf<NativeNodeGraphViewInterop.Editor>(),
                    Name = Utf8(parameterId),
                    Label = Utf8(editor.Label ?? parameterId),
                    Kind = editor.Kind,
                    Minimum = editor.Minimum,
                    Maximum = editor.Maximum,
                    Step = editor.Step,
                    Decimals = editor.Decimals,
                    ChoiceCount = (nuint)editor.Choices.Count
                };
                if (editor.Choices.Count > 0)
                {
                    int stride = Marshal.SizeOf<NativeNodeGraphViewInterop.Choice>();
                    Descriptor.Choices = Allocate(checked(editor.Choices.Count * stride));
                    for (int i = 0; i < editor.Choices.Count; i++)
                        Marshal.StructureToPtr(new NativeNodeGraphViewInterop.Choice { Value = Utf8(editor.Choices[i].Value), Label = Utf8(editor.Choices[i].Label) }, IntPtr.Add(Descriptor.Choices, i * stride), false);
                }
            }
            catch
            {
                Dispose();
                throw;
            }
        }
        private IntPtr Allocate(int size)
        {
            IntPtr pointer = Marshal.AllocHGlobal(size);
            _allocations.Add(pointer);
            return pointer;
        }
        private IntPtr Utf8(string text)
        {
            if (text.IndexOf('\0') >= 0)
                throw new ArgumentException("Native descriptor strings must not contain NUL.");
            byte[] bytes = Encoding.UTF8.GetBytes(text + "\0");
            IntPtr pointer = Allocate(bytes.Length);
            Marshal.Copy(bytes, 0, pointer, bytes.Length);
            return pointer;
        }
        public void Dispose()
        {
            foreach (IntPtr pointer in _allocations)
                Marshal.FreeHGlobal(pointer);
            _allocations.Clear();
        }
    }
}

internal static class NativeNodeGraphViewInterop
{
    private const string Dll = "termin_nodegraph_ui";
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void DestroyUserdata(IntPtr userdata);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal delegate bool PresentParameter(IntPtr userdata, NativeNodeHandle node, IntPtr name, IntPtr value, ref Editor descriptor);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void RequestRender(IntPtr userdata);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void GraphChanged(IntPtr userdata, ulong revision);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void ParameterChanged(IntPtr userdata, NativeNodeHandle node, IntPtr name, IntPtr value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void ContextRequested(IntPtr userdata, float x, float y, IntPtr semantic);
    [StructLayout(LayoutKind.Sequential)]
    internal struct Config
    {
        internal nuint StructSize;
        internal IntPtr Userdata;
        internal DestroyUserdata DestroyUserdata;
        internal PresentParameter PresentParameter;
        internal IntPtr CreateBody, UpdateBody;
        internal RequestRender RequestRender;
        internal GraphChanged GraphChanged;
        internal ParameterChanged ParameterChanged;
        internal ContextRequested ContextRequested;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct Editor
    {
        internal nuint StructSize;
        internal IntPtr Name, Label;
        internal NativeNodeGraphParameterEditorKind Kind;
        internal double Minimum, Maximum, Step;
        internal int Decimals;
        internal IntPtr Choices;
        internal nuint ChoiceCount;
        internal IntPtr Style;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct Choice
    {
        internal IntPtr Value, Label;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct Semantic
    {
        internal nuint StructSize;
        internal NativeNodeGraphSemanticKind Kind;
        internal NativeNodeHandle Node, Group, Edge;
        internal IntPtr SocketName;
        internal byte SocketIsOutput;
    }
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeUiHandle Create(NativeUiHandle document, NativeGraphHandle graph, ref Config config);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_destroy", CallingConvention = CallingConvention.Cdecl)] internal static extern void Destroy(NativeUiHandle view);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_root_widget", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRawHandle Root(NativeUiHandle view);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_sync", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool Sync(NativeUiHandle view);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_sync_checked", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool SyncChecked(NativeUiHandle view, [MarshalAs(UnmanagedType.I1)] out bool changed);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_rebuild", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool Rebuild(NativeUiHandle view);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_set_viewport", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetViewport(NativeUiHandle view, float zoom, float offsetX, float offsetY);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_parameter_widget", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRawHandle ParameterWidget(NativeUiHandle view, NativeNodeHandle node, [MarshalAs(UnmanagedType.LPUTF8Str)] string name);
    [DllImport(Dll, EntryPoint = "tc_nodegraph_view_copy_last_error", CallingConvention = CallingConvention.Cdecl)] internal static extern nuint CopyError(NativeUiHandle view, IntPtr buffer, nuint capacity);
}
