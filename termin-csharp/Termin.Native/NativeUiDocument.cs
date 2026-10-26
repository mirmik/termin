using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

namespace Termin.Native;

public readonly struct NativeWidgetHandle
{
    public readonly uint Index;
    public readonly uint Generation;
    internal readonly NativeUiDocument? Owner;
    internal NativeWidgetHandle(NativeWidgetRawHandle raw, NativeUiDocument owner)
    {
        Index = raw.Index;
        Generation = raw.Generation;
        Owner = owner;
    }
    internal NativeWidgetRawHandle Raw => new() { Index = Index, Generation = Generation };
    public bool IsValid => Owner is not null && Index != uint.MaxValue && Generation != 0;
}

[StructLayout(LayoutKind.Sequential)]
internal struct NativeWidgetRawHandle
{
    internal uint Index, Generation;
    internal bool IsValid => Index != uint.MaxValue && Generation != 0;
}

[StructLayout(LayoutKind.Sequential)]
internal struct NativeUiHandle
{
    internal uint Index, Generation;
    internal bool IsValid => Index != uint.MaxValue && Generation != 0;
}

[StructLayout(LayoutKind.Sequential)]
public struct NativeUiRect
{
    public float X, Y, Width, Height;
    public NativeUiRect(float x, float y, float width, float height)
    {
        X = x;
        Y = y;
        Width = width;
        Height = height;
    }
}

/// <summary>
/// Owns a native UI document on its creating thread. Dispose attached views and
/// renderers before disposing the document. Widgets remain owned by native code.
/// </summary>
public sealed class NativeUiDocument : IDisposable
{
    private readonly int _thread = Thread.CurrentThread.ManagedThreadId;
    private NativeUiHandle _handle;
    private int _borrowers;
    private readonly List<Action> _callbackChecks = new();
    private bool _disposed;

    public NativeUiDocument(string debugName = "C# native document")
    {
        NativeRuntimeSearchPath.Configure();
        _handle = NativeUiDocumentInterop.Create();
        if (!_handle.IsValid)
            throw new InvalidOperationException("Failed to create native UI document. See native log.");
        if (!NativeUiDocumentInterop.SetDebugName(_handle, debugName))
        {
            NativeUiDocumentInterop.Destroy(_handle);
            _disposed = true;
            throw new InvalidOperationException("Failed to set native UI document name. See native log.");
        }
    }

    internal NativeUiHandle Handle
    {
        get
        {
            VerifyAccess();
            return _handle;
        }
    }
    public int LiveWidgetCount
    {
        get
        {
            VerifyAccess();
            return checked((int)NativeUiDocumentInterop.LiveWidgetCount(_handle));
        }
    }
    public int RootCount
    {
        get
        {
            VerifyAccess();
            return checked((int)NativeUiDocumentInterop.RootCount(_handle));
        }
    }
    public bool HasPointerCapture
    {
        get
        {
            VerifyAccess();
            return NativeUiDocumentInterop.PointerCapture(_handle).IsValid;
        }
    }

    public void AddRoot(NativeWidgetHandle widget)
    {
        VerifyAccess();
        if (!ReferenceEquals(widget.Owner, this) || !NativeUiDocumentInterop.AddRoot(_handle, widget.Raw))
            throw new ArgumentException("Root widget must be alive in this document. See native log.", nameof(widget));
    }

    public void RemoveRoot(NativeWidgetHandle widget)
    {
        VerifyAccess();
        if (!ReferenceEquals(widget.Owner, this) || !NativeUiDocumentInterop.RemoveRoot(_handle, widget.Raw))
            throw new ArgumentException("Widget is not a root of this document. See native log.", nameof(widget));
    }

    public bool IsAlive(NativeWidgetHandle widget)
    {
        VerifyAccess();
        return ReferenceEquals(widget.Owner, this) && NativeUiDocumentInterop.IsAlive(_handle, widget.Raw);
    }

    public void Focus(NativeWidgetHandle widget)
    {
        VerifyAccess();
        if (!ReferenceEquals(widget.Owner, this) || !NativeUiDocumentInterop.SetFocus(_handle, widget.Raw))
            throw new ArgumentException("Focused widget must be alive and focusable in this document. See native log.", nameof(widget));
        ThrowPendingCallbackExceptions();
    }

    /// <summary>Low-level document input for headless hosts; a renderer supplies platform services.</summary>
    public bool DispatchKey(NativeUiKeyEvent key)
    {
        VerifyAccess();
        bool handled = NativeUiDocumentInterop.DispatchKey(_handle, ref key) != 0;
        ThrowPendingCallbackExceptions();
        return handled;
    }

    public bool DispatchPointer(NativeUiPointerEvent pointer)
    {
        VerifyAccess();
        bool handled = NativeUiDocumentInterop.DispatchPointer(_handle, ref pointer) != 0;
        ThrowPendingCallbackExceptions();
        return handled;
    }

    public bool DispatchText(string text)
    {
        VerifyAccess();
        if (text is null)
            throw new ArgumentNullException(nameof(text));
        if (text.IndexOf('\0') >= 0)
            throw new ArgumentException("Input text must not contain NUL.", nameof(text));
        var input = new NativeUiDocumentInterop.TextEvent { Text = text };
        bool handled = NativeUiDocumentInterop.DispatchText(_handle, ref input) != 0;
        ThrowPendingCallbackExceptions();
        return handled;
    }

    public void LayoutRoots(NativeUiRect viewport)
    {
        VerifyAccess();
        if (!(viewport.Width > 0) || !(viewport.Height > 0) ||
            float.IsInfinity(viewport.Width) || float.IsInfinity(viewport.Height))
            throw new ArgumentOutOfRangeException(nameof(viewport));
        NativeUiDocumentInterop.LayoutRoots(_handle, viewport);
    }

    internal void VerifyAccess()
    {
        if (Thread.CurrentThread.ManagedThreadId != _thread)
            throw new InvalidOperationException("Native UI document must be accessed on its owning thread.");
        if (_disposed)
            throw new ObjectDisposedException(nameof(NativeUiDocument));
    }

    internal void AcquireBorrower()
    {
        VerifyAccess();
        checked
        {
            ++_borrowers;
        }
    }
    internal void ReleaseBorrower()
    {
        VerifyAccess();
        --_borrowers;
    }
    internal void RegisterCallbackCheck(Action check)
    {
        VerifyAccess();
        _callbackChecks.Add(check);
    }
    internal void UnregisterCallbackCheck(Action check)
    {
        VerifyAccess();
        _callbackChecks.Remove(check);
    }
    internal void ThrowPendingCallbackExceptions()
    {
        foreach (Action check in _callbackChecks)
            check();
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        VerifyAccess();
        if (_borrowers != 0)
            throw new InvalidOperationException("Dispose native document views and renderers before their document.");
        NativeUiDocumentInterop.Destroy(_handle);
        _disposed = true;
        GC.SuppressFinalize(this);
    }
}

internal static class NativeUiDocumentInterop
{
    private const string Dll = "termin_gui_native";
    [DllImport(Dll, EntryPoint = "tc_ui_document_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeUiHandle Create();
    [DllImport(Dll, EntryPoint = "tc_ui_document_destroy", CallingConvention = CallingConvention.Cdecl)] internal static extern void Destroy(NativeUiHandle document);
    [DllImport(Dll, EntryPoint = "tc_ui_document_set_debug_name", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetDebugName(NativeUiHandle document, [MarshalAs(UnmanagedType.LPUTF8Str)] string name);
    [DllImport(Dll, EntryPoint = "tc_ui_document_add_root", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool AddRoot(NativeUiHandle document, NativeWidgetRawHandle widget);
    [DllImport(Dll, EntryPoint = "tc_ui_document_remove_root", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool RemoveRoot(NativeUiHandle document, NativeWidgetRawHandle widget);
    [DllImport(Dll, EntryPoint = "tc_ui_document_is_alive", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool IsAlive(NativeUiHandle document, NativeWidgetRawHandle widget);
    [DllImport(Dll, EntryPoint = "tc_ui_document_live_widget_count", CallingConvention = CallingConvention.Cdecl)] internal static extern nuint LiveWidgetCount(NativeUiHandle document);
    [DllImport(Dll, EntryPoint = "tc_ui_document_root_count", CallingConvention = CallingConvention.Cdecl)] internal static extern nuint RootCount(NativeUiHandle document);
    [DllImport(Dll, EntryPoint = "tc_ui_document_pointer_capture", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRawHandle PointerCapture(NativeUiHandle document);
    [DllImport(Dll, EntryPoint = "tc_ui_document_set_focus", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetFocus(NativeUiHandle document, NativeWidgetRawHandle widget);
    [StructLayout(LayoutKind.Sequential)]
    internal struct TextEvent
    {
        [MarshalAs(UnmanagedType.LPUTF8Str)] internal string Text;
    }
    [DllImport(Dll, EntryPoint = "tc_ui_document_dispatch_key_event", CallingConvention = CallingConvention.Cdecl)] internal static extern int DispatchKey(NativeUiHandle document, ref NativeUiKeyEvent key);
    [DllImport(Dll, EntryPoint = "tc_ui_document_dispatch_pointer_event", CallingConvention = CallingConvention.Cdecl)] internal static extern int DispatchPointer(NativeUiHandle document, ref NativeUiPointerEvent pointer);
    [DllImport(Dll, EntryPoint = "tc_ui_document_dispatch_text_event", CallingConvention = CallingConvention.Cdecl)] internal static extern int DispatchText(NativeUiHandle document, ref TextEvent text);
    [DllImport(Dll, EntryPoint = "tc_ui_document_layout_roots", CallingConvention = CallingConvention.Cdecl)] internal static extern void LayoutRoots(NativeUiHandle document, NativeUiRect viewport);
}
