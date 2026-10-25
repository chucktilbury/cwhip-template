# Current Cwhip syntax

The starter in [`src/main.cw`](../src/main.cw) prints `Hello, world!` followed
by a newline. `Greeter.message` returns a managed `String` with
`return(expression)`. The start block constructs a greeter, captures its bound
method in a `String<String>` callable, and invokes it with the name read from
a dictionary.

Callable types spell the result first, followed by parameter types:
`R<P1,P2>`, or `R<>` for no parameters. Capturing `greeter.message` does not
invoke the method; `greeting(...)` invokes the captured method and retains its
receiver. Recursive callable types are supported. The former
`callback<R(P...)>` spelling is no longer a type; `callback` is an ordinary
identifier.

## Migration checklist

- Use `#`, `//`, or `/* ... */` for comments. Semicolons are not Cwhip comments
  or statement separators; leave semicolons in native/inline C unchanged.
- Dictionaries use `[key: value]`, including multiline entries and trailing
  commas as shown in the starter. `[:]` is an empty dictionary; `[]` is an
  empty list. Lists also support multiline entries and trailing commas.
- Return a value with `return(expression)`. Bare `return` and `return()` are
  void returns. Use `raise(expression)` or `raise()` to rethrow, and put
  keyword parameters in parentheses, such as `if (condition)` and
  `for (item in items)`.
- Conditional chains use `if (condition) { ... } else (condition) { ... }`
  followed by an optional final `else { ... }`, not `else if`.
- Bitwise operators bind more tightly than comparisons, in the order shifts,
  `&`, `^`, `|`, then comparisons. Write `(flags & mask) == expected` for an
  explicit bitmask test. Audit mixed expressions and use parentheses to
  preserve the intended grouping.
- Prefer explicit-width numeric types when widths matter. `int`, `uint`, and
  `float` are aliases for `int32`, `uint32`, and `fp32`, not their old 64-bit
  meanings. `unsigned` is reserved. See [Building](BUILDING.md#numeric-v2-migration)
  for numeric and native-package migration.
- Class fields may have compile-time constant initializers. Keywords are
  case-insensitive; the starter uses lowercase keywords consistently.
  `and`/`&&`, `or`/`||`, and `not`/`!` are equivalent spellings.

The compiler's [grammar](https://github.com/chucktilbury/cwhip/blob/master/doc/GRAMMAR.md)
and [language reference](https://github.com/chucktilbury/cwhip/blob/master/doc/LANGUAGE-REFERENCE.md)
are the authoritative syntax references. [Building](BUILDING.md#test-template-discovery)
describes the isolated real-SDK check that builds and runs this source both
before and after installation.
