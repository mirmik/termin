#pragma once

#include <cstddef>

namespace termin::qopt {

    using DenseIndex = std::ptrdiff_t;

    struct ConstDenseVectorView;
    struct ConstDenseMatrixView;

    // Non-owning views use element strides rather than byte strides. Lifetimes
    // remain the caller's responsibility; solver entry points validate shapes.
    struct DenseVectorView {
        double* data = nullptr;
        std::size_t size = 0;
        DenseIndex stride = 1;

        [[nodiscard]] constexpr bool empty() const noexcept {
            return size == 0;
        }

        [[nodiscard]] constexpr double& operator[](std::size_t index) const noexcept {
            return data[static_cast<DenseIndex>(index) * stride];
        }
    };

    struct ConstDenseVectorView {
        const double* data = nullptr;
        std::size_t size = 0;
        DenseIndex stride = 1;

        constexpr ConstDenseVectorView() noexcept = default;

        constexpr ConstDenseVectorView(const double* data_value,
                                       std::size_t size_value,
                                       DenseIndex stride_value = 1) noexcept
            : data(data_value),
              size(size_value),
              stride(stride_value) {}

        constexpr ConstDenseVectorView(DenseVectorView view) noexcept
            : data(view.data),
              size(view.size),
              stride(view.stride) {}

        [[nodiscard]] constexpr bool empty() const noexcept {
            return size == 0;
        }

        [[nodiscard]] constexpr const double& operator[](std::size_t index) const noexcept {
            return data[static_cast<DenseIndex>(index) * stride];
        }
    };

    struct DenseMatrixView {
        double* data = nullptr;
        std::size_t rows = 0;
        std::size_t columns = 0;
        DenseIndex row_stride = 0;
        DenseIndex column_stride = 0;

        [[nodiscard]] static constexpr DenseMatrixView
        row_major(double* data, std::size_t rows, std::size_t columns) noexcept {
            return {data, rows, columns, static_cast<DenseIndex>(columns), 1};
        }

        [[nodiscard]] static constexpr DenseMatrixView
        column_major(double* data, std::size_t rows, std::size_t columns) noexcept {
            return {data, rows, columns, 1, static_cast<DenseIndex>(rows)};
        }

        [[nodiscard]] constexpr bool empty() const noexcept {
            return rows == 0 || columns == 0;
        }

        [[nodiscard]] constexpr double& operator()(std::size_t row, std::size_t column) const noexcept {
            return data[static_cast<DenseIndex>(row) * row_stride + static_cast<DenseIndex>(column) * column_stride];
        }
    };

    struct ConstDenseMatrixView {
        const double* data = nullptr;
        std::size_t rows = 0;
        std::size_t columns = 0;
        DenseIndex row_stride = 0;
        DenseIndex column_stride = 0;

        constexpr ConstDenseMatrixView() noexcept = default;

        constexpr ConstDenseMatrixView(const double* data_value,
                                       std::size_t rows_value,
                                       std::size_t columns_value,
                                       DenseIndex row_stride_value,
                                       DenseIndex column_stride_value) noexcept
            : data(data_value),
              rows(rows_value),
              columns(columns_value),
              row_stride(row_stride_value),
              column_stride(column_stride_value) {}

        constexpr ConstDenseMatrixView(DenseMatrixView view) noexcept
            : data(view.data),
              rows(view.rows),
              columns(view.columns),
              row_stride(view.row_stride),
              column_stride(view.column_stride) {}

        [[nodiscard]] static constexpr ConstDenseMatrixView
        row_major(const double* data, std::size_t rows, std::size_t columns) noexcept {
            return {
                data,
                rows,
                columns,
                static_cast<DenseIndex>(columns),
                1,
            };
        }

        [[nodiscard]] static constexpr ConstDenseMatrixView
        column_major(const double* data, std::size_t rows, std::size_t columns) noexcept {
            return {
                data,
                rows,
                columns,
                1,
                static_cast<DenseIndex>(rows),
            };
        }

        [[nodiscard]] constexpr bool empty() const noexcept {
            return rows == 0 || columns == 0;
        }

        [[nodiscard]] constexpr const double& operator()(std::size_t row, std::size_t column) const noexcept {
            return data[static_cast<DenseIndex>(row) * row_stride + static_cast<DenseIndex>(column) * column_stride];
        }
    };

} // namespace termin::qopt
