"""Configuration collection."""

import os
from pathlib import Path
from typing import Any, Dict

__all__ = ["create_config"]


def create_config() -> Dict[str, Any]:
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
    c: Dict[str, Any] = {}

    # Application run profile. 'development' or 'production'
    c["api.lsst.codes/profile"] = os.getenv(
        "API_LSST_CODES_PROFILE", "development"
    ).lower()

    # That name of the api.lsst.codes service, which is also the root path
    # that the app's API is served from.
    c["api.lsst.codes/name"] = os.getenv(
        "API_LSST_CODES_NAME", "templatebot-aide"
    )

    # The name of the logger, which should also be the name of the Python
    # package.
    c["api.lsst.codes/loggerName"] = os.getenv(
        "API_LSST_CODES_LOGGER_NAME", "templatebotaide"
    )

    # Log level (INFO or DEBUG)
    c["api.lsst.codes/logLevel"] = os.getenv(
        "API_LSST_CODES_LOG_LEVEL",
        "info" if c["api.lsst.codes/profile"] == "production" else "debug",
    ).upper()

    # Schema Registry hostname (use same config variable as SQRBOTJR)
    c["templatebot-aide/registryUrl"] = os.getenv("REGISTRY_URL")

    # Kafka broker host (use same config variable as SQRBOTJR)
    c["templatebot-aide/brokerUrl"] = os.getenv("KAFKA_BROKER")

    # Kafka security protocol: PLAINTEXT or SSL
    c["templatebot-aide/kafkaProtocol"] = os.getenv("KAFKA_PROTOCOL")

    # TLS certificates for cluster + client for use with the SSL Kafka protocol
    c["templatebot-aide/clusterCaPath"] = os.getenv("KAFKA_CLUSTER_CA")
    c["templatebot-aide/clientCaPath"] = os.getenv("KAFKA_CLIENT_CA")
    c["templatebot-aide/clientCertPath"] = os.getenv("KAFKA_CLIENT_CERT")
    c["templatebot-aide/clientKeyPath"] = os.getenv("KAFKA_CLIENT_KEY")

    c["templatebot-aide/certCacheDir"] = Path(
        os.getenv("TEMPLATEBOT_CERT_CACHE", ".")
    )

    # Slack token (use same config variable as SQRBOTJR)
    c["templatebot-aide/slackToken"] = os.getenv("SLACK_TOKEN")

    # Suffix to add to Schema Registry suffix names. This is useful when
    # deploying sqrbot-jr for testing/staging and you do not want to affect
    # the production subject and its compatibility lineage.
    c["templatebot-aide/subjectSuffix"] = os.getenv(
        "TEMPLATEBOT_SUBJECT_SUFFIX", ""
    )

    # Topic names
    c["templatebot-aide/prerenderTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_PRERENDER", "templatebot.prerender"
    )
    c["templatebot-aide/renderreadyTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_RENDERREADY", "templatebot.render-ready"
    )
    c["templatebot-aide/postrenderTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_POSTRENDER", "templatebot.postrender"
    )

    # GitHub token for SQuaRE bot
    c["templatebot-aide/githubToken"] = os.getenv("TEMPLATEBOT_GITHUB_TOKEN")
    c["templatebot-aide/githubUsername"] = os.getenv("TEMPLATEBOT_GITHUB_USER")

    # Travis CI tokens for both .com and .org APIs
    c["templatebot-aide/travisTokenCom"] = os.getenv(
        "TEMPLATEBOT_TRAVIS_TOKEN_COM"
    )
    c["templatebot-aide/travisTokenOrg"] = os.getenv(
        "TEMPLATEBOT_TRAVIS_TOKEN_ORG"
    )

    # Credentials for LSST the Docs
    c["templatebot-aide/ltdUsername"] = os.getenv("TEMPLATEBOT_LTD_USERNAME")
    c["templatebot-aide/ltdPassword"] = os.getenv("TEMPLATEBOT_LTD_PASSWORD")

    # Credentials that can be embedded in CI configs (encrypted) for their
    # LSST the Docs deployments
    c["templatebot-aide/ltdEmbedAwsId"] = os.getenv("TEMPLATEBOT_LTD_AWS_ID")
    c["templatebot-aide/ltdEmbedAwsSecret"] = os.getenv(
        "TEMPLATEBOT_LTD_AWS_SECRET"
    )
    c["templatebot-aide/ltdEmbedLtdUser"] = os.getenv(
        "TEMPLATEBOT_LTD_USERNAME_EMBED"
    )
    c["templatebot-aide/ltdEmbedLtdPassword"] = os.getenv(
        "TEMPLATEBOT_LTD_PASSWORD_EMBED"
    )

    # Kafka consumer group ID
    c["templatebot-aide/kafkaGroupId"] = os.getenv(
        "TEMPLATEBOT_GROUP_ID", c["api.lsst.codes/name"]
    )

    return c
