// scene_manager_bindings.cpp - Python bindings for SceneManager
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/trampoline.h>
#include <memory>

#include "scene_manager.hpp"

extern "C" {
#include "../../../core_c/include/tc_scene.h"
#include "../../../core_c/include/tc_scene_pool.h"
}

namespace nb = nanobind;

namespace termin {

// Trampoline class for Python inheritance
class PySceneManager : public SceneManager {
public:
    NB_TRAMPOLINE(SceneManager, 1);

    bool tick(double dt) override {
        NB_OVERRIDE(tick, dt);
    }
};

void bind_scene_manager(nb::module_& m) {
    // Bind SceneMode enum
    nb::enum_<tc_scene_mode>(m, "SceneMode")
        .value("INACTIVE", TC_SCENE_MODE_INACTIVE, "Loaded but not updated")
        .value("STOP", TC_SCENE_MODE_STOP, "Editor update (gizmos, selection)")
        .value("PLAY", TC_SCENE_MODE_PLAY, "Full simulation")
        .export_values();

    // Bind SceneManager class
    nb::class_<SceneManager, PySceneManager>(m, "SceneManager")
        .def(nb::init<>())

        // --- Scene lifecycle ---

        .def("create_scene", [](SceneManager& self, const std::string& name) -> nb::object {
            tc_scene_handle h = self.create_scene(name);
            if (!tc_scene_handle_valid(h)) {
                return nb::none();
            }
            // Import TcScene from _entity_native and create via from_handle
            nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
            nb::object tc_scene_class = entity_module.attr("TcScene");
            return tc_scene_class.attr("from_handle")(h.index, h.generation);
        }, nb::arg("name"),
           "Create a new scene and register it. Returns TcScene.")

        .def("close_scene", &SceneManager::close_scene, nb::arg("name"),
             "Close and destroy a scene.")

        .def("close_all_scenes", &SceneManager::close_all_scenes,
             "Close all scenes.")

        .def("copy_scene", [](SceneManager& self, const std::string& src_name,
                              const std::string& dst_name) -> nb::object {
            tc_scene_handle src_h = self.get_scene(src_name);
            if (!tc_scene_handle_valid(src_h)) {
                return nb::none();
            }

            // Get source scene as TcScene
            nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
            nb::object tc_scene_class = entity_module.attr("TcScene");
            nb::object src_scene = tc_scene_class.attr("from_handle")(src_h.index, src_h.generation);

            // Serialize source
            nb::object data = src_scene.attr("serialize")();

            // Create destination scene
            nb::object dst_scene = tc_scene_class.attr("create")(dst_name);
            dst_scene.attr("load_from_data")(data, nb::none(), true);

            // Register in SceneManager
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(dst_scene.attr("scene_handle")());
            tc_scene_handle dst_h;
            dst_h.index = std::get<0>(h);
            dst_h.generation = std::get<1>(h);
            self.register_scene(dst_name, dst_h);

            return dst_scene;
        }, nb::arg("source_name"), nb::arg("dest_name"),
           "Copy scene. Returns new TcScene.")

        .def("load_scene", [](SceneManager& self, const std::string& name,
                              const std::string& path) -> nb::object {
            // Check if scene already exists
            if (self.has_scene(name)) {
                return nb::none();
            }

            // Read file
            std::string json_str = SceneManager::read_json_file(path);
            if (json_str.empty()) {
                return nb::none();
            }

            // Parse JSON
            nb::module_ json_module = nb::module_::import_("json");
            nb::object data = json_module.attr("loads")(json_str);

            // Extract scene data (support both formats)
            nb::object scene_data = data.attr("get")("scene");
            if (scene_data.is_none()) {
                nb::object scenes = data.attr("get")("scenes");
                if (!scenes.is_none() && nb::len(scenes) > 0) {
                    scene_data = scenes[nb::int_(0)];
                }
            }

            // Create scene
            nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
            nb::object tc_scene_class = entity_module.attr("TcScene");
            nb::object scene = tc_scene_class.attr("create")(name);

            // Load data if present
            if (!scene_data.is_none()) {
                scene.attr("load_from_data")(scene_data, nb::none(), true);
            }

            // Register in SceneManager
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene.attr("scene_handle")());
            tc_scene_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            self.register_scene(name, handle);
            self.set_scene_path(name, path);

            // Notify editor start
            scene.attr("notify_editor_start")();

            return scene;
        }, nb::arg("name"), nb::arg("path"),
           "Load scene from file. Returns TcScene or None.")

        .def("save_scene", [](SceneManager& self, const std::string& name,
                              const std::string& path,
                              nb::object editor_data) -> bool {
            tc_scene_handle h = self.get_scene(name);
            if (!tc_scene_handle_valid(h)) {
                return false;
            }

            // Get scene as TcScene
            nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
            nb::object tc_scene_class = entity_module.attr("TcScene");
            nb::object scene = tc_scene_class.attr("from_handle")(h.index, h.generation);

            // Serialize scene
            nb::object scene_data = scene.attr("serialize")();

            // Build full data dict
            nb::dict data;
            data["version"] = "1.0";
            data["scene"] = scene_data;
            if (!editor_data.is_none()) {
                data["editor"] = editor_data;
            }

            // Convert to JSON
            nb::module_ json_module = nb::module_::import_("json");
            nb::object json_str = json_module.attr("dumps")(data,
                nb::arg("indent") = 2,
                nb::arg("ensure_ascii") = false);

            // Write file
            SceneManager::write_json_file(path, nb::cast<std::string>(json_str));
            self.set_scene_path(name, path);

            return true;
        }, nb::arg("name"), nb::arg("path"),
           nb::arg("editor_data") = nb::none(),
           "Save scene to file. Returns true on success.")

        // --- Scene registration (for external scenes) ---

        .def("register_scene", [](SceneManager& self, const std::string& name, std::tuple<uint32_t, uint32_t> handle_tuple) {
            tc_scene_handle h;
            h.index = std::get<0>(handle_tuple);
            h.generation = std::get<1>(handle_tuple);
            self.register_scene(name, h);
        }, nb::arg("name"), nb::arg("handle"),
           "Register an external scene by name. handle is (index, generation) tuple.")

        .def("unregister_scene", &SceneManager::unregister_scene, nb::arg("name"),
             "Unregister a scene by name (does not destroy it).")

        // --- Scene access ---

        .def("get_scene", [](const SceneManager& self, const std::string& name) -> nb::object {
            tc_scene_handle h = self.get_scene(name);
            if (!tc_scene_handle_valid(h)) {
                return nb::none();
            }
            nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
            nb::object tc_scene_class = entity_module.attr("TcScene");
            return tc_scene_class.attr("from_handle")(h.index, h.generation);
        }, nb::arg("name"),
           "Get scene by name. Returns TcScene or None.")

        .def("has_scene", &SceneManager::has_scene, nb::arg("name"),
             "Check if scene exists.")

        .def("scene_names", &SceneManager::scene_names,
             "Get list of all scene names.")

        // --- Path management ---

        .def("get_scene_path", &SceneManager::get_scene_path, nb::arg("name"),
             "Get file path for scene (empty if not set).")

        .def("set_scene_path", &SceneManager::set_scene_path,
             nb::arg("name"), nb::arg("path"),
             "Set file path for scene.")

        // --- Mode management ---

        .def("get_mode", [](const SceneManager& self, const std::string& name) {
            return self.get_mode(name);
        }, nb::arg("name"), "Get scene mode.")

        .def("set_mode", [](SceneManager& self, const std::string& name, tc_scene_mode mode) {
            self.set_mode(name, mode);
        }, nb::arg("name"), nb::arg("mode"), "Set scene mode.")

        .def("has_play_scenes", &SceneManager::has_play_scenes,
             "Check if any scene is in PLAY mode.")

        // --- Update cycle ---

        .def("tick", &SceneManager::tick, nb::arg("dt"),
             "Update all scenes based on their mode. Returns true if render needed.")

        .def("tick_and_render", &SceneManager::tick_and_render, nb::arg("dt"),
             "Full update cycle: tick, before_render, render_all, after_render callback.")

        .def("before_render", &SceneManager::before_render,
             "Call before_render on all active scenes.")

        // --- Render request ---

        .def("request_render", &SceneManager::request_render,
             "Request render on next tick.")

        .def("consume_render_request", &SceneManager::consume_render_request,
             "Consume and return render request flag.")

        // --- File I/O ---

        .def_static("read_json_file", &SceneManager::read_json_file, nb::arg("path"),
             "Read JSON file and return as string. Returns empty string on error.")

        .def_static("write_json_file", &SceneManager::write_json_file,
             nb::arg("path"), nb::arg("json"),
             "Write JSON string to file (atomic write).")

        // --- Callbacks ---

        .def("set_on_after_render", [](SceneManager& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_on_after_render(nullptr);
            } else {
                // Store callback as shared_ptr to prevent preventing Python shutdown
                auto cb = std::make_shared<nb::object>(callback);
                self.set_on_after_render([cb]() {
                    nb::gil_scoped_acquire guard;
                    (*cb)();
                });
            }
        }, nb::arg("callback"),
             "Set callback to run after render. Pass None to clear.")

        .def("set_on_before_scene_close", [](SceneManager& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_on_before_scene_close(nullptr);
            } else {
                auto cb = std::make_shared<nb::object>(callback);
                self.set_on_before_scene_close([cb](const std::string& name) {
                    nb::gil_scoped_acquire guard;
                    (*cb)(name);
                });
            }
        }, nb::arg("callback"),
             "Set callback to run before scene close. Pass None to clear.")

        .def("invoke_after_render", &SceneManager::invoke_after_render,
             "Invoke after_render callback (if set).")

        .def("invoke_before_scene_close", &SceneManager::invoke_before_scene_close, nb::arg("name"),
             "Invoke before_scene_close callback (if set).")
        ;
}

} // namespace termin
