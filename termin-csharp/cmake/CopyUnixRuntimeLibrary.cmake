if(NOT DEFINED SOURCE_FILE OR
   NOT DEFINED SONAME_FILE OR
   NOT DEFINED LINKER_FILE OR
   NOT DEFINED DESTINATION_DIR)
    message(FATAL_ERROR "CopyUnixRuntimeLibrary.cmake requires all paths")
endif()

file(MAKE_DIRECTORY "${DESTINATION_DIR}")
get_filename_component(_source_name "${SOURCE_FILE}" NAME)
set(_destination "${DESTINATION_DIR}/${_source_name}")
file(COPY_FILE "${SOURCE_FILE}" "${_destination}" ONLY_IF_DIFFERENT)

foreach(_alias_file IN ITEMS "${SONAME_FILE}" "${LINKER_FILE}")
    get_filename_component(_alias_name "${_alias_file}" NAME)
    if(NOT _alias_name STREQUAL _source_name)
        set(_alias_path "${DESTINATION_DIR}/${_alias_name}")
        file(REMOVE "${_alias_path}")
        file(CREATE_LINK "${_source_name}" "${_alias_path}" SYMBOLIC)
    endif()
endforeach()

# Imported SDK targets may expose their real file as TARGET_LINKER_FILE even
# when the installed SDK also contains the conventional unversioned linker
# name. Preserve that name explicitly because .NET maps DllImport("foo") to
# libfoo.so on Linux.
if(_source_name MATCHES "^(.+\\.so)\\.")
    set(_linker_name "${CMAKE_MATCH_1}")
    set(_linker_path "${DESTINATION_DIR}/${_linker_name}")
    file(REMOVE "${_linker_path}")
    file(CREATE_LINK "${_source_name}" "${_linker_path}" SYMBOLIC)
endif()
