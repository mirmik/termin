# C++ Style Guide

## Порядок членов класса

Поля `class` и `struct` располагаются в верхней части определения — перед
конструкторами и методами. Это относится также к статическим полям и bit-fields.

Если полям нужны вложенные типы, `using` или перечисления, их объявления
располагаются перед полями.

Секции `public`, `protected` и `private` можно повторять: сначала идут секции с
полями, затем публичный интерфейс и внутренние методы. Взаимный порядок полей
сохраняется осмысленным и стабильным.

```cpp
class TableModel {
  private:
    std::vector<TableRow> rows_;
    std::unordered_map<TableRowId, size_t> indices_;
    TableRowId next_id_ = 1;
    Signal<TableModel&, const TableChange&> changed_;

  public:
    size_t size() const;
    void set_rows(std::vector<TableRowData> rows);
    void clear();

  private:
    static void validate_row(const TableRowData& row);
    void notify(TableChange change);
};
```

Для простых структур данных поля естественно остаются публичными:

```cpp
struct RenderTargetContext {
    std::string name;
    Rect2i render_rect;
    uint64_t layer_mask = ~uint64_t{0};

    bool has_render_area() const;
};
```
