# CWhip project template

A small starter project for building CWhip applications against an installed
CWhip SDK. The example program lives in `src/main.cw`; CMake builds it into the
project's `bin/` directory.

## Get started

Install the complete CWhip SDK prefix and its host prerequisites. SDK selection
uses a non-empty `CWHIP_SDK` override first, then the top-level `sdk_prefix`
string in `$HOME/.config/cwhip/settings.toml`, then normal CMake discovery
through `CMAKE_PREFIX_PATH` or `Cwhip_DIR`. Both direct CMake configuration and
`scripts/setup` use this order. Reading settings requires Python 3.11+.
Then start the project shell and build:

```sh
./scripts/setup
cmake --build .
../bin/hello
```

The default build type is `debug`. Choose `release` or `profile` with
`./scripts/setup release` or `./scripts/setup profile`.

See [Building](doc/BUILDING.md) for SDK selection and output-directory
customization, and [Project shell](doc/PROJECT-SHELL.md) for the shell
environment and available commands. See the [changelog](doc/CHANGELOG.md) for
template updates.
