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

    [LibraryImport(DLL, EntryPoint = "tc_render_view_to_fbo")]
    public static partial void RenderViewToFbo(
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

    // ========================================================================
    // Mesh Registry
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_mesh_init")]
    public static partial void MeshInit();

    [LibraryImport(DLL, EntryPoint = "tc_mesh_shutdown")]
    public static partial void MeshShutdown();

    [LibraryImport(DLL, EntryPoint = "tc_mesh_create", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcMeshHandle MeshCreate(string? uuid);

    [LibraryImport(DLL, EntryPoint = "tc_mesh_get")]
    public static partial IntPtr MeshGet(TcMeshHandle handle);

    [LibraryImport(DLL, EntryPoint = "tc_mesh_set_data", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool MeshSetData(
        IntPtr mesh,
        IntPtr vertices,
        nuint vertexCount,
        ref TcVertexLayout layout,
        IntPtr indices,
        nuint indexCount,
        string? name
    );

    [LibraryImport(DLL, EntryPoint = "tc_mesh_upload_gpu")]
    public static partial uint MeshUploadGpu(IntPtr mesh);

    [LibraryImport(DLL, EntryPoint = "tc_mesh_draw_gpu")]
    public static partial void MeshDrawGpu(IntPtr mesh);

    // ========================================================================
    // Vertex Layout
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_init")]
    public static partial void VertexLayoutInit(ref TcVertexLayout layout);

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_add", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool VertexLayoutAdd(
        ref TcVertexLayout layout,
        string name,
        byte size,
        TcAttribType type,
        byte location
    );

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_pos")]
    public static partial TcVertexLayout VertexLayoutPos();

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal")]
    public static partial TcVertexLayout VertexLayoutPosNormal();

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal_uv")]
    public static partial TcVertexLayout VertexLayoutPosNormalUv();

    [LibraryImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal_uv_color")]
    public static partial TcVertexLayout VertexLayoutPosNormalUvColor();

    // ========================================================================
    // Shader Registry
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_shader_init")]
    public static partial void ShaderInit();

    [LibraryImport(DLL, EntryPoint = "tc_shader_shutdown")]
    public static partial void ShaderShutdown();

    [LibraryImport(DLL, EntryPoint = "tc_shader_from_sources", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcShaderHandle ShaderFromSources(
        string vertexSource,
        string fragmentSource,
        string? geometrySource,
        string? name,
        string? sourcePath
    );

    [LibraryImport(DLL, EntryPoint = "tc_shader_get")]
    public static partial IntPtr ShaderGet(TcShaderHandle handle);

    [LibraryImport(DLL, EntryPoint = "tc_shader_compile_gpu")]
    public static partial uint ShaderCompileGpu(IntPtr shader);

    [LibraryImport(DLL, EntryPoint = "tc_shader_use_gpu")]
    public static partial void ShaderUseGpu(IntPtr shader);

    [LibraryImport(DLL, EntryPoint = "tc_shader_set_int")]
    public static partial void ShaderSetInt(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, int value);

    [LibraryImport(DLL, EntryPoint = "tc_shader_set_float")]
    public static partial void ShaderSetFloat(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float value);

    [LibraryImport(DLL, EntryPoint = "tc_shader_set_vec3")]
    public static partial void ShaderSetVec3(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float x, float y, float z);

    [LibraryImport(DLL, EntryPoint = "tc_shader_set_vec4")]
    public static partial void ShaderSetVec4(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float x, float y, float z, float w);

    [LibraryImport(DLL, EntryPoint = "tc_shader_set_mat4")]
    public static partial void ShaderSetMat4(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float[] data, [MarshalAs(UnmanagedType.U1)] bool transpose);

    // ========================================================================
    // Material Registry
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_material_init")]
    public static partial void MaterialInit();

    [LibraryImport(DLL, EntryPoint = "tc_material_shutdown")]
    public static partial void MaterialShutdown();

    [LibraryImport(DLL, EntryPoint = "tc_material_create", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcMaterialHandle MaterialCreate(string? uuid, string name);

    [LibraryImport(DLL, EntryPoint = "tc_material_get")]
    public static partial IntPtr MaterialGet(TcMaterialHandle handle);

    [LibraryImport(DLL, EntryPoint = "tc_material_add_phase", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr MaterialAddPhase(IntPtr material, TcShaderHandle shader, string phaseMark, int priority);

    [LibraryImport(DLL, EntryPoint = "tc_material_set_color")]
    public static partial void MaterialSetColor(IntPtr material, float r, float g, float b, float a);

    [LibraryImport(DLL, EntryPoint = "tc_material_phase_apply_gpu")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool MaterialPhaseApplyGpu(IntPtr phase);

    // ========================================================================
    // Component Registry
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_component_registry_create", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr ComponentRegistryCreate(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_component_registry_has", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentRegistryHas(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_add_component")]
    public static partial void EntityPoolAddComponent(IntPtr pool, TcEntityId id, IntPtr component);

    // ========================================================================
    // Pass Registry
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_pass_registry_has", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool PassRegistryHas(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_pass_registry_create", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr PassRegistryCreate(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_pass_registry_type_count")]
    public static partial nuint PassRegistryTypeCount();

    [LibraryImport(DLL, EntryPoint = "tc_pass_registry_type_at")]
    public static partial IntPtr PassRegistryTypeAt(nuint index);

    [LibraryImport(DLL, EntryPoint = "tc_pass_set_name", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void PassSetName(IntPtr pass, string name);

    [LibraryImport(DLL, EntryPoint = "tc_pass_set_enabled")]
    public static partial void PassSetEnabled(IntPtr pass, [MarshalAs(UnmanagedType.U1)] bool enabled);

    [LibraryImport(DLL, EntryPoint = "tc_pass_drop")]
    public static partial void PassDrop(IntPtr pass);

    // ========================================================================
    // FBO Pool Extended
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_ensure", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr FboPoolEnsure(
        IntPtr pool,
        string key,
        int width,
        int height,
        int samples,
        string? format
    );

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_get", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr FboPoolGet(IntPtr pool, string key);

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_set", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void FboPoolSet(IntPtr pool, string key, IntPtr fbo);

    [LibraryImport(DLL, EntryPoint = "tc_fbo_pool_clear")]
    public static partial void FboPoolClear(IntPtr pool);

    // ========================================================================
    // tc_value - Tagged union for field values
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_value_nil")]
    public static partial TcValue ValueNil();

    [LibraryImport(DLL, EntryPoint = "tc_value_bool")]
    public static partial TcValue ValueBool([MarshalAs(UnmanagedType.U1)] bool v);

    [LibraryImport(DLL, EntryPoint = "tc_value_int")]
    public static partial TcValue ValueInt(long v);

    [LibraryImport(DLL, EntryPoint = "tc_value_float")]
    public static partial TcValue ValueFloat(float v);

    [LibraryImport(DLL, EntryPoint = "tc_value_double")]
    public static partial TcValue ValueDouble(double v);

    [LibraryImport(DLL, EntryPoint = "tc_value_string", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcValue ValueString(string s);

    [LibraryImport(DLL, EntryPoint = "tc_value_free")]
    public static partial void ValueFree(ref TcValue v);

    // ========================================================================
    // tc_inspect - Field inspection and access
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_inspect_has_type", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool InspectHasType(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_inspect_field_count", StringMarshalling = StringMarshalling.Utf8)]
    public static partial nuint InspectFieldCount(string typeName);

    [LibraryImport(DLL, EntryPoint = "tc_inspect_get", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcValue InspectGet(IntPtr obj, string typeName, string path);

    [LibraryImport(DLL, EntryPoint = "tc_inspect_set", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void InspectSet(IntPtr obj, string typeName, string path, TcValue value, IntPtr scene);

    // ========================================================================
    // Pass field inspection (via tc_pass*)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_pass_inspect_get", StringMarshalling = StringMarshalling.Utf8)]
    public static partial TcValue PassInspectGet(IntPtr pass, string path);

    [LibraryImport(DLL, EntryPoint = "tc_pass_inspect_set", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void PassInspectSet(IntPtr pass, string path, TcValue value, IntPtr scene);

    // ========================================================================
    // Component External Body Management (for C# prevent-GC mechanism)
    // ========================================================================

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void ComponentBodyIncrefDelegate(IntPtr body);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void ComponentBodyDecrefDelegate(IntPtr body);

    [StructLayout(LayoutKind.Sequential)]
    public struct ComponentExternalCallbacks
    {
        public IntPtr incref;
        public IntPtr decref;
    }

    [LibraryImport(DLL, EntryPoint = "tc_component_set_external_callbacks")]
    public static partial void ComponentSetExternalCallbacks(ref ComponentExternalCallbacks callbacks);

    [LibraryImport(DLL, EntryPoint = "tc_component_body_incref")]
    public static partial void ComponentBodyIncref(IntPtr body);

    [LibraryImport(DLL, EntryPoint = "tc_component_body_decref")]
    public static partial void ComponentBodyDecref(IntPtr body);

    // ========================================================================
    // Pass External Body Management (for C# prevent-GC mechanism)
    // ========================================================================

    [StructLayout(LayoutKind.Sequential)]
    public struct PassExternalCallbacks
    {
        public IntPtr execute;           // not used for C++ passes
        public IntPtr get_reads;         // not used for C++ passes
        public IntPtr get_writes;        // not used for C++ passes
        public IntPtr get_inplace_aliases; // not used for C++ passes
        public IntPtr get_resource_specs;  // not used for C++ passes
        public IntPtr get_internal_symbols; // not used for C++ passes
        public IntPtr destroy;           // not used for C++ passes
        public IntPtr incref;
        public IntPtr decref;
    }

    [LibraryImport(DLL, EntryPoint = "tc_pass_set_external_callbacks")]
    public static partial void PassSetExternalCallbacks(ref PassExternalCallbacks callbacks);
}

/// <summary>
/// Manages external body for C++ components created from C#.
/// Prevents GC from collecting the C# wrapper while C++ holds a reference.
/// </summary>
public static class ComponentExternalBody
{
    private static TerminCore.ComponentBodyIncrefDelegate? _increfDelegate;
    private static TerminCore.ComponentBodyDecrefDelegate? _decrefDelegate;
    private static bool _initialized;

    /// <summary>
    /// Initialize the external body callbacks. Call once at startup.
    /// </summary>
    public static void Initialize()
    {
        if (_initialized) return;

        _increfDelegate = IncrefCallback;
        _decrefDelegate = DecrefCallback;

        var callbacks = new TerminCore.ComponentExternalCallbacks
        {
            incref = Marshal.GetFunctionPointerForDelegate(_increfDelegate),
            decref = Marshal.GetFunctionPointerForDelegate(_decrefDelegate)
        };

        TerminCore.ComponentSetExternalCallbacks(ref callbacks);
        _initialized = true;
    }

    private static void IncrefCallback(IntPtr body)
    {
        // body is a GCHandle - incref means allocate another Normal handle
        // But since we use Normal handle which prevents GC, incref is no-op
        // The C++ side will call decref when done
    }

    private static void DecrefCallback(IntPtr body)
    {
        // body is a GCHandle - free it to allow GC
        if (body != IntPtr.Zero)
        {
            var handle = GCHandle.FromIntPtr(body);
            if (handle.IsAllocated)
            {
                handle.Free();
            }
        }
    }

    /// <summary>
    /// Register a C# object as external body for a component.
    /// Returns the GCHandle IntPtr to pass to set_external_body().
    /// </summary>
    public static IntPtr Register(object obj)
    {
        var handle = GCHandle.Alloc(obj, GCHandleType.Normal);
        return GCHandle.ToIntPtr(handle);
    }

    /// <summary>
    /// Get the C# object from an external body IntPtr.
    /// </summary>
    public static object? GetObject(IntPtr body)
    {
        if (body == IntPtr.Zero) return null;
        var handle = GCHandle.FromIntPtr(body);
        return handle.IsAllocated ? handle.Target : null;
    }
}

/// <summary>
/// Manages external body for C++ passes created from C#.
/// Prevents GC from collecting the C# wrapper while C++ holds a reference.
/// Same pattern as ComponentExternalBody but for passes.
/// </summary>
public static class PassExternalBody
{
    private static TerminCore.ComponentBodyIncrefDelegate? _increfDelegate;
    private static TerminCore.ComponentBodyDecrefDelegate? _decrefDelegate;
    private static bool _initialized;

    /// <summary>
    /// Initialize the external body callbacks for passes. Call once at startup.
    /// </summary>
    public static void Initialize()
    {
        if (_initialized) return;

        _increfDelegate = IncrefCallback;
        _decrefDelegate = DecrefCallback;

        var callbacks = new TerminCore.PassExternalCallbacks
        {
            incref = Marshal.GetFunctionPointerForDelegate(_increfDelegate),
            decref = Marshal.GetFunctionPointerForDelegate(_decrefDelegate)
        };

        TerminCore.PassSetExternalCallbacks(ref callbacks);
        _initialized = true;
    }

    private static void IncrefCallback(IntPtr body)
    {
        // body is a GCHandle - incref is no-op since Normal handle prevents GC
    }

    private static void DecrefCallback(IntPtr body)
    {
        // body is a GCHandle - free it to allow GC
        if (body != IntPtr.Zero)
        {
            var handle = GCHandle.FromIntPtr(body);
            if (handle.IsAllocated)
            {
                handle.Free();
            }
        }
    }

    /// <summary>
    /// Register a C# object as external body for a pass.
    /// Returns the GCHandle IntPtr to pass to set_external_body().
    /// </summary>
    public static IntPtr Register(object obj)
    {
        var handle = GCHandle.Alloc(obj, GCHandleType.Normal);
        return GCHandle.ToIntPtr(handle);
    }

    /// <summary>
    /// Get the C# object from an external body IntPtr.
    /// </summary>
    public static object? GetObject(IntPtr body)
    {
        if (body == IntPtr.Zero) return null;
        var handle = GCHandle.FromIntPtr(body);
        return handle.IsAllocated ? handle.Target : null;
    }
}
