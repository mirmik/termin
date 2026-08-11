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

add_executable(termin_web_core
    src/visual_scene_example.cpp
    src/web_core.cpp
)
target_include_directories(termin_web_core PRIVATE
    "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
target_link_libraries(termin_web_core PRIVATE
    tcbase::termin_base
    termin_inspect::termin_inspect
    termin_bootstrap::termin_bootstrap
    termin_runtime::termin_runtime
    tmesh::termin_mesh
    termin_scene::termin_scene
    termin_visual_scene::termin_visual_scene
    tgfx::termin_graphics2
)
target_link_options(termin_web_core PRIVATE
    "-fexceptions"
    "--no-entry"
    "-sMODULARIZE=1"
    "-sEXPORT_ES6=1"
    "-sEXPORT_NAME=createTerminWebCore"
    "-sENVIRONMENT=web,node"
    "-sALLOW_MEMORY_GROWTH=1"
    "-sFORCE_FILESYSTEM=1"
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_termin_web_core_smoke','_termin_web_core_lifecycle_smoke','_termin_web_core_shutdown','_termin_web_host_graphics_start','_termin_web_host_graphics_status','_termin_web_host_graphics_error','_termin_web_host_set_package_blob','_termin_web_host_load','_termin_web_host_load_headless','_termin_web_host_tick','_termin_web_host_loop_start','_termin_web_host_loop_stop','_termin_web_host_unload','_termin_web_host_error','_termin_web_host_frame_count','_termin_web_host_entity_count','_termin_web_host_resize','_termin_web_host_dispatch_pointer','_termin_web_host_dispatch_mouse_move','_termin_web_host_dispatch_mouse_button','_termin_web_host_dispatch_wheel','_termin_web_host_dispatch_key','_termin_web_host_dispatch_text','_termin_web_host_dispatch_focus_lost','_termin_web_visual_scene_render','_termin_web_visual_scene_error','_termin_web_render_smoke_start','_termin_web_render_smoke_status','_termin_web_render_smoke_error','_termin_web_render_smoke_resize']"
    "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString','FS','ccall','getExceptionMessage','HEAPU8']"
)
set_target_properties(termin_web_core PROPERTIES
    OUTPUT_NAME "termin_web_core"
    SUFFIX ".mjs"
)

file(MAKE_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
configure_file(web/termin-web-core.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-core.mjs" COPYONLY)
configure_file(web/termin-web-host.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-host.mjs" COPYONLY)
configure_file(web/termin-web-input.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-input.mjs" COPYONLY)
configure_file(web/smoke.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/smoke.html" COPYONLY)
configure_file(web/viewer.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/viewer.html" COPYONLY)
configure_file(web/visual-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/visual-scene.html" COPYONLY)
file(COPY web/fixtures DESTINATION "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")

find_program(TERMIN_HOST_PYTHON NAMES python3 python REQUIRED)

set(TERMIN_PACKAGE_BLOB_SCRIPT
    "${CMAKE_CURRENT_SOURCE_DIR}/../termin-project-build/python/termin/project_build/runtime_package_blob.py")
foreach(TERMIN_WEB_FIXTURE
        core-package
        invalid-package
        invalid-path-package
        unsupported-component-package
        unsupported-resource-package
        render-package)
    add_custom_command(TARGET termin_web_core POST_BUILD
        COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_PACKAGE_BLOB_SCRIPT}"
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/${TERMIN_WEB_FIXTURE}"
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/${TERMIN_WEB_FIXTURE}/package.trpkg"
        VERBATIM)
endforeach()

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

add_custom_target(termin_web_visual_scene_browser_smoke
    COMMAND "${TERMIN_HOST_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/visual_scene_browser_smoke.py"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    DEPENDS termin_web_core
    USES_TERMINAL
)
