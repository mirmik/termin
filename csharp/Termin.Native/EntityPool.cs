using System.Collections.Generic;
using System.Numerics;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// High-level wrapper for tc_entity_pool.
/// </summary>
public class EntityPool : IDisposable
{
    private IntPtr _handle;
    private readonly bool _ownsHandle;
    private bool _disposed;

    public IntPtr Handle => _handle;

    public EntityPool(IntPtr handle, bool ownsHandle = true)
    {
        _handle = handle;
        _ownsHandle = ownsHandle;
    }

    /// <summary>
    /// Create a new standalone entity pool (not associated with a scene).
    /// </summary>
    public static EntityPool Create(int initialCapacity = 16)
    {
        var handle = TerminCore.EntityPoolCreate((nuint)initialCapacity);
        if (handle == IntPtr.Zero)
            throw new InvalidOperationException("Failed to create EntityPool");

        // Register pool in global registry so C++ Entity can find it
        var poolHandle = TerminCore.EntityPoolRegistryRegister(handle);
        if (!poolHandle.IsValid)
        {
            TerminCore.EntityPoolDestroy(handle);
            throw new InvalidOperationException("Failed to register EntityPool");
        }

        return new EntityPool(handle, ownsHandle: true);
    }

    public int Count => (int)TerminCore.EntityPoolCount(_handle);

    /// <summary>
    /// Create a new entity with the given name.
    /// </summary>
    public Entity CreateEntity(string name)
    {
        var id = TerminCore.EntityPoolAlloc(_handle, name);
        return new Entity(this, id);
    }

    /// <summary>
    /// Create a new entity with the given name and UUID.
    /// </summary>
    public Entity CreateEntity(string name, string uuid)
    {
        var id = TerminCore.EntityPoolAllocWithUuid(_handle, name, uuid);
        return new Entity(this, id);
    }

    /// <summary>
    /// Get an Entity wrapper for an existing entity ID.
    /// </summary>
    public Entity GetEntity(TcEntityId id)
    {
        return new Entity(this, id);
    }

    public void DestroyEntity(TcEntityId id)
    {
        TerminCore.EntityPoolFree(_handle, id);
    }

    public bool IsAlive(TcEntityId id)
    {
        return TerminCore.EntityPoolAlive(_handle, id);
    }

    public string? GetName(TcEntityId id)
    {
        var ptr = TerminCore.EntityPoolName(_handle, id);
        return Marshal.PtrToStringUTF8(ptr);
    }

    public void SetName(TcEntityId id, string name)
    {
        TerminCore.EntityPoolSetName(_handle, id, name);
    }

    // Transform
    public Vector3 GetPosition(TcEntityId id)
    {
        var xyz = new double[3];
        TerminCore.EntityPoolGetLocalPosition(_handle, id, xyz);
        return new Vector3((float)xyz[0], (float)xyz[1], (float)xyz[2]);
    }

    public void SetPosition(TcEntityId id, Vector3 pos)
    {
        var xyz = new double[] { pos.X, pos.Y, pos.Z };
        TerminCore.EntityPoolSetLocalPosition(_handle, id, xyz);
    }

    public Quaternion GetRotation(TcEntityId id)
    {
        var xyzw = new double[4];
        TerminCore.EntityPoolGetLocalRotation(_handle, id, xyzw);
        return new Quaternion((float)xyzw[0], (float)xyzw[1], (float)xyzw[2], (float)xyzw[3]);
    }

    public void SetRotation(TcEntityId id, Quaternion rot)
    {
        var xyzw = new double[] { rot.X, rot.Y, rot.Z, rot.W };
        TerminCore.EntityPoolSetLocalRotation(_handle, id, xyzw);
    }

    public Vector3 GetScale(TcEntityId id)
    {
        var xyz = new double[3];
        TerminCore.EntityPoolGetLocalScale(_handle, id, xyz);
        return new Vector3((float)xyz[0], (float)xyz[1], (float)xyz[2]);
    }

    public void SetScale(TcEntityId id, Vector3 scale)
    {
        var xyz = new double[] { scale.X, scale.Y, scale.Z };
        TerminCore.EntityPoolSetLocalScale(_handle, id, xyz);
    }

    public Matrix4x4 GetWorldMatrix(TcEntityId id)
    {
        var m = new double[16];
        TerminCore.EntityPoolGetWorldMatrix(_handle, id, m);
        return new Matrix4x4(
            (float)m[0], (float)m[1], (float)m[2], (float)m[3],
            (float)m[4], (float)m[5], (float)m[6], (float)m[7],
            (float)m[8], (float)m[9], (float)m[10], (float)m[11],
            (float)m[12], (float)m[13], (float)m[14], (float)m[15]
        );
    }

    public void UpdateTransforms()
    {
        TerminCore.EntityPoolUpdateTransforms(_handle);
    }

    /// <summary>
    /// Get all entities as Entity wrappers.
    /// </summary>
    public IEnumerable<Entity> GetAllEntities()
    {
        // For now, iterate through possible indices. This is a simplified approach.
        // A proper implementation would query the pool for valid entity IDs.
        var count = (int)Count;
        for (uint i = 0; i < count * 2 && count > 0; i++) // scan up to 2x count to find all
        {
            var id = new TcEntityId { Index = i, Generation = 0 };
            // Try different generations
            for (uint gen = 0; gen < 4; gen++)
            {
                id.Generation = gen;
                if (IsAlive(id))
                {
                    yield return new Entity(this, id);
                    break;
                }
            }
        }
    }

    /// <summary>
    /// Delete an entity.
    /// </summary>
    public void DeleteEntity(TcEntityId id)
    {
        TerminCore.EntityPoolFree(_handle, id);
    }

    // Flags
    public bool IsVisible(TcEntityId id) => TerminCore.EntityPoolVisible(_handle, id);
    public void SetVisible(TcEntityId id, bool v) => TerminCore.EntityPoolSetVisible(_handle, id, v);

    public bool IsEnabled(TcEntityId id) => TerminCore.EntityPoolEnabled(_handle, id);
    public void SetEnabled(TcEntityId id, bool v) => TerminCore.EntityPoolSetEnabled(_handle, id, v);

    // Hierarchy
    public TcEntityId GetParent(TcEntityId id) => TerminCore.EntityPoolParent(_handle, id);
    public void SetParent(TcEntityId id, TcEntityId parent) => TerminCore.EntityPoolSetParent(_handle, id, parent);

    public void Dispose()
    {
        if (!_disposed && _ownsHandle && _handle != IntPtr.Zero)
        {
            TerminCore.EntityPoolDestroy(_handle);
            _handle = IntPtr.Zero;
        }
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    ~EntityPool() => Dispose();
}
