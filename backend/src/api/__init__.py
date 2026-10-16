"""The delivery layer's shared HTTP plumbing.

* ``auth``           -- Cognito JWT verification, the dev bypass and the
  identity dependencies (``get_current_user_id`` and friends);
* ``security``       -- the API-key guard (``require_api_key``);
* ``errors``         -- the uniform error envelope;
* ``origins``        -- CORS origins and the WebSocket origin/close helpers;
* ``ws_origin``      -- which browser origins may open a WebSocket;
* ``request_limits`` -- body-size cap, pagination and study-duration bounds,
  the synchronous-compute slot;
* ``validation``     -- configuration and scenario failures worded as 400s;
* ``meta``           -- /health, /api/version, /api/me, /api/users.

Nothing here knows about a particular resource; each resource's routes live
with the package that owns it (``live/``, ``simulations/``, ``study/``, ...)
and ``main.py`` mounts them.
"""
