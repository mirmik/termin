// scene_manager_bindings.cpp - Python bindings for SceneManager
#include <memory>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>
#include <nanobind/trampoline.h>

#include "termin/scene/scene_manager.hpp"
#include <termin/tc_scene.hpp>

extern "C" {
#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
}

namespace nb = nanobind;

namespace termin {

    static nb::object scene_from_handle(tc_scene_handle h) {
        nb::module_ scene_module = nb::module_::import_("termin.scene._scene_native");
        nb::object tc_scene_class = scene_module.attr("TcScene");
        return tc_scene_class.attr("from_handle")(h.index, h.generation);
    }

    // Trampoline class for Python inheritance
    class PySceneManager : public SceneManager {
    public:
        NB_TRAMPOLINE(SceneManager, 1);

        bool tick(double dt) override {
            NB_OVERRIDE(tick, dt);
        }
    };

    void bind_scene_manager(nb::module_& m) {
        nb::enum_<tc_scene_mode>(m, "SceneMode")
            .value("INACTIVE", TC_SCENE_MODE_INACTIVE, "Loaded but not updated")
            .value("STOP", TC_SCENE_MODE_STOP, "Editor update (gizmos, selection)")
            .value("PLAY", TC_SCENE_MODE_PLAY, "Full simulation")
            .export_values();

        nb::enum_<SceneRole>(m, "SceneRole")
            .value("AUTHORING", SceneRole::Authoring)
            .value("RUNTIME", SceneRole::Runtime);

        nb::class_<SceneKey>(m, "SceneKey")
            .def(nb::init<std::string, SceneRole>(), nb::arg("identity"), nb::arg("role"))
            .def_ro("identity", &SceneKey::identity)
            .def_ro("role", &SceneKey::role)
            .def("__eq__", [](const SceneKey& self, const SceneKey& other) { return self == other; })
            .def("__hash__", [](const SceneKey& self) { return SceneKeyHash{}(self); })
            .def("__repr__", [](const SceneKey& self) {
                return "SceneKey(identity='" + self.identity + "', role=SceneRole." +
                       (self.role == SceneRole::Authoring ? "AUTHORING" : "RUNTIME") + ")";
            });

        nb::class_<ManagedSceneInfo>(m, "ManagedSceneInfo")
            .def_ro("key", &ManagedSceneInfo::key)
            .def_ro("path", &ManagedSceneInfo::path)
            .def_prop_ro("scene", [](const ManagedSceneInfo& self) { return scene_from_handle(self.handle); });

        nb::class_<SceneManager, PySceneManager>(m, "SceneManager")
            .def(nb::init<>())
            .def(
                "create_scene",
                [](SceneManager& self, const SceneKey& key, nb::object extensions_obj) -> nb::object {
                    std::vector<tc_scene_ext_type_id> extensions;
                    if (!extensions_obj.is_none()) {
                        extensions = nb::cast<std::vector<tc_scene_ext_type_id>>(extensions_obj);
                    }
                    tc_scene_handle h = self.create_scene(key, extensions);
                    if (!tc_scene_handle_valid(h)) {
                        return nb::none();
                    }
                    return scene_from_handle(h);
                },
                nb::arg("key"),
                nb::arg("extensions") = nb::none(),
                "Create a new scene and register it. Returns TcScene.")
            .def("close_scene", [](SceneManager& self, const SceneKey& key) { return self.close_scene(key); },
                 nb::arg("key"), "Close and destroy a scene by key.")
            .def("close_scene", [](SceneManager& self, const TcSceneRef& scene) {
                    return self.close_scene(scene.handle());
                 }, nb::arg("scene"), "Close and destroy an exact scene instance.")
            .def("close_all_scenes", &SceneManager::close_all_scenes, "Close all scenes.")
            .def("close_scenes", &SceneManager::close_scenes, nb::arg("role"), "Close all scenes with a role.")
            .def(
                "copy_scene",
                [](SceneManager& self, const SceneKey& source, const SceneKey& destination) -> nb::object {
                    tc_scene_handle src_h = self.get_scene(source);
                    if (!tc_scene_handle_valid(src_h)) {
                        return nb::none();
                    }
                    nb::object src_scene = scene_from_handle(src_h);
                    nb::object data = src_scene.attr("serialize")();
                    tc_scene_handle dst_h = self.create_scene(destination, {});
                    if (!tc_scene_handle_valid(dst_h)) {
                        return nb::none();
                    }
                    nb::object dst_scene = scene_from_handle(dst_h);
                    dst_scene.attr("load_from_data")(data, nb::none(), true);

                    return dst_scene;
                },
                nb::arg("source_key"),
                nb::arg("destination_key"),
                "Copy scene. Returns new TcScene.")
            .def(
                "load_scene",
                [](SceneManager& self, const SceneKey& key, const std::string& path) -> nb::object {
                    if (self.has_scene(key)) {
                        return nb::none();
                    }
                    std::string json_str = SceneManager::read_json_file(path);
                    if (json_str.empty()) {
                        return nb::none();
                    }
                    nb::module_ json_module = nb::module_::import_("json");
                    nb::object data = json_module.attr("loads")(json_str);
                    nb::object scene_data = data.attr("get")("scene");
                    if (scene_data.is_none()) {
                        nb::object scenes = data.attr("get")("scenes");
                        if (!scenes.is_none() && nb::len(scenes) > 0) {
                            scene_data = scenes[nb::int_(0)];
                        }
                    }
                    tc_scene_handle handle = self.create_scene(key, {});
                    if (!tc_scene_handle_valid(handle)) {
                        return nb::none();
                    }
                    nb::object scene = scene_from_handle(handle);
                    if (!scene_data.is_none()) {
                        scene.attr("load_from_data")(scene_data, nb::none(), true);
                    }
                    self.set_scene_path(key, path);
                    scene.attr("notify_editor_start")();
                    return scene;
                },
                nb::arg("key"),
                nb::arg("path"),
                "Load scene from file. Returns TcScene or None.")
            .def(
                "save_scene",
                [](SceneManager& self, const SceneKey& key, const std::string& path, nb::object editor_data)
                    -> bool {
                    tc_scene_handle h = self.get_scene(key);
                    if (!tc_scene_handle_valid(h)) {
                        return false;
                    }
                    nb::object scene = scene_from_handle(h);
                    nb::object scene_data = scene.attr("serialize")();
                    nb::dict data;
                    data["version"] = "1.0";
                    data["scene"] = scene_data;
                    if (!editor_data.is_none()) {
                        data["editor"] = editor_data;
                    }
                    nb::module_ json_module = nb::module_::import_("json");
                    nb::object json_str =
                        json_module.attr("dumps")(data, nb::arg("indent") = 2, nb::arg("ensure_ascii") = false);

                    SceneManager::write_json_file(path, nb::cast<std::string>(json_str));
                    self.set_scene_path(key, path);
                    return true;
                },
                nb::arg("key"),
                nb::arg("path"),
                nb::arg("editor_data") = nb::none(),
                "Save scene to file. Returns true on success.")
            .def(
                "register_scene",
                [](SceneManager& self, const SceneKey& key, tc_scene_handle h) { return self.register_scene(key, h); },
                nb::arg("key"),
                nb::arg("handle"))
            .def("unregister_scene",
                 &SceneManager::unregister_scene,
                 nb::arg("key"),
                 "Unregister a scene by key (does not destroy it).")
            .def("rekey_scene",
                 &SceneManager::rekey_scene,
                 nb::arg("source_key"),
                 nb::arg("destination_key"),
                 "Atomically replace a scene registry key without changing its instance.")
            .def(
                "get_scene",
                [](const SceneManager& self, const SceneKey& key) -> nb::object {
                    tc_scene_handle h = self.get_scene(key);
                    if (!tc_scene_handle_valid(h)) {
                        return nb::none();
                    }
                    return scene_from_handle(h);
                },
                nb::arg("key"),
                "Get scene by key. Returns TcScene or None.")
            .def(
                "elevate_scene",
                [](SceneManager& self, const SceneKey& key) -> nb::object {
                    const tc_scene_handle scene = self.elevate_scene(key);
                    return tc_scene_alive(scene) ? scene_from_handle(scene) : nb::none();
                },
                nb::arg("key"),
                "Return an existing scene or ask the host provider to materialize and register it.")
            .def("has_scene", &SceneManager::has_scene, nb::arg("key"), "Check if scene exists.")
            .def(
                "is_registered",
                [](const SceneManager& self, const TcSceneRef& scene) {
                    return self.is_registered(scene.handle());
                },
                nb::arg("scene"),
                "Check whether this exact live scene instance is registered.")
            .def("key_of", [](const SceneManager& self, const TcSceneRef& scene) -> nb::object {
                    const auto key = self.key_of(scene.handle());
                    return key ? nb::cast(*key) : nb::none();
                 }, nb::arg("scene"), "Return the key of an exact registered scene instance.")
            .def("scene_entries", &SceneManager::scene_entries, "Return registry entry snapshots.")
            .def("get_scene_path", [](const SceneManager& self, const SceneKey& key) {
                    return self.get_scene_path(key);
                 }, nb::arg("key"))
            .def("get_scene_path", [](const SceneManager& self, const TcSceneRef& scene) {
                    return self.get_scene_path(scene.handle());
                 }, nb::arg("scene"))
            .def("set_scene_path", [](SceneManager& self, const SceneKey& key, const std::string& path) {
                    return self.set_scene_path(key, path);
                 }, nb::arg("key"), nb::arg("path"))
            .def("set_scene_path", [](SceneManager& self, const TcSceneRef& scene, const std::string& path) {
                    return self.set_scene_path(scene.handle(), path);
                 }, nb::arg("scene"), nb::arg("path"))
            .def("get_mode", [](const SceneManager& self, const SceneKey& key) { return self.get_mode(key); },
                 nb::arg("key"), "Get scene mode.")
            .def("get_mode", [](const SceneManager& self, const TcSceneRef& scene) {
                    return self.get_mode(scene.handle());
                 }, nb::arg("scene"), "Get exact scene instance mode.")
            .def("set_mode", [](SceneManager& self, const SceneKey& key, tc_scene_mode mode) {
                    return self.set_mode(key, mode);
                 }, nb::arg("key"), nb::arg("mode"), "Set scene mode.")
            .def("set_mode", [](SceneManager& self, const TcSceneRef& scene, tc_scene_mode mode) {
                    return self.set_mode(scene.handle(), mode);
                 }, nb::arg("scene"), nb::arg("mode"), "Set exact scene instance mode.")
            .def("has_play_scenes", &SceneManager::has_play_scenes, "Check if any scene is in PLAY mode.")
            .def("tick",
                 &SceneManager::tick,
                 nb::arg("dt"),
                 "Update all scenes based on their mode. Returns true if render "
                 "needed.")
            .def("request_render", &SceneManager::request_render, "Request render on next tick.")
            .def("consume_render_request",
                 &SceneManager::consume_render_request,
                 "Consume and return render request flag.")
            .def_static("read_json_file",
                        &SceneManager::read_json_file,
                        nb::arg("path"),
                        "Read JSON file and return as string. Returns empty string on error.")

            .def_static("write_json_file",
                        &SceneManager::write_json_file,
                        nb::arg("path"),
                        nb::arg("json"),
                        "Write JSON string to file (atomic write).")
            .def(
                "set_on_after_render",
                [](SceneManager& self, nb::object callback) {
                    if (callback.is_none()) {
                        self.set_on_after_render(nullptr);
                    } else {
                        auto cb = std::make_shared<nb::object>(callback);
                        self.set_on_after_render([cb]() {
                            nb::gil_scoped_acquire guard;
                            (*cb)();
                        });
                    }
                },
                nb::arg("callback").none(),
                "Set callback to run after render. Pass None to clear.")

            .def(
                "set_on_before_scene_close",
                [](SceneManager& self, nb::object callback) {
                    if (callback.is_none()) {
                        self.set_on_before_scene_close(nullptr);
                    } else {
                        auto cb = std::make_shared<nb::object>(callback);
                        self.set_on_before_scene_close([cb](const SceneKey& key) {
                            nb::gil_scoped_acquire guard;
                            (*cb)(key);
                        });
                    }
                },
                nb::arg("callback").none(),
                "Set callback to run before scene close. Pass None to clear.")

            .def(
                "set_scene_elevator",
                [](SceneManager& self, nb::object callback) {
                    if (callback.is_none()) {
                        self.set_scene_elevator(nullptr);
                    } else {
                        auto cb = std::make_shared<nb::object>(callback);
                        self.set_scene_elevator([cb](const SceneKey& key) {
                            nb::gil_scoped_acquire guard;
                            return nb::cast<bool>((*cb)(key));
                        });
                    }
                },
                nb::arg("callback").none(),
                "Set the host scene materialization provider. Pass None to clear.")

            .def("invoke_after_render", &SceneManager::invoke_after_render, "Invoke after_render callback (if set).")

            .def("invoke_before_scene_close",
                 &SceneManager::invoke_before_scene_close,
                 nb::arg("key"),
                 "Invoke before_scene_close callback (if set).");

        // Scene pool query functions (used by CoreRegistryViewer)

        m.def("tc_scene_registry_count", []() -> size_t { return tc_scene_pool_count(); });

        m.def("tc_scene_registry_get_all_info", []() {
            size_t count = 0;
            tc_scene_info* infos = tc_scene_pool_get_all_info(&count);
            nb::list result;
            for (size_t i = 0; i < count; ++i) {
                nb::dict d;
                d["handle"] = nb::make_tuple(infos[i].handle.index, infos[i].handle.generation);
                d["name"] = infos[i].name ? nb::str(infos[i].name) : nb::none();
                d["entity_count"] = infos[i].entity_count;
                d["pending_count"] = infos[i].pending_count;
                d["update_count"] = infos[i].update_count;
                d["fixed_update_count"] = infos[i].fixed_update_count;
                result.append(d);
            }
            free(infos);
            return result;
        });

        m.def(
            "tc_scene_get_entities",
            [](nb::tuple handle_tuple) {
                tc_scene_handle h;
                h.index = nb::cast<uint32_t>(handle_tuple[0]);
                h.generation = nb::cast<uint32_t>(handle_tuple[1]);

                if (!tc_scene_pool_alive(h)) {
                    return nb::list();
                }

                tc_entity_pool* pool = tc_scene_entity_pool(h);
                if (!pool) {
                    return nb::list();
                }

                struct CollectCtx {
                    tc_entity_pool* pool;
                    nb::list result;
                };
                CollectCtx ctx{pool, nb::list()};

                tc_entity_pool_foreach(
                    pool,
                    [](tc_entity_pool* p, tc_entity_id id, void* ud) -> bool {
                        auto* c = static_cast<CollectCtx*>(ud);
                        nb::dict d;
                        const char* name = tc_entity_pool_name(c->pool, id);
                        const char* uuid = tc_entity_pool_uuid(c->pool, id);
                        tc_entity_id parent = tc_entity_pool_parent(c->pool, id);
                        size_t component_count = tc_entity_pool_component_count(c->pool, id);
                        nb::list components;
                        for (size_t i = 0; i < component_count; ++i) {
                            tc_component* component = tc_entity_pool_component_at(c->pool, id, i);
                            nb::dict component_info;
                            const char* type_name = tc_component_type_name(component);
                            component_info["type_name"] = type_name ? nb::str(type_name) : nb::str("<unknown>");
                            component_info["enabled"] = component ? component->enabled : false;
                            component_info["active_in_editor"] = component ? component->active_in_editor : false;
                            component_info["started"] = component ? component->_started : false;
                            component_info["has_update"] = component ? component->has_update : false;
                            component_info["has_fixed_update"] = component ? component->has_fixed_update : false;
                            component_info["has_late_update"] = component ? component->has_late_update : false;
                            component_info["ptr"] = reinterpret_cast<uintptr_t>(component);
                            components.append(component_info);
                        }

                        d["name"] = name ? nb::str(name) : nb::none();
                        d["uuid"] = uuid ? nb::str(uuid) : nb::str("");
                        d["id_index"] = id.index;
                        d["id_generation"] = id.generation;
                        d["runtime_id"] = tc_entity_pool_runtime_id(c->pool, id);
                        d["pick_id"] = tc_entity_pool_pick_id(c->pool, id);
                        d["enabled"] = tc_entity_pool_enabled(c->pool, id);
                        d["visible"] = tc_entity_pool_visible(c->pool, id);
                        d["pickable"] = tc_entity_pool_pickable(c->pool, id);
                        d["selectable"] = tc_entity_pool_selectable(c->pool, id);
                        d["priority"] = tc_entity_pool_priority(c->pool, id);
                        d["layer"] = tc_entity_pool_layer(c->pool, id);
                        d["flags"] = tc_entity_pool_flags(c->pool, id);
                        if (tc_entity_id_valid(parent)) {
                            d["parent_index"] = parent.index;
                            d["parent_generation"] = parent.generation;
                        } else {
                            d["parent_index"] = nb::none();
                            d["parent_generation"] = nb::none();
                        }
                        d["children_count"] = tc_entity_pool_children_count(c->pool, id);
                        d["component_count"] = component_count;
                        d["components"] = components;
                        c->result.append(d);
                        return true;
                    },
                    &ctx);

                return ctx.result;
            },
            nb::arg("handle"));

        m.def(
            "tc_scene_get_component_types",
            [](nb::tuple handle_tuple) {
                tc_scene_handle h;
                h.index = nb::cast<uint32_t>(handle_tuple[0]);
                h.generation = nb::cast<uint32_t>(handle_tuple[1]);

                size_t count = 0;
                tc_scene_component_type* types = tc_scene_get_all_component_types(h, &count);
                nb::list result;
                for (size_t i = 0; i < count; ++i) {
                    nb::dict d;
                    d["type_name"] = types[i].type_name ? nb::str(types[i].type_name) : nb::str("unknown");
                    d["count"] = types[i].count;
                    result.append(d);
                }
                free(types);
                return result;
            },
            nb::arg("handle"));
    }

} // namespace termin
