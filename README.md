# Landscape Client Charm

Docs have moved to [Charmhub](https://charmhub.io/landscape-client).

## Developing

Lint and run tests:

```sh
make check
make test
```

Format code automatically:

```sh
make lint
```

Build charm:

```sh
make build
```

Ubuntu 26.04 builds require Charmcraft 4.1 or newer.

Set `PLATFORM` to build for another declared Ubuntu platform, for example
`PLATFORM=ubuntu@24.04:amd64 make build`.
