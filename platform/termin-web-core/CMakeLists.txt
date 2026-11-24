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

add_library(termin_web_runtime_objects OBJECT
    src/visual_scene_example.cpp
    src/web_chart2d.cpp
    src/web_chart3d.cpp
    src/web_core.cpp
    src/web_scene_pick.cpp
    src/web_graphics_assets.cpp
)
target_include_directories(termin_web_runtime_objects PRIVATE
    "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
target_link_libraries(termin_web_runtime_objects PUBLIC
    tcbase::termin_base
    termin_inspect::termin_inspect
    termin_bootstrap::termin_bootstrap
    termin_components_physics::termin_components_physics
    termin_components_ui::termin_components_ui
    termin_runtime::termin_runtime
    tmesh::termin_mesh
    termin_scene::termin_scene
    termin_visual_scene::termin_visual_scene
    tgfx::termin_graphics2
    tcplot::tcplot
)
set(TERMIN_WEB_CHART_FONT
    "${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/recastnavigation/RecastDemo/Bin/DroidSans.ttf")
target_compile_options(termin_web_runtime_objects PUBLIC -fexceptions)
target_link_options(termin_web_runtime_objects INTERFACE
    "-fexceptions"
    "--no-entry"
    "--embed-file" "${TERMIN_WEB_CHART_FONT}@/fonts/DroidSans.ttf"
    "-sMODULARIZE=1"
    "-sEXPORT_ES6=1"
    "-sEXPORT_NAME=createTerminWebCore"
    "-sENVIRONMENT=web,node"
    "-sALLOW_MEMORY_GROWTH=1"
    "-sFORCE_FILESYSTEM=1"
    "-sMIN_WEBGL_VERSION=2"
    "-sMAX_WEBGL_VERSION=2"
    "-sFULL_ES3=1"
    "-sEXPORTED_FUNCTIONS=['_malloc','_free','_termin_web_core_smoke','_termin_web_core_lifecycle_smoke','_termin_web_core_shutdown','_termin_web_host_graphics_start','_termin_web_host_graphics_status','_termin_web_host_graphics_backend','_termin_web_host_graphics_error','_termin_web_host_set_package_blob','_termin_web_host_load','_termin_web_host_load_headless','_termin_web_host_tick','_termin_web_host_pick_entity','_termin_web_host_set_light_enabled','_termin_web_host_reset_rigid_body','_termin_web_host_record_rigid_body_height','_termin_web_host_read_rigid_body_height_trace','_termin_web_host_height_trace_error','_termin_web_host_set_ui_widget_enabled','_termin_web_host_bind_ui_button','_termin_web_host_unbind_ui_button','_termin_web_host_loop_start','_termin_web_host_loop_stop','_termin_web_host_unload','_termin_web_host_error','_termin_web_host_frame_count','_termin_web_host_entity_count','_termin_web_host_resize','_termin_web_host_dispatch_pointer','_termin_web_host_dispatch_mouse_move','_termin_web_host_dispatch_mouse_button','_termin_web_host_dispatch_wheel','_termin_web_host_dispatch_key','_termin_web_host_dispatch_text','_termin_web_host_dispatch_focus_lost','_termin_web_visual_scene_render','_termin_web_visual_scene_error','_termin_web_chart2d_create','_termin_web_chart2d_set_data','_termin_web_chart2d_set_range','_termin_web_chart2d_resize','_termin_web_chart2d_pointer','_termin_web_chart2d_wheel','_termin_web_chart2d_range','_termin_web_chart2d_render','_termin_web_chart2d_destroy','_termin_web_chart2d_error','_termin_web_chart3d_create','_termin_web_chart3d_set_surface','_termin_web_chart3d_resize','_termin_web_chart3d_pointer','_termin_web_chart3d_wheel','_termin_web_chart3d_fit','_termin_web_chart3d_reset','_termin_web_chart3d_camera','_termin_web_chart3d_render','_termin_web_chart3d_destroy','_termin_web_chart3d_error','_termin_web_render_smoke_start','_termin_web_render_smoke_status','_termin_web_render_smoke_error','_termin_web_render_smoke_resize']"
    "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString','FS','ccall','getExceptionMessage','HEAPU8']"
)
# Link example gameplay only into its own Wasm module. Both modules share the
# same compiled runtime and browser ABI.
add_executable(termin_web_core)
add_executable(termin_web_salvage examples/salvage/web_salvage.cpp)
target_include_directories(termin_web_salvage PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
foreach(runtime IN ITEMS termin_web_core termin_web_salvage)
    target_link_libraries(${runtime} PRIVATE termin_web_runtime_objects)
    set_property(TARGET ${runtime} APPEND PROPERTY LINK_DEPENDS "${TERMIN_WEB_CHART_FONT}")
    set_target_properties(${runtime} PROPERTIES SUFFIX ".mjs")
endforeach()

file(MAKE_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
configure_file(web/termin-web-assets.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-assets.mjs" COPYONLY)
configure_file(web/termin-web-core.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-core.mjs" COPYONLY)
configure_file(web/termin-web-host.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-host.mjs" COPYONLY)
configure_file(web/termin-web-input.mjs "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-input.mjs" COPYONLY)
configure_file(web/smoke.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/smoke.html" COPYONLY)
configure_file(web/physics-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/physics-scene.html" COPYONLY)
configure_file(web/ui-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/ui-scene.html" COPYONLY)
configure_file(web/interactive-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/interactive-scene.html" COPYONLY)
configure_file(web/bathyscaphe-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/bathyscaphe-scene.html" COPYONLY)
configure_file(web/salvage-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/salvage-scene.html" COPYONLY)
configure_file(web/viewer.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/viewer.html" COPYONLY)
configure_file(web/visual-scene.html "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/visual-scene.html" COPYONLY)
set(TERMIN_WEB_CHART_MODULES
    termin-web-chart.mjs
    termin-web-chart2d.mjs
    termin-web-chart3d.mjs
)
foreach(asset IN ITEMS ${TERMIN_WEB_CHART_MODULES} chart2d.html chart3d.html)
    configure_file("web/${asset}" "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/${asset}" COPYONLY)
endforeach()
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
set(TERMIN_WEB_HOST_WGSL_VALIDATOR "" CACHE FILEPATH
    "Native Naga validator for demo WebGPU shaders")
set(TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT "" CACHE PATH
    "Canonical native build root containing offline built-in shader artifacts")
if(NOT EXISTS "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/builtin-shader-artifacts.json")
    message(FATAL_ERROR
        "Web packaging requires TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT with a "
        "built-in shader artifact manifest. Configure through 'task build:web'.")
endif()
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
file(GLOB_RECURSE TERMIN_WEB_GRAPHICS_ASSETS CONFIGURE_DEPENDS
    "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/builtin_shaders/*"
    "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/shaders/*")
set(TERMIN_WEB_GRAPHICS_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/graphics.trpkg")
add_custom_command(OUTPUT "${TERMIN_WEB_GRAPHICS_PACKAGE}"
    COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_PACKAGE_BLOB_SCRIPT}"
        "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}" "${TERMIN_WEB_GRAPHICS_PACKAGE}"
    DEPENDS "${TERMIN_PACKAGE_BLOB_SCRIPT}"
        "${TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT}/builtin-shader-artifacts.json"
        ${TERMIN_WEB_GRAPHICS_ASSETS}
    VERBATIM)
add_custom_target(termin_web_graphics_package DEPENDS "${TERMIN_WEB_GRAPHICS_PACKAGE}")
add_dependencies(termin_web_core termin_web_graphics_package)

set(TERMIN_WEB_CHART3D_PAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/Termin-Chart3D.html")
set(TERMIN_WEB_HTML_PACKER "${CMAKE_CURRENT_SOURCE_DIR}/tools/package_web_html.py")
set(TERMIN_WEB_HTML_LOADER "${CMAKE_CURRENT_SOURCE_DIR}/tools/standalone-loader.js")
add_custom_command(OUTPUT "${TERMIN_WEB_CHART3D_PAGE}"
    COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_WEB_HTML_PACKER}"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/chart3d.html" "${TERMIN_WEB_CHART3D_PAGE}"
    DEPENDS termin_web_core "${TERMIN_WEB_HTML_PACKER}" "${TERMIN_WEB_HTML_LOADER}" "${TERMIN_WEB_GRAPHICS_PACKAGE}"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/chart3d.html"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-chart3d.mjs"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-chart.mjs"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-core.mjs"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-assets.mjs"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-host.mjs"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-input.mjs"
    VERBATIM)
add_custom_target(termin_web_chart3d_standalone DEPENDS "${TERMIN_WEB_CHART3D_PAGE}")

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

if(TARGET termin_web_core_webgl2_artifacts)
    add_dependencies(termin_web_core_fixture_packages termin_web_core_webgl2_artifacts)
endif()

set(TERMIN_WEB_INTERACTIVE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/examples/interactive-scene")
set(TERMIN_WEB_INTERACTIVE_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/interactive-scene/package.trpkg")
set(TERMIN_WEB_PHYSICS_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/physics-scene/package.trpkg")
set(TERMIN_WEB_BATHYSCAPHE_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/bathyscaphe-scene/package.trpkg")
set(TERMIN_WEB_SALVAGE_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/salvage-scene/package.trpkg")
add_custom_command(OUTPUT "${TERMIN_WEB_INTERACTIVE_PACKAGE}" "${TERMIN_WEB_PHYSICS_PACKAGE}"
        "${TERMIN_WEB_BATHYSCAPHE_PACKAGE}" "${TERMIN_WEB_SALVAGE_PACKAGE}"
    COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_WEB_INTERACTIVE_SOURCE}/build_package.py"
        --fixture "${TERMIN_WEB_RENDER_FIXTURE_DIR}"
        --shaderc "${TERMIN_WEB_HOST_SHADERC}" --slangc "${TERMIN_WEB_HOST_SLANGC}"
        --wgsl-validator "${TERMIN_WEB_HOST_WGSL_VALIDATOR}" --output "${TERMIN_WEB_INTERACTIVE_PACKAGE}"
        --physics-output "${TERMIN_WEB_PHYSICS_PACKAGE}"
        --bathyscaphe-output "${TERMIN_WEB_BATHYSCAPHE_PACKAGE}"
        --salvage-output "${TERMIN_WEB_SALVAGE_PACKAGE}"
    DEPENDS "${TERMIN_WEB_INTERACTIVE_SOURCE}/build_package.py" "${TERMIN_WEB_INTERACTIVE_SOURCE}/demo_scenes.py"
        "${TERMIN_WEB_INTERACTIVE_SOURCE}/bathyscaphe.py" "${TERMIN_WEB_INTERACTIVE_SOURCE}/salvage.py"
        "${TERMIN_WEB_INTERACTIVE_SOURCE}/salvage.frag.slang"
        "${TERMIN_WEB_INTERACTIVE_SOURCE}/physics-hud.ui-document.json"
        "${TERMIN_WEB_INTERACTIVE_SOURCE}/lit.vert.slang" "${TERMIN_WEB_INTERACTIVE_SOURCE}/lit.frag.slang"
        "${TERMIN_WEB_INTERACTIVE_SOURCE}/static-shadow.vert.slang" "${TERMIN_WEB_INTERACTIVE_SOURCE}/static-shadow.variants.json"
        "${TERMIN_WEB_RENDER_FIXTURE_DIR}/package.trpkg" "${TERMIN_PACKAGE_BLOB_SCRIPT}"
        "${TERMIN_WEB_HOST_SHADERC}" "${TERMIN_WEB_HOST_SLANGC}" "${TERMIN_WEB_HOST_WGSL_VALIDATOR}"
    VERBATIM)
set(TERMIN_WEB_UI_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/examples/ui-scene")
set(TERMIN_WEB_UI_PACKAGE "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/fixtures/ui-scene/package.trpkg")
add_custom_command(OUTPUT "${TERMIN_WEB_UI_PACKAGE}"
    COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_WEB_UI_SOURCE}/build_package.py"
        --fixture "${TERMIN_WEB_RENDER_FIXTURE_DIR}" --output "${TERMIN_WEB_UI_PACKAGE}"
    DEPENDS "${TERMIN_WEB_UI_SOURCE}/build_package.py" "${TERMIN_WEB_UI_SOURCE}/hud.ui-document.json"
        "${TERMIN_WEB_RENDER_FIXTURE_DIR}/package.trpkg" "${TERMIN_PACKAGE_BLOB_SCRIPT}"
    VERBATIM)
add_custom_target(termin_web_demo_packages DEPENDS
    "${TERMIN_WEB_INTERACTIVE_PACKAGE}" "${TERMIN_WEB_PHYSICS_PACKAGE}"
    "${TERMIN_WEB_BATHYSCAPHE_PACKAGE}" "${TERMIN_WEB_SALVAGE_PACKAGE}" "${TERMIN_WEB_UI_PACKAGE}")
add_dependencies(termin_web_demo_packages termin_web_core_fixture_packages)

function(termin_web_scene_demo name page package runtime)
    set(source "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/${name}-scene.html")
    set(output "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/${page}.html")
    add_custom_command(OUTPUT "${output}"
        COMMAND "${TERMIN_HOST_PYTHON}" "${TERMIN_WEB_HTML_PACKER}"
            "${source}" "${output}" --scene-package "${package}" --wasm "${runtime}.wasm"
        DEPENDS ${runtime} "${TERMIN_WEB_HTML_PACKER}" "${TERMIN_WEB_HTML_LOADER}" "${package}" "${source}"
            ${ARGN}
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-core.mjs"
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-assets.mjs"
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-host.mjs"
            "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-input.mjs"
        VERBATIM)
    add_custom_target(termin_web_${name}_scene DEPENDS "${output}")
    add_dependencies(termin_web_${name}_scene termin_web_demo_packages)
endfunction()
termin_web_scene_demo(salvage Termin-Salvage "${TERMIN_WEB_SALVAGE_PACKAGE}" termin_web_salvage)
termin_web_scene_demo(interactive Termin-InteractiveScene "${TERMIN_WEB_INTERACTIVE_PACKAGE}" termin_web_core)
termin_web_scene_demo(bathyscaphe Termin-Bathyscaphe "${TERMIN_WEB_BATHYSCAPHE_PACKAGE}" termin_web_core)
termin_web_scene_demo(physics Termin-PhysicsScene "${TERMIN_WEB_PHYSICS_PACKAGE}" termin_web_core
    "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-chart2d.mjs"
    "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/termin-web-chart.mjs")
termin_web_scene_demo(ui Termin-UiScene "${TERMIN_WEB_UI_PACKAGE}" termin_web_core)
add_custom_target(termin_web_standalone_demos)
add_dependencies(termin_web_standalone_demos
    termin_web_chart3d_standalone termin_web_interactive_scene termin_web_physics_scene termin_web_ui_scene
    termin_web_bathyscaphe_scene termin_web_salvage_scene)

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
    DEPENDS termin_web_standalone_demos
    USES_TERMINAL
)
if(TARGET tgfx2_webgpu_binding_layout_browser_gate)
    add_dependencies(termin_web_core_browser_smoke tgfx2_webgpu_binding_layout_browser_gate)
endif()

add_custom_target(termin_web_visual_scene_browser_smoke
    COMMAND "${TERMIN_HOST_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/visual_scene_browser_smoke.py"
        "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    DEPENDS termin_web_core termin_web_core_fixture_packages
    USES_TERMINAL
)
