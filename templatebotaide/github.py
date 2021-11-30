"""Workflows for GitHub operations common to many handlers."""

import urllib

__all__ = [
    "create_repo",
    "get_authenticated_user",
    "add_auth_to_remote",
    "create_pr",
]


async def create_repo(
    homepage=None,
    description=None,
    allow_squash_merge=False,
    allow_merge_commit=True,
    allow_rebase_merge=False,
    delete_branch_on_merge=True,
    *,
    org_name,
    repo_name,
    app,
    logger,
):
    """Create a new repository on GitHub.

    This function wraps the `/orgs{/org_name}/repos
    <https://developer.github.com/v3/repos/#create>`__ GitHub API.

    Parameters
    ----------
    org_name : `str`
        Name of a GitHub organization.
    repo_name : `str`
        Name of the repository that's being created.
    app : `aiohttp.web.Application`
        The App instance.
    logger
        A `structlog` logger instance.

    Returns
    -------
    response : `dict`
        The response from the GitHub API. See the linked API documentation.

    Raises
    ------
    gidgethub.GitHubException
        Raised if there is an error using the GitHub API.
    """
    # Construct arguments to GitHub
    data = {
        "name": repo_name,
        # We want an empty repo for the render step.
        "auto_init": False,
        # Defaults for LSST
        "has_projects": False,
        "has_wiki": False,
        "allow_squash_merge": allow_squash_merge,
        "allow_merge_commit": allow_merge_commit,
        "allow_rebase_merge": allow_rebase_merge,
        "delete_branch_on_merge": delete_branch_on_merge,
    }
    if homepage is not None:
        data["homepage"] = homepage
    if description is not None:
        data["description"] = description
    logger.info("creating repo", request_data=data)
    ghclient = app["templatebot-aide/gidgethub"]
    response = await ghclient.post(
        "/orgs{/org_name}/repos", url_vars={"org_name": org_name}, data=data
    )
    return response


async def get_authenticated_user(*, app, logger):
    """Get information about the authenticated GitHub user.

    This function wraps the `GET /user
    <https://developer.github.com/v3/users/#get-the-authenticated-user>`_
    method.

    Parameters
    ----------
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Returns
    -------
    response : `dict`
        The parsed JSON response body from GitHub.
    """
    ghclient = app["templatebot-aide/gidgethub"]
    response = await ghclient.getitem("/user")
    return response


def add_auth_to_remote(*, remote, app):
    """Add username and password authentication to the URL of a GitPython
    remote.

    Parameters
    ----------
    remote
        A GitPython remote instance.
    app : `aiohttp.web.Application`
        The app instance, for configuration.

    Returns
    -------
    remote
        The modified remote instance (same as the parameter).
    """
    # Modify the repo URL to include auth info in the netloc
    # <user>:<token>@github.com
    bottoken = app["templatebot-aide/githubToken"]
    botuser = app["templatebot-aide/githubUsername"]

    remote_url = [u for u in remote.urls][0]
    url_parts = urllib.parse.urlparse(remote_url)
    authed_url_parts = list(url_parts)
    # The [1] index is the netloc.
    authed_url_parts[1] = f"{botuser}:{bottoken}@{url_parts[1]}"
    authed_remote_url = urllib.parse.urlunparse(authed_url_parts)
    remote.set_url(authed_remote_url, old_url=remote_url)

    return remote


async def create_pr(
    maintainer_can_modify=True,
    draft=False,
    *,
    owner,
    repo,
    head,
    base,
    title,
    body,
    app,
    logger,
):
    """Create a GitHub pull request.

    This function wraps `POST /repos/:owner/:repo/pulls
    <https://developer.github.com/v3/pulls/#create-a-pull-request>`_.

    Parameters
    ----------
    owner : `str`
        The owner or organization name.
    repo : `str`
        The name of the repository.
    title : `str`
        The title of the pull request.
    body : `str`
        The content of the pull request message. This message can be
        formatted with GitHub-flavored markdown.
    head : `str`
        The head of the pull request (the name of a branch). To create a
        pull request from a fork, use the syntax ``username:branch``.
    base : `str`
        The name of the branch to merge ``head`` into.

    Returns
    -------
    response : `dict`
        The parsed JSON response body from GitHub.
    """
    url_vars = {"owner": owner, "repo": repo}
    data = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "maintainer_can_modify": maintainer_can_modify,
        "draft": draft,
    }
    ghclient = app["templatebot-aide/gidgethub"]
    response = await ghclient.post(
        "/repos{/owner}{/repo}/pulls", url_vars=url_vars, data=data
    )
    return response
