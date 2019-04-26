.PHONY: install
install:
	pip install -e ".[dev]"

.PHONY: test
test:
	pytest

.PHONY: dev
dev:
	adev runserver --app-factory create_app templatebotaide/app.py --port 8085

.PHONY: image
image:
	python setup.py sdist
	docker build --build-arg VERSION=`templatebot-aide --version` -t lsstsqre/templatebot-aide:build .

.PHONY: travis-docker-deploy
travis-docker-deploy:
	./bin/travis-docker-deploy.sh lsstsqre/templatebot-aide build

.PHONY: version
version:
	templatebot-aide --version
