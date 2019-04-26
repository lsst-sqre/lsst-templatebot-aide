"""Post-render handler for technotes.
"""

__all__ = ('handle_technote_postrender',)

import asyncio
from tempfile import TemporaryDirectory
from pathlib import Path
from io import StringIO
import urllib

import git
import ruamel.yaml

from templatebotaide.lsstthedocs import register_ltd_product
from templatebotaide.travisci import (
    activate_travis, sync_travis_account, make_travis_repo_url,
    encrypt_travis_secret, get_generated_travis_repo_key)
from templatebotaide.slack import post_message
from templatebotaide import github


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

    This handler activates Travis CI for the repository.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-postrender`` event's message.
    schema : `dict`
        The Avro schema corresponding to the ``event``.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    """
    logger.debug('In handle_technote_postrender', event_data=event)

    github_repo_url_parts = event['github_repo'].split('/')
    slug = '/'.join((github_repo_url_parts[-2], github_repo_url_parts[-1]))
    travis_url = make_travis_repo_url(slug)

    ltd_slug = '-'.join((event['variables']['series'].lower(),
                         event['variables']['serial_number']))

    try:
        ltd_product = await register_ltd_product(
            slug=ltd_slug,
            title=event['variables']['title'],
            github_repo=event['github_repo'],
            app=app,
            logger=logger)
        if event['slack_username'] is not None:
            await post_message(
                text="I've set up the technote on _LSST the Docs._ Your "
                     f"document will appear at {ltd_product['published_url']}",
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

    try:
        await sync_travis_account(slug=slug, app=app, logger=logger)
    except Exception:
        if event['slack_username'] is not None:
            await post_message(
                text="Something went wrong syncing with Travis. "
                     ":crying_cat_face: I can't fix it.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise

    try:
        await activate_travis(slug=slug, app=app, logger=logger)
        if event['slack_username'] is not None:
            await post_message(
                text=f"I've activated Travis CI: {travis_url}",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app)
    except Exception:
        if event['slack_username'] is not None:
            await post_message(
                text=f"Something went wrong activating `{slug}` with Travis. "
                     ":crying_cat_face: I can't fix it.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise

    if event['template_name'] == 'technote_rst':
        # Handle the configuration for an rst technote
        try:
            pr_data = await pr_ltd_credentials_for_travis(
                event=event, ltd_url=ltd_product['published_url'],
                app=app, logger=logger)
            if event['slack_username'] is not None:
                await post_message(
                    text=f"I've submitted a PR with deployment credentials. "
                         "Go and merge it to finish your technote's set up!"
                         f"\n\n{pr_data['html_url']}",
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )
        except Exception:
            logger.exception('Error PRing ltd credentials for travis')
            if event['slack_username'] is not None:
                await post_message(
                    text=f"Something went wrong creating a PR with "
                         "deployment credentials.",
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )


async def pr_ltd_credentials_for_travis(*, event, ltd_url, app, logger):
    """Create a pull request to an LTD-Conveyor client-based technical note
    containing encrypted credentials in the ``.travis.yml`` file.

    This function applies to reStructuredText-based technotes (`technote_rst`
    template).

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-postrender`` event's message.
    ltd_url : `str`
        The homepage URL of the project, served by LSST the Docs. For example,
        ``https://sqr-000.lsst.io``. This is the ``published_url`` field
        of the LTD ``product`` resource.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    """
    github_repo_url = event['github_repo']
    github_repo_url_parts = event['github_repo'].split('/')
    repo_owner = github_repo_url_parts[-2]
    repo_name = github_repo_url_parts[-1]
    slug = f'{repo_owner}/{repo_name}'

    with TemporaryDirectory() as tmpdir_name:
        repo = git.Repo.clone_from(github_repo_url, to_path=tmpdir_name)

        travis_yml_path = Path(tmpdir_name) / '.travis.yml'
        logger.debug(
            '.travis.yml path',
            path=str(travis_yml_path),
            exists=travis_yml_path.is_file())

        # Create the branch
        new_branch_name = 'u/{user}/config'.format(
            user=app['templatebot-aide/githubUsername'])
        new_branch = repo.create_head(new_branch_name)
        repo.head.reference = new_branch
        # reset the index and working tree to match the pointed-to commit
        repo.head.reset(index=True, working_tree=True)

        # Add LTD client credentials to the env.global section of .travis.yml
        travis_yml_data = await insert_ltd_client_credentials(
            slug=slug,
            travis_yml_path=travis_yml_path,
            repo=repo,
            app=app,
            logger=logger)
        travis_yml_path.write_text(travis_yml_data)

        # Add `.travis.yml` and create commit
        repo.index.add([str(travis_yml_path)])
        # The comitter is the bot
        github_user = await github.get_authenticated_user(
            app=app, logger=logger)
        author = git.Actor(github_user['name'], github_user['email'])
        repo.index.commit('Added credentials', author=author)

        # since we cloned from GitHub, this should be GitHub
        origin = repo.remotes[0]
        origin = add_auth_to_remote(remote=origin, app=app)
        origin.push(refspec=f'{new_branch_name}:{new_branch_name}')

        await asyncio.sleep(1.)

        pr_body = write_travis_pr_body(
            ltd_url=ltd_url, branch_name=new_branch_name)
        pr_response = await github.create_pr(
            owner=repo_owner,
            repo=repo_name,
            title='Add deployment credentials',
            body=pr_body,
            head=new_branch_name,
            base='master',
            app=app,
            logger=logger
        )

        logger.debug('Pushed credentials to branch', branch=new_branch_name)
    return pr_response


async def insert_ltd_client_credentials(
        *, slug, travis_yml_path, repo, app, logger):
    """Insert credentials needed by the LTD Conveyor client into the
    ``.travis.yml`` file of a repository.

    Parameters
    ----------
    slug : `str`
        The slug of the repository (``<owner>/<name>``) that identifies this
        repository to Travis CI.
    travis_yml_path : `pathlib.Path`
        The local filessytem path of the ``.travis.yml`` file in a repository.
    repo
        A GitPython repository instance.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Notes
    -----
    This function adds secrets to the ``env.global`` key of the ``.travis.yml``
    file so that the secrets are available in all jobs in the matrix. The
    follow enironment variables are added as encrypted strings

    - ``LTD_AWS_ID``
    - ``LTD_AWS_SECRET``
    - ``LTD_USERNAME``
    - ``LTD_PASSWORD``

    These environment variables can be consumed by the ``ltd`` upload tool
    (see https://ltd-conveyor.lsst.io for more information).
    """
    yaml_text = travis_yml_path.read_text()
    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(yaml_text)
    if 'env' not in data:
        data['env'] = ruamel.yaml.comments.CommentedMap()
    env = data['env']
    if 'global' not in env:
        env['global'] = ruamel.yaml.comments.CommentedSeq()
    env_global = env['global']

    key_info = await get_generated_travis_repo_key(
        slug=slug,
        app=app,
        logger=logger
    )

    env_global.append(new_secure_map(
        encrypt_travis_secret(
            public_key=key_info['public_key'],
            secret=f"LTD_AWS_ID={app['templatebot-aide/ltdEmbedAwsId']}"),
        comment='LTD_AWS_ID',
        comment_indent=6
    ))

    env_global.append(new_secure_map(
        encrypt_travis_secret(
            public_key=key_info['public_key'],
            secret="LTD_AWS_SECRET="
                   f"{app['templatebot-aide/ltdEmbedAwsSecret']}"),
        comment='LTD_AWS_SECRET',
        comment_indent=6
    ))

    env_global.append(new_secure_map(
        encrypt_travis_secret(
            public_key=key_info['public_key'],
            secret=f"LTD_USERNAME={app['templatebot-aide/ltdEmbedLtdUser']}"),
        comment='LTD_USERNAME',
        comment_indent=6
    ))

    env_global.append(new_secure_map(
        encrypt_travis_secret(
            public_key=key_info['public_key'],
            secret="LTD_PASSWORD="
                   f"{app['templatebot-aide/ltdEmbedLtdPassword']}"),
        comment='LTD_PASSWORD',
        comment_indent=6
    ))

    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def new_secure_map(secret, comment=None, comment_indent=0):
    """Create a secure (encrpyted) item that can be inserted into a
    Travis YAML file.

    Parameters
    ----------
    secret : `bytes`
        The encrypted secret.
    comment : `str`, optional
        An optional YAML comment that can be inserted before the secret.
    comment_indent : int
        Number of spaces to indent the comment. For a ``env.global`` secret,
        the best indentation is ``6``.

    Returns
    -------
    secret_map : `ruamel.yaml.comments.CommentedMap`
        The commented map instance containing the secure element.

    Notes
    -----
    This method generates a ``ruamel.yaml`` object that leads to this YAML
    syntax::

        secure: "<secret>"
    """
    new_map = ruamel.yaml.comments.CommentedMap()
    new_map['secure'] = secret.decode('utf-8')
    if comment is not None:
        new_map.yaml_set_comment_before_after_key(
            'secure', before=comment, indent=comment_indent)
    return new_map


def add_auth_to_remote(*, remote, app):
    """Add username and password authentication to the URL of a GitPython
    remote.

    Parameters
    ----------
    remote
        A GitPython remote instance.
    app : `aiohttp.web.Application`
        The app instance, for configuration.

    Returns
    -------
    remote
        The modified remote instance (same as the parameter).
    """
    # Modify the repo URL to include auth info in the netloc
    # <user>:<token>@github.com
    bottoken = app['templatebot-aide/githubToken']
    botuser = app['templatebot-aide/githubUsername']

    remote_url = [u for u in remote.urls][0]
    url_parts = urllib.parse.urlparse(remote_url)
    authed_url_parts = list(url_parts)
    # The [1] index is the netloc.
    authed_url_parts[1] = f'{botuser}:{bottoken}@{url_parts[1]}'
    authed_remote_url = urllib.parse.urlunparse(authed_url_parts)
    remote.set_url(authed_remote_url, old_url=remote_url)

    return remote


def write_travis_pr_body(*, ltd_url, branch_name):
    """Write out the body of the Pull Request message for adding Travis CI
    secrets to the technote.
    """
    if ltd_url.endswith('/'):
        ltd_url.rstrip('/')
    branch_url = ltd_url + "/v/" + branch_name.replace('/', '-')
    dashboard_url = ltd_url + "/v"
    return (
        "This pull request adds credentials to the `.travis.yml` file that "
        "are needed by LSST the Docs to deploy this technote to the web. "
        f"You should see the doc online at {branch_url} (once this branch is "
        f"built by Travis CI).\n\nThe edition dashboard is: {dashboard_url}."
        "\n\nThis PR is automatically generated. Feel free to update this PR "
        "or the underlying branch if there's an issue."
    )
