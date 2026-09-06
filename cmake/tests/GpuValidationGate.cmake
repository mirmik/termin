# Exercise the real CTest policy against native Vulkan errors, without leaking
# the intentional negative cases into the outer test's diagnostics. All inner
# output remains available in the per-case LastTest.log and ctest.log files.
file(MAKE_DIRECTORY "${TEST_ROOT}/source" "${TEST_ROOT}/empty-layers")
file(WRITE "${TEST_ROOT}/source/CMakeLists.txt" [=[
cmake_minimum_required(VERSION 3.19)
project(GpuValidationGate NONE)
enable_testing()
include("${METADATA}")
add_test(NAME probe COMMAND "${PROBE}" "${MODE}")
set_tests_properties(probe PROPERTIES
    SKIP_REGULAR_EXPRESSION "skipping"
    TIMEOUT 20)
termin_add_test_labels(probe "termin:capability:vulkan")
termin_require_gpu_validation(probe)
if(MODE STREQUAL "missing-layer")
    set_property(TEST probe APPEND PROPERTY ENVIRONMENT
        "VK_LAYER_PATH=${EMPTY_LAYERS}"
        "VK_ADD_LAYER_PATH="
        "VK_INSTANCE_LAYERS=")
endif()
]=])

foreach(_mode IN ITEMS clean invalid shutdown init missing-layer)
    set(_build "${TEST_ROOT}/${_mode}")
    execute_process(COMMAND "${CMAKE_COMMAND}"
        -S "${TEST_ROOT}/source" -B "${_build}"
        "-DMETADATA=${METADATA}" "-DPROBE=${PROBE}" "-DMODE=${_mode}"
        "-DEMPTY_LAYERS=${TEST_ROOT}/empty-layers"
        RESULT_VARIABLE _configured OUTPUT_VARIABLE _out ERROR_VARIABLE _err)
    if(NOT _configured EQUAL 0)
        message(FATAL_ERROR "Gate fixture configure failed: ${_out}${_err}")
    endif()
    execute_process(COMMAND "${CTEST}" --test-dir "${_build}" --output-on-failure -V
        RESULT_VARIABLE _result OUTPUT_VARIABLE _out ERROR_VARIABLE _err)
    file(WRITE "${_build}/ctest.log" "${_out}${_err}")
    if(_mode STREQUAL "clean")
        if(NOT _result EQUAL 0 OR NOT _out MATCHES "Vulkan validation.*errors=0")
            message(FATAL_ERROR "Clean validation fixture failed; see ${_build}/ctest.log")
        endif()
    elseif(_result EQUAL 0 OR NOT _out MATCHES "Error regular expression found"
           OR NOT _out MATCHES "probe returning zero"
           OR NOT _out MATCHES "\\[GPU validation error\\]")
        message(FATAL_ERROR "Gate did not reject ${_mode}; see ${_build}/ctest.log")
    endif()
    message(STATUS "GPU gate ${_mode}: expected result verified")
endforeach()
