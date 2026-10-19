"""Suggestions are hints, never accepted names (confirm.md A5)."""

import pytest

from apkverify.suggest import suggestion


@pytest.mark.parametrize(
    "name,candidates,expected",
    [
        ("home_bottom", ["home_botto"], " Gần giống: 'home_botto'."),
        ("home_bottom", ["home_bottom"], ""),
        ("home_bottom", ["unrelated"], ""),
        ("home_bottom", [], ""),
        ("home_bottom", ["Home_bottom"], " Gần giống: 'Home_bottom'."),
    ],
)
def test_suggestion(name: str, candidates: list[str], expected: str) -> None:
    assert suggestion(name, iter(candidates)) == expected
