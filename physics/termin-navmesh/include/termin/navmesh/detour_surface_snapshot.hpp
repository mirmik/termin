#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include <termin/geom/vec3.hpp>

namespace termin {

    // Directed adjacency. Coordinates are Termin coordinates in the bake frame.
    // Typed links may have different source and destination attachment points.
    struct DetourSurfaceLink {
        unsigned long long poly_ref = 0;
        Vec3f left{}, right{};
        Vec3f target_left{}, target_right{};
        unsigned char edge = 0xff;
    };

    struct DetourSurfacePolygon {
        unsigned long long poly_ref = 0;
        unsigned char poly_type = 0;
        unsigned char area = 0;
        unsigned int user_id = 0;
        unsigned short flags = 0;
        std::vector<Vec3f> vertices;
        // Ground polygons retain their actual detail surface, including interior vertices.
        std::vector<std::array<Vec3f, 3>> detail_triangles;
        std::vector<DetourSurfaceLink> links;
    };

    struct DetourSurfaceSnapshot {
        std::uint64_t generation = 0;
        float walkable_climb = 0;
        std::vector<DetourSurfacePolygon> polygons;
    };

} // namespace termin
