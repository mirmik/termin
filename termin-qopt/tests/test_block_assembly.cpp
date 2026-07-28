#include <termin/qopt/block_assembly.hpp>

#include "test_check.hpp"

#include <array>
#include <limits>
#include <utility>

using namespace termin::qopt;

int main() {
  DenseBlockTopology rows;
  const DenseBlockRegistrationResult body = rows.register_block(2, "body");
  const DenseBlockRegistrationResult joint = rows.register_block(1, "joint");
  TERMIN_QOPT_CHECK(body.ok());
  TERMIN_QOPT_CHECK(joint.ok());
  TERMIN_QOPT_CHECK(
      rows.register_block(1, "body").diagnostic
      == AssemblyDiagnostic::DuplicateBlockName
  );
  TERMIN_QOPT_CHECK(rows.block_count() == 2);
  TERMIN_QOPT_CHECK(rows.total_size() == 3);

  std::array<double, 9> premature_storage{};
  DenseBlockMatrixAssembly premature(
      rows, rows, DenseMatrixView::row_major(premature_storage.data(), 3, 3)
  );
  TERMIN_QOPT_CHECK(
      premature.diagnostic() == AssemblyDiagnostic::TopologyNotFinalized
  );

  TERMIN_QOPT_CHECK(rows.finalize() == AssemblyDiagnostic::None);
  TERMIN_QOPT_CHECK(
      rows.register_block(1, "late").diagnostic
      == AssemblyDiagnostic::TopologyFinalized
  );

  DenseBlockTopology moved = std::move(rows);
  TERMIN_QOPT_CHECK(moved.block_info(body.handle).offset == 0);
  TERMIN_QOPT_CHECK(moved.block_info(joint.handle).offset == 2);

  DenseBlockTopology columns;
  const DenseBlockRegistrationResult state =
      columns.register_block(3, "state");
  TERMIN_QOPT_CHECK(state.ok());
  TERMIN_QOPT_CHECK(columns.finalize() == AssemblyDiagnostic::None);

  std::array<double, 9> matrix_storage;
  matrix_storage.fill(42.0);
  DenseBlockMatrixAssembly matrix(
      moved,
      columns,
      DenseMatrixView::row_major(matrix_storage.data(), 3, 3)
  );
  TERMIN_QOPT_CHECK(matrix.valid());
  TERMIN_QOPT_CHECK(matrix.clear() == AssemblyDiagnostic::None);

  const std::array<double, 6> body_contribution{
      1.0, 2.0, 3.0,
      4.0, 5.0, 6.0,
  };
  TERMIN_QOPT_CHECK(
      matrix.add(
          body.handle,
          state.handle,
          ConstDenseMatrixView::row_major(body_contribution.data(), 2, 3)
      ) == AssemblyDiagnostic::None
  );
  const std::array<double, 3> joint_contribution{7.0, 8.0, 9.0};
  TERMIN_QOPT_CHECK(
      matrix.add(
          joint.handle,
          state.handle,
          ConstDenseMatrixView::row_major(joint_contribution.data(), 1, 3)
      ) == AssemblyDiagnostic::None
  );
  for (std::size_t index = 0; index < matrix_storage.size(); ++index) {
    TERMIN_QOPT_CHECK(matrix_storage[index] == static_cast<double>(index + 1));
  }

  const std::array<double, 1> wrong_shape{1.0};
  TERMIN_QOPT_CHECK(
      matrix.add(
          body.handle,
          state.handle,
          ConstDenseMatrixView::row_major(wrong_shape.data(), 1, 1)
      ) == AssemblyDiagnostic::DimensionMismatch
  );
  DenseBlockTopology foreign;
  const DenseBlockRegistrationResult foreign_block =
      foreign.register_block(2, "foreign");
  TERMIN_QOPT_CHECK(foreign.finalize() == AssemblyDiagnostic::None);
  TERMIN_QOPT_CHECK(
      matrix.block(foreign_block.handle, state.handle).diagnostic
      == AssemblyDiagnostic::InvalidBlock
  );

  std::array<double, 3> vector_storage{4.0, 4.0, 4.0};
  DenseBlockVectorAssembly vector(
      moved, DenseVectorView{vector_storage.data(), vector_storage.size(), 1}
  );
  TERMIN_QOPT_CHECK(vector.clear() == AssemblyDiagnostic::None);
  const std::array<double, 2> body_vector{2.0, 3.0};
  const std::array<double, 1> joint_vector{5.0};
  TERMIN_QOPT_CHECK(
      vector.add(body.handle, {body_vector.data(), body_vector.size(), 1})
      == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(
      vector.add(joint.handle, {joint_vector.data(), joint_vector.size(), 1})
      == AssemblyDiagnostic::None
  );
  TERMIN_QOPT_CHECK(vector_storage[0] == 2.0);
  TERMIN_QOPT_CHECK(vector_storage[1] == 3.0);
  TERMIN_QOPT_CHECK(vector_storage[2] == 5.0);

  const double nan = std::numeric_limits<double>::quiet_NaN();
  TERMIN_QOPT_CHECK(
      vector.add(joint.handle, {&nan, 1, 1})
      == AssemblyDiagnostic::NonFiniteContribution
  );
  TERMIN_QOPT_CHECK(vector_storage[2] == 5.0);

  return 0;
}
