#include "inspect_registry.hpp"
#include "termin/assets/handles.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/entity_handle.hpp"
#include "termin/entity/entity_registry.hpp"

namespace termin {

py::object InspectRegistry::convert_value_for_kind(py::object value, const std::string& kind) {
    if (value.is_none()) {
        // Return empty handle for handle types
        if (kind == "mesh") {
            return py::cast(MeshHandle());
        }
        if (kind == "material") {
            return py::cast(MaterialHandle());
        }
        if (kind == "skeleton") {
            return py::cast(SkeletonHandle());
        }
        return value;
    }

    // If already the correct handle type, return as-is
    if (kind == "mesh" && py::isinstance<MeshHandle>(value)) {
        return value;
    }
    if (kind == "material" && py::isinstance<MaterialHandle>(value)) {
        return value;
    }
    if (kind == "skeleton" && py::isinstance<SkeletonHandle>(value)) {
        return value;
    }

    // Convert from data/asset to handle
    if (kind == "skeleton") {
        // Check if it's a SkeletonData*
        try {
            auto* skel_data = value.cast<SkeletonData*>();
            if (skel_data != nullptr) {
                // Create asset via SkeletonAsset.from_skeleton_data() and register
                py::object skel_asset_module = py::module_::import("termin.assets.skeleton_asset");
                py::object SkeletonAsset = skel_asset_module.attr("SkeletonAsset");
                py::object asset = SkeletonAsset.attr("from_skeleton_data")(value, py::arg("name") = "skeleton");

                // Register with ResourceManager
                py::object rm_module = py::module_::import("termin.assets.resources");
                py::object rm = rm_module.attr("ResourceManager").attr("instance")();
                rm.attr("register_skeleton")(
                    py::arg("name") = "skeleton",
                    py::arg("skeleton") = value
                );

                return py::cast(SkeletonHandle::from_asset(asset));
            }
        } catch (const py::cast_error&) {
            // Not SkeletonData*, try SkeletonAsset
        }

        // Check if it's a SkeletonAsset (has 'resource' attribute)
        if (py::hasattr(value, "resource")) {
            return py::cast(SkeletonHandle::from_asset(value));
        }
    }

    // For other kinds, return value as-is
    return value;
}

nos::trent InspectRegistry::py_to_trent_with_kind(py::object obj, const std::string& kind) {
    // Handle types serialize to dict
    if (kind == "mesh" || kind == "material" || kind == "skeleton") {
        if (py::hasattr(obj, "serialize")) {
            py::dict d = obj.attr("serialize")();
            return py_dict_to_trent(d);
        }
        return nos::trent::nil();
    }

    // Entity list - serialize EntityHandle list as list of UUIDs
    if (kind == "entity_list") {
        nos::trent result;
        result.init(nos::trent_type::list);

        if (py::isinstance<py::list>(obj)) {
            for (auto item : obj) {
                if (item.is_none()) {
                    result.push_back(nos::trent::nil());
                } else {
                    try {
                        // Try EntityHandle first
                        EntityHandle handle = item.cast<EntityHandle>();
                        if (!handle.uuid.empty()) {
                            result.push_back(nos::trent(handle.uuid));
                        } else {
                            result.push_back(nos::trent::nil());
                        }
                    } catch (const py::cast_error&) {
                        result.push_back(nos::trent::nil());
                    }
                }
            }
        }
        return result;
    }

    return py_to_trent(obj);
}

py::object InspectRegistry::trent_to_py_with_kind(const nos::trent& t, const std::string& kind) {
    if (kind == "mesh") {
        if (!t.is_dict()) {
            return py::cast(MeshHandle());
        }
        py::dict d = trent_to_py_dict(t);
        return py::cast(MeshHandle::deserialize(d));
    }
    if (kind == "material") {
        if (!t.is_dict()) {
            return py::cast(MaterialHandle());
        }
        py::dict d = trent_to_py_dict(t);
        return py::cast(MaterialHandle::deserialize(d));
    }
    if (kind == "skeleton") {
        if (!t.is_dict()) {
            return py::cast(SkeletonHandle());
        }
        py::dict d = trent_to_py_dict(t);
        return py::cast(SkeletonHandle::deserialize(d));
    }

    // Entity list - deserialize from list of UUIDs into EntityHandle list
    if (kind == "entity_list") {
        std::cout << "[trent_to_py_with_kind] entity_list, is_list=" << t.is_list() << std::endl;
        std::vector<EntityHandle> result;
        if (t.is_list()) {
            std::cout << "[trent_to_py_with_kind] list size=" << t.as_list().size() << std::endl;
            for (const auto& item : t.as_list()) {
                if (item.is_string()) {
                    std::string uuid = item.as_string();
                    std::cout << "[trent_to_py_with_kind] uuid=" << uuid << std::endl;
                    result.push_back(EntityHandle(uuid));
                } else {
                    result.push_back(EntityHandle());
                }
            }
        }
        std::cout << "[trent_to_py_with_kind] result size=" << result.size() << std::endl;
        return py::cast(result);
    }

    return trent_to_py(t);
}

} // namespace termin
