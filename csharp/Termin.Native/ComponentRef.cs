using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Component kind - distinguishes native vs external (scripted) components.
/// </summary>
public enum ComponentKind
{
    Native = 0,
    External = 1
}

/// <summary>
/// Non-owning reference to a tc_component.
/// Allows working with components without requiring bindings for their specific type.
/// Similar to TcComponentRef in Python bindings.
/// </summary>
public readonly struct ComponentRef
{
    private readonly IntPtr _ptr;

    /// <summary>
    /// The underlying tc_component pointer.
    /// </summary>
    public IntPtr Ptr => _ptr;

    /// <summary>
    /// Create component reference from pointer.
    /// </summary>
    public ComponentRef(IntPtr ptr)
    {
        _ptr = ptr;
    }

    /// <summary>
    /// Check if component reference is valid.
    /// </summary>
    public bool IsValid => _ptr != IntPtr.Zero;

    /// <summary>
    /// Get the component type name.
    /// </summary>
    public string? TypeName
    {
        get
        {
            if (_ptr == IntPtr.Zero) return null;
            var namePtr = TerminCore.ComponentGetTypeName(_ptr);
            return Marshal.PtrToStringUTF8(namePtr);
        }
    }

    /// <summary>
    /// Get or set whether the component is enabled.
    /// </summary>
    public bool Enabled
    {
        get => _ptr != IntPtr.Zero && TerminCore.ComponentGetEnabled(_ptr);
        set
        {
            if (_ptr != IntPtr.Zero)
                TerminCore.ComponentSetEnabled(_ptr, value);
        }
    }

    /// <summary>
    /// Get or set whether the component is active in editor.
    /// </summary>
    public bool ActiveInEditor
    {
        get => _ptr != IntPtr.Zero && TerminCore.ComponentGetActiveInEditor(_ptr);
        set
        {
            if (_ptr != IntPtr.Zero)
                TerminCore.ComponentSetActiveInEditor(_ptr, value);
        }
    }

    /// <summary>
    /// Check if this component is drawable (has drawable vtable).
    /// </summary>
    public bool IsDrawable => _ptr != IntPtr.Zero && TerminCore.ComponentGetIsDrawable(_ptr);

    /// <summary>
    /// Check if this component handles input (has input vtable).
    /// </summary>
    public bool IsInputHandler => _ptr != IntPtr.Zero && TerminCore.ComponentGetIsInputHandler(_ptr);

    /// <summary>
    /// Get the component kind (Native or External).
    /// </summary>
    public ComponentKind Kind
    {
        get
        {
            if (_ptr == IntPtr.Zero) return ComponentKind.Native;
            return (ComponentKind)TerminCore.ComponentGetKind(_ptr);
        }
    }

    /// <summary>
    /// Get the owner entity as Entity struct.
    /// Returns default Entity if component has no owner.
    /// </summary>
    public Entity GetEntity(EntityPool pool)
    {
        if (_ptr == IntPtr.Zero) return default;
        var entityId = TerminCore.ComponentGetOwnerEntityId(_ptr);
        return new Entity(pool, entityId);
    }

    /// <summary>
    /// Get the owner entity ID.
    /// </summary>
    public TcEntityId OwnerEntityId
    {
        get
        {
            if (_ptr == IntPtr.Zero)
                return new TcEntityId { Index = 0xFFFFFFFF, Generation = 0 };
            return TerminCore.ComponentGetOwnerEntityId(_ptr);
        }
    }

    // ========================================================================
    // Equality
    // ========================================================================

    public override bool Equals(object? obj)
    {
        return obj is ComponentRef other && _ptr == other._ptr;
    }

    public override int GetHashCode() => _ptr.GetHashCode();

    public static bool operator ==(ComponentRef left, ComponentRef right) => left._ptr == right._ptr;
    public static bool operator !=(ComponentRef left, ComponentRef right) => left._ptr != right._ptr;

    public override string ToString()
    {
        if (!IsValid) return "ComponentRef(invalid)";
        return $"ComponentRef({TypeName})";
    }

    // ========================================================================
    // Implicit conversions
    // ========================================================================

    public static implicit operator IntPtr(ComponentRef r) => r._ptr;
    public static implicit operator ComponentRef(IntPtr ptr) => new(ptr);
}
