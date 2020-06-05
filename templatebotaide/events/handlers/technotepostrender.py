"""Post-render handler for technotes."""

__all__ = ('handle_technote_postrender',)

import asyncio
from tempfile import TemporaryDirectory
from pathlib import Path

import git

from templatebotaide import github
from templatebotaide.slack import post_message


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

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

    if event['template_name'] in ('technote_latex', 'technote_aastex'):
        # Handle the configuration PR for a LaTeX technote to add the
        # lsst-texmf submodule.
        try:
            pr_data = await pr_latex_submodules(
                event=event,
                app=app,
                logger=logger
            )
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
            logger.exception(
                'Failed to PR latex submodules for technote',
                github_repo=event['github_repo'])
            if event['slack_username'] is not None:
                await post_message(
                    text=(
                        "Something went wrong adding the lsst-texmf submodule "
                        f"to {event['github_repo']}. Contact SQuaRE for help."
                    ),
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )


async def pr_latex_submodules(*, event, app, logger):
    """Create a GitHub Pull Request that adds the lsst-texmf submodule.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-postrender`` event's message.
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
    ltd_slug = '-'.join((event['variables']['series'].lower(),
                         event['variables']['serial_number']))
    ltd_url = f'https://{ltd_slug}.lsst.io'

    # The comitter is the bot
    github_user = await github.get_authenticated_user(
        app=app, logger=logger)
    author = git.Actor(github_user['name'], github_user['email'])

    with TemporaryDirectory() as tmpdir_name:
        repo = git.Repo.clone_from(github_repo_url, to_path=tmpdir_name)

        # Since we cloned from GitHub, the first origin should be GitHub
        origin = repo.remotes[0]
        origin = github.add_auth_to_remote(remote=origin, app=app)

        # Create the branch
        new_branch_name = 'u/{user}/config'.format(
            user=app['templatebot-aide/githubUsername'])
        new_branch = repo.create_head(new_branch_name)
        repo.head.reference = new_branch
        # reset the index and working tree to match the pointed-to commit
        repo.head.reset(index=True, working_tree=True)

        # Add the lsst-texmf submodule
        git.objects.submodule.base.Submodule.add(
            repo,
            'lsst-texmf',
            path='lsst-texmf',
            url='https://github.com/lsst/lsst-texmf.git',
            branch='master'
        )
        repo.index.add([
            str(Path(tmpdir_name) / '.gitmodules')
        ])
        repo.index.commit('Add lsst-texmf submodule',
                          author=author,
                          committer=author)

        origin.push(refspec=f'{new_branch_name}:{new_branch_name}')

        await asyncio.sleep(1.)

        if ltd_url.endswith('/'):
            ltd_url.rstrip('/')
        branch_url = ltd_url + "/v/" + new_branch_name.replace('/', '-')
        dashboard_url = ltd_url + "/v"
        pr_body = (
            "This pull request adds the "
            "[lsst-texmf](https://lsst-texmf.lsst.io) submodule.\n\n"
            f"You should see the doc online at {branch_url} (once this branch "
            "is built by GitHub Actions).\n\nThe edition dashboard is: "
            f"{dashboard_url}.\n\nThis PR is automatically generated. Feel "
            "free to update this PR or the underlying branch if there's an "
            "issue."
        )

        pr_response = await github.create_pr(
            owner=repo_owner,
            repo=repo_name,
            title='Add lsst-texmf submodule',
            body=pr_body,
            head=new_branch_name,
            base='master',
            app=app,
            logger=logger
        )

        logger.debug('Finished pushing lsst-texmf PR', branch=new_branch_name)

    return pr_response
