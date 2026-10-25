# CWhip project template

A small starter project for building CWhip applications against an installed
CWhip SDK. The example program lives in `src/main.cw`; CMake builds it into the
project's `bin/` directory.

`src/` contains a small greeting class, a bound-method callable, and a
multiline dictionary using current Cwhip syntax. `scripts/` provides SDK
discovery and project-shell commands; `tests/` covers discovery and opt-in
build/install checks against a real SDK.

See [Building](doc/BUILDING.md) for prerequisites, SDK selection, build/run/test
commands, and output customization; [Syntax](doc/SYNTAX.md) for the example
and migration notes; [Project shell](doc/PROJECT-SHELL.md) for the interactive
environment; and the [changelog](doc/CHANGELOG.md) for template updates.
