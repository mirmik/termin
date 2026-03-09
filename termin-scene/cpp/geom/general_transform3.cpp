#include <termin/geom/general_transform3.hpp>
#include <termin/entity/entity.hpp>

namespace termin {

Entity GeneralTransform3::entity() const {
    return Entity(_h);
}

} // namespace termin
