#include "general_transform3.hpp"
#include "../entity/entity.hpp"

namespace termin {

Entity GeneralTransform3::entity() const {
    return Entity(_pool, _id);
}

} // namespace termin
