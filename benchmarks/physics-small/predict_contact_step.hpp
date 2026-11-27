// Optional MuJoCo 3.15 fixed-step contact experiment.
#pragma once
#include "predict_contact_sweep.hpp"

namespace predict_contact {

    class Step {
    public:
        explicit Step(const mjModel* model);
        // Called after free acceleration, before mj_fwdConstraint. Requires the current
        // configuration's full mass factor, collision result and constraint Jacobian.
        void prepare(mjData* data);
        int hit_count() const;
        double fraction(int i) const;
        void advance(mjData* data);

    private:
        const mjModel* model_;
        Sweep sweep_;
        std::vector<double> end_velocity_;
        std::vector<double> normal_velocity_;
        std::vector<double> fractions_;
        std::vector<std::array<int, 2>> previous_pairs_, next_pairs_;
        std::vector<int> arrival_indices_;
        const mjData* previous_data_ = nullptr;
        double next_time_ = 0;
    };

} // namespace predict_contact
