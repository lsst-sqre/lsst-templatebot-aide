##########
Change log
##########

0.4.0 (2021-12-01)
==================

- Change PR for lsst-texmf to use main branches, not master.
- Update to GitHub Actions from Travis CI
- Modernize packaging to meet SQuaRE's current standards (tox, pre-commit, formatting with Black and isort, pip-tools compiled dependencies and multi-stage docker image build).

0.3.3 (2020-06-30)
==================

- Verify that the handle for a generic doc is not a technote, giving the user feedback in Slack.
- Improve Slack message copy.

0.3.2 (2020-06-16)
==================

- The pre-render handlers now clean user content:

  - The ``title`` field of documents and technotes no longer contains any line breaks as this isn't compatible with the title's use for a GitHub repository description.

  - The name of a repository no longer contains any whitespace.

0.3.1 (2020-06-15)
==================

- Update to kafkit 0.2.0b3.

- Update to aiokafka 0.6.0.
  This should resolve the issue of unhandled UnknownMemberId exceptions causing consumers to unexpectedly drop their connection to the Kafka brokers.

0.3.0 (2020-06-15)
==================

- Add support for document templates where the name of the GitHub repository is known in advance by the user (because the document handle was assigned by DocuShare, for example).
  These templates are specifically the ``latex_lsstdoc`` and ``test_report`` templates.

- Refactor the code for creating a PR with the ``lsst-texmf`` submodule since both the ``technote_latex`` and new ``latex_lsstdoc`` / ``test_report`` templates make use of the functionality.

0.2.1 (2020-06-06)
==================

- Fix the confirmation message on technote creation (the multi line string was accidentally turned into a sequence of strings).

- Centralize the image tag version in ``kustomization.yaml``, which is easier to maintain on a release-by-release basis than the deployment YAML.

0.2.0 (2020-06-05)
==================

- This release updates the technote handlers to work with the new GitHub Actions templates.
  This greatly simplifies the technote post rendering handler since all the work related to Travis CI (registering a repo and encrypting credentials) is deleted.
  LaTeX-based technotes still have a post-rendering step that PRs the submodule.
  See https://github.com/lsst/templates/pull/80.

- Updates GitPython to 3.1.3 (to resolve an inconsistent GitDB dependency) and updates the testing stack to pytest 5.4.3 and pytest-flake8 to 1.0.6.

0.1.0 (2019-11-29)
==================

This release focuses on providing a better deployment, configuration, and compatibility with Kubernetes clusters secured with SSL:

- templatebot-aide can now be deployed through Kustomize.
  The base is located at ``/manifests/base``.
  This means that you can incorporate this application into a specific Kustomize-based application (such as one deployed by Argo CD) with a URL such as ``github.com/lsst-sqre/lsst-templatebot-aide.git//manifests/base?ref=0.1.0``.
  There is a separate template for the Secret resource expected by the deployment at ``/manifest/base/secret.template.yaml``.

- Topics names can now be configured directly.
  See the environment variables:

  - ``TEMPLATEBOT_TOPIC_PRERENDER``
  - ``TEMPLATEBOT_TOPIC_RENDERREADY``
  - ``TEMPLATEBOT_TOPIC_POSTRENDER``

  This granular configuration allows you to consume production topics, but output development topics, for example.

- The old "staging version" configuration is now the ``TEMPLATEBOT_SUBJECT_SUFFIX`` environment variable.
  This configuration is used solely as a suffix on the fully-qualified name of a schema when determining it's subject name at the Schema Registry.
  Previously it also impacted topic names.
  Use a subject suffix when trying out new Avro schemas to avoid polluting the production subject in the registry.

- templatebot-aide can now connect to Kafka brokers through SSL.
  Set the ``KAFKA_PROTOCOL`` environment variable to ``SSL``.
  Then set these environment variables to the paths of specific TLS certificates and keys:

  - ``KAFKA_CLUSTER_CA`` (the Kafka cluster's CA certificate)
  - ``KAFKA_CLIENT_CA`` (Templatebot's client CA certificate)
  - ``KAFKA_CLIENT_CERT`` (Templatebot's client certificate)
  - ``KAFKA_CLIENT_KEY`` (Templatebot's client key)

- The consumer group ID can now be set independently of the application name with the environment variable ``TEMPLATEBOT_GROUP_ID``.

:jirab:`DM-22100`

0.0.4 (2019-09-20)
==================

This release provides support for ``technote_aastex`` templates, which are prepared similarly to ``technote_latex`` templates.

:jirab:`DM-21378`

0.0.3 (2019-09-11)
==================

This release fixes error reporting when a GitHub repo could not be created for a technote.

:jirab:`DM-21257`

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
