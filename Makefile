PLATFORM ?= ubuntu@24.04:amd64

.PHONY: test
test:
	uv run pytest --tb native tests/unit

.PHONY: integration-test
integration-test:
	uv run --group integration pytest -v --tb native tests/integration

.PHONY: coverage
coverage:
	uv run coverage run --branch --source=src -m pytest -v --tb native tests/unit
	uv run coverage report

.PHONY: check
check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run codespell src tests

.PHONY: lint
lint:
	uv run ruff check --fix src tests
	uv run ruff format src tests

.PHONY: build
build: clean
	charmcraft pack --platform $(PLATFORM)
	juju add-model testclient
	juju deploy ./bundle.yaml

.PHONY: clean
clean:
	-rm *.charm
	-juju destroy-model --no-prompt testclient --force
