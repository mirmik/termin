# C API

Публичные C-заголовки предоставляют доступ к collision системе из любого языка через FFI.

## Заголовки

### `termin_collision/termin_collision.h`

Точка входа библиотеки:

```c
const char* termin_collision_version(void);
void termin_collision_runtime_init(void);
void termin_collision_runtime_shutdown(void);
```

### `physics/tc_collision.h`

Высокоуровневый API через scene handle:

```c
// Обновить позиции всех коллайдеров
void tc_scene_collision_update(tc_scene_handle scene);

// Есть ли коллизии?
int tc_scene_has_collisions(tc_scene_handle scene);

// Количество пар столкновений
size_t tc_scene_collision_count(tc_scene_handle scene);

// Обнаружить все столкновения (массив валиден до следующего вызова)
tc_contact_manifold* tc_scene_detect_collisions(tc_scene_handle scene, size_t* out_count);

// Получить manifold по индексу
tc_contact_manifold* tc_scene_get_collision(tc_scene_handle scene, size_t index);
```

#### Структуры данных

```c
typedef struct tc_contact_point {
    double position[3];   // позиция в мировых координатах
    double penetration;   // глубина (отрицательное = пенетрация)
} tc_contact_point;

typedef struct tc_contact_manifold {
    tc_entity_id entity_a;       // первая сущность
    tc_entity_id entity_b;       // вторая сущность
    double normal[3];            // нормаль контакта (от A к B)
    int point_count;             // количество точек (0-4)
    tc_contact_point points[4];  // контактные точки
} tc_contact_manifold;
```

### `physics/tc_collision_world.h`

Низкоуровневый API для управления collision world extension:

```c
// Opaque handle
typedef void tc_collision_world;

// ID типа scene extension
#define TC_SCENE_EXT_TYPE_COLLISION_WORLD UINT64_C(0x636f6c6c6973696f)

// Регистрация аллокатора (вызывается entity_lib при инициализации)
void tc_collision_world_set_allocator(
    tc_collision_world_alloc_fn alloc_fn,
    tc_collision_world_free_fn free_fn
);

// Создание/уничтожение
tc_collision_world* tc_collision_world_new(void);
void tc_collision_world_free(tc_collision_world* cw);

// Инициализация типа extension (idempotent)
void tc_collision_world_extension_init(void);

// Привязка к сцене
tc_collision_world* tc_collision_world_get_scene(tc_scene_handle scene);
bool tc_collision_world_set_scene(tc_scene_handle scene, tc_collision_world* cw);
```

### `collision_world_c.hpp` (C-обёртки для C++ CollisionWorld)

```c
void* tc_collision_world_create(void);
void tc_collision_world_destroy(void* cw);
int tc_collision_world_size(void* cw);
void tc_collision_world_update_all(void* cw);
size_t tc_collision_world_detect_contacts(void* cw, tc_contact_manifold** out_manifolds);
```

## Типичный поток использования (C)

```c
// Инициализация
termin_collision_runtime_init();
tc_collision_world_extension_init();

// Создание сцены (через termin_scene API)
tc_scene_handle scene = tc_scene_new_named("Game");

// Каждый кадр:
tc_scene_collision_update(scene);
size_t count;
tc_contact_manifold* manifolds = tc_scene_detect_collisions(scene, &count);
for (size_t i = 0; i < count; ++i) {
    // Обработка manifolds[i]
}

// Завершение
termin_collision_runtime_shutdown();
```
