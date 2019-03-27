"""Workflows for Travis CI.
"""

__all__ = ('activate_travis', 'sync_travis_account', 'make_travis_repo_url',
           'get_current_user')

import asyncio

import uritemplate


def _get_travis_endpoint_type(org=None, slug=None):
    if org is None and slug is None:
        raise ValueError(
            'Either `slug` or `org` must be specified.')
    elif slug is None:
        org = slug.split('/')[0]

    if org in ('lsst', 'lsst-sims'):
        return 'org'
    else:
        return 'com'


def _get_travis_url(slug=None, org=None):
    """Get the right API host (.org or .com) for different LSST GitHub
    organizations.

    Returns
    -------
    url : `str`
        The API URL, either ``https://api.travis-ci.org`` or
        ``https://api.travis-ci.com``
    """
    if _get_travis_endpoint_type(org=org, slug=slug) == 'com':
        return 'https://api.travis-ci.com'
    else:
        return 'https://api.travis-ci.org'


def _get_travis_token(*, app, org=None, slug=None):
    if _get_travis_endpoint_type(org=org, slug=slug) == 'com':
        return app['templatebot-aide/travisTokenCom']
    else:
        return app['templatebot-aide/travisToken']


def make_travis_headers(*, token):
    return {
        'Travis-API-Version': '3',
        'User-Agent': 'lsst-templatebot-aide',
        'Authorization': 'token ' + token
    }


async def activate_travis(*, slug, app, logger):
    """Activate Travis CI for a repository.

    Parameters
    ----------
    slug : `str`
        The repo's GitHub slug. This determines whether the "com" or "org"
        endpoint is used.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Returns
    -------
    data : `dict`
        A repository payload:
        https://developer.travis-ci.org/resource/repository
    """
    host = _get_travis_url(slug=slug)
    headers = make_travis_headers(token=_get_travis_token(app=app, slug=slug))
    http_session = app['api.lsst.codes/httpSession']

    url = uritemplate.expand(
        host + '/repo{/slug}/activate',
        slug=slug
    )
    async with http_session.post(url, headers=headers) as response:
        response_data = await response.json()
        logger.debug(
            'Activating repository',
            slug=slug,
            url=response.url,
            status=response.status,
            message=response_data)


async def get_current_user(*, slug, app, logger):
    """Get information about the logged-in Travis user.

    Parameters
    ----------
    slug : `str`
        The repo's GitHub slug. This determines whether the "com" or "org"
        endpoint is used.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Returns
    -------
    data : `dict`
        The payload is documented at
        https://developer.travis-ci.org/resource/user#current
    """
    host = _get_travis_url(slug=slug)
    headers = make_travis_headers(token=_get_travis_token(app=app, slug=slug))
    http_session = app['api.lsst.codes/httpSession']

    url = host + '/user'
    async with http_session.get(url, headers=headers) as response:
        data = await response.json()
        logger.debug('Got Travis user data', data=data)
        return data


async def sync_travis_account(*, slug, app, logger):
    """Trigger a Travis sync and wait for its completion.

    Parameters
    ----------
    slug : `str`
        The repo's GitHub slug. This determines whether the "com" or "org"
        endpoint is used.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    """
    host = _get_travis_url(slug=slug)
    headers = make_travis_headers(token=_get_travis_token(app=app, slug=slug))
    http_session = app['api.lsst.codes/httpSession']

    # Check if there was already an existing user sync event
    while True:
        user_data = await get_current_user(slug=slug, app=app, logger=logger)
        if user_data['is_syncing'] is True:
            await asyncio.sleep(10.)
            logger.debug('Travis is already syncing')
        else:
            break

    user_id = str(user_data['id'])

    # Start a new sync
    url = uritemplate.expand(
        host + '/user{/user_id}/sync',
        user_id=user_id
    )
    async with http_session.post(url, headers=headers) as response:
        message = await response.json()
        logger.debug('Triggered Travis CI sync', body=message)

    # Wait for the sync to complete
    await asyncio.sleep(10.)
    while True:
        user_data = await get_current_user(slug=slug, app=app, logger=logger)
        if user_data['is_syncing'] is True:
            await asyncio.sleep(10.)
            logger.debug('Travis is currently syncing')
        else:
            break
    await asyncio.sleep(10.)


def make_travis_repo_url(slug):
    """Make the user accessible URL for a repository on Travis.

    This function adapts to whether the slug is associated with a ``.com`` or
    ``.org`` repository.

    Parameters
    ----------
    slug : `str`
        The repository's GitHub slug.

    Returns
    -------
    url : `str`
        Repository URL on Travis.
    """
    if _get_travis_endpoint_type(slug=slug) == 'com':
        host = 'https://travis-ci.com'
    else:
        host = 'https://travis-ci.org'
    return '/'.join((host, slug))
