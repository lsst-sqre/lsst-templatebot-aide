"""Configuration collection.
"""

__all__ = ('create_config',)

import os


def create_config():
    """Create a config mapping from defaults and environment variable
    overrides.

    Returns
    -------
    c : `dict`
        A configuration dictionary.

    Examples
    --------
    Apply the configuration to the aiohttp.web application::

        app = web.Application()
        app.update(create_config)
    """
    c = {}

    # Application run profile. 'development' or 'production'
    c['api.lsst.codes/profile'] = os.getenv(
        'API_LSST_CODES_PROFILE',
        'development').lower()

    # That name of the api.lsst.codes service, which is also the root path
    # that the app's API is served from.
    c['api.lsst.codes/name'] = os.getenv('API_LSST_CODES_NAME',
                                         'templatebot-aide')

    # The name of the logger, which should also be the name of the Python
    # package.
    c['api.lsst.codes/loggerName'] = os.getenv(
        'API_LSST_CODES_LOGGER_NAME', 'templatebotaide')

    # Log level (INFO or DEBUG)
    c['api.lsst.codes/logLevel'] = os.getenv(
        'API_LSST_CODES_LOG_LEVEL',
        'info' if c['api.lsst.codes/profile'] == 'production' else 'debug'
    ).upper()

    # Schema Registry hostname (use same config variable as SQRBOTJR)
    c['templatebot-aide/registryUrl'] = os.getenv('REGISTRY_URL')

    # Kafka broker host (use same config variable as SQRBOTJR)
    c['templatebot-aide/brokerUrl'] = os.getenv('KAFKA_BROKER')

    # Slack token (use same config variable as SQRBOTJR)
    c['templatebot-aide/slackToken'] = os.getenv('SLACK_TOKEN')

    # Version name for Kafka topics, if application is running in a staging
    # environment. This functions similarly to $SQRBOTJR_STAGING_VERSION but
    # it's an independent configuration so that templatebot can be developed
    # independently of sqrbot.
    c['templatebot-aide/topicsVersion'] = \
        os.getenv('TEMPLATEBOT_TOPICS_VERSION') or ''

    # GitHub token for SQuaRE bot
    c['templatebot-aide/githubToken'] = os.getenv('TEMPLATEBOT_GITHUB_TOKEN')
    c['templatebot-aide/githubUsername'] = os.getenv('TEMPLATEBOT_GITHUB_USER')

    # Travis CI tokens for both .com and .org APIs
    c['templatebot-aide/travisTokenCom'] \
        = os.getenv('TEMPLATEBOT_TRAVIS_TOKEN_COM')
    c['templatebot-aide/travisTokenOrg'] \
        = os.getenv('TEMPLATEBOT_TRAVIS_TOKEN_ORG')

    # Credentials for LSST the Docs
    c['templatebot-aide/ltdUsername'] = os.getenv('TEMPLATEBOT_LTD_USERNAME')
    c['templatebot-aide/ltdPassword'] = os.getenv('TEMPLATEBOT_LTD_PASSWORD')

    # Credentials that can be embedded in CI configs (encrypted) for their
    # LSST the Docs deployments
    c['templatebot-aide/ltdEmbedAwsId'] \
        = os.getenv('TEMPLATEBOT_LTD_AWS_ID')
    c['templatebot-aide/ltdEmbedAwsSecret'] \
        = os.getenv('TEMPLATEBOT_LTD_AWS_SECRET')
    c['templatebot-aide/ltdEmbedLtdUser'] \
        = os.getenv('TEMPLATEBOT_LTD_USERNAME_EMBED')
    c['templatebot-aide/ltdEmbedLtdPassword'] \
        = os.getenv('TEMPLATEBOT_LTD_PASSWORD_EMBED')

    return c
