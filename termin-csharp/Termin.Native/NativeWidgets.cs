using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>A generation-checked reference to a widget owned by a native document.</summary>
public class NativeWidgetRef
{
    internal NativeWidgetRef(NativeUiDocument document, NativeWidgetRefInterop reference)
    {
        if (!reference.Handle.IsValid)
            throw new InvalidOperationException("Failed to create native widget. See native log.");
        Document = document;
        Reference = reference;
    }

    private protected NativeWidgetRefInterop Reference { get; }
    public NativeUiDocument Document { get; }
    public NativeWidgetHandle Handle => new(Reference.Handle, Document);
    public bool IsAlive => !Document.IsDisposed && Document.IsAlive(Handle);

    /// <summary>Last laid-out bounds in document logical coordinates.</summary>
    public NativeUiRect Bounds
    {
        get
        {
            VerifyAlive();
            Require(NativeWidgetInterop.GetBounds(Reference, out NativeUiRect value), "read bounds");
            return value;
        }
    }

    public bool Visible
    {
        get
        {
            VerifyAlive();
            Require(NativeWidgetInterop.GetVisible(Reference, out bool value), "read visibility");
            return value;
        }
        set
        {
            VerifyMutation();
            Require(NativeWidgetInterop.SetVisible(Reference, value), "set visibility");
            Document.ThrowPendingCallbackExceptions();
        }
    }

    public bool Enabled
    {
        get
        {
            VerifyAlive();
            Require(NativeWidgetInterop.GetEnabled(Reference, out bool value), "read enabled state");
            return value;
        }
        set
        {
            VerifyMutation();
            Require(NativeWidgetInterop.SetEnabled(Reference, value), "set enabled state");
            Document.ThrowPendingCallbackExceptions();
        }
    }

    public void RemoveChild(NativeWidgetRef child)
    {
        VerifyMutation();
        Require(NativeWidgetInterop.RemoveChild(Reference, ChildReference(child)), "remove child");
        Document.ThrowPendingCallbackExceptions();
    }

    /// <summary>Destroy this widget and its descendants, invalidating all references.</summary>
    public void Destroy()
    {
        VerifyMutation();
        Require(NativeWidgetInterop.Destroy(Reference), "destroy");
        Document.ThrowPendingCallbackExceptions();
    }

    private protected NativeWidgetRefInterop ChildReference(NativeWidgetRef child)
    {
        if (child is null)
            throw new ArgumentNullException(nameof(child));
        if (!ReferenceEquals(Document, child.Document))
            throw new ArgumentException("Child belongs to another document.", nameof(child));
        child.VerifyAlive();
        return child.Reference;
    }

    private protected void VerifyAlive()
    {
        Document.VerifyAccess();
        if (!IsAlive)
            throw new InvalidOperationException("Native widget reference is stale.");
    }

    private protected void VerifyMutation()
    {
        Document.VerifyOutsideWidgetCallback();
        VerifyAlive();
    }

    private protected static NativeUiHandle CreateIn(NativeUiDocument document)
    {
        if (document is null)
            throw new ArgumentNullException(nameof(document));
        document.VerifyOutsideWidgetCallback();
        return document.Handle;
    }

    private protected static string ValidateText(string text)
    {
        if (text is null)
            throw new ArgumentNullException(nameof(text));
        if (text.IndexOf('\0') >= 0)
            throw new ArgumentException("Widget text must not contain NUL.", nameof(text));
        return text;
    }

    private protected static void Require(bool success, string operation)
    {
        if (!success)
            throw new InvalidOperationException($"Native widget failed to {operation}. See native log.");
    }

    // Native consumes the userdata on every normal return. Interop failures
    // before the call still belong to the caller.
    private protected static T RegisterCallback<T>(object target, Func<IntPtr, T> register)
    {
        var handle = GCHandle.Alloc(target);
        try
        {
            return register(GCHandle.ToIntPtr(handle));
        }
        catch
        {
            handle.Free();
            throw;
        }
    }
}

public enum NativeBoxSizing { Fixed, Preferred, Flex, Stretch }

public sealed class NativeBoxLayout : NativeWidgetRef
{
    public NativeBoxLayout(NativeUiDocument document, bool vertical = true)
        : base(document, NativeWidgetInterop.CreateBox(CreateIn(document), vertical ? 1 : 0)) { }

    public float Spacing
    {
        set
        {
            VerifyMutation();
            Require(NativeWidgetInterop.SetSpacing(Reference, value), "set spacing");
        }
    }

    /// <summary>Attach or reparent a widget using the native box's size policy.</summary>
    public void AddChild(NativeWidgetRef child, NativeBoxSizing sizing = NativeBoxSizing.Flex, float value = 1)
    {
        VerifyMutation();
        Require(NativeWidgetInterop.AddChild(Reference, ChildReference(child), sizing, value), "add box child");
        Document.ThrowPendingCallbackExceptions();
    }
}

public sealed class NativeButton : NativeWidgetRef
{
    private static readonly NativeWidgetInterop.Activate ClickCallback = OnClick;
    private static readonly NativeWidgetInterop.Release ReleaseClickCallback = ReleaseClick;
    private EventHandler? _clicked;
    private nuint _connection;

    public NativeButton(NativeUiDocument document, string text)
        : base(document, NativeWidgetInterop.CreateButton(CreateIn(document), ValidateText(text))) { }

    public string Text
    {
        set
        {
            VerifyAlive();
            Require(NativeWidgetInterop.SetButtonText(Reference, ValidateText(value)), "set button text");
        }
    }

    /// <summary>Raised by native pointer or keyboard dispatch.</summary>
    public event EventHandler? Clicked
    {
        add
        {
            VerifyMutation();
            if (value is null)
                return;
            if (_connection == 0)
            {
                _connection = RegisterCallback(this, token =>
                    NativeWidgetInterop.ConnectClicked(Reference, ClickCallback, token, ReleaseClickCallback));
                Require(_connection != 0, "connect button activation");
            }
            _clicked += value;
        }
        remove
        {
            if (_connection == 0 || value is null)
                return;
            VerifyMutation();
            var remaining = _clicked - value;
            if (remaining is null)
                Require(NativeWidgetInterop.DisconnectClicked(Reference, _connection), "disconnect button activation");
            else
                _clicked = remaining;
        }
    }

    private static void OnClick(IntPtr token)
    {
        var button = (NativeButton)GCHandle.FromIntPtr(token).Target!;
        button.Document.RunWidgetCallback(() =>
        {
            button._clicked?.Invoke(button, EventArgs.Empty);
            return true;
        }, false);
    }

    private static void ReleaseClick(IntPtr token)
    {
        var handle = GCHandle.FromIntPtr(token);
        var button = (NativeButton)handle.Target!;
        button._connection = 0;
        button._clicked = null;
        handle.Free();
    }
}

public sealed class NativeLabel : NativeWidgetRef
{
    public NativeLabel(NativeUiDocument document, string text)
        : base(document, NativeWidgetInterop.CreateLabel(CreateIn(document), ValidateText(text))) { }

    public string Text
    {
        set
        {
            VerifyAlive();
            Require(NativeWidgetInterop.SetLabelText(Reference, ValidateText(value)), "set label text");
        }
    }
}

/// <summary>Native widget that borrows a retained scene. Keep its owner alive until the view is destroyed.</summary>
public sealed class NativeSceneView : NativeWidgetRef
{
    private static readonly NativeWidgetInterop.Pointer PointerCallback = OnPointer;
    private static readonly NativeWidgetInterop.Release ReleasePointerCallback = token => GCHandle.FromIntPtr(token).Free();

    public NativeSceneView(NativeUiDocument document, TcVisualScene2D scene)
        : base(document, NativeWidgetInterop.CreateSceneView(CreateIn(document), SceneHandle(scene))) { }

    public bool NavigationEnabled
    {
        set
        {
            VerifyMutation();
            Require(NativeWidgetInterop.SetNavigationEnabled(Reference, value), "set scene navigation");
        }
    }

    public bool ShowGrid
    {
        set
        {
            VerifyAlive();
            Require(NativeWidgetInterop.SetGridVisible(Reference, value), "set scene grid visibility");
        }
    }

    /// <summary>Handle explicit pointer dispatch. X and Y use scene-local coordinates.</summary>
    public Func<NativeUiPointerEvent, bool>? PointerHandler
    {
        set
        {
            VerifyMutation();
            bool registered = value is null
                ? NativeWidgetInterop.SetPointerHandler(Reference, null, IntPtr.Zero, null)
                : RegisterCallback((Document, value), token =>
                    NativeWidgetInterop.SetPointerHandler(Reference, PointerCallback, token, ReleasePointerCallback));
            Require(registered, "set scene input handler");
        }
    }

    private static VisualSceneNativeHandle SceneHandle(TcVisualScene2D scene)
    {
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));
        if (!scene.IsValid)
            throw new ArgumentException("Scene must be alive.", nameof(scene));
        return scene.NativeHandle;
    }

    private static bool OnPointer(IntPtr token, float x, float y, ref NativeUiPointerEvent pointer)
    {
        var (document, handler) = ((NativeUiDocument, Func<NativeUiPointerEvent, bool>))GCHandle.FromIntPtr(token).Target!;
        var input = pointer;
        input.X = x;
        input.Y = y;
        return document.RunWidgetCallback(() => handler(input), false);
    }
}

[StructLayout(LayoutKind.Sequential)]
internal readonly struct NativeWidgetRefInterop
{
    internal readonly NativeUiHandle Document;
    internal readonly NativeWidgetRawHandle Handle;

    internal NativeWidgetRefInterop(NativeUiHandle document, NativeWidgetRawHandle handle)
    {
        Document = document;
        Handle = handle;
    }
}

internal static class NativeWidgetInterop
{
    private const string Dll = "termin_gui_native";
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void Activate(IntPtr userdata);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void Release(IntPtr userdata);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal delegate bool Pointer(IntPtr userdata, float x, float y, [In] ref NativeUiPointerEvent pointer);

    [DllImport(Dll, EntryPoint = "tc_ui_box_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRefInterop CreateBox(NativeUiHandle document, int orientation);
    [DllImport(Dll, EntryPoint = "tc_ui_button_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRefInterop CreateButton(NativeUiHandle document, [MarshalAs(UnmanagedType.LPUTF8Str)] string text);
    [DllImport(Dll, EntryPoint = "tc_ui_label_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRefInterop CreateLabel(NativeUiHandle document, [MarshalAs(UnmanagedType.LPUTF8Str)] string text);
    [DllImport(Dll, EntryPoint = "tc_ui_scene_view_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeWidgetRefInterop CreateSceneView(NativeUiHandle document, VisualSceneNativeHandle scene);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_get_bounds", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool GetBounds(NativeWidgetRefInterop widget, out NativeUiRect bounds);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_get_visible", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool GetVisible(NativeWidgetRefInterop widget, [MarshalAs(UnmanagedType.I1)] out bool visible);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_set_visible", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetVisible(NativeWidgetRefInterop widget, [MarshalAs(UnmanagedType.I1)] bool visible);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_get_enabled", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool GetEnabled(NativeWidgetRefInterop widget, [MarshalAs(UnmanagedType.I1)] out bool enabled);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_set_enabled", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetEnabled(NativeWidgetRefInterop widget, [MarshalAs(UnmanagedType.I1)] bool enabled);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_remove_child", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool RemoveChild(NativeWidgetRefInterop parent, NativeWidgetRefInterop child);
    [DllImport(Dll, EntryPoint = "tc_ui_widget_ref_destroy", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool Destroy(NativeWidgetRefInterop widget);
    [DllImport(Dll, EntryPoint = "tc_ui_box_add_child", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool AddChild(NativeWidgetRefInterop box, NativeWidgetRefInterop child, NativeBoxSizing sizing, float value);
    [DllImport(Dll, EntryPoint = "tc_ui_box_set_spacing", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetSpacing(NativeWidgetRefInterop box, float spacing);
    [DllImport(Dll, EntryPoint = "tc_ui_button_set_text", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetButtonText(NativeWidgetRefInterop button, [MarshalAs(UnmanagedType.LPUTF8Str)] string text);
    [DllImport(Dll, EntryPoint = "tc_ui_label_set_text", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetLabelText(NativeWidgetRefInterop label, [MarshalAs(UnmanagedType.LPUTF8Str)] string text);
    [DllImport(Dll, EntryPoint = "tc_ui_button_connect_clicked", CallingConvention = CallingConvention.Cdecl)] internal static extern nuint ConnectClicked(NativeWidgetRefInterop button, Activate fn, IntPtr userdata, Release release);
    [DllImport(Dll, EntryPoint = "tc_ui_button_disconnect_clicked", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool DisconnectClicked(NativeWidgetRefInterop button, nuint connection);
    [DllImport(Dll, EntryPoint = "tc_ui_scene_view_set_pointer_handler", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetPointerHandler(NativeWidgetRefInterop view, Pointer? fn, IntPtr userdata, Release? release);
    [DllImport(Dll, EntryPoint = "tc_ui_scene_view_set_navigation_enabled", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetNavigationEnabled(NativeWidgetRefInterop view, [MarshalAs(UnmanagedType.I1)] bool enabled);
    [DllImport(Dll, EntryPoint = "tc_ui_scene_view_set_grid_visible", CallingConvention = CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetGridVisible(NativeWidgetRefInterop view, [MarshalAs(UnmanagedType.I1)] bool visible);
}
