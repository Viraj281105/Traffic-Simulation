"""Reinforcement-learning signal control for one junction (F18, W34-W40).

Everything here sits *beside* the simulation domain: it drives a normal
:class:`~src.engine.simulation_engine.SimulationEngine` through a controller
that obeys an external phase request, and never changes engine behaviour.

Optional dependencies (``backend/requirements-rl.txt``) are imported lazily:
``gymnasium`` and ``numpy`` for the environment, ``stable-baselines3`` for
training, ``mlflow`` for tracking. Importing this package needs none of them.
"""
