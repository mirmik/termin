find_package(Python 3.14 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_mesh_native NB_SHARED
    bindings/tmesh_module.cpp
    bindings/mesh_bindings.cpp
)

target_link_libraries(_mesh_native PRIVATE termin_mesh)
target_include_directories(_mesh_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../include)

termin_set_rpath_pip(_mesh_native)

install(TARGETS _mesh_native DESTINATION lib/python/termin/mesh)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin/mesh/
    DESTINATION lib/python/termin/mesh
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
)
