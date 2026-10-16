"""HTTP plumbing shared by every router: the API-key guard, the uniform error
envelope, the CORS/WebSocket origin policy and the translation of
configuration and scenario validation into 400 responses.

Nothing here knows about a particular resource; each resource's routes live
with the package that owns it (``live/``, ``simulations/``, ``study/``, ...)
and ``main.py`` mounts them. ``auth.py``, ``request_limits.py`` and
``ws_origin.py`` are delivery-layer modules too; they predate this package
and stay at the top level.
"""
