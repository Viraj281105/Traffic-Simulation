"""The simulation runtime: the tick loop (SimulationEngine), the vehicle pool
that moves every vehicle through the conflict layers, the deadlock detector,
and the tick callback that feeds a metric collector.

Top of the simulation domain: it may import core, roads, vehicles,
intersection, controllers and metrics; only snapshot/ and the application
layer import it (tests/test_architecture.py).
"""
