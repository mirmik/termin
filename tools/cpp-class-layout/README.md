# C++ Class Layout Checker

`termin-cpp-class-layout` checks the repository rule documented in
[`docs/cpp-style.md`](../../docs/cpp-style.md): data members of a C++ class or
struct are declared before its member functions.

The checker uses Clang LibTooling and the repository compilation database. It
reports one record per violating class and deduplicates definitions from headers
included by multiple translation units.

## Dependencies

Ubuntu with LLVM 18:

```bash
sudo apt-get install libclang-18-dev llvm-18-dev
```

## Repository runner

Generate the compilation database when needed:

```bash
task lint:cpp -- --configure-only
```

Run the checker:

```bash
task check:cpp-layout
```

Limit diagnostics to selected repository paths:

```bash
task check:cpp-layout -- --path termin-render --path termin-graphics
```

`--path` filters declarations in the report, not translation units in the
compilation database. The checker still parses every repository-owned C++
translation unit so that headers reached through consumers in other modules are
not missed.

Generate a JSONL migration inventory without failing on violations:

```bash
task check:cpp-layout -- --format jsonl --no-fail
```

Check the separate Python/nanobind compilation profile with:

```bash
task lint:cpp -- --python-bindings --configure-only
task check:cpp-layout -- --python-bindings --no-fail
```

The runner builds the isolated tool in `build/cpp-class-layout-checker`. Set
`CPP_CLASS_LAYOUT_TOOL_BUILD_DIR` or `CPP_CLASS_LAYOUT_COMPILE_DB_DIR` to
override the tool and compilation database directories. The checker uses four
analysis jobs by default; override this with `CPP_CLASS_LAYOUT_JOBS`.

Run the fixture tests with:

```bash
task check:cpp-layout -- --self-test
```
