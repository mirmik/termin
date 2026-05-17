add_executable(termin_csg_basic_test
    csg_basic_test.cpp
)

target_link_libraries(termin_csg_basic_test PRIVATE
    tcsg::termin_csg
)

add_test(NAME termin_csg_basic_test COMMAND termin_csg_basic_test)
