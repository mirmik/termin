#pragma once

#include "core/tc_archetype.h"
#include "core/tc_entity_pool.h"
#include "tc_hash_map.h"

#include <tcbase/tc_types.h>

typedef tc_vec3 Vec3;
typedef tc_quat Quat;

typedef struct {
    Vec3 position;
    Quat rotation;
    Vec3 scale;
} Pose3;

typedef struct {
    tc_entity_id* items;
    size_t count;
    size_t capacity;
} EntityIdArray;

typedef struct {
    tc_component** items;
    size_t count;
    size_t capacity;
} ComponentArray;

typedef struct {
    const char** items;
    size_t count;
    size_t capacity;
} StringArray;

struct tc_entity_pool {
    size_t capacity;
    size_t count;
    uint64_t next_runtime_id;

    uint32_t* free_stack;
    size_t free_count;

    uint32_t* generations;
    bool* alive;

    bool* visible;
    bool* enabled;
    bool* pickable;
    bool* selectable;
    bool* transform_dirty;
    uint32_t* version_for_walking_to_proximal;
    uint32_t* version_for_walking_to_distal;
    uint32_t* version_only_my;
    int* priorities;
    uint64_t* layers;
    uint64_t* entity_flags;
    uint32_t* pick_ids;
    uint32_t next_pick_id;

    Vec3* local_positions;
    Quat* local_rotations;
    Vec3* local_scales;
    Vec3* world_positions;
    Quat* world_rotations;
    Vec3* world_scales;
    double* world_matrices;

    char** names;
    char** uuids;
    uint64_t* runtime_ids;

    tc_entity_id* parent_ids;
    EntityIdArray roots;
    EntityIdArray* children;

    ComponentArray* components;

    tc_str_map* by_uuid;
    tc_u32_map* by_pick_id;

    tc_scene_handle scene;

    tc_archetype** archetypes;
    size_t archetype_count;
    size_t archetype_capacity;
    tc_u64_map* archetype_by_mask;
    uint32_t* soa_archetype_ids;
    uint32_t* soa_archetype_rows;
    uint64_t* soa_type_masks;
};
