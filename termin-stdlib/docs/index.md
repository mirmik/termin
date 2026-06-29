# termin-stdlib

Termin standard library resources and deployment helpers.

This package owns the SDK stdlib resource tree distributed into projects under
`<project>/stdlib`: standard materials, shader descriptors, Slang modules, and
standard UI scripts.

Runtime/editor code should use `termin.stdlib.stdlib_root()` to locate the
installed resource root and `termin.stdlib.sync_stdlib()` to deploy resources
into a project. Other packages should not derive this path from the root
`termin` namespace package.
