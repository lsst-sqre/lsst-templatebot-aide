__all__ = ('handle_technote_prerender',)

import re
from copy import deepcopy
import datetime
import gidgethub

from templatebotaide.github import create_repo
from templatebotaide.slack import post_message, get_user_info


async def handle_technote_prerender(*, event, schema, app, logger):
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
    logger.info('In handle_technote_prerender', event_data=event)

    # Get data from the event (user dialog input)
    org_name = event['variables']['github_org']
    series = event['variables']['series'].lower()

    series_pattern = re.compile(r'^' + series + r'-(?P<number>\d+)$')

    # Get repository names from GitHub for this org
    ghclient = app['templatebot-aide/gidgethub']
    repo_iter = ghclient.getiter(
        '/orgs{/org}/repos', url_vars={'org': org_name})
    series_numbers = []
    async for repo_info in repo_iter:
        name = repo_info['name'].lower()
        m = series_pattern.match(name)
        if m is None:
            continue
        series_numbers.append(int(m.group('number')))

    new_number = propose_number([int(n) for n in series_numbers])
    serial_number = f'{new_number:03d}'
    repo_name = f'{series.lower()}-{serial_number}'

    logger.debug('Selected new technote repo name',
                 name=repo_name, org=org_name)

    try:
        repo_info = await create_repo(
            org_name=org_name,
            repo_name=repo_name,
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
                text="This is the repo URL I tried: "
                     f"`{repo_info['html_url']}`.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise

    logger.info('Created repo', repo_info=repo_info)

    # Get the user's identity to use as the initial author
    user_info = await get_user_info(
        user=event['slack_username'], logger=logger, app=app)

    # Send a response message to templatebot-render_ready
    # The render_ready message is based on the prerender payload, but now
    # we can inject resolved variables
    render_ready_message = deepcopy(event)
    render_ready_message['github_repo'] = repo_info['html_url']
    render_ready_message['variables']['serial_number'] = serial_number
    render_ready_message['variables']['first_author'] \
        = user_info['user']['real_name']
    render_ready_message['retry_count'] = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    render_ready_message['initial_timestamp'] = now

    serializer = app['templatebot-aide/renderreadySerializer']
    render_ready_data = serializer(render_ready_message)

    producer = app['templatebot-aide/producer']
    topic_name = app['templatebot-aide/renderreadyTopic']
    await producer.send_and_wait(topic_name, render_ready_data)
    logger.info('Sent render_ready message', data=render_ready_message)


def propose_number(series_numbers):
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

    raise RuntimeError('propose_number should not be in this state.')
