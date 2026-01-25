// collision_world_c.cpp - C API implementation for CollisionWorld
#include "collision_world_c.hpp"
#include "collision_world.hpp"

using termin::collision::CollisionWorld;

extern "C" {

void* tc_collision_world_create(void) {
    return new CollisionWorld();
}

void tc_collision_world_destroy(void* cw) {
    delete static_cast<CollisionWorld*>(cw);
}

int tc_collision_world_size(void* cw) {
    if (!cw) return 0;
    return static_cast<int>(static_cast<CollisionWorld*>(cw)->size());
}

}
