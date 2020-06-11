__all__ = ['handle_document_prerender']

import datetime
import re
from copy import deepcopy

import gidgethub

from templatebotaide.lsstthedocs import register_ltd_product
from templatebotaide.github import create_repo
from templatebotaide.slack import post_message


async def handle_document_prerender(*, event, schema, app, logger):
    """Handle a ``templatebot-prerender`` event for a document template where
    the repository is known and needs to be registered with LSST the Docs.

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
    logger.info('In handle_document_prerender', event_data=event)

    # In the latex_lsstdoc template, the series and serial_number are
    # determined from the handle. This logic attempts to match this metadata
    # and extract it, if necessary and possible.
    if 'handle' in event['variables']:
        handle = event['variables']['handle']  # for latex_lsstdoc
        handle_match = re.match(
            r"(?P<series>[A-Z]+)-(?P<serial_number>[0-9]+)",
            handle
        )
    else:
        handle = None
        handle_match = None

    if 'series' in event['variables'] and event['variables']['series']:
        series = event['variables']['series']
    elif handle_match:
        series = handle_match['series']
    else:
        series = ""

    if 'serial_number' in event['variables'] \
            and event['variables']['serial_number']:
        serial_number = event['variables']['serial_number']
    elif handle_match:
        serial_number = handle_match['serial_number']
    else:
        serial_number = ""

    if handle is None:
        if series and serial_number:
            handle = f"{series}-{serial_number}"
        else:
            await post_message(
                text=f"<@{event['slack_username']}>, oh no! "
                     "I could not determine the document's handle."
                     "I can't do anything to fix it. Could you ask someone at "
                     "SQuaRE to look into it?",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
            raise RuntimeError(
                "Could not determine the document handle."
            )

    org_name = event['variables']['github_org']
    repo_name = handle
    ltd_slug = repo_name.lower()
    ltd_url = f"https://{ltd_slug}.lsst.io"

    try:
        repo_info = await create_repo(
            org_name=org_name,
            repo_name=repo_name,
            homepage=ltd_url,
            description=event['variables']['title'],
            app=app,
            logger=logger
        )
    except gidgethub.GitHubException:
        logger.exception('Error creating the GitHub repository')
        # Send a threaded Slack message back to the user if appropriate
        if event['slack_username'] is not None:
            await post_message(
                text=f"<@{event['slack_username']}>, oh no! "
                     ":slightly_frowning_face:, something went wrong when "
                     "I tried to create a GitHub repo.\n\n"
                     "I can't do anything to fix it. Could you ask someone at "
                     "SQuaRE to look into it?",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
            await post_message(
                text="This is the repo I tried: "
                     f"`{org_name}/{repo_name}`.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise

    logger.info('Created repo', repo_info=repo_info)

    try:
        ltd_product = await register_ltd_product(
            slug=ltd_slug,
            title=event['variables']['title'],
            github_repo=repo_info['html_url'],
            app=app,
            logger=logger,
            main_mode="lsst_doc")
        if event['slack_username'] is not None:
            await post_message(
                text=(
                    "I've set up the document on _LSST the Docs._ Your "
                    f"document will appear at {ltd_product['published_url']} "
                    "in a few minutes after the GitHub Actions build finishes."
                ),
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
    except Exception:
        logger.exception(
            'Failed to create the LTD product',
            ltd_slug=ltd_slug)
        if event['slack_username'] is not None:
            await post_message(
                text="Something went wrong setting up _LSST the Docs._ I will "
                     "continue to configure the technote, but docs won't be "
                     "available right away. Contact SQuaRE for help.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )

    # Send a response message to templatebot-render_ready
    # The render_ready message is based on the prerender payload, but now
    # we can inject resolved variables
    render_ready_message = deepcopy(event)
    if 'series' not in render_ready_message['variables'] or \
            render_ready_message['variables']['series'] == "":
        render_ready_message['variables']['series'] = series
    if 'serial_number' not in render_ready_message['variables'] or \
            render_ready_message['variables']['serial_number'] == "":
        render_ready_message['variables']['serial_number'] = serial_number
    render_ready_message['github_repo'] = repo_info['html_url']
    render_ready_message['retry_count'] = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    render_ready_message['initial_timestamp'] = now

    serializer = app['templatebot-aide/renderreadySerializer']
    render_ready_data = serializer(render_ready_message)

    producer = app['templatebot-aide/producer']
    topic_name = app['templatebot-aide/renderreadyTopic']
    await producer.send_and_wait(topic_name, render_ready_data)
    logger.info('Sent render_ready message', data=render_ready_message)
