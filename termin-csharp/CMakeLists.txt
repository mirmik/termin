cmake_minimum_required(VERSION 3.16)
project(termin_csharp LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include(GNUInstallDirs)

option(TERMIN_CSHARP_BUILD_NATIVE "Build native SWIG bridge for C# bindings" ON)
option(TERMIN_CSHARP_BUILD_MANAGED "Build managed C# projects with dotnet" OFF)
option(TERMIN_CSHARP_BUILD_TESTS "Build Termin.Test project with dotnet" OFF)
set(TERMIN_CSHARP_PROFILE "full" CACHE STRING "C# SDK profile: full or plot-d3d11")
set_property(CACHE TERMIN_CSHARP_PROFILE PROPERTY STRINGS full plot-d3d11)

if(NOT TERMIN_CSHARP_PROFILE STREQUAL "full" AND NOT TERMIN_CSHARP_PROFILE STREQUAL "plot-d3d11")
    message(FATAL_ERROR "Unsupported TERMIN_CSHARP_PROFILE='${TERMIN_CSHARP_PROFILE}'. Expected 'full' or 'plot-d3d11'.")
endif()
if(WIN32)
    set(TERMIN_CSHARP_RUNTIME_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/runtimes/win-x64/native")
else()
    set(TERMIN_CSHARP_RUNTIME_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/runtimes/linux-x64/native")
endif()

file(MAKE_DIRECTORY "${TERMIN_CSHARP_RUNTIME_DIR}")
file(MAKE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Generated")

if(TERMIN_CSHARP_BUILD_NATIVE)
    find_package(SWIG REQUIRED COMPONENTS csharp)
    include(UseSWIG)

    function(termin_csharp_require_package package_name)
        if(COMMAND termin_require_package)
            termin_require_package(${ARGV})
        else()
            find_package(${package_name} REQUIRED)
        endif()
    endfunction()

    message(STATUS "termin-csharp: profile=${TERMIN_CSHARP_PROFILE}")

    termin_csharp_require_package(termin_mesh tmesh::termin_mesh)
    termin_csharp_require_package(termin_graphics tgfx::termin_graphics tgfx::termin_graphics2)
    termin_csharp_require_package(tcplot tcplot::tcplot)

    if(TERMIN_CSHARP_PROFILE STREQUAL "full")
        termin_csharp_require_package(termin_bootstrap termin_bootstrap::termin_bootstrap)
        termin_csharp_require_package(termin_materials termin_materials::termin_materials)
        termin_csharp_require_package(termin_scene termin_scene::termin_scene)
        termin_csharp_require_package(termin_collision termin_collision::termin_collision)
        termin_csharp_require_package(termin_components_collision termin_components_collision::termin_components_collision)
        termin_csharp_require_package(termin_components_mesh termin_components_mesh::termin_components_mesh)
        termin_csharp_require_package(termin_components_kinematic termin_components_kinematic::termin_components_kinematic)

        # These component DLLs are pulled in transitively by the engine/render stack
        # and can appear in termin.dll's import table, so they must be copied next to it.
        termin_csharp_require_package(termin_components_render termin_components_render::termin_components_render)
        termin_csharp_require_package(termin_components_skeleton termin_components_skeleton::termin_components_skeleton)
        termin_csharp_require_package(termin_components_foliage termin_components_foliage::termin_components_foliage)

        termin_csharp_require_package(termin_engine termin_engine::termin_engine)
        termin_csharp_require_package(termin_display termin_display::termin_display)
        termin_csharp_require_package(termin_animation termin_animation::termin_animation)
        termin_csharp_require_package(termin_skeleton termin_skeleton::termin_skeleton)
        termin_csharp_require_package(termin_render termin_render::termin_render)
        termin_csharp_require_package(termin_render_passes termin_render_passes::termin_render_passes)
    endif()
    if(NOT DEFINED TERMIN_CSHARP_ENABLE_OPENGL)
        if(DEFINED _termin_graphics_enable_opengl)
            set(TERMIN_CSHARP_ENABLE_OPENGL ${_termin_graphics_enable_opengl} CACHE BOOL "Expose OpenGL APIs in C# bindings")
        elseif(DEFINED TGFX2_ENABLE_OPENGL)
            set(TERMIN_CSHARP_ENABLE_OPENGL ${TGFX2_ENABLE_OPENGL} CACHE BOOL "Expose OpenGL APIs in C# bindings")
        else()
            set(TERMIN_CSHARP_ENABLE_OPENGL ON CACHE BOOL "Expose OpenGL APIs in C# bindings")
        endif()
    endif()
    if(TERMIN_CSHARP_ENABLE_OPENGL)
        message(STATUS "termin-csharp: OpenGL APIs enabled")
    else()
        message(STATUS "termin-csharp: OpenGL APIs disabled")
    endif()

    set(CMAKE_SWIG_OUTDIR "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Generated")

    set(_termin_csharp_swig_flags "-namespace;Termin.Native")
    if(TERMIN_CSHARP_ENABLE_OPENGL)
        list(APPEND _termin_csharp_swig_flags "-DTERMIN_CSHARP_ENABLE_OPENGL")
    endif()

    if(TERMIN_CSHARP_PROFILE STREQUAL "plot-d3d11")
        set(_termin_csharp_swig_interface "${CMAKE_CURRENT_SOURCE_DIR}/termin_plot.i")
        list(APPEND _termin_csharp_swig_flags "-DTERMIN_CSHARP_PLOT_ONLY")
        set(_termin_csharp_bridge_sources)
    else()
        set(_termin_csharp_swig_interface "${CMAKE_CURRENT_SOURCE_DIR}/termin.i")
        set(_termin_csharp_bridge_sources
            ${CMAKE_CURRENT_SOURCE_DIR}/src/tc_component_csharp.cpp
            ${CMAKE_CURRENT_SOURCE_DIR}/src/tc_inspect_csharp.cpp
        )
    endif()

    set_source_files_properties(
        ${_termin_csharp_swig_interface}
        PROPERTIES
        CPLUSPLUS ON
        SWIG_USE_TARGET_INCLUDE_DIRECTORIES ON
        SWIG_FLAGS "${_termin_csharp_swig_flags}"
    )

    swig_add_library(termin_csharp_native
        TYPE SHARED
        LANGUAGE csharp
        SOURCES
            ${_termin_csharp_swig_interface}
            ${_termin_csharp_bridge_sources}
    )
    set_target_properties(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PROPERTIES
        OUTPUT_NAME "termin"
        # Per-config overrides bypass Visual Studio's default
        # "$(Configuration)" subfolder append. Without these the DLL
        # lands in runtimes/win-x64/native/Release/termin.dll — and
        # .NET's RID resolver expects it at runtimes/win-x64/native/,
        # so the process fails to load termin.dll at startup with
        # DllNotFoundException. Flatten the output path explicitly.
        LIBRARY_OUTPUT_DIRECTORY         "${TERMIN_CSHARP_RUNTIME_DIR}"
        LIBRARY_OUTPUT_DIRECTORY_DEBUG   "${TERMIN_CSHARP_RUNTIME_DIR}"
        LIBRARY_OUTPUT_DIRECTORY_RELEASE "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY         "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY_DEBUG   "${TERMIN_CSHARP_RUNTIME_DIR}"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${TERMIN_CSHARP_RUNTIME_DIR}"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/lib"
    )

    target_include_directories(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    target_compile_definitions(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE TCBASE_EXPORTS TC_EXPORTS)
    if(TERMIN_CSHARP_ENABLE_OPENGL)
        target_compile_definitions(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE TERMIN_CSHARP_ENABLE_OPENGL)
    endif()

    if(TERMIN_CSHARP_PROFILE STREQUAL "plot-d3d11")
        target_link_libraries(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE
            tcbase::termin_base
            tmesh::termin_mesh
            tgfx::termin_graphics
            tgfx::termin_graphics2
            tcplot::tcplot
        )
    else()
        target_link_libraries(${SWIG_MODULE_termin_csharp_native_REAL_NAME} PRIVATE
            tcbase::termin_base
            tgfx::termin_graphics
            termin_bootstrap::termin_bootstrap
            termin_engine::termin_engine
            termin_scene::termin_scene
            termin_collision::termin_collision
            termin_components_collision::termin_components_collision
            termin_components_kinematic::termin_components_kinematic
            termin_render::termin_render
            termin_render_passes::termin_render_passes
            tcplot::tcplot
        )
    endif()
    # This list MUST cover every transitive DLL that ends up in
    # termin.dll's PE import table. Missing entries silently go to
    # Windows loader's default search path (PATH, System32, …) and
    # pick up whatever stale copy happens to be around — classic
    # ABI-mismatch source. To verify: dumpbin /DEPENDENTS termin.dll
    # after a build and diff against the files in runtimes/win-x64/native/.
    if(TERMIN_CSHARP_PROFILE STREQUAL "plot-d3d11")
        set(_termin_csharp_runtime_targets
            tcbase::termin_base
            tmesh::termin_mesh
            tgfx::termin_graphics
            tgfx::termin_graphics2
            tcplot::tcplot
        )
    else()
        set(_termin_csharp_runtime_targets
            tcbase::termin_base
            termin_bootstrap::termin_bootstrap
            termin_inspect::termin_inspect
            termin_scene::termin_scene
            termin_input::termin_input
            termin_collision::termin_collision
            termin_components_collision::termin_components_collision
            termin_components_mesh::termin_components_mesh
            termin_components_kinematic::termin_components_kinematic
            termin_components_skeleton::termin_components_skeleton
            termin_components_render::termin_components_render
            termin_components_foliage::termin_components_foliage
            termin_engine::termin_engine
            termin_display::termin_display
            termin_animation::termin_animation
            termin_skeleton::termin_skeleton
            termin_render::termin_render
            termin_render_passes::termin_render_passes
            tgfx::termin_graphics
            tgfx::termin_graphics2
            termin_materials::termin_materials
            termin_modules::termin_modules
            tmesh::termin_mesh
            tcplot::tcplot
        )
    endif()
    foreach(_dep IN LISTS _termin_csharp_runtime_targets)
        add_custom_command(TARGET ${SWIG_MODULE_termin_csharp_native_REAL_NAME} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:${_dep}>
                "${TERMIN_CSHARP_RUNTIME_DIR}/"
            VERBATIM
        )
    endforeach()

    set(_termin_csharp_share_dir "${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/share/termin")
    set(TERMIN_CSHARP_SDK_SHARE_DIR "" CACHE PATH
        "Installed SDK share/termin directory copied into Termin.Native")
    if(NOT TERMIN_CSHARP_SDK_SHARE_DIR)
        foreach(_prefix IN LISTS CMAKE_PREFIX_PATH)
            if(EXISTS "${_prefix}/share/termin")
                set(TERMIN_CSHARP_SDK_SHARE_DIR "${_prefix}/share/termin")
                break()
            endif()
        endforeach()
    endif()
    if(NOT TERMIN_CSHARP_SDK_SHARE_DIR AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/share/termin")
        set(TERMIN_CSHARP_SDK_SHARE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/share/termin")
    endif()
    if(NOT TERMIN_CSHARP_SDK_SHARE_DIR OR NOT EXISTS "${TERMIN_CSHARP_SDK_SHARE_DIR}/builtin_shaders/engine-shader-catalog.json")
        message(FATAL_ERROR
            "termin-csharp: SDK share/termin resources were not found. "
            "Build/install the C++ SDK first, or set TERMIN_CSHARP_SDK_SHARE_DIR.")
    endif()

    add_custom_command(TARGET ${SWIG_MODULE_termin_csharp_native_REAL_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory "${_termin_csharp_share_dir}"
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${TERMIN_CSHARP_SDK_SHARE_DIR}"
            "${_termin_csharp_share_dir}"
        VERBATIM
    )
endif()

if(TERMIN_CSHARP_BUILD_MANAGED)
    find_program(DOTNET_EXECUTABLE dotnet REQUIRED)

    # `dotnet build` без `-c` собирает csproj в Debug по умолчанию,
    # даже если cmake запущен с --config Release. AppsUIMonorepo-овский
    # update-sdk.ps1 ищет managed DLLs в bin/Release/ — если мы
    # не пробросим конфигурацию сюда, он молча находит старый Release-
    # билд или не находит вообще. Пробрасываем через $<CONFIG>.
    add_custom_target(termin_csharp_managed ALL
        COMMAND ${DOTNET_EXECUTABLE} build ${CMAKE_CURRENT_SOURCE_DIR}/Termin.Native/Termin.Native.csproj -c $<CONFIG> -p:TerminCsharpProfile=${TERMIN_CSHARP_PROFILE}
        COMMAND ${DOTNET_EXECUTABLE} build ${CMAKE_CURRENT_SOURCE_DIR}/Termin.Wpf/Termin.Wpf.csproj -c $<CONFIG> -p:TerminCsharpProfile=${TERMIN_CSHARP_PROFILE}
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        VERBATIM
    )

    if(TERMIN_CSHARP_BUILD_NATIVE)
        add_dependencies(termin_csharp_managed ${SWIG_MODULE_termin_csharp_native_REAL_NAME})
    endif()

    if(TERMIN_CSHARP_BUILD_TESTS AND TERMIN_CSHARP_PROFILE STREQUAL "plot-d3d11")
        message(STATUS "termin-csharp: Termin.Test is skipped for plot-d3d11 profile")
    elseif(TERMIN_CSHARP_BUILD_TESTS)
        add_custom_target(termin_csharp_tests ALL
            COMMAND ${DOTNET_EXECUTABLE} build ${CMAKE_CURRENT_SOURCE_DIR}/Termin.Test/Termin.Test.csproj -c $<CONFIG>
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            VERBATIM
        )
        add_dependencies(termin_csharp_tests termin_csharp_managed)
    endif()
endif()
