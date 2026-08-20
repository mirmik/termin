#include <termin/engine/world_controller.hpp>

#include <utility>

#include <tcbase/tc_log.hpp>

namespace termin {

    namespace {

        struct WorldControllerErrorBuffer {
            char text[1024] = {};
            tc_world_controller_error_v1 error{sizeof(tc_world_controller_error_v1), text, sizeof(text)};
        };

    } // namespace

    WorldControllerInstance::~WorldControllerInstance() {
        reset();
    }

    WorldControllerInstance::WorldControllerInstance(WorldControllerInstance&& other) noexcept
        : _instance(std::exchange(other._instance, nullptr)) {}

    WorldControllerInstance& WorldControllerInstance::operator=(WorldControllerInstance&& other) noexcept {
        if (this != &other) {
            if (!reset()) {
                return *this;
            }
            _instance = std::exchange(other._instance, nullptr);
        }
        return *this;
    }

    WorldControllerInstance WorldControllerInstance::create(const char* type_name, std::string& error) {
        error.clear();
        WorldControllerErrorBuffer buffer;
        tc_world_controller_instance* instance = tc_world_controller_instance_create(type_name, &buffer.error);
        if (!instance) {
            error = buffer.text[0] ? buffer.text : "WorldController instance creation failed";
        }
        return WorldControllerInstance(instance);
    }

    tc_world_controller_state WorldControllerInstance::state() const noexcept {
        return tc_world_controller_instance_state(_instance);
    }

    const char* WorldControllerInstance::type_name() const noexcept {
        return tc_world_controller_instance_type_name(_instance);
    }

    bool WorldControllerInstance::reset() noexcept {
        if (!_instance) {
            return true;
        }
        WorldControllerErrorBuffer buffer;
        const bool result = tc_world_controller_instance_destroy(&_instance, &buffer.error);
        if (!result) {
            tc::Log::error("[WorldControllerInstance] destroy failed: %s",
                           buffer.text[0] ? buffer.text : "unknown lifecycle failure");
        }
        return result;
    }

    WorldControllerTypeDescriptorBuilder::WorldControllerTypeDescriptorBuilder(const char* type_name,
                                                                               const char* owner,
                                                                               const char* parent,
                                                                               tc_runtime_owned_factory factory,
                                                                               bool is_abstract,
                                                                               bool allow_same_owner_replacement)
        : _factory(factory),
          _type_name(type_name ? type_name : ""),
          _abstract(is_abstract) {
        if (_type_name.empty() || !owner || !owner[0]) {
            tc::Log::error("[WorldControllerTypeDescriptor] type and owner must be non-empty");
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

    WorldControllerTypeDescriptorBuilder::~WorldControllerTypeDescriptorBuilder() {
        tc_runtime_type_descriptor_destroy(_descriptor);
        tc_runtime_owned_factory_reset(&_factory);
    }

    WorldControllerTypeDescriptorBuilder::WorldControllerTypeDescriptorBuilder(
        WorldControllerTypeDescriptorBuilder&& other) noexcept
        : _descriptor(other._descriptor),
          _factory(tc_runtime_owned_factory_take(&other._factory)),
          _type_name(std::move(other._type_name)),
          _abstract(other._abstract),
          _valid(other._valid) {
        other._descriptor = nullptr;
    }

    WorldControllerTypeDescriptorBuilder&
    WorldControllerTypeDescriptorBuilder::operator=(WorldControllerTypeDescriptorBuilder&& other) noexcept {
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

    WorldControllerTypeDescriptorBuilder& WorldControllerTypeDescriptorBuilder::runtime_binding(
        const char* binding_id, void* payload, tc_runtime_type_facet_destroy_fn destroy) {
        if (!_descriptor || !tc_runtime_type_descriptor_add_binding(_descriptor, binding_id, payload, destroy)) {
            _valid = false;
        }
        return *this;
    }

    bool WorldControllerTypeDescriptorBuilder::commit() {
        if (!_valid || !_descriptor) {
            tc::Log::error("[WorldControllerTypeDescriptor] invalid descriptor for %s", _type_name.c_str());
            return false;
        }
        if (!tc_world_controller_type_descriptor_add_facet(_descriptor, &_factory, _abstract)) {
            tc::Log::error("[WorldControllerTypeDescriptor] failed to stage the facet for %s", _type_name.c_str());
            _valid = false;
            return false;
        }

        tc_runtime_type_descriptor* descriptor = _descriptor;
        _descriptor = nullptr;
        if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
            tc::Log::error("[WorldControllerTypeDescriptor] failed to commit %s", _type_name.c_str());
            _valid = false;
            return false;
        }
        return true;
    }

} // namespace termin
