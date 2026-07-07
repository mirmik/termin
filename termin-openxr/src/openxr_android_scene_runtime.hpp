tc_pass* create_scene_pass(
    const char* type_name,
    const char* pass_name,
    std::initializer_list<std::pair<const char*, const char*>> fields
) {
    if (!tc_pass_registry_has(type_name)) {
        tc_log_error("[OpenXR scene] pass type is not registered: '%s'", type_name);
        return nullptr;
    }
    tc_pass* pass = tc_pass_registry_create(type_name);
    if (!pass) {
        tc_log_error("[OpenXR scene] failed to create pass '%s'", type_name);
        return nullptr;
    }
    tc_pass_set_name(pass, pass_name);
    for (const auto& [field, value] : fields) {
        tc_value field_value = tc_value_string(value);
        tc_pass_inspect_set(pass, field, field_value, nullptr);
        tc_value_free(&field_value);
    }
    return pass;
}

void set_pass_float(tc_pass* pass, const char* field, float value) {
    if (!pass || !field) {
        return;
    }
    tc_value field_value = tc_value_float(value);
    tc_pass_inspect_set(pass, field, field_value, nullptr);
    tc_value_free(&field_value);
}

void set_pass_int(tc_pass* pass, const char* field, int value) {
    if (!pass || !field) {
        return;
    }
    tc_value field_value = tc_value_int(value);
    tc_pass_inspect_set(pass, field, field_value, nullptr);
    tc_value_free(&field_value);
}

class UIWidgetPass : public termin::CxxFramePass {
public:
    std::string input_res = "color";
    std::string output_res = "color+widgets";

public:
    INSPECT_FIELD(UIWidgetPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(UIWidgetPass, output_res, "Output Resource", "string")
    INSPECT_TYPE_METADATA(UIWidgetPass, graph, termin::make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {}
    ))

    UIWidgetPass() {
        pass_name_set("UIWidgets");
        link_to_type_registry("UIWidgetPass");
    }

    std::set<const char*> compute_reads() const override {
        return {input_res.c_str()};
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {};
    }

    void execute(termin::ExecuteContext& ctx) override {
        if (!ctx.ctx2) {
            tc_log_error("[OpenXR UIWidgetPass] ctx.ctx2 is null");
            return;
        }

        auto in_it = ctx.tex2_reads.find(input_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second) {
            tc_log_warn("[OpenXR UIWidgetPass] missing tgfx2 input '%s'", input_res.c_str());
            return;
        }
        auto out_it = ctx.tex2_writes.find(output_res);
        if (out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc_log_warn("[OpenXR UIWidgetPass] missing tgfx2 output '%s'", output_res.c_str());
            return;
        }

        ctx.ctx2->blit(in_it->second, out_it->second);
    }
};

TC_REGISTER_FRAME_PASS(UIWidgetPass);

termin::RenderPipeline make_openxr_scene_pipeline() {
    tc_pipeline_handle ph = tc_pipeline_create("OpenXRScene");
    termin::RenderPipeline pipeline(ph);

    if (tc_pass* p = create_scene_pass("ColorPass", "Color", {
            {"input_res", "empty"},
            {"output_res", "color_opaque"},
            {"shadow_res", ""},
            {"phase_mark", "opaque"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }
    if (tc_pass* p = create_scene_pass("ColorPass", "Transparent", {
            {"input_res", "color_opaque"},
            {"output_res", "color"},
            {"shadow_res", ""},
            {"phase_mark", "transparent"},
            {"sort_mode", "far_to_near"}
    })) {
        tc_pipeline_add_pass(ph, p);
    }
    if (tc_pass* p = create_scene_pass("TonemapPass", "Tonemap", {
            {"input_res", "color"},
            {"output_res", "color_ldr"},
        })) {
        set_pass_float(p, "exposure", 1.0f);
        set_pass_int(p, "method", 0);
        tc_pipeline_add_pass(ph, p);
    }
    if (tc_pass* p = create_scene_pass("PresentToScreenPass", "Present", {
            {"input_res", "color_ldr"},
            {"output_res", "OUTPUT"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    const char* color_resources[] = {
        "empty",
        "color_opaque",
        "color",
        "color_ldr",
    };
    for (const char* resource : color_resources) {
        termin::ResourceSpec spec;
        spec.resource = resource;
        spec.format =
            (std::strcmp(resource, "color_ldr") == 0)
                ? "render_target"
                : "rgba16f";
        if (std::strcmp(resource, "empty") == 0) {
            spec.clear_color = std::array<double, 4>{0.015, 0.018, 0.024, 1.0};
            spec.clear_depth = 1.0f;
        }
        pipeline.add_spec(spec);
    }
    return pipeline;
}

bool cstr_nonempty(const char* value) {
    return value && value[0] != '\0';
}

std::string read_runtime_text_file(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    std::ostringstream out;
    out << in.rdbuf();
    if (!in.good() && !in.eof()) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return out.str();
}

const nos::trent* trent_dict_get(const nos::trent& t, const char* key) {
    if (!t.is_dict()) {
        return nullptr;
    }
    return t._get(key);
}

std::string trent_string_field(const nos::trent& t, const char* key) {
    const nos::trent* value = trent_dict_get(t, key);
    if (!value || !value->is_string()) {
        return "";
    }
    return value->as_string();
}

std::filesystem::path runtime_package_path(
    const std::filesystem::path& root,
    const std::string& rel
) {
    std::filesystem::path path(rel);
    if (path.is_absolute()) {
        throw std::runtime_error("runtime package path must be relative: " + rel);
    }
    return root / path;
}

std::string normalized_pipeline_name(const char* value) {
    if (!cstr_nonempty(value) || std::strcmp(value, "(Default)") == 0) {
        return "Default";
    }
    return value;
}

termin::RenderPipeline make_pipeline_for_xr_render_target(
    termin::EngineCore& engine,
    const tc_render_target_config* config
) {
    if (config && cstr_nonempty(config->pipeline_uuid)) {
        const std::string pipeline_uuid = config->pipeline_uuid;
        tc_pipeline_handle handle = engine.rendering_manager.create_pipeline(pipeline_uuid);
        if (tc_pipeline_handle_valid(handle)) {
            termin::RenderPipeline pipeline(handle);
            tc_log_info(
                "[OpenXR scene] using render target pipeline uuid='%s' name='%s' passes=%zu",
                pipeline_uuid.c_str(),
                cstr_nonempty(config->pipeline_name) ? config->pipeline_name : "",
                pipeline.pass_count()
            );
            return pipeline;
        }

        tc_log_warn(
            "[OpenXR scene] failed to create render target pipeline uuid='%s'; trying pipeline_name",
            pipeline_uuid.c_str()
        );
    }

    if (config && cstr_nonempty(config->pipeline_name)) {
        const std::string pipeline_name = normalized_pipeline_name(config->pipeline_name);
        tc_pipeline_handle handle = engine.rendering_manager.create_pipeline(pipeline_name);
        if (tc_pipeline_handle_valid(handle)) {
            termin::RenderPipeline pipeline(handle);
            tc_log_info(
                "[OpenXR scene] using render target pipeline '%s' passes=%zu",
                pipeline_name.c_str(),
                pipeline.pass_count()
            );
            return pipeline;
        }

        tc_log_error(
            "[OpenXR scene] failed to create render target pipeline '%s'",
            pipeline_name.c_str()
        );
    }

    tc_log_warn("[OpenXR scene] using built-in OpenXRScene fallback pipeline");
    return make_openxr_scene_pipeline();
}

const tc_render_target_config* find_xr_render_target_config(termin::TcSceneRef scene) {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene.handle());
    if (!mount) {
        return nullptr;
    }
    for (size_t i = 0; i < mount->render_target_config_count; ++i) {
        const tc_render_target_config& config = mount->render_target_configs[i];
        tc_render_target_kind kind = TC_RENDER_TARGET_TEXTURE_2D;
        if (config.kind && tc_render_target_kind_from_string(config.kind, &kind)
                && kind == TC_RENDER_TARGET_XR_STEREO
                && config.enabled) {
            return &config;
        }
    }
    return nullptr;
}

termin::XrOriginComponent* xr_origin_component_from_entity_uuid(termin::TcSceneRef scene, const char* uuid) {
    if (!uuid || uuid[0] == '\0') {
        return nullptr;
    }
    tc_entity_pool* pool = tc_scene_entity_pool(scene.handle());
    if (!pool) {
        return nullptr;
    }
    tc_entity_id entity_id = tc_entity_pool_find_by_uuid(pool, uuid);
    if (!tc_entity_id_valid(entity_id)) {
        return nullptr;
    }
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    termin::Entity entity(tc_entity_handle_make(pool_handle, entity_id));
    tc_component* raw = entity.get_component_by_type_name("XrOriginComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent* cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::XrOriginComponent*>(cxx);
}

termin::XrOriginComponent* find_first_runtime_xr_origin(termin::TcSceneRef scene) {
    tc_component* raw = tc_scene_first_component_of_type(scene.handle(), "XrOriginComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent* cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::XrOriginComponent*>(cxx);
}

termin::XrOriginComponent* resolve_runtime_xr_origin(
    termin::TcSceneRef scene,
    const tc_render_target_config* xr_config
) {
    if (xr_config) {
        const char* target_name = xr_config->name ? xr_config->name : "XRStereoTarget";
        if (!xr_config->xr_origin_uuid || xr_config->xr_origin_uuid[0] == '\0') {
            tc_log_error("[OpenXR scene] xr_stereo render target '%s' has no xr_origin_uuid", target_name);
            return nullptr;
        }
        termin::XrOriginComponent* xr_origin = xr_origin_component_from_entity_uuid(scene, xr_config->xr_origin_uuid);
        if (!xr_origin) {
            tc_log_error(
                "[OpenXR scene] xr_stereo render target '%s' xr_origin_uuid '%s' does not resolve to XrOriginComponent",
                target_name,
                xr_config->xr_origin_uuid
            );
            return nullptr;
        }
        return xr_origin;
    }

    tc_log(
        TC_LOG_WARN,
        "[OpenXR scene] no xr_stereo render target config found; using first XrOriginComponent"
    );
    return find_first_runtime_xr_origin(scene);
}

void register_openxr_scene_runtime() {
    static bool registered = false;
    if (registered) {
        return;
    }
    registered = true;

    termin_scene_runtime_init();
    tc_inspect_kind_core_init();
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    termin_collision_runtime_init();
    tc::KindRegistryCpp::instance();
    termin::MeshComponent::register_type();
    termin::XrOriginComponent::register_type();
    termin::XrThumbstickLocomotionComponent::register_type();
}

struct OpenXRRuntimeScene {
    struct EyeFrame {
        tgfx::TextureHandle color_texture;
        tgfx::TextureHandle depth_texture;
        uint32_t width = 0;
        uint32_t height = 0;
        tgfx::PixelFormat color_format = tgfx::PixelFormat::Undefined;
        XrView view{};
        uint32_t eye_index = 0;
        bool valid = false;
    };

    std::unique_ptr<termin::EngineCore> engine;
    termin::runtime::RuntimePackageLoadResult package;
    termin::TcSceneRef scene;
    termin::RenderPipeline pipeline;
    tc_render_target_handle xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    termin::XrOriginComponent* xr_origin = nullptr;
    termin::Mat44 origin_from_xr_reference = termin::Mat44::identity();
    EyeFrame active_eye_frame;
    std::unordered_map<std::string, std::filesystem::path> runtime_pipeline_paths;
    bool reference_alignment_initialized = false;
    bool ready = false;

    void reset_reference_alignment() {
        origin_from_xr_reference = termin::Mat44::identity();
        reference_alignment_initialized = false;
    }

    bool update_reference_alignment(const XrView& view, XrViewStateFlags view_state_flags) {
        if (reference_alignment_initialized) {
            return true;
        }
        if (!xr_origin) {
            return false;
        }

        if (xr_origin->reference_alignment == termin::XrReferenceAlignment::StageAxes) {
            origin_from_xr_reference = termin::Mat44::identity();
            reference_alignment_initialized = true;
            tc_log_info("[OpenXR scene] XR reference alignment initialized mode=stage_axes yaw_degrees=0");
            return true;
        }

        if ((view_state_flags & XR_VIEW_STATE_ORIENTATION_VALID_BIT) == 0) {
            return false;
        }

        termin::Vec3 forward = xr_direction_to_scene_direction(
            rotate_xr_vector(view.pose.orientation, XrVector3f{0.0f, 0.0f, -1.0f})
        );
        forward.z = 0.0;
        const double len = forward.norm();
        if (len < 1e-6) {
            tc_log_warn("[OpenXR scene] cannot initialize XR reference alignment: head forward is vertical");
            return false;
        }
        forward = forward / len;

        const double yaw = std::atan2(forward.x, forward.y);
        origin_from_xr_reference =
            termin::Mat44::rotation_axis_angle(termin::Vec3{0.0, 0.0, 1.0}, yaw);
        reference_alignment_initialized = true;

        constexpr double kRadToDeg = 180.0 / 3.14159265358979323846;
        tc_log_info(
            "[OpenXR scene] XR reference alignment initialized mode=initial_head_yaw "
            "yaw_degrees=%.3f initial_forward=(%.3f, %.3f, %.3f)",
            yaw * kRadToDeg,
            forward.x,
            forward.y,
            forward.z
        );
        return true;
    }

    void install_runtime_pipeline_factory(const std::string& asset_root) {
        runtime_pipeline_paths.clear();
        const std::filesystem::path root(asset_root);
        const std::filesystem::path manifest_path = root / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            return;
        }

        try {
            nos::trent manifest = nos::json::parse(read_runtime_text_file(manifest_path));
            const nos::trent* resources = trent_dict_get(manifest, "resources");
            if (!resources || !resources->is_list()) {
                return;
            }

            for (const nos::trent& resource : resources->as_list()) {
                if (!resource.is_dict()) {
                    continue;
                }
                if (trent_string_field(resource, "type") != "pipeline") {
                    continue;
                }

                const std::string path = trent_string_field(resource, "path");
                if (path.empty()) {
                    tc_log_warn("[OpenXR scene] runtime pipeline resource has no path");
                    continue;
                }

                const std::filesystem::path full_path = runtime_package_path(root, path);
                const std::string uuid = trent_string_field(resource, "uuid");
                const std::string name = trent_string_field(resource, "name");
                if (!uuid.empty()) {
                    runtime_pipeline_paths[uuid] = full_path;
                }
                if (!name.empty()) {
                    runtime_pipeline_paths[name] = full_path;
                }
                tc_log_info(
                    "[OpenXR scene] registered runtime pipeline asset name='%s' uuid='%s' path='%s'",
                    name.empty() ? "(unnamed)" : name.c_str(),
                    uuid.empty() ? "(none)" : uuid.c_str(),
                    path.c_str()
                );
            }
        } catch (const std::exception& e) {
            tc_log_error("[OpenXR scene] failed to read runtime pipeline assets: %s", e.what());
            return;
        }

        if (runtime_pipeline_paths.empty()) {
            return;
        }

        engine->rendering_manager.set_pipeline_factory(
            [this](const std::string& key) -> tc_pipeline_handle {
                auto it = runtime_pipeline_paths.find(key);
                if (it == runtime_pipeline_paths.end()) {
                    tc_log_error("[OpenXR scene] runtime pipeline asset '%s' was not found", key.c_str());
                    return TC_PIPELINE_HANDLE_INVALID;
                }

                try {
                    std::unique_ptr<termin::RenderPipeline> compiled(
                        tc::compile_graph(read_runtime_text_file(it->second))
                    );
                    if (!compiled || !compiled->is_valid()) {
                        tc_log_error("[OpenXR scene] failed to compile runtime pipeline '%s'", key.c_str());
                        return TC_PIPELINE_HANDLE_INVALID;
                    }
                    compiled->set_name(key);
                    tc_pipeline_handle handle = compiled->handle();
                    tc_log_info(
                        "[OpenXR scene] compiled runtime pipeline '%s' passes=%zu",
                        key.c_str(),
                        compiled->pass_count()
                    );
                    return handle;
                } catch (const std::exception& e) {
                    tc_log_error(
                        "[OpenXR scene] runtime pipeline '%s' compile failed: %s",
                        key.c_str(),
                        e.what()
                    );
                    return TC_PIPELINE_HANDLE_INVALID;
                }
            }
        );
    }

    bool load(const std::string& asset_root) {
        if (ready) {
            return true;
        }
        if (asset_root.empty()) {
            log_error("OpenXR scene", "asset_root is empty");
            tc_log_error("[OpenXR scene] asset_root is empty");
            return false;
        }

        register_openxr_scene_runtime();

        const char* required_components[] = {
            "MeshComponent",
            "MeshRenderer",
            "XrOriginComponent",
            "XrThumbstickLocomotionComponent",
            "LightComponent",
            "UnknownComponent",
        };
        for (const char* name : required_components) {
            if (!tc_component_registry_has(name)) {
                log_error("OpenXR scene", (std::string("required component is not registered: ") + name).c_str());
                tc_log_error("[OpenXR scene] required component is not registered: %s", name);
                return false;
            }
        }

        const std::filesystem::path manifest_path =
            std::filesystem::path(asset_root) / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            log_error("OpenXR scene", (std::string("runtime manifest not found at ") + manifest_path.string()).c_str());
            tc_log_error("[OpenXR scene] runtime manifest not found at '%s'", manifest_path.c_str());
            return false;
        }

        engine = std::make_unique<termin::EngineCore>();
        termin::runtime::RuntimePackageLoader loader;
        package = loader.load(asset_root);
        if (!package.ok || !package.scene.valid()) {
            log_error("OpenXR scene", (std::string("runtime package load failed: ") + package.message).c_str());
            tc_log_error("[OpenXR scene] runtime package load failed: %s", package.message.c_str());
            package = termin::runtime::RuntimePackageLoadResult();
            engine.reset();
            return false;
        }

        const tc_render_target_config* xr_config = find_xr_render_target_config(package.scene);
        install_runtime_pipeline_factory(asset_root);
        xr_origin = resolve_runtime_xr_origin(package.scene, xr_config);
        if (!xr_origin) {
            log_error("OpenXR scene", "runtime package loaded but has no XR camera origin");
            tc_log_error("[OpenXR scene] runtime package loaded but has no XR camera origin");
            package.scene.destroy();
            package = termin::runtime::RuntimePackageLoadResult();
            engine.reset();
            return false;
        }
        reset_reference_alignment();

        pipeline = make_pipeline_for_xr_render_target(*engine, xr_config);
        if (!pipeline.is_valid() || pipeline.pass_count() == 0) {
            log_error("OpenXR scene", "failed to create render pipeline");
            tc_log_error("[OpenXR scene] failed to create render pipeline");
            package.scene.destroy();
            package = termin::runtime::RuntimePackageLoadResult();
            engine.reset();
            return false;
        }

        scene = package.scene;
        create_xr_render_target();
        register_context_provider();
        ready = true;
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR runtime scene loaded root='%s' entities=%zu passes=%zu",
            asset_root.c_str(),
            scene.entity_count(),
            pipeline.pass_count()
        );
        return true;
    }

    std::string choose_xr_render_target_name(const tc_render_target_config* config) const {
        if (config && config->name && config->name[0] != '\0') {
            return config->name;
        }
        return "XRStereoTarget";
    }

    void create_xr_render_target() {
        const tc_render_target_config* config = find_xr_render_target_config(scene);
        const std::string name = choose_xr_render_target_name(config);
        xr_render_target = tc_render_target_new(name.c_str());
        tc_render_target_set_kind(xr_render_target, TC_RENDER_TARGET_XR_STEREO);
        tc_render_target_set_scene(xr_render_target, scene.handle());
        tc_render_target_set_xr_origin(xr_render_target, xr_origin ? xr_origin->c_component() : nullptr);
        tc_render_target_set_pipeline(xr_render_target, pipeline.handle());
        tc_render_target_set_enabled(xr_render_target, true);
        if (config) {
            tc_render_target_set_layer_mask(xr_render_target, config->layer_mask);
            tc_render_target_set_clear_color_enabled(xr_render_target, config->clear_color);
            tc_render_target_set_clear_color_value(
                xr_render_target,
                config->clear_color_value[0],
                config->clear_color_value[1],
                config->clear_color_value[2],
                config->clear_color_value[3]
            );
            tc_render_target_set_clear_depth_enabled(xr_render_target, config->clear_depth);
            tc_render_target_set_clear_depth_value(xr_render_target, config->clear_depth_value);
        } else {
            tc_render_target_set_clear_color_enabled(xr_render_target, true);
            tc_render_target_set_clear_color_value(xr_render_target, 0.015f, 0.018f, 0.024f, 1.0f);
            tc_render_target_set_clear_depth_enabled(xr_render_target, true);
            tc_render_target_set_clear_depth_value(xr_render_target, 1.0f);
        }
        engine->rendering_manager.register_managed_render_target(xr_render_target);
    }

    void register_context_provider() {
        engine->rendering_manager.set_render_target_context_provider(
            TC_RENDER_TARGET_XR_STEREO,
            [this](
                termin::RenderingManager&,
                tc_render_target_handle render_target,
                const std::string& base_context_name,
                tc_entity_handle internal_entities,
                std::unordered_map<std::string, termin::RenderTargetContext>& contexts,
                std::string& default_context_name
            ) {
                return build_active_eye_context(
                    render_target,
                    base_context_name,
                    internal_entities,
                    contexts,
                    default_context_name
                );
            }
        );
    }

    bool build_active_eye_context(
        tc_render_target_handle render_target,
        const std::string& base_context_name,
        tc_entity_handle internal_entities,
        std::unordered_map<std::string, termin::RenderTargetContext>& contexts,
        std::string& default_context_name
    ) {
        if (!tc_render_target_handle_eq(render_target, xr_render_target)) {
            return false;
        }
        if (!active_eye_frame.valid || !xr_origin) {
            return false;
        }

        const EyeFrame& eye = active_eye_frame;
        const std::string name =
            (base_context_name.empty() ? "XRStereoTarget" : base_context_name) +
            (eye.eye_index == 0 ? ".left" : ".right");

        termin::RenderTargetContext target;
        target.name = name;
        target.render_rect = termin::Rect2i{
            0,
            0,
            static_cast<int>(eye.width),
            static_cast<int>(eye.height)
        };
        target.internal_entities = internal_entities;
        target.output_color_tex = eye.color_texture;
        target.output_depth_tex = eye.depth_texture;
        target.output_color_format = eye.color_format;
        target.output_depth_format = tgfx::PixelFormat::D32F;
        target.clear_color_enabled = tc_render_target_get_clear_color_enabled(render_target);
        tc_render_target_get_clear_color_value(render_target, target.clear_color);
        target.clear_depth_enabled = tc_render_target_get_clear_depth_enabled(render_target);
        target.clear_depth = tc_render_target_get_clear_depth_value(render_target);
        termin::GeneralPose3 origin_pose = xr_origin->entity().transform().global_pose();
        termin::Pose3 origin_pose3(origin_pose.ang, origin_pose.lin);
        // XrOriginComponent uses engine authoring axes: +X right, +Y forward,
        // +Z up. OpenXR reference poses are first converted from +X right, +Y
        // up, -Z forward into that engine basis, then optionally yaw-aligned
        // under the origin by XrOriginComponent::reference_alignment.
        termin::Mat44 scene_to_origin = origin_pose3.inverse().as_mat44();
        termin::Mat44 scene_from_origin = scene_to_origin.inverse();
        termin::Mat44 reference_to_origin = origin_from_xr_reference.inverse();
        termin::Vec3 eye_position_in_reference = xr_position_to_scene_position(eye.view.pose.position);
        termin::Vec3 eye_position_in_origin =
            origin_from_xr_reference.transform_point(eye_position_in_reference);

        target.camera.view =
            make_xr_to_scene_matrix() *
            mat44_from_float_array(make_view_matrix_from_xr_pose(eye.view.pose)) *
            make_scene_to_xr_matrix() *
            reference_to_origin *
            scene_to_origin;
        target.camera.projection = make_engine_projection_from_xr_fov(
            eye.view.fov,
            static_cast<float>(xr_origin->near_clip),
            static_cast<float>(xr_origin->far_clip)
        );
        target.camera.position = scene_from_origin.transform_point(eye_position_in_origin);
        target.camera.near_clip = xr_origin->near_clip;
        target.camera.far_clip = xr_origin->far_clip;
        target.layer_mask = xr_origin->layer_mask & tc_render_target_get_layer_mask(render_target);

        contexts.emplace(name, std::move(target));
        default_context_name = name;
        return true;
    }

    void render_eye(
        tgfx::TextureHandle color_texture,
        tgfx::TextureHandle depth_texture,
        uint32_t width,
        uint32_t height,
        tgfx::PixelFormat color_format,
        const XrView& view,
        uint32_t eye_index
    ) {
        if (!ready || !engine || !xr_origin) {
            return;
        }
        if (!tc_render_target_handle_valid(xr_render_target)) {
            tc_log_error("[OpenXR scene] XR render target is unavailable");
            return;
        }

        active_eye_frame.color_texture = color_texture;
        active_eye_frame.depth_texture = depth_texture;
        active_eye_frame.width = width;
        active_eye_frame.height = height;
        active_eye_frame.color_format = color_format;
        active_eye_frame.view = view;
        active_eye_frame.eye_index = eye_index;
        active_eye_frame.valid = true;
        engine->rendering_manager.render_render_target_offscreen(xr_render_target);
        active_eye_frame.valid = false;
    }

    void update(double dt) {
        if (!ready || !scene.valid()) {
            return;
        }
        scene.update(dt);
    }

    bool begin_render_frame() {
        if (!ready || !engine) {
            return false;
        }
        termin::RenderEngine* render_engine = engine->rendering_manager.render_engine();
        if (!render_engine) {
            tc_log_error("[OpenXR scene] render engine is unavailable");
            return false;
        }
        render_engine->ensure_tgfx2();
        tgfx::RenderContext2* ctx = render_engine->tgfx2_ctx();
        if (!ctx) {
            tc_log_error("[OpenXR scene] tgfx2 render context is unavailable");
            return false;
        }
        if (ctx->in_frame()) {
            return false;
        }
        ctx->begin_frame();
        return true;
    }

    void end_render_frame() {
        if (!ready || !engine) {
            return;
        }
        termin::RenderEngine* render_engine = engine->rendering_manager.render_engine();
        if (!render_engine) {
            tc_log_error("[OpenXR scene] render engine is unavailable while ending frame");
            return;
        }
        tgfx::RenderContext2* ctx = render_engine->tgfx2_ctx();
        if (!ctx) {
            tc_log_error("[OpenXR scene] tgfx2 render context is unavailable while ending frame");
            return;
        }
        if (!ctx->in_frame()) {
            tc_log_error("[OpenXR scene] tgfx2 render frame was not open while ending frame");
            return;
        }
        ctx->end_frame();
    }

    void destroy() {
        active_eye_frame = {};
        if (engine) {
            engine->rendering_manager.clear_render_target_context_provider(TC_RENDER_TARGET_XR_STEREO);
            if (tc_render_target_handle_valid(xr_render_target)) {
                engine->rendering_manager.unregister_managed_render_target(xr_render_target);
                tc_render_target_free(xr_render_target);
            }
        }
        xr_render_target = TC_RENDER_TARGET_HANDLE_INVALID;
        pipeline = {};
        xr_origin = nullptr;
        if (scene.valid()) {
            scene.destroy();
        }
        scene = {};
        package = termin::runtime::RuntimePackageLoadResult();
        engine.reset();
        ready = false;
    }
};
