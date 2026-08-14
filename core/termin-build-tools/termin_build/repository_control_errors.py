"""Shared errors for repository control-plane modules."""


class ManifestError(ValueError):
    """Raised when repository control-plane metadata is invalid."""
