#include <termin/foliage/foliage_file.hpp>

#include <array>
#include <cstring>
#include <fstream>
#include <limits>

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
    float bounds_min[3] = {0.0f, 0.0f, 0.0f};
    float bounds_max[3] = {0.0f, 0.0f, 0.0f};
    uint8_t reserved[32] = {};
};

static_assert(sizeof(FoliageInstance) == FOLIAGE_INSTANCE_STRIDE);
static_assert(sizeof(FoliageFileHeader) == FOLIAGE_HEADER_SIZE);

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

    std::vector<FoliageInstance> instances;
    instances.resize(static_cast<size_t>(header.instance_count));
    const uint64_t byte_count = header.instance_count * FOLIAGE_INSTANCE_STRIDE;
    if (byte_count > 0) {
        if (byte_count > static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())) {
            return fail_result("foliage instance block is too large: " + path.string());
        }
        if (!read_exact(in, instances.data(), static_cast<std::streamsize>(byte_count))) {
            return fail_result("failed to read foliage instances: " + path.string());
        }
    }

    out.instances = std::move(instances);
    out.local_bounds.min = {header.bounds_min[0], header.bounds_min[1], header.bounds_min[2]};
    out.local_bounds.max = {header.bounds_max[0], header.bounds_max[1], header.bounds_max[2]};
    out.local_bounds.valid = header.instance_count > 0;
    out.source_path = path.string();
    out.loaded = true;
    ++out.version;
    return FoliageFileResult{true, "ok"};
}

FoliageFileResult save_foliage_file(const std::filesystem::path& path, const FoliageData& data) {
    if (!host_is_little_endian()) {
        return fail_result("big-endian hosts are not supported by .tfoliage v1");
    }

    FoliageFileHeader header;
    std::memcpy(header.magic, FOLIAGE_MAGIC.data(), FOLIAGE_MAGIC.size());
    header.instance_count = static_cast<uint64_t>(data.instances.size());
    if (data.local_bounds.valid) {
        header.bounds_min[0] = data.local_bounds.min.x;
        header.bounds_min[1] = data.local_bounds.min.y;
        header.bounds_min[2] = data.local_bounds.min.z;
        header.bounds_max[0] = data.local_bounds.max.x;
        header.bounds_max[1] = data.local_bounds.max.y;
        header.bounds_max[2] = data.local_bounds.max.z;
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
