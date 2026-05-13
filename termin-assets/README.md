# termin-assets

Shared asset-system contracts for Termin.

This package is intentionally small at this stage. It provides the neutral
interfaces used by asset plugins and file preloading while the current concrete
asset implementations still live in `termin-app`.

The plugin API separates two roles:

- runtime plugins register and reload already discovered assets;
- import plugins turn files into preload results for editor/watch/build flows.

A concrete plugin may temporarily implement both roles while an asset type is
being migrated, but the contracts keep the runtime surface independent from
editor-only import tooling.
