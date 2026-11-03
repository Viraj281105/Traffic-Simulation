"""Seed derivation for multi-seed studies.

A study is given one *base seed*; the seed of each repetition is derived from
it, so the whole set is a pure function of ``(base_seed, n)`` and a study can be
repeated exactly from the base seed recorded in its result.

The construction (SHA-256 of a labelled string, first four bytes, 31 bits)
matches ``uncertainty.sampler.derive_seed`` but uses its own label: that
function's outputs are pinned by Robustness Lab fingerprints and must not
change, and the two seed families should not coincide.
"""

import hashlib
from typing import List

SEED_SCHEME = "sha256-v1"

# Engine seeds are stored as SQLite integers and exchanged as JSON numbers;
# 31 bits is the width the rest of the project uses (uncertainty/sampler.py).
MAX_SEED = 2**31 - 1


def derive_run_seeds(base_seed: int, count: int) -> List[int]:
    """``count`` distinct engine seeds derived from ``base_seed``, in order.

    Deterministic and independent of ``count``: the first ``k`` seeds of a
    longer list equal the seeds of a ``k``-run study with the same base seed.
    """
    if not 0 <= base_seed <= MAX_SEED:
        raise ValueError(f"base_seed must lie in [0, {MAX_SEED}]")
    if count < 0:
        raise ValueError("count must not be negative")
    seeds: List[int] = []
    seen = set()
    for index in range(count):
        # A 31-bit collision between a handful of seeds is vanishingly rare,
        # but a repeated seed would silently halve a study's information, so
        # step to the next candidate for that index instead.
        attempt = 0
        while True:
            label = f"urbanflow-multiseed-v1:{base_seed}:{index}:{attempt}"
            digest = hashlib.sha256(label.encode()).digest()
            seed = int.from_bytes(digest[:4], "big") & MAX_SEED
            if seed not in seen:
                break
            attempt += 1
        seen.add(seed)
        seeds.append(seed)
    return seeds
