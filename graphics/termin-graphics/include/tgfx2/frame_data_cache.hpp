#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <unordered_map>
#include <utility>
#include <vector>

namespace tgfx {

    struct FrameDataInput {
        const void* data;
        size_t size;
    };

    // CPU-only derived data owned by one render frame. The hint accelerates
    // lookup; exact source snapshots, including segment boundaries, establish
    // identity. Callers supply a distinct stable domain token per derivation.
    // Returned storage remains valid until store() for the same domain/hint or
    // clear(). No source pointers are retained or dereferenced after the call.
    class FrameDataCache {
        struct Key {
            const void* domain;
            size_t hint;
            bool operator==(const Key&) const = default;
        };
        struct KeyHash {
            size_t operator()(const Key& key) const {
                const size_t domain = reinterpret_cast<uintptr_t>(key.domain);
                return domain ^ (key.hint + size_t{0x9e3779b9} + (domain << 6) + (domain >> 2));
            }
        };
        struct Entry {
            std::vector<size_t> input_sizes;
            std::vector<uint8_t> input_bytes;
            std::vector<uint8_t> output;
        };
        std::unordered_map<Key, Entry, KeyHash> entries_;

    public:
        std::span<const uint8_t> find(const void* domain, size_t hint, std::span<const FrameDataInput> inputs) const {
            const auto it = entries_.find({domain, hint});
            if (it == entries_.end() || it->second.input_sizes.size() != inputs.size())
                return {};
            const Entry& entry = it->second;
            size_t offset = 0;
            for (size_t i = 0; i < inputs.size(); ++i) {
                const FrameDataInput& input = inputs[i];
                if (input.size != entry.input_sizes[i] ||
                    (input.size && std::memcmp(input.data, entry.input_bytes.data() + offset, input.size) != 0))
                    return {};
                offset += input.size;
            }
            return entry.output;
        }

        std::span<const uint8_t> store(const void* domain,
                                       size_t hint,
                                       std::span<const FrameDataInput> inputs,
                                       std::vector<uint8_t> output) {
            Entry& entry = entries_[{domain, hint}];
            entry.input_sizes.clear();
            entry.input_bytes.clear();
            for (const FrameDataInput& input : inputs) {
                entry.input_sizes.push_back(input.size);
                if (input.size) {
                    const auto* begin = static_cast<const uint8_t*>(input.data);
                    entry.input_bytes.insert(entry.input_bytes.end(), begin, begin + input.size);
                }
            }
            entry.output = std::move(output);
            return entry.output;
        }

        void clear() { entries_.clear(); }
    };

} // namespace tgfx
