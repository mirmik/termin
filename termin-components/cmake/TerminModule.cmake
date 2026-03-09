include(CMakeParseArguments)
include(GNUInstallDirs)

function(termin_add_module)
    cmake_parse_arguments(TAM "" "NAME;NAMESPACE" "SOURCES;PUBLIC_DEPS;FIND_DEPS;INSTALL_HEADERS" ${ARGN})

    if(NOT TAM_NAME)
        message(FATAL_ERROR "termin_add_module: NAME is required")
    endif()
    if(NOT TAM_SOURCES)
        message(FATAL_ERROR "termin_add_module: SOURCES are required")
    endif()

    if(NOT TAM_NAMESPACE)
        set(TAM_NAMESPACE "${TAM_NAME}::")
    endif()

    set(_export_name "${TAM_NAME}Targets")
    set(_cmake_install_dir "${CMAKE_INSTALL_LIBDIR}/cmake/${TAM_NAME}")
    set(_config_path "${CMAKE_CURRENT_BINARY_DIR}/${TAM_NAME}Config.cmake")

    add_library(${TAM_NAME} SHARED ${TAM_SOURCES})
    target_include_directories(${TAM_NAME} PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
        $<INSTALL_INTERFACE:include>
    )

    if(TAM_PUBLIC_DEPS)
        target_link_libraries(${TAM_NAME} PUBLIC ${TAM_PUBLIC_DEPS})
    endif()

    install(TARGETS ${TAM_NAME}
        EXPORT ${_export_name}
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_LIBDIR}
    )

    foreach(_hdr_dir IN LISTS TAM_INSTALL_HEADERS)
        install(DIRECTORY ${_hdr_dir} DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
    endforeach()

    install(EXPORT ${_export_name}
        FILE ${_export_name}.cmake
        NAMESPACE ${TAM_NAMESPACE}
        DESTINATION ${_cmake_install_dir}
    )

    set(_config_text "include(CMakeFindDependencyMacro)\n")
    foreach(_dep IN LISTS TAM_FIND_DEPS)
        string(APPEND _config_text "find_dependency(${_dep} REQUIRED)\n")
    endforeach()

    set(_cmake_current_list_dir_literal [[${CMAKE_CURRENT_LIST_DIR}]])
    string(APPEND _config_text "\ninclude(\"${_cmake_current_list_dir_literal}/${_export_name}.cmake\")\n")
    file(WRITE ${_config_path} "${_config_text}")

    install(FILES ${_config_path} DESTINATION ${_cmake_install_dir})
endfunction()
