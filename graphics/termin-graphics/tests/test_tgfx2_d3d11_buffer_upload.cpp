#include "tgfx2/d3d11/internal/dynamic_buffer_upload.hpp"

#include <array>
#include <cstdint>
#include <cstdio>
#include <span>

namespace {

    struct FakeMap {
        std::array<uint8_t, 12> storage{};
        bool acquire = true;
        bool return_null = false;
        int map_calls = 0;
        int unmap_calls = 0;
    };

    tgfx::d3d11_internal::DiscardMapResult map_discard(void* user) {
        auto& map = *static_cast<FakeMap*>(user);
        ++map.map_calls;
        return {map.return_null ? nullptr : map.storage.data(), map.acquire};
    }

    void unmap(void* user) {
        ++static_cast<FakeMap*>(user)->unmap_calls;
    }

    tgfx::d3d11_internal::DiscardMapOps ops(FakeMap& map) {
        return {&map, map_discard, unmap};
    }

#define CHECK(condition)                                                                                               \
    do {                                                                                                               \
        if (!(condition)) {                                                                                            \
            std::fprintf(stderr, "CHECK failed at %s:%d: %s\n", __FILE__, __LINE__, #condition);                       \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (false)

} // namespace

int main() {
    using tgfx::d3d11_internal::DiscardUploadResult;
    using tgfx::d3d11_internal::upload_discard_preserving;

    std::array<uint8_t, 12> shadow{};
    const std::array<uint8_t, 12> original{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
    FakeMap initial_map;
    initial_map.storage.fill(0xff);
    CHECK(upload_discard_preserving(shadow, original, 0, ops(initial_map)) == DiscardUploadResult::Success);
    CHECK(shadow == original);
    CHECK(initial_map.storage == original);

    FakeMap middle_map;
    middle_map.storage.fill(0xee);
    const std::array<uint8_t, 3> middle_patch{40, 41, 42};
    CHECK(upload_discard_preserving(shadow, middle_patch, 4, ops(middle_map)) == DiscardUploadResult::Success);
    const std::array<uint8_t, 12> after_middle{0, 1, 2, 3, 40, 41, 42, 7, 8, 9, 10, 11};
    CHECK(shadow == after_middle);
    CHECK(middle_map.storage == after_middle);
    CHECK(initial_map.storage == original);
    CHECK(middle_map.map_calls == 1);
    CHECK(middle_map.unmap_calls == 1);

    // A second discard represents a newly renamed backing allocation.  It
    // receives the whole logical buffer, while the previous in-flight bytes
    // remain untouched.
    const auto in_flight_storage = middle_map.storage;
    FakeMap prefix_map;
    prefix_map.storage.fill(0xdd);
    const std::array<uint8_t, 2> prefix_patch{90, 91};
    CHECK(upload_discard_preserving(shadow, prefix_patch, 0, ops(prefix_map)) == DiscardUploadResult::Success);
    const std::array<uint8_t, 12> after_prefix{90, 91, 2, 3, 40, 41, 42, 7, 8, 9, 10, 11};
    CHECK(shadow == after_prefix);
    CHECK(prefix_map.storage == after_prefix);
    CHECK(middle_map.storage == in_flight_storage);

    FakeMap failed_map;
    failed_map.acquire = false;
    const auto before_failed_map = shadow;
    CHECK(upload_discard_preserving(shadow, prefix_patch, 6, ops(failed_map)) == DiscardUploadResult::MapFailed);
    CHECK(shadow == before_failed_map);
    CHECK(failed_map.map_calls == 1);
    CHECK(failed_map.unmap_calls == 0);

    FakeMap null_map;
    null_map.return_null = true;
    CHECK(upload_discard_preserving(shadow, prefix_patch, 6, ops(null_map)) == DiscardUploadResult::NullMappedData);
    CHECK(shadow == before_failed_map);
    CHECK(null_map.map_calls == 1);
    CHECK(null_map.unmap_calls == 1);

    FakeMap invalid_range_map;
    CHECK(upload_discard_preserving(shadow, prefix_patch, shadow.size() - 1, ops(invalid_range_map)) ==
          DiscardUploadResult::InvalidRange);
    CHECK(shadow == before_failed_map);
    CHECK(invalid_range_map.map_calls == 0);
    CHECK(invalid_range_map.unmap_calls == 0);

    CHECK(original != shadow);
    std::puts("D3D11 discard upload preservation contract passed");
    return 0;
}
