foreach(_required IN ITEMS ROOT_BINARY RUNTIME_DIR SDK_BIN_DIR)
    if(NOT DEFINED ${_required} OR "${${_required}}" STREQUAL "")
        message(FATAL_ERROR "CopyWindowsRuntimeClosure.cmake requires ${_required}")
    endif()
endforeach()

file(GET_RUNTIME_DEPENDENCIES
    LIBRARIES "${ROOT_BINARY}"
    DIRECTORIES "${RUNTIME_DIR}" "${SDK_BIN_DIR}"
    RESOLVED_DEPENDENCIES_VAR _resolved_dependencies
    UNRESOLVED_DEPENDENCIES_VAR _unresolved_dependencies
    PRE_EXCLUDE_REGEXES
        "^api-ms-"
        "^ext-ms-"
        "^AzureAttestManager\\.dll$"
        "^AzureAttestNormal\\.dll$"
        "^HvsiFileTrust\\.dll$"
        "^PdmUtilities\\.dll$"
        "^wpaxholder\\.dll$"
    POST_EXCLUDE_REGEXES
        "[/\\\\]Windows[/\\\\]System32[/\\\\]"
        "[/\\\\]Windows[/\\\\]SysWOW64[/\\\\]"
)

set(_allowed_unresolved_windows_components
    azureattestmanager.dll
    azureattestnormal.dll
    hvsifiletrust.dll
    pdmutilities.dll
    wpaxholder.dll
)
set(_unexpected_unresolved_dependencies)
foreach(_dependency IN LISTS _unresolved_dependencies)
    string(TOLOWER "${_dependency}" _dependency_lower)
    if(NOT _dependency_lower IN_LIST _allowed_unresolved_windows_components)
        list(APPEND _unexpected_unresolved_dependencies "${_dependency}")
    endif()
endforeach()
if(_unexpected_unresolved_dependencies)
    list(JOIN _unexpected_unresolved_dependencies ", " _unresolved_text)
    message(FATAL_ERROR
        "Unresolved non-system dependencies for ${ROOT_BINARY}: ${_unresolved_text}")
endif()

cmake_path(NORMAL_PATH RUNTIME_DIR OUTPUT_VARIABLE _runtime_dir_normalized)
cmake_path(NORMAL_PATH SDK_BIN_DIR OUTPUT_VARIABLE _sdk_bin_dir_normalized)
foreach(_dependency IN LISTS _resolved_dependencies)
    cmake_path(GET _dependency PARENT_PATH _dependency_dir)
    cmake_path(NORMAL_PATH _dependency_dir OUTPUT_VARIABLE _dependency_dir_normalized)
    cmake_path(IS_PREFIX _sdk_bin_dir_normalized "${_dependency}" NORMALIZE _from_sdk)
    if(_from_sdk AND NOT _dependency_dir_normalized STREQUAL _runtime_dir_normalized)
        file(COPY "${_dependency}" DESTINATION "${RUNTIME_DIR}")
    endif()
endforeach()

# The installed termin_bootstrap target cannot expose its private Python link
# through the exported CMake graph. Keep the Python ABI DLLs version-agnostic
# and copy them only for profiles that actually contain bootstrap.
if(EXISTS "${RUNTIME_DIR}/termin_bootstrap.dll")
    file(GLOB _python_runtime_dlls "${SDK_BIN_DIR}/python*t.dll")
    if(NOT _python_runtime_dlls)
        message(FATAL_ERROR
            "termin_bootstrap.dll is present, but no python*t.dll runtime was found in ${SDK_BIN_DIR}")
    endif()
    file(COPY ${_python_runtime_dlls} DESTINATION "${RUNTIME_DIR}")
endif()
