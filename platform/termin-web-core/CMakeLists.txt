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
    "-sMIN_WEBGL_VERSION=2"
    "-sMAX_WEBGL_VERSION=2"
    "-sFULL_ES3=1"
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_termin_web_core_smoke','_termin_web_core_lifecycle_smoke','_termin_web_core_shutdown','_termin_web_host_graphics_start','_termin_web_host_graphics_status','_termin_web_host_graphics_backend','_termin_web_host_graphics_error','_termin_web_host_set_package_blob','_termin_web_host_load','_termin_web_host_load_headless','_termin_web_host_tick','_termin_web_host_loop_start','_termin_web_host_loop_stop','_termin_web_host_unload','_termin_web_host_error','_termin_web_host_frame_count','_termin_web_host_entity_count','_termin_web_host_resize','_termin_web_host_dispatch_pointer','_termin_web_host_dispatch_mouse_move','_termin_web_host_dispatch_mouse_button','_termin_web_host_dispatch_wheel','_termin_web_host_dispatch_key','_termin_web_host_dispatch_text','_termin_web_host_dispatch_focus_lost','_termin_web_visual_scene_render','_termin_web_visual_scene_error','_termin_web_render_smoke_start','_termin_web_render_smoke_status','_termin_web_render_smoke_error','_termin_web_render_smoke_resize']"
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
foreach(TERMIN_WEB_STATIC_FIXTURE
        core-package
        invalid-package
        invalid-path-package
        unsupported-component-package
        unsupported-resource-package)
    file(COPY "web/fixtures/${TERMIN_WEB_STATIC_FIXTURE}"
        DESTINATION "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures")
endforeach()

find_program(TERMIN_HOST_PYTHON NAMES python3 python REQUIRED)

set(TERMIN_WEB_RENDER_FIXTURE_DIR
    "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/render-package")
set(TERMIN_WEB_RENDER_FIXTURE_SOURCE_STAMP
    "${TERMIN_WEB_RENDER_FIXTURE_DIR}/.source-fixture.stamp")
file(GLOB_RECURSE TERMIN_WEB_RENDER_FIXTURE_SOURCE_FILES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/web/fixtures/render-package/*")
add_custom_command(OUTPUT "${TERMIN_WEB_RENDER_FIXTURE_SOURCE_STAMP}"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory
        "${CMAKE_CURRENT_SOURCE_DIR}/web/fixtures/render-package"
        "${TERMIN_WEB_RENDER_FIXTURE_DIR}"
    COMMAND "${CMAKE_COMMAND}" -E touch "${TERMIN_WEB_RENDER_FIXTURE_SOURCE_STAMP}"
    DEPENDS ${TERMIN_WEB_RENDER_FIXTURE_SOURCE_FILES}
    VERBATIM)

set(TERMIN_WEB_HOST_SHADERC "" CACHE FILEPATH
    "Native termin_shaderc used to prepare offline WebGL2 artifacts")
set(TERMIN_WEB_HOST_SLANGC "" CACHE FILEPATH
    "Native slangc used to prepare offline WebGL2 artifacts")
set(TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT "" CACHE PATH
    "Canonical native build root containing offline built-in shader artifacts")
if(TGFX2_ENABLE_WEBGL2)
    if(NOT EXISTS "${TERMIN_WEB_HOST_SHADERC}")
        message(FATAL_ERROR
            "WebGL2 packaging requires native TERMIN_WEB_HOST_SHADERC. "
            "Configure through 'task build:web -- ...' or provide the executable explicitly.")
    endif()
    if(NOT EXISTS "${TERMIN_WEB_HOST_SLANGC}")
        message(FATAL_ERROR
            "WebGL2 packaging requires native TERMIN_WEB_HOST_SLANGC. "
            "Configure through 'task build:web -- ...' or provide the executable explicitly.")
    endif()
    if(NOT EXISTS "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/builtin-shader-artifacts.json")
        message(FATAL_ERROR
            "Web packaging requires TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT with a "
            "built-in shader artifact manifest. Configure through 'task build:web'.")
    endif()
    set(TERMIN_WEBGL2_FIXTURE_STAMP
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/render-package/.webgl2-artifacts.stamp")
    add_custom_command(OUTPUT "${TERMIN_WEBGL2_FIXTURE_STAMP}"
        COMMAND "${TERMIN_HOST_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_webgl2_fixture.py"
            --shaderc "${TERMIN_WEB_HOST_SHADERC}"
            --slangc "${TERMIN_WEB_HOST_SLANGC}"
            --builtin-artifact-root "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}"
            --fixture "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/render-package"
        COMMAND "${CMAKE_COMMAND}" -E touch "${TERMIN_WEBGL2_FIXTURE_STAMP}"
        DEPENDS
            "${TERMIN_WEB_RENDER_FIXTURE_SOURCE_STAMP}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_webgl2_fixture.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/web/fixtures/render-package/manifest.json"
            "${TERMIN_WEB_HOST_SHADERC}"
            "${TERMIN_WEB_HOST_SLANGC}"
            "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/builtin-shader-artifacts.json"
        VERBATIM)
    add_custom_target(termin_web_core_webgl2_artifacts
        DEPENDS "${TERMIN_WEBGL2_FIXTURE_STAMP}")
    add_dependencies(termin_web_core termin_web_core_webgl2_artifacts)
endif()

set(TERMIN_PACKAGE_BLOB_SCRIPT
    "${CMAKE_CURRENT_SOURCE_DIR}/../../editor/termin-project-build/python/termin/project_build/runtime_package_blob.py")
set(TERMIN_WEB_FIXTURE_PACKAGES)
foreach(TERMIN_WEB_FIXTURE
        core-package
        invalid-package
        invalid-path-package
        unsupported-component-package
        unsupported-resource-package
        render-package)
    set(TERMIN_WEB_FIXTURE_DIR
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/${TERMIN_WEB_FIXTURE}")
    set(TERMIN_WEB_FIXTURE_BLOB "${TERMIN_WEB_FIXTURE_DIR}/package.trpkg")
    file(GLOB_RECURSE TERMIN_WEB_FIXTURE_SOURCE_FILES CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/web/fixtures/${TERMIN_WEB_FIXTURE}/*")
    set(TERMIN_WEB_FIXTURE_DEPENDS
        "${TERMIN_PACKAGE_BLOB_SCRIPT}"
        ${TERMIN_WEB_FIXTURE_SOURCE_FILES})
    if(TERMIN_WEB_FIXTURE STREQUAL "render-package" AND TGFX2_ENABLE_WEBGL2)
        list(APPEND TERMIN_WEB_FIXTURE_DEPENDS "${TERMIN_WEBGL2_FIXTURE_STAMP}")
    endif()
    add_custom_command(OUTPUT "${TERMIN_WEB_FIXTURE_BLOB}"
        COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_PACKAGE_BLOB_SCRIPT}"
            "${TERMIN_WEB_FIXTURE_DIR}"
            "${TERMIN_WEB_FIXTURE_BLOB}"
        DEPENDS ${TERMIN_WEB_FIXTURE_DEPENDS}
        VERBATIM)
    list(APPEND TERMIN_WEB_FIXTURE_PACKAGES "${TERMIN_WEB_FIXTURE_BLOB}")
endforeach()
add_custom_target(termin_web_core_fixture_packages
    DEPENDS ${TERMIN_WEB_FIXTURE_PACKAGES})

add_custom_target(termin_web_core_node_smoke
    COMMAND "${CMAKE_COMMAND}" -E env
        "TERMIN_WEB_CORE_DIR=${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
        node "${CMAKE_CURRENT_SOURCE_DIR}/tests/node-smoke.mjs"
    DEPENDS termin_web_core termin_web_core_fixture_packages
    USES_TERMINAL
)

add_custom_target(termin_web_core_browser_smoke
    COMMAND "${TERMIN_HOST_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_smoke.py"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    DEPENDS termin_web_core termin_web_core_fixture_packages
    USES_TERMINAL
)

add_custom_target(termin_web_visual_scene_browser_smoke
    COMMAND "${TERMIN_HOST_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/visual_scene_browser_smoke.py"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    DEPENDS termin_web_core termin_web_core_fixture_packages
    USES_TERMINAL
)
