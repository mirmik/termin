add_executable(termin_csg_boolean_boxes
    csg_boolean_boxes.cpp
)

target_link_libraries(termin_csg_boolean_boxes PRIVATE
    tcsg::termin_csg
)
