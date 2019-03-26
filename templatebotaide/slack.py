"""Workflows for using the Slack API that are common to many handlers.
"""

__all__ = ('post_message',)

import yarl


async def post_message(body=None, text=None, channel=None, thread_ts=None,
                       *, logger, app):
    """Send a ``chat.postMessage`` request to Slack.

    Parameters
    ----------
    body : `dict`, optional
        The ``chat.postMessage`` payload. See
        https://api.slack.com/methods/chat.postMessage. Set this parameter to
        have full control over the message. If you only need to send a simple
        message, see ``text``.
    text : `str`, optional
        Text content of the message. Use this parameter to send simple markdown
        messages rather than fully specifying the ``body``.
    channel : `str`, optional
        The channel ID, only used if the ``text`` parameter is used.
    thread_ts : `str`, optional
        The ``thread_ts`` to send a threaded message. Only use this parameter
        if ``text`` is set and you want to send a threaded message.
    logger
        Logger instance.
    app
        Application instance.
    """
    if body is None:
        if text is None or channel is None:
            raise ValueError(
                'If "body" is not set, then set "text" and "channel" '
                'for post_message')

        body = {
            "token": app["templatebot-aide/slackToken"],
            "channel": channel,
            "text": text
        }
        if thread_ts is not None:
            body['thread_ts'] = thread_ts

    httpsession = app['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["templatebot-aide/slackToken"]}'
    }

    logger.info(
        'chat.postMessage',
        body=body)

    url = 'https://slack.com/api/chat.postMessage'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.debug(
            'chat.postMessage reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.postMessage',
            contents=response_json)


async def get_user_info(*, user, logger, app):
    """Get information about a Slack user through the ``users.info`` web API.

    Parameters
    ----------
    user : `str`
        The user's ID (not their handle, but a Slack ID).
    logger
        Logger instance.
    app
        Application instance.
    """
    httpsession = app['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
        'authorization': f'Bearer {app["templatebot-aide/slackToken"]}'
    }
    url = 'https://slack.com/api/users.info'
    body = {
        'token': app["templatebot-aide/slackToken"],
        'user': user
    }
    encoded_body = yarl.URL.build(query=body).query_string.encode('utf-8')
    async with httpsession.post(url, data=encoded_body, headers=headers) \
            as response:
        response_json = await response.json()
        logger.debug(
            'users.info reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from users.info',
            response=response_json)

    return response_json
