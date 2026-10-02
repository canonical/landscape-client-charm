# Landscape Client Charm

Docs have moved to [Charmhub](https://charmhub.io/landscape-client).

## Developing

Lint and run tests:

```sh
tox run
```

Format code automatically:

```sh
tox run -e fmt
```

Build charm:

```sh
make build
```

Set `PLATFORM` to build for another declared Ubuntu platform, for example
`PLATFORM=ubuntu@22.04:amd64 make build`.
