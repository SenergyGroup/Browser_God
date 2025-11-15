"""Lightweight subset of Pydantic features required for the test harness."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class _MissingType:
    pass


_MISSING = _MissingType()


class FieldInfo:
    def __init__(self, default: Any = _MISSING, *, default_factory: Optional[Callable[[], Any]] = None, const: bool = False) -> None:
        self.default = default
        self.default_factory = default_factory
        self.const = const


def Field(default: Any = _MISSING, *, default_factory: Optional[Callable[[], Any]] = None, const: bool = False) -> FieldInfo:
    return FieldInfo(default=default, default_factory=default_factory, const=const)


def model_validator(*, mode: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(self: Any) -> Any:
            return func(type(self), self)

        wrapper.__model_validator_config__ = {"mode": mode}
        wrapper.__original_validator__ = func
        return wrapper

    return decorator


class ModelMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: Dict[str, Any]) -> "ModelMeta":
        annotations = namespace.get("__annotations__", {})
        field_defaults: Dict[str, Any] = {}
        for base in bases:
            field_defaults.update(getattr(base, "__field_defaults__", {}))
        for field in annotations:
            if field in namespace:
                field_defaults[field] = namespace[field]
        validators: List[Callable[[Any], Any]] = []
        for base in bases:
            validators.extend(getattr(base, "__model_validators__", []))
        for value in namespace.values():
            config = getattr(value, "__model_validator_config__", None)
            if config and config.get("mode") == "after":
                validators.append(value)
        namespace["__field_defaults__"] = field_defaults
        namespace["__model_validators__"] = validators
        return super().__new__(mcls, name, bases, namespace)


class BaseModel(metaclass=ModelMeta):
    __field_defaults__: Dict[str, Any]
    __model_validators__: List[Callable[[Any], Any]]

    def __init__(self, **data: Any) -> None:
        cls = type(self)
        annotations: Dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))
        defaults: Dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            defaults.update(getattr(base, "__field_defaults__", {}))
        for field in annotations:
            value = data.pop(field, _MISSING)
            default = defaults.get(field, _MISSING)
            if value is _MISSING:
                if isinstance(default, FieldInfo):
                    if default.default_factory is not None:
                        value = default.default_factory()
                    elif default.default is not _MISSING:
                        value = default.default
                    else:
                        value = None
                elif default is not _MISSING:
                    value = default
                else:
                    value = None
            setattr(self, field, value)
        if data:
            for key, value in data.items():
                setattr(self, key, value)
        for validator in cls.__model_validators__:
            validator(self)

    def model_dump(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        annotations: Dict[str, Any] = {}
        for base in reversed(type(self).__mro__):
            annotations.update(getattr(base, "__annotations__", {}))
        for field in annotations:
            value = getattr(self, field)
            result[field] = self._serialize(value)
        return result

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, list):
            return [BaseModel._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: BaseModel._serialize(val) for key, val in value.items()}
        return value

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        fields = ", ".join(f"{k}={getattr(self, k)!r}" for k in self.__annotations__)
        return f"{type(self).__name__}({fields})"


__all__ = ["BaseModel", "Field", "model_validator"]
