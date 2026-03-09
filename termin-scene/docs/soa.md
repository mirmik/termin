# SoA и архетипы

SoA-слой хранит data-only компоненты в плотном формате и группирует сущности по `type_mask`.

## Регистрация SoA-типа

```c
tc_soa_type_id id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
    .name = "Velocity",
    .element_size = sizeof(Velocity),
    .init = NULL,
    .destroy = NULL
});
```

Ограничение: максимум 64 типа (`TC_SOA_MAX_TYPES`).

## Добавление и удаление

```c
tc_entity_pool_add_soa(pool, entity, type_id);
tc_entity_pool_remove_soa(pool, entity, type_id);
```

Эти операции меняют `type_mask` сущности и, при необходимости, переносят её между архетипами (миграция).

## Доступ к данным сущности

| Функция | Описание |
|---------|----------|
| `tc_entity_pool_has_soa(pool, entity, type_id)` | Есть ли SoA-данные этого типа |
| `tc_entity_pool_get_soa(pool, entity, type_id)` | Указатель на данные |
| `tc_entity_pool_soa_mask(pool, entity)` | Текущая type_mask сущности |

## Query по архетипам

`tc_soa_query` фильтрует архетипы по `required_mask` и `excluded_mask` и возвращает chunk:

```c
tc_soa_query_result result;
while (tc_soa_query_next(pool, &query, &result)) {
    // result.entities  — массив entity_id
    // result.data[i]   — массив данных для i-го required типа
    // result.count      — количество сущностей в chunk
}
```

## Когда использовать

| Задача | Подход |
|--------|--------|
| Массовые проходы по однотипным данным (физика, AI) | SoA-архетипы |
| Lifecycle-поведение (start/update/render) | Object-компоненты |
| Смешанная логика | Оба: SoA для данных, object-компонент для управления |
