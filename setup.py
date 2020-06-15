from setuptools import setup, find_packages
from pathlib import Path

package_name = 'templatebotaide'
description = (
    'lsst-templatebot-aide is a microservice that works with Templatebot '
    'to set up GitHub repos, Travis CI, LSST the Docs deployments, and make '
    'other LSST-specific configurations.'
)
author = 'Association of Universities for Research in Astronomy'
author_email = 'sqre-admin@lists.lsst.org'
license = 'MIT'
url = 'https://github.com/lsst-sqre/lsst-templatebot-aide'
pypi_classifiers = [
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.7'
]
keywords = ['lsst']
readme = Path(__file__).parent / 'README.rst'

# Core dependencies
install_requires = [
    'aiodns==1.1.1',
    'aiohttp==3.5.0',
    'cchardet==2.1.4',
    'structlog==18.2.0',
    'colorama==0.4.1',  # used by structlog
    'click>=6.7,<7.0',
    'fastavro==0.21.16',
    'kafkit==0.1.1',
    'aiokafka==0.6.0',
    'gidgethub==3.1.0',
    'cachetools==3.1.0',
    'pycryptodomex==3.8.0',
    'ruamel.yaml==0.15.89',
    'GitPython==3.1.3',
]

# Test dependencies
tests_require = [
    'pytest==5.4.3',
    'pytest-flake8==1.0.6',
    'aiohttp-devtools==0.11',
]
tests_require += install_requires

# Sphinx documentation dependencies
docs_require = [
    'documenteer[pipelines]>=0.5.0,<0.6.0',
]

# Optional dependencies (like for dev)
extras_require = {
    # For development environments
    'dev': tests_require + docs_require
}

# Setup-time dependencies
setup_requires = [
    'pytest-runner>=4.2.0,<5.0.0',
    'setuptools_scm',
]

setup(
    name=package_name,
    description=description,
    long_description=readme.read_text(),
    author=author,
    author_email=author_email,
    url=url,
    license=license,
    classifiers=pypi_classifiers,
    keywords=keywords,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=install_requires,
    tests_require=tests_require,
    setup_requires=setup_requires,
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'templatebot-aide = templatebotaide.cli:main'
        ]
    },
    use_scm_version=True,
    include_package_data=True
)
