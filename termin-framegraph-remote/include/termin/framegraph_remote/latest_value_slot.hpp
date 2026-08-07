#pragma once

#include <cstdint>
#include <mutex>
#include <optional>
#include <utility>

namespace termin::framegraph_remote
{

    // One ready value with latest-wins replacement. The producer never waits
    // for a slow consumer beyond the short ownership swap, and every replaced
    // or explicitly rejected value is reported with the next delivered one.
    template <typename T> class LatestValueSlot
    {
    public:
        struct Delivery
        {
            T value;
            std::uint64_t dropped_before = 0;
        };

        std::optional<T> publish(T value)
        {
            std::lock_guard lock(mutex_);
            std::optional<T> replaced;
            if (ready_)
            {
                pending_drops_ += ready_->dropped_before + 1;
                replaced.emplace(std::move(ready_->value));
            }
            ready_ = Delivery{std::move(value), pending_drops_};
            pending_drops_ = 0;
            return replaced;
        }

        void note_drop()
        {
            std::lock_guard lock(mutex_);
            ++pending_drops_;
        }

        std::optional<Delivery> take()
        {
            std::lock_guard lock(mutex_);
            return std::exchange(ready_, std::nullopt);
        }

        std::optional<T> discard_ready()
        {
            std::lock_guard lock(mutex_);
            if (!ready_)
                return std::nullopt;
            pending_drops_ += ready_->dropped_before + 1;
            std::optional<T> discarded(
                std::move(ready_->value));
            ready_.reset();
            return discarded;
        }

        std::optional<T> clear()
        {
            std::lock_guard lock(mutex_);
            std::optional<T> discarded;
            if (ready_)
                discarded.emplace(std::move(ready_->value));
            ready_.reset();
            pending_drops_ = 0;
            return discarded;
        }

    private:
        std::mutex mutex_;
        std::optional<Delivery> ready_;
        std::uint64_t pending_drops_ = 0;
    };

} // namespace termin::framegraph_remote
