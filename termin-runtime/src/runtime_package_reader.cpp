#include <termin/runtime/runtime_package.hpp>

#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

#include <tcbase/trent/json.h>

namespace termin::runtime {
namespace {

constexpr std::array<std::uint8_t, 8> blob_magic{
    'T', 'R', 'P', 'K', 'G', '0', '1', '\n'};

std::string validate_path(std::string_view path) {
    if (path.empty()) {
        throw std::runtime_error("runtime package path must not be empty");
    }
    if (path.front() == '/' || path.find('\\') != std::string_view::npos ||
            path.find(':') != std::string_view::npos) {
        throw std::runtime_error(
            "runtime package path must be portable and relative: " + std::string(path));
    }
    std::size_t start = 0;
    while (start <= path.size()) {
        const std::size_t end = path.find('/', start);
        const std::string_view component = path.substr(
            start, end == std::string_view::npos ? path.size() - start : end - start);
        if (component.empty() || component == "." || component == "..") {
            throw std::runtime_error(
                "runtime package path must not contain empty or dot segments: " +
                std::string(path));
        }
        if (end == std::string_view::npos) break;
        start = end + 1;
    }
    return std::string(path);
}

bool contained(const std::filesystem::path& root, const std::filesystem::path& path) {
    auto root_it = root.begin();
    auto path_it = path.begin();
    for (; root_it != root.end(); ++root_it, ++path_it) {
        if (path_it == path.end() || *root_it != *path_it) return false;
    }
    return true;
}

std::uint32_t read_u32_le(const std::uint8_t* data) {
    return static_cast<std::uint32_t>(data[0]) |
        (static_cast<std::uint32_t>(data[1]) << 8) |
        (static_cast<std::uint32_t>(data[2]) << 16) |
        (static_cast<std::uint32_t>(data[3]) << 24);
}

constexpr std::array<std::uint32_t, 64> sha256_k{
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

void sha256_transform(
    std::array<std::uint32_t, 8>& state,
    const std::uint8_t* block) {
    std::array<std::uint32_t, 64> words{};
    for (int index = 0; index < 16; ++index) {
        const std::size_t offset = static_cast<std::size_t>(index) * 4;
        words[index] = (static_cast<std::uint32_t>(block[offset]) << 24) |
            (static_cast<std::uint32_t>(block[offset + 1]) << 16) |
            (static_cast<std::uint32_t>(block[offset + 2]) << 8) |
            block[offset + 3];
    }
    for (int index = 16; index < 64; ++index) {
        const std::uint32_t s0 = std::rotr(words[index - 15], 7) ^
            std::rotr(words[index - 15], 18) ^ (words[index - 15] >> 3);
        const std::uint32_t s1 = std::rotr(words[index - 2], 17) ^
            std::rotr(words[index - 2], 19) ^ (words[index - 2] >> 10);
        words[index] = words[index - 16] + s0 + words[index - 7] + s1;
    }
    auto [a, b, c, d, e, f, g, h] = state;
    for (int index = 0; index < 64; ++index) {
        const std::uint32_t s1 = std::rotr(e, 6) ^ std::rotr(e, 11) ^ std::rotr(e, 25);
        const std::uint32_t choice = (e & f) ^ (~e & g);
        const std::uint32_t temp1 = h + s1 + choice + sha256_k[index] + words[index];
        const std::uint32_t s0 = std::rotr(a, 2) ^ std::rotr(a, 13) ^ std::rotr(a, 22);
        const std::uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        const std::uint32_t temp2 = s0 + majority;
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

std::string sha256(std::span<const std::uint8_t> input) {
    std::array<std::uint32_t, 8> state{
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    const std::size_t full_blocks = input.size() / 64;
    for (std::size_t block = 0; block < full_blocks; ++block) {
        sha256_transform(state, input.data() + block * 64);
    }
    std::array<std::uint8_t, 128> tail{};
    const std::size_t remainder = input.size() % 64;
    if (remainder > 0) {
        std::memcpy(tail.data(), input.data() + full_blocks * 64, remainder);
    }
    tail[remainder] = 0x80;
    const std::size_t tail_size = remainder < 56 ? 64 : 128;
    const std::uint64_t bits = static_cast<std::uint64_t>(input.size()) * 8;
    for (int index = 0; index < 8; ++index) {
        tail[tail_size - 1 - index] =
            static_cast<std::uint8_t>(bits >> (index * 8));
    }
    sha256_transform(state, tail.data());
    if (tail_size == 128) sha256_transform(state, tail.data() + 64);
    constexpr char hex[] = "0123456789abcdef";
    std::string result(64, '0');
    for (std::size_t index = 0; index < state.size(); ++index) {
        for (int nibble = 0; nibble < 8; ++nibble) {
            result[index * 8 + nibble] =
                hex[(state[index] >> ((7 - nibble) * 4)) & 0xf];
        }
    }
    return result;
}

const nos::trent* field(const nos::trent& object, const char* key) {
    return object.is_dict() ? object._get(key) : nullptr;
}

std::string required_string(const nos::trent& object, const char* key) {
    const nos::trent* value = field(object, key);
    if (!value || !value->is_string() || value->as_string().empty()) {
        throw std::runtime_error(std::string("runtime package blob entry requires '") + key + "'");
    }
    return value->as_string();
}

std::size_t required_size(const nos::trent& object, const char* key) {
    const nos::trent* value = field(object, key);
    if (!value || !value->is_numer()) {
        throw std::runtime_error(std::string("runtime package blob entry requires numeric '") + key + "'");
    }
    const double number = static_cast<double>(value->as_numer());
    if (number < 0 || number > static_cast<double>(std::numeric_limits<std::size_t>::max()) ||
            number != static_cast<double>(static_cast<std::size_t>(number))) {
        throw std::runtime_error(std::string("invalid runtime package blob '") + key + "'");
    }
    return static_cast<std::size_t>(number);
}

class DirectoryReader final : public RuntimePackageReader {
public:
    explicit DirectoryReader(const std::string& root_path) {
        std::error_code error;
        root_ = std::filesystem::canonical(root_path, error);
        if (error || !std::filesystem::is_directory(root_)) {
            throw std::runtime_error("runtime package root is not a directory: " + root_path);
        }
    }

    RuntimePackageBytes read(std::string_view path) const override {
        const std::filesystem::path resolved = resolve(path);
        std::ifstream input(resolved, std::ios::binary | std::ios::ate);
        if (!input) throw std::runtime_error("failed to open file: " + resolved.string());
        const std::streampos end = input.tellg();
        if (end < 0) throw std::runtime_error("failed to determine file size: " + resolved.string());
        auto bytes = std::make_shared<std::vector<std::uint8_t>>(static_cast<std::size_t>(end));
        input.seekg(0, std::ios::beg);
        if (!bytes->empty()) {
            input.read(
                reinterpret_cast<char*>(bytes->data()),
                static_cast<std::streamsize>(bytes->size()));
        }
        if (!input) throw std::runtime_error("failed to read file: " + resolved.string());
        return {bytes, bytes->data(), bytes->size()};
    }

    bool contains(std::string_view path) const override {
        try {
            std::error_code error;
            return std::filesystem::is_regular_file(resolve(path), error) && !error;
        } catch (...) {
            return false;
        }
    }

    std::string describe(std::string_view path) const override { return resolve(path).string(); }
    std::string materialized_path(std::string_view path) const override { return resolve(path).string(); }

private:
    std::filesystem::path resolve(std::string_view path) const {
        const std::string normalized = validate_path(path);
        std::error_code error;
        const std::filesystem::path result =
            std::filesystem::weakly_canonical(root_ / normalized, error);
        if (error || !contained(root_, result)) {
            throw std::runtime_error("runtime package path escapes bundle root: " + normalized);
        }
        return result;
    }

    std::filesystem::path root_;
};

class BlobReader final : public RuntimePackageReader {
public:
    BlobReader(std::shared_ptr<const std::vector<std::uint8_t>> blob, std::string label)
        : blob_(std::move(blob)), label_(std::move(label)) {
        if (!blob_ || blob_->size() < blob_magic.size() + 4 ||
                !std::equal(blob_magic.begin(), blob_magic.end(), blob_->begin())) {
            throw std::runtime_error("invalid runtime package blob magic: " + label_);
        }
        const std::size_t header_size = read_u32_le(blob_->data() + blob_magic.size());
        const std::size_t header_offset = blob_magic.size() + 4;
        if (header_size == 0 || header_size > blob_->size() - header_offset) {
            throw std::runtime_error("invalid runtime package blob header size: " + label_);
        }
        payload_offset_ = header_offset + header_size;
        const std::string header(
            reinterpret_cast<const char*>(blob_->data() + header_offset), header_size);
        const nos::trent index = nos::json::parse(header);
        const nos::trent* version = field(index, "version");
        const nos::trent* entries = field(index, "entries");
        if (!version || !version->is_numer() || version->as_numer() != 1 ||
                !entries || !entries->is_list()) {
            throw std::runtime_error("runtime package blob requires index version 1 and entries");
        }
        std::size_t expected_offset = 0;
        for (const nos::trent& value : entries->as_list()) {
            const std::string path = validate_path(required_string(value, "path"));
            const std::size_t offset = required_size(value, "offset");
            const std::size_t size = required_size(value, "size");
            const std::string digest = required_string(value, "sha256");
            const std::size_t payload_size = blob_->size() - payload_offset_;
            if (digest.size() != 64 || offset != expected_offset ||
                    offset > payload_size || size > payload_size - offset) {
                throw std::runtime_error("invalid runtime package blob entry bounds: " + path);
            }
            if (!entries_.emplace(path, Entry{offset, size}).second) {
                throw std::runtime_error("duplicate runtime package blob path: " + path);
            }
            const auto bytes = std::span<const std::uint8_t>(
                blob_->data() + payload_offset_ + offset, size);
            if (sha256(bytes) != digest) {
                throw std::runtime_error("runtime package blob hash mismatch: " + path);
            }
            expected_offset += size;
        }
        if (payload_offset_ + expected_offset != blob_->size()) {
            throw std::runtime_error("runtime package blob has unindexed trailing data: " + label_);
        }
    }

    RuntimePackageBytes read(std::string_view path) const override {
        const std::string normalized = validate_path(path);
        const auto found = entries_.find(normalized);
        if (found == entries_.end()) {
            throw std::runtime_error("runtime package blob entry not found: " + normalized);
        }
        return {blob_, blob_->data() + payload_offset_ + found->second.offset, found->second.size};
    }

    bool contains(std::string_view path) const override {
        try { return entries_.contains(validate_path(path)); }
        catch (...) { return false; }
    }

    std::string describe(std::string_view path) const override {
        return label_ + "#" + validate_path(path);
    }

    std::string materialized_path(std::string_view) const override { return {}; }

private:
    struct Entry { std::size_t offset; std::size_t size; };
    std::shared_ptr<const std::vector<std::uint8_t>> blob_;
    std::string label_;
    std::size_t payload_offset_ = 0;
    std::unordered_map<std::string, Entry> entries_;
};

} // namespace

std::shared_ptr<RuntimePackageReader> open_runtime_package_directory(
    const std::string& root_path) {
    return std::make_shared<DirectoryReader>(root_path);
}

std::shared_ptr<RuntimePackageReader> open_runtime_package_blob(
    std::shared_ptr<const std::vector<std::uint8_t>> blob,
    std::string label) {
    return std::make_shared<BlobReader>(std::move(blob), std::move(label));
}

} // namespace termin::runtime
