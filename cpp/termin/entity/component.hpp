#pragma once

#include <string>
#include <cstdint>

namespace termin {

class Entity;  // Forward declaration

/**
 * Base class for all components.
 *
 * Both C++ and Python components inherit from this.
 * C++ components use REGISTER_COMPONENT macro for auto-registration.
 * Python components register via Component.__init_subclass__.
 */
class Component {
public:
    virtual ~Component() = default;

    // Type identification (for serialization)
    virtual const char* type_name() const = 0;

    // Lifecycle hooks
    virtual void start() {}
    virtual void update(float dt) {}
    virtual void on_destroy() {}

    // Called when added/removed from entity
    virtual void on_added_to_entity() {}
    virtual void on_removed_from_entity() {}

    // Flags
    bool enabled = true;
    bool is_native = false;  // True for C++ components, false for Python

    // Owner entity (set by Entity::add_component)
    Entity* entity = nullptr;

protected:
    Component() = default;
};

// Helper macro for declaring type_name in derived classes
#define COMPONENT_BODY(TypeName) \
    const char* type_name() const override { return #TypeName; }

} // namespace termin
