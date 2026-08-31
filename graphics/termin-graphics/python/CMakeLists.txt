find_package(Python 3.14 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_tgfx_native NB_SHARED
    bindings/tgfx_module.cpp
    bindings/graphics_bindings.cpp
    bindings/shader_bindings.cpp
    bindings/texture_bindings.cpp
    bindings/tgfx2_bindings.cpp
    bindings/immediate_bindings.cpp
)

target_link_libraries(_tgfx_native PRIVATE termin_graphics termin_graphics2 tmesh::termin_mesh)
if(TGFX2_ENABLE_OPENGL)
    target_link_libraries(_tgfx_native PRIVATE OpenGL::GL)
endif()
target_include_directories(_tgfx_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../include)

termin_set_rpath_pip(_tgfx_native)

install(TARGETS _tgfx_native DESTINATION lib/python/tgfx)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tgfx/
    DESTINATION lib/python/tgfx
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.so" EXCLUDE
)
