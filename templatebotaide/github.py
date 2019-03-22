"""Workflows for GitHub operations common to many handlers.
"""

__all__ = ('create_repo',)


async def create_repo(homepage=None, description=None, *, org_name, repo_name,
                      app, logger):
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
        'name': repo_name,
        # We want an empty repo for the render step.
        'auto_init': False,
        # Defaults for LSST
        'has_projects': False,
        'has_wiki': False
    }
    if homepage is not None:
        data['homepage'] = homepage
    if description is not None:
        data['description'] = description
    logger.info('creating repo', request_data=data)
    ghclient = app['templatebot-aide/gidgethub']
    response = await ghclient.post(
        '/orgs{/org_name}/repos',
        url_vars={'org_name': org_name},
        data=data)
    return response
