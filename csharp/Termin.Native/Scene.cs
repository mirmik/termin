namespace Termin.Native;

/// <summary>
/// High-level wrapper for tc_scene (handle-based).
/// </summary>
public class Scene : IDisposable
{
    private TcSceneHandle _handle;
    private bool _disposed;

    public TcSceneHandle Handle => _handle;
    public EntityPool Entities { get; }

    public Scene()
    {
        _handle = TerminCore.SceneNew();
        var poolHandle = TerminCore.SceneEntityPool(_handle);
        Entities = new EntityPool(poolHandle, ownsHandle: false);
    }

    public Scene(string name)
    {
        _handle = TerminCore.SceneNewNamed(name);
        var poolHandle = TerminCore.SceneEntityPool(_handle);
        Entities = new EntityPool(poolHandle, ownsHandle: false);
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

    public void Dispose()
    {
        if (!_disposed && _handle.IsValid)
        {
            TerminCore.SceneFree(_handle);
            _handle = TcSceneHandle.Invalid;
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }

    ~Scene() => Dispose();
}
