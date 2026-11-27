// Experimental swept collision queries for the MuJoCo 3.15.0 comparison.
// Each interval follows mj_integratePos from the accepted pose at fixed generalized
// velocity. Interior crossings are resolved to 2^-25 of one step; tangencies and
// shorter visits between all resolved samples are outside this benchmark's oracle.
// A pair exceeding the distance-query budget raises an error.
#pragma once

#include <mujoco/mujoco.h>

#include <array>
#include <memory>
#include <vector>

namespace predict_contact {

    struct Hit {
        int geom1, geom2;
        double fraction;    // Unitless time along the frozen generalized-velocity drift.
        double gap;         // Signed surface distance at the start of this step, metres.
        double position[3]; // Midpoint of the two impact witnesses mapped back to their current poses.
        double normal[3];   // World separating normal at impact, directed from geom1 to geom2.
    };

    class Sweep {
    public:
        explicit Sweep(const mjModel* model);
        const std::vector<Hit>& find(const mjData* data, const mjtNum* end_velocity, double h);

    private:
        const mjModel* model_;
        std::unique_ptr<mjData, decltype(&mj_deleteData)> scratch_;
        std::vector<std::array<int, 2>> pairs_;
        std::vector<double> travel_;
        std::vector<double> curvature_;
        std::vector<double> extent_;
        std::vector<std::array<double, 3>> translation_;
        std::vector<Hit> hits_;
    };

} // namespace predict_contact
