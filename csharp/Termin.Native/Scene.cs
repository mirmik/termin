namespace Termin.Native;

/// <summary>
/// High-level wrapper for tc_scene.
/// </summary>
public class Scene : IDisposable
{
    private IntPtr _handle;
    private bool _disposed;

    public IntPtr Handle => _handle;
    public EntityPool Entities { get; }

    public Scene()
    {
        _handle = TerminCore.SceneNew();
        var poolHandle = TerminCore.SceneEntityPool(_handle);
        Entities = new EntityPool(poolHandle, ownsHandle: false);
    }

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

    public void Dispose()
    {
        if (!_disposed)
        {
            TerminCore.SceneFree(_handle);
            _handle = IntPtr.Zero;
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }

    ~Scene() => Dispose();
}
