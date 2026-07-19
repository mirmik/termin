# Static registration inventory после #138

## Runtime type registrations

Production component, frame-pass и inspect registration больше не выполняется
из static constructors. Built-in тип владеет `register_type()`, deterministic
bootstrap вызывает только эти методы, project module вызывает их из ABI `init`.
Публичные `INSPECT_*` macros определяют явные helpers без dynamic initialization.
Frame-pass типы собирают runtime descriptor через
`FramePassTypeDescriptorBuilder`: parent, pass factory и inspect fields
публикуются одним commit. `Pass::register_type()` только формирует descriptor;
composition root заранее регистрирует абстрактный `CxxFramePass` и затем
вызывает регистрации concrete types. Старые
`TC_DEFINE_FRAME_PASS_FACTORY[_DERIVED]` удалены.

Legacy `ComponentRegistrar`, `AbstractComponentRegistrar`,
`ComponentRequirementRegistrar` и macros `REGISTER_*` остаются временным
source-compatibility API и используются только test translation units. Простое
подключение их заголовка не создаёт side effects; production tree не содержит
их экземпляров. Новый SDK/project code должен использовать
`register_component_type`, `register_component_requirement` и type-owned
`register_type()`.

## Не относящиеся к module-owned runtime types

- `SoaRegistrar`/`REGISTER_SOA_TYPE` остаётся неиспользуемым legacy helper для
  низкоуровневого archetype registry; production invocations отсутствуют.
- `CollisionWorldAllocatorRegistrar` устанавливает C allocator hooks для
  collision subsystem и не регистрирует component/pass/inspect runtime type.
- Function-local `static bool registered` в отдельных bindings/runtime adapters
  является idempotency guard, а не constructor-driven registration. Его
  дальнейшая унификация относится к lifecycle соответствующих подсистем, не к
  module ownership.
