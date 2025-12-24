#include "inspect_registry.hpp"
#include "termin/assets/handles.hpp"

namespace termin {

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
    return trent_to_py(t);
}

} // namespace termin
