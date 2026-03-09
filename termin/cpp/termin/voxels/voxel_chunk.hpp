#pragma once

#include <array>
#include <cstdint>
#include <vector>
#include <tuple>

namespace termin {
namespace voxels {

constexpr int CHUNK_SIZE = 16;
constexpr int CHUNK_VOLUME = CHUNK_SIZE * CHUNK_SIZE * CHUNK_SIZE;

// Voxel types
constexpr uint8_t VOXEL_EMPTY = 0;
constexpr uint8_t VOXEL_SOLID = 1;
constexpr uint8_t VOXEL_SURFACE = 2;

class VoxelChunk {
public:
    VoxelChunk() : data_{}, non_empty_count_(0) {
        data_.fill(VOXEL_EMPTY);
    }

    inline int index(int x, int y, int z) const {
        return x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE;
    }

    inline uint8_t get(int x, int y, int z) const {
        return data_[index(x, y, z)];
    }

    inline void set(int x, int y, int z, uint8_t value) {
        int idx = index(x, y, z);
        uint8_t old_value = data_[idx];

        if (old_value == VOXEL_EMPTY && value != VOXEL_EMPTY) {
            non_empty_count_++;
        } else if (old_value != VOXEL_EMPTY && value == VOXEL_EMPTY) {
            non_empty_count_--;
        }

        data_[idx] = value;
    }

    inline bool is_empty() const {
        return non_empty_count_ == 0;
    }

    inline int non_empty_count() const {
        return non_empty_count_;
    }

    inline void fill(uint8_t value) {
        data_.fill(value);
        non_empty_count_ = (value != VOXEL_EMPTY) ? CHUNK_VOLUME : 0;
    }

    inline void clear() {
        fill(VOXEL_EMPTY);
    }

    // Iterator over non-empty voxels: returns (local_x, local_y, local_z, type)
    std::vector<std::tuple<int, int, int, uint8_t>> iter_non_empty() const {
        std::vector<std::tuple<int, int, int, uint8_t>> result;
        result.reserve(non_empty_count_);

        for (int z = 0; z < CHUNK_SIZE; z++) {
            for (int y = 0; y < CHUNK_SIZE; y++) {
                for (int x = 0; x < CHUNK_SIZE; x++) {
                    uint8_t v = get(x, y, z);
                    if (v != VOXEL_EMPTY) {
                        result.emplace_back(x, y, z, v);
                    }
                }
            }
        }
        return result;
    }

    const std::array<uint8_t, CHUNK_VOLUME>& data() const { return data_; }

private:
    std::array<uint8_t, CHUNK_VOLUME> data_;
    int non_empty_count_;
};

} // namespace voxels
} // namespace termin
