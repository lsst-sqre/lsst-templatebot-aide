"""Workflows for LSST the Docs.
"""

__all__ = ('get_ltd_token', 'register_ltd_product')

import aiohttp


async def get_ltd_token(*, app, logger):
    """Get an auth token for LSST the Docs.

    Parameters
    ----------
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Returns
    -------
    token : `str`
        The auth token (use in the 'username' field of basic auth, without
        a separate password).

    Notes
    -----
    Auth is provided through these app-level configuration variables:

    - ``templatebot-aide/ltdUsername``
    - ``templatebot-aide/ltdPassword``
    """
    http_session = app['api.lsst.codes/httpSession']
    url = 'https://keeper.lsst.codes/token'
    auth = aiohttp.BasicAuth(
        app['templatebot-aide/ltdUsername'],
        password=app['templatebot-aide/ltdPassword'])
    async with http_session.get(url, auth=auth) as response:
        response.raise_for_status()
        data = await response.json()
    return data['token']


async def register_ltd_product(*, slug, title, github_repo, app, logger,
                               main_mode="git_refs"):
    """Register a new product on LSST the Docs.

    Parameters
    ----------
    slug : `str`
        The *slug* is the sub-domain component of the lsst.io domain.
    title : `str`
        The product's title.
    github_repo : `str`
        The URL of the product's source repository.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    main_mode : `str`
        The tracking mode of the main edition. See
        https://ltd-keeper.lsst.io/editions.html#tracking-modes

    Returns
    -------
    data : `dict`
        The product resource, see
        https://ltd-keeper.lsst.io/products.html#get--products-(slug)

    Notes
    -----
    Authentication is done through application configuration variables. See
    `get_ltd_token`.
    """
    data = {
        'title': title,
        'slug': slug,
        'doc_repo': github_repo,
        'main_mode': main_mode,
        'bucket_name': 'lsst-the-docs',
        'root_domain': 'lsst.io',
        'root_fastly_domain': 'n.global-ssl.fastly.net',
    }

    http_session = app['api.lsst.codes/httpSession']
    url = 'https://keeper.lsst.codes/products/'
    logger.debug(
        'Registering product on LTD',
        url=url,
        payload=data)
    token = await get_ltd_token(app=app, logger=logger)
    auth = aiohttp.BasicAuth(token)
    async with http_session.post(url, json=data, auth=auth) as response:
        response.raise_for_status()
        product_url = response.headers['Location']

    # Get data about the product
    async with http_session.get(product_url, auth=auth) as response:
        response.raise_for_status()
        product_data = await response.json()

    return product_data
