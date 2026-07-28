#include <termin/qopt/dense_views.hpp>

#include "test_check.hpp"

#include <array>
#include <type_traits>

using termin::qopt::ConstDenseMatrixView;
using termin::qopt::ConstDenseVectorView;
using termin::qopt::DenseMatrixView;
using termin::qopt::DenseVectorView;

static_assert(std::is_trivially_copyable_v<DenseVectorView>);
static_assert(std::is_trivially_copyable_v<ConstDenseVectorView>);
static_assert(std::is_trivially_copyable_v<DenseMatrixView>);
static_assert(std::is_trivially_copyable_v<ConstDenseMatrixView>);

int main() {
  std::array<double, 12> values{
      0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0,
  };

  DenseVectorView strided_vector{values.data() + 1, 3, 2};
  TERMIN_QOPT_CHECK(strided_vector[0] == 1.0);
  TERMIN_QOPT_CHECK(strided_vector[1] == 3.0);
  TERMIN_QOPT_CHECK(strided_vector[2] == 5.0);

  ConstDenseVectorView const_vector = strided_vector;
  TERMIN_QOPT_CHECK(const_vector.data == strided_vector.data);
  TERMIN_QOPT_CHECK(const_vector.stride == 2);

  DenseMatrixView row_major = DenseMatrixView::row_major(values.data(), 3, 4);
  TERMIN_QOPT_CHECK(row_major(0, 3) == 3.0);
  TERMIN_QOPT_CHECK(row_major(2, 1) == 9.0);

  ConstDenseMatrixView const_row_major = row_major;
  TERMIN_QOPT_CHECK(const_row_major.row_stride == 4);
  TERMIN_QOPT_CHECK(const_row_major.column_stride == 1);

  DenseMatrixView column_major =
      DenseMatrixView::column_major(values.data(), 3, 4);
  TERMIN_QOPT_CHECK(column_major(2, 0) == 2.0);
  TERMIN_QOPT_CHECK(column_major(1, 3) == 10.0);

  ConstDenseMatrixView transposed{
      values.data(), 4, 3, 1, 4,
  };
  TERMIN_QOPT_CHECK(transposed(3, 2) == 11.0);

  return 0;
}
