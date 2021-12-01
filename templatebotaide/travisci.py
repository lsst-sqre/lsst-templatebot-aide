"""Workflows for Travis CI."""

__all__ = [
    "get_current_user",
    "activate_travis",
    "sync_travis_account",
    "get_generated_travis_repo_key",
    "encrypt_travis_secret",
    "make_travis_repo_url",
]

import asyncio
import base64

import Cryptodome.Cipher.PKCS1_v1_5
import Cryptodome.PublicKey.RSA
import uritemplate


def _get_travis_endpoint_type(org=None, slug=None):
    if org is None and slug is None:
        raise ValueError("Either `slug` or `org` must be specified.")
    elif slug is None:
        org = slug.split("/")[0]

    if org in ("lsst", "lsst-sims"):
        return "org"
    else:
        return "com"


def _get_travis_url(slug=None, org=None):
    """Get the right API host (.org or .com) for different LSST GitHub
    organizations.

    Returns
    -------
    url : `str`
        The API URL, either ``https://api.travis-ci.org`` or
        ``https://api.travis-ci.com``
    """
    if _get_travis_endpoint_type(org=org, slug=slug) == "com":
        return "https://api.travis-ci.com"
    else:
        return "https://api.travis-ci.org"


def _get_travis_token(*, app, org=None, slug=None):
    if _get_travis_endpoint_type(org=org, slug=slug) == "com":
        return app["templatebot-aide/travisTokenCom"]
    else:
        return app["templatebot-aide/travisToken"]


def make_travis_headers(*, token):
    return {
        "Travis-API-Version": "3",
        "User-Agent": "lsst-templatebot-aide",
        "Authorization": "token " + token,
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
    http_session = app["api.lsst.codes/httpSession"]

    url = uritemplate.expand(host + "/repo{/slug}/activate", slug=slug)
    async with http_session.post(url, headers=headers) as response:
        response_data = await response.json()
        logger.debug(
            "Activating repository",
            slug=slug,
            url=response.url,
            status=response.status,
            message=response_data,
        )


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
    http_session = app["api.lsst.codes/httpSession"]

    url = host + "/user"
    async with http_session.get(url, headers=headers) as response:
        data = await response.json()
        logger.debug("Got Travis user data", data=data)
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
    http_session = app["api.lsst.codes/httpSession"]

    # Check if there was already an existing user sync event
    while True:
        user_data = await get_current_user(slug=slug, app=app, logger=logger)
        if user_data["is_syncing"] is True:
            await asyncio.sleep(10.0)
            logger.debug("Travis is already syncing")
        else:
            break

    user_id = str(user_data["id"])

    # Start a new sync
    url = uritemplate.expand(host + "/user{/user_id}/sync", user_id=user_id)
    async with http_session.post(url, headers=headers) as response:
        message = await response.json()
        logger.debug("Triggered Travis CI sync", body=message)

    # Wait for the sync to complete
    await asyncio.sleep(10.0)
    while True:
        user_data = await get_current_user(slug=slug, app=app, logger=logger)
        if user_data["is_syncing"] is True:
            await asyncio.sleep(10.0)
            logger.debug("Travis is currently syncing")
        else:
            break
    await asyncio.sleep(10.0)


async def get_generated_travis_repo_key(*, slug, app, logger):
    """Get the generated public key of a Travis repo.

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
        Public key payload. See
        https://developer.travis-ci.com/resource/key_pair_generated#attributes
        for a description of what's included in this data.

    Notes
    -----
    Uses https://developer.travis-ci.com/resource/key_pair_generated#find
    """
    host = _get_travis_url(slug=slug)
    headers = make_travis_headers(token=_get_travis_token(app=app, slug=slug))
    http_session = app["api.lsst.codes/httpSession"]
    url = uritemplate.expand(
        host + "/repo{/slug}/key_pair/generated", slug=slug
    )
    logger.debug("Public key url", url=url)
    async with http_session.get(url, headers=headers) as response:
        text = await response.text()
        logger.debug("Public key response", data=text)
        response.raise_for_status()
        data = await response.json()
    return data


def encrypt_travis_secret(*, public_key, secret):
    """Encrypt a string using a repository's public Travis CI key.

    Parameters
    ----------
    public_key : `bytes`
        The RSA public key. This can be obtained through
        `get_generated_travis_repo_key` and the ``"public_key"`` key
        of the returned object.
    secret : `str`
        The secret content to encrypt.

    Returns
    -------
    encrypted : `bytes`
        The encrypted secret. This content can be used as the value of a
        ``secure`` key in a ``.travis.yml`` file.

    Notes
    ----
    This function uses a ``PKCS1_v1_5`` RSA cipher, which isn't ideal, but
    Travis *requires* it.
    """
    rsa_key = Cryptodome.PublicKey.RSA.import_key(public_key)
    rsa_cipher = Cryptodome.Cipher.PKCS1_v1_5.new(rsa_key)

    return base64.b64encode(rsa_cipher.encrypt(secret.encode("utf-8")))


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
    if _get_travis_endpoint_type(slug=slug) == "com":
        host = "https://travis-ci.com"
    else:
        host = "https://travis-ci.org"
    return "/".join((host, slug))
