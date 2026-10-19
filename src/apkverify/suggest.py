"""Hints never change exact name matching (confirm.md A5)."""

from collections.abc import Iterable
from difflib import get_close_matches


def suggestion(name: str, candidates: Iterable[str]) -> str:
    matches = get_close_matches(name, [c for c in candidates if c != name], n=1, cutoff=0.8)
    return f" Gần giống: '{matches[0]}'." if matches else ""
