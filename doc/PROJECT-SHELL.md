# Project shell

Run `scripts/setup [--clean] [debug|release|profile]` from any working directory to
configure this project and start its interactive Bash shell. The script
locates the project relative to itself, so it does not depend on the caller's
current directory. Without an argument, the configured build type is inherited
from the SDK application default or the existing build cache. An explicit
argument overrides it.

`--clean` may appear before or after the build type. It invokes `scripts/clean`
before configuration, removing the project's `bin/`, `build/`, `lib/`,
`doc/out/`, and `share/` directories, including the previous CMake cache.
Without a build type, a clean setup therefore inherits the SDK default rather
than the deleted cache. Sources and user configuration are not removed.

SDK selection follows `CWHIP_SDK` (non-empty) > the dedicated SDK file's
top-level `sdk_prefix` > normal CMake discovery. SDK configuration lives at
`$XDG_CONFIG_HOME/cwhip/sdk.toml`, falling back to
`$HOME/.config/cwhip/sdk.toml` only when `XDG_CONFIG_HOME` is unset/empty.
Only if `sdk.toml` is absent is legacy `settings.toml` in the same directory
consulted. An existing SDK file without `sdk_prefix` means normal discovery;
an empty or invalid value fails rather than falling back to preferences.
Reading an existing settings file requires Python 3.11+.
See [Building](BUILDING.md#select-an-sdk) for the settings format and errors.
When settings select the SDK, setup exports that prefix as `CWHIP_SDK` to
CMake and the child shell; it does not modify settings or the calling shell.

The setup script configures before starting the shell. If configuration
fails, it reports the error and exits without opening a project shell.
Launching setup from an already initialized project shell is rejected to
avoid stacking project environments; this guard runs before any cleanup.
Unknown arguments, repeated options, or multiple build types report usage
and exit with status 2 without cleaning. Exiting the child Bash returns to the
shell from which setup was launched.

The project shell sources `~/.bashrc` when readable, adds the project's
`bin/` and `scripts/` directories to `PATH`, and starts in `build/`. If
`CWHIP_SDK` is set, its `bin/` directory is also added to `PATH` after the
project directories so the SDK compiler and package tools are available.
This includes a prefix discovered from user settings by setup.

The shell exports:

| Variable | Meaning |
| --- | --- |
| `_PROJECT_NAME` | Project directory name |
| `_PROJECT_LOC` | Absolute project root |
| `_BUILD_TYPE` | Lowercase configured type (`debug`, `release`, or `profile` for the standard configurations; `default` if unset) |
| `CWHIP_BUILD_TYPE` | Configured CMake build type, or empty if unset |

Build commands are available in the project shell:

| Command | Action |
| --- | --- |
| `build [TARGET...]` | Build all default targets or the supplied targets with 12 parallel jobs |
| `rebuild [TARGET...]` | Clean the configured targets first, then build with 12 parallel jobs |
| `clean` | Delete the project's generated build and staging directories |

`build` and `rebuild` are Bash functions in `.project_env`, not standalone
scripts. They use `${_PROJECT_BUILD_DIR:-$_PROJECT_LOC/build}` regardless of
the current directory, preserve target arguments, and return CMake's exit
status without exiting the shell. `clean` remains `scripts/clean` and removes
the build directory too; exit the project shell and run `scripts/setup` again
after using it. Use `rebuild` to clean and build without deleting the cache.

Repository convenience commands are also available:

| Command | Action |
| --- | --- |
| `status [args...]` | Run `git status` |
| `add [pathspec...]` | Stage the supplied pathspecs, or `.` when omitted |
| `commit [args...]` | Run `git commit` |
| `push [args...]` | Run `git push` |
| `all [commit args...]` | Explicitly stage all changes, commit, then push |
| `dbg [args...]` | Run `cdbg` with the supplied source or executable arguments |

These commands do not run automatically. In particular, entering the shell
does not stage, commit, or push changes.
