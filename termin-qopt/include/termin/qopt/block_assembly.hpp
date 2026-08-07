#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <string_view>

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

    enum class AssemblyDiagnostic : std::uint8_t {
        None,
        TopologyFinalized,
        TopologyNotFinalized,
        ZeroBlockSize,
        DuplicateBlockName,
        InvalidBlock,
        NullData,
        InvalidStride,
        DimensionMismatch,
        NonFiniteContribution,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view assembly_diagnostic_name(AssemblyDiagnostic diagnostic) noexcept;

    struct DenseBlockHandle {
        std::uint64_t topology_id = 0;
        std::size_t index = std::numeric_limits<std::size_t>::max();

        [[nodiscard]] constexpr bool valid() const noexcept {
            return topology_id != 0 && index != std::numeric_limits<std::size_t>::max();
        }

        friend constexpr bool operator==(DenseBlockHandle, DenseBlockHandle) noexcept = default;
    };

    struct DenseBlockRegistrationResult {
        DenseBlockHandle handle;
        AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

        [[nodiscard]] constexpr bool ok() const noexcept {
            return diagnostic == AssemblyDiagnostic::None;
        }
    };

    struct DenseBlockInfo {
        std::size_t offset = 0;
        std::size_t size = 0;
        AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

        [[nodiscard]] constexpr bool ok() const noexcept {
            return diagnostic == AssemblyDiagnostic::None;
        }
    };

    // A topology owns only immutable block metadata. Numerical model state and
    // matrix storage remain outside it. Handles stay valid when the topology is
    // moved and cannot be used with another topology.
    class TERMIN_QOPT_API DenseBlockTopology {
    public:
        DenseBlockTopology();
        ~DenseBlockTopology();

        DenseBlockTopology(DenseBlockTopology&&) noexcept;
        DenseBlockTopology& operator=(DenseBlockTopology&&) noexcept;

        DenseBlockTopology(const DenseBlockTopology&) = delete;
        DenseBlockTopology& operator=(const DenseBlockTopology&) = delete;

        [[nodiscard]] DenseBlockRegistrationResult register_block(std::size_t size,
                                                                  std::string_view diagnostic_name) noexcept;
        [[nodiscard]] AssemblyDiagnostic finalize() noexcept;

        [[nodiscard]] bool finalized() const noexcept;
        [[nodiscard]] std::size_t block_count() const noexcept;
        [[nodiscard]] std::size_t total_size() const noexcept;
        [[nodiscard]] DenseBlockInfo block_info(DenseBlockHandle handle) const noexcept;

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

    struct DenseMatrixBlockResult {
        DenseMatrixView view;
        AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

        [[nodiscard]] constexpr bool ok() const noexcept {
            return diagnostic == AssemblyDiagnostic::None;
        }
    };

    struct DenseVectorBlockResult {
        DenseVectorView view;
        AssemblyDiagnostic diagnostic = AssemblyDiagnostic::None;

        [[nodiscard]] constexpr bool ok() const noexcept {
            return diagnostic == AssemblyDiagnostic::None;
        }
    };

    // Caller-owned dense storage with checked block addressing. Construction does
    // not clear the target; clear() is an explicit per-assembly operation.
    class TERMIN_QOPT_API DenseBlockMatrixAssembly {
    public:
        DenseBlockMatrixAssembly(const DenseBlockTopology& row_topology,
                                 const DenseBlockTopology& column_topology,
                                 DenseMatrixView target) noexcept;

        [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] AssemblyDiagnostic clear() noexcept;
        [[nodiscard]] DenseMatrixBlockResult block(DenseBlockHandle row, DenseBlockHandle column) const noexcept;
        [[nodiscard]] AssemblyDiagnostic
        add(DenseBlockHandle row, DenseBlockHandle column, ConstDenseMatrixView contribution) noexcept;

    private:
        const DenseBlockTopology* rows_ = nullptr;
        const DenseBlockTopology* columns_ = nullptr;
        DenseMatrixView target_;
        AssemblyDiagnostic diagnostic_ = AssemblyDiagnostic::InternalFailure;
    };

    class TERMIN_QOPT_API DenseBlockVectorAssembly {
    public:
        DenseBlockVectorAssembly(const DenseBlockTopology& topology, DenseVectorView target) noexcept;

        [[nodiscard]] AssemblyDiagnostic diagnostic() const noexcept;
        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] AssemblyDiagnostic clear() noexcept;
        [[nodiscard]] DenseVectorBlockResult block(DenseBlockHandle handle) const noexcept;
        [[nodiscard]] AssemblyDiagnostic add(DenseBlockHandle handle, ConstDenseVectorView contribution) noexcept;

    private:
        const DenseBlockTopology* topology_ = nullptr;
        DenseVectorView target_;
        AssemblyDiagnostic diagnostic_ = AssemblyDiagnostic::InternalFailure;
    };

} // namespace termin::qopt
