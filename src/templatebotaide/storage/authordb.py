"""Storage interface for lsst-texmf's authordb.yaml file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict

import aiohttp
import yaml
from pydantic import BaseModel, Field, RootModel
from pylatexenc.latex2text import LatexNodes2Text


class AuthorDbAuthor(BaseModel):
    """Model for an author entry in author.yaml file."""

    name: str = Field(description="Author's family name")

    initials: str = Field(description="Author's given name")

    affil: list[str] = Field(default_factory=list, description="Affiliations")

    orcid: str | None = Field(
        default=None,
        description="Author's ORCiD identifier (optional)",
    )


class AuthorDbAuthors(RootModel):
    """Model for the authors mapping in authordb.yaml file."""

    root: Dict[str, AuthorDbAuthor]

    def __getitem__(self, author_id: str) -> AuthorDbAuthor:
        """Get an author entry by ID."""
        return self.root[author_id]


class AuthorDbYaml(BaseModel):
    """Model for the authordb.yaml file in lsst/lsst-texmf."""

    affiliations: dict[str, str] = Field(
        description=(
            "Mapping of affiliation IDs to affiliation names. Affiliations "
            "are their name, a comma, and thier address."
        )
    )

    authors: AuthorDbAuthors = Field(
        description="Mapping of author IDs to author information"
    )


@dataclass
class AuthorInfo:
    """Consolidated author information."""

    author_id: str
    given_name: str
    family_name: str
    orcid: str
    affiliation_name: str
    affiliation_id: str
    affiliation_address: str

    @classmethod
    def create_from_db(
        cls,
        author_id: str,
        db_author: AuthorDbAuthor,
        db_affils: dict[str, str],
    ) -> AuthorInfo:
        """Create an AuthorInfo from an AuthorDbAuthor and affiliations."""
        # Transform orcid path to a full orcid.org URL
        if db_author.orcid:
            if db_author.orcid.startswith("http"):
                orcid = db_author.orcid
            else:
                orcid = f"https://orcid.org/{db_author.orcid}"
        else:
            orcid = ""

        # Transform the first affiliation
        if db_author.affil:
            affiliation_id = db_author.affil[0]
            affil = db_affils[affiliation_id]
            parts = affil.split(",")
            affiliation_name = parts[0]
            if len(parts) > 1:
                address_parts = [p.strip() for p in parts[1:]]
                affiliation_address = ", ".join(address_parts)
            else:
                affiliation_address = ""
        else:
            affiliation_id = ""
            affiliation_name = ""
            affiliation_address = ""

        return cls(
            author_id=author_id,
            given_name=Latex(db_author.initials).to_text(),
            family_name=Latex(db_author.name).to_text(),
            orcid=orcid,
            affiliation_name=Latex(affiliation_name).to_text(),
            affiliation_id=affiliation_id,
            affiliation_address=Latex(affiliation_address).to_text(),
        )


class AuthorDb:
    """An interface for the lsst/lsst-texmf authordb.yaml file content."""

    def __init__(self, data: AuthorDbYaml) -> None:
        """Initialize the interface."""
        self._data = data

    @classmethod
    def from_yaml(cls, yaml_data: str) -> AuthorDb:
        """Create an AuthorDb from a string of YAML data."""
        return cls(AuthorDbYaml.model_validate(yaml.safe_load(yaml_data)))

    @classmethod
    async def download(cls) -> AuthorDb:
        """Download a authordb.yaml from GitHub."""
        url = (
            "https://raw.githubusercontent.com/lsst/lsst-texmf"
            "/main/etc/authordb.yaml"
        )
        async with aiohttp.ClientSession() as client:
            async with client.get(url) as response:
                response.raise_for_status()
                yaml_data = await response.text()
        return cls.from_yaml(yaml_data)

    def get_author(self, author_id: str) -> AuthorInfo:
        """Get an author entry by ID."""
        # return self._data.authors[author_id]
        db_author = self._data.authors[author_id]
        db_affiliations = {
            k: self._data.affiliations[k] for k in db_author.affil
        }
        return AuthorInfo.create_from_db(author_id, db_author, db_affiliations)


class Latex:
    """A class for handling LaTeX text content."""

    def __init__(self, tex: str) -> None:
        self.tex = tex

    def to_text(self) -> str:
        """Convert LaTeX to text."""
        text = LatexNodes2Text().latex_to_text(self.tex.strip())
        # Remove running spaces inside the content
        return re.sub(" +", " ", text)
