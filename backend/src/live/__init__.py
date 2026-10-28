"""The live dashboard: per-client sessions that each hold one live simulation
and one signal-vs-roundabout comparison, the dashboard's flat scenario
payload and how it compiles into an engine configuration, and the
``/api/simulation/*`` and ``/ws/simulation/*`` routes that drive them.

``dashboard_config`` is plain configuration logic; ``sessions`` owns the
in-memory session registry; ``capture`` reads an exact, reproducible record
of a session's run; ``router`` is the HTTP/WebSocket surface.
"""
