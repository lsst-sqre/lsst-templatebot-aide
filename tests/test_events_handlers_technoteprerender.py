"""Test for the technote prerender handler."""

from typing import List

from templatebotaide.events.handlers.technoteprerender import propose_number


def test_initial_document() -> None:
    numbers: List[int] = []
    assert propose_number(numbers) == 1


def test_filling_hole() -> None:
    numbers = [1, 2, 4]
    assert propose_number(numbers) == 3


def test_filling_initial_hole() -> None:
    numbers = [2, 4]
    assert propose_number(numbers) == 1


def test_assign_next() -> None:
    numbers = [1, 2, 3]
    assert propose_number(numbers) == 4
