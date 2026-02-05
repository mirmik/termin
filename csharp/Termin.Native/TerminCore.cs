using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// P/Invoke declarations for termin_core.dll (C API).
/// </summary>
public static class TerminCore
{
    const string DLL = "termin_core";

    // ========================================================================
    // Library Initialization
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_init")]
    public static extern void Init();

    [DllImport(DLL, EntryPoint = "tc_shutdown")]
    public static extern void Shutdown();

    // ========================================================================
    // Scene (handle-based API)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_scene_new")]
    public static extern TcSceneHandle SceneNew();

    [DllImport(DLL, EntryPoint = "tc_scene_new_named", CharSet = CharSet.Ansi)]
    public static extern TcSceneHandle SceneNewNamed(string name);

    [DllImport(DLL, EntryPoint = "tc_scene_free")]
    public static extern void SceneFree(TcSceneHandle scene);

    [DllImport(DLL, EntryPoint = "tc_scene_alive")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool SceneAlive(TcSceneHandle scene);

    [DllImport(DLL, EntryPoint = "tc_scene_update")]
    public static extern void SceneUpdate(TcSceneHandle scene, double dt);

    [DllImport(DLL, EntryPoint = "tc_scene_editor_update")]
    public static extern void SceneEditorUpdate(TcSceneHandle scene, double dt);

    [DllImport(DLL, EntryPoint = "tc_scene_before_render")]
    public static extern void SceneBeforeRender(TcSceneHandle scene);

    [DllImport(DLL, EntryPoint = "tc_scene_entity_pool")]
    public static extern IntPtr SceneEntityPool(TcSceneHandle scene);

    [DllImport(DLL, EntryPoint = "tc_scene_entity_count")]
    public static extern nuint SceneEntityCount(TcSceneHandle scene);

    // EntityPool lifecycle (for standalone pools)
    [DllImport(DLL, EntryPoint = "tc_entity_pool_create")]
    public static extern IntPtr EntityPoolCreate(nuint initialCapacity);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_destroy")]
    public static extern void EntityPoolDestroy(IntPtr pool);

    // EntityPool registry (for C++ components to find Entity)
    [DllImport(DLL, EntryPoint = "tc_entity_pool_registry_register")]
    public static extern TcEntityPoolHandle EntityPoolRegistryRegister(IntPtr pool);

    // ========================================================================
    // Entity Pool
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_entity_pool_alloc", CharSet = CharSet.Ansi)]
    public static extern TcEntityId EntityPoolAlloc(IntPtr pool, string name);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_alloc_with_uuid", CharSet = CharSet.Ansi)]
    public static extern TcEntityId EntityPoolAllocWithUuid(IntPtr pool, string name, string uuid);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_free")]
    public static extern void EntityPoolFree(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_alive")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool EntityPoolAlive(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_count")]
    public static extern nuint EntityPoolCount(IntPtr pool);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_name", CharSet = CharSet.Ansi)]
    public static extern IntPtr EntityPoolName(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_name", CharSet = CharSet.Ansi)]
    public static extern void EntityPoolSetName(IntPtr pool, TcEntityId id, string name);

    // Transform
    [DllImport(DLL, EntryPoint = "tc_entity_pool_get_local_position")]
    public static extern void EntityPoolGetLocalPosition(IntPtr pool, TcEntityId id, double[] xyz);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_local_position")]
    public static extern void EntityPoolSetLocalPosition(IntPtr pool, TcEntityId id, double[] xyz);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_get_local_rotation")]
    public static extern void EntityPoolGetLocalRotation(IntPtr pool, TcEntityId id, double[] xyzw);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_local_rotation")]
    public static extern void EntityPoolSetLocalRotation(IntPtr pool, TcEntityId id, double[] xyzw);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_get_local_scale")]
    public static extern void EntityPoolGetLocalScale(IntPtr pool, TcEntityId id, double[] xyz);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_local_scale")]
    public static extern void EntityPoolSetLocalScale(IntPtr pool, TcEntityId id, double[] xyz);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_get_world_matrix")]
    public static extern void EntityPoolGetWorldMatrix(IntPtr pool, TcEntityId id, double[] m16);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_update_transforms")]
    public static extern void EntityPoolUpdateTransforms(IntPtr pool);

    // Flags
    [DllImport(DLL, EntryPoint = "tc_entity_pool_visible")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool EntityPoolVisible(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_visible")]
    public static extern void EntityPoolSetVisible(IntPtr pool, TcEntityId id, [MarshalAs(UnmanagedType.U1)] bool v);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_enabled")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool EntityPoolEnabled(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_enabled")]
    public static extern void EntityPoolSetEnabled(IntPtr pool, TcEntityId id, [MarshalAs(UnmanagedType.U1)] bool v);

    // Hierarchy
    [DllImport(DLL, EntryPoint = "tc_entity_pool_parent")]
    public static extern TcEntityId EntityPoolParent(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_set_parent")]
    public static extern void EntityPoolSetParent(IntPtr pool, TcEntityId id, TcEntityId parent);

    // Components
    [DllImport(DLL, EntryPoint = "tc_entity_pool_component_count")]
    public static extern nuint EntityPoolComponentCount(IntPtr pool, TcEntityId id);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_component_at")]
    public static extern IntPtr EntityPoolComponentAt(IntPtr pool, TcEntityId id, nuint index);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_remove_component")]
    public static extern void EntityPoolRemoveComponent(IntPtr pool, TcEntityId id, IntPtr component);

    // ========================================================================
    // Pipeline
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_pipeline_create", CharSet = CharSet.Ansi)]
    public static extern IntPtr PipelineCreate(string name);

    [DllImport(DLL, EntryPoint = "tc_pipeline_destroy")]
    public static extern void PipelineDestroy(IntPtr pipeline);

    [DllImport(DLL, EntryPoint = "tc_pipeline_add_pass")]
    public static extern void PipelineAddPass(IntPtr pipeline, IntPtr pass);

    // ========================================================================
    // Render
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_create")]
    public static extern IntPtr FboPoolCreate();

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_destroy")]
    public static extern void FboPoolDestroy(IntPtr pool);

    [DllImport(DLL, EntryPoint = "tc_render_view_to_fbo")]
    public static extern void RenderViewToFbo(
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

    [DllImport(DLL, EntryPoint = "tc_mesh_init")]
    public static extern void MeshInit();

    [DllImport(DLL, EntryPoint = "tc_mesh_shutdown")]
    public static extern void MeshShutdown();

    [DllImport(DLL, EntryPoint = "tc_mesh_create", CharSet = CharSet.Ansi)]
    public static extern TcMeshHandle MeshCreate(string? uuid);

    [DllImport(DLL, EntryPoint = "tc_mesh_get")]
    public static extern IntPtr MeshGet(TcMeshHandle handle);

    [DllImport(DLL, EntryPoint = "tc_mesh_set_data", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool MeshSetData(
        IntPtr mesh,
        IntPtr vertices,
        nuint vertexCount,
        ref TcVertexLayout layout,
        IntPtr indices,
        nuint indexCount,
        string? name
    );

    [DllImport(DLL, EntryPoint = "tc_mesh_upload_gpu")]
    public static extern uint MeshUploadGpu(IntPtr mesh);

    [DllImport(DLL, EntryPoint = "tc_mesh_draw_gpu")]
    public static extern void MeshDrawGpu(IntPtr mesh);

    // ========================================================================
    // Vertex Layout
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_init")]
    public static extern void VertexLayoutInit(ref TcVertexLayout layout);

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_add", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool VertexLayoutAdd(
        ref TcVertexLayout layout,
        string name,
        byte size,
        TcAttribType type,
        byte location
    );

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_pos")]
    public static extern TcVertexLayout VertexLayoutPos();

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal")]
    public static extern TcVertexLayout VertexLayoutPosNormal();

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal_uv")]
    public static extern TcVertexLayout VertexLayoutPosNormalUv();

    [DllImport(DLL, EntryPoint = "tc_vertex_layout_pos_normal_uv_color")]
    public static extern TcVertexLayout VertexLayoutPosNormalUvColor();

    // ========================================================================
    // Shader Registry
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_shader_init")]
    public static extern void ShaderInit();

    [DllImport(DLL, EntryPoint = "tc_shader_shutdown")]
    public static extern void ShaderShutdown();

    [DllImport(DLL, EntryPoint = "tc_shader_from_sources", CharSet = CharSet.Ansi)]
    public static extern TcShaderHandle ShaderFromSources(
        string vertexSource,
        string fragmentSource,
        string? geometrySource,
        string? name,
        string? sourcePath,
        string? uuid
    );

    [DllImport(DLL, EntryPoint = "tc_shader_get")]
    public static extern IntPtr ShaderGet(TcShaderHandle handle);

    [DllImport(DLL, EntryPoint = "tc_shader_compile_gpu")]
    public static extern uint ShaderCompileGpu(IntPtr shader);

    [DllImport(DLL, EntryPoint = "tc_shader_use_gpu")]
    public static extern void ShaderUseGpu(IntPtr shader);

    [DllImport(DLL, EntryPoint = "tc_shader_set_int")]
    public static extern void ShaderSetInt(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, int value);

    [DllImport(DLL, EntryPoint = "tc_shader_set_float")]
    public static extern void ShaderSetFloat(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float value);

    [DllImport(DLL, EntryPoint = "tc_shader_set_vec3")]
    public static extern void ShaderSetVec3(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float x, float y, float z);

    [DllImport(DLL, EntryPoint = "tc_shader_set_vec4")]
    public static extern void ShaderSetVec4(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float x, float y, float z, float w);

    [DllImport(DLL, EntryPoint = "tc_shader_set_mat4")]
    public static extern void ShaderSetMat4(IntPtr shader, [MarshalAs(UnmanagedType.LPStr)] string name, float[] data, [MarshalAs(UnmanagedType.U1)] bool transpose);

    // ========================================================================
    // Material Registry
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_material_init")]
    public static extern void MaterialInit();

    [DllImport(DLL, EntryPoint = "tc_material_shutdown")]
    public static extern void MaterialShutdown();

    [DllImport(DLL, EntryPoint = "tc_material_create", CharSet = CharSet.Ansi)]
    public static extern TcMaterialHandle MaterialCreate(string? uuid, string name);

    [DllImport(DLL, EntryPoint = "tc_material_get")]
    public static extern IntPtr MaterialGet(TcMaterialHandle handle);

    [DllImport(DLL, EntryPoint = "tc_material_add_phase", CharSet = CharSet.Ansi)]
    public static extern IntPtr MaterialAddPhase(IntPtr material, TcShaderHandle shader, string phaseMark, int priority);

    [DllImport(DLL, EntryPoint = "tc_material_set_color")]
    public static extern void MaterialSetColor(IntPtr material, float r, float g, float b, float a);

    [DllImport(DLL, EntryPoint = "tc_material_phase_apply_gpu")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool MaterialPhaseApplyGpu(IntPtr phase);

    // ========================================================================
    // Component Registry
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_component_registry_create", CharSet = CharSet.Ansi)]
    public static extern IntPtr ComponentRegistryCreate(string typeName);

    [DllImport(DLL, EntryPoint = "tc_component_registry_has", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentRegistryHas(string typeName);

    [DllImport(DLL, EntryPoint = "tc_entity_pool_add_component")]
    public static extern void EntityPoolAddComponent(IntPtr pool, TcEntityId id, IntPtr component);

    // ========================================================================
    // Component Properties (for ComponentRef)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_component_get_type_name")]
    public static extern IntPtr ComponentGetTypeName(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_get_enabled")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentGetEnabled(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_set_enabled")]
    public static extern void ComponentSetEnabled(IntPtr component, [MarshalAs(UnmanagedType.U1)] bool enabled);

    [DllImport(DLL, EntryPoint = "tc_component_get_active_in_editor")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentGetActiveInEditor(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_set_active_in_editor")]
    public static extern void ComponentSetActiveInEditor(IntPtr component, [MarshalAs(UnmanagedType.U1)] bool active);

    [DllImport(DLL, EntryPoint = "tc_component_get_is_drawable")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentGetIsDrawable(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_get_is_input_handler")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentGetIsInputHandler(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_get_kind")]
    public static extern int ComponentGetKind(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_get_owner_entity_id")]
    public static extern TcEntityId ComponentGetOwnerEntityId(IntPtr component);

    [DllImport(DLL, EntryPoint = "tc_component_get_owner_pool")]
    public static extern IntPtr ComponentGetOwnerPool(IntPtr component);

    // ========================================================================
    // Component Field Access (Inspect) - in entity_lib
    // ========================================================================

    private const string ENTITY_DLL = "entity_lib";

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_int", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldInt(IntPtr component, string path, long value, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_float", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldFloat(IntPtr component, string path, float value, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_double", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldDouble(IntPtr component, string path, double value, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_bool", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldBool(IntPtr component, string path, [MarshalAs(UnmanagedType.U1)] bool value, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_string", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldString(IntPtr component, string path, string value, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_mesh", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldMesh(IntPtr component, string path, TcMeshHandle handle, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_set_field_material", CharSet = CharSet.Ansi)]
    public static extern void ComponentSetFieldMaterial(IntPtr component, string path, TcMaterialHandle handle, IntPtr scene);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_int", CharSet = CharSet.Ansi)]
    public static extern long ComponentGetFieldInt(IntPtr component, string path);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_float", CharSet = CharSet.Ansi)]
    public static extern float ComponentGetFieldFloat(IntPtr component, string path);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_double", CharSet = CharSet.Ansi)]
    public static extern double ComponentGetFieldDouble(IntPtr component, string path);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_bool", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ComponentGetFieldBool(IntPtr component, string path);

    [DllImport(ENTITY_DLL, EntryPoint = "tc_component_get_field_string", CharSet = CharSet.Ansi)]
    public static extern IntPtr ComponentGetFieldString(IntPtr component, string path);

    // ========================================================================
    // Pass Registry
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_pass_registry_has", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool PassRegistryHas(string typeName);

    [DllImport(DLL, EntryPoint = "tc_pass_registry_create", CharSet = CharSet.Ansi)]
    public static extern IntPtr PassRegistryCreate(string typeName);

    [DllImport(DLL, EntryPoint = "tc_pass_registry_type_count")]
    public static extern nuint PassRegistryTypeCount();

    [DllImport(DLL, EntryPoint = "tc_pass_registry_type_at")]
    public static extern IntPtr PassRegistryTypeAt(nuint index);

    [DllImport(DLL, EntryPoint = "tc_pass_set_name", CharSet = CharSet.Ansi)]
    public static extern void PassSetName(IntPtr pass, string name);

    [DllImport(DLL, EntryPoint = "tc_pass_set_enabled")]
    public static extern void PassSetEnabled(IntPtr pass, [MarshalAs(UnmanagedType.U1)] bool enabled);

    [DllImport(DLL, EntryPoint = "tc_pass_drop")]
    public static extern void PassDrop(IntPtr pass);

    // ========================================================================
    // FBO Pool Extended
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_ensure", CharSet = CharSet.Ansi)]
    public static extern IntPtr FboPoolEnsure(
        IntPtr pool,
        string key,
        int width,
        int height,
        int samples,
        string? format
    );

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_get", CharSet = CharSet.Ansi)]
    public static extern IntPtr FboPoolGet(IntPtr pool, string key);

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_set", CharSet = CharSet.Ansi)]
    public static extern void FboPoolSet(IntPtr pool, string key, IntPtr fbo);

    [DllImport(DLL, EntryPoint = "tc_fbo_pool_clear")]
    public static extern void FboPoolClear(IntPtr pool);

    // ========================================================================
    // tc_value - Tagged union for field values
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_value_nil")]
    public static extern TcValue ValueNil();

    [DllImport(DLL, EntryPoint = "tc_value_bool")]
    public static extern TcValue ValueBool([MarshalAs(UnmanagedType.U1)] bool v);

    [DllImport(DLL, EntryPoint = "tc_value_int")]
    public static extern TcValue ValueInt(long v);

    [DllImport(DLL, EntryPoint = "tc_value_float")]
    public static extern TcValue ValueFloat(float v);

    [DllImport(DLL, EntryPoint = "tc_value_double")]
    public static extern TcValue ValueDouble(double v);

    [DllImport(DLL, EntryPoint = "tc_value_string", CharSet = CharSet.Ansi)]
    public static extern TcValue ValueString(string s);

    [DllImport(DLL, EntryPoint = "tc_value_free")]
    public static extern void ValueFree(ref TcValue v);

    // ========================================================================
    // tc_inspect - Field inspection and access
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_inspect_has_type", CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool InspectHasType(string typeName);

    [DllImport(DLL, EntryPoint = "tc_inspect_field_count", CharSet = CharSet.Ansi)]
    public static extern nuint InspectFieldCount(string typeName);

    [DllImport(DLL, EntryPoint = "tc_inspect_get", CharSet = CharSet.Ansi)]
    public static extern TcValue InspectGet(IntPtr obj, string typeName, string path);

    [DllImport(DLL, EntryPoint = "tc_inspect_set", CharSet = CharSet.Ansi)]
    public static extern void InspectSet(IntPtr obj, string typeName, string path, TcValue value, IntPtr scene);

    // ========================================================================
    // Pass field inspection (via tc_pass*)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_pass_inspect_get", CharSet = CharSet.Ansi)]
    public static extern TcValue PassInspectGet(IntPtr pass, string path);

    [DllImport(DLL, EntryPoint = "tc_pass_inspect_set", CharSet = CharSet.Ansi)]
    public static extern void PassInspectSet(IntPtr pass, string path, TcValue value, IntPtr scene);

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

    [DllImport(DLL, EntryPoint = "tc_component_set_external_callbacks")]
    public static extern void ComponentSetExternalCallbacks(ref ComponentExternalCallbacks callbacks);

    [DllImport(DLL, EntryPoint = "tc_component_body_incref")]
    public static extern void ComponentBodyIncref(IntPtr body);

    [DllImport(DLL, EntryPoint = "tc_component_body_decref")]
    public static extern void ComponentBodyDecref(IntPtr body);

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

    [DllImport(DLL, EntryPoint = "tc_pass_set_external_callbacks")]
    public static extern void PassSetExternalCallbacks(ref PassExternalCallbacks callbacks);

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

    [DllImport(DLL, EntryPoint = "tc_render_surface_new_external")]
    public static extern IntPtr RenderSurfaceNewExternal(IntPtr body, ref RenderSurfaceVTable vtable);

    [DllImport(DLL, EntryPoint = "tc_render_surface_free_external")]
    public static extern void RenderSurfaceFreeExternal(IntPtr surface);

    // ========================================================================
    // Display (tc_display)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_display_new", CharSet = CharSet.Ansi)]
    public static extern IntPtr DisplayNew(string name, IntPtr surface);

    [DllImport(DLL, EntryPoint = "tc_display_free")]
    public static extern void DisplayFree(IntPtr display);

    [DllImport(DLL, EntryPoint = "tc_display_set_name", CharSet = CharSet.Ansi)]
    public static extern void DisplaySetName(IntPtr display, string name);

    [DllImport(DLL, EntryPoint = "tc_display_get_name")]
    public static extern IntPtr DisplayGetName(IntPtr display);

    [DllImport(DLL, EntryPoint = "tc_display_get_size")]
    public static extern void DisplayGetSize(IntPtr display, out int width, out int height);

    [DllImport(DLL, EntryPoint = "tc_display_add_viewport")]
    public static extern void DisplayAddViewport(IntPtr display, TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_display_remove_viewport")]
    public static extern void DisplayRemoveViewport(IntPtr display, TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_display_get_viewport_count")]
    public static extern nuint DisplayGetViewportCount(IntPtr display);

    [DllImport(DLL, EntryPoint = "tc_display_get_first_viewport")]
    public static extern TcViewportHandle DisplayGetFirstViewport(IntPtr display);

    [DllImport(DLL, EntryPoint = "tc_display_viewport_at_screen")]
    public static extern TcViewportHandle DisplayViewportAtScreen(IntPtr display, float px, float py);

    // ========================================================================
    // Input Manager (tc_input_manager)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_input_manager_dispatch_mouse_button")]
    public static extern void InputManagerDispatchMouseButton(IntPtr manager, int button, int action, int mods);

    [DllImport(DLL, EntryPoint = "tc_input_manager_dispatch_mouse_move")]
    public static extern void InputManagerDispatchMouseMove(IntPtr manager, double x, double y);

    [DllImport(DLL, EntryPoint = "tc_input_manager_dispatch_scroll")]
    public static extern void InputManagerDispatchScroll(IntPtr manager, double x, double y, int mods);

    [DllImport(DLL, EntryPoint = "tc_input_manager_dispatch_key")]
    public static extern void InputManagerDispatchKey(IntPtr manager, int key, int scancode, int action, int mods);

    [DllImport(DLL, EntryPoint = "tc_input_manager_dispatch_char")]
    public static extern void InputManagerDispatchChar(IntPtr manager, uint codepoint);

    // ========================================================================
    // Simple Input Manager (tc_simple_input_manager)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_simple_input_manager_new")]
    public static extern IntPtr SimpleInputManagerNew(IntPtr display);

    [DllImport(DLL, EntryPoint = "tc_simple_input_manager_free")]
    public static extern void SimpleInputManagerFree(IntPtr manager);

    [DllImport(DLL, EntryPoint = "tc_simple_input_manager_base")]
    public static extern IntPtr SimpleInputManagerBase(IntPtr manager);

    // ========================================================================
    // Viewport (tc_viewport) - handle-based API
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_viewport_new", CharSet = CharSet.Ansi)]
    public static extern TcViewportHandle ViewportNew(string? name, TcSceneHandle scene, IntPtr camera);

    [DllImport(DLL, EntryPoint = "tc_viewport_free")]
    public static extern void ViewportFree(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_alive")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ViewportAlive(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_scene")]
    public static extern void ViewportSetScene(TcViewportHandle viewport, TcSceneHandle scene);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_scene")]
    public static extern TcSceneHandle ViewportGetScene(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_camera")]
    public static extern void ViewportSetCamera(TcViewportHandle viewport, IntPtr camera);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_camera")]
    public static extern IntPtr ViewportGetCamera(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_rect")]
    public static extern void ViewportSetRect(TcViewportHandle viewport, float x, float y, float w, float h);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_pipeline")]
    public static extern void ViewportSetPipeline(TcViewportHandle viewport, TcPipelineHandle pipeline);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_pipeline")]
    public static extern TcPipelineHandle ViewportGetPipeline(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_enabled")]
    public static extern void ViewportSetEnabled(TcViewportHandle viewport, [MarshalAs(UnmanagedType.U1)] bool enabled);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_enabled")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ViewportGetEnabled(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_set_depth")]
    public static extern void ViewportSetDepth(TcViewportHandle viewport, int depth);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_depth")]
    public static extern int ViewportGetDepth(TcViewportHandle viewport);

    // Internal entities (for viewport-specific components like camera controllers)
    [DllImport(DLL, EntryPoint = "tc_viewport_set_internal_entities")]
    public static extern void ViewportSetInternalEntities(TcViewportHandle viewport, TcEntityHandle entityHandle);

    [DllImport(DLL, EntryPoint = "tc_viewport_has_internal_entities")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static extern bool ViewportHasInternalEntities(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_internal_entities_pool")]
    public static extern IntPtr ViewportGetInternalEntitiesPool(TcViewportHandle viewport);

    [DllImport(DLL, EntryPoint = "tc_viewport_get_internal_entities_id")]
    public static extern TcEntityId ViewportGetInternalEntitiesId(TcViewportHandle viewport);

    // ========================================================================
    // Primitive Mesh Generation (tc_primitive_mesh)
    // ========================================================================

    [DllImport(DLL, EntryPoint = "tc_primitive_cube")]
    public static extern IntPtr PrimitiveCube(float sizeX, float sizeY, float sizeZ);

    [DllImport(DLL, EntryPoint = "tc_primitive_sphere")]
    public static extern IntPtr PrimitiveSphere(float radius, int meridians, int parallels);

    [DllImport(DLL, EntryPoint = "tc_primitive_cylinder")]
    public static extern IntPtr PrimitiveCylinder(float radius, float height, int segments);

    [DllImport(DLL, EntryPoint = "tc_primitive_cone")]
    public static extern IntPtr PrimitiveCone(float radius, float height, int segments);

    [DllImport(DLL, EntryPoint = "tc_primitive_plane")]
    public static extern IntPtr PrimitivePlane(float width, float height, int segmentsW, int segmentsH);

    // Lazy singleton primitives - return handles to shared meshes in registry
    [DllImport(DLL, EntryPoint = "tc_primitive_unit_cube")]
    public static extern TcMeshHandle PrimitiveUnitCube();

    [DllImport(DLL, EntryPoint = "tc_primitive_unit_sphere")]
    public static extern TcMeshHandle PrimitiveUnitSphere();

    [DllImport(DLL, EntryPoint = "tc_primitive_unit_cylinder")]
    public static extern TcMeshHandle PrimitiveUnitCylinder();

    [DllImport(DLL, EntryPoint = "tc_primitive_unit_cone")]
    public static extern TcMeshHandle PrimitiveUnitCone();

    [DllImport(DLL, EntryPoint = "tc_primitive_unit_plane")]
    public static extern TcMeshHandle PrimitiveUnitPlane();

    [DllImport(DLL, EntryPoint = "tc_primitive_cleanup")]
    public static extern void PrimitiveCleanup();

    // ========================================================================
    // Collision Detection (tc_collision)
    // Note: These functions are in entity_lib.dll because collision detection
    // requires the C++ CollisionWorld class which is part of entity_lib.
    // ========================================================================

    private const string ENTITY_LIB_DLL = "entity_lib";

    /// <summary>
    /// Update all collider positions in the collision world.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_scene_collision_update")]
    public static extern void SceneCollisionUpdate(TcSceneHandle scene);

    /// <summary>
    /// Check if there are any collisions in the scene.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_scene_has_collisions")]
    public static extern int SceneHasCollisions(TcSceneHandle scene);

    /// <summary>
    /// Get the number of collision pairs detected.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_scene_collision_count")]
    public static extern nuint SceneCollisionCount(TcSceneHandle scene);

    /// <summary>
    /// Contact point data.
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct TcContactPoint
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 3)]
        public double[] Position;
        public double Penetration;
    }

    /// <summary>
    /// Contact manifold data - information about a collision pair.
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct TcContactManifold
    {
        public TcEntityId EntityA;
        public TcEntityId EntityB;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 3)]
        public double[] Normal;
        public int PointCount;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public TcContactPoint[] Points;
    }

    /// <summary>
    /// Detect all collisions and get manifolds.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_scene_detect_collisions")]
    public static extern IntPtr SceneDetectCollisions(TcSceneHandle scene, out nuint outCount);

    /// <summary>
    /// Get collision manifold at index.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_scene_get_collision")]
    public static extern IntPtr SceneGetCollision(TcSceneHandle scene, nuint index);

    // ========================================================================
    // Collision World Management
    // ========================================================================

    /// <summary>
    /// Create a new CollisionWorld.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_collision_world_create")]
    public static extern IntPtr CollisionWorldCreate();

    /// <summary>
    /// Destroy a CollisionWorld.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_collision_world_destroy")]
    public static extern void CollisionWorldDestroy(IntPtr cw);

    /// <summary>
    /// Get number of colliders in the world.
    /// </summary>
    [DllImport(ENTITY_LIB_DLL, EntryPoint = "tc_collision_world_size")]
    public static extern int CollisionWorldSize(IntPtr cw);

    /// <summary>
    /// Set the collision world for a scene.
    /// </summary>
    [DllImport(DLL, EntryPoint = "tc_scene_set_collision_world")]
    public static extern void SceneSetCollisionWorld(TcSceneHandle scene, IntPtr cw);

    /// <summary>
    /// Get the collision world for a scene.
    /// </summary>
    [DllImport(DLL, EntryPoint = "tc_scene_get_collision_world")]
    public static extern IntPtr SceneGetCollisionWorld(TcSceneHandle scene);
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
