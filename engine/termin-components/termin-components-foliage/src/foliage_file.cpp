#include <termin/foliage/foliage_file.hpp>

#include "foliage_bounds_internal.hpp"

#include <array>
#include <cstddef>
#include <cstring>
#include <fstream>
#include <limits>
#include <new>
#include <stdexcept>

#include <tcbase/tc_log.h>

namespace termin {
    namespace {

        constexpr std::array<char, 8> FOLIAGE_MAGIC = {'T', 'F', 'O', 'L', 'I', 'A', 'G', 'E'};
        constexpr uint32_t FOLIAGE_FORMAT_VERSION = 1;
        constexpr uint32_t FOLIAGE_HEADER_SIZE = 96;
        constexpr uint32_t FOLIAGE_INSTANCE_STRIDE = 40;
        constexpr uint32_t FOLIAGE_COORDINATE_SPACE_LOCAL = 1;

        struct FoliageFileHeader {
        public:
            char magic[8] = {};
            uint32_t version = FOLIAGE_FORMAT_VERSION;
            uint32_t header_size = FOLIAGE_HEADER_SIZE;
            uint32_t instance_stride = FOLIAGE_INSTANCE_STRIDE;
            uint32_t flags = 0;
            uint32_t coordinate_space = FOLIAGE_COORDINATE_SPACE_LOCAL;
            uint32_t reserved0 = 0;
            uint64_t instance_count = 0;
            // Stable .tfoliage v1 byte layout; keep these as raw packed file fields.
            float bounds_min[3] = {0.0f, 0.0f, 0.0f};
            float bounds_max[3] = {0.0f, 0.0f, 0.0f};
            uint8_t reserved[32] = {};
        };

        static_assert(sizeof(FoliageInstance) == FOLIAGE_INSTANCE_STRIDE);
        static_assert(sizeof(FoliageFileHeader) == FOLIAGE_HEADER_SIZE);
        static_assert(offsetof(FoliageFileHeader, instance_count) == 32);
        static_assert(offsetof(FoliageFileHeader, bounds_min) == 40);
        static_assert(offsetof(FoliageFileHeader, bounds_max) == 52);

        bool host_is_little_endian() {
            const uint16_t value = 1;
            return *reinterpret_cast<const uint8_t*>(&value) == 1;
        }

        FoliageFileResult fail_result(const std::string& message) {
            tc_log_error("[FoliageFile] %s", message.c_str());
            return FoliageFileResult{false, message};
        }

        bool read_exact(std::ifstream& in, void* data, std::streamsize size) {
            in.read(static_cast<char*>(data), size);
            return in.good() || (in.eof() && in.gcount() == size);
        }

        bool write_exact(std::ofstream& out, const void* data, std::streamsize size) {
            out.write(static_cast<const char*>(data), size);
            return out.good();
        }

    } // namespace

    FoliageFileResult load_foliage_file(const std::filesystem::path& path, FoliageData& out) {
        if (!host_is_little_endian()) {
            return fail_result("big-endian hosts are not supported by .tfoliage v1");
        }

        std::ifstream in(path, std::ios::binary);
        if (!in) {
            return fail_result("failed to open foliage file: " + path.string());
        }

        FoliageFileHeader header;
        if (!read_exact(in, &header, static_cast<std::streamsize>(sizeof(header)))) {
            return fail_result("failed to read foliage header: " + path.string());
        }

        if (std::memcmp(header.magic, FOLIAGE_MAGIC.data(), FOLIAGE_MAGIC.size()) != 0) {
            return fail_result("invalid foliage file magic: " + path.string());
        }
        if (header.version != FOLIAGE_FORMAT_VERSION) {
            return fail_result("unsupported foliage file version: " + std::to_string(header.version));
        }
        if (header.header_size < sizeof(FoliageFileHeader)) {
            return fail_result("invalid foliage header size: " + std::to_string(header.header_size));
        }
        if (header.instance_stride != FOLIAGE_INSTANCE_STRIDE) {
            return fail_result("unsupported foliage instance stride: " + std::to_string(header.instance_stride));
        }
        if (header.coordinate_space != FOLIAGE_COORDINATE_SPACE_LOCAL) {
            return fail_result("unsupported foliage coordinate space: " + std::to_string(header.coordinate_space));
        }
        if (header.instance_count > static_cast<uint64_t>(std::numeric_limits<size_t>::max())) {
            return fail_result("foliage instance count does not fit size_t: " + std::to_string(header.instance_count));
        }
        if (header.instance_count > std::numeric_limits<uint64_t>::max() / FOLIAGE_INSTANCE_STRIDE) {
            return fail_result("foliage instance byte count overflows uint64: " + std::to_string(header.instance_count));
        }

        const uint64_t byte_count = header.instance_count * FOLIAGE_INSTANCE_STRIDE;
        if (byte_count > static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())) {
            return fail_result("foliage instance block is too large: " + path.string());
        }

        in.seekg(0, std::ios::end);
        const std::streampos end_position = in.tellg();
        if (end_position == std::streampos{-1}) {
            return fail_result("failed to determine foliage file size: " + path.string());
        }
        const auto end_offset = static_cast<std::streamoff>(end_position);
        if (end_offset < 0) {
            return fail_result("invalid foliage file size: " + path.string());
        }
        const uint64_t file_size = static_cast<uint64_t>(end_offset);
        const uint64_t payload_offset = header.header_size;
        if (payload_offset > file_size || byte_count > file_size - payload_offset) {
            return fail_result("foliage instance block is truncated: " + path.string());
        }
        if (payload_offset > static_cast<uint64_t>(std::numeric_limits<std::streamoff>::max())) {
            return fail_result("foliage header offset is too large: " + path.string());
        }
        in.seekg(static_cast<std::streamoff>(payload_offset), std::ios::beg);
        if (!in.good()) {
            return fail_result("failed to seek to foliage instances: " + path.string());
        }

        const AABBf serialized_bounds{
            {header.bounds_min[0], header.bounds_min[1], header.bounds_min[2]},
            {header.bounds_max[0], header.bounds_max[1], header.bounds_max[2]},
        };
        if (!serialized_bounds.is_valid()) {
            return fail_result("foliage header contains invalid bounds: " + path.string());
        }

        std::vector<FoliageInstance> instances;
        if (header.instance_count > static_cast<uint64_t>(instances.max_size())) {
            return fail_result("foliage instance count exceeds container capacity: " +
                               std::to_string(header.instance_count));
        }
        try {
            instances.resize(static_cast<size_t>(header.instance_count));
        } catch (const std::length_error&) {
            return fail_result("foliage instance count exceeds container capacity: " +
                               std::to_string(header.instance_count));
        } catch (const std::bad_alloc&) {
            return fail_result("failed to allocate foliage instance block: " + path.string());
        }
        if (byte_count > 0) {
            if (!read_exact(in, instances.data(), static_cast<std::streamsize>(byte_count))) {
                return fail_result("failed to read foliage instances: " + path.string());
            }
        }

        const foliage_detail::BoundsComputation computed = foliage_detail::compute_bounds(instances);
        if (!computed.valid) {
            return fail_result("foliage instance " + std::to_string(computed.invalid_instance) +
                               " contains non-finite geometry: " + path.string());
        }
        if (computed.has_bounds != (header.instance_count > 0)) {
            return fail_result("foliage instance count and computed bounds state disagree: " + path.string());
        }
        if (computed.has_bounds) {
            if (!foliage_detail::bounds_equal(serialized_bounds, computed.bounds)) {
                return fail_result("foliage header bounds do not match instance geometry: " + path.string());
            }
        } else if (!foliage_detail::bounds_equal(serialized_bounds, AABBf{})) {
            return fail_result("empty foliage file must encode zero bounds: " + path.string());
        }

        out.instances = std::move(instances);
        out.local_bounds = computed.bounds;
        out.has_local_bounds = computed.has_bounds;
        out.source_path = path.string();
        out.loaded = true;
        ++out.version;
        return FoliageFileResult{true, "ok"};
    }

    FoliageFileResult save_foliage_file(const std::filesystem::path& path, const FoliageData& data) {
        if (!host_is_little_endian()) {
            return fail_result("big-endian hosts are not supported by .tfoliage v1");
        }

        const foliage_detail::BoundsComputation computed = foliage_detail::compute_bounds(data.instances);
        if (!computed.valid) {
            return fail_result("cannot save non-finite foliage instance " + std::to_string(computed.invalid_instance));
        }
        if (data.has_local_bounds != computed.has_bounds) {
            return fail_result("foliage bounds state does not match instance count");
        }
        if (computed.has_bounds &&
            (!data.local_bounds.is_valid() || !foliage_detail::bounds_equal(data.local_bounds, computed.bounds))) {
            return fail_result("foliage bounds do not match instance geometry");
        }
        if (data.instances.size() > std::numeric_limits<uint64_t>::max() / FOLIAGE_INSTANCE_STRIDE) {
            return fail_result("foliage instance byte count overflows uint64");
        }

        FoliageFileHeader header;
        std::memcpy(header.magic, FOLIAGE_MAGIC.data(), FOLIAGE_MAGIC.size());
        header.instance_count = static_cast<uint64_t>(data.instances.size());
        if (computed.has_bounds) {
            header.bounds_min[0] = computed.bounds.min_point.x;
            header.bounds_min[1] = computed.bounds.min_point.y;
            header.bounds_min[2] = computed.bounds.min_point.z;
            header.bounds_max[0] = computed.bounds.max_point.x;
            header.bounds_max[1] = computed.bounds.max_point.y;
            header.bounds_max[2] = computed.bounds.max_point.z;
        }

        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) {
            return fail_result("failed to open foliage file for writing: " + path.string());
        }
        if (!write_exact(out, &header, static_cast<std::streamsize>(sizeof(header)))) {
            return fail_result("failed to write foliage header: " + path.string());
        }
        if (!data.instances.empty()) {
            const uint64_t byte_count = static_cast<uint64_t>(data.instances.size()) * FOLIAGE_INSTANCE_STRIDE;
            if (byte_count > static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())) {
                return fail_result("foliage instance block is too large: " + path.string());
            }
            if (!write_exact(out, data.instances.data(), static_cast<std::streamsize>(byte_count))) {
                return fail_result("failed to write foliage instances: " + path.string());
            }
        }
        return FoliageFileResult{true, "ok"};
    }

} // namespace termin
