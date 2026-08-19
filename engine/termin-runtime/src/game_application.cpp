#include <termin/runtime/game_application.hpp>

#include <utility>

#include <tcbase/tc_log.hpp>

namespace termin::runtime {

    GameApplicationTypeDescriptorBuilder::GameApplicationTypeDescriptorBuilder(const char* type_name,
                                                                               const char* owner,
                                                                               const char* parent,
                                                                               tc_runtime_owned_factory factory,
                                                                               bool is_abstract,
                                                                               bool allow_same_owner_replacement)
        : _factory(factory),
          _type_name(type_name ? type_name : ""),
          _abstract(is_abstract) {
        if (_type_name.empty() || !owner || !owner[0]) {
            tc::Log::error("[GameApplicationTypeDescriptor] type and owner must be non-empty");
            _valid = false;
            return;
        }

        _descriptor =
            tc_runtime_type_descriptor_create(_type_name.c_str(), owner, parent && parent[0] ? parent : nullptr);
        if (!_descriptor) {
            _valid = false;
        } else if (allow_same_owner_replacement &&
                   !tc_runtime_type_descriptor_allow_same_owner_replacement(_descriptor)) {
            _valid = false;
        }
    }

    GameApplicationTypeDescriptorBuilder::~GameApplicationTypeDescriptorBuilder() {
        tc_runtime_type_descriptor_destroy(_descriptor);
        tc_runtime_owned_factory_reset(&_factory);
    }

    GameApplicationTypeDescriptorBuilder::GameApplicationTypeDescriptorBuilder(
        GameApplicationTypeDescriptorBuilder&& other) noexcept
        : _descriptor(other._descriptor),
          _factory(tc_runtime_owned_factory_take(&other._factory)),
          _type_name(std::move(other._type_name)),
          _abstract(other._abstract),
          _valid(other._valid) {
        other._descriptor = nullptr;
    }

    GameApplicationTypeDescriptorBuilder&
    GameApplicationTypeDescriptorBuilder::operator=(GameApplicationTypeDescriptorBuilder&& other) noexcept {
        if (this == &other) {
            return *this;
        }

        tc_runtime_type_descriptor_destroy(_descriptor);
        tc_runtime_owned_factory_reset(&_factory);
        _descriptor = other._descriptor;
        other._descriptor = nullptr;
        _factory = tc_runtime_owned_factory_take(&other._factory);
        _type_name = std::move(other._type_name);
        _abstract = other._abstract;
        _valid = other._valid;
        return *this;
    }

    bool GameApplicationTypeDescriptorBuilder::commit() {
        if (!_valid || !_descriptor) {
            tc::Log::error("[GameApplicationTypeDescriptor] invalid descriptor for %s", _type_name.c_str());
            return false;
        }
        if (!tc_game_application_type_descriptor_add_facet(_descriptor, &_factory, _abstract)) {
            tc::Log::error("[GameApplicationTypeDescriptor] failed to stage the facet for %s", _type_name.c_str());
            _valid = false;
            return false;
        }

        tc_runtime_type_descriptor* descriptor = _descriptor;
        _descriptor = nullptr;
        if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
            tc::Log::error("[GameApplicationTypeDescriptor] failed to commit %s", _type_name.c_str());
            _valid = false;
            return false;
        }
        return true;
    }

} // namespace termin::runtime
