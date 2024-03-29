import datetime
import re
from copy import deepcopy
from typing import Any, Dict, List

import gidgethub
from aiohttp.web import Application
from structlog.stdlib import BoundLogger

from templatebotaide.events.handlers.utilities import clean_string_whitespace
from templatebotaide.github import create_repo
from templatebotaide.lsstthedocs import register_ltd_product
from templatebotaide.slack import get_user_info, post_message
from templatebotaide.storage.authordb import AuthorDb

__all__ = ["handle_technote_prerender"]


async def handle_technote_prerender(
    *,
    event: Dict[str, Any],
    schema: Dict[str, Any],
    app: Application,
    logger: BoundLogger,
) -> None:
    """Handle a ``templatebot-prerender`` event for a technote template where
    the repository is assigned based on a sequence numbering schema.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-prerender`` event's message.
    schema : `dict`
        The Avro schema corresponding to the ``event``.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Notes
    -----
    Once the handler is finished, it sends a ``templatebot-render_ready``
    event.
    """
    logger.info("In handle_technote_prerender", event_data=event)

    # Clean user input
    event["variables"]["title"] = clean_string_whitespace(
        event["variables"]["title"]
    )

    # This is the payload to send to the templatebot-render_ready topic.
    # The render_ready message is based on the prerender payload, but now
    # we can inject resolved variables
    render_ready_message = deepcopy(event)

    # Validate author_id early because it's easy to get wrong and we don't
    # want to create a repo if we can't get the author information
    if "author_id" in event["variables"]:
        # Look up author from lsst/lsst-texmf's authordb.yaml
        authordb = await AuthorDb.download()
        try:
            author_info = authordb.get_author(event["variables"]["author_id"])
        except KeyError:
            logger.exception(
                "Failed to find author in authordb.yaml",
                author_id=event["variables"]["author_id"],
            )
            author_id = event["variables"]["author_id"]
            message = (
                "Something went wrong getting your author information from "
                "`authordb.yaml`. Check that your author ID is correct at "
                f"http://ls.st/uyr and try again. You provided: `{author_id}`."
            )
            await post_message(
                text=message,
                channel=event["slack_channel"],
                thread_ts=event["slack_thread_ts"],
                logger=logger,
                app=app,
            )
            await print_input(event, logger, app)
            raise
        # Fill in fields
        render_ready_message["variables"][
            "first_author_given"
        ] = author_info.given_name
        render_ready_message["variables"][
            "first_author_family"
        ] = author_info.family_name
        render_ready_message["variables"][
            "first_author_orcid"
        ] = author_info.orcid
        render_ready_message["variables"][
            "first_author_affil_name"
        ] = author_info.affiliation_name
        render_ready_message["variables"][
            "first_author_affil_internal_id"
        ] = author_info.affiliation_id
        render_ready_message["variables"][
            "first_author_affil_address"
        ] = author_info.affiliation_address

    # Get data from the event (user dialog input)
    org_name = event["variables"]["github_org"]
    series = event["variables"]["series"].lower()

    series_pattern = re.compile(r"^" + series + r"-(?P<number>\d+)$")

    # Get repository names from GitHub for this org
    ghclient = app["templatebot-aide/gidgethub"]
    repo_iter = ghclient.getiter(
        "/orgs{/org}/repos", url_vars={"org": org_name}
    )
    series_numbers = []
    async for repo_info in repo_iter:
        name = repo_info["name"].lower()
        m = series_pattern.match(name)
        if m is None:
            continue
        series_numbers.append(int(m.group("number")))

    logger.info(
        "Collected existing numbers for series, series_numbers",
        series=series,
        series_numbers=series_numbers,
    )

    new_number = propose_number([int(n) for n in series_numbers])
    serial_number = f"{new_number:03d}"
    repo_name = f"{series.lower()}-{serial_number}"

    logger.info(
        "Selected new technote repo name", name=repo_name, org=org_name
    )

    ltd_slug = f"{series.lower()}-{serial_number}"
    ltd_url = f"https://{ltd_slug}.lsst.io"

    try:
        repo_info = await create_repo(
            org_name=org_name,
            repo_name=repo_name,
            homepage=ltd_url,
            description=event["variables"]["title"],
            app=app,
            logger=logger,
        )
    except gidgethub.GitHubException:
        logger.exception("Error creating the GitHub repository")
        # Send a threaded Slack message back to the user if appropriate
        if event["slack_username"] is not None:
            await post_message(
                text=f"<@{event['slack_username']}>, oh no! "
                ":slightly_frowning_face:, something went wrong when "
                "I tried to create a GitHub repo.\n\n"
                "I can't do anything to fix it. Could you ask someone at "
                "SQuaRE to look into it?",
                channel=event["slack_channel"],
                thread_ts=event["slack_thread_ts"],
                logger=logger,
                app=app,
            )
            await post_message(
                text="This is the repo I tried: " f"`{org_name}/{repo_name}`.",
                channel=event["slack_channel"],
                thread_ts=event["slack_thread_ts"],
                logger=logger,
                app=app,
            )
            await print_input(event, logger, app)
        raise

    logger.info("Created repo", repo_info=repo_info)

    try:
        ltd_product = await register_ltd_product(
            slug=ltd_slug,
            title=event["variables"]["title"],
            github_repo=repo_info["html_url"],
            app=app,
            logger=logger,
        )
        if event["slack_username"] is not None:
            await post_message(
                text=(
                    f"<@{event['slack_username']}>, the documentation URL "
                    f"will be:\n\n{ltd_product['published_url']}.\n\n"
                    "_That page will give a 404 error until the first build "
                    "completes. Hold tight!_"
                ),
                channel=event["slack_channel"],
                thread_ts=event["slack_thread_ts"],
                logger=logger,
                app=app,
            )
    except Exception:
        logger.exception("Failed to create the LTD product", ltd_slug=ltd_slug)
        if event["slack_username"] is not None:
            await post_message(
                text="Something went wrong setting up _LSST the Docs._ I will "
                "continue to configure the technote, but docs won't be "
                "available right away. Contact SQuaRE for help.",
                channel=event["slack_channel"],
                thread_ts=event["slack_thread_ts"],
                logger=logger,
                app=app,
            )
            await print_input(event, logger, app)

    # Add information to the render_ready message payload

    # Get the user's identity to use as the initial author
    user_info = await get_user_info(
        user=event["slack_username"], logger=logger, app=app
    )

    render_ready_message["github_repo"] = repo_info["html_url"]
    render_ready_message["variables"]["serial_number"] = serial_number
    render_ready_message["variables"]["first_author"] = user_info["user"][
        "real_name"
    ]
    render_ready_message["retry_count"] = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    render_ready_message["initial_timestamp"] = now

    serializer = app["templatebot-aide/renderreadySerializer"]
    render_ready_data = serializer(render_ready_message)

    producer = app["templatebot-aide/producer"]
    topic_name = app["templatebot-aide/renderreadyTopic"]
    await producer.send_and_wait(topic_name, render_ready_data)
    logger.info("Sent render_ready message", data=render_ready_message)


def propose_number(series_numbers: List[int]) -> int:
    """Propose a technote number given the list of available document numbers.

    This algorithm starts from 1, increments numbers by 1, and will fill in
    any gaps in the numbering scheme.
    """
    series_numbers.sort()

    n_documents = len(series_numbers)

    if n_documents == 0:
        return 1

    for i in range(n_documents):
        serial_number = series_numbers[i]

        if i == 0 and serial_number > 1:
            return 1

        if i + 1 == n_documents:
            # it might be the next-highest number
            return series_numbers[i] + 1

        # check if the next number is missing
        if series_numbers[i + 1] != serial_number + 1:
            return serial_number + 1

    raise RuntimeError("propose_number should not be in this state.")


async def print_input(
    event: Dict[str, Any], logger: BoundLogger, app: Application
) -> None:
    """Print the user input to Slack."""
    message = (
        "Here's what you sent me:\n\n"
        "```\n"
        f"{event['variables']}\n"
        "```\n\n"
    )
    await post_message(
        text=message,
        channel=event["slack_channel"],
        thread_ts=event["slack_thread_ts"],
        logger=logger,
        app=app,
    )
