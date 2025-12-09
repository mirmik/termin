# Project Rules

## Code Style

### Attribute Access
Methods `getattr`, `hasattr`, and `setattr` are only allowed in contexts where the algorithm explicitly requires reflection (e.g., serialization, deserialization, dynamic dispatch).

In all other cases, all required fields must be explicitly declared in the class. Write code as if this were C++, not Python — all attributes must exist and be initialized in `__init__` or as class-level defaults.

Bad:
```python
value = getattr(obj, 'foo', None) or default
if hasattr(obj, 'bar'):
    do_something(obj.bar)
```

Good:
```python
class MyClass:
    foo: str = "default"
    bar: int = 0

    def __init__(self, foo: str = "default", bar: int = 0):
        self.foo = foo
        self.bar = bar

# Then simply:
value = obj.foo
do_something(obj.bar)
```
