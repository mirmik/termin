// tc_component_python_bindings.hpp - Python component callback setup
#pragma once

namespace termin {

// Initialize drawable and input callbacks for Python components.
// Core lifecycle callbacks are set up by _scene_native; this adds
// termin-specific drawable and input dispatch.
void init_python_component_callbacks();

} // namespace termin
