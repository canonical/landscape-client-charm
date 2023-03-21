build: clean
	charmcraft pack
	juju add-model testclient
	juju deploy ./bundle.yaml

clean:
	-rm *.charm
	-juju destroy-model -y testclient --force
