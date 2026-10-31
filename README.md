# Cwhip project template

`cwhip-template` is a small starter for Cwhip applications against an installed
SDK. Source:
[github.com/chucktilbury/cwhip-template](https://github.com/chucktilbury/cwhip-template).
`cwhip-pkg new` downloads this repository and rewrites the heading above to the
new project name.

This directory contains the example program in `src/main.cw`, CMake that builds
it into `bin/`, tests in `tests/`, and SDK discovery helpers in `scripts/`.

With a current Cwhip SDK installed, run `scripts/setup [--clean] [debug|release|profile]`
from the checkout, then `build` in the project shell. Use `rebuild` for a
clean-first build, or `clean` to remove generated outputs; exit the shell before
running setup again.

```sh
./scripts/setup [--clean] [debug|release|profile]
build
../bin/hello
```

- [Building](doc/BUILDING.md)
- [Syntax](doc/SYNTAX.md)
- [Project shell](doc/PROJECT-SHELL.md)
- [Changelog](doc/CHANGELOG.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
