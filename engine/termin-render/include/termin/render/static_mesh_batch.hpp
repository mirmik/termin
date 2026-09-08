#pragma once
#include <cstdint>
#include <memory>
#include <termin/render/render_export.hpp>
#include <termin/render/render_item_collection.hpp>
extern "C" {
#include <core/tc_scene_pool.h>
}
namespace termin {
    struct StaticMeshBatchStats {
        uint64_t input_geometry = 0;
        uint64_t eligible_geometry = 0;
        uint64_t merged_geometry = 0;
        uint64_t output_batches = 0;
        uint64_t rebuilt_batches = 0;
        uint64_t reused_batches = 0;
        uint64_t unsupported_geometry = 0;
    };
    // Scene-adapter owned cache. Never holds component pointers across publications.
    // Rebuilt meshes are retained by each immutable snapshot that references them.
    class RENDER_API StaticMeshBatchCache {
    public:
        StaticMeshBatchCache();
        ~StaticMeshBatchCache();
        StaticMeshBatchCache(const StaticMeshBatchCache&) = delete;
        StaticMeshBatchCache& operator=(const StaticMeshBatchCache&) = delete;
        bool apply(RenderItemCollection& items,
                   tc_scene_handle scene,
                   uint64_t layer_mask,
                   uint64_t category_mask,
                   int filter_flags = 0);
        void clear_scene(tc_scene_handle scene);
        void clear();
        const StaticMeshBatchStats& stats() const;

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };
} // namespace termin
