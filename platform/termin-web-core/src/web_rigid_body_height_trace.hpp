#pragma once

#include <cstddef>
#include <stdexcept>
#include <vector>

#include <tcbase/tc_log.hpp>
#include <termin/physics_components/components.hpp>

namespace termin::web {

    // The scene owns this transient component and schedules it after the solver,
    // including every catch-up step in frames that advance physics more than once.
    class RigidBodyHeightTrace final : public CxxComponent {
    public:
        RigidBodyHeightTrace() : CxxComponent("WebRigidBodyHeightTrace") {
            set_has_fixed_update(true);
            set_fixed_update_priority(fixed_update_priority::post_physics);
        }

        void begin(double height, int max_samples) {
            max_samples_ = static_cast<std::size_t>(max_samples);
            samples_.assign(1, {0.0, height});
            lost_body_ = false;
        }

        void fixed_update(float dt) override {
            if (lost_body_ || samples_.size() >= max_samples_) return;
            auto* component = entity().get_component<RigidBodyComponent>();
            const auto* body = component ? component->rigid_body() : nullptr;
            if (!body) {
                lost_body_ = true;
                tc::Log::error("[WebRigidBodyHeightTrace] tracked physics body disappeared");
                return;
            }
            samples_.push_back({samples_.back().time + dt, body->position().z});
        }

        // A null output queries the size. A supplied buffer holds the times
        // followed by the heights, matching RetainedChart2D's series arrays.
        int read(double* output, int capacity) const {
            if (lost_body_) throw std::runtime_error("tracked physics body disappeared");
            const int count = static_cast<int>(samples_.size());
            if (output) {
                if (capacity < count) throw std::invalid_argument("height trace buffer is too small");
                for (int i = 0; i < count; ++i) {
                    output[i] = samples_[i].time;
                    output[count + i] = samples_[i].height;
                }
            }
            return count;
        }

    private:
        struct Sample {
            double time;
            double height;
        };
        std::vector<Sample> samples_;
        std::size_t max_samples_ = 0;
        bool lost_body_ = false;
    };

} // namespace termin::web
