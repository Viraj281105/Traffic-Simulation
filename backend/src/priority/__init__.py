"""Emergency and transit priority on the single-junction simulation (F12).

Built on top of the engine without modifying it: the junction's fixed-time
controller is wrapped (``controller.PriorityController``), emergency and transit
vehicles are injected on a schedule, and with-versus-without comparisons run
over seeds with the repository's paired statistics (``comparison``).

Results are in-model only.
"""
