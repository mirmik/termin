using System;
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
    // Field Access (Inspect System)
    // ========================================================================

    /// <summary>
    /// Set a field by path. Supports int, long, float, double, bool, string.
    /// For mesh/material handles, use SetFieldMesh/SetFieldMaterial.
    /// Note: scene parameter is currently unused, pass null.
    /// </summary>
    public void SetField(string path, object value, Scene? scene = null)
    {
        if (_ptr == IntPtr.Zero || path == null) return;
        // Entity_lib functions still use IntPtr for scene, pass zero for now
        var scenePtr = IntPtr.Zero;

        switch (value)
        {
            case bool b:
                TerminCore.ComponentSetFieldBool(_ptr, path, b, scenePtr);
                break;
            case int i:
                TerminCore.ComponentSetFieldInt(_ptr, path, i, scenePtr);
                break;
            case long l:
                TerminCore.ComponentSetFieldInt(_ptr, path, l, scenePtr);
                break;
            case float f:
                TerminCore.ComponentSetFieldFloat(_ptr, path, f, scenePtr);
                break;
            case double d:
                TerminCore.ComponentSetFieldDouble(_ptr, path, d, scenePtr);
                break;
            case string s:
                TerminCore.ComponentSetFieldString(_ptr, path, s, scenePtr);
                break;
            case TcMeshHandle mh:
                TerminCore.ComponentSetFieldMesh(_ptr, path, mh, scenePtr);
                break;
            case TcMaterialHandle matH:
                TerminCore.ComponentSetFieldMaterial(_ptr, path, matH, scenePtr);
                break;
            case TcVec3 v3:
                TerminCore.ComponentSetFieldVec3(_ptr, path, v3, scenePtr);
                break;
            default:
                throw new ArgumentException($"Unsupported field type: {value.GetType().Name}");
        }
    }

    /// <summary>
    /// Set a mesh field by handle.
    /// </summary>
    public void SetFieldMesh(string path, TcMeshHandle handle, Scene? scene = null)
    {
        if (_ptr == IntPtr.Zero) return;
        // Entity_lib functions still use IntPtr for scene, pass zero for now
        TerminCore.ComponentSetFieldMesh(_ptr, path, handle, IntPtr.Zero);
    }

    /// <summary>
    /// Set a material field by handle.
    /// </summary>
    public void SetFieldMaterial(string path, TcMaterialHandle handle, Scene? scene = null)
    {
        if (_ptr == IntPtr.Zero) return;
        // Entity_lib functions still use IntPtr for scene, pass zero for now
        TerminCore.ComponentSetFieldMaterial(_ptr, path, handle, IntPtr.Zero);
    }

    /// <summary>
    /// Get a vec3 field value.
    /// </summary>
    public TcVec3 GetFieldVec3(string path)
    {
        if (_ptr == IntPtr.Zero) return new TcVec3(0, 0, 0);
        return TerminCore.ComponentGetFieldVec3(_ptr, path);
    }

    /// <summary>
    /// Set a vec3 field value.
    /// </summary>
    public void SetFieldVec3(string path, TcVec3 value, Scene? scene = null)
    {
        if (_ptr == IntPtr.Zero) return;
        TerminCore.ComponentSetFieldVec3(_ptr, path, value, IntPtr.Zero);
    }

    /// <summary>
    /// Get an integer field value.
    /// </summary>
    public long GetFieldInt(string path)
    {
        if (_ptr == IntPtr.Zero) return 0;
        return TerminCore.ComponentGetFieldInt(_ptr, path);
    }

    /// <summary>
    /// Get a float field value.
    /// </summary>
    public float GetFieldFloat(string path)
    {
        if (_ptr == IntPtr.Zero) return 0f;
        return TerminCore.ComponentGetFieldFloat(_ptr, path);
    }

    /// <summary>
    /// Get a double field value.
    /// </summary>
    public double GetFieldDouble(string path)
    {
        if (_ptr == IntPtr.Zero) return 0.0;
        return TerminCore.ComponentGetFieldDouble(_ptr, path);
    }

    /// <summary>
    /// Get a boolean field value.
    /// </summary>
    public bool GetFieldBool(string path)
    {
        if (_ptr == IntPtr.Zero) return false;
        return TerminCore.ComponentGetFieldBool(_ptr, path);
    }

    /// <summary>
    /// Get a string field value.
    /// </summary>
    public string? GetFieldString(string path)
    {
        if (_ptr == IntPtr.Zero) return null;
        var ptr = TerminCore.ComponentGetFieldString(_ptr, path);
        return Marshal.PtrToStringUTF8(ptr);
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
