# Building

This starter consumes the installed CWhip SDK; it does not build or download
the compiler or SDK for you. Use the complete SDK installation prefix, not
just its `bin/` directory. CMake requires SDK version `0.0.2` (exactly), its
`Cwhip_SDK_ABI` identifier must be `numeric-v2`, and it must be an
installation that supports configurable application output directories and
provides `cwhip_apply_application_defaults()`.

If configuration reports a missing application-defaults capability, rebuild
and reinstall an updated Cwhip SDK at the prefix shown in the error, then
configure again. Updating or merging the Cwhip source checkout alone does not
update an existing SDK installation.
Alternatively, select an already updated installation with `CWHIP_SDK`.
The template rejects older SDKs rather than silently omitting application
defaults.

## Numeric-v2 migration

This template depends on the numeric execution work in
[chucktilbury/cwhip#25](https://github.com/chucktilbury/cwhip/pull/25) and the
subsequent numeric-v2 SDK/package migration. Until that SDK is published, use
an explicitly selected rebuilt development SDK; the old installed SDK is not
compatible. The hello-world starter has no numeric declarations, native
examples, or checked-in package manifests to migrate.

For applications derived from the template, replace removed Cwhip types `int`,
`unsigned`, and `float` with `int64`, `uint64`, and `fp64` where preserving the
old width is intended. All fixed-width types are supported: `int8/16/32/64`,
`uint8/16/32/64`, and `fp32/64`. String parsers are now `toInt8/16/32/64`,
`toUint8/16/32/64`, and `toFp32/64`. These slash-separated names describe
individual methods, such as `toInt64()` and `toFp64()`.

Integer literals now start at the smallest fitting width, and unsuffixed
floating literals start at fp32. Widen operands before arithmetic when needed:
`int64(127) + 1` avoids the int8 overflow in `127 + 1`, while `0.1f64`
preserves fp64 literal precision rather than widening an already rounded
fp32 value. Destination types do not widen intermediate expressions.

Rebuild every native module against the new SDK using the matching exact-width
C types (and `float`/`double` for fp32/fp64); C itself still uses C type names.
Only after rebuilding, declare `sdk-abi = "numeric-v2"` in each package's
`[package]` table in `cwhip-package.toml`. The SDK rejects missing or stale
package ABI metadata. The SDK application helper generates project metadata
and a lockfile in the build tree using its own package tool; do not copy an old
generated project or relabel stale native artifacts.

## Select an SDK

Direct `cmake -S . -B build` and `scripts/setup` select the SDK in this exact
order:

1. An explicit, non-empty `CWHIP_SDK` environment variable.
2. The top-level TOML string `sdk_prefix` in
   `$XDG_CONFIG_HOME/cwhip/sdk.toml`, or
   `$HOME/.config/cwhip/sdk.toml` when `XDG_CONFIG_HOME` is unset/empty.
3. The legacy `settings.toml` file in that same directory, **only if
   `sdk.toml` is absent**.
4. Normal CMake package discovery, including `CMAKE_PREFIX_PATH` and
   `Cwhip_DIR`, when neither selection is present.

For example, the dedicated SDK configuration file `cwhip/sdk.toml` can contain:

```toml
sdk_prefix = "/absolute/path/to/installed/sdk"

[applications]
install_prefix = "/absolute/path/to/common/application/install"
build_type = "Release"
```

This matches the compiler installer's SDK registration location and keeps SDK
selection separate from editor/debugger preferences in `settings.toml`.
Rewriting those preferences cannot erase the dedicated SDK selection.
A non-empty `XDG_CONFIG_HOME` must be absolute and selects the only config root:
a missing file there does not fall back to the home settings file.
If neither `XDG_CONFIG_HOME` nor `HOME` is available, the template retains
normal CMake discovery. An explicit `CWHIP_SDK` bypasses config-home lookup.

The Cwhip installer records `[applications].install_prefix` and
`[applications].build_type` in `sdk.toml` after a successful install that is
not using `DESTDIR`. The install prefix is the common, non-`DESTDIR`
application install location; the build type is the CMake configuration used
for the SDK. A staged `DESTDIR` install does not register staged paths as
defaults.

The top-level `sdk_prefix` is the **whole SDK installation prefix**, not its
`bin/` directory or the CMake package directory. Paths with spaces and
TOML-escaped quotes are preserved; TOML literal strings are also supported.
A settings prefix must be a non-empty absolute path to an existing directory,
without NUL or line breaks. Python 3.11+ (`tomllib`) is required only when
reading an existing settings file; `scripts/setup` uses `python3`, while
direct CMake configuration uses CMake's Python3 interpreter discovery.

To temporarily override the shared setting:

```sh
export CWHIP_SDK="/path/to/cwhip-sdk"
./scripts/setup
```

An explicit non-empty `CWHIP_SDK` bypasses both configuration files entirely, even
if they are malformed. An unset or empty override allows settings discovery.
A missing file or absent top-level key leaves normal CMake discovery unchanged.
An existing `sdk.toml` is authoritative even without a top-level `sdk_prefix`:
it never falls back to legacy preferences. An explicitly empty `sdk_prefix`
is invalid, not an instruction to use legacy preferences. Malformed TOML, an
invalid value, or an unreadable selected configuration file stops configuration
with a diagnostic; it does not silently select another SDK.

When either `CWHIP_SDK` or `sdk_prefix` selects a prefix, CMake searches only
that prefix and clears the previously cached `Cwhip_DIR`. A prefix without a
compatible Cwhip package fails configuration rather than falling back. To
return to normal CMake discovery, unset `CWHIP_SDK` and remove the
`sdk_prefix` setting from `sdk.toml` (or from legacy `settings.toml` if no
`sdk.toml` exists), and clear `Cwhip_DIR` in an existing build cache if
needed.

The template never edits user settings or copies the SDK into the project.

## Application defaults

Before enabling project languages, the template finds the Cwhip package and
calls `cwhip_apply_application_defaults()` from the selected SDK. This lets
the SDK distinguish unset cache entries from explicit values, including
explicit empty values. The helper seeds `CMAKE_INSTALL_PREFIX` and
`CMAKE_BUILD_TYPE` from the `[applications]` values in `sdk.toml` only when
the corresponding cache entry is absent; explicit `-D` options, environment
overrides, and all existing cache values take precedence.

Running `scripts/setup` without an argument preserves an existing build type
or inherits the SDK's registered default. An explicit `debug`, `release`, or
`profile` argument supplies `Debug`, `Release`, or `RelWithDebInfo` and
overrides the build type for that configure. Direct CMake configuration uses
the same SDK defaults and respects its normal explicit/cache precedence. The
helper does not create a shared build directory or supply arbitrary compiler
flags.

## Configure and build

The setup script configures the `build/` directory and launches an interactive
project shell there. Its optional build type argument is an explicit override:

| Argument | CMake build type |
| --- | --- |
| `debug` | `Debug` |
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
It also rejects old/newer SDK versions and missing or incompatible ABI markers
before setup can enter a project shell.

To additionally build and install a temporary copy of the starter, execute both
its built and installed hello-world binaries, and check generated package ABI
metadata and stale-package rejection against a real SDK:

```sh
CWHIP_TEST_SDK=/absolute/path/to/numeric-v2/sdk \
  python3 -m unittest discover -s tests -v
```

This opt-in check uses a private temporary install prefix and isolated home
and XDG directories. It does not write to the SDK or user configuration.
