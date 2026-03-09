// scene_module.cpp - NB_MODULE entry point for _scene_native
//
// Contains: Entity, TcComponentRef, CxxComponent, ComponentRegistry,
// TcSceneRef (core), TcComponent (Python wrapper), SoA registry info.

#include <nanobind/nanobind.h>

#include <termin/bindings/entity_bindings.hpp>
#include <termin/bindings/tc_component_ref_bindings.hpp>
#include <termin/bindings/component_bindings.hpp>
#include <termin/bindings/scene_bindings.hpp>
#include <termin/bindings/soa_bindings.hpp>
#include <termin/bindings/tc_component_python_bindings.hpp>
#include <termin/bindings/transform_bindings.hpp>

namespace nb = nanobind;

NB_MODULE(_scene_native, m) {
    m.doc() = "Scene native module (Entity, Component, TcScene core, registries)";

    // Order matters: TcSceneRef before Entity (Entity.scene() returns TcSceneRef)
    // CxxComponent before Entity (Entity methods return components)
    // TcComponentRef before Entity (Entity methods return TcComponentRef)

    termin::bind_tc_scene_core(m);
    termin::bind_cxx_component(m);
    termin::bind_component_registry(m);
    termin::bind_tc_component_ref(m);
    termin::bind_tc_component_python(m);
    termin::bind_transform(m);
    termin::bind_entity_class(m);
    termin::bind_soa_registry(m);
}
