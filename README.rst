####################
lsst-templatbot-aide
####################

``lsst-templatebot-aide`` is a microservice that works with Templatebot_ to set up GitHub repos, Travis CI, LSST the Docs deployments, and make other LSST-specific configurations.
The Aide talks to Templatebot_ through SQuaRE Events, our Kafka message service for ``api.lsst.codes``.

A typical sequence operations looks like this:

1. Templatebot_ publishes a Kafka message (the **prerender phase**) describing the template and template variables.

2. ``lsst-templatebot-aide`` receives that message and sets up the GitHub repository.

   If the project is something like a technote, the Aide will even determine which GitHub repository to claim.
   Otherwise, the Aide will use some combination of ``github_repo`` or ``github_org`` and ``name`` template variables to determine the URL of the GitHub repository to make.

   The Aide publishes a new message containing a ``github_repo`` Cookiecutter_ variable that contains the URL for the new repository.

3. Templatebot_ receives that message and renders the repository using Cookiecutter_/Templatekit_ and pushes the contents to GitHub.
   This is the **render phase**.

   Once the project is rendered, it sends another Kafka message that again describes the repository, its template, and template variables.
   This is message triggers a **postrender phase**.

   The Aide can optionally act on the postrender message to do things like configure LSST the Docs and Travis CI.
   If necessary, it can submit a PR with new repository content (such as encrypted variables in a ``.travis.yml`` file).

.. _Templatebot: https://github.com/lsst-sqre/templatebot
.. _Cookiecutter: https://cookiecutter.readthedocs.io/en/latest/
.. _Templatekit: https://templatekit.lsst.io
