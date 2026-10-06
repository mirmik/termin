#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace termin::detail {
    // Indexes existing semantic keys without owning or copying them. Entries in
    // hash chain are verified with full equality to resolve collisions.
    class StaticBatchKeyIndex {
        struct Entry {
            uint64_t hash;
            size_t value;
            size_t next;
        };
        std::vector<size_t> buckets_;
        std::vector<Entry> entries_;

    public:
        static constexpr size_t missing = std::numeric_limits<size_t>::max();

        void reset(size_t expected_entries) {
            size_t bucket_count = 16;
            while (bucket_count < expected_entries && bucket_count <= std::numeric_limits<size_t>::max() / 2)
                bucket_count *= 2;
            // Do not shrink: warmed frames retain the index's allocation.
            if (buckets_.size() < bucket_count)
                buckets_.resize(bucket_count);
            std::fill(buckets_.begin(), buckets_.end(), missing);
            entries_.clear();
            if (entries_.capacity() < expected_entries)
                entries_.reserve(expected_entries);
        }

        void insert(uint64_t hash, size_t value) {
            const size_t bucket = hash & (buckets_.size() - 1);
            entries_.push_back({hash, value, buckets_[bucket]});
            buckets_[bucket] = entries_.size() - 1;
        }

        template <typename Equal>
        size_t find(uint64_t hash, Equal&& equal) const {
            for (size_t entry = buckets_[hash & (buckets_.size() - 1)]; entry != missing; entry = entries_[entry].next) {
                const Entry& candidate = entries_[entry];
                if (candidate.hash == hash && equal(candidate.value))
                    return candidate.value;
            }
            return missing;
        }
    };
} // namespace termin::detail
