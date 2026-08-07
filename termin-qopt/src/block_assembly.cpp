#include <termin/qopt/block_assembly.hpp>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace termin::qopt {
    namespace {

        std::atomic<std::uint64_t> next_topology_id{1};

        [[nodiscard]] AssemblyDiagnostic validate_matrix_view(ConstDenseMatrixView view,
                                                              std::size_t expected_rows,
                                                              std::size_t expected_columns) noexcept {
            if (view.rows != expected_rows || view.columns != expected_columns) {
                return AssemblyDiagnostic::DimensionMismatch;
            }
            if (view.empty()) {
                return AssemblyDiagnostic::None;
            }
            if (view.data == nullptr) {
                return AssemblyDiagnostic::NullData;
            }
            if (view.row_stride <= 0 || view.column_stride <= 0) {
                return AssemblyDiagnostic::InvalidStride;
            }
            return AssemblyDiagnostic::None;
        }

        [[nodiscard]] AssemblyDiagnostic validate_vector_view(ConstDenseVectorView view,
                                                              std::size_t expected_size) noexcept {
            if (view.size != expected_size) {
                return AssemblyDiagnostic::DimensionMismatch;
            }
            if (view.empty()) {
                return AssemblyDiagnostic::None;
            }
            if (view.data == nullptr) {
                return AssemblyDiagnostic::NullData;
            }
            if (view.stride <= 0) {
                return AssemblyDiagnostic::InvalidStride;
            }
            return AssemblyDiagnostic::None;
        }

        void log_internal_failure(const char* operation, const char* message) noexcept {
            std::fprintf(stderr, "[termin-qopt] dense block assembly %s failed: %s\n", operation, message);
        }

    } // namespace

    struct DenseBlockTopology::Impl {
        struct Block {
            std::size_t offset = 0;
            std::size_t size = 0;
            std::string name;
        };

        std::uint64_t id = next_topology_id.fetch_add(1, std::memory_order_relaxed);
        std::vector<Block> blocks;
        std::size_t total_size = 0;
        bool finalized = false;
    };

    std::string_view assembly_diagnostic_name(AssemblyDiagnostic diagnostic) noexcept {
        switch (diagnostic) {
        case AssemblyDiagnostic::None:
            return "none";
        case AssemblyDiagnostic::TopologyFinalized:
            return "topology_finalized";
        case AssemblyDiagnostic::TopologyNotFinalized:
            return "topology_not_finalized";
        case AssemblyDiagnostic::ZeroBlockSize:
            return "zero_block_size";
        case AssemblyDiagnostic::DuplicateBlockName:
            return "duplicate_block_name";
        case AssemblyDiagnostic::InvalidBlock:
            return "invalid_block";
        case AssemblyDiagnostic::NullData:
            return "null_data";
        case AssemblyDiagnostic::InvalidStride:
            return "invalid_stride";
        case AssemblyDiagnostic::DimensionMismatch:
            return "dimension_mismatch";
        case AssemblyDiagnostic::NonFiniteContribution:
            return "non_finite_contribution";
        case AssemblyDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    DenseBlockTopology::DenseBlockTopology()
        : impl_(std::make_unique<Impl>()) {}

    DenseBlockTopology::~DenseBlockTopology() = default;
    DenseBlockTopology::DenseBlockTopology(DenseBlockTopology&&) noexcept = default;
    DenseBlockTopology& DenseBlockTopology::operator=(DenseBlockTopology&&) noexcept = default;

    DenseBlockRegistrationResult DenseBlockTopology::register_block(std::size_t size,
                                                                    std::string_view diagnostic_name) noexcept {
        if (impl_ == nullptr) {
            return {{}, AssemblyDiagnostic::InternalFailure};
        }
        if (impl_->finalized) {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        if (size == 0) {
            return {{}, AssemblyDiagnostic::ZeroBlockSize};
        }
        if (!diagnostic_name.empty()) {
            const auto duplicate =
                std::find_if(impl_->blocks.begin(), impl_->blocks.end(), [diagnostic_name](const Impl::Block& block) {
                    return block.name == diagnostic_name;
                });
            if (duplicate != impl_->blocks.end()) {
                return {{}, AssemblyDiagnostic::DuplicateBlockName};
            }
        }
        if (size > std::numeric_limits<std::size_t>::max() - impl_->total_size) {
            log_internal_failure("registration", "total block size overflow");
            return {{}, AssemblyDiagnostic::InternalFailure};
        }

        try {
            const std::size_t index = impl_->blocks.size();
            impl_->blocks.push_back({
                impl_->total_size,
                size,
                std::string(diagnostic_name),
            });
            impl_->total_size += size;
            return {{impl_->id, index}, AssemblyDiagnostic::None};
        } catch (const std::exception& error) {
            log_internal_failure("registration", error.what());
        } catch (...) {
            log_internal_failure("registration", "unknown exception");
        }
        return {{}, AssemblyDiagnostic::InternalFailure};
    }

    AssemblyDiagnostic DenseBlockTopology::finalize() noexcept {
        if (impl_ == nullptr) {
            return AssemblyDiagnostic::InternalFailure;
        }
        if (impl_->finalized) {
            return AssemblyDiagnostic::TopologyFinalized;
        }
        impl_->finalized = true;
        return AssemblyDiagnostic::None;
    }

    bool DenseBlockTopology::finalized() const noexcept {
        return impl_ != nullptr && impl_->finalized;
    }

    std::size_t DenseBlockTopology::block_count() const noexcept {
        return impl_ == nullptr ? 0 : impl_->blocks.size();
    }

    std::size_t DenseBlockTopology::total_size() const noexcept {
        return impl_ == nullptr ? 0 : impl_->total_size;
    }

    DenseBlockInfo DenseBlockTopology::block_info(DenseBlockHandle handle) const noexcept {
        if (impl_ == nullptr || handle.topology_id != impl_->id || handle.index >= impl_->blocks.size()) {
            return {0, 0, AssemblyDiagnostic::InvalidBlock};
        }
        const Impl::Block& block = impl_->blocks[handle.index];
        return {block.offset, block.size, AssemblyDiagnostic::None};
    }

    DenseBlockMatrixAssembly::DenseBlockMatrixAssembly(const DenseBlockTopology& row_topology,
                                                       const DenseBlockTopology& column_topology,
                                                       DenseMatrixView target) noexcept
        : rows_(&row_topology),
          columns_(&column_topology),
          target_(target) {
        if (!rows_->finalized() || !columns_->finalized()) {
            diagnostic_ = AssemblyDiagnostic::TopologyNotFinalized;
            return;
        }
        diagnostic_ = validate_matrix_view(ConstDenseMatrixView(target_), rows_->total_size(), columns_->total_size());
    }

    AssemblyDiagnostic DenseBlockMatrixAssembly::diagnostic() const noexcept {
        return diagnostic_;
    }

    bool DenseBlockMatrixAssembly::valid() const noexcept {
        return diagnostic_ == AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic DenseBlockMatrixAssembly::clear() noexcept {
        if (!valid()) {
            return diagnostic_;
        }
        for (std::size_t row = 0; row < target_.rows; ++row) {
            for (std::size_t column = 0; column < target_.columns; ++column) {
                target_(row, column) = 0.0;
            }
        }
        return AssemblyDiagnostic::None;
    }

    DenseMatrixBlockResult DenseBlockMatrixAssembly::block(DenseBlockHandle row,
                                                           DenseBlockHandle column) const noexcept {
        if (!valid()) {
            return {{}, diagnostic_};
        }
        const DenseBlockInfo row_info = rows_->block_info(row);
        if (!row_info.ok()) {
            return {{}, row_info.diagnostic};
        }
        const DenseBlockInfo column_info = columns_->block_info(column);
        if (!column_info.ok()) {
            return {{}, column_info.diagnostic};
        }
        DenseMatrixView result = target_;
        result.data = &target_(row_info.offset, column_info.offset);
        result.rows = row_info.size;
        result.columns = column_info.size;
        return {result, AssemblyDiagnostic::None};
    }

    AssemblyDiagnostic DenseBlockMatrixAssembly::add(DenseBlockHandle row,
                                                     DenseBlockHandle column,
                                                     ConstDenseMatrixView contribution) noexcept {
        const DenseMatrixBlockResult destination = block(row, column);
        if (!destination.ok()) {
            return destination.diagnostic;
        }
        const AssemblyDiagnostic source_diagnostic =
            validate_matrix_view(contribution, destination.view.rows, destination.view.columns);
        if (source_diagnostic != AssemblyDiagnostic::None) {
            return source_diagnostic;
        }
        for (std::size_t r = 0; r < contribution.rows; ++r) {
            for (std::size_t c = 0; c < contribution.columns; ++c) {
                if (!std::isfinite(contribution(r, c))) {
                    return AssemblyDiagnostic::NonFiniteContribution;
                }
            }
        }
        for (std::size_t r = 0; r < contribution.rows; ++r) {
            for (std::size_t c = 0; c < contribution.columns; ++c) {
                destination.view(r, c) += contribution(r, c);
            }
        }
        return AssemblyDiagnostic::None;
    }

    DenseBlockVectorAssembly::DenseBlockVectorAssembly(const DenseBlockTopology& topology,
                                                       DenseVectorView target) noexcept
        : topology_(&topology),
          target_(target) {
        if (!topology_->finalized()) {
            diagnostic_ = AssemblyDiagnostic::TopologyNotFinalized;
            return;
        }
        diagnostic_ = validate_vector_view(ConstDenseVectorView(target_), topology_->total_size());
    }

    AssemblyDiagnostic DenseBlockVectorAssembly::diagnostic() const noexcept {
        return diagnostic_;
    }

    bool DenseBlockVectorAssembly::valid() const noexcept {
        return diagnostic_ == AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic DenseBlockVectorAssembly::clear() noexcept {
        if (!valid()) {
            return diagnostic_;
        }
        for (std::size_t index = 0; index < target_.size; ++index) {
            target_[index] = 0.0;
        }
        return AssemblyDiagnostic::None;
    }

    DenseVectorBlockResult DenseBlockVectorAssembly::block(DenseBlockHandle handle) const noexcept {
        if (!valid()) {
            return {{}, diagnostic_};
        }
        const DenseBlockInfo info = topology_->block_info(handle);
        if (!info.ok()) {
            return {{}, info.diagnostic};
        }
        DenseVectorView result = target_;
        result.data = &target_[info.offset];
        result.size = info.size;
        return {result, AssemblyDiagnostic::None};
    }

    AssemblyDiagnostic DenseBlockVectorAssembly::add(DenseBlockHandle handle,
                                                     ConstDenseVectorView contribution) noexcept {
        const DenseVectorBlockResult destination = block(handle);
        if (!destination.ok()) {
            return destination.diagnostic;
        }
        const AssemblyDiagnostic source_diagnostic = validate_vector_view(contribution, destination.view.size);
        if (source_diagnostic != AssemblyDiagnostic::None) {
            return source_diagnostic;
        }
        for (std::size_t index = 0; index < contribution.size; ++index) {
            if (!std::isfinite(contribution[index])) {
                return AssemblyDiagnostic::NonFiniteContribution;
            }
        }
        for (std::size_t index = 0; index < contribution.size; ++index) {
            destination.view[index] += contribution[index];
        }
        return AssemblyDiagnostic::None;
    }

} // namespace termin::qopt
