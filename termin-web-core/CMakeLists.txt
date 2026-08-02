cmake_minimum_required(VERSION 3.18)

if(NOT EMSCRIPTEN)
    message(FATAL_ERROR "termin-web-core can only be built with Emscripten")
endif()

file(READ "${CMAKE_CURRENT_SOURCE_DIR}/shaders/web_triangle.wgsl" TRIANGLE_WGSL)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/shaders/web_triangle.layout.json" TRIANGLE_LAYOUT)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/shaders/web_textured_mesh.wgsl" TEXTURED_MESH_WGSL)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/shaders/web_textured_mesh.layout.json" TEXTURED_MESH_LAYOUT)
configure_file(
    src/web_render_shaders.hpp.in
    "${CMAKE_CURRENT_BINARY_DIR}/generated/web_render_shaders.hpp"
    @ONLY
)

add_executable(termin_web_core src/web_core.cpp)
target_include_directories(termin_web_core PRIVATE
    "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
target_link_libraries(termin_web_core PRIVATE
    tcbase::termin_base
    termin_inspect::termin_inspect
    termin_bootstrap::termin_bootstrap
    tmesh::termin_mesh
    termin_scene::termin_scene
    tgfx::termin_graphics2
)
target_link_options(termin_web_core PRIVATE
    "--no-entry"
    "-sMODULARIZE=1"
    "-sEXPORT_ES6=1"
    "-sEXPORT_NAME=createTerminWebCore"
    "-sENVIRONMENT=web,node"
    "-sALLOW_MEMORY_GROWTH=1"
    "-sFILESYSTEM=0"
    "-sEXPORTED_FUNCTIONS=['_termin_web_core_smoke','_termin_web_render_smoke_start','_termin_web_render_smoke_status','_termin_web_render_smoke_error','_termin_web_render_smoke_resize']"
    "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString']"
)
set_target_properties(termin_web_core PROPERTIES
    OUTPUT_NAME "termin_web_core"
    SUFFIX ".mjs"
)

file(MAKE_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
configure_file(web/termin-web-core.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-core.mjs" COPYONLY)
configure_file(web/smoke.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/smoke.html" COPYONLY)

find_program(TERMIN_HOST_PYTHON NAMES python3 python REQUIRED)

add_custom_target(termin_web_core_node_smoke
    COMMAND "${CMAKE_COMMAND}" -E env
        "TERMIN_WEB_CORE_DIR=${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
        node "${CMAKE_CURRENT_SOURCE_DIR}/tests/node-smoke.mjs"
    DEPENDS termin_web_core
    USES_TERMINAL
)

add_custom_target(termin_web_core_browser_smoke
    COMMAND "${TERMIN_HOST_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_smoke.py"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    DEPENDS termin_web_core
    USES_TERMINAL
)
