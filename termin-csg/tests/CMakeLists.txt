add_executable(termin_csg_basic_test
    csg_basic_test.cpp
)

target_include_directories(termin_csg_basic_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../termin-thirdparty/guard
)

target_link_libraries(termin_csg_basic_test PRIVATE
    tcsg::termin_csg
)

add_test(NAME termin_csg_basic_test COMMAND termin_csg_basic_test)

termin_label_tests_in_directory("termin-csg")
