"""Minimal Pydantic-compatible helpers for offline environments."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, get_args, get_origin

T = TypeVar("T", bound="BaseModel")


class ValidationError(ValueError):
    """Raised when model validation fails."""


@dataclass
class _FieldInfo:
    default: Any = None
    default_factory: Optional[Any] = None


def Field(*, default: Any = None, default_factory: Optional[Any] = None) -> _FieldInfo:
    return _FieldInfo(default=default, default_factory=default_factory)


_MISSING = object()


class BaseModel:
    __field_defaults__: Dict[str, _FieldInfo] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        annotations = getattr(cls, "__annotations__", {})
        defaults: Dict[str, _FieldInfo] = {}
        for name in annotations:
            value = getattr(cls, name, _MISSING)
            if isinstance(value, _FieldInfo):
                defaults[name] = value
            elif value is not _MISSING:
                defaults[name] = _FieldInfo(default=value)
            else:
                defaults[name] = _FieldInfo(default=_MISSING)
        cls.__field_defaults__ = defaults

    def __init__(self, **data: Any) -> None:
        annotations = getattr(self.__class__, "__annotations__", {})
        for name, info in self.__class__.__field_defaults__.items():
            if name in data:
                value = data.pop(name)
            else:
                if info.default_factory is not None:
                    value = info.default_factory()
                elif info.default is _MISSING:
                    raise ValidationError(f"Missing field '{name}'")
                else:
                    value = info.default
            value = self._convert_value(annotations.get(name), value)
            setattr(self, name, value)
        for name, value in data.items():
            setattr(self, name, value)

    @classmethod
    def _convert_value(cls, annotation: Any, value: Any) -> Any:
        if annotation is None:
            return value
        origin = get_origin(annotation)
        if origin in (list, List):
            inner = get_args(annotation)[0] if get_args(annotation) else Any
            if value is None:
                return []
            return [cls._convert_value(inner, item) for item in value]
        if origin in (Union, Optional):  # type: ignore[name-defined]
            for arg in get_args(annotation):
                if arg is type(None):
                    if value is None:
                        return None
                    continue
                try:
                    return cls._convert_value(arg, value)
                except ValidationError:
                    continue
            return value
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if isinstance(value, annotation):
                return value
            if isinstance(value, dict):
                return annotation(**value)
        return value

    def dict(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        annotations = getattr(self.__class__, "__annotations__", {})
        for name in annotations:
            output[name] = self._serialize(getattr(self, name, None))
        return output

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.dict()
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        return value

    def model_dump_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.dict(), indent=indent, ensure_ascii=ensure_ascii)

    def json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return self.model_dump_json(indent=indent, ensure_ascii=ensure_ascii)

    @classmethod
    def model_validate_json(cls: Type[T], data: str) -> T:
        payload = json.loads(data)
        if isinstance(payload, dict):
            return cls(**payload)
        raise ValidationError("JSON root must be an object")

    @classmethod
    def parse_raw(cls: Type[T], data: str) -> T:
        return cls.model_validate_json(data)

    def model_copy(self: T, *, update: Optional[Dict[str, Any]] = None) -> T:
        payload = self.dict()
        if update:
            payload.update(update)
        return self.__class__(**payload)

    def copy(self: T, update: Optional[Dict[str, Any]] = None) -> T:
        return self.model_copy(update=update)
