"""Physical limits shared by the strategy descriptors and the engine.

``strategies/`` is a leaf package (it may not import ``core/`` or ``roads/``),
while ``roads/`` may import it, so a limit both must agree on lives here and the
engine re-exports it rather than the descriptor mirroring a copy.
"""

from __future__ import annotations

# Ring lanes the V1.4 lane designation supports (roads/lane_config.py module
# docstring). The config schema accepts 3, but scenario validation rejects it as
# unsupported.
MAX_CIRCULATING_LANES: int = 2
