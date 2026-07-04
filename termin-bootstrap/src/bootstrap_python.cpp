#include <termin/bootstrap/bootstrap.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <unordered_map>

#include <inspect/tc_inspect_python.hpp>
#include <inspect/tc_kind_python.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component.hpp>
#include <termin/input/input_events.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_context.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>
#include <termin/voxels/tc_voxel_grid_handle.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/resources/tc_material.h>

#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
#include <termin/animation/tc_animation_handle.hpp>
#endif

extern "C" {
#include <core/tc_scene.h>
#include <tc_component_python_drawable.h>
#include <tc_component_python_input.h>
}

namespace nb = nanobind;

namespace termin::bootstrap {
namespace {

template<typename H>
nb::object serialize_uuid_handle(nb::object obj) {
    H handle = nb::cast<H>(obj);
    nb::dict result;
    if (handle.is_valid()) {
        result["uuid"] = nb::str(handle.uuid());
        result["name"] = nb::str(handle.name());
        result["type"] = "uuid";
    } else {
        result["type"] = "none";
    }
    return result;
}

template<typename H>
nb::object deserialize_uuid_handle(nb::object data) {
    if (nb::isinstance<nb::str>(data)) {
        return nb::cast(H::from_uuid(nb::cast<std::string>(data)));
    }
    if (nb::isinstance<nb::dict>(data)) {
        nb::dict dict = nb::cast<nb::dict>(data);
        if (dict.contains("uuid")) {
            return nb::cast(H::from_uuid(nb::cast<std::string>(dict["uuid"])));
        }
    }
    return nb::cast(H());
}

template<typename H>
void register_python_uuid_handle_kind(const char* kind_name, nb::handle type_obj) {
    tc::KindRegistry::instance().register_type(type_obj, kind_name);
    tc::KindRegistry::instance().register_python(
        kind_name,
        nb::cpp_function([](nb::object obj) -> nb::object {
            return serialize_uuid_handle<H>(obj);
        }),
        nb::cpp_function([](nb::object data) -> nb::object {
            return deserialize_uuid_handle<H>(data);
        })
    );
}

void register_python_entity_kind() {
    nb::module_ scene_module = nb::module_::import_("termin.scene");
    nb::handle entity_type = scene_module.attr("Entity");

    tc::KindRegistry::instance().register_type(entity_type, "entity");
    tc::KindRegistry::instance().register_python(
        "entity",
        nb::cpp_function([](nb::object obj) -> nb::object {
            Entity entity = nb::cast<Entity>(obj);
            nb::dict result;
            if (entity.valid()) {
                result["uuid"] = nb::str(entity.uuid());
                if (entity.name() != nullptr) {
                    result["name"] = nb::str(entity.name());
                }
            }
            return result;
        }),
        nb::cpp_function([](nb::object data, uintptr_t context_ptr) -> nb::object {
            tc_value value = tc::nb_to_tc_value(data);
            Entity entity;
            entity.deserialize_from(&value, reinterpret_cast<void*>(context_ptr));
            tc_value_free(&value);
            if (!entity.valid()) {
                return nb::none();
            }
            return nb::cast(entity);
        })
    );
}

static bool g_pointer_extractors_initialized = false;
static bool g_callbacks_initialized = false;
static bool g_python_inspect_adapters_initialized = false;
static bool g_python_render_passes_initialized = false;

static bool g_mesh_python_kind_initialized = false;
static bool g_material_python_kind_initialized = false;
static bool g_skeleton_python_kind_initialized = false;
static bool g_animation_python_kind_initialized = false;
static bool g_voxel_grid_python_kind_initialized = false;
static bool g_navmesh_python_kind_initialized = false;
static bool g_entity_python_kind_initialized = false;

bool py_drawable_cb_has_phase(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    bool result = false;
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "phase_marks")) {
            nb::object marks = self.attr("phase_marks");
            if (!marks.is_none()) {
                std::string pm = phase_mark ? phase_mark : "";
                result = nb::cast<bool>(marks.attr("__contains__")(pm));
            }
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "Drawable::has_phase");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
}

void py_drawable_cb_draw_geometry(void* py_self, void* render_context, int geometry_id) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "draw_geometry")) {
            RenderContext* ctx = static_cast<RenderContext*>(render_context);
            nb::object py_ctx = nb::cast(ctx, nb::rv_policy::reference);
            self.attr("draw_geometry")(py_ctx, geometry_id);
        }
    } catch (const std::exception& e) {
        tc::Log::warn(e, "Drawable::draw_geometry");
    }
    PyGILState_Release(gstate);
}

std::unordered_map<void*, std::vector<GeometryDrawCall>> g_py_geometry_draw_cache;

void* py_drawable_cb_get_geometry_draws(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    void* result = nullptr;
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "get_geometry_draws")) {
            std::string pm = phase_mark ? phase_mark : "";
            nb::object py_draws = self.attr("get_geometry_draws")(pm.empty() ? nb::none() : nb::cast(pm));

            auto& cached = g_py_geometry_draw_cache[py_self];
            cached.clear();

            if (!py_draws.is_none()) {
                for (auto item : py_draws) {
                    GeometryDrawCall dc;
                    nb::object phase_obj = item.attr("phase");
                    if (!phase_obj.is_none()) {
                        try {
                            dc.bind_phase_ref(nb::cast<tc_material_phase*>(phase_obj));
                        } catch (const nb::cast_error&) {
                            continue;
                        }
                    }
                    nb::object gid_obj = item.attr("geometry_id");
                    if (!gid_obj.is_none()) {
                        dc.geometry_id = nb::cast<int>(gid_obj);
                    }
                    cached.push_back(dc);
                }
            }
            result = &cached;
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "Drawable::get_geometry_draws");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
}

void py_input_cb_on_mouse_button(void* py_self, tc_mouse_button_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        MouseButtonEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_mouse_button")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_button");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

void py_input_cb_on_mouse_move(void* py_self, tc_mouse_move_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        MouseMoveEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_mouse_move")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_move");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

void py_input_cb_on_scroll(void* py_self, tc_scroll_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        ScrollEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_scroll")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_scroll");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

void py_input_cb_on_key(void* py_self, tc_key_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        KeyEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_key")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_key");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

} // namespace

void init_python_inspect_adapters() {
    if (g_python_inspect_adapters_initialized) {
        return;
    }
    tc::init_python_lang_vtable();
    tc::init_python_inspect_vtable();
    g_python_inspect_adapters_initialized = true;
}

void init_python_render_passes() {
    if (g_python_render_passes_initialized) {
        return;
    }

    try {
        nb::module_::import_("termin.render_passes");
        g_python_render_passes_initialized = true;
    } catch (const std::exception& e) {
        tc::Log::error(e, "[termin-bootstrap] Failed to import Python render passes");
        PyErr_Print();
        throw;
    }
}

void init_python_kind_handlers(const RuntimeKindOptions& options) {
    if (options.mesh && !g_mesh_python_kind_initialized) {
        nb::module_ mesh_module = nb::module_::import_("tmesh");
        register_python_uuid_handle_kind<TcMesh>("tc_mesh", mesh_module.attr("TcMesh"));
        g_mesh_python_kind_initialized = true;
    }
    if (options.material && !g_material_python_kind_initialized) {
        nb::module_ materials_module = nb::module_::import_("termin.materials");
        register_python_uuid_handle_kind<TcMaterial>("tc_material", materials_module.attr("TcMaterial"));
        g_material_python_kind_initialized = true;
    }
    if (options.skeleton && !g_skeleton_python_kind_initialized) {
        nb::module_ skeleton_module = nb::module_::import_("termin.skeleton");
        register_python_uuid_handle_kind<TcSkeleton>("tc_skeleton", skeleton_module.attr("TcSkeleton"));
        g_skeleton_python_kind_initialized = true;
    }
    if (options.animation && !g_animation_python_kind_initialized) {
#ifdef TERMIN_BOOTSTRAP_HAS_ANIMATION
        nb::module_ animation_module = nb::module_::import_("termin.animation");
        register_python_uuid_handle_kind<animation::TcAnimationClip>(
            "tc_animation_clip",
            animation_module.attr("TcAnimationClip")
        );
        g_animation_python_kind_initialized = true;
#endif
    }
    if (options.voxel_grid && !g_voxel_grid_python_kind_initialized) {
        nb::module_ voxels_module = nb::module_::import_("termin.voxels._voxels_native");
        register_python_uuid_handle_kind<voxels::TcVoxelGrid>("voxel_grid_handle", voxels_module.attr("TcVoxelGrid"));
        g_voxel_grid_python_kind_initialized = true;
    }
    if (options.navmesh && !g_navmesh_python_kind_initialized) {
        nb::module_ navmesh_module = nb::module_::import_("termin.navmesh");
        register_python_uuid_handle_kind<TcNavMesh>("navmesh_handle", navmesh_module.attr("TcNavMesh"));
        g_navmesh_python_kind_initialized = true;
    }
    if (options.entity && !g_entity_python_kind_initialized) {
        register_python_entity_kind();
        g_entity_python_kind_initialized = true;
    }
}

void init_pointer_extractors() {
    if (g_pointer_extractors_initialized) {
        return;
    }

    nb::module_ inspect_native = nb::module_::import_("termin.inspect._inspect_native");
    nb::object register_fn = inspect_native.attr("register_ptr_extractor");

    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            void* ptr = static_cast<void*>(nb::cast<Component*>(obj));
            return nb::int_(reinterpret_cast<uintptr_t>(ptr));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));

    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            TcMaterial mat = nb::cast<TcMaterial>(obj);
            return nb::int_(reinterpret_cast<uintptr_t>(mat.get()));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));

    register_fn(nb::cpp_function([](nb::object obj) -> nb::object {
        try {
            void* ptr = static_cast<void*>(nb::cast<CxxFramePass*>(obj));
            return nb::int_(reinterpret_cast<uintptr_t>(ptr));
        } catch (const nb::cast_error&) {
            return nb::none();
        }
    }));

    g_pointer_extractors_initialized = true;
}

void init_python_component_callbacks() {
    if (g_callbacks_initialized) {
        return;
    }

    tc_python_drawable_callbacks drawable_callbacks = {
        .has_phase = py_drawable_cb_has_phase,
        .draw_geometry = py_drawable_cb_draw_geometry,
        .get_geometry_draws = py_drawable_cb_get_geometry_draws,
    };
    tc_component_set_python_drawable_callbacks(&drawable_callbacks);

    tc_python_input_callbacks input_callbacks = {
        .on_mouse_button = py_input_cb_on_mouse_button,
        .on_mouse_move = py_input_cb_on_mouse_move,
        .on_scroll = py_input_cb_on_scroll,
        .on_key = py_input_cb_on_key,
    };
    tc_component_set_python_input_callbacks(&input_callbacks);

    g_callbacks_initialized = true;
}

void reset_python_bootstrap_state() {
    if (Py_IsInitialized()) {
        PyGILState_STATE gil = PyGILState_Ensure();
        tc::reset_kind_registry_python();
        PyGILState_Release(gil);
    }

    g_pointer_extractors_initialized = false;
    g_callbacks_initialized = false;
    g_python_inspect_adapters_initialized = false;
    g_python_render_passes_initialized = false;

    g_mesh_python_kind_initialized = false;
    g_material_python_kind_initialized = false;
    g_skeleton_python_kind_initialized = false;
    g_animation_python_kind_initialized = false;
    g_voxel_grid_python_kind_initialized = false;
    g_navmesh_python_kind_initialized = false;
    g_entity_python_kind_initialized = false;

    g_py_geometry_draw_cache.clear();

    tc_python_drawable_callbacks drawable_callbacks = {};
    tc_component_set_python_drawable_callbacks(&drawable_callbacks);

    tc_python_input_callbacks input_callbacks = {};
    tc_component_set_python_input_callbacks(&input_callbacks);
}

} // namespace termin::bootstrap
