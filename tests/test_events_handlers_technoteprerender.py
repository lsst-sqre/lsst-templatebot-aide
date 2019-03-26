"""Test for the technote prerender handler.
"""

from templatebotaide.events.handlers.technoteprerender import propose_number


def test_initial_document():
    numbers = []
    assert propose_number(numbers) == 1


def test_filling_hole():
    numbers = [1, 2, 4]
    assert propose_number(numbers) == 3


def test_filling_initial_hole():
    numbers = [2, 4]
    assert propose_number(numbers) == 1


def test_assign_next():
    numbers = [1, 2, 3]
    assert propose_number(numbers) == 4
