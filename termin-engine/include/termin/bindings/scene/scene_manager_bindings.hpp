// scene_manager_bindings.hpp - Python bindings header
#ifndef TC_SCENE_MANAGER_BINDINGS_HPP
#define TC_SCENE_MANAGER_BINDINGS_HPP

#include <nanobind/nanobind.h>

namespace termin {

void bind_scene_manager(nanobind::module_& m);

} // namespace termin

#endif // TC_SCENE_MANAGER_BINDINGS_HPP
