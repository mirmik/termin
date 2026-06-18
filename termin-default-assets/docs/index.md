# termin-default-assets

Default asset adapters for Termin SDK.

This package owns the standard `termin-assets` integrations for domain data
packages. Domain packages such as `tmesh` should remain usable without the
project asset runtime.

Current adapters:

- `termin.default_assets.mesh.MeshAsset`
- mesh import/runtime plugins for `.obj` and `.stl`
- mesh import specs and OBJ/STL loaders
