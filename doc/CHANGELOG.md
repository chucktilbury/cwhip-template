# Changelog

## Unreleased

- Add the standard MIT license.
- Add a CWhip hello-world starter with a project setup script and interactive
  development shell.
- Configure CMake to discover an installed CWhip 0.0.1 SDK, support explicit
  SDK selection, and place application/native outputs in configurable
  project directories.
- Document SDK selection, building, output customization, and project-shell
  commands.

The starter requires a CWhip SDK that provides configurable application
output directories. SDKs without the `Cwhip_APPLICATION_OUTPUT_DIRECTORIES`
capability are rejected during configuration.
