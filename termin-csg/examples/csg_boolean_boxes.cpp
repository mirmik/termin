#include <iostream>

#include <termin/csg/csg.hpp>

int main() {
    termin::csg::Solid wall = termin::csg::make_box(8.0, 0.4, 3.0);
    termin::csg::Solid doorway = termin::csg::make_box(1.5, 0.8, 2.2).translated(0.0, 0.0, -0.4);
    termin::csg::Solid wall_with_door = termin::csg::subtract(wall, doorway);

    termin::Mesh3 mesh = termin::csg::to_mesh3(wall_with_door, "wall_with_door");

    std::cout << "status=" << wall_with_door.status_string()
              << " vertices=" << mesh.vertex_count()
              << " triangles=" << mesh.triangle_count()
              << " volume=" << wall_with_door.volume()
              << "\n";

    return mesh.is_valid() ? 0 : 1;
}
