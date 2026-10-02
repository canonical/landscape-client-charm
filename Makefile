PLATFORM ?= ubuntu@24.04:amd64

.PHONY: build
build: clean
	charmcraft pack --platform $(PLATFORM)
	juju add-model testclient
	juju deploy ./bundle.yaml

.PHONY: clean
clean:
	-rm *.charm
	-juju destroy-model --no-prompt testclient --force
