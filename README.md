# CWhip project template

A small starter project for building CWhip applications against an installed
CWhip SDK. The example program lives in `src/main.cw`; CMake builds it into the
project's `bin/` directory.

## Get started

Install the complete CWhip SDK prefix and its host prerequisites. SDK selection
uses a non-empty `CWHIP_SDK` override first, then the top-level `sdk_prefix`
string in `$XDG_CONFIG_HOME/cwhip/sdk.toml` (or
`$HOME/.config/cwhip/sdk.toml` when `XDG_CONFIG_HOME` is unset/empty).
Only when `sdk.toml` is absent is the legacy `settings.toml` consulted.
Without a selected prefix, use normal CMake discovery
through `CMAKE_PREFIX_PATH` or `Cwhip_DIR`. Both direct CMake configuration and
`scripts/setup` use this order. Reading settings requires Python 3.11+.
Then start the project shell and build:

```sh
./scripts/setup
cmake --build .
../bin/hello
```

With no setup argument, the project inherits the SDK's registered application
build type when available. Pass `debug`, `release`, or `profile` to explicitly
select a build type, for example `./scripts/setup release`.

See [Building](doc/BUILDING.md) for SDK selection and output-directory
customization and application defaults, and [Project shell](doc/PROJECT-SHELL.md)
for the shell environment and available commands. See the
[changelog](doc/CHANGELOG.md) for template updates.
