"""Compatibility import for the canonical component API router.

The live application registers :mod:`app.api.modules`; keeping a second,
outdated implementation here previously referenced schemas and CRUD functions
that no longer exist.
"""

from app.api.modules import router


__all__ = ["router"]
