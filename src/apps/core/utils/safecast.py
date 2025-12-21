from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


def safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert value to int. Returns default if conversion fails."""
    if value is None:
        return default
    try:
        # Handle floats like 1.0 -> 1
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert value to float. Returns default if conversion fails."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_enum(enum_cls: type[Enum], value: Any, default: Any = None) -> Any:
    """
    Safely convert value to an Enum member.
    Tries matching by value, then name (case-insensitive).
    """
    if value is None:
        return default

    try:
        return enum_cls(value)
    except ValueError:
        pass

    if isinstance(value, str):
        # Try matching by name (case-insensitive)
        value_upper = value.upper()
        # Direct name lookup
        if value in enum_cls.__members__:
            return enum_cls[value]
        # Case insensitive name lookup
        for name, member in enum_cls.__members__.items():
            if name.upper() == value_upper:
                return member

        # Try matching by value (if value is string representation of enum value)
        for member in enum_cls:
            if str(member.value).upper() == value_upper:
                return member

    return default
