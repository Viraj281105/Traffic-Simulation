"""Digital twin core (F14, package 1E): observations in, predictions out.

``sources`` reads observations (replay now, a live feed later), ``runner``
drives the network simulator with the demand the latest observations imply
and keeps a prediction timeline, ``compare`` scores predictions against
observations, ``whatif`` forks the twin's state into a scenario variant.
"""
