# Plan: Унификация tc_inspect

## Текущая проблема

Дублирование данных:
- `tc_field_desc` (C) хранит path, label, kind, min/max/step, choices...
- `InspectFieldInfo` (C++) хранит то же самое + getter/setter

## Цель

Вся информация о полях хранится в C API (`tc_inspect.h`).
InspectRegistry исчезает или становится тонкой обёрткой.

## Шаг 1: Language slots для vtable

Аналогично tc_kind, добавляем slots для разных языков:

```c
// tc_inspect.h

typedef enum {
    TC_INSPECT_LANG_C = 0,
    TC_INSPECT_LANG_CPP = 1,
    TC_INSPECT_LANG_PYTHON = 2,
    TC_INSPECT_LANG_COUNT = 3
} tc_inspect_lang;

// Vtable для одного языка
typedef struct tc_field_vtable {
    tc_value (*get)(void* obj, const tc_field_desc* field, void* user_data);
    void (*set)(void* obj, const tc_field_desc* field, tc_value value, void* user_data);
    void (*action)(void* obj, const tc_field_desc* field, void* user_data);
    void* user_data;
} tc_field_vtable;

// Расширенный field descriptor с per-field vtable slots
typedef struct tc_field_desc {
    const char* path;
    const char* label;
    const char* kind;
    double min, max, step;
    bool is_serializable;
    bool is_inspectable;
    const tc_enum_choice* choices;
    size_t choice_count;

    // Language-specific access (per-field, not per-type)
    tc_field_vtable lang[TC_INSPECT_LANG_COUNT];
} tc_field_desc;
```

## Шаг 2: Регистрация полей из разных языков

```c
// C API для регистрации поля
TC_API void tc_inspect_register_field(
    const char* type_name,
    const tc_field_desc* field
);

// Регистрация vtable для конкретного поля и языка
TC_API void tc_inspect_set_field_vtable(
    const char* type_name,
    const char* field_path,
    tc_inspect_lang lang,
    const tc_field_vtable* vtable
);
```

## Шаг 3: C++ обёртка (без дублирования)

```cpp
// cpp/termin/inspect/tc_inspect_cpp.hpp

namespace tc {

// Тонкая обёртка - не хранит данные, только конвертирует
class InspectCpp {
public:
    // Регистрация C++ поля - создаёт tc_field_desc и vtable
    template<typename C, typename T>
    static void register_field(
        const char* type_name,
        T C::*member,
        const char* path,
        const char* label,
        const char* kind
    ) {
        // 1. Создать tc_field_desc
        tc_field_desc desc = {};
        desc.path = intern(path);  // интернирование строк
        desc.label = intern(label);
        desc.kind = intern(kind);
        desc.is_serializable = true;
        desc.is_inspectable = true;

        // 2. Зарегистрировать в C API
        tc_inspect_register_field(type_name, &desc);

        // 3. Создать C++ vtable с type erasure
        static auto getter = [](void* obj, const tc_field_desc* f, void* ud) -> tc_value {
            auto member_ptr = *static_cast<T C::**>(ud);
            T& value = static_cast<C*>(obj)->*member_ptr;
            return cpp_to_tc_value(value);  // конвертация T → tc_value
        };

        static auto setter = [](void* obj, const tc_field_desc* f, tc_value v, void* ud) {
            auto member_ptr = *static_cast<T C::**>(ud);
            static_cast<C*>(obj)->*member_ptr = tc_value_to_cpp<T>(v);
        };

        // Сохраняем member pointer
        static T C::* stored_member = member;

        tc_field_vtable vtable = {};
        vtable.get = getter;
        vtable.set = setter;
        vtable.user_data = &stored_member;

        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_CPP, &vtable);
    }
};

} // namespace tc
```

## Шаг 4: Python обёртка

```cpp
// cpp/termin/inspect/tc_inspect_python.hpp

namespace tc {

class InspectPython {
public:
    // Регистрация Python поля
    static void register_field(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        nb::object py_getter,
        nb::object py_setter
    ) {
        // 1. Проверить существует ли field, если нет - создать
        if (!tc_inspect_find_field(type_name, path)) {
            tc_field_desc desc = {};
            desc.path = path;
            desc.label = label;
            desc.kind = kind;
            tc_inspect_register_field(type_name, &desc);
        }

        // 2. Сохранить Python callbacks (prevent GC)
        auto* ctx = new PythonFieldContext{py_getter, py_setter};

        // 3. Создать Python vtable
        tc_field_vtable vtable = {};
        vtable.get = python_field_getter;  // статическая функция
        vtable.set = python_field_setter;
        vtable.user_data = ctx;

        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_PYTHON, &vtable);
    }
};

} // namespace tc
```

## Шаг 5: Унифицированный доступ

```c
// tc_inspect.h

// Получить значение поля (пробует языки по приоритету)
TC_API tc_value tc_inspect_get(void* obj, const char* type_name, const char* path);

// Получить значение через конкретный язык
TC_API tc_value tc_inspect_get_lang(
    void* obj,
    const char* type_name,
    const char* path,
    tc_inspect_lang lang
);
```

## Шаг 6: Что удаляется

1. `InspectFieldInfo` struct - больше не нужен
2. `InspectRegistry::_py_fields` - данные в C API
3. `InspectRegistry::_type_backends` - определяется наличием vtable
4. `InspectRegistry::_type_parents` - уже есть в `tc_type_desc.base_type`
5. Большая часть методов InspectRegistry

## Шаг 7: Что остаётся в C++ слое

```cpp
// Тонкие обёртки для удобства
namespace tc {

// Конвертация tc_value ↔ C++ types
template<typename T> T tc_value_to_cpp(const tc_value& v);
template<typename T> tc_value cpp_to_tc_value(const T& v);

// Конвертация tc_value ↔ nb::object
tc_value nb_to_tc_value(nb::object obj);
nb::object tc_value_to_nb(const tc_value* v);

// Конвертация tc_value ↔ trent
tc_value trent_to_tc_value(const nos::trent& t);
nos::trent tc_value_to_trent(const tc_value* v);

// Макросы регистрации (используют InspectCpp внутри)
#define INSPECT_FIELD(cls, field, label, kind) \
    inline static auto _reg_##field = InspectCpp::register_field<cls>( \
        #cls, &cls::field, #field, label, kind);

} // namespace tc
```

## Результат

```
core_c/ (чистый C)
├── tc_inspect.h      - ВСЯ метаинформация о полях
├── tc_inspect.c      - registry, get/set через vtable
├── tc_kind.h         - сериализация по языкам
└── tc_kind.c

cpp/termin/inspect/ (тонкие обёртки)
├── tc_inspect_cpp.hpp    - register_field<C,T>, конвертация
├── tc_inspect_python.hpp - Python vtable, nb::object конвертация
├── tc_kind_cpp.hpp       - C++ kind handlers
└── tc_kind_python.hpp    - Python kind handlers
```

## Порядок реализации

1. [x] Добавить `tc_inspect_lang` enum и `tc_field_vtable` в tc_inspect.h
2. [x] Изменить `tc_field_desc` - добавить per-field vtable slots
3. [x] Добавить `tc_inspect_add_field`, `tc_inspect_set_field_vtable`
4. [x] Обновить `tc_inspect.c` с новой реализацией
5. [x] Обновить тесты под новый API
6. [x] Создать `tc_inspect_cpp.hpp` с template регистрацией
7. [x] Создать `tc_inspect_python.hpp` с Python регистрацией
8. [ ] Мигрировать существующий код с InspectRegistry на новый API
9. [ ] Удалить InspectRegistry и InspectFieldInfo
