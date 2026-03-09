using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Base class for components defined in C#.
/// Subclass this and override lifecycle methods. Mark properties with
/// [InspectField] to expose them in the editor inspector.
/// Register with CSharpComponentRuntime.RegisterType&lt;T&gt;("TypeName").
/// </summary>
public abstract class CSharpComponent
{
    /// <summary>
    /// Pointer to the native tc_component allocated by tc_component_new_csharp.
    /// </summary>
    internal IntPtr NativePtr;

    /// <summary>
    /// GCHandle preventing this object from being garbage-collected
    /// while native code holds a reference.
    /// </summary>
    internal GCHandle GcHandle;

    // ====================================================================
    // Lifecycle — override in subclasses
    // ====================================================================

    protected virtual void OnStart() { }
    protected virtual void OnUpdate(float dt) { }
    protected virtual void OnFixedUpdate(float dt) { }
    protected virtual void OnBeforeRender() { }
    protected virtual void OnDestroy() { }
    protected virtual void OnAddedToEntity() { }
    protected virtual void OnRemovedFromEntity() { }
    protected virtual void OnAdded() { }
    protected virtual void OnRemoved() { }
    protected virtual void OnSceneInactive() { }
    protected virtual void OnSceneActive() { }

    // Internal dispatch — called by CSharpComponentRuntime
    internal void DispatchStart()              => OnStart();
    internal void DispatchUpdate(float dt)     => OnUpdate(dt);
    internal void DispatchFixedUpdate(float dt) => OnFixedUpdate(dt);
    internal void DispatchBeforeRender()       => OnBeforeRender();
    internal void DispatchOnDestroy()          => OnDestroy();
    internal void DispatchOnAddedToEntity()    => OnAddedToEntity();
    internal void DispatchOnRemovedFromEntity() => OnRemovedFromEntity();
    internal void DispatchOnAdded()            => OnAdded();
    internal void DispatchOnRemoved()          => OnRemoved();
    internal void DispatchOnSceneInactive()    => OnSceneInactive();
    internal void DispatchOnSceneActive()      => OnSceneActive();

    // ====================================================================
    // Entity access
    // ====================================================================

    /// <summary>
    /// Get the Entity this component is attached to.
    /// </summary>
    public Entity GetEntity(EntityPool pool)
    {
        return new ComponentRef(NativePtr).GetEntity(pool);
    }

    /// <summary>
    /// Get a ComponentRef wrapper for this component.
    /// </summary>
    public ComponentRef AsComponentRef()
    {
        return new ComponentRef(NativePtr);
    }
}
