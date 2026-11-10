# Scene Extensions

`tc_scene_extension` позволяет подключать stateful-модули к сцене без изменения core-структур.

## Что даёт extension-слой

- Отдельный реестр типов расширений.
- Экземпляры расширений на конкретных сценах.
- Хук `update` и нотификации регистрации/удаления компонентов.
- Сериализация/десериализация по `persistence_key`.

## Базовый поток работы

Реестр типов живёт столько же, сколько процесс runtime. Его создаёт только
канонический `tc_init`/`bootstrap_runtime`, а уничтожает `tc_shutdown` после
закрытия всех сцен. `EngineCore` реестром не владеет. Регистрация или attach до
явного bootstrap завершаются ошибкой и не создают реестр лениво.

### 1. Зарегистрировать тип

```c
tc_scene_ext_type_id type_id = tc_scene_ext_register(&(tc_scene_ext_type_desc){
    .name = "MyExtension",
    .persistence_key = "my_ext",
    .create = my_ext_create,
    .destroy = my_ext_destroy,
    .on_scene_update = my_ext_update,
    .on_component_registered = my_ext_component_registered,
    .on_component_unregistering = my_ext_component_unregistering,
    .serialize = my_ext_serialize,
    .deserialize = my_ext_deserialize,
});
```

### 2. Подключить к сцене

```c
tc_scene_ext_attach(scene, type_id);
```

### 3. Получить instance

```c
void* ext = tc_scene_ext_get(scene, type_id);
```

### 4. Отключить

```c
tc_scene_ext_detach(scene, type_id);
// или отключить все:
tc_scene_ext_detach_all(scene);
```

## Хуки расширения

| Хук | Когда вызывается |
|-----|-----------------|
| `on_scene_update(ext, dt, userdata)` | В конце `tc_scene_update`, после update компонентов |
| `on_component_registered(ext, component, userdata)` | После индексации нового компонента |
| `on_component_unregistering(ext, component, userdata)` | Перед снятием component/capability indexes |
| `serialize(ext, out_data, userdata)` | При сериализации сцены |
| `deserialize(ext, in_data, userdata)` | При десериализации сцены |

## Формат сериализации

Сериализация сцены формирует словарь, где ключ — `persistence_key` расширения:

```json
{
  "my_ext": { ... },
  "physics": { ... }
}
```

## Когда использовать

Extensions подходят для систем, которые:

- Работают на уровне всей сцены, а не отдельной сущности.
- Имеют собственное состояние, которое нужно сохранять.
- Должны обновляться каждый кадр.

Примеры: физический мир, навигационная сетка, аудио-менеджер, система частиц.

## Scheduling update hooks

An attached `on_scene_update` callback is a continuous update consumer by
default. This preserves existing extension lifecycle semantics in event-driven
hosts. An extension which only synchronizes state on requested updates may set
`requires_continuous_update` in its vtable. Returning false lets the editor
sleep; the update callback still runs whenever the scene is updated. Collision
transform synchronization uses this contract because it has no independent
clock.

If this predicate changes while the scene is otherwise idle, call
`tc_scene_notify_work_changed(scene)` on the owner thread. Attach/detach and
component lifecycle changes notify the owner automatically. Reading
`tc_scene_get_work_state` does not consume a render request. Temporary owners
can pair `tc_scene_acquire_update_request` and `tc_scene_release_update_request`
to keep updates active; use the C++ `SceneUpdateRequest` RAII owner when possible.
