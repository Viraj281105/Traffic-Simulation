"""Control Strategy Discovery Lab (V3.0 W6, strategy section 15.2).

Bounded multi-objective evolutionary search (NSGA-II-style non-dominated sorting with crowding distance)
over the parameters of the registered control strategies, for one declared traffic regime. It is a
black-box optimiser, not a learned model, and every candidate it reports is EXPERIMENTAL: tuned to this
simulator under the declared assumptions, evaluated against the unchanged baselines on held-out seeds that
the search never saw.
"""
