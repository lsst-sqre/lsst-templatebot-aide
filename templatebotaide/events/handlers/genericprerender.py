__all__ = ('handle_generic_prerender',)

from copy import deepcopy
import datetime
import gidgethub

from templatebotaide.github import create_repo
from templatebotaide.slack import post_message


async def handle_generic_prerender(*, event, schema, app, logger):
    """Handle a ``templatebot-prerender`` event for a template where the
    GitHub organization and repository can be determined directly from the
    template variables.

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
    logger.info('In handle_generic_prerender', event_data=event)

    if event['template_name'] == 'stack_package':
        org_name = event['variables']['github_org']
        repo_name = event['variables']['package_name']
    else:
        # Try to work with a general case where github_org and name are the
        # cookiecutter variables for the repo's org and name on GitHub.
        try:
            org_name = event['variables']['github_org']
        except KeyError:
            logger.error('event does not have a variables.github_org key')
            raise
        try:
            repo_name = event['variables']['name']
        except KeyError:
            logger.error('event does not have a variables.name key')
            raise

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

    # Send a response message to templatebot-render_ready
    render_ready_message = deepcopy(event)
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
