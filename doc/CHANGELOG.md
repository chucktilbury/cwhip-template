# Changelog

## Unreleased

- Require Cwhip SDK 0.0.2 and its `numeric-v2` ABI; reject missing or
  incompatible SDK markers before applying application defaults. Update mock
  SDKs, add version/ABI rejection coverage and an opt-in real-SDK private
  build/install check, and document source and native-package migration.
- Inherit application install-prefix and build-type defaults registered by the
  Cwhip SDK, while preserving explicit CMake settings and existing cache
  values. Setup's optional build-type argument is now an explicit override.
- Separate SDK selection into `cwhip/sdk.toml` so editor/debugger preference
  rewrites cannot erase it. Read legacy `settings.toml` only when the dedicated
  file is absent, consistently in CMake and setup. Keep environment overrides,
  strict validation, and explicit-prefix-only package discovery.
- Retain compatibility with the whole installed SDK prefix from the top-level `sdk_prefix`
  string in `$XDG_CONFIG_HOME/cwhip/settings.toml` (or
  `$HOME/.config/cwhip/settings.toml` when `XDG_CONFIG_HOME` is unset/empty)
  in both CMake and setup when `sdk.toml` is absent.
  Preserve precedence: non-empty `CWHIP_SDK` > SDK config (or legacy settings) > normal CMake
  discovery. Parse TOML with Python 3.11+ without evaluating or modifying
  user settings, and reject invalid selections without falling back.
- Export a settings-selected SDK to the setup shell and add regression
  coverage for discovery precedence, TOML paths, errors, and shell handoff.
- Add the standard MIT license.
- Add a CWhip hello-world starter with a project setup script and interactive
  development shell.
- Configure CMake to discover an installed CWhip 0.0.1 SDK, support explicit
  SDK selection, and place application/native outputs in configurable
  project directories.
- Document SDK selection, building, output customization, and project-shell
  commands.

The starter requires a CWhip SDK that provides configurable application
output directories and `cwhip_apply_application_defaults()`. SDKs without
these capabilities are rejected during configuration.
