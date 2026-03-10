using System;
using System.Collections.Generic;
using System.Numerics;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Wrapper around EntityPool + TcEntityId providing convenient entity access.
/// Similar to termin::Entity in C++.
/// </summary>
public readonly struct Entity
{
    private readonly EntityPool _pool;
    private readonly TcEntityId _id;

    /// <summary>
    /// The underlying entity pool.
    /// </summary>
    public EntityPool Pool => _pool;

    /// <summary>
    /// The entity ID within the pool.
    /// </summary>
    public TcEntityId Id => _id;

    /// <summary>
    /// Create entity wrapper from pool and id.
    /// </summary>
    public Entity(EntityPool pool, TcEntityId id)
    {
        _pool = pool;
        _id = id;
    }

    /// <summary>
    /// Check if entity is valid (pool exists and id is alive).
    /// </summary>
    public bool IsValid => _pool != null && _pool.IsAlive(_id);

    // ========================================================================
    // Name
    // ========================================================================

    /// <summary>
    /// Get or set the entity name.
    /// </summary>
    public string? Name
    {
        get => _pool?.GetName(_id);
        set
        {
            if (_pool != null && value != null)
                _pool.SetName(_id, value);
        }
    }

    // ========================================================================
    // Transform
    // ========================================================================

    /// <summary>
    /// Get or set the local position.
    /// </summary>
    public Vector3 Position
    {
        get => _pool?.GetPosition(_id) ?? Vector3.Zero;
        set => _pool?.SetPosition(_id, value);
    }

    /// <summary>
    /// Get or set the local rotation.
    /// </summary>
    public Quaternion Rotation
    {
        get => _pool?.GetRotation(_id) ?? Quaternion.Identity;
        set => _pool?.SetRotation(_id, value);
    }

    /// <summary>
    /// Get or set the local scale.
    /// </summary>
    public Vector3 Scale
    {
        get => _pool?.GetScale(_id) ?? Vector3.One;
        set => _pool?.SetScale(_id, value);
    }

    /// <summary>
    /// Get the world transformation matrix.
    /// </summary>
    public Matrix4x4 WorldMatrix => _pool?.GetWorldMatrix(_id) ?? Matrix4x4.Identity;

    // ========================================================================
    // Flags
    // ========================================================================

    /// <summary>
    /// Get or set visibility.
    /// </summary>
    public bool Visible
    {
        get => _pool?.IsVisible(_id) ?? false;
        set => _pool?.SetVisible(_id, value);
    }

    /// <summary>
    /// Get or set enabled state.
    /// </summary>
    public bool Enabled
    {
        get => _pool?.IsEnabled(_id) ?? false;
        set => _pool?.SetEnabled(_id, value);
    }

    // ========================================================================
    // Layer
    // ========================================================================

    /// <summary>
    /// Get or set the entity layer bitmask.
    /// </summary>
    public ulong Layer
    {
        get => _pool?.GetLayer(_id) ?? 0;
        set => _pool?.SetLayer(_id, value);
    }

    // ========================================================================
    // Hierarchy
    // ========================================================================

    /// <summary>
    /// Get the parent entity, or default if no parent.
    /// </summary>
    public Entity Parent
    {
        get
        {
            if (_pool == null) return default;
            var parentId = _pool.GetParent(_id);
            return new Entity(_pool, parentId);
        }
    }

    /// <summary>
    /// Set the parent entity.
    /// </summary>
    public void SetParent(Entity parent)
    {
        _pool?.SetParent(_id, parent._id);
    }

    /// <summary>
    /// Get direct children of this entity.
    /// </summary>
    public List<Entity> Children => _pool?.GetDirectChildren(_id) ?? new List<Entity>();

    /// <summary>
    /// Number of direct children.
    /// </summary>
    public int ChildCount => _pool?.GetChildrenCount(_id) ?? 0;

    // ========================================================================
    // Components
    // ========================================================================

    /// <summary>
    /// Number of components attached to this entity.
    /// </summary>
    public int ComponentCount
    {
        get
        {
            if (_pool == null) return 0;
            return (int)TerminCore.EntityPoolComponentCount(_pool.Handle, _id);
        }
    }

    /// <summary>
    /// Get component reference at index.
    /// </summary>
    public ComponentRef GetComponentAt(int index)
    {
        if (_pool == null) return default;
        return new ComponentRef(TerminCore.EntityPoolComponentAt(_pool.Handle, _id, (nuint)index));
    }

    /// <summary>
    /// Get all components as an enumerable.
    /// </summary>
    public IEnumerable<ComponentRef> Components
    {
        get
        {
            int count = ComponentCount;
            for (int i = 0; i < count; i++)
            {
                yield return GetComponentAt(i);
            }
        }
    }

    /// <summary>
    /// Find component by type name.
    /// </summary>
    public ComponentRef GetComponent(string typeName)
    {
        foreach (var comp in Components)
        {
            if (comp.TypeName == typeName)
                return comp;
        }
        return default;
    }

    /// <summary>
    /// Add a component (from tc_component pointer).
    /// </summary>
    public void AddComponent(IntPtr componentPtr)
    {
        if (_pool == null || componentPtr == IntPtr.Zero) return;
        TerminCore.EntityPoolAddComponent(_pool.Handle, _id, componentPtr);
    }

    /// <summary>
    /// Add a component (from ComponentRef).
    /// </summary>
    public void AddComponent(ComponentRef component)
    {
        AddComponent(component.Ptr);
    }

    /// <summary>
    /// Add a SWIG-wrapped component (CameraComponent, MeshRenderer, etc.)
    /// </summary>
    public void AddComponent(CameraComponent component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a SWIG-wrapped component (OrbitCameraController).
    /// </summary>
    public void AddComponent(OrbitCameraController component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a SWIG-wrapped component (MeshRenderer).
    /// </summary>
    public void AddComponent(MeshRenderer component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a SWIG-wrapped component (ColliderComponent).
    /// </summary>
    public void AddComponent(ColliderComponent component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a SWIG-wrapped component (RotatorComponent).
    /// </summary>
    public void AddComponent(RotatorComponent component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a SWIG-wrapped component (ActuatorComponent).
    /// </summary>
    public void AddComponent(ActuatorComponent component)
    {
        AddComponent(component.tc_component_ptr());
    }

    /// <summary>
    /// Add a component by type name. Creates the component from registry.
    /// Returns a ComponentRef to the created component.
    /// </summary>
    public ComponentRef AddComponentByName(string typeName)
    {
        if (_pool == null) return default;

        // Check if type is registered
        if (!TerminCore.ComponentRegistryHas(typeName))
        {
            return default;
        }

        // Create component from registry
        var componentPtr = TerminCore.ComponentRegistryCreate(typeName);
        if (componentPtr == IntPtr.Zero)
        {
            return default;
        }

        // Add to entity
        TerminCore.EntityPoolAddComponent(_pool.Handle, _id, componentPtr);
        return new ComponentRef(componentPtr);
    }

    /// <summary>
    /// Remove a component (from tc_component pointer).
    /// </summary>
    public void RemoveComponent(IntPtr componentPtr)
    {
        if (_pool == null || componentPtr == IntPtr.Zero) return;
        TerminCore.EntityPoolRemoveComponent(_pool.Handle, _id, componentPtr);
    }

    /// <summary>
    /// Remove a component (from ComponentRef).
    /// </summary>
    public void RemoveComponent(ComponentRef component)
    {
        RemoveComponent(component.Ptr);
    }

    // ========================================================================
    // Destruction
    // ========================================================================

    /// <summary>
    /// Destroy this entity, removing it from the pool.
    /// </summary>
    public void Destroy()
    {
        _pool?.DestroyEntity(_id);
    }

    // ========================================================================
    // Equality
    // ========================================================================

    public override bool Equals(object? obj)
    {
        return obj is Entity other && this == other;
    }

    public override int GetHashCode()
    {
        return HashCode.Combine(_pool?.Handle ?? IntPtr.Zero, _id.Index, _id.Generation);
    }

    public static bool operator ==(Entity left, Entity right)
    {
        if (left._pool == null && right._pool == null) return true;
        if (left._pool == null || right._pool == null) return false;
        return left._pool.Handle == right._pool.Handle &&
               left._id.Index == right._id.Index &&
               left._id.Generation == right._id.Generation;
    }

    public static bool operator !=(Entity left, Entity right) => !(left == right);

    public override string ToString()
    {
        if (!IsValid) return "Entity(invalid)";
        return $"Entity({Name ?? "unnamed"}, id={_id.Index}:{_id.Generation})";
    }
}
