##########
Change log
##########

0.0.4 (2019-09-20)
==================

This release provides support for ``technote_aastex`` templates, which are prepared similarly to ``technote_latex`` templates.

:jirab:`21378`

0.0.3 (2019-09-11)
==================

This release fixes error reporting when a GitHub repo could not be created for a technote.

:jirab:`21257`

0.0.2 (2019-04-30)
==================

This release handles the unique post render requirements of ``technote_latex`` templates:

- The encrypted environment variables are slightly different than reStructuredText technotes.
- Add the lsst-texmf submodule.

:jirab:`DM-19186`

0.0.1 (2019-04-17)
==================

This is the initial proof-of-concept of ``lsst-templatebot-aide``.
This microservice handles ``templatebot-prerender`` messages, including special handling for technical notes to provision a GitHub repository based on the next available serial number.
This microservice also handles ``templatebot-postrender`` messages for technotes to enable the LSST the Docs deployments, activate Travis CI, and submit a GitHub Pull Request with encrypted credentials for Travis CI.

:jirab:`DM-18535`
