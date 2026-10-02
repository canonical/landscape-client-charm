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

Set `PLATFORM` to build for another declared Ubuntu platform, for example
`PLATFORM=ubuntu@22.04:amd64 make build`.
