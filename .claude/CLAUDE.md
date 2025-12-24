# Project Rules

## Debugging

Debug prints are allowed for investigating issues.

## Code Style

### No Speculative Code
No fallbacks, backwards compatibility, or special cases "just in case". Add them only when there is a proven, specific need. If something doesn't work, find the root cause instead of adding workarounds.

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

### C++ Class Layout

All fields (public, protected, private) must be declared at the top of the class, before any methods. Group fields first, then methods.

```cpp
class MyClass {
public:
    // Public fields first
    int public_field = 0;
    std::string name;

private:
    // Private fields
    int _private_field = 0;
    bool _initialized = false;

public:
    // Then methods
    MyClass();
    void do_something();

private:
    void _helper();
};
```

### C++ Migration

When migrating Python classes to C++, do not leave Python wrappers. Python modules should contain only re-exports from `termin._native`.

Bad:
```python
# Don't wrap C++ classes in Python
from termin._native import _CppClass

class MyClass:
    def __init__(self):
        self._impl = _CppClass()

    def method(self):
        return self._impl.method()
```

Good:
```python
# Just re-export
from termin._native import MyClass

__all__ = ["MyClass"]
```

If additional Python-only functionality is needed (e.g., exception classes), keep it minimal alongside the re-exports.
