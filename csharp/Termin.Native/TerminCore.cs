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

    // EntityPool lifecycle (for standalone pools)
    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_create")]
    public static partial IntPtr EntityPoolCreate(nuint initialCapacity);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_destroy")]
    public static partial void EntityPoolDestroy(IntPtr pool);

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

    // Components
    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_component_count")]
    public static partial nuint EntityPoolComponentCount(IntPtr pool, TcEntityId id);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_component_at")]
    public static partial IntPtr EntityPoolComponentAt(IntPtr pool, TcEntityId id, nuint index);

    [LibraryImport(DLL, EntryPoint = "tc_entity_pool_remove_component")]
    public static partial void EntityPoolRemoveComponent(IntPtr pool, TcEntityId id, IntPtr component);

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
        string? sourcePath,
        string? uuid
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
    // Component Properties (for ComponentRef)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_component_get_type_name")]
    public static partial IntPtr ComponentGetTypeName(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_enabled")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentGetEnabled(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_set_enabled")]
    public static partial void ComponentSetEnabled(IntPtr component, [MarshalAs(UnmanagedType.U1)] bool enabled);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_active_in_editor")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentGetActiveInEditor(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_set_active_in_editor")]
    public static partial void ComponentSetActiveInEditor(IntPtr component, [MarshalAs(UnmanagedType.U1)] bool active);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_is_drawable")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentGetIsDrawable(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_is_input_handler")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentGetIsInputHandler(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_kind")]
    public static partial int ComponentGetKind(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_owner_entity_id")]
    public static partial TcEntityId ComponentGetOwnerEntityId(IntPtr component);

    [LibraryImport(DLL, EntryPoint = "tc_component_get_owner_pool")]
    public static partial IntPtr ComponentGetOwnerPool(IntPtr component);

    // ========================================================================
    // Component Field Access (Inspect) - in entity_lib
    // ========================================================================

    private const string ENTITY_DLL = "entity_lib";

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_int", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldInt(IntPtr component, string path, long value, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_float", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldFloat(IntPtr component, string path, float value, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_double", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldDouble(IntPtr component, string path, double value, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_bool", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldBool(IntPtr component, string path, [MarshalAs(UnmanagedType.U1)] bool value, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_string", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldString(IntPtr component, string path, string value, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_mesh", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldMesh(IntPtr component, string path, TcMeshHandle handle, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_material", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void ComponentSetFieldMaterial(IntPtr component, string path, TcMaterialHandle handle, IntPtr scene);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_int", StringMarshalling = StringMarshalling.Utf8)]
    public static partial long ComponentGetFieldInt(IntPtr component, string path);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_float", StringMarshalling = StringMarshalling.Utf8)]
    public static partial float ComponentGetFieldFloat(IntPtr component, string path);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_double", StringMarshalling = StringMarshalling.Utf8)]
    public static partial double ComponentGetFieldDouble(IntPtr component, string path);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_bool", StringMarshalling = StringMarshalling.Utf8)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ComponentGetFieldBool(IntPtr component, string path);

    [LibraryImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_string", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr ComponentGetFieldString(IntPtr component, string path);

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

    // ========================================================================
    // Render Surface (tc_render_surface)
    // ========================================================================

    // VTable function pointer delegates
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate uint RenderSurfaceGetFramebufferDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceGetSizeDelegate(IntPtr surface, out int width, out int height);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceMakeCurrentDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceSwapBuffersDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate nuint RenderSurfaceContextKeyDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfacePollEventsDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceGetWindowSizeDelegate(IntPtr surface, out int width, out int height);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    [return: MarshalAs(UnmanagedType.U1)]
    public delegate bool RenderSurfaceShouldCloseDelegate(IntPtr surface);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceSetShouldCloseDelegate(IntPtr surface, [MarshalAs(UnmanagedType.U1)] bool value);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceGetCursorPosDelegate(IntPtr surface, out double x, out double y);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void RenderSurfaceDestroyDelegate(IntPtr surface);

    // VTable structure (must match tc_render_surface_vtable in C)
    [StructLayout(LayoutKind.Sequential)]
    public struct RenderSurfaceVTable
    {
        public IntPtr get_framebuffer;
        public IntPtr get_size;
        public IntPtr make_current;
        public IntPtr swap_buffers;
        public IntPtr context_key;
        public IntPtr poll_events;
        public IntPtr get_window_size;
        public IntPtr should_close;
        public IntPtr set_should_close;
        public IntPtr get_cursor_pos;
        public IntPtr destroy;
    }

    [LibraryImport(DLL, EntryPoint = "tc_render_surface_new_external")]
    public static partial IntPtr RenderSurfaceNewExternal(IntPtr body, ref RenderSurfaceVTable vtable);

    [LibraryImport(DLL, EntryPoint = "tc_render_surface_free_external")]
    public static partial void RenderSurfaceFreeExternal(IntPtr surface);

    // ========================================================================
    // Display (tc_display)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_display_new", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr DisplayNew(string name, IntPtr surface);

    [LibraryImport(DLL, EntryPoint = "tc_display_free")]
    public static partial void DisplayFree(IntPtr display);

    [LibraryImport(DLL, EntryPoint = "tc_display_set_name", StringMarshalling = StringMarshalling.Utf8)]
    public static partial void DisplaySetName(IntPtr display, string name);

    [LibraryImport(DLL, EntryPoint = "tc_display_get_name")]
    public static partial IntPtr DisplayGetName(IntPtr display);

    [LibraryImport(DLL, EntryPoint = "tc_display_get_size")]
    public static partial void DisplayGetSize(IntPtr display, out int width, out int height);

    [LibraryImport(DLL, EntryPoint = "tc_display_add_viewport")]
    public static partial void DisplayAddViewport(IntPtr display, IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_display_remove_viewport")]
    public static partial void DisplayRemoveViewport(IntPtr display, IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_display_get_viewport_count")]
    public static partial nuint DisplayGetViewportCount(IntPtr display);

    [LibraryImport(DLL, EntryPoint = "tc_display_get_first_viewport")]
    public static partial IntPtr DisplayGetFirstViewport(IntPtr display);

    [LibraryImport(DLL, EntryPoint = "tc_display_viewport_at_screen")]
    public static partial IntPtr DisplayViewportAtScreen(IntPtr display, float px, float py);

    // ========================================================================
    // Input Manager (tc_input_manager)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_input_manager_dispatch_mouse_button")]
    public static partial void InputManagerDispatchMouseButton(IntPtr manager, int button, int action, int mods);

    [LibraryImport(DLL, EntryPoint = "tc_input_manager_dispatch_mouse_move")]
    public static partial void InputManagerDispatchMouseMove(IntPtr manager, double x, double y);

    [LibraryImport(DLL, EntryPoint = "tc_input_manager_dispatch_scroll")]
    public static partial void InputManagerDispatchScroll(IntPtr manager, double x, double y, int mods);

    [LibraryImport(DLL, EntryPoint = "tc_input_manager_dispatch_key")]
    public static partial void InputManagerDispatchKey(IntPtr manager, int key, int scancode, int action, int mods);

    [LibraryImport(DLL, EntryPoint = "tc_input_manager_dispatch_char")]
    public static partial void InputManagerDispatchChar(IntPtr manager, uint codepoint);

    // ========================================================================
    // Simple Input Manager (tc_simple_input_manager)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_simple_input_manager_new")]
    public static partial IntPtr SimpleInputManagerNew(IntPtr display);

    [LibraryImport(DLL, EntryPoint = "tc_simple_input_manager_free")]
    public static partial void SimpleInputManagerFree(IntPtr manager);

    [LibraryImport(DLL, EntryPoint = "tc_simple_input_manager_base")]
    public static partial IntPtr SimpleInputManagerBase(IntPtr manager);

    // ========================================================================
    // Viewport (tc_viewport)
    // ========================================================================

    [LibraryImport(DLL, EntryPoint = "tc_viewport_new", StringMarshalling = StringMarshalling.Utf8)]
    public static partial IntPtr ViewportNew(string? name, IntPtr scene, IntPtr camera);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_free")]
    public static partial void ViewportFree(IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_set_scene")]
    public static partial void ViewportSetScene(IntPtr viewport, IntPtr scene);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_get_scene")]
    public static partial IntPtr ViewportGetScene(IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_set_camera")]
    public static partial void ViewportSetCamera(IntPtr viewport, IntPtr camera);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_set_rect")]
    public static partial void ViewportSetRect(IntPtr viewport, float x, float y, float w, float h);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_set_pipeline")]
    public static partial void ViewportSetPipeline(IntPtr viewport, IntPtr pipeline);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_get_pipeline")]
    public static partial IntPtr ViewportGetPipeline(IntPtr viewport);

    // Internal entities (for viewport-specific components like camera controllers)
    [LibraryImport(DLL, EntryPoint = "tc_viewport_set_internal_entities")]
    public static partial void ViewportSetInternalEntities(IntPtr viewport, IntPtr pool, TcEntityId entityId);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_has_internal_entities")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool ViewportHasInternalEntities(IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_get_internal_entities_pool")]
    public static partial IntPtr ViewportGetInternalEntitiesPool(IntPtr viewport);

    [LibraryImport(DLL, EntryPoint = "tc_viewport_get_internal_entities_id")]
    public static partial TcEntityId ViewportGetInternalEntitiesId(IntPtr viewport);
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
