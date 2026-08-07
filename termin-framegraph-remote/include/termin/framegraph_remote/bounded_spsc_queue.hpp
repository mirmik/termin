#pragma once

#include <atomic>
#include <cstddef>
#include <limits>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

namespace termin::framegraph_remote {

    // Fixed-capacity single-producer/single-consumer storage. Allocation
    // happens only in the constructor. A rejected push leaves the queue
    // unchanged, so a caller can account for one complete dropped command or
    // packet.
    template <typename T> class BoundedSpscQueue {
    public:
        explicit BoundedSpscQueue(std::size_t capacity)
            : slots_(checked_storage_size(capacity)),
              capacity_(capacity) {}

        BoundedSpscQueue(const BoundedSpscQueue&) = delete;
        BoundedSpscQueue& operator=(const BoundedSpscQueue&) = delete;

        bool try_push(T value) {
            const std::size_t tail = tail_.load(std::memory_order_relaxed);
            const std::size_t next = increment(tail);
            if (next == head_.load(std::memory_order_acquire))
                return false;
            slots_[tail].emplace(std::move(value));
            tail_.store(next, std::memory_order_release);
            return true;
        }

        bool try_pop(T& value) {
            const std::size_t head = head_.load(std::memory_order_relaxed);
            if (head == tail_.load(std::memory_order_acquire))
                return false;
            value = std::move(*slots_[head]);
            slots_[head].reset();
            head_.store(increment(head), std::memory_order_release);
            return true;
        }

        std::size_t capacity() const {
            return capacity_;
        }

        std::size_t size_approximate() const {
            const std::size_t head = head_.load(std::memory_order_acquire);
            const std::size_t tail = tail_.load(std::memory_order_acquire);
            return tail >= head ? tail - head : slots_.size() - head + tail;
        }

    private:
        static std::size_t checked_storage_size(std::size_t capacity) {
            if (capacity == 0 || capacity == std::numeric_limits<std::size_t>::max()) {
                throw std::invalid_argument("BoundedSpscQueue capacity is invalid");
            }
            return capacity + 1;
        }

        std::size_t increment(std::size_t index) const {
            return index + 1 == slots_.size() ? 0 : index + 1;
        }

        std::vector<std::optional<T>> slots_;
        std::size_t capacity_ = 0;
        alignas(64) std::atomic<std::size_t> head_{0};
        alignas(64) std::atomic<std::size_t> tail_{0};
    };

} // namespace termin::framegraph_remote
