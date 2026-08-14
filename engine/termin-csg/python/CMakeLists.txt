find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_csg_native NB_SHARED
    bindings/csg_module.cpp
)

target_link_libraries(_csg_native PRIVATE termin_csg)
target_include_directories(_csg_native PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../include)

if(NOT WIN32)
    set_target_properties(_csg_native PROPERTIES
        BUILD_WITH_INSTALL_RPATH TRUE
        INSTALL_RPATH "$ORIGIN/../../lib"
    )
endif()

install(TARGETS _csg_native DESTINATION lib/python/termin/csg)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/termin/csg/
    DESTINATION lib/python/termin/csg
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    PATTERN "*.so" EXCLUDE
)
