using System;
namespace Termin.Native;

/// <summary>
/// High-level wrapper for tc_scene (handle-based).
/// </summary>
public class Scene : IDisposable
{
    private TcSceneHandle _handle;
    private IntPtr _collisionWorld;
    private bool _disposed;

    public TcSceneHandle Handle => _handle;
    public EntityPool Entities { get; }

    public Scene()
    {
        _handle = TerminCore.SceneNew();
        var poolHandle = TerminCore.SceneEntityPool(_handle);
        Entities = new EntityPool(poolHandle, ownsHandle: false);
        InitializeCollisionWorld();
    }

    public Scene(string name)
    {
        _handle = TerminCore.SceneNewNamed(name);
        var poolHandle = TerminCore.SceneEntityPool(_handle);
        Entities = new EntityPool(poolHandle, ownsHandle: false);
        InitializeCollisionWorld();
    }

    private void InitializeCollisionWorld()
    {
        // Create collision world and attach it to the scene
        _collisionWorld = TerminCore.CollisionWorldCreate();
        TerminCore.SceneSetCollisionWorld(_handle, _collisionWorld);
    }

    public bool IsAlive => TerminCore.SceneAlive(_handle);

    public void Update(double dt)
    {
        TerminCore.SceneUpdate(_handle, dt);
    }

    public void EditorUpdate(double dt)
    {
        TerminCore.SceneEditorUpdate(_handle, dt);
    }

    public void BeforeRender()
    {
        TerminCore.SceneBeforeRender(_handle);
    }

    public int EntityCount => (int)TerminCore.SceneEntityCount(_handle);

    /// <summary>
    /// Serializes scene to JSON string (entities, components, settings).
    /// Uses the native engine's inspect-based serialization.
    /// </summary>
    public string ToJson()
    {
        var swigHandle = SwigHelpers.ToSwigSceneHandle(_handle);
        return termin.scene_to_json(swigHandle);
    }

    /// <summary>
    /// Loads entities and settings from JSON into this scene.
    /// Returns number of loaded entities.
    /// </summary>
    public int FromJson(string json)
    {
        var swigHandle = SwigHelpers.ToSwigSceneHandle(_handle);
        return termin.scene_from_json(swigHandle, json);
    }

    /// <summary>
    /// Serializes a single entity and its entire subtree to JSON string.
    /// </summary>
    public string SubtreeToJson(Entity entity)
    {
        var swigHandle = SwigHelpers.ToSwigSceneHandle(_handle);
        return termin.entity_subtree_to_json(swigHandle, entity.Id.Index, entity.Id.Generation);
    }

    /// <summary>
    /// Gets the collision world pointer (for debugging).
    /// </summary>
    public IntPtr CollisionWorldPtr => _collisionWorld;

    /// <summary>
    /// Gets the number of colliders in the collision world.
    /// </summary>
    public int CollisionWorldSize => _collisionWorld != IntPtr.Zero ? TerminCore.CollisionWorldSize(_collisionWorld) : 0;

    public void Dispose()
    {
        if (!_disposed && _handle.IsValid)
        {
            // Clear collision world from scene first
            TerminCore.SceneSetCollisionWorld(_handle, IntPtr.Zero);

            // Destroy collision world
            if (_collisionWorld != IntPtr.Zero)
            {
                TerminCore.CollisionWorldDestroy(_collisionWorld);
                _collisionWorld = IntPtr.Zero;
            }

            TerminCore.SceneFree(_handle);
            _handle = TcSceneHandle.Invalid;
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }

    ~Scene() => Dispose();
}
