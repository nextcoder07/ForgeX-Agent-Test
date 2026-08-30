"""
Canonical Enum and String Normalization Utilities.
Safely converts Python Enum objects, strings, None, or custom types into clean primitive strings.
"""
from typing import Any, Optional


def normalize_enum_value(value: Any, default: Optional[str] = None) -> Optional[str]:
    """
    Normalizes any Enum, string, or primitive value into a clean string representation.
    - Enum -> value.value
    - str -> str
    - None -> default
    - custom -> str(value)
    """
    if value is None:
        return default
    if hasattr(value, "value"):
        val = value.value
        return str(val) if val is not None else default
    if isinstance(value, str):
        return value
    return str(value)
