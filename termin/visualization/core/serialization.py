# serialization.py

COMPONENT_REGISTRY = {}

def serializable(fields):
    def wrapper(cls):
        cls._serializable_fields = fields
        COMPONENT_REGISTRY[cls.__name__] = cls
        return cls
    return wrapper