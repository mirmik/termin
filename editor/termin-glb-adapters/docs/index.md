# termin-glb-adapters

Termin-owned integration for the portable `termin-glb` domain.

The distribution owns:

- `GLBAsset` and asset discovery/runtime plugins;
- `Entity`, render-component and material instantiation;
- serialized scene animation repair.

It depends on `termin-assets`, scene/ECS and component packages. None of these
dependencies are part of the portable `termin-glb` wheel.
