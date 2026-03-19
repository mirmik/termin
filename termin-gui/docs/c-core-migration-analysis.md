# Анализ: перенос ядра tcgui в C (по модели tc_component)

## Мотивация

tcgui сейчас — чисто Python-фреймворк. В tc_component ядро живёт в C (`tc_component` struct),
а компоненты могут быть написаны на любом языке (C++, Python, C#). Благодаря этому компоненты
из разных языков сосуществуют в одном Entity.

Цель — применить ту же модель к tcgui: C владеет деревом виджетов (layouts, children),
а языковые обёртки держат ссылки на виджеты через `tc_widget*`.

## Текущая архитектура tcgui

- **~35 виджетов** (Label, Button, HStack, VStack, GridLayout, TreeWidget, TableWidget и т.д.)
- **Retained-mode**: дерево виджетов живёт между кадрами
- **Layout**: двухфазный — `compute_size()` → `layout()`, каждый тип виджета реализует свою логику
- **Rendering**: через `UIRenderer`, обёртку над tgfx (OpenGL 330), один шейдер с тремя режимами
- **Event dispatch**: hit-testing по дереву, focus/hover tracking, overlay stack, event bubbling
- **Scene system**: отдельная подсистема (`GraphicsItem`, `GraphicsScene`, `SceneView`)

## Как работает tc_component (для справки)

```c
struct tc_component {
    tc_component_vtable* vtable;       // start, update, on_destroy...
    tc_component_ref_vtable* ref_vtable; // retain, release (Py_INCREF/DECREF)
    void* body;                         // указатель на языковой объект-владелец
    tc_component_kind kind;             // CXX, PYTHON, CSHARP
    tc_language native_language;
    // ...
};
```

- C владеет структурой, язык владеет объектом через `body`
- ref_vtable позволяет C управлять refcount без знания о конкретном языке
- vtable делегирует вызовы (update, render) на сторону языка

## Предлагаемая архитектура tc_widget

### C ядро

```c
typedef struct tc_widget_vtable {
    // Layout
    void (*compute_size)(tc_widget* w, float vp_w, float vp_h, float* out_w, float* out_h);
    void (*layout)(tc_widget* w, float x, float y, float w, float h, float vp_w, float vp_h);

    // Rendering
    void (*render)(tc_widget* w, tc_ui_renderer* renderer);

    // Events
    bool (*on_mouse_down)(tc_widget* w, tc_mouse_event* event);
    void (*on_mouse_move)(tc_widget* w, tc_mouse_event* event);
    void (*on_mouse_up)(tc_widget* w, tc_mouse_event* event);
    bool (*on_mouse_wheel)(tc_widget* w, tc_mouse_wheel_event* event);
    void (*on_mouse_enter)(tc_widget* w);
    void (*on_mouse_leave)(tc_widget* w);
    bool (*on_key_down)(tc_widget* w, tc_key_event* event);
    bool (*on_text_input)(tc_widget* w, tc_text_event* event);
    void (*on_focus)(tc_widget* w);
    void (*on_blur)(tc_widget* w);

    // Hit-testing (опционально, можно дефолтный в C)
    tc_widget* (*hit_test)(tc_widget* w, float px, float py);

    // Lifecycle
    void (*on_destroy)(tc_widget* w);
} tc_widget_vtable;

typedef struct tc_widget {
    tc_widget_vtable* vtable;
    tc_component_ref_vtable* ref_vtable;  // переиспользуем из tc_component
    void* body;                            // Python/C++/C# объект
    tc_language native_language;

    // Дерево
    tc_widget* parent;
    tc_widget** children;
    int children_count;
    int children_capacity;

    // Computed layout (заполняется в layout phase)
    float x, y, width, height;

    // Input properties
    float preferred_width, preferred_height;  // или tc_value с единицами
    int preferred_width_unit, preferred_height_unit;  // px, ndc, percent

    // Flags
    bool visible;
    bool enabled;
    bool focusable;
    bool stretch;
    bool clip;
    bool needs_layout;

    // Идентификация
    const char* name;
    const char* widget_type;  // "button", "hstack", etc.
} tc_widget;
```

### C ядро: UI manager

```c
typedef struct tc_ui {
    tc_widget* root;

    // Overlay stack
    tc_overlay_entry* overlays;
    int overlay_count;

    // Interaction state
    tc_widget* focused_widget;
    tc_widget* hovered_widget;
    tc_widget* pressed_widget;

    // Viewport
    float viewport_w, viewport_h;
} tc_ui;

// API
void tc_ui_set_root(tc_ui* ui, tc_widget* root);
void tc_ui_add_overlay(tc_ui* ui, tc_widget* widget, bool modal, bool dismiss_on_outside);
void tc_ui_remove_overlay(tc_ui* ui, tc_widget* widget);
void tc_ui_process_mouse_move(tc_ui* ui, float x, float y);
void tc_ui_process_mouse_down(tc_ui* ui, float x, float y, int button, int mods);
void tc_ui_process_mouse_up(tc_ui* ui, float x, float y, int button, int mods);
void tc_ui_process_key(tc_ui* ui, int key, int mods);
void tc_ui_process_text(tc_ui* ui, const char* text);
void tc_ui_layout(tc_ui* ui);
void tc_ui_render(tc_ui* ui, tc_ui_renderer* renderer);
```

## Что держать в C, что делегировать

### В C ядре (владение и dispatch):
- Дерево виджетов (parent/children, add/remove)
- Computed-позиции (x, y, width, height)
- Hit-testing — обход дерева по координатам (дефолтная реализация, переопределяемая через vtable)
- Focus/hover tracking
- Overlay stack
- Scissor/clip stack
- Tab navigation

### Через vtable (делегируется языку):
- `compute_size` / `layout` — каждый тип виджета реализует свою логику
- `render` — рисование конкретного виджета
- Все event-handlers (on_mouse_down, on_key_down и т.д.)
- Специфические данные виджета (spacing у HStack, text у Label) остаются на стороне языка

### Опционально встроенные layouts в C:
- `tc_hstack_layout()`, `tc_vstack_layout()`, `tc_grid_layout()` — для производительности
- Языковые виджеты могут использовать их или реализовать свои через vtable

## Аналогия с tc_component

| tc_component | tc_widget |
|---|---|
| vtable (start, update...) | vtable (compute_size, layout, render, events...) |
| ref_vtable (retain, release) | ref_vtable (retain, release) — переиспользуется |
| body (PyObject*) | body (PyObject*) |
| Entity владеет компонентом | parent виджет владеет дочерними |
| add_component_ptr(tc) | tc_widget_add_child(parent, child) |
| tc_component_to_python() | tc_widget_to_python() |
| REGISTER_COMPONENT | REGISTER_WIDGET (опционально) |

## Выигрыш

- Виджет из C++ может быть дочерним виджету из Python (и наоборот)
- Одно дерево, один event dispatch, один layout pass — всё в C
- Производительность: layout/hit-testing в C вместо Python
- Языковые обёртки лёгкие — ссылка на `tc_widget*` + специфические данные

## Сложности и риски

1. **Объём работы**: ~35 виджетов нужно обернуть, но можно делать инкрементально
2. **Свойства виджетов**: у каждого типа свои данные (spacing, text, columns) — они остаются
   на стороне языка, C хранит только общие поля
3. **Отладка**: баги на границе C/Python сложнее, но опыт с tc_component показывает что управляемо
4. **Unit system**: `Value` (px/ndc/%) нужно продублировать в C или хранить только на стороне языка

## Стратегия миграции

1. Определить `tc_widget` struct и C API для дерева (add_child, remove_child)
2. Реализовать `tc_ui` с event dispatch и hit-testing
3. Сделать Python-биндинги (nanobind), обернуть текущий `Widget` класс
4. Портировать базовые контейнеры (HStack, VStack, Panel)
5. Постепенно портировать остальные виджеты
6. На каждом шаге можно смешивать старые Python-only виджеты с новыми tc_widget-based
