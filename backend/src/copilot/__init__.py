"""AI Traffic Experiment Copilot (V3.0 W5, strategy section 15.1).

Question -> ``ExperimentIntent`` (deterministic keyword proposer, or a language model when one is configured)
-> deterministic builder -> ``urbanflow-experiment`` document -> validation boundary -> inspect-and-confirm ->
ordinary ``/api/v3/experiments`` submission. Interpretation of a measured result is a template summary,
optionally rewritten by the model and kept only if it passes the grounding check.

Nothing the model returns is executed: it only fills a small intent document whose every field has bounds,
and the experiment built from it passes the same validation as any request.
"""
