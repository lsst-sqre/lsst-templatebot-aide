"""Common handler workflows and other utilities."""

import asyncio
import re
from tempfile import TemporaryDirectory
from typing import Any, Dict

import git
from aiohttp.web import Application
from structlog.stdlib import BoundLogger

from templatebotaide import github

__all__ = ["pr_latex_submodules", "clean_string_whitespace"]


async def pr_latex_submodules(
    *, event: Dict[str, Any], app: Application, logger: BoundLogger
) -> Dict[str, Any]:
    """Create a GitHub Pull Request that adds the lsst-texmf submodule.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-postrender`` event's message.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    """
    github_repo_url = event["github_repo"]
    github_repo_url_parts = event["github_repo"].split("/")
    repo_owner = github_repo_url_parts[-2]
    repo_name = github_repo_url_parts[-1]
    ltd_slug = "-".join(
        (
            event["variables"]["series"].lower(),
            event["variables"]["serial_number"],
        )
    )
    ltd_url = f"https://{ltd_slug}.lsst.io"

    # The comitter is the bot
    github_user = await github.get_authenticated_user(app=app, logger=logger)
    author = git.Actor(github_user["name"], github_user["email"])

    with TemporaryDirectory() as tmpdir_name:
        repo = git.Repo.clone_from(github_repo_url, to_path=tmpdir_name)

        # Since we cloned from GitHub, the first origin should be GitHub
        origin = repo.remotes[0]
        origin = github.add_auth_to_remote(remote=origin, app=app)

        # Create the branch
        new_branch_name = f"u/{app['templatebot-aide/githubUsername']}/config"
        new_branch = repo.create_head(new_branch_name)
        new_branch.checkout()

        # Add the lsst-texmf submodule
        repo.create_submodule(
            "lsst-texmf",
            path="lsst-texmf",
            url="https://github.com/lsst/lsst-texmf.git",
            branch="main",
            depth=1,
        )
        repo.index.commit(
            "Add lsst-texmf submodule", author=author, committer=author
        )
        origin.push(refspec=f"{new_branch_name}:{new_branch_name}")

        # Ensure GitHub can register the new branch before submitting a PR
        await asyncio.sleep(10.0)

        # Create PR
        if ltd_url.endswith("/"):
            ltd_url.rstrip("/")
        branch_url = ltd_url + "/v/" + new_branch_name.replace("/", "-")
        dashboard_url = ltd_url + "/v"
        pr_body = (
            "This pull request adds the "
            "[lsst-texmf](https://lsst-texmf.lsst.io) submodule.\n\n"
            f"You should see the doc online at {branch_url} (once this branch "
            "is built by GitHub Actions).\n\nThe edition dashboard is: "
            f"{dashboard_url}.\n\nThis PR is automatically generated. Feel "
            "free to update this PR or the underlying branch if there's an "
            "issue."
        )
        pr_response = await github.create_pr(
            owner=repo_owner,
            repo=repo_name,
            title="Add lsst-texmf submodule",
            body=pr_body,
            head=new_branch_name,
            base="main",
            app=app,
            logger=logger,
        )

        logger.debug("Finished pushing lsst-texmf PR", branch=new_branch_name)

    return pr_response


def clean_string_whitespace(text: str) -> str:
    """Clean whitespace from text that should only be a single paragraph.

    1. Apply ``str.strip`` method
    2. Apply regular expression substitution of the ``\\s`` whitespace
       character group with `` `` (a single whitespace).
    """
    text = text.strip()
    text = re.sub(r"\s", " ", text)  # replace all kinds of whitespace
    return text
