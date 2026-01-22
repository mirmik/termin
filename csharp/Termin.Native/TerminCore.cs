using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// P/Invoke declarations for termin_core.dll (C API).
/// </summary>
public static partial class TerminCore
{
    const string DLL = "termin_core";

    // ========================================================================
    // Scene
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_scene_new")]
    public static partial IntPtr SceneNew();

    [LibraryImport(DLL, EntryPoint = "tc_scene_free")]
    public static partial void SceneFree(IntPtr scene);

    [LibraryImport(DLL, EntryPoint = "tc_scene_update")]
    public static partial void SceneUpdate(IntPtr scene, double dt);

    [LibraryImport(DLL, EntryPoint = "tc_scene_editor_update")]
    public static partial void SceneEditorUpdate(IntPtr scene, double dt);

    [LibraryImport(DLL, EntryPoint = "tc_scene_before_render")]
    public static partial void SceneBeforeRender(IntPtr scene);

    [LibraryImport(DLL, EntryPoint = "tc_scene_entity_pool")]
    public static partial IntPtr SceneEntityPool(IntPtr scene);

    [LibraryImport(DLL, EntryPoint = "tc_scene_entity_count")]
    public static partial nuint SceneEntityCount(IntPtr scene);

    // ========================================================================
    // Entity Pool
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_alloc", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcEntityId EntityPoolAlloc(IntPtr pool, string name);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_alloc_with_uuid", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcEntityId EntityPoolAllocWithUuid(IntPtr pool, string name, string uuid);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_free")]
    public static partial void EntityPoolFree(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_alive")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool EntityPoolAlive(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_count")]
    public static partial nuint EntityPoolCount(IntPtr pool);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_name", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr EntityPoolName(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_name", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void EntityPoolSetName(IntPtr pool, TcEntityId id, string name);

    // Transform
    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_get_local_position")]
    public static partial void EntityPoolGetLocalPosition(IntPtr pool, TcEntityId id, double[] xyz);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_local_position")]
    public static partial void EntityPoolSetLocalPosition(IntPtr pool, TcEntityId id, double[] xyz);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_get_local_rotation")]
    public static partial void EntityPoolGetLocalRotation(IntPtr pool, TcEntityId id, double[] xyzw);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_local_rotation")]
    public static partial void EntityPoolSetLocalRotation(IntPtr pool, TcEntityId id, double[] xyzw);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_get_local_scale")]
    public static partial void EntityPoolGetLocalScale(IntPtr pool, TcEntityId id, double[] xyz);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_local_scale")]
    public static partial void EntityPoolSetLocalScale(IntPtr pool, TcEntityId id, double[] xyz);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_get_world_matrix")]
    public static partial void EntityPoolGetWorldMatrix(IntPtr pool, TcEntityId id, double[] m16);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_update_transforms")]
    public static partial void EntityPoolUpdateTransforms(IntPtr pool);

    // Flags
    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_visible")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool EntityPoolVisible(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_visible")]
    public static partial void EntityPoolSetVisible(IntPtr pool, TcEntityId id, [MarshalAs(UnmanagedType.U1)] bool v);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_enabled")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool EntityPoolEnabled(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_enabled")]
    public static partial void EntityPoolSetEnabled(IntPtr pool, TcEntityId id, [MarshalAs(UnmanagedType.U1)] bool v);

    // Hierarchy
    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_parent")]
    public static partial TcEntityId EntityPoolParent(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_set_parent")]
    public static partial void EntityPoolSetParent(IntPtr pool, TcEntityId id, TcEntityId parent);

    // ========================================================================
    // Pipeline
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_pipeline_create", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr PipelineCreate(string name);

    [LibraryImport(DLL, EntryPoint = "tc_pipeline_destroy")]
    public static partial void PipelineDestroy(IntPtr pipeline);

    [LibraryImport(DLL, EntryPoint = "tc_pipeline_add_pass")]
    public static partial void PipelineAddPass(IntPtr pipeline, IntPtr pass);

    // ========================================================================
    // Render
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_create")]
    public static partial IntPtr FboPoolCreate();

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_destroy")]
    public static partial void FboPoolDestroy(IntPtr pool);

    [LibraryImport(DLL, EntryPoint = "tc_render_pipeline")]
    public static partial void RenderPipeline(
        IntPtr pipeline,
        IntPtr fboPool,
        IntPtr targetFbo,
        int width,
        int height,
        IntPtr scene,
        IntPtr camera,
        IntPtr graphics,
        long contextKey
    );
}
