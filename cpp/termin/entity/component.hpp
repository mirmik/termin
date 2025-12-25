#pragma once

#include <string>
#include <cstdint>
#include <pybind11/pybind11.h>
#include "../../trent/trent.h"
#include "../inspect/inspect_registry.hpp"

namespace py = pybind11;

namespace termin {

class Entity;  // Forward declaration

// Base class for all components.
// Both C++ and Python components inherit from this.
// C++ components use REGISTER_COMPONENT macro for auto-registration.
// Python components register via Component.__init_subclass__.
class ENTITY_API Component {
public:
    virtual ~Component() = default;

    // Type identification (for serialization)
    const char* type_name() const { return _type_name; }
    void set_type_name(const char* name) { _type_name = name; }

    // Lifecycle hooks
    virtual void start() {}
    virtual void update(float dt) {}
    virtual void fixed_update(float dt) {}
    virtual void on_destroy() {}
    virtual void on_editor_start() {}

    // Editor hooks
    virtual void setup_editor_defaults() {}  // Called when created via editor UI

    // Called when added/removed from entity
    virtual void on_added_to_entity() {}
    virtual void on_removed_from_entity() {}

    // Called when entity is added/removed from scene
    virtual void on_added(py::object scene) {}
    virtual void on_removed() {}

    /**
     * Serialization - uses InspectRegistry for INSPECT_FIELD properties.
     *
     * DO NOT OVERRIDE in derived components!
     * All serializable fields should be registered via INSPECT_FIELD macro.
     * Use appropriate "kind" for special types:
     * - "mesh_handle", "material_handle", "skeleton_handle" for asset handles
     * - "entity_handle_list" for std::vector<EntityHandle>
     */
    virtual nos::trent serialize_data() const {
        return InspectRegistry::instance().serialize_all(
            const_cast<void*>(static_cast<const void*>(this)),
            _type_name
        );
    }
    virtual void deserialize_data(const nos::trent& data) {
        InspectRegistry::instance().deserialize_all(
            static_cast<void*>(this),
            _type_name,
            data
        );
    }

    nos::trent serialize() const {
        nos::trent result;
        result["type"] = _type_name;
        result["data"] = serialize_data();
        return result;
    }

    // Flags
    bool enabled = true;
    bool is_native = false;  // True for C++ components, false for Python
    bool _started = false;   // True after start() has been called
    bool has_update = false;        // True if update() is overridden
    bool has_fixed_update = false;  // True if fixed_update() is overridden

    // Owner entity (set by Entity::add_component)
    Entity* entity = nullptr;

protected:
    Component() = default;
    const char* _type_name = "Component";
};

} // namespace termin
