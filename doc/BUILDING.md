# Building

This starter consumes the installed CWhip SDK; it does not build or download
the compiler or SDK for you. Use the complete SDK installation prefix, not
just its `bin/` directory. CMake requires SDK version `0.0.1` and an
installation that supports configurable application output directories.

## Select an SDK

Direct `cmake -S . -B build` and `scripts/setup` select the SDK in this exact
order:

1. An explicit, non-empty `CWHIP_SDK` environment variable.
2. The top-level TOML string `sdk_prefix` in
   `$XDG_CONFIG_HOME/cwhip/settings.toml`, or
   `$HOME/.config/cwhip/settings.toml` when `XDG_CONFIG_HOME` is unset/empty.
3. Normal CMake package discovery, including `CMAKE_PREFIX_PATH` and
   `Cwhip_DIR`, when neither selection is present.

For example, a shared user settings file can contain:

```toml
sdk_prefix = "/absolute/path/to/installed/sdk"
```

This matches the compiler installer's settings location. A non-empty
`XDG_CONFIG_HOME` must be absolute and selects the only settings location:
a missing file there does not fall back to the home settings file.
If neither `XDG_CONFIG_HOME` nor `HOME` is available, the template retains
normal CMake discovery. An explicit `CWHIP_SDK` bypasses config-home lookup.

The value is the **whole installation prefix**, not its `bin/` directory or
the CMake package directory. Paths with spaces and TOML-escaped quotes are
preserved; TOML literal strings are also supported. A settings prefix must
be a non-empty absolute path to an existing directory, without NUL or line
breaks. Python 3.11+ (`tomllib`) is required only when reading an existing
settings file; `scripts/setup` uses `python3`, while direct CMake configuration
uses CMake's Python3 interpreter discovery.

To temporarily override the shared setting:

```sh
export CWHIP_SDK="/path/to/cwhip-sdk"
./scripts/setup
```

An explicit non-empty `CWHIP_SDK` bypasses the settings file entirely, even
if it is malformed. An unset or empty override allows settings discovery.
A missing file or absent top-level key quietly leaves normal CMake discovery
unchanged. Malformed TOML, an invalid value, or an unreadable settings file
stops configuration with a diagnostic; it does not silently select another SDK.

When either `CWHIP_SDK` or `sdk_prefix` selects a prefix, CMake searches only
that prefix and clears the previously cached `Cwhip_DIR`. A prefix without a
compatible Cwhip package fails configuration rather than falling back. To
return to normal CMake discovery, unset `CWHIP_SDK` and remove the
`sdk_prefix` setting (and clear `Cwhip_DIR` in an existing build cache if
needed).

The template never edits user settings or copies the SDK into the project.

## Configure and build

The setup script configures the `build/` directory and launches an interactive
project shell there. Its build type argument is optional:

| Argument | CMake build type |
| --- | --- |
| `debug` (default) | `Debug` |
| `release` | `Release` |
| `profile` | `RelWithDebInfo` |

Build and run the example from the project shell:

```sh
cmake --build .
../bin/hello
```

The Cwhip application helper writes generated sources and package metadata
inside the build tree. The compiled application is written directly to
`bin/`. Neither `bin/` nor `lib/` is created during configuration; the build
creates an output directory only when a target needs it.

## Customize output directories

The cache variables `CWHIP_BIN_DIR` and `CWHIP_LIB_DIR` choose output
locations. They default to the project-root `bin/` and `lib/`; native runtime
targets use the former, and native library/archive targets use the latter.
For example:

```sh
cmake -S . -B build \
  -DCWHIP_BIN_DIR="$PWD/out/bin" \
  -DCWHIP_LIB_DIR="$PWD/out/lib"
cmake --build build
```

The starter Cwhip executable follows `CWHIP_BIN_DIR`. Generated output
directories are ignored by Git.

## Clean

Use CMake's normal clean target to remove generated build artifacts:

```sh
cmake --build build --target clean
```

Rebuilding recreates the required output directories.

## Test template discovery

Run the discovery regression suite with Python 3.11+, CMake 3.24+, and a host
C compiler:

```sh
python3 -m unittest discover -s tests -v
```

The suite uses temporary mock SDK packages and isolated home directories.
It exercises real CMake configuration, setup's shell handoff, and the shell's
SDK search path without requiring an installed CWhip compiler or user input.
