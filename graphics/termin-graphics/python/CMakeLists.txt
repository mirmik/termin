find_package(Python 3.14 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_graphics_native NB_SHARED
    bindings/tgfx_module.cpp
    bindings/graphics_bindings.cpp
    bindings/shader_bindings.cpp
    bindings/texture_bindings.cpp
    bindings/tgfx2_bindings.cpp
    bindings/immediate_bindings.cpp
)

target_link_libraries(_graphics_native PRIVATE termin_graphics termin_graphics2 tmesh::termin_mesh)
if(TGFX2_ENABLE_OPENGL)
    target_link_libraries(_graphics_native PRIVATE OpenGL::GL)
endif()
target_include_directories(_graphics_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../include)

termin_set_rpath_pip(_graphics_native)

install(TARGETS _graphics_native DESTINATION lib/python/termin/graphics)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin/graphics/
    DESTINATION lib/python/termin/graphics
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.so" EXCLUDE
)
