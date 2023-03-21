# landscape-client


## Description

Landscape client is the daemon for Landscape server. This subordinate charm is intended to be used to register a machine against a running Landscape server. This charm uses the [Ops framework](https://juju.is/docs/sdk/ops)


## Usage

The minimal example to get started with [Landscape SAAS](https://landscape.canonical.com)

```
juju deploy landscape-client --channel edge --config computer-title=x1 --config account-name=foo-bar
juju deploy ubuntu --series jammy
juju relate landscape-client ubuntu
```

To install using a PPA

```
--config ppa=ppa:landscape/self-hosted-beta
```

To connect to a Landscape Self-Hosted instance

```
juju deploy landscape-client --channel edge \
    --config computer-title=helloworld \
    --config account-name=standalone \
    --config url=https://mydomain.com/message-system \
    --config ping-url=http://mydomain.com/ping \
```

However, when registering the client against a server with a custom or not well known
CA, we need to use the `ssl-public-key` option. To insert the certificate
contents into the charm config directly, encode it in base64 using the following syntax

```
--config ssl-public-key=base64:LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS4HY5RHZ6VWxUcDYwcjFNRmw1bG16M2I5a2dJeTVJeUYyUURCNnhXeEFMYXoKUGJwVCtnZ2NvYTN5Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0=
```

If the certificate is already present in the client machine then

```
--config ssl-public-key=/path/to/ca.cert
```

## Upgrading

It is recommended to use the PPA.

```
juju config landscape-client ppa=ppa:landscape/self-hosted-beta
```

The charm upgrade action can be run as shown where `landscape-client/0` is the desired unit.
```
juju run-action landscape-client/0 upgrade --wait
```

## Relations

Since this is a subordinate charm, a relation is required.  (Breaking the relation via `remove-relation` will disable the client.)

In the following example the [Ubuntu Charm](https://charmhub.io/ubuntu) is used.

```
juju deploy landscape-client --channel edge --config computer-title=x1 --config account-name=foo-bar
juju deploy ubuntu --series jammy
juju relate landscape-client ubuntu
```

This is accomplished using the `juju-info` interface. More information is available [here](https://juju.is/docs/sdk/relations#heading--implicit-relations).


## Source Code

The code for this updated version of the charm is in <https://github.com/CanonicalLtd/landscape-client-charm>


## Development

Make your code modifications and ensure that the options `bundle.yaml` are correct. Then

``
make build
`` 

To run linting and tests, `cd` into the top level directory and

```
sudo apt install tox
tox
```

The following commands may also be helpful:

```
juju status --watch 1s
juju debug-log --include landscape-client
```
