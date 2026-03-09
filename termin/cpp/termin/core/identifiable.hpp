#pragma once

#include <string>
#include <cstdint>
#include <random>
#include <sstream>
#include <iomanip>
#include <functional>

namespace termin {

/**
 * Generate UUID v4 string.
 */
inline std::string generate_uuid() {
    static std::random_device rd;
    static std::mt19937_64 gen(rd());
    static std::uniform_int_distribution<uint64_t> dist;

    uint64_t a = dist(gen);
    uint64_t b = dist(gen);

    // Set version (4) and variant bits
    a = (a & 0xFFFFFFFFFFFF0FFFULL) | 0x0000000000004000ULL;
    b = (b & 0x3FFFFFFFFFFFFFFFULL) | 0x8000000000000000ULL;

    std::ostringstream ss;
    ss << std::hex << std::setfill('0');
    ss << std::setw(8) << ((a >> 32) & 0xFFFFFFFF) << "-";
    ss << std::setw(4) << ((a >> 16) & 0xFFFF) << "-";
    ss << std::setw(4) << (a & 0xFFFF) << "-";
    ss << std::setw(4) << ((b >> 48) & 0xFFFF) << "-";
    ss << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return ss.str();
}

/**
 * Compute 64-bit hash from UUID string for fast runtime lookup.
 */
inline uint64_t compute_runtime_id(const std::string& uuid) {
    std::hash<std::string> hasher;
    return hasher(uuid);
}

/**
 * Base class for objects that need unique identification.
 *
 * Provides:
 * - uuid: string - unique identifier for serialization
 * - runtime_id: uint64_t - 64-bit hash for fast runtime lookup
 */
class Identifiable {
public:
    std::string uuid;
    uint64_t runtime_id;

    Identifiable()
        : uuid(generate_uuid())
        , runtime_id(compute_runtime_id(uuid)) {}

    explicit Identifiable(const std::string& existing_uuid)
        : uuid(existing_uuid.empty() ? generate_uuid() : existing_uuid)
        , runtime_id(compute_runtime_id(uuid)) {}

    virtual ~Identifiable() = default;

    // Regenerate UUID (for copying/cloning)
    void regenerate_uuid() {
        uuid = generate_uuid();
        runtime_id = compute_runtime_id(uuid);
    }
};

} // namespace termin
