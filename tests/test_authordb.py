"""tests for the authordb storage module."""

from __future__ import annotations

from pathlib import Path

import pytest

from templatebotaide.storage.authordb import AuthorDb


@pytest.fixture
def author_db_yaml() -> str:
    """Return the path to a sample authordb.yaml file."""
    return (Path(__file__).parent / "data" / "authordb.yaml").read_text()


def test_from_yaml(author_db_yaml: str) -> None:
    author_db = AuthorDb.from_yaml(author_db_yaml)

    # Assert that the AuthorDb object is created correctly
    author = author_db.get_author("sickj")
    assert author.family_name == "Sick"
    assert author.given_name == "Jonathan"
    assert author.orcid == "https://orcid.org/0000-0003-3001-676X"
    assert author.affiliation_id == "RubinObs"
    assert author.author_id == "sickj"
    assert (
        author.affiliation_address
        == "950 N. Cherry Ave., Tucson, AZ 85719, USA"
    )
    assert author.affiliation_name == "Rubin Observatory Project Office"
