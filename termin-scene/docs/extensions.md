# Scene Extensions

`tc_scene_extension` позволяет подключать stateful-модули к сцене без изменения core-структур.

## Что даёт extension-слой

- Отдельный реестр типов расширений.
- Экземпляры расширений на конкретных сценах.
- Хуки `update` / `before_render`, вызываемые в потоке кадра.
- Сериализация/десериализация по `persistence_key`.

## Базовый поток работы

### 1. Зарегистрировать тип

```c
tc_scene_ext_type_id type_id = tc_scene_ext_register(&(tc_scene_ext_type_desc){
    .name = "MyExtension",
    .persistence_key = "my_ext",
    .create = my_ext_create,
    .destroy = my_ext_destroy,
    .on_scene_update = my_ext_update,
    .on_scene_before_render = my_ext_before_render,
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
| `on_scene_before_render(ext, userdata)` | В конце `tc_scene_before_render` |
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
