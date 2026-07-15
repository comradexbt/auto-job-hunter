"""Shared helpers for configuration, display, and runtime control."""
import json
import time
from collections.abc import Callable
from typing import Optional, TypeVar

T = TypeVar("T")


def read_json(path: str):
    """Read and decode a JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_json(path: str, fallback: T, error_prefix: str = "") -> T:
    """Read JSON, returning a fallback for missing or invalid files."""
    try:
        return read_json(path)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        if error_prefix:
            print(f"{error_prefix}: {error}")
        return fallback


def save_json(path: str, data: object, error_prefix: str) -> bool:
    """Write JSON and report whether the operation succeeded."""
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except (OSError, TypeError, ValueError) as error:
        print(f"{error_prefix}: {error}")
        return False


def pop_one_based(items: list[T], value: str) -> tuple[Optional[T], Optional[str]]:
    """Remove an item selected by a one-based user-facing index."""
    try:
        index = int(value) - 1
    except ValueError:
        return None, "❌ Please send a valid number!"

    if not 0 <= index < len(items):
        return None, f"❌ Invalid number! Choose 1-{len(items)}"

    return items.pop(index), None


def truncate_text(value: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length, including the suffix."""
    if len(value) <= max_length:
        return value
    return value[: max_length - len(suffix)] + suffix


def interruptible_sleep(
    seconds: float,
    should_continue: Callable[[], bool],
) -> None:
    """Sleep in short increments so shutdown signals can interrupt the wait."""
    deadline = time.monotonic() + seconds
    while should_continue():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1, remaining))
